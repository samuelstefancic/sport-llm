"""Import du catalogue fictif. Connexion PostgreSQL via PG* ou DATABASE_URL."""

import argparse
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re

import psycopg


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data/dev/catalog.json"
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,95}")
MICRONUTRIENT = re.compile(r"(vitamin|mineral)_[a-z][a-z0-9_]{0,40}")
GRAM_NUTRIENTS = {"protein", "carbohydrate", "fat", "fiber", "sugars", "salt"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Clé JSON répétée : {key}")
        result[key] = value
    return result


def fields(value, names, where):
    require(isinstance(value, dict) and set(value) == set(names.split()), f"Champs invalides : {where}")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


def nonnegative(value):
    # Les booléens JSON ne sont pas des quantités.
    return type(value) in (int, Decimal) and value >= 0


def parse_catalog(raw):
    doc = json.loads(raw.decode("utf-8"), parse_float=Decimal, object_pairs_hook=unique_keys)
    fields(doc, "catalog_id version fictitious purpose created_on provenance lineage missing_policy "
                "nutrient_definitions items", "catalogue")
    require(identifier(doc["catalog_id"]) and identifier(doc["version"]), "Catalogue ou version invalide")
    require(doc["fictitious"] is True and doc["purpose"] == "development_only", "Catalogue fictif requis")
    provenance = doc["provenance"]
    fields(provenance, "kind source not_real_food_reference usage", "provenance")
    require(provenance["kind"] == "project_authored_fiction" and provenance["not_real_food_reference"] is True
            and text(provenance["source"]) and text(provenance["usage"]), "Provenance fictive incomplète")
    require(text(doc["created_on"]) and date.fromisoformat(doc["created_on"]).isoformat() == doc["created_on"],
            "Date de création invalide")
    require(text(doc["missing_policy"]), "Politique des valeurs absentes manquante")
    lineage = doc["lineage"]
    require(isinstance(lineage, dict) and lineage and all(text(v) for v in lineage.values()),
            "Historique de version invalide")

    definitions = doc["nutrient_definitions"]
    require(isinstance(definitions, list) and definitions, "Aucune définition d’apport")
    units = {}
    for definition in definitions:
        fields(definition, "id label unit default", "définition d’apport")
        name, unit = definition["id"], definition["unit"]
        require(identifier(name) and name not in units, "Identifiant d’apport invalide ou répété")
        require(text(definition["label"]) and isinstance(definition["default"], bool), f"Définition invalide : {name}")
        require((name == "energy" and unit == "kcal") or (name in GRAM_NUTRIENTS and unit == "g")
                or (MICRONUTRIENT.fullmatch(name) and unit in ("mg", "ug")), f"Unité invalide : {name}")
        units[name] = unit

    foods, nutrients = [], []
    seen = set()
    require(isinstance(doc["items"], list) and doc["items"], "Aucune fiche alimentaire")
    for food in doc["items"]:
        fields(food, "food_id label state basis nutrients", "fiche")
        food_id = food["food_id"]
        require(identifier(food_id) and food_id not in seen, "Identifiant de fiche invalide ou répété")
        seen.add(food_id)
        require(text(food["label"]) and food["state"] in ("raw", "cooked", "not_applicable", "unknown"),
                f"Libellé ou état invalide : {food_id}")
        basis = food["basis"]
        fields(basis, "value unit", f"{food_id}.basis")
        require(nonnegative(basis["value"]) and basis["value"] > 0 and basis["unit"] == "g",
                f"Base de référence invalide : {food_id}")
        key = (doc["catalog_id"], doc["version"], food_id)
        foods.append((*key, food["label"], food["state"], basis["value"], basis["unit"]))
        cells = food["nutrients"]
        require(isinstance(cells, dict) and cells.keys() <= units.keys(), f"Apport non déclaré : {food_id}")
        for name, unit in units.items():
            value, availability = None, "absent"
            if name in cells:
                cell = cells[name]
                where = f"{food_id}.{name}"
                fields(cell, "value unit availability", where)
                value, availability = cell["value"], cell["availability"]
                require(cell["unit"] == unit, f"Unité incohérente : {where}")
                require((availability == "known" and nonnegative(value)) or (availability == "absent" and value is None),
                        f"Valeur incompatible avec sa disponibilité : {where}")
            nutrients.append((*key, name, unit, value, availability))
    return doc["catalog_id"], doc["version"], foods, nutrients


def import_catalog(connection, raw):
    with connection.transaction(), connection.cursor() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        db.execute("CREATE TEMP TABLE catalog_stage (raw bytea NOT NULL) ON COMMIT DROP")
        db.execute("INSERT INTO catalog_stage VALUES (%s)", (raw,))
        staged = bytes(db.execute("SELECT raw FROM catalog_stage").fetchone()[0])
        catalog_id, version, foods, nutrients = parse_catalog(staged)
        digest = sha256(staged).hexdigest()
        key = (catalog_id, version)

        # Serialiser les publications d’un même catalogue, y compris sa toute première version.
        db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (catalog_id,))
        previous = db.execute(
            "SELECT source_sha256 FROM catalog_version WHERE catalog_id = %s AND version = %s", key
        ).fetchone()
        if previous is not None:
            require(previous[0] == digest, "Version existante avec une empreinte différente")
            return "already_imported", catalog_id, version, digest

        db.execute(
            """INSERT INTO catalog_version (catalog_id, version, source_sha256, document)
               SELECT %s, %s, %s, convert_from(raw, 'UTF8')::jsonb FROM catalog_stage""", (*key, digest)
        )
        db.executemany(
            """INSERT INTO catalog_food (catalog_id, version, food_id, label, state, basis_value, basis_unit)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""", foods
        )
        db.executemany(
            """INSERT INTO catalog_nutrient (catalog_id, version, food_id, nutrient_id, unit, value, availability)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""", nutrients
        )
        db.execute(
            """INSERT INTO catalog_active (catalog_id, version) VALUES (%s, %s)
               ON CONFLICT (catalog_id) DO UPDATE SET version = EXCLUDED.version""", key
        )
    return "activated", catalog_id, version, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", default=DEFAULT_SOURCE)
    parser.add_argument("--init-schema", action="store_true",
                        help="Initialiser une fois les tables avant la transaction d’import.")
    args = parser.parse_args()
    try:
        raw = args.source.read_bytes()
        with psycopg.connect(os.environ.get("DATABASE_URL", ""), autocommit=True) as connection:
            if args.init_schema:
                connection.execute(Path(__file__).with_name("schema.sql").read_text(), prepare=False)
            result = import_catalog(connection, raw)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Échec de l’import : {error}\n")
    except psycopg.Error as error:
        # Ne pas afficher la chaîne de connexion, ses paramètres ou le contenu de la source.
        parser.exit(1, f"Échec PostgreSQL : {type(error).__name__} ({error.sqlstate or 'connexion'})\n")
    print(*result)


if __name__ == "__main__":
    main()

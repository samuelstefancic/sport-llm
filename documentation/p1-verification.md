# P1 — Vérifications des chaînes applicatives

## Reproduction locale

Depuis la racine du clone, utiliser Java 17 ou supérieur, Maven, une base PostgreSQL de développement dédiée et un Python équipé de `python/requirements.txt`, `catalog/requirements.txt` et `jsonschema==4.26.0`. Les tests du journal créent et suppriment chacun leur propre schéma PostgreSQL. Configurer `PGHOST=127.0.0.1`, `PGPORT`, `PGDATABASE`, `PGUSER` et le moyen d’authentification local. Les scripts construisent le JAR avec Maven hors ligne lorsque les dépendances sont déjà en cache. Lancer les scripts successivement pour éviter deux constructions du même JAR en parallèle.

## T06 — Bilan alimentaire

`python -B scripts/verify_t06.py` lance l’API Java et le serveur FastAPI sur la boucle locale. `POST /meals` accepte la déclaration, l’identifiant, la révision et la sélection facultative des apports. `GET /meals/{id}/revisions/{r}` relit la version enregistrée. Java contrôle les fragments de la déclaration et les candidats reçus, consulte le catalogue actif, calcule en décimal et écrit le rapport avec sa provenance dans PostgreSQL. Une quantité corrigée peut être indiquée par son identifiant dans `corrected_mentions`.

| Oracle ou contrôle | Résultat observé |
|---|---|
| F02, catalogue fictif 0.2.0 | 415 kcal, 42,5 g de protéines, 46 g de glucides, 4,3 g de lipides. Tous complets. Rapport validé contre T03 puis relu par HTTP et SQL. |
| T03-SEL-001, variante historique isolée | Riz corrigé à 100 g, autres aliments déclarés. Protéines 34,5 g complètes, énergie 295 kcal partielles, sel 0 g partiel avec deux manques, glucides et lipides indéterminés. L’ancien rapport F02 reste lisible après activation de cette variante. |
| Ambiguïté et décimales | Le riz sans quantité provoque une clarification. Avec 12,5 g de riz, le résultat est 0,0375 g de lipides. |
| Validation | Un espace insécable seul reçoit HTTP 400. Une quantité Python portée à 150 g pour une déclaration de 100 g reçoit HTTP 502. Dans les deux cas, zéro résultat enregistré. |

Les règles de lecture en français couvrent des formulations bornées. Chaque référence de calcul porte sa fiche et sa version, distinctes du texte saisi. Régressions exécutées : P0 (25 exemples, 30 cas), T04 (HTTP et délai) et T05 (import, interruption et rejeu). [Oracles](../data/dev/oracles.md) · [Schéma](../contracts/analysis.schema.json) · [Cas du sel](../contracts/examples/java-salt-reference.json) · [Test HTTP et SQL](../scripts/verify_t06.py)

**Exercice T06.** Si seul le riz a une teneur en sel connue, quel statut et quelles preuves doivent accompagner une somme de zéro ?

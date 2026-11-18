BEGIN;

-- Évite deux créations concurrentes des tables lors du premier lancement.
SELECT pg_advisory_xact_lock(hashtextextended('llmsport:catalog:init:' || current_schema(), 0));

CREATE TABLE IF NOT EXISTS catalog_version (
    catalog_id text NOT NULL,
    version text NOT NULL,
    source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    document jsonb NOT NULL,
    PRIMARY KEY (catalog_id, version)
);

CREATE TABLE IF NOT EXISTS catalog_food (
    catalog_id text NOT NULL,
    version text NOT NULL,
    food_id text NOT NULL,
    label text NOT NULL,
    state text NOT NULL CHECK (state IN ('raw', 'cooked', 'not_applicable', 'unknown')),
    basis_value numeric NOT NULL CHECK (basis_value > 0),
    basis_unit text NOT NULL CHECK (basis_unit = 'g'),
    PRIMARY KEY (catalog_id, version, food_id),
    FOREIGN KEY (catalog_id, version) REFERENCES catalog_version
);

CREATE TABLE IF NOT EXISTS catalog_nutrient (
    catalog_id text NOT NULL,
    version text NOT NULL,
    food_id text NOT NULL,
    nutrient_id text NOT NULL,
    unit text NOT NULL CHECK (unit IN ('kcal', 'g', 'mg', 'ug')),
    value numeric,
    availability text NOT NULL,
    CHECK ((availability = 'known' AND value IS NOT NULL AND value >= 0)
        OR (availability = 'absent' AND value IS NULL)),
    PRIMARY KEY (catalog_id, version, food_id, nutrient_id),
    FOREIGN KEY (catalog_id, version, food_id) REFERENCES catalog_food
);

CREATE TABLE IF NOT EXISTS catalog_active (
    catalog_id text PRIMARY KEY,
    version text NOT NULL,
    FOREIGN KEY (catalog_id, version) REFERENCES catalog_version
);

COMMIT;

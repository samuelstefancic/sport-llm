BEGIN;

CREATE TABLE IF NOT EXISTS journal_result (
    entry_id text NOT NULL,
    entry_revision bigint NOT NULL CHECK (entry_revision > 0),
    entry_kind text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (entry_id, entry_revision)
);

CREATE TABLE IF NOT EXISTS journal_entry (
    entry_id text PRIMARY KEY,
    entry_kind text NOT NULL,
    current_revision bigint NOT NULL CHECK (current_revision > 0)
);

INSERT INTO journal_entry (entry_id, entry_kind, current_revision)
SELECT DISTINCT ON (r.entry_id) r.entry_id, r.entry_kind, r.entry_revision
FROM journal_result r
LEFT JOIN journal_entry e ON e.entry_id = r.entry_id
WHERE e.entry_id IS NULL
   OR (e.entry_kind = r.entry_kind AND e.current_revision < r.entry_revision)
ORDER BY r.entry_id, r.entry_revision DESC
ON CONFLICT (entry_id) DO UPDATE SET current_revision = EXCLUDED.current_revision
WHERE journal_entry.entry_kind = EXCLUDED.entry_kind
  AND journal_entry.current_revision < EXCLUDED.current_revision;

CREATE TABLE IF NOT EXISTS journal_declaration (
    entry_id text NOT NULL REFERENCES journal_entry(entry_id),
    entry_revision bigint NOT NULL CHECK (entry_revision > 0),
    body jsonb NOT NULL,
    PRIMARY KEY (entry_id, entry_revision)
);

CREATE TABLE IF NOT EXISTS journal_idempotency (
    request_key text PRIMARY KEY,
    entry_id text NOT NULL,
    entry_revision bigint NOT NULL,
    FOREIGN KEY (entry_id, entry_revision) REFERENCES journal_declaration(entry_id, entry_revision),
    FOREIGN KEY (entry_id, entry_revision) REFERENCES journal_result(entry_id, entry_revision)
);

ALTER TABLE journal_result ADD COLUMN IF NOT EXISTS declaration_bound boolean NOT NULL DEFAULT false;
ALTER TABLE journal_result ADD COLUMN IF NOT EXISTS recorded_at timestamptz;
ALTER TABLE journal_result ALTER COLUMN recorded_at SET DEFAULT clock_timestamp();

-- Older writers omit declaration_bound. Preserve their INSERT format for an unreserved revision
-- in the entry's domain, including the first result for a new identifier.
CREATE OR REPLACE FUNCTION check_journal_result_binding()
RETURNS trigger LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE
    expected_kind text;
    declaration_exists boolean;
BEGIN
    INSERT INTO journal_entry(entry_id,entry_kind,current_revision)
    VALUES (NEW.entry_id,NEW.entry_kind,NEW.entry_revision)
    ON CONFLICT (entry_id) DO NOTHING;

    SELECT entry_kind INTO expected_kind FROM journal_entry WHERE entry_id=NEW.entry_id FOR UPDATE;
    IF expected_kind IS DISTINCT FROM NEW.entry_kind THEN
        RAISE EXCEPTION 'Result domain differs from the journal entry domain'
            USING ERRCODE = '23514', CONSTRAINT = 'journal_result_entry_kind';
    END IF;

    SELECT EXISTS (SELECT 1 FROM journal_declaration
                   WHERE entry_id=NEW.entry_id AND entry_revision=NEW.entry_revision) INTO declaration_exists;
    IF NEW.declaration_bound IS DISTINCT FROM declaration_exists THEN
        RAISE EXCEPTION 'Result binding differs from the declaration at this revision'
            USING ERRCODE = '23514', CONSTRAINT = 'journal_result_declaration_binding';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS journal_result_check_binding ON journal_result;
CREATE TRIGGER journal_result_check_binding BEFORE INSERT ON journal_result
FOR EACH ROW EXECUTE FUNCTION check_journal_result_binding();

COMMIT;

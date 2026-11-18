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
SELECT DISTINCT ON (entry_id) entry_id, entry_kind, entry_revision
FROM journal_result ORDER BY entry_id, entry_revision DESC
ON CONFLICT (entry_id) DO NOTHING;

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

COMMIT;

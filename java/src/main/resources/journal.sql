CREATE TABLE IF NOT EXISTS journal_result (
    entry_id text NOT NULL,
    entry_revision bigint NOT NULL CHECK (entry_revision > 0),
    entry_kind text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (entry_id, entry_revision)
);

package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.sql.*;
import java.util.Properties;

@Component
class JournalStore {
    private final String url;
    private final Properties credentials = new Properties();
    private final ObjectMapper mapper;

    private record Entry(String kind, long revision) {}

    record AppliedResult(JsonNode payload, boolean replayed) {}

    static final class Conflict extends Exception {
        final long currentRevision;

        Conflict(String code) {
            this(code, 0);
        }

        Conflict(String code, long currentRevision) {
            super(code);
            this.currentRevision = currentRevision;
        }
    }

    @FunctionalInterface
    interface Calculation {
        JsonNode calculate(Connection db) throws SQLException;
    }

    @FunctionalInterface
    interface Validation {
        void validate(Connection db) throws SQLException;
    }

    JournalStore(@Value("${journal.jdbc.url:jdbc:postgresql://127.0.0.1:5432/llmsport}") String url,
                 @Value("${journal.db.user:llmsport}") String user,
                 @Value("${journal.db.password:}") String password, ObjectMapper mapper) {
        this.url = url;
        credentials.setProperty("user", user);
        credentials.setProperty("password", password);
        this.mapper = mapper;
    }

    private Connection open() throws SQLException {
        return DriverManager.getConnection(url, credentials);
    }

    JsonNode prepare(JournalDeclaration declaration, String key) throws SQLException, IOException, Conflict {
        try (var db = open()) {
            JsonNode replay = replay(db, declaration, key);
            if (replay != null) return replay;
            checkTarget(entry(db, declaration.id(), false), declaration);
            return null;
        }
    }

    AppliedResult apply(JournalDeclaration declaration, String key, Calculation calculation)
            throws SQLException, IOException, Conflict {
        try (var db = open()) {
            db.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
            db.setAutoCommit(false);
            if (key != null) {
                lockKey(db, key);
                JsonNode replay = replay(db, declaration, key);
                if (replay != null) return new AppliedResult(replay, true);
            }
            Entry current = lockEntry(db, declaration);
            checkTarget(current, declaration);
            if (declaration.revision() < current.revision) {
                throw new Conflict("stale_revision", current.revision);
            }
            // The lock on journal_entry is held until the result and its optional key are committed.
            if (needsDeclaration(db, current, declaration)) insertDeclaration(db, current, declaration);
            else if (hasResult(db, declaration)) throw new Conflict("revision_conflict");
            JsonNode payload = calculation.calculate(db);
            writeResult(db, declaration, payload);
            if (key != null) remember(db, declaration, key);
            db.commit();
            return new AppliedResult(payload, false);
        }
    }

    JsonNode declare(JournalDeclaration declaration, Validation validation) throws SQLException, Conflict {
        try (var db = open()) {
            db.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
            db.setAutoCommit(false);
            Entry current = lockEntry(db, declaration);
            checkTarget(current, declaration);
            if (needsDeclaration(db, current, declaration)) {
                validation.validate(db);
                insertDeclaration(db, current, declaration);
            }
            db.commit();
            return declaration.body();
        }
    }

    private static void checkTarget(Entry current, JournalDeclaration declaration) throws Conflict {
        long revision = current == null ? 0 : current.revision;
        if ((current != null && !current.kind.equals(declaration.kind())) || declaration.revision() - revision > 1) {
            throw new Conflict("revision_conflict");
        }
    }

    private static Entry entry(Connection db, String id, boolean lock) throws SQLException {
        String query = "SELECT entry_kind,current_revision FROM journal_entry WHERE entry_id=?";
        try (var statement = db.prepareStatement(lock ? query + " FOR UPDATE" : query)) {
            statement.setString(1, id);
            try (var row = statement.executeQuery()) {
                return row.next() ? new Entry(row.getString(1), row.getLong(2)) : null;
            }
        }
    }

    private static Entry lockEntry(Connection db, JournalDeclaration declaration) throws SQLException {
        Entry current = entry(db, declaration.id(), true);
        if (current != null || declaration.revision() != 1) return current;
        try (var statement = db.prepareStatement("""
                INSERT INTO journal_entry(entry_id,entry_kind,current_revision) VALUES (?,?,1)
                ON CONFLICT (entry_id) DO NOTHING""")) {
            statement.setString(1, declaration.id());
            statement.setString(2, declaration.kind());
            statement.executeUpdate();
        }
        return entry(db, declaration.id(), true);
    }

    private static boolean needsDeclaration(Connection db, Entry current, JournalDeclaration declaration)
            throws SQLException, Conflict {
        try (var statement = db.prepareStatement("""
                SELECT body=?::jsonb FROM journal_declaration WHERE entry_id=? AND entry_revision=?""")) {
            statement.setString(1, declaration.body().toString());
            statement.setString(2, declaration.id());
            statement.setLong(3, declaration.revision());
            try (var row = statement.executeQuery()) {
                if (row.next()) {
                    if (!row.getBoolean(1)) throw new Conflict("revision_conflict");
                    return false;
                }
            }
        }

        // Historical results have no canonical declaration to match. Never attach new text to them.
        if (declaration.revision() < current.revision || hasResult(db, declaration)) {
            throw new Conflict("revision_conflict");
        }
        return true;
    }

    private static void insertDeclaration(Connection db, Entry current, JournalDeclaration declaration)
            throws SQLException {
        try (var statement = db.prepareStatement("""
                INSERT INTO journal_declaration(entry_id,entry_revision,body) VALUES (?,?,?::jsonb)""")) {
            bindRevision(statement, declaration);
            statement.setString(3, declaration.body().toString());
            statement.executeUpdate();
        }
        if (declaration.revision() > current.revision) {
            try (var statement = db.prepareStatement("UPDATE journal_entry SET current_revision=? WHERE entry_id=?")) {
                statement.setLong(1, declaration.revision());
                statement.setString(2, declaration.id());
                statement.executeUpdate();
            }
        }
    }

    private static boolean hasResult(Connection db, JournalDeclaration declaration) throws SQLException {
        try (var statement = db.prepareStatement("SELECT 1 FROM journal_result WHERE entry_id=? AND entry_revision=?")) {
            bindRevision(statement, declaration);
            try (var row = statement.executeQuery()) {
                return row.next();
            }
        }
    }

    private static void writeResult(Connection db, JournalDeclaration declaration, JsonNode payload) throws SQLException {
        try (var statement = db.prepareStatement("""
                INSERT INTO journal_result(entry_id,entry_revision,entry_kind,payload,declaration_bound)
                VALUES (?,?,?,?::jsonb,true)""")) {
            bindRevision(statement, declaration);
            statement.setString(3, declaration.kind());
            statement.setString(4, payload.toString());
            statement.executeUpdate();
        }
    }

    private static void lockKey(Connection db, String key) throws SQLException {
        try (var statement = db.prepareStatement("""
                SELECT pg_advisory_xact_lock(hashtextextended('llmsport:journal:idempotency:' || ?, 0))""")) {
            statement.setString(1, key);
            statement.execute();
        }
    }

    private JsonNode replay(Connection db, JournalDeclaration declaration, String key)
            throws SQLException, IOException, Conflict {
        if (key == null) return null;
        try (var statement = db.prepareStatement("""
                SELECT d.body=?::jsonb, r.payload
                FROM journal_idempotency k
                JOIN journal_declaration d USING (entry_id,entry_revision)
                JOIN journal_result r USING (entry_id,entry_revision)
                WHERE k.request_key=?""")) {
            statement.setString(1, declaration.body().toString());
            statement.setString(2, key);
            try (var row = statement.executeQuery()) {
                if (!row.next()) return null;
                if (!row.getBoolean(1)) throw new Conflict("idempotency_conflict");
                return mapper.readTree(row.getString(2));
            }
        }
    }

    private static void remember(Connection db, JournalDeclaration declaration, String key) throws SQLException {
        try (var statement = db.prepareStatement("""
                INSERT INTO journal_idempotency(entry_id,entry_revision,request_key) VALUES (?,?,?)""")) {
            bindRevision(statement, declaration);
            statement.setString(3, key);
            statement.executeUpdate();
        }
    }

    JsonNode result(String kind, String id, long revision) throws SQLException, IOException {
        return read("""
                SELECT payload FROM journal_result WHERE entry_kind=? AND entry_id=? AND entry_revision=?""",
                kind, id, revision);
    }

    JsonNode declaration(String kind, String id, long revision) throws SQLException, IOException {
        return read("""
                SELECT body FROM journal_declaration WHERE body->>'entry_kind'=? AND entry_id=? AND entry_revision=?""",
                kind, id, revision);
    }

    JsonNode currentResult(String kind, String id) throws SQLException, IOException {
        return read("""
                SELECT r.payload FROM journal_entry e JOIN journal_result r
                ON e.entry_id=r.entry_id AND e.current_revision=r.entry_revision AND e.entry_kind=r.entry_kind
                WHERE e.entry_kind=? AND e.entry_id=?""", kind, id, null);
    }

    private JsonNode read(String query, String kind, String id, Long revision) throws SQLException, IOException {
        try (var db = open(); var statement = db.prepareStatement(query)) {
            statement.setString(1, kind);
            statement.setString(2, id);
            if (revision != null) statement.setLong(3, revision);
            try (var row = statement.executeQuery()) {
                return row.next() ? mapper.readTree(row.getString(1)) : null;
            }
        }
    }

    private static void bindRevision(PreparedStatement statement, JournalDeclaration declaration) throws SQLException {
        statement.setString(1, declaration.id());
        statement.setLong(2, declaration.revision());
    }
}

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

    JournalStore(@Value("${journal.jdbc.url:jdbc:postgresql://127.0.0.1:5432/llmsport}") String url,
                 @Value("${journal.db.user:llmsport}") String user,
                 @Value("${journal.db.password:}") String password, ObjectMapper mapper) {
        this.url = url;
        credentials.setProperty("user", user);
        credentials.setProperty("password", password);
        this.mapper = mapper;
    }

    Connection open() throws SQLException {
        return DriverManager.getConnection(url, credentials);
    }

    boolean save(Connection db, JsonNode input, String kind, JsonNode payload) throws SQLException {
        try (var statement = db.prepareStatement("""
                INSERT INTO journal_result(entry_id,entry_revision,entry_kind,payload)
                VALUES (?,?,?,?::jsonb) ON CONFLICT (entry_id,entry_revision) DO NOTHING""")) {
            statement.setString(1, input.get("entry_id").textValue());
            statement.setLong(2, input.get("entry_revision").longValue());
            statement.setString(3, kind);
            statement.setString(4, payload.toString());
            return statement.executeUpdate() == 1;
        }
    }

    JsonNode read(String id, long revision, String kind) throws SQLException, IOException {
        try (var db = open(); var statement = db.prepareStatement("""
                SELECT payload FROM journal_result WHERE entry_id=? AND entry_revision=? AND entry_kind=?""")) {
            statement.setString(1, id);
            statement.setLong(2, revision);
            statement.setString(3, kind);
            try (var row = statement.executeQuery()) {
                return row.next() ? mapper.readTree(row.getString(1)) : null;
            }
        }
    }
}

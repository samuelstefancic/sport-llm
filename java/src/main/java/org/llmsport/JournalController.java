package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.sql.*;
import java.util.Map;
import java.util.UUID;

@RestController
class JournalController {
    private static final Logger LOG = LoggerFactory.getLogger(JournalController.class);
    private static final String CORRELATION = "X-Correlation-ID";
    private final ProposalClient python;
    private final JournalStore store;
    private final ObjectMapper mapper;

    JournalController(ProposalClient python, JournalStore store, ObjectMapper mapper) {
        this.python = python;
        this.store = store;
        this.mapper = mapper;
    }

    @PostMapping(path = "/meals", consumes = "application/json", produces = "application/json")
    ResponseEntity<?> meal(@RequestBody JsonNode input,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        UUID id = supplied == null ? UUID.randomUUID() : supplied;
        if (!input.isObject()) return error(400, id, "invalid_request");
        ObjectNode envelope = ((ObjectNode) input).deepCopy();
        JsonNode selected = envelope.remove("selected_nutrients");
        JsonNode corrected = envelope.remove("corrected_mentions");
        if (!ProposalClient.validInput(envelope) || (corrected != null &&
                (!corrected.isArray() || envelope.get("entry_revision").longValue() <= 1))) {
            return error(400, id, "invalid_request");
        }
        var received = python.analyze(envelope, id);
        if (!received.getStatusCode().is2xxSuccessful()) return received;
        try (var db = store.open()) {
            db.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
            db.setAutoCommit(false);
            JsonNode payload = MealCalculator.calculate(db, mapper, input, (JsonNode) received.getBody(), selected);
            if (!store.save(db, input, "meal", payload)) return error(409, id, "revision_conflict");
            db.commit();
            return ResponseEntity.ok().header(CORRELATION, id.toString()).body(payload);
        } catch (MealCalculator.InvalidSelection e) {
            return error(400, id, "invalid_selection");
        } catch (MealCalculator.InvalidCorrection e) {
            return error(400, id, "invalid_correction");
        } catch (IllegalArgumentException e) {
            return error(502, id, "invalid_proposal");
        } catch (SQLException e) {
            return error(503, id, "journal_unavailable");
        }
    }

    @GetMapping("/meals/{entry}/revisions/{revision}")
    ResponseEntity<?> mealRevision(@PathVariable String entry, @PathVariable long revision,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        UUID id = supplied == null ? UUID.randomUUID() : supplied;
        try {
            JsonNode payload = store.read(entry, revision, "meal");
            return payload == null ? error(404, id, "not_found")
                    : ResponseEntity.ok().header(CORRELATION, id.toString()).body(payload);
        } catch (SQLException e) {
            return error(503, id, "journal_unavailable");
        }
    }

    private static ResponseEntity<?> error(int status, UUID id, String code) {
        LOG.info("correlation={} outcome={}", id, code);
        return ResponseEntity.status(status).header(CORRELATION, id.toString()).body(Map.of("error", code));
    }
}

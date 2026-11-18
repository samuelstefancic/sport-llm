package org.llmsport;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.sql.SQLException;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Pattern;

@RestController
class JournalController {
    private static final Logger LOG = LoggerFactory.getLogger(JournalController.class);
    private static final String CORRELATION = "X-Correlation-ID";
    private static final String DOMAIN = "/{domain:meals|workouts}";
    private static final String ENTRY = DOMAIN + "/{entry}";
    private static final String REVISION = ENTRY + "/revisions/{revision}";
    private static final String DECLARATION = REVISION + "/declaration";
    private static final Pattern KEY = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._:-]{0,127}");
    private final ProposalClient python;
    private final JournalStore store;
    private final ObjectMapper mapper;

    JournalController(ProposalClient python, JournalStore store, ObjectMapper mapper) {
        this.python = python;
        this.store = store;
        this.mapper = mapper;
    }

    @PostMapping(path = DOMAIN, consumes = "application/json", produces = "application/json")
    ResponseEntity<?> analyze(@PathVariable String domain, @RequestBody JsonNode input,
            @RequestHeader(value = "Idempotency-Key", required = false) String key,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        UUID id = correlation(supplied);
        if (key != null && !KEY.matcher(key).matches()) return error(400, id, "invalid_idempotency_key");
        JournalDeclaration declaration;
        try {
            declaration = JournalDeclaration.parse(kind(domain), input);
        } catch (IllegalArgumentException e) {
            return error(400, id, e.getMessage());
        }

        JsonNode proposal = null;
        try {
            JsonNode replay = store.prepare(declaration, key);
            if (replay != null) {
                LOG.info("correlation={} outcome=idempotent_replay", id);
                return ok(id, replay);
            }
            boolean meal = declaration.kind().equals("meal");
            var workout = meal ? null : WorkoutCalculator.parse(declaration.text());
            var received = meal ? python.analyze(declaration.envelope(), id)
                    : python.analyzeWorkout(declaration.envelope(), id);
            if (!received.getStatusCode().is2xxSuccessful()) return received;
            JsonNode accepted = (JsonNode) received.getBody();
            proposal = accepted;
            var body = declaration.body();
            var result = store.apply(declaration, key, db -> meal
                    ? MealCalculator.calculate(db, mapper, body, accepted)
                    : workout.calculate(mapper, body, accepted));
            LOG.info("correlation={} outcome={}", id, result.replayed() ? "idempotent_replay" : "journal_committed");
            return ok(id, result.payload());
        } catch (JournalStore.Conflict e) {
            if (e.currentRevision > 0 && proposal != null) {
                return stale(id, declaration, proposal, e.currentRevision);
            }
            return error(409, id, e.getMessage());
        } catch (MealCalculator.InvalidSelection | MealCalculator.InvalidCorrection | MealCalculator.NegativeQuantity
                | WorkoutCalculator.InvalidDeclaration e) {
            return error(400, id, e.getMessage());
        } catch (IllegalArgumentException e) {
            return error(502, id, "invalid_proposal");
        } catch (SQLException e) {
            return error(503, id, "journal_unavailable");
        }
    }

    @PutMapping(path = DECLARATION, consumes = "application/json", produces = "application/json")
    ResponseEntity<?> declare(@PathVariable String domain, @PathVariable String entry, @PathVariable long revision,
            @RequestBody JsonNode input, @RequestHeader(value = CORRELATION, required = false) UUID supplied) {
        UUID id = correlation(supplied);
        try {
            var declaration = JournalDeclaration.fromRevisionPath(kind(domain), entry, revision, input);
            return ok(id, store.declare(declaration, db -> {
                if ("meal".equals(declaration.kind())) MealCalculator.validateDeclaration(db, declaration.body());
                else WorkoutCalculator.parse(declaration.text());
            }));
        } catch (IllegalArgumentException e) {
            return error(400, id, e.getMessage());
        } catch (JournalStore.Conflict e) {
            return error(409, id, e.getMessage());
        } catch (SQLException e) {
            return error(503, id, "journal_unavailable");
        }
    }

    @GetMapping(DECLARATION)
    ResponseEntity<?> declaration(@PathVariable String domain, @PathVariable String entry, @PathVariable long revision,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        return read(supplied, () -> store.declaration(kind(domain), entry, revision));
    }

    @GetMapping(REVISION)
    ResponseEntity<?> revision(@PathVariable String domain, @PathVariable String entry, @PathVariable long revision,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        return read(supplied, () -> store.result(kind(domain), entry, revision));
    }

    @GetMapping(ENTRY)
    ResponseEntity<?> current(@PathVariable String domain, @PathVariable String entry,
            @RequestHeader(value = CORRELATION, required = false) UUID supplied) throws IOException {
        return read(supplied, () -> store.currentResult(kind(domain), entry));
    }

    @FunctionalInterface
    private interface Read {
        JsonNode get() throws SQLException, IOException;
    }

    private static ResponseEntity<?> read(UUID supplied, Read query) throws IOException {
        UUID id = correlation(supplied);
        try {
            JsonNode payload = query.get();
            return payload == null ? error(404, id, "not_found") : ok(id, payload);
        } catch (SQLException e) {
            return error(503, id, "journal_unavailable");
        }
    }

    private ResponseEntity<?> stale(UUID id, JournalDeclaration declaration, JsonNode proposal, long currentRevision) {
        var rejection = mapper.createObjectNode().put("kind", "java_analysis_rejection")
                .put("schema_version", proposal.path("schema_version").textValue())
                .put("entry_id", declaration.id())
                .put("proposal_id", proposal.path("proposal_id").textValue())
                .put("analysis_revision", declaration.revision()).put("current_revision", currentRevision)
                .put("code", "stale_revision").put("detail", "La révision analysée est antérieure à la déclaration courante.");
        LOG.info("correlation={} outcome=stale_revision", id);
        return ResponseEntity.status(409).header(CORRELATION, id.toString()).body(rejection);
    }

    private static String kind(String domain) { return "meals".equals(domain) ? "meal" : "workout"; }

    private static UUID correlation(UUID supplied) { return supplied == null ? UUID.randomUUID() : supplied; }

    private static ResponseEntity<?> ok(UUID id, JsonNode payload) {
        return ResponseEntity.ok().header(CORRELATION, id.toString()).body(payload);
    }

    private static ResponseEntity<?> error(int status, UUID id, String code) {
        LOG.info("correlation={} outcome={}", id, code);
        return ResponseEntity.status(status).header(CORRELATION, id.toString()).body(Map.of("error", code));
    }
}

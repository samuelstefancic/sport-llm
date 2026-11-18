package org.llmsport;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.networknt.schema.JsonNodePath;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.PathType;
import com.networknt.schema.SpecVersion;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.regex.Pattern;

@Service
public class ProposalClient {
    private static final Logger LOG = LoggerFactory.getLogger(ProposalClient.class);
    private static final String CORRELATION = "X-Correlation-ID";
    private static final Duration TIMEOUT = Duration.ofSeconds(2);
    private static final Pattern ENTRY_ID = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._:-]{0,95}");

    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(TIMEOUT)
            .followRedirects(HttpClient.Redirect.NEVER)
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    private final ObjectMapper mapper;
    private final URI proposalsUri;
    private final JsonSchema proposalSchema;

    public ProposalClient(ObjectMapper mapper, @Value("${python.base-url}") URI pythonBaseUrl) throws IOException {
        this.mapper = mapper;
        this.proposalsUri = pythonBaseUrl.resolve("/internal/proposals");
        try (var input = new ClassPathResource("analysis.schema.json").getInputStream()) {
            var root = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012).getSchema(input);
            var branch = new JsonNodePath(PathType.JSON_POINTER).append("$defs").append("python_proposal");
            this.proposalSchema = root.getSubSchema(branch);
            this.proposalSchema.initializeValidators();
        }
    }

    public ResponseEntity<?> analyze(JsonNode input, UUID correlation)
            throws JsonProcessingException {
        return analyze(input, correlation, "meal");
    }

    ResponseEntity<?> analyzeWorkout(JsonNode input, UUID correlation) throws JsonProcessingException {
        return analyze(input, correlation, "workout");
    }

    private ResponseEntity<?> analyze(JsonNode input, UUID correlation, String entryKind)
            throws JsonProcessingException {
        String id = (correlation == null ? UUID.randomUUID() : correlation).toString();
        if (!validInput(input)) {
            return error(400, id, "invalid_request");
        }

        JsonNode envelope = input;
        if ("workout".equals(entryKind)) {
            envelope = ((ObjectNode) input).deepCopy().put("entry_kind", entryKind);
        }
        HttpRequest request = HttpRequest.newBuilder(proposalsUri)
                .timeout(TIMEOUT)
                .header(CORRELATION, id)
                .header("Content-Type", "application/json")
                .header("Accept", "application/json")
                .POST(HttpRequest.BodyPublishers.ofByteArray(mapper.writeValueAsBytes(envelope)))
                .build();
        var exchange = http.sendAsync(request, HttpResponse.BodyHandlers.ofByteArray());
        HttpResponse<byte[]> response;
        try {
            // The deadline covers the complete body, including a peer that stalls after sending headers.
            response = exchange.get(TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
        } catch (TimeoutException e) {
            exchange.cancel(true);
            return error(504, id, "python_timeout");
        } catch (InterruptedException e) {
            exchange.cancel(true);
            Thread.currentThread().interrupt();
            return error(502, id, "python_unavailable");
        } catch (ExecutionException e) {
            if (e.getCause() instanceof HttpTimeoutException) {
                return error(504, id, "python_timeout");
            }
            return error(502, id, "python_unavailable");
        }
        if (response.statusCode() != 200) {
            return error(502, id, "python_http_error");
        }
        if (!response.headers().allValues(CORRELATION).equals(java.util.List.of(id))) {
            return error(502, id, "invalid_correlation");
        }

        JsonNode proposal;
        try {
            proposal = mapper.readTree(response.body());
        } catch (IOException e) {
            return error(502, id, "invalid_json");
        }
        if (proposal == null || proposal.isMissingNode()) {
            return error(502, id, "invalid_json");
        }
        if (!proposalSchema.validate(proposal).isEmpty()
                || !input.get("entry_id").equals(proposal.get("entry_id"))
                || input.get("entry_revision").decimalValue().compareTo(proposal.get("entry_revision").decimalValue()) != 0
                || !entryKind.equals(proposal.path("entry_kind").textValue())) {
            return error(502, id, "invalid_proposal");
        }
        LOG.info("correlation={} outcome=proposal_accepted", id);
        return ResponseEntity.ok().header(CORRELATION, id).body(proposal);
    }

    static boolean validInput(JsonNode input) {
        return input.isObject() && input.size() == 3
                && input.path("entry_id").isTextual() && ENTRY_ID.matcher(input.get("entry_id").textValue()).matches()
                && input.path("entry_revision").isIntegralNumber() && input.get("entry_revision").canConvertToLong() && input.get("entry_revision").longValue() > 0
                && input.path("text").isTextual() && input.get("text").textValue().codePoints().anyMatch(c -> !Character.isWhitespace(c) && !Character.isSpaceChar(c))
                && input.get("text").textValue().codePoints().count() <= 4000;
    }

    private static ResponseEntity<?> error(int status, String id, String reason) {
        LOG.info("correlation={} outcome={}", id, reason);
        return ResponseEntity.status(status).header(CORRELATION, id).body(Map.of("error", reason));
    }
}

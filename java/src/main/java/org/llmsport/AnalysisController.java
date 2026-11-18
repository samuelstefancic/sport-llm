package org.llmsport;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
public class AnalysisController {
    private final ProposalClient python;

    public AnalysisController(ProposalClient python) {
        this.python = python;
    }

    @PostMapping(path = "/analysis", consumes = "application/json", produces = "application/json")
    public ResponseEntity<?> analyze(@RequestBody JsonNode input,
            @RequestHeader(value = "X-Correlation-ID", required = false) UUID correlation)
            throws JsonProcessingException {
        return python.analyze(input, correlation);
    }
}

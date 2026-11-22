package org.llmsport;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.http.CacheControl;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.net.ProxySelector;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

@Profile("ecran-local")
@RestController
class LocalQwenController {
    private static final int MAX_INPUT = 24_576;
    private static final int MAX_GAME = 98_304;
    private static final String GAME = "[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?";
    private static final String SERIES = "[0-9]{8}-[0-9]{6}-[0-9a-f]{12}";
    private final HttpClient http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .proxy(ProxySelector.of(null))
            .followRedirects(HttpClient.Redirect.NEVER)
            .version(HttpClient.Version.HTTP_1_1)
            .build();
    private final String host;
    private final URI python;
    private final String token;

    LocalQwenController(@Value("${ecran.trial:false}") boolean trial,
                        @Value("${LLMSPORT_QWEN_TOKEN:}") String token) {
        host = trial ? "127.0.0.1:8213" : "127.0.0.1:8113";
        python = URI.create(trial ? "http://127.0.0.1:8214" : "http://127.0.0.1:8114");
        this.token = token;
    }

    @GetMapping("/api/local/qwen/status")
    ResponseEntity<?> status(HttpServletRequest request) {
        return read("status", request);
    }

    @GetMapping("/api/local/qwen/{collection:jeux|series}")
    ResponseEntity<?> index(@PathVariable String collection, HttpServletRequest request) {
        return read(collection, request);
    }

    @GetMapping("/api/local/qwen/jeux/{id:" + GAME + "}")
    ResponseEntity<?> game(@PathVariable String id, HttpServletRequest request) {
        return read("jeux/" + id, request);
    }

    @GetMapping("/api/local/qwen/series/{id:" + SERIES + "}")
    ResponseEntity<?> series(@PathVariable String id, HttpServletRequest request) {
        return read("series/" + id, request);
    }

    @PostMapping("/api/local/qwen/jeux/{id:" + GAME + "}")
    ResponseEntity<?> saveGame(@PathVariable String id, HttpServletRequest request) {
        return submit("jeux/" + id, request, MAX_GAME, Duration.ofSeconds(10));
    }

    @PostMapping("/api/local/qwen/series")
    ResponseEntity<?> startSeries(HttpServletRequest request) {
        return submit("series", request, MAX_INPUT, Duration.ofSeconds(10));
    }

    @PostMapping("/api/local/qwen/{operation:load|run}")
    ResponseEntity<?> action(@PathVariable String operation, HttpServletRequest request) {
        return submit(operation, request, MAX_INPUT, Duration.ofSeconds(70));
    }

    private ResponseEntity<?> read(String operation, HttpServletRequest request) {
        var rejection = reject(request, false, operation);
        if (rejection != null) return rejection;
        if (!"GET".equals(request.getMethod())) return error(405, "method_not_allowed");
        return forward(operation, null, Duration.ofSeconds(6));
    }

    private ResponseEntity<?> submit(String operation, HttpServletRequest request, int maximum, Duration timeout) {
        var rejection = reject(request, true, operation);
        if (rejection != null) return rejection;
        var contentTypes = Collections.list(request.getHeaders("Content-Type"));
        if (contentTypes.size() != 1 || !"application/json".equalsIgnoreCase(contentTypes.get(0).split(";", 2)[0].trim())) {
            return error(415, "json_required");
        }
        if (request.getContentLengthLong() > maximum) return error(413, "request_too_large");
        try {
            byte[] body = request.getInputStream().readNBytes(maximum + 1);
            if (body.length > maximum) return error(413, "request_too_large");
            return forward(operation, body, timeout);
        } catch (IOException ignored) {
            return error(400, "invalid_request");
        }
    }

    private ResponseEntity<?> reject(HttpServletRequest request, boolean action, String operation) {
        if (!token.matches("[0-9a-f]{64}")) return error(503, "qwen_disabled");
        var hosts = Collections.list(request.getHeaders("Host"));
        var origins = Collections.list(request.getHeaders("Origin"));
        if (!hosts.equals(List.of(host)) || ((action || !origins.isEmpty()) && !origins.equals(List.of("http://" + host)))) {
            return error(403, "local_origin_required");
        }
        if (request.getQueryString() != null || !request.getRequestURI().equals("/api/local/qwen/" + operation)) {
            return error(400, "invalid_request");
        }
        return null;
    }

    private ResponseEntity<?> forward(String operation, byte[] body, Duration timeout) {
        var builder = HttpRequest.newBuilder(python.resolve("/internal/qwen/" + operation))
                .timeout(timeout).header("X-LLMSPORT-Qwen", token);
        var request = body == null ? builder.GET().build() : builder
                .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofByteArray(body)).build();
        var exchange = http.sendAsync(request, HttpResponse.BodyHandlers.ofByteArray());
        try {
            // L'API interne authentifiée borne les réponses. L'attente couvre aussi leur réception complète.
            var response = exchange.get(timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (!response.headers().firstValue("Content-Type").orElse("").startsWith("application/json")) {
                return error(502, "qwen_backend_unavailable");
            }
            return ResponseEntity.status(response.statusCode()).cacheControl(CacheControl.noStore())
                    .contentType(MediaType.APPLICATION_JSON).header("X-Content-Type-Options", "nosniff").body(response.body());
        } catch (TimeoutException ignored) {
            exchange.cancel(true);
            return error(504, "ollama_timeout");
        } catch (InterruptedException ignored) {
            exchange.cancel(true);
            Thread.currentThread().interrupt();
            return error(502, "qwen_backend_unavailable");
        } catch (ExecutionException failure) {
            if (failure.getCause() instanceof HttpTimeoutException) return error(504, "ollama_timeout");
            return error(502, "qwen_backend_unavailable");
        }
    }

    private static ResponseEntity<?> error(int status, String code) {
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore())
                .contentType(MediaType.APPLICATION_JSON).header("X-Content-Type-Options", "nosniff")
                .body(Map.of("error", code));
    }
}

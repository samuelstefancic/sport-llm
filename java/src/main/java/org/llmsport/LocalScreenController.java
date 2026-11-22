package org.llmsport;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Profile;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.SQLException;
import java.util.Map;

@Profile("ecran-local")
@RestController
class LocalScreenController {
    private static final String T10 = "github-t10/.local/t10/reference-42c47d22/run-1/";
    private static final String BENCH = "pre-t11-banc/.local/pre-t11/";
    private static final String PROBE = "pre-t11-banc/.local/pre-t11-schema-compatible.9Q2aUX/";
    private static final String VS1 = "github-fix-vs1/.local/vs1/qa/";
    private static final Map<String, String> EVIDENCE = Map.ofEntries(
            Map.entry("t10-mesures", T10 + "metrics.json"),
            Map.entry("t10-manifeste", T10 + "manifest.json"),
            Map.entry("banc-resultats", BENCH + "RESULTATS.md"),
            Map.entry("banc-protocole", BENCH + "PROTOCOLE.md"),
            Map.entry("banc-mesures", BENCH + "runs/reference/summary.json"),
            Map.entry("banc-memoire", "pre-t11-banc/.local/pre-t11-runtime/footprint-summary.json"),
            Map.entry("sonde-mesures", PROBE + "summary.json"),
            Map.entry("sonde-manifeste", PROBE + "manifest.json"),
            Map.entry("vs1-recu", VS1 + "livraison.json"),
            Map.entry("vs1-fusion", VS1 + "fusion.json"),
            Map.entry("vs1-comparaison", VS1 + "t10-fusion-16e27c42-comparaison.json"));
    private static final String POLICY = "default-src 'self'; object-src 'none'; base-uri 'none'; "
            + "frame-ancestors 'none'; form-action 'self'";
    private final Path worktree;
    private final Path liveSnapshot;
    private final JournalStore store;

    LocalScreenController(@Value("${ecran.worktree}") String worktree,
                          @Value("${ecran.trial:false}") boolean trial, JournalStore store) throws IOException {
        this.worktree = Path.of(worktree).toRealPath();
        this.liveSnapshot = this.worktree.resolve(trial ? ".local/ecran-essai" : ".local/ecran")
                .resolve("suivi-direct/affichage.json");
        this.store = store;
    }

    @GetMapping("/")
    ResponseEntity<Resource> screen() {
        return asset("index.html", "text/html; charset=UTF-8");
    }

    @GetMapping({"/ecran/style.css", "/ecran/journal.js", "/ecran/suivi.js"})
    ResponseEntity<Resource> staticFile(HttpServletRequest request) {
        String file = Path.of(request.getServletPath()).getFileName().toString();
        return asset(file, file.endsWith(".css") ? "text/css; charset=UTF-8" : "text/javascript; charset=UTF-8");
    }

    @GetMapping("/ecran/suivi.json")
    ResponseEntity<Resource> tracking() {
        return localFile(worktree.resolve("documentation/suivi-local.json"), "application/json");
    }

    @GetMapping("/api/local/suivi/direct")
    ResponseEntity<?> liveTracking(HttpServletRequest request) {
        if (!HttpMethod.GET.matches(request.getMethod())) {
            return ResponseEntity.status(405).allow(HttpMethod.GET).build();
        }
        if (request.getQueryString() != null) {
            return ResponseEntity.badRequest().body(Map.of("error", "unexpected_parameters"));
        }
        try {
            if (liveSnapshot.equals(liveSnapshot.toRealPath()) && Files.isRegularFile(liveSnapshot)) {
                // Lire un instantané entier malgré le remplacement atomique du fichier par le collecteur.
                byte[] snapshot = Files.readAllBytes(liveSnapshot);
                return ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.APPLICATION_JSON)
                        .header("X-Content-Type-Options", "nosniff").body(snapshot);
            }
        } catch (IOException ignored) {
            // Le collecteur peut démarrer après Java.
        }
        return ResponseEntity.status(503).cacheControl(CacheControl.noStore())
                .body(Map.of("error", "live_tracking_unavailable"));
    }

    @GetMapping("/ecran/preuves/{id:[a-z0-9-]+}")
    ResponseEntity<Resource> evidence(@PathVariable String id) {
        String relative = EVIDENCE.get(id);
        if (relative == null) return ResponseEntity.notFound().build();
        return localFile(worktree.getParent().resolve(relative), "text/plain; charset=UTF-8");
    }

    @GetMapping("/workouts")
    ResponseEntity<?> workoutHistory(@RequestParam(defaultValue = "0") long offset) {
        if (offset < 0) {
            return ResponseEntity.badRequest().body(Map.of("error", "invalid_offset"));
        }
        try {
            return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(store.workoutHistory(offset));
        } catch (SQLException e) {
            return ResponseEntity.status(503).body(Map.of("error", "journal_unavailable"));
        }
    }

    private static ResponseEntity<Resource> asset(String file, String contentType) {
        return response(new ClassPathResource("ecran-local/" + file), contentType);
    }

    private static ResponseEntity<Resource> localFile(Path file, String contentType) {
        try {
            if (file.equals(file.toRealPath()) && Files.isRegularFile(file) && Files.isReadable(file)) {
                return response(new FileSystemResource(file), contentType);
            }
        } catch (IOException ignored) {
            // A local artifact may be unavailable in another checkout.
        }
        return ResponseEntity.notFound().build();
    }

    private static ResponseEntity<Resource> response(Resource resource, String contentType) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).contentType(MediaType.parseMediaType(contentType))
                .header("Content-Security-Policy", POLICY).header("X-Content-Type-Options", "nosniff").body(resource);
    }
}

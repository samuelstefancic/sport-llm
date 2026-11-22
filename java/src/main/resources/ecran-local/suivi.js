const dataKeys = new Set([
  "t10-mesures", "t10-manifeste", "banc-mesures", "banc-memoire", "sonde-mesures",
  "sonde-manifeste", "vs1-recu", "vs1-comparaison",
]);
const lotEvidenceId = /^[a-z0-9][a-z0-9-]{0,63}$/;
const number = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 3 });
const memory = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const calendar = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "UTC" });
const content = document.querySelector("#tracking-content");
let loading = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function date(text) {
  if (typeof text !== "string") return "Date indisponible";
  const value = new Date(text);
  if (!Number.isFinite(value.getTime())) return "Date indisponible";
  return calendar.format(value);
}

function unavailable(value) {
  return !Number.isFinite(value);
}

function format(value, suffix, formatter = number) {
  return unavailable(value) ? "Indisponible" : `${formatter.format(value)} ${suffix}`;
}

function ratio(numerator, denominator) {
  return unavailable(numerator) || unavailable(denominator) ? "Indisponible" : `${numerator}/${denominator}`;
}

function inMio(value, unitsPerMio) {
  return format(unavailable(value) ? null : value / unitsPerMio, "Mio", memory);
}

function panel(title, className = "") {
  const section = node("section", undefined, `panel ${className}`);
  section.append(node("h2", title));
  return section;
}

function time(text) {
  const element = node("time", date(text));
  element.dateTime = text;
  return element;
}

function link(label, url) {
  const anchor = node("a", label);
  anchor.href = url;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  return anchor;
}

function githubNumber(url, route) {
  const prefix = `https://github.com/samuelstefancic/sport-llm/${route}/`;
  const suffix = typeof url === "string" && url.startsWith(prefix) ? url.slice(prefix.length) : "";
  return /^[0-9]+$/.test(suffix) ? suffix : null;
}

function table(container, label, headings, values) {
  const wrapper = node("div", undefined, "table-wrap");
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", label);
  wrapper.tabIndex = 0;
  const table = node("table");
  const head = node("thead");
  const header = node("tr");
  for (const heading of headings) {
    const cell = node("th", heading);
    cell.scope = "col";
    header.append(cell);
  }
  head.append(header);
  const body = node("tbody");
  for (const [name, ...row] of values) {
    const tr = node("tr");
    const cell = node("th", name);
    cell.scope = "row";
    tr.append(cell, ...row.map(value => node("td", value)));
    body.append(tr);
  }
  table.append(head, body);
  wrapper.append(table);
  container.append(wrapper);
}

function sourceHref(key) {
  return `/ecran/preuves/${encodeURIComponent(key)}`;
}

function lotEvidenceHref(key) {
  return `/ecran/preuves-lots/${encodeURIComponent(key)}`;
}

function evidenceLinks(keys, labels, sources, href = sourceHref) {
  const list = node("ul", undefined, "evidence-list");
  for (const key of keys) {
    const item = node("li");
    const label = labels?.[key] ?? `Reçu · ${key}`;
    if (sources[key]?.available) item.append(link(label, href(key)));
    else item.append(node("span", `${label} · source indisponible`, "muted"));
    list.append(item);
  }
  return list;
}

async function loadEvidence(url, isData = false) {
  try {
    const response = await fetch(url, {
      method: isData ? "GET" : "HEAD", cache: "no-store", signal: AbortSignal.timeout(4000),
    });
    if (response.ok) return { available: true, data: isData ? await response.json() : null };
  } catch {
    // Unavailable sources stay visible with their status in the list.
  }
  return { available: false, data: null };
}

function addBench(tracking, sources) {
  const section = panel("Banc d’extraction pré-T11");
  const summary = sources["banc-mesures"]?.data;
  const footprint = sources["banc-memoire"]?.data;
  if (!summary?.engines) {
    section.append(node("p", "Mesures de qualité, de latence et de RSS indisponibles."));
    return section;
  }
  const rows = [];
  for (const [key, label] of [["baseline", "Baseline"], ["qwen3:0.6b", "Qwen3 0,6B"], ["qwen3:4b", "Qwen3 4B"]]) {
    const engine = summary.engines[key];
    const revision = engine?.model?.tag?.digest ?? summary.source_commit;
    const rss = key === "baseline" ? engine?.peak_rss?.bench_max_kib : engine?.peak_rss?.server_tree_max_kib;
    const physical = footprint?.[key]?.peak_sampled_tree_footprint?.footprint_bytes;
    const warm = engine?.warm;
    const f10 = engine?.cases?.F10;
    rows.push([
      `${label} · ${revision?.slice(0, 8) ?? "version inconnue"}`,
      key === "baseline" ? "Retenue" : (summary.decisions?.[key]?.eligible === false ? "Essayé, écarté" : "Décision indisponible"),
      ratio(engine?.stable_cases?.length, Object.keys(engine?.cases ?? {}).length || null),
      ratio(warm?.complete, warm?.recorded), ratio(f10?.filter(run => run.complete).length, f10?.length),
      format(engine?.warmup?.latency_ms, "ms"), format(warm?.latency?.p50_ms, "ms"), format(warm?.latency?.p95_ms, "ms"),
      inMio(rss, 1024), inMio(physical, 1024 ** 2),
    ]);
  }
  const model = summary.engines["qwen3:4b"]?.model;
  const measuredOn = summary.frozen?.frozen_at ? date(summary.frozen.frozen_at) : "Date indisponible";
  section.append(node("p", `${measuredOn} · source ${summary.source_commit ?? "indisponible"} · Mac Apple M2 Pro, 16 Gio.`, "source-note"));
  section.append(node("p", `Données de développement fictives. Deux passages chauds sur 16 cas et 2 variantes par moteur, plus un appel de chauffe. Ollama ${model?.ollama_version ?? "version indisponible"} · ${model?.tag?.details?.quantization_level ?? "quantification indisponible"}.`));
  table(section, "Qualité, latence et mémoire par moteur",
    ["Moteur / révision", "Statut", "Cas stables", "Exacts", "F10", "1er appel", "P50 chaud", "P95 chaud", "Pic RSS", "Empreinte macOS"], rows);
  section.append(node("p", "La baseline appelle le gestionnaire Python directement. Les mesures Qwen incluent l’aller-retour HTTP local et comptent les réponses échouées. Le RSS est échantillonné pour Python avec le banc (2 mesures) et pour Ollama avec ses descendants (intervalle visé de 100 ms). L’empreinte macOS est échantillonnée séparément toutes les 250 ms pour Ollama. Les pics transitoires peuvent échapper aux deux mesures.", "source-note"));
  section.append(evidenceLinks(["banc-protocole", "banc-mesures", "banc-memoire"], tracking.preuves, sources));
  return section;
}

function addT10(tracking, sources) {
  const section = panel("Baseline métier · T10 et fusion VS1");
  const metrics = sources["t10-mesures"]?.data;
  const manifest = sources["t10-manifeste"]?.data;
  const comparison = sources["vs1-comparaison"]?.data;
  const receipt = sources["vs1-recu"]?.data;
  if (metrics) {
    section.append(node("p",
      `${date(manifest?.started_at_utc)} · ${manifest?.commit ?? "SHA indisponible"} · ${ratio(metrics.executed_cases, metrics.corpus_cases)} cas fictifs exécutés. ` +
      `${ratio(metrics.accuracy?.numerator, metrics.accuracy?.denominator)} corrects avant F10 · ${ratio(metrics.automatic_precision?.numerator, metrics.automatic_precision?.denominator)} acceptations automatiques correctes.`,
      "source-note"));
    section.append(node("p", `Premier run T10 · P50 ${format(metrics.latency_p50_ms, "ms")} · P95 ${format(metrics.latency_p95_ms, "ms")} sur ${metrics.latency_sample_count} POST chronométrés du parcours métier Java, FastAPI et PostgreSQL. Mémoire T10 indisponible.`));
  } else {
    section.append(node("p", "Métriques T10 avant F10 indisponibles."));
  }
  if (comparison?.runs?.length) {
    const scores = comparison.runs.map(run => ratio(run.accuracy?.numerator, run.accuracy?.denominator)).join(" et ");
    const sport = comparison.runs.map(run => ratio(run.correct_sport_cases, metrics?.accuracy_by_category?.sport?.denominator));
    const diffs = comparison.runs.every(run => Array.isArray(run.different_cases))
      ? [...new Set(comparison.runs.flatMap(run => run.different_cases))] : null;
    const changes = diffs === null ? "Différences par cas indisponibles." :
      (diffs.length ? `Cas avec un écart : ${diffs.join(", ")}.` : "Aucun écart par cas observé.");
    const deliveredOn = tracking.reperes.find(event => event.preuves.includes("vs1-recu"))?.date;
    section.append(node("p", `${date(deliveredOn)} · Scores du rejeu T10 en fusion VS1 ${scores} · Sport ${[...new Set(sport)].join(" et ")}. Comparaison sur la source F10 ${comparison.baseline_sha?.slice(0, 8) ?? "indisponible"}. ${changes}`));
  } else {
    section.append(node("p", "Comparaison T10 après fusion VS1 indisponible."));
  }
  if (receipt?.merged_commit && receipt.ci?.head_sha === receipt.merged_commit) {
    const outcome = receipt.ci.conclusion === "success" ? "CI réussie" : "Réussite de la CI indisponible";
    const ci = node("p", `Fusion ${receipt.merged_commit} · ${outcome} sur ce SHA`, "source-note");
    const pull = githubNumber(receipt.pr, "pull");
    const run = githubNumber(receipt.ci.run, "actions/runs");
    if (pull) ci.append(document.createTextNode(" · "), link(`PR #${pull}`, receipt.pr));
    if (run) ci.append(document.createTextNode(" · "), link(`CI #${run}`, receipt.ci.run));
    section.append(ci);
  }
  const vs1 = receipt?.after?.VS1;
  const distance = vs1?.measures?.find(measure => measure.id === "distance");
  if (distance?.source?.text && vs1.distance?.status === "known") {
    section.append(node("p", `VS1 · « ${distance.source.text} » retenu, ${format(vs1.distance.value, vs1.distance.unit)} normalisés. Le cas « objectif seul » indique ${receipt.after.OBJECTIF?.distance?.status === "absent" ? "une distance non renseignée" : "un statut à relire dans le reçu"}.`));
  } else {
    section.append(node("p", "Résultat de livraison VS1 indisponible."));
  }
  section.append(evidenceLinks(["t10-mesures", "t10-manifeste", "vs1-comparaison", "vs1-recu"], tracking.preuves, sources));
  return section;
}

function addProbe(tracking, sources) {
  const section = panel("Sonde Qwen3 4B · format JSON");
  const probe = sources["sonde-mesures"]?.data;
  const manifest = sources["sonde-manifeste"]?.data;
  if (!probe?.schema || !probe.json) {
    section.append(node("p", "Mesures de la sonde indisponibles."));
    return section;
  }
  const total = manifest?.cases?.length * manifest?.repetitions;
  section.append(node("p",
    `${date(manifest?.start)} · ${manifest?.model ?? "Modèle indisponible"} · digest ${manifest?.tag_digest?.slice(0, 12) ?? "indisponible"} · source ${manifest?.commit?.slice(0, 8) ?? "indisponible"}. ${manifest?.cases?.length ?? "Effectif indisponible"} cas choisis et ${manifest?.repetitions ?? "nombre de"} répétitions par format.`,
    "source-note"));
  table(section, "Comparaison des formats Qwen3 4B", ["Format", "Structures valides", "Exacts", "F10", "Médiane"], [
    ["JSON libre", probe.json], ["Schéma adapté", probe.schema],
  ].map(([label, run]) => [
    label, ratio(run.schema, total), ratio(run.exact, total),
    ratio(run.by_case?.F10?.filter(item => item.exact).length, run.by_case?.F10?.length),
    format(run.median_ms, "ms"),
  ]));
  section.append(node("p", `Pic d’empreinte échantillonné de la sonde ${inMio(probe.peak_sampled_process_footprint_bytes, 1024 ** 2)}. Le protocole principal et le parcours HTTP du journal mesurent d’autres populations.`, "source-note"));
  section.append(evidenceLinks(["sonde-mesures", "sonde-manifeste"], tracking.preuves, sources));
  return section;
}

function timeline(tracking, sources) {
  const section = panel("Chronologie");
  const list = node("ol", undefined, "timeline");
  for (const event of tracking.reperes) {
    const row = node("li", undefined, "event");
    const body = node("div");
    body.append(node("h3", event.titre), node("p", event.texte), evidenceLinks(event.preuves, tracking.preuves, sources));
    row.append(time(event.date), body);
    list.append(row);
  }
  section.append(list);
  return section;
}

export async function showTracking() {
  if (loading) return;
  loading = true;
  try {
    const response = await fetch("/ecran/suivi.json", { cache: "no-store" });
    if (!response.ok) throw new Error();
    const tracking = await response.json();
    const dateBadge = document.querySelector("#tracking-date");
    dateBadge.textContent = date(tracking.maj);
    dateBadge.hidden = false;

    const decision = panel(tracking.decision.titre, "decision-panel");
    decision.prepend(node("span", tracking.encours, "pill"));
    decision.append(node("p", tracking.decision.texte), time(tracking.decision.date));

    const stack = node("div", undefined, "tracking-stack");
    stack.append(decision, node("p", "Chargement des preuves…", "muted"));
    content.replaceChildren(stack);

    const keys = Object.keys(tracking.preuves);
    const sources = Object.fromEntries(await Promise.all(
      keys.map(async key => [key, await loadEvidence(sourceHref(key), dataKeys.has(key))])));
    stack.replaceChildren(decision, addT10(tracking, sources), addBench(tracking, sources), addProbe(tracking, sources), timeline(tracking, sources));
  } catch {
    content.replaceChildren(node("p", "Le suivi est indisponible. Rechargez l’écran pour réessayer.", "panel muted"));
  } finally {
    loading = false;
  }
}


const liveCollector = document.querySelector("#live-collector");
const liveTasks = document.querySelector("#live-tasks");
const liveMemory = document.querySelector("#live-memory");
const instant = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "short", timeStyle: "medium", timeZone: "Europe/Paris",
});
const serviceNames = [["java", "Spring Boot"], ["python", "FastAPI"], ["postgres", "PostgreSQL · parent"]];
const roles = { principal: "Principal", "sous-agent": "Sous-agent", demandeur: "Demandeur" };
const sourceStatus = {
  non_lu: "Lecture en attente", indisponible: "Source indisponible",
  hors_perimetre: "Session hors périmètre", lecture_en_cours: "Lecture en cours",
};
const pressureLabels = { 1: "Normale", 2: "Avertissement", 4: "Critique" };
let liveData;
let liveNetworkError = false;
let liveLoading = false;
let pollTimer;
let clockTimer;

function observedAt(value) {
  const parsed = Date.parse(value?.replace(/(\.\d{3})\d+Z$/, "$1Z"));
  return Number.isFinite(parsed) ? instant.format(parsed) : "Indisponible";
}

function duration(value) {
  const seconds = Math.max(0, Math.floor(value));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor(seconds / 60) % 60;
  return [hours ? `${hours} h` : "", minutes || hours ? `${minutes} min` : "", `${seconds % 60} s`]
    .filter(Boolean).join(" ");
}

function updateClock(clock, at) {
  const elapsed = clock.dataset.end
    ? Number(clock.dataset.elapsed)
    : Math.max(0, (at - Date.parse(clock.dataset.start)) / 1000);
  if (!Number.isFinite(elapsed)) return;
  let gapText = "Écart indisponible";
  if (clock.dataset.low !== undefined) {
    const low = Number(clock.dataset.low) * 60;
    const high = Number(clock.dataset.high) * 60;
    const gap = elapsed - Math.min(Math.max(elapsed, low), high);
    gapText = gap === 0 ? "Dans la fourchette"
      : `${gap < 0 ? "−" : "+"}${duration(Math.abs(gap))} · ${gap < 0 ? "sous la borne basse" : "au-delà de la borne haute"}`;
  }
  const text = `Temps mural · ${duration(elapsed)} · ${gapText}`;
  if (clock.textContent !== text) clock.textContent = text;
}

function updateLiveClocks() {
  const at = Date.now();
  for (const clock of liveTasks.querySelectorAll("[data-live-clock]")) updateClock(clock, at);
  const sample = liveData?.latest_sample;
  const age = sample ? Math.max(0, (at - Date.parse(sample.at)) / 1000) : null;
  const valid = sample && serviceNames.some(([key]) => Number.isFinite(sample[key]));
  let state = "Collecte indisponible";
  if (age !== null) {
    state = age > liveData.sample_interval_seconds * 3 ? `Relevé en retard · ${duration(age)}`
      : valid ? `Relevé il y a ${duration(age)}` : "RSS indisponible";
  }
  if (liveNetworkError) state += " · actualisation impossible";
  if (liveCollector.textContent !== state) liveCollector.textContent = state;
}

function liveMemoryOverview(sample) {
  const block = node("div", undefined, "live-memory");
  block.append(node("h3", "Mémoire de la démo locale"));
  if (!sample) {
    block.append(node("p", "Aucun échantillon disponible.", "muted"));
    return block;
  }
  const values = serviceNames.map(([key, label]) => `${label} ${inMio(sample[key], 1024)}`);
  const pressure = sample.pressure === null ? "indisponible" : (pressureLabels[sample.pressure] ?? `niveau ${sample.pressure}`);
  block.append(node("p", values.join(" · ")),
    node("p", `RSS observé le ${observedAt(sample.at)} · Pression système ${pressure}.`, "muted"));
  return block;
}

function liveSessionRows(task) {
  return task.sessions.map(session => {
    const tokens = session.tokens;
    const known = session.snapshots > 0;
    const usage = known ? [
      `${number.format(tokens.input_tokens)} entrée (${tokens.cached_input_tokens === null
        ? "cache indisponible" : `dont ${number.format(tokens.cached_input_tokens)} en cache`})`,
      `${number.format(tokens.output_tokens)} sortie (${tokens.reasoning_output_tokens === null
        ? "inclusion du raisonnement non attestée" : `dont ${number.format(tokens.reasoning_output_tokens)} de raisonnement`})`,
      `${number.format(tokens.total_tokens)} au total`,
    ].join(" · ") : "Indisponibles";
    const notes = [];
    if (known) notes.push(`${session.snapshots} relevé(s) · dernier ${observedAt(session.last_at)}`);
    if (session.missing_snapshots) notes.push(`${session.missing_snapshots} relevé(s) incomplet(s)`);
    if (session.counter_resets) notes.push(`${session.counter_resets} remise(s) à zéro observée(s)`);
    if (session.boundary_snapshots) notes.push(`${session.boundary_snapshots} relevé(s) à la frontière de début`);
    if (sourceStatus[session.source_status]) notes.push(sourceStatus[session.source_status]);
    return [
      `${roles[session.role]} #${session.number}`, session.models.join(", ") || "Indisponible", usage,
      notes.join(" · ") || "Aucun compteur dans la fenêtre",
    ];
  });
}

function lotEvidenceIds(task) {
  return (task.evidence_ids ?? []).filter(id => typeof id === "string" && lotEvidenceId.test(id));
}

function liveTaskDetails(task, openSamples, sources) {
  const block = node("article", undefined, "live-task");
  const title = node("h3", task.id);
  title.append(node("span", task.status === "actif" ? "En cours" : "Terminée", "pill live-state"));
  block.append(title);
  const details = node("dl", undefined, "live-task-details");
  for (const [label, value] of [
    ["Objectif", task.objective],
    ["Responsable", task.owner],
    ["Critère de fin", task.completion_criterion],
  ]) {
    details.append(node("dt", label), node("dd", value ?? "Non renseigné", value == null ? "muted" : ""));
  }
  block.append(details);
  const proofs = lotEvidenceIds(task);
  if (proofs.length) block.append(evidenceLinks(proofs, null, sources, lotEvidenceHref));
  const clock = node("p", undefined, "live-clock");
  clock.dataset.liveClock = "";
  clock.dataset.start = task.started_at;
  clock.dataset.end = task.finished_at ?? "";
  clock.dataset.elapsed = task.elapsed_seconds;
  if (task.estimate) {
    clock.dataset.low = task.estimate.min_minutes;
    clock.dataset.high = task.estimate.max_minutes;
  }
  updateClock(clock, Date.now());
  const estimate = task.estimate
    ? `${task.estimate.min_minutes}–${task.estimate.max_minutes} min · estimées le ${observedAt(task.estimate.estimated_at)}`
    : "Estimation initiale inconnue";
  const finished = task.finished_at ? ` · fin ${observedAt(task.finished_at)}` : "";
  block.append(node("p", `Début ${observedAt(task.started_at)}${finished} · ${estimate}`, "live-times muted"), clock);
  if (task.sessions.length) {
    table(block, "Compteurs Codex par session", ["Session", "Modèle observé", "Jetons", "Collecte"], liveSessionRows(task));
    block.append(node("p", "Jetons attribués à la date d’émission du compteur, par session. Les appels qui chevauchent une borne ne sont pas ventilés.", "source-note"));
  } else {
    block.append(node("p", "Aucune session Codex inscrite pour mesurer les jetons.", "muted"));
  }
  const samples = node("details");
  samples.dataset.liveSamples = task.id;
  samples.open = openSamples.has(task.id);
  const peaks = serviceNames.map(([key, label]) => `${label} ${inMio(task.memory[key], 1024)}`);
  samples.append(node("summary", "Pics RSS et derniers échantillons"));
  if (task.memory.count === 0) {
    samples.append(node("p", "Aucun relevé mémoire dans cette fenêtre.", "muted"));
  } else {
    samples.append(node("p", `${task.memory.count} échantillon(s) du ${observedAt(task.memory.first_at)} au ${observedAt(task.memory.last_at)} · maximum par service.`),
      node("p", peaks.join(" · ")));
    table(samples, "Derniers échantillons RSS en Mio", ["Relevé", ...serviceNames.map(([, label]) => label)],
      task.recent_memory_samples.map(row => [observedAt(row.at), ...serviceNames.map(([key]) => inMio(row[key], 1024))]));
  }
  block.append(samples);
  return block;
}

function renderLive(data, sources) {
  const openSamples = new Set([...liveTasks.querySelectorAll("details[data-live-samples][open]")]
    .map(details => details.dataset.liveSamples));
  const historyOpen = liveTasks.querySelector(".live-tasks-history")?.open;
  const blocks = data.active_tasks.map(task => liveTaskDetails(task, openSamples, sources));
  if (!blocks.length) blocks.push(node("p", "Aucune tâche en cours.", "muted"));
  if (data.history.length) {
    const history = node("details", undefined, "live-tasks-history");
    history.open = historyOpen ?? (data.active_tasks.length === 0);
    history.append(node("summary", "Tâches terminées"),
      ...data.history.map(task => liveTaskDetails(task, openSamples, sources)));
    blocks.push(history);
  }
  liveTasks.replaceChildren(...blocks);
  liveMemory.replaceChildren(liveMemoryOverview(data.latest_sample));
}

async function refreshLive() {
  if (liveLoading || document.hidden) return;
  liveLoading = true;
  try {
    const response = await fetch("/api/local/suivi/direct", { cache: "no-store", signal: AbortSignal.timeout(4000) });
    if (!response.ok) throw new Error();
    const data = await response.json();
    if (data.schema_version !== 1) throw new Error();
    const keys = new Set([...data.active_tasks, ...data.history].flatMap(lotEvidenceIds));
    const sources = Object.fromEntries(await Promise.all(
      [...keys].map(async key => [key, await loadEvidence(lotEvidenceHref(key))])));
    liveData = data;
    liveNetworkError = false;
    renderLive(data, sources);
  } catch {
    liveNetworkError = true;
    if (!liveData) liveTasks.replaceChildren(node("p", "Aucun relevé du collecteur disponible.", "muted"));
  } finally {
    liveLoading = false;
    updateLiveClocks();
  }
}

export function watchLiveTracking(enabled) {
  clearInterval(pollTimer);
  clearInterval(clockTimer);
  if (!enabled) return;
  refreshLive();
  pollTimer = setInterval(refreshLive, 5000);
  clockTimer = setInterval(updateLiveClocks, 1000);
}

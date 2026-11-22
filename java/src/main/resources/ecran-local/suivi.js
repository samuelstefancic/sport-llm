const dataKeys = new Set([
  "t10-mesures", "t10-manifeste", "banc-mesures", "banc-memoire", "sonde-mesures",
  "sonde-manifeste", "vs1-recu", "vs1-comparaison",
]);
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

function evidenceLinks(keys, tracking, sources) {
  const list = node("ul", undefined, "evidence-list");
  for (const key of keys) {
    const item = node("li");
    const label = tracking.preuves[key];
    if (sources[key]?.available) item.append(link(label, sourceHref(key)));
    else item.append(node("span", `${label} · source indisponible`, "muted"));
    list.append(item);
  }
  return list;
}

async function loadEvidence(key) {
  try {
    const isData = dataKeys.has(key);
    const response = await fetch(sourceHref(key), { method: isData ? "GET" : "HEAD", cache: "no-store" });
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
  section.append(evidenceLinks(["banc-protocole", "banc-mesures", "banc-memoire"], tracking, sources));
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
  section.append(evidenceLinks(["t10-mesures", "t10-manifeste", "vs1-comparaison", "vs1-recu"], tracking, sources));
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
  section.append(evidenceLinks(["sonde-mesures", "sonde-manifeste"], tracking, sources));
  return section;
}

function timeline(tracking, sources) {
  const section = panel("Chronologie");
  const list = node("ol", undefined, "timeline");
  for (const event of tracking.reperes) {
    const row = node("li", undefined, "event");
    const body = node("div");
    body.append(node("h3", event.titre), node("p", event.texte), evidenceLinks(event.preuves, tracking, sources));
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
    const sources = Object.fromEntries(await Promise.all(keys.map(async key => [key, await loadEvidence(key)])));
    stack.replaceChildren(decision, addT10(tracking, sources), addBench(tracking, sources), addProbe(tracking, sources), timeline(tracking, sources));
  } catch {
    content.replaceChildren(node("p", "Le suivi est indisponible. Rechargez l’écran pour réessayer.", "panel muted"));
  } finally {
    loading = false;
  }
}

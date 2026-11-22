const field = name => document.getElementById("qwen-" + name);
const form = field("form");
const text = field("text");
const mode = field("mode");
const prompt = field("prompt");
const temperature = field("temperature");
const tokens = field("tokens");
const feedback = field("feedback");
const run = field("run");
const load = field("load");
const refresh = field("refresh");
const example = field("example");
const reset = field("reset-prompt");
const memory = [];
const drafts = {};
const format = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 });
const clock = new Intl.DateTimeFormat("fr-FR", { timeStyle: "medium" });
const modes = { reference: "Référence pré-T11", citations: "Variante repas et citations", passages: "Sélection de passages" };
const oracle = {
  pass: "F10 réussi",
  fail: "F10 échoué",
  not_evaluated: "F10 non évalué",
  not_applicable: "Oracle F10 inapplicable",
};
const labels = {
  invalid_request: "Vérifiez la consigne, le texte, la température et le plafond de jetons.",
  request_too_large: "La requête dépasse la taille autorisée.",
  invalid_passages: "La déclaration doit donner entre un et quarante passages.",
  ollama_unavailable: "Le serveur Ollama est inaccessible sur 127.0.0.1:11434.",
  ollama_timeout: "Le délai d’attente du laboratoire est écoulé.",
  ollama_http_error: "Ollama a refusé la demande.",
  ollama_invalid_response: "Ollama a renvoyé une réponse inattendue.",
  ollama_response_too_large: "La réponse d’Ollama est trop volumineuse.",
  qwen_not_installed: "Le modèle qwen3:4b est absent d’Ollama.",
  qwen_busy: "Un chargement ou un essai est déjà en cours sur cet écran ou l’instance d’essai.",
  qwen_disabled: "Le lanceur de l’écran doit activer le laboratoire.",
  qwen_backend_unavailable: "Le service Python du laboratoire est indisponible.",
  qwen_lock_unavailable: "Le verrou du laboratoire est indisponible.",
  local_origin_required: "Ouvrez le laboratoire depuis l’adresse locale indiquée par le lanceur.",
};

let config;
let installed = null;
let busy = false;
let checking = false;
let attemptNumber = 0;

function node(tag, content, className) {
  const element = document.createElement(tag);
  if (content != null) element.textContent = content;
  if (className) element.className = className;
  return element;
}

function message(value = "", error = false) {
  feedback.textContent = value;
  feedback.classList.toggle("error", error);
}

function errorText(code) {
  return labels[code] ?? "Le laboratoire est momentanément indisponible.";
}

function buttons() {
  run.disabled = !config || installed !== true || busy || checking;
  load.disabled = run.disabled;
  refresh.disabled = busy || checking;
  example.disabled = !config;
  reset.disabled = !config;
}

function setHint() {
  field("oracle-hint").textContent = config && text.value === config.example.text
    ? "Oracle applicable · exemple fictif F10, révision 2."
    : "Oracle F10 inapplicable à cette déclaration. Le format et les citations restent vérifiés.";
}

function definitions(list, values) {
  list.replaceChildren();
  for (const [label, value] of Object.entries(values)) list.append(node("dt", label), node("dd", value));
  return list;
}

async function request(operation, args) {
  const options = { cache: "no-store", mode: "same-origin" };
  if (args !== undefined) {
    options.method = "POST";
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(args);
  }
  const response = await fetch("/api/local/qwen/" + operation, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error);
  return data;
}

async function checkStatus(announce = true) {
  if (checking) return;
  checking = true;
  buttons();
  if (announce) message("Lecture de l’état Ollama…");
  try {
    const result = await request("status");
    installed = result.installed;
    if (!config) {
      config = result;
      prompt.value = config.prompts[mode.value];
      text.value = config.example.text;
      setHint();
    }
    definitions(field("server-status"), {
      "Modèle": result.model,
      "Adresse": result.host + ":" + result.port,
      "Installation": result.installed == null ? "Inconnue" : result.installed ? "Installé" : "Absent",
      "Résidence": result.resident == null ? "Inconnue" : result.resident ? "En mémoire" : "Hors mémoire",
    });
    if (announce) message(result.error ? errorText(result.error) : "", Boolean(result.error));
  } catch (error) {
    installed = null;
    definitions(field("server-status"), {
      "Modèle": "qwen3:4b", "Adresse": "127.0.0.1:11434", "Installation": "Inconnue", "Résidence": "Inconnue",
    });
    if (announce) message(errorText(error.message), true);
  } finally {
    checking = false;
    buttons();
  }
}

function expandable(title, content) {
  const details = node("details");
  details.append(node("summary", title), content);
  return details;
}

function measured(value, unit, divisor = 1) {
  return value == null ? "Inconnu" : format.format(value / divisor) + (unit ? " " + unit : "");
}

function verdict(value) {
  return value == null ? "Non évalué" : value ? "Oui" : "Non";
}

function showEvidence(args, result) {
  const evidence = node("div", null, "qwen-source-and-mentions");
  const source = node("div");
  source.append(node("h3", "Déclaration envoyée"), node("p", args.text, "qwen-declaration"));
  const extracted = node("div");
  extracted.append(node("h3", result.passages ? "Passages recopiés et valeurs proposées" : "Citations et valeurs proposées"));
  if (!result.mentions.length) extracted.append(node("p", "Aucune mention exploitable.", "source-note"));
  const list = node("ol", null, "qwen-mention-list");
  for (const item of result.mentions) {
    const entry = node("li");
    const states = { cooked: "cuit", raw: "cru", unknown: "état inconnu" };
    const quantity = item.value == null ? "Quantité inconnue" : item.value + " " + item.unit;
    const food = item.expected_food ? "Attendu : " + item.expected_food + " · Proposé : " : "";
    entry.append(node("strong", food + quantity + " · " + states[item.state]));
    if (item.quote != null) entry.append(node("p", (item.passage_id ? item.passage_id + " · " : "") + "« " + item.quote + " »"));
    entry.append(node("p", "Citation verbatim " + verdict(item.verbatim).toLowerCase(), "source-note"));
    if (item.anchor_ok != null) {
      const criterion = item.expected_food === "riz" ? "Rejet intégral des 150 g" : "Maintien intégral du poulet";
      entry.append(node("p", criterion + " " + verdict(item.anchor_ok).toLowerCase()
        + " · Quantité exacte " + verdict(item.quantity_ok).toLowerCase()
        + " · État exact " + verdict(item.state_ok).toLowerCase(), "source-note"));
    }
    list.append(entry);
  }
  extracted.append(list);
  evidence.append(source, extracted);
  return evidence;
}

function download(attempt) {
  const { args, result, error, number, date } = attempt;
  const artifact = {
    schema_version: "1.0.0",
    date: date.toISOString(),
    attempt: number,
    model: result?.model ?? { name: "qwen3:4b", digest: null, ollama_version: null },
    entry: args.text,
    prompt: args.prompt,
    mode: args.mode,
    requested_options: { temperature: args.temperature, max_tokens: args.max_tokens },
    generation: result?.generation ?? null,
    passages_supplied: result?.passages ?? null,
    native_output: result?.raw ?? null,
    extraction: result ? { checks: result.checks, mentions: result.mentions, reasons: result.errors } : null,
    done_reason: result?.done_reason ?? null,
    metrics: result?.metrics ?? null,
    error: error ?? null,
  };
  const blob = new Blob([JSON.stringify(artifact, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = node("a");
  link.href = url;
  link.download = "llmsport-qwen-essai-" + number + ".json";
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function attemptCard(attempt, latest) {
  const { args, result, error, number, date } = attempt;
  const content = node("div");
  const label = error ? "Essai interrompu" : oracle[result.checks.oracle_f10];
  content.append(node("p", "Température " + format.format(args.temperature) + " · Plafond " + args.max_tokens + " jetons", "source-note"));
  if (error) {
    content.append(node("p", error, "feedback error"), expandable("Déclaration envoyée", node("pre", args.text, "qwen-pre")));
  } else {
    const { checks, metrics } = result;
    content.append(showEvidence(args, result));
    content.append(node("p", "JSON valide " + verdict(checks.json).toLowerCase()
      + " · Structure valide " + verdict(checks.structure).toLowerCase()
      + " · Citations verbatim " + verdict(checks.citations).toLowerCase(), "source-note"));
    if (result.errors.length) {
      const list = node("ul");
      for (const reason of result.errors) list.append(node("li", reason));
      content.append(list);
    }
    content.append(definitions(node("dl", null, "qwen-definitions"), {
      "Latence murale Ollama": measured(metrics.wall_ns, "ms", 1e6),
      "Temps total Ollama": measured(metrics.ollama_total_ns, "ms", 1e6),
      "Temps de charge Ollama": measured(metrics.ollama_load_ns, "ms", 1e6),
      "Jetons d’entrée": measured(metrics.prompt_tokens),
      "Jetons générés": measured(metrics.output_tokens),
      "Débit de génération": measured(metrics.output_tokens_per_s, "jetons/s"),
      "Pic RSS échantillonné": measured(metrics.peak_tree_rss_kib, "Mio", 1024),
      "PID du serveur · relevés": measured(metrics.server_pid) + " · " + measured(metrics.rss_samples),
    }));
    content.append(node("p", "Murale sur l’appel FastAPI → Ollama. RSS du serveur et de ses descendants, relevé toutes les 250 ms environ. La somme peut compter des pages partagées et manquer un pic bref. Le RSS exclut toute mesure distincte de l’occupation GPU.", "source-note"));
    if (result.passages) {
      content.append(expandable("Passages fournis au modèle", node("pre", JSON.stringify(result.passages, null, 2), "qwen-pre")));
    }
    content.append(expandable("Sortie brute du modèle", node("pre", result.raw || "Sortie vide", "qwen-pre")));
  }
  content.append(expandable("Consigne envoyée", node("pre", args.prompt, "qwen-pre")));
  const exportButton = node("button", "Télécharger l’essai JSON", "button secondary qwen-export");
  exportButton.type = "button";
  exportButton.addEventListener("click", () => download(attempt));
  content.append(exportButton);
  const entry = node("li", null, "panel");
  const details = expandable("Essai " + number + " · " + modes[args.mode] + " · " + label + " · " + clock.format(date), content);
  details.open = latest;
  entry.append(details);
  return entry;
}

function addAttempt(args, result, error) {
  memory.unshift({ args, result, error, number: ++attemptNumber, date: new Date() });
  if (memory.length > 3) memory.pop();
  field("empty").hidden = true;
  field("history").replaceChildren(...memory.map((attempt, index) => attemptCard(attempt, index === 0)));
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (run.disabled) return;
  const args = { text: text.value, mode: mode.value, prompt: prompt.value,
    temperature: temperature.valueAsNumber, max_tokens: tokens.valueAsNumber };
  const encode = new TextEncoder();
  if (encode.encode(args.text).length > config.limits.text_bytes || encode.encode(args.prompt).length > config.limits.prompt_bytes
      || !args.text.trim() || !args.prompt.trim()) {
    message(errorText("invalid_request"), true);
    return;
  }
  busy = true;
  buttons();
  message("Essai en cours…");
  try {
    const result = await request("run", args);
    addAttempt(args, result);
    message("Essai terminé. " + oracle[result.checks.oracle_f10] + ".");
  } catch (error) {
    const detail = errorText(error.message);
    addAttempt(args, null, detail);
    message(detail, true);
  } finally {
    await checkStatus(false);
    busy = false;
    buttons();
  }
});

load.addEventListener("click", async () => {
  if (load.disabled) return;
  busy = true;
  buttons();
  message("Chargement du modèle…");
  try {
    await request("load", {});
    message("Ollama a confirmé la demande de chargement.");
  } catch (error) {
    message(errorText(error.message), true);
  } finally {
    await checkStatus(false);
    busy = false;
    buttons();
  }
});

refresh.addEventListener("click", () => checkStatus());
text.addEventListener("input", setHint);
prompt.addEventListener("input", () => { drafts[mode.value] = prompt.value; });
mode.addEventListener("change", () => {
  if (config) prompt.value = drafts[mode.value] ?? config.prompts[mode.value];
});
reset.addEventListener("click", () => {
  delete drafts[mode.value];
  prompt.value = config.prompts[mode.value];
  prompt.focus();
});
example.addEventListener("click", () => {
  text.value = config.example.text;
  setHint();
  text.focus();
});

export function openQwenLab() {
  if (!busy) checkStatus();
}

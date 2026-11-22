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
const modes = {
  reference: "Référence pré-T11", citations: "Variante repas et citations",
  passages: "Passages · JSON libre", passages_schema: "Passages · JSON Schema",
};
const evaluationLabels = {
  structure_error: "Échec de structure", citation_error: "Échec de citation",
  oracle_failed: "Écart avec l’attendu", success: "Succès", exploratory: "Exploratoire", interrupted: "Interrompu",
};
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
  qwen_storage_unavailable: "Le dossier des jeux ou séries est inaccessible.",
  qwen_storage_full: "Le dossier a atteint sa limite de 100 fichiers.",
  qwen_invalid_record: "Vérifiez le nom, les textes, le format des attendus et leurs ancres.",
  qwen_invalid_id: "L’identifiant est invalide.",
  qwen_record_not_found: "Le fichier demandé est absent.",
  qwen_model_changed: "L’empreinte du modèle a changé pendant la série.",
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
let savedGame = null;
let f10Case = null;
let directory = "";
let checkingGames = false;
let gameIO = false;
let seriesAction = false;
let seriesView = 0;
const gameForm = field("game-form");
const gameCases = field("game-cases");
const gameSelect = field("game-select");
const seriesSelect = field("series-select");

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
  run.disabled = !config || installed !== true || busy || checking || seriesAction;
  load.disabled = run.disabled;
  refresh.disabled = busy || checking || seriesAction;
  example.disabled = !config;
  reset.disabled = !config;
  field("game-add-case").disabled = gameCases.childElementCount >= 5;
  field("game-add-f10").disabled = !f10Case || field("game-add-case").disabled;
  field("game-save").disabled = gameIO || !gameCases.childElementCount;
  field("game-open").disabled = gameIO || !gameSelect.value;
  field("series-open").disabled = !seriesSelect.value || seriesAction;
  field("series-start").disabled = run.disabled || gameIO || !savedGame;
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
      prompt.value = config.prompts[promptKey()];
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

function showEvidence(args, result, showF10) {
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
    const food = showF10 && item.expected_food ? "Attendu : " + item.expected_food + " · Proposé : " : "";
    entry.append(node("strong", food + quantity + " · " + states[item.state]));
    if (item.quote != null) entry.append(node("p", (item.passage_id ? item.passage_id + " · " : "") + "« " + item.quote + " »"));
    entry.append(node("p", "Citation verbatim " + verdict(item.verbatim).toLowerCase(), "source-note"));
    if (showF10 && item.anchor_ok != null) {
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
  const { args, result, error, number, date, name, evaluation } = attempt;
  const content = node("div");
  const label = evaluation ? evaluationLabels[evaluation.verdict]
    : error ? "Essai interrompu" : oracle[result.checks.oracle_f10];
  content.append(node("p", "Température " + format.format(args.temperature) + " · Plafond " + args.max_tokens + " jetons", "source-note"));
  if (error) {
    content.append(node("p", error, "feedback error"), expandable("Déclaration envoyée", node("pre", args.text, "qwen-pre")));
  } else {
    const { checks, metrics } = result;
    content.append(showEvidence(args, result, !evaluation));
    content.append(node("p", "JSON valide " + verdict(checks.json).toLowerCase()
      + " · Structure valide " + verdict(checks.structure).toLowerCase()
      + " · Citations verbatim " + verdict(checks.citations).toLowerCase(), "source-note"));
    if (evaluation) {
      content.append(showComparison(evaluation));
      if (evaluation.verdict === "structure_error" && result.errors[0]) {
        content.append(node("p", result.done_reason === "length" ? "Plafond de génération atteint." : result.errors[0], "source-note"));
      }
      content.append(node("p", "Empreinte du modèle " + (result.model.digest ?? "inconnue")
        + " · Ollama " + (result.model.ollama_version ?? "version inconnue")
        + " · Motif d’arrêt " + (result.done_reason ?? "inconnu"), "source-note"));
    } else if (result.errors.length) {
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
  if (!evaluation) {
    const exportButton = node("button", "Télécharger l’essai JSON", "button secondary qwen-export");
    exportButton.type = "button";
    exportButton.addEventListener("click", () => download(attempt));
    content.append(exportButton);
  }
  const entry = node("li", null, "panel");
  const details = expandable((name ?? ("Essai " + number)) + " · " + modes[args.mode] + " · " + label + " · " + clock.format(date), content);
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
  const args = { ...settings(), text: text.value };
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
function promptKey() {
  return mode.value === "passages_schema" ? "passages" : mode.value;
}

function settings() {
  return { mode: mode.value, prompt: prompt.value, temperature: temperature.valueAsNumber, max_tokens: tokens.valueAsNumber };
}

prompt.addEventListener("input", () => { drafts[promptKey()] = prompt.value; });
mode.addEventListener("change", () => {
  if (config) prompt.value = drafts[promptKey()] ?? config.prompts[promptKey()];
});
reset.addEventListener("click", () => {
  delete drafts[promptKey()];
  prompt.value = config.prompts[promptKey()];
  prompt.focus();
});
example.addEventListener("click", () => {
  text.value = config.example.text;
  setHint();
  text.focus();
});

export function openQwenLab() {
  if (!busy && !seriesAction) checkStatus();
  refreshRecords();
}

function showComparison(evaluation) {
  const panel = node("div");
  if (!evaluation.differences.length) {
    if (evaluation.expected === null) {
      panel.append(node("p", "Aucun attendu renseigné.", "source-note"));
    }
    return panel;
  }
  const quantity = value => value === null ? "sans quantité" : value.value + " " + value.unit;
  const states = { cooked: "cuit", raw: "cru", unknown: "état inconnu" };
  panel.append(node("h3", "Comparaison avec l’attendu du jeu"));
  const list = node("ol", null, "qwen-mention-list");
  for (const row of evaluation.differences) {
    const entry = node("li");
    const expected = row.expected ? quantity(row.expected.quantity) + " · " + states[row.expected.state] : "mention supplémentaire";
    const observed = row.observed ? quantity(row.observed.quantity) + " · " + states[row.observed.state] : "mention absente";
    entry.append(node("p", "Attendu · " + expected), node("p", "Proposé · " + observed));
    if (row.expected) {
      entry.append(node("p", "Ancre « " + row.expected.anchor + " » couverte "
        + verdict(row.anchor_ok).toLowerCase() + " · Quantité exacte " + verdict(row.quantity_ok).toLowerCase()
        + " · État exact " + verdict(row.state_ok).toLowerCase(), "source-note"));
    }
    list.append(entry);
  }
  panel.append(list);
  return panel;
}

function gameMessage(value = "", error = false) {
  const output = field("game-feedback");
  output.textContent = value;
  output.classList.toggle("error", error);
}

function fileLink(kind, identifier) {
  const link = field(kind === "jeux" ? "game-file" : "series-file");
  link.hidden = !identifier;
  if (!identifier) return;
  link.href = "/api/local/qwen/" + kind + "/" + identifier;
  link.textContent = directory + "/" + kind + "/" + identifier + ".json";
}

function options(select, ids, empty, selected = select.value) {
  select.replaceChildren(...(ids.length ? ids : [""]).map(id => {
    const option = node("option", id || empty);
    option.value = id;
    return option;
  }));
  if (ids.includes(selected)) select.value = selected;
}

async function refreshRecords(gameId, seriesId) {
  if (checkingGames) return;
  checkingGames = true;
  try {
    const [games, histories] = await Promise.all([request("jeux"), request("series")]);
    f10Case = games.f10;
    directory = games.directory;
    field("game-directory").textContent = directory;
    options(gameSelect, games.ids, "Aucun jeu enregistré", gameId);
    options(seriesSelect, histories.ids, "Aucune série enregistrée", seriesId);
  } catch (error) {
    gameMessage(errorText(error.message), true);
  } finally {
    checkingGames = false;
    buttons();
  }
}

let editRevision = 0;

function dirtyGame() {
  editRevision += 1;
  savedGame = null;
  fileLink("jeux", null);
  buttons();
}

function caseLabel(label, control) {
  const wrapper = node("label", label);
  wrapper.append(control);
  return wrapper;
}

function appendCase(data = {}) {
  if (gameCases.childElementCount >= 5) return;
  const row = node("fieldset");
  const name = node("input");
  name.type = "text";
  name.maxLength = 100;
  name.value = data.name ?? "";
  name.required = true;
  name.dataset.case = "name";
  const source = node("textarea");
  source.rows = 3;
  source.maxLength = 4096;
  source.value = data.text ?? "";
  source.required = true;
  source.dataset.case = "text";
  const expected = node("textarea");
  expected.rows = 5;
  expected.maxLength = 12000;
  expected.spellcheck = false;
  expected.dataset.case = "expected";
  expected.value = data.expected == null ? "" : JSON.stringify(data.expected, null, 2);
  expected.placeholder = '[{"anchor":"extrait littéral","state":"unknown","quantity":null}]';
  const remove = node("button", "Retirer ce cas", "text-button");
  remove.type = "button";
  remove.addEventListener("click", () => { row.remove(); dirtyGame(); });
  row.append(node("legend", "Cas fictif"), caseLabel("Nom du cas", name), caseLabel("Déclaration", source),
    expandable("Attendu d’extraction facultatif", caseLabel("Mentions ordonnées en JSON", expected)), remove);
  gameCases.append(row);
  return name;
}

function populateGame(identifier, data) {
  field("game-id").value = identifier ?? "";
  field("game-name").value = data?.name ?? "";
  gameCases.replaceChildren();
  for (const item of data?.cases ?? [{}]) appendCase(item);
  savedGame = identifier;
  editRevision += 1;
  fileLink("jeux", identifier);
  buttons();
}

field("game-new").addEventListener("click", () => { populateGame(null, null); gameMessage(); });
field("game-add-case").addEventListener("click", () => { appendCase()?.focus(); dirtyGame(); });
field("game-add-f10").addEventListener("click", () => {
  const initial = gameCases.childElementCount === 1 && [...gameCases.querySelectorAll("input, textarea")].every(input => !input.value);
  if (initial) gameCases.replaceChildren();
  appendCase(f10Case)?.focus();
  dirtyGame();
});
gameForm.addEventListener("input", dirtyGame);
gameSelect.addEventListener("change", buttons);
seriesSelect.addEventListener("change", buttons);

field("game-open").addEventListener("click", async () => {
  const identifier = gameSelect.value;
  const revision = editRevision;
  gameIO = true;
  buttons();
  try {
    const record = await request("jeux/" + identifier);
    if (revision === editRevision) {
      populateGame(identifier, record);
      gameMessage("Jeu ouvert.");
    }
  } catch (error) {
    gameMessage(errorText(error.message), true);
  } finally {
    gameIO = false;
    buttons();
  }
});

gameForm.addEventListener("submit", async event => {
  event.preventDefault();
  if (gameIO) return;
  const identifier = field("game-id").value;
  const name = field("game-name").value;
  const revision = editRevision;
  let cases;
  try {
    cases = [...gameCases.children].map(row => {
      const read = key => row.querySelector('[data-case="' + key + '"]').value;
      const expected = read("expected");
      return { name: read("name"), text: read("text"), expected: expected.trim() ? JSON.parse(expected) : null };
    });
  } catch {
    gameMessage("L’attendu doit contenir un tableau JSON valide. Laissez le champ vide pour un cas exploratoire.", true);
    return;
  }
  gameIO = true;
  buttons();
  try {
    const result = await request("jeux/" + identifier, { name, cases });
    if (revision === editRevision) {
      savedGame = identifier;
      fileLink("jeux", identifier);
    }
    gameMessage("Jeu enregistré dans " + result.path + ".");
    await refreshRecords(identifier);
  } catch (error) {
    gameMessage(errorText(error.message), true);
  } finally {
    gameIO = false;
    buttons();
  }
});

const dateTime = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "medium" });

function renderSeries(receipt, lastProgress) {
  fileLink("series", receipt.id);
  const progress = receipt.results.length + "/" + receipt.game.cases.length;
  const status = { running: "En cours", completed: "Terminée", interrupted: "Interrompue" };
  const summary = receipt.game.name + " · " + modes[receipt.settings.mode] + " · "
    + dateTime.format(new Date(receipt.started_at)) + " · " + progress + " · " + status[receipt.status];
  field("series-summary").textContent = summary + (receipt.error ? " · " + errorText(receipt.error) : "");
  if (progress !== lastProgress) {
    field("series-results").replaceChildren(...receipt.results.map((item, index) => attemptCard({
      args: { ...receipt.settings, text: receipt.game.cases[index].text },
      result: item.outcome, evaluation: item.evaluation, name: item.name,
      error: item.error ? errorText(item.error) : null, date: new Date(item.finished_at),
    }, index === receipt.results.length - 1)));
  }
  return progress;
}

async function watchSeries(identifier) {
  const view = ++seriesView;
  let progress;
  for (;;) {
    const receipt = await request("series/" + identifier);
    if (view !== seriesView) return;
    progress = renderSeries(receipt, progress);
    if (receipt.status !== "running") return;
    await new Promise(resolve => window.setTimeout(resolve, 2000));
    if (view !== seriesView) return;
  }
}

field("series-open").addEventListener("click", async () => {
  try {
    await watchSeries(seriesSelect.value);
  } catch (error) {
    field("series-summary").textContent = errorText(error.message);
  }
});

field("series-start").addEventListener("click", async () => {
  if (field("series-start").disabled) return;
  if (!mode.reportValidity() || !prompt.reportValidity() || !temperature.reportValidity() || !tokens.reportValidity()) return;
  seriesAction = true;
  buttons();
  gameMessage("Démarrage de la série…");
  try {
    const result = await request("series", { ...settings(), game_id: savedGame });
    gameMessage("Série enregistrée dans " + result.path + ".");
    field("series-summary").textContent = "Lecture de la progression…";
    await refreshRecords(savedGame, result.id);
    await watchSeries(result.id);
  } catch (error) {
    gameMessage(errorText(error.message), true);
  } finally {
    await checkStatus(false);
    seriesAction = false;
    buttons();
  }
});

populateGame(null, null);

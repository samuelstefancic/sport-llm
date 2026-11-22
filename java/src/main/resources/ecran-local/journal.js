import { showTracking } from "./suivi.js";

const example = "Sortie à vélo : objectif 10 km, mais j’ai parcouru 4,5 km.";
const activityLabels = { cycling: "Vélo", running: "Course", mobility: "Mobilité", squat: "Squat" };
const fields = {
  distance: "Distance", duration: "Durée", sets: "Séries", repetitions: "Répétitions",
  total_repetitions: "Total de répétitions", load: "Charge",
};
const errors = {
  invalid_request: "Vérifiez que la déclaration contient entre 1 et 4 000 caractères.",
  ambiguous_activity: "Plusieurs activités ont été détectées. Décrivez une séance à la fois.",
  invalid_measure_unit: "Vérifiez l’unité indiquée pour cette mesure.",
  invalid_measure_number: "Vérifiez l’écriture des nombres dans la déclaration.",
  negative_duration: "Une durée ne peut pas être négative.",
  negative_measure: "Une mesure ne peut pas être négative.",
  invalid_count: "Le nombre de séries ou de répétitions doit être entier.",
  journal_unavailable: "Le journal est momentanément indisponible. Vous pouvez réessayer.",
  python_timeout: "L’analyse a dépassé le délai autorisé. Vous pouvez réessayer.",
  idempotency_conflict: "Cette demande entre en conflit avec un envoi précédent. Réessayez.",
  not_found: "Cette révision est introuvable dans le journal.",
};

const number = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 20 });
const elapsed = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const recorded = new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const form = document.querySelector("#entry-form");
const input = document.querySelector("#entry-text");
const submit = document.querySelector("#submit");
const fillExample = document.querySelector("#example");
const list = document.querySelector("#history-list");
const more = document.querySelector("#history-more");
const refresh = document.querySelector("#refresh");
const pendingInMemory = new Map();
const timingInMemory = new Map();
let nextOffset = null;
let activeResult = null;
let selectionVersion = 0;
let historyVersion = 0;
let submitting = false;

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
}

function readStorage(storage, key) {
  try { return JSON.parse(window[storage].getItem(key)); }
  catch { return null; }
}

function writeStorage(storage, key, value) {
  try {
    if (value === null) window[storage].removeItem(key);
    else window[storage].setItem(key, JSON.stringify(value));
  } catch {
    // The current page still retains request identity and measured times.
  }
}

function message(id, text, error = false) {
  const element = document.querySelector(id);
  element.hidden = !text;
  element.textContent = text;
  element.classList.toggle("error", error);
}

function route() {
  const tracking = window.location.hash === "#suivi";
  document.querySelector("#journal").hidden = tracking;
  document.querySelector("#suivi").hidden = !tracking;
  for (const link of document.querySelectorAll("nav a")) {
    if (link.hash === (tracking ? "#suivi" : "#journal")) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (tracking) showTracking();
}

function usableNumber(value) {
  return Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value));
}

function quantity(value, unit) {
  if (!usableNumber(value)) return "Valeur hors plage d’affichage";
  return number.format(value) + (unit === "count" ? "" : ` ${unit || "(unité à préciser)"}`);
}

function summaryValue(row) {
  if (row?.status === "known" && row.value != null) return quantity(row.value, row.unit);
  if (row?.status === "absent") return "Non renseignée";
  if (row?.status === "unresolved") return "À préciser";
  return "Indisponible";
}

function metric(container, label, value, detail) {
  const tile = node("div");
  tile.append(node("dt", label), node("dd", value));
  if (detail) tile.append(node("small", detail));
  container.append(tile);
}

function fact(container, label, value) {
  const row = node("div");
  row.append(node("dt", label), node("dd", value));
  container.append(row);
}

function resultKey(result) {
  return `${result.entry_id}:${result.entry_revision}`;
}

function selectRow() {
  for (const button of list.querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(button.dataset.key === activeResult));
  }
}

function renderResult(result, statusText) {
  const content = document.querySelector("#result-content");
  const status = document.querySelector("#result-status");
  const key = resultKey(result);
  const timing = timingInMemory.get(key) ?? readStorage("localStorage", `llmsport:elapsed:${key}`);
  const hasTiming = Number.isFinite(timing?.ms) && timing.ms >= 0;
  const distance = result.summary?.distance;
  const declared = (result.measures ?? []).filter(measure => measure.id === "distance");
  const distanceKnown = distance?.status === "known";
  status.hidden = false;
  status.textContent = statusText;

  const text = node("blockquote", result.source?.text || "Déclaration indisponible.", "result-quote");
  const metrics = node("dl", undefined, "result-metrics");
  if (distanceKnown && declared.length === 1 && declared[0].unit !== distance.unit) {
    metric(metrics, "Distance parcourue", quantity(declared[0].value, declared[0].unit),
      `${summaryValue(distance)} normalisés`);
  } else {
    metric(metrics, "Distance parcourue", summaryValue(distance));
  }
  metric(metrics, "Durée", summaryValue(result.summary?.duration));
  metric(metrics, "Latence HTTP", hasTiming ? `${elapsed.format(timing.ms)} ms` : "Indisponible",
    hasTiming
      ? (timing.retry ? "Rejeu POST mesuré dans ce navigateur" : "POST complet mesuré dans ce navigateur")
      : "Aucune mesure locale pour cette révision");
  content.replaceChildren(text, metrics);

  const sources = (distance?.sources ?? []).map(source => source.text).filter(Boolean);
  if (sources.length) {
    content.append(node("p", `Source de la distance · ${sources.map(source => `« ${source} »`).join(" · ")}`, "source-line"));
  }
  for (const { question } of result.clarifications ?? []) {
    content.append(node("p", question, "clarification"));
  }

  const detail = node("details");
  detail.append(node("summary", "Toutes les mesures et la révision"));
  const facts = node("dl", undefined, "facts");
  fact(facts, "Activité", activityLabels[result.activity] ?? (result.activity || "Non renseignée"));
  for (const [field, label] of Object.entries(fields)) {
    fact(facts, label, summaryValue(result.summary?.[field]));
  }
  fact(facts, "Dépense énergétique", result.energy_burned == null ? "Non calculée" : quantity(result.energy_burned, null));
  fact(facts, "Révision", String(result.entry_revision));
  fact(facts, "Identifiant", result.entry_id);
  detail.append(facts);

  if (result.measures?.length) {
    const declarations = node("dl", undefined, "facts");
    for (const measure of result.measures) {
      const source = measure.source?.text;
      fact(declarations, `${fields[measure.id] ?? measure.id} déclarée`,
        `${quantity(measure.value, measure.unit)}${source ? ` · « ${source} »` : ""}`);
    }
    detail.append(node("h3", "Mesures relevées dans le texte"), declarations);
  }
  content.append(detail);
  activeResult = key;
  selectRow();
}

async function body(response, content) {
  const payload = content === undefined ? await response.json() : JSON.parse(content);
  if (!response.ok) {
    const failure = new Error(errors[payload.error] || `Le serveur a répondu avec le statut HTTP ${response.status}.`);
    failure.status = response.status;
    throw failure;
  }
  return payload;
}

async function readResult(entry) {
  const version = ++selectionVersion;
  const { entry_id: id, entry_revision: revision, current_revision: current } = entry;
  message("#history-message", "Relecture de la séance…");
  try {
    const response = await fetch(`/workouts/${encodeURIComponent(id)}/revisions/${revision}`, { cache: "no-store" });
    const result = await body(response);
    if (version !== selectionVersion) return;
    if (!result.source?.text && entry.text) result.source = { text: entry.text };
    renderResult(result, revision === current ? "Relu dans le journal" : "Révision antérieure");
    message("#history-message", "");
  } catch (failure) {
    if (version === selectionVersion) {
      message("#history-message", failure.status ? failure.message : "La séance n’a pas pu être relue.", true);
    }
  }
}

async function loadHistory(offset = 0, selectFirst = false) {
  const version = ++historyVersion;
  refresh.disabled = more.disabled = true;
  message("#history-message", "Chargement du journal…");
  try {
    const response = await fetch(`/workouts?offset=${offset}`, { cache: "no-store" });
    const { entries, next_offset: next } = await body(response);
    if (version !== historyVersion) return;
    if (offset === 0) list.replaceChildren();
    const existingKeys = new Set(Array.from(list.querySelectorAll("button"), button => button.dataset.key));
    for (const entry of entries) {
      if (existingKeys.has(resultKey(entry))) continue;
      const item = node("li");
      const button = node("button");
      button.type = "button";
      button.dataset.key = resultKey(entry);
      button.append(node("span", entry.text || "Déclaration indisponible", "history-text"));
      const date = entry.recorded_at ? recorded.format(new Date(entry.recorded_at)) : "Date indisponible";
      const prior = entry.entry_revision === entry.current_revision ? "" : " antérieure";
      button.append(node("span", `${date} · r${entry.entry_revision}${prior}`, "history-meta"));
      button.addEventListener("click", () => readResult(entry));
      item.append(button);
      list.append(item);
    }
    selectRow();
    nextOffset = next;
    more.hidden = next === null;
    message("#history-message", list.childElementCount ? "" : "Aucune séance enregistrée.");
    if (selectFirst && entries.length && !activeResult && !selectionVersion) await readResult(entries[0]);
  } catch (failure) {
    if (version === historyVersion) {
      message("#history-message", failure.status ? failure.message : "Impossible de lire l’historique.", true);
    }
  } finally {
    if (version === historyVersion) refresh.disabled = more.disabled = false;
  }
}

async function declarationKey(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return "llmsport:pending:" + Array.from(digest, byte => byte.toString(16).padStart(2, "0")).join("");
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const text = input.value.trim();
  if (submitting || !text) {
    if (!submitting) message("#entry-message", "Saisissez une déclaration avant de l’envoyer.", true);
    return;
  }
  submitting = submit.disabled = fillExample.disabled = input.readOnly = true;
  message("#entry-message", "Analyse et enregistrement en cours…");
  let pendingKey;
  try {
    pendingKey = await declarationKey(text);
    const existing = pendingInMemory.get(pendingKey) ?? readStorage("sessionStorage", pendingKey);
    const id = existing ?? `local-${crypto.randomUUID()}`;
    pendingInMemory.set(pendingKey, id);
    writeStorage("sessionStorage", pendingKey, id);

    const serialized = JSON.stringify({ entry_id: id, entry_revision: 1, text });
    const beginning = performance.now();
    const request = await fetch("/workouts", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": id },
      body: serialized,
    });
    const raw = await request.text();
    const timing = { ms: performance.now() - beginning, retry: Boolean(existing) };
    const result = await body(request, raw);
    const key = resultKey(result);
    timingInMemory.set(key, timing);
    writeStorage("localStorage", `llmsport:elapsed:${key}`, timing);
    pendingInMemory.delete(pendingKey);
    writeStorage("sessionStorage", pendingKey, null);
    input.value = "";
    selectionVersion++;
    renderResult(result, "Enregistré");
    message("#entry-message", "Séance enregistrée.");
    await loadHistory();
  } catch (failure) {
    if (pendingKey && [400, 409].includes(failure.status)) {
      pendingInMemory.delete(pendingKey);
      writeStorage("sessionStorage", pendingKey, null);
    }
    message("#entry-message", failure.status ? failure.message :
      "Réponse indisponible. Réessayez avec le même texte pour reprendre l’envoi.", true);
  } finally {
    submitting = submit.disabled = fillExample.disabled = input.readOnly = false;
  }
});

fillExample.addEventListener("click", () => {
  input.value = example;
  input.focus();
});
refresh.addEventListener("click", () => loadHistory());
more.addEventListener("click", () => { if (nextOffset !== null) loadHistory(nextOffset); });
document.querySelector(".skip").addEventListener("click", event => {
  event.preventDefault();
  document.querySelector("#contenu").focus();
});
window.addEventListener("hashchange", route);
route();
loadHistory(0, true);

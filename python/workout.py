"""Extraction française bornée. Les mesures sont vérifiées et calculées par Java."""

from decimal import Decimal
import re


GROUP_SPACE = r"[ \u00a0\u2009\u202f]"
# Read the whole numeric token even for an invalid separator or group length.
NUMBER = re.compile(rf"(?<![\w.,+−-])([+−-]?[0-9]+(?:(?:[.,]|{GROUP_SPACE}+)[0-9]+)*)")
NUMBER_FORMAT = re.compile(rf"[+−-]?(?:[0-9]+|[0-9]{{1,3}}(?:{GROUP_SPACE}[0-9]{{3}})+)(?:[.,][0-9]+)?")
GROUP_SEPARATOR = re.compile(GROUP_SPACE)
COMPOUND_UNIT_COMPONENT = r"(?:h|heures?|min|minutes?|s|secondes?|km|kilom[èe]tres?|m|m[èe]tres?|j|jours?|semaines?|mois|ans?)"
COMPOUND_UNIT_TAIL = re.compile(
    rf"\s*[/⁄∕·⋅*^²³⁻]|\s+par\s+{COMPOUND_UNIT_COMPONENT}\b"
    rf"|\s+{COMPOUND_UNIT_COMPONENT}\s*⁻[⁰¹²³⁴⁵⁶⁷⁸⁹]+",
    re.IGNORECASE,
)
UNIT_PATTERNS = {
    ("duration", "s"): r"secondes?|secs?|s",
    ("duration", "min"): r"minutes?|mins?",
    ("duration", "h"): r"heures?|h",
    ("distance", "m"): r"m[èe]tres?|m",
    ("distance", "km"): r"kilom[èe]tres?|km",
    ("sets", "count"): r"s[ée]ries?",
    ("repetitions", "count"): r"r[ée]p[ée]titions?|reps?",
    ("load", "kg"): r"kilogrammes?|kilos?|kg",
}
UNITS = [(key, re.compile(rf"\s*(?:{expression})\b", re.IGNORECASE))
         for key, expression in UNIT_PATTERNS.items()]
ALTERNATIVE = re.compile(r"\s+ou\s+", re.IGNORECASE)
FIELD_LABEL = re.compile(
    r"\b(?:(?P<duration>dur[ée]e)|(?P<distance>distance(?:\s+parcourue)?)|(?P<load>charge))\s*:?\s*$",
    re.IGNORECASE,
)
ACTIVITIES = {
    "running": r"\b(?:course|couru)\b",
    "cycling": r"\b(?:vélo|velo|cyclisme|bicyclette)\b",
    "squat": r"\bsquats?\b",
    "mobility": r"\bmobilit[ée]\b",
}
UNRESOLVED_FIELDS = {
    "duration": r"\bpendant\s*$",
    "distance": r"\b(?:couru|course(?:\s+à\s+pied)?)\s*:?\s*$",
    "load": r"\b(?:r[ée]p[ée]titions?|reps?)\s*,?\s+à\s*$",
}
NEGATED = re.compile(r"\b(?:pas|ni|au lieu de)\s*$", re.IGNORECASE)


def measure(text, number, source, next_duration_start):
    prefix = text[:number.start()]
    if NEGATED.search(prefix):
        return None
    end = number.end()
    unit = None
    field = None
    for (dimension, code), pattern in UNITS:
        if found := pattern.match(text, end):
            field, unit, end = dimension, code, found.end()
            if COMPOUND_UNIT_TAIL.match(text, end):
                return None
            break
    if field is None:
        if label := FIELD_LABEL.search(prefix):
            field = label.lastgroup
        elif next_duration_start is not None and ALTERNATIVE.fullmatch(text, end, next_duration_start):
            field = "duration"
        else:
            field = next((dimension for dimension, pattern in UNRESOLVED_FIELDS.items()
                          if re.search(pattern, prefix, re.IGNORECASE)), None)
    if field is None or not NUMBER_FORMAT.fullmatch(number[1]):
        return None
    normalized = GROUP_SEPARATOR.sub("", number[1]).replace(",", ".").replace("−", "-")
    value = Decimal(normalized)
    if value < 0:
        return None
    # Les propositions arrondies ne peuvent pas servir de source pour une mesure.
    numeric = int(value) if value == value.to_integral_value() else float(value)
    if Decimal(str(numeric)) != value:
        return None
    return {"id": field, "unit": unit, "value": numeric,
            "source": {**source, "text": text[number.start():end]}}


def workout_mention(entry_id, revision, text):
    activities = [activity for activity, pattern in ACTIVITIES.items() if re.search(pattern, text, re.IGNORECASE)]
    source = {"kind": "user_declaration", "input_id": entry_id, "input_revision": revision, "text": text}
    measures = []
    next_duration_start = None
    # The written duration on the right can classify each adjacent bare choice.
    for number in reversed(list(NUMBER.finditer(text))):
        item = measure(text, number, source, next_duration_start)
        next_duration_start = number.start() if item is not None and item["id"] == "duration" else None
        if item is not None:
            measures.append(item)
    measures.reverse()
    return {"mention_id": "s1", "text": text, "activity": activities[0] if len(activities) == 1 else None,
            "source": source, "measures": measures}

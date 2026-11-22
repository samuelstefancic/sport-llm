"""Extraction française bornée. Les mesures sont vérifiées et calculées par Java."""

from decimal import Decimal
import re


GROUP_SPACE = r"[ \u00a0\u2009\u202f]"
# Read the whole numeric token even for an invalid separator or group length.
NUMBER_START = r"(?<![\w.,+−-])"
INTEGER = r"[+−-]?[0-9]+"
NUMBER_HEAD = rf"{NUMBER_START}({INTEGER}(?:(?:[.,]|{GROUP_SPACE}+)[0-9]+)*)"
COMPACT_DIGITS = r"[.,:+−-]*\d\w*(?:[.,:+−-]\d+)*"
# Consume malformed compact tokens too, so neither component becomes a standalone quantity.
NUMBER = re.compile(rf"{NUMBER_HEAD}((?:km|h){COMPACT_DIGITS})?", re.IGNORECASE)
NUMBER_FORMAT = re.compile(rf"[+−-]?(?:[0-9]+|[0-9]{{1,3}}(?:{GROUP_SPACE}[0-9]{{3}})+)(?:[.,][0-9]+)?")
GROUP_SEPARATOR = re.compile(GROUP_SPACE)
COMPACT_END = r"(?!\w|[.,:+−-]\d)"
COMPACT_DISTANCE = rf"km[0-9]{{3}}{COMPACT_END}"
COMPACT_DURATION = rf"h[0-5][0-9]{COMPACT_END}"
COMPACT_UNIT = re.compile(rf"(?P<meters>{COMPACT_DISTANCE})|(?P<minutes>{COMPACT_DURATION})", re.IGNORECASE)
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
DISTANCE_UNIT_SPELLING = "|".join(expression for (field, _), expression in UNIT_PATTERNS.items() if field == "distance")
GOAL_UNIT = rf"(?:\s*(?:{DISTANCE_UNIT_SPELLING})\b)"
GOAL_LINK = r"(?:\s*,\s*|\s+)(?:et|ou|puis)\s+"
GOAL_PART = rf"{NUMBER_HEAD}(?:km{COMPACT_DIGITS}|{GOAL_UNIT})?"
MEASURED_GOAL_PART = rf"(?:{NUMBER_START}{INTEGER}{COMPACT_DISTANCE}|{NUMBER_HEAD}{GOAL_UNIT})"
DISTANCE_GOAL = re.compile(
    r"\b(?P<reached_before>j['’]ai\s+(?:bien\s+)?atteint\s+(?:mon\s+|l['’]))?objectif(?:\s+de)?\s*:?\s*"
    rf"(?P<parts>{GOAL_PART}(?:{GOAL_LINK}{GOAL_PART})*+)"
    r"(?P<reached_after>\s+(?:est\s+)?atteint\b(?!\s*(?:\?|ou\s+non\b)))?",
    re.IGNORECASE,
)
MEASURED_GOAL_PARTS = re.compile(rf"{MEASURED_GOAL_PART}(?:{GOAL_LINK}{MEASURED_GOAL_PART})*+", re.IGNORECASE)
DURATION_UNIT_SPELLING = "|".join(expression for (field, _), expression in UNIT_PATTERNS.items() if field == "duration")
COMPACT_DURATION_CONTEXT = re.compile(
    r"\b(?:(?:en|pendant)\s+|dur[ée]e\s*:?\s*)"
    rf"(?:{NUMBER_HEAD}(?:{COMPACT_DURATION}|\s*(?:{DURATION_UNIT_SPELLING})\b)?{GOAL_LINK})*+$",
    re.IGNORECASE,
)
CLOCK_CONTEXT = re.compile(
    r"\b(?:d[ée]part|rendez[-\s]+vous|rdv)\b(?![^.,;!?\n]*\b(?:puis|mais)\b)[^.,;!?\n]*$",
    re.IGNORECASE,
)


def unmeasured_goal_parts(text):
    parts = []
    for goal in DISTANCE_GOAL.finditer(text):
        start, end = goal.span("parts")
        reached = goal["reached_before"] is not None or goal["reached_after"] is not None
        if reached and MEASURED_GOAL_PARTS.fullmatch(text, start, end):
            continue
        parts.append((start, end))
    return parts


def measure(text, number, source, next_duration_start, unmeasured_goals):
    prefix = text[:number.start()]
    if NEGATED.search(prefix):
        return None
    within_goal = any(start <= number.start() < end for start, end in unmeasured_goals)
    end = number.end()
    if number[2] is not None:
        compact = COMPACT_UNIT.fullmatch(text, number.end(1), end)
        if not compact or not re.fullmatch(INTEGER, number[1]) or COMPOUND_UNIT_TAIL.match(text, compact.end()):
            return None
        if compact["meters"] is not None:
            if within_goal:
                return None
            field, unit, factor, remainder = "distance", "m", 1000, compact["meters"][2:]
        else:
            elapsed = COMPACT_DURATION_CONTEXT.search(prefix)
            if not elapsed or CLOCK_CONTEXT.search(prefix, 0, elapsed.start()):
                return None
            if any(end <= elapsed.start() and text[end:elapsed.start()].isspace() for _, end in unmeasured_goals):
                return None
            field, unit, factor, remainder = "duration", "min", 60, compact["minutes"][1:]
        value = int(number[1].lstrip("+−-")) * factor + int(remainder)
        if value and number[1].startswith(("-", "−")):
            return None
        return {"id": field, "unit": unit, "value": value,
                "source": {**source, "text": text[number.start():compact.end()]}}
    unit = None
    field = None
    for (dimension, code), pattern in UNITS:
        if found := pattern.match(text, end):
            field, unit, end = dimension, code, found.end()
            if COMPOUND_UNIT_TAIL.match(text, end):
                return None
            if field == "distance" and within_goal:
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
    unmeasured_goals = unmeasured_goal_parts(text)
    # The written duration on the right can classify each adjacent bare choice.
    for number in reversed(list(NUMBER.finditer(text))):
        item = measure(text, number, source, next_duration_start, unmeasured_goals)
        next_duration_start = number.start() if item is not None and item["id"] == "duration" else None
        if item is not None:
            measures.append(item)
    measures.reverse()
    return {"mention_id": "s1", "text": text, "activity": activities[0] if len(activities) == 1 else None,
            "source": source, "measures": measures}

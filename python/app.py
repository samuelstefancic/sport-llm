"""Propositions déterministes pour le journal local."""

from decimal import Decimal
import logging
import re
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from workout import workout_mention


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entry_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
    entry_revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    entry_kind: Literal["meal", "workout"] = "meal"


app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# Virgule décimale française dans « 12,5 g » ou séparateur entre deux aliments.
FOOD_SEPARATOR = re.compile(r"(\s+et\s+(?=non\b))|\s+et\s+|;|(?<!\d),|,(?!\d)", re.IGNORECASE)
DISPLAY_SUFFIX = re.compile(r"[.!?]\s*affiche\b[^.!?]*[.!?]?\s*$", re.IGNORECASE)
NUMBER = r"[+-]?\d+(?:[.,]\d+)?"
UNIT = r"kg|g|ml|l|portions?|bols?"
AMOUNT = re.compile(rf"^(?:({NUMBER})\s*({UNIT})|un\s+bol)\b", re.IGNORECASE)
NUMBER_WITH_UNIT = rf"{NUMBER}\s*(?:{UNIT})"
QUANTITY_CHOICES = rf"{NUMBER_WITH_UNIT}(?:\s+ou\s+{NUMBER_WITH_UNIT})*"
CORRECTION_HEADER = r"(?:correction(?:\s+du\s+repas)?\s*:\s*)?"
CORRECTION_FOOD = rf"{CORRECTION_HEADER}pour\s+[^,:;]+,\s*"
QUANTITATIVE_CORRECTION = re.compile(
    rf"{CORRECTION_FOOD}{QUANTITY_CHOICES}\s+et\s+non\s+{QUANTITY_CHOICES}", re.IGNORECASE,
)
REPLACED_AMOUNT = re.compile(
    rf"{CORRECTION_FOOD}(?P<amount>{NUMBER_WITH_UNIT})\s+et\s+non\s+{NUMBER_WITH_UNIT}",
    re.IGNORECASE,
)
RETAINED_AMOUNT = re.compile(
    rf"{CORRECTION_HEADER}[^,:;]+?\s+reste\s+à\s+(?P<amount>{NUMBER_WITH_UNIT})",
    re.IGNORECASE,
)
STATES = re.compile(r"\b(cru(?:e)?s?|cuit(?:e)?s?)\b", re.IGNORECASE)


def declared_quantity(fragment, source):
    match = AMOUNT.match(fragment)
    if match:
        number = Decimal(match[1].replace(",", ".")) if match[1] else Decimal(1)
        unit = match[2].lower().removesuffix("s") if match[2] else "portion"
        if unit == "bol":
            unit = "portion"
        if number >= 0:
            value = int(number) if number == number.to_integral_value() else float(number)
            # Seuls les nombres conservés exactement par le sérialiseur JSON sont proposés.
            if Decimal(str(value)) == number:
                return {"value": value, "unit": unit, "source": source}, None
        return None, ("other", "Peux-tu préciser une quantité positive ou nulle et son unité ?")
    if re.match(r"^[+-]?\d", fragment):
        return None, ("unit_absent", "Avec quelle unité la quantité de cet aliment est-elle exprimée ?")
    return None, ("quantity_absent", "Quelle quantité de cet aliment as-tu consommée ?")


def trim_fragment(text):
    return text.strip().rstrip(".!?").strip()


def meal_fragments(text):
    content = DISPLAY_SUFFIX.sub("", text)
    start = 0
    parts = []
    separators = list(FOOD_SEPARATOR.finditer(content))
    correction = False
    for index, separator in enumerate(separators):
        if correction and separator[1]:
            continue
        # Conserver la virgule et « et non » uniquement entre quantités de la même mention.
        if separator[0] == "," and index + 1 < len(separators) and separators[index + 1][1]:
            end = separators[index + 2].start() if index + 2 < len(separators) else len(content)
            if QUANTITATIVE_CORRECTION.fullmatch(trim_fragment(content[start:end])):
                correction = True
                continue
        correction = False
        parts.append(content[start:separator.start()])
        start = separator.end()
    parts.append(content[start:])
    fragments = [trim_fragment(part) for part in parts]
    return [fragment for fragment in fragments if fragment] or [text]


def meal_proposal(meal):
    mentions = []
    clarifications = []
    for index, fragment in enumerate(meal_fragments(meal.text), 1):
        mention_id = f"m{index}"
        source = {
            "kind": "user_declaration",
            "input_id": meal.entry_id,
            "input_revision": meal.entry_revision,
            "text": fragment,
        }
        explicit = REPLACED_AMOUNT.fullmatch(fragment) or RETAINED_AMOUNT.fullmatch(fragment)
        quantity, problem = declared_quantity(explicit["amount"] if explicit else fragment, source)
        states = {"raw" if word.lower().startswith("cru") else "cooked" for word in STATES.findall(fragment)}
        mentions.append({
            "mention_id": mention_id,
            "text": fragment,
            "source": source,
            "quantity": quantity,
            "food_state": next(iter(states)) if len(states) == 1 else "unknown",
            "catalog_candidates": [],
        })
        if problem:
            reason, question = problem
            clarifications.append({"mention_id": mention_id, "field": "quantity", "reason": reason, "question": question})
    return mentions, clarifications


@app.post("/internal/proposals")
def propose(entry: ProposalInput, response: Response, x_correlation_id: Annotated[UUID, Header()]):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    logger.info("proposal correlation=%s", x_correlation_id)
    food_mentions, sport_mentions, clarifications = [], [], []
    if entry.entry_kind == "workout":
        sport_mentions.append(workout_mention(entry.entry_id, entry.entry_revision, entry.text))
    else:
        food_mentions, clarifications = meal_proposal(entry)
    return {
        "schema_version": "0.1.0",
        "kind": "python_proposal",
        "proposal_id": str(uuid5(NAMESPACE_URL, f"urn:llmsport:{entry.entry_kind}:{entry.entry_id}:{entry.entry_revision}")),
        "entry_id": entry.entry_id,
        "entry_revision": entry.entry_revision,
        "entry_kind": entry.entry_kind,
        "food_mentions": food_mentions,
        "sport_mentions": sport_mentions,
        "clarifications": clarifications,
    }

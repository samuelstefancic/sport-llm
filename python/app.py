"""Propositions déterministes pour le journal local."""

from decimal import Decimal
import logging
import re
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import FastAPI, Header, Response
from pydantic import BaseModel, ConfigDict, Field


class MealInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    entry_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
    entry_revision: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=4000, pattern=r"\S")


app = FastAPI()
logger = logging.getLogger("uvicorn.error")

# Virgule décimale française dans « 12,5 g » ou séparateur entre deux aliments.
FOOD_SEPARATOR = re.compile(r"\s+et\s+|;|(?<!\d),|,(?!\d)", re.IGNORECASE)
DISPLAY_SUFFIX = re.compile(r"[.!?]\s*affiche\b[^.!?]*[.!?]?\s*$", re.IGNORECASE)
AMOUNT = re.compile(r"^([+-]?\d+(?:[.,]\d+)?)\s*(kg|g|ml|l|portions?)\b", re.IGNORECASE)
STATES = re.compile(r"\b(cru(?:e)?s?|cuit(?:e)?s?)\b", re.IGNORECASE)


def declared_quantity(fragment, source):
    match = AMOUNT.match(fragment)
    if match:
        number = Decimal(match[1].replace(",", "."))
        unit = match[2].lower().removesuffix("s")
        if number >= 0:
            value = int(number) if number == number.to_integral_value() else float(number)
            # Seuls les nombres conservés exactement par le sérialiseur JSON sont proposés.
            if Decimal(str(value)) == number:
                return {"value": value, "unit": unit, "source": source}, None
        return None, ("other", "Peux-tu préciser une quantité positive ou nulle et son unité ?")
    if re.match(r"^[+-]?\d", fragment):
        return None, ("unit_absent", "Avec quelle unité la quantité de cet aliment est-elle exprimée ?")
    return None, ("quantity_absent", "Quelle quantité de cet aliment as-tu consommée ?")


def meal_proposal(meal):
    content = DISPLAY_SUFFIX.sub("", meal.text)
    parts = [part.strip().rstrip(".!?").strip() for part in FOOD_SEPARATOR.split(content)]
    fragments = [part for part in parts if part] or [meal.text]
    mentions = []
    clarifications = []
    for index, fragment in enumerate(fragments, 1):
        mention_id = f"m{index}"
        source = {
            "kind": "user_declaration",
            "input_id": meal.entry_id,
            "input_revision": meal.entry_revision,
            "text": fragment,
        }
        quantity, problem = declared_quantity(fragment, source)
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
def propose(meal: MealInput, response: Response, x_correlation_id: Annotated[UUID, Header()]):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    logger.info("proposal correlation=%s", x_correlation_id)
    mentions, clarifications = meal_proposal(meal)
    return {
        "schema_version": "0.1.0",
        "kind": "python_proposal",
        "proposal_id": str(uuid5(NAMESPACE_URL, f"urn:llmsport:meal:{meal.entry_id}:{meal.entry_revision}")),
        "entry_id": meal.entry_id,
        "entry_revision": meal.entry_revision,
        "entry_kind": "meal",
        "food_mentions": mentions,
        "sport_mentions": [],
        "clarifications": clarifications,
    }

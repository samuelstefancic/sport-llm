"""Extraction déterministe minimale pour l'échange local T04."""

import logging
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


@app.post("/internal/proposals")
def propose(meal: MealInput, response: Response, x_correlation_id: Annotated[UUID, Header()]):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    logger.info("proposal correlation=%s", x_correlation_id)
    # T04 transporte une mention. L'identification du produit arrive avec T06.
    return {
        "schema_version": "0.1.0",
        "kind": "python_proposal",
        "proposal_id": str(uuid5(NAMESPACE_URL, f"urn:llmsport:meal:{meal.entry_id}:{meal.entry_revision}")),
        "entry_id": meal.entry_id,
        "entry_revision": meal.entry_revision,
        "entry_kind": "meal",
        "food_mentions": [{
            "mention_id": "m1",
            "text": meal.text,
            "source": {
                "kind": "user_declaration",
                "input_id": meal.entry_id,
                "input_revision": meal.entry_revision,
                "text": meal.text,
            },
            "quantity": None,
            "food_state": "unknown",
            "catalog_candidates": [],
        }],
        "sport_mentions": [],
        "clarifications": [{
            "mention_id": "m1",
            "field": "food",
            "reason": "food_unresolved",
            "question": "De quel aliment s’agit-il ?",
        }],
    }

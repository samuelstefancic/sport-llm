"""Pair FastAPI réservé au scénario de réponse invalide de T09."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, Header, Response


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
logger = logging.getLogger("uvicorn.error")


@app.post("/internal/proposals")
def invalid_proposal(response: Response, x_correlation_id: Annotated[UUID, Header()]):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    logger.info("invalid_reply correlation=%s", x_correlation_id)
    return {"kind": "python_proposal"}  # Incomplet selon le contrat T03.

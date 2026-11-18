"""Pair FastAPI de test. Jamais chargé par le service applicatif."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response, StreamingResponse

examples = Path(__file__).resolve().parents[1] / "contracts" / "examples"
app = FastAPI()


@app.post("/internal/proposals")
async def faulty_reply(meal: dict, x_correlation_id: Annotated[str, Header()]):
    headers = {"X-Correlation-ID": x_correlation_id}
    case = meal["text"]
    if case == "invalid-json":
        return Response(b'{"kind":', media_type="application/json", headers=headers)
    if case == "100 g de riz cuit":
        original = json.loads((examples / "python-meal-nominal.json").read_text())
        mention = original["food_mentions"][0]
        source = {**mention["source"], "input_id": meal["entry_id"], "input_revision": meal["entry_revision"]}
        mention.update(source=source, catalog_candidates=[],
                       quantity={"value": 150, "unit": "g", "source": source})
        original.update(entry_id=meal["entry_id"], entry_revision=meal["entry_revision"], food_mentions=[mention])
        return JSONResponse(original, headers=headers)
    if case == "slow-body":
        async def delayed_body():
            yield b"{"
            await asyncio.sleep(6)
            yield b"}"

        return StreamingResponse(delayed_body(), media_type="application/json", headers=headers)
    files = {
        "java-report": "business-invalid-python-forges-java-report.json",
        "invalid-shape": "invalid-python-claims-validation.json",
        "other-entry": "python-meal-nominal.json",
        "other-revision": "python-meal-nominal.json",
        "other-correlation": "python-meal-nominal.json",
    }
    payload = json.loads((examples / files[case]).read_text())
    if case == "other-entry":
        payload["entry_id"] = "MEAL-002"
    if case == "other-revision":
        payload["entry_revision"] = 1
    if case == "other-correlation":
        headers["X-Correlation-ID"] = "00000000-0000-4000-8000-000000000000"
    return JSONResponse(payload, headers=headers)

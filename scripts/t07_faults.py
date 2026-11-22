"""Propositions sportives de test. Ce module ne fait pas partie du service applicatif."""

import json
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, Response

EXAMPLES = Path(__file__).resolve().parents[1] / "contracts" / "examples"
app = FastAPI()


def proposal(entry):
    payload = json.loads((EXAMPLES / "python-workout-nominal.json").read_text())
    payload.update(entry_id=entry["entry_id"], entry_revision=entry["entry_revision"])
    mention, = payload["sport_mentions"]
    source = {"kind": "user_declaration", "input_id": entry["entry_id"],
              "input_revision": entry["entry_revision"], "text": entry["text"]}
    mention.update(source=source, text=entry["text"])
    if entry["entry_id"] == "T07-FORGED-GOAL":
        mention.update(activity="cycling", measures=[
            {"id": "distance", "unit": "km", "value": value, "source": {**source, "text": fragment}}
            for value, fragment in ((10, "10 km"), (4.5, "4,5 km"))
        ])
        return payload
    distance, duration = mention["measures"]
    distance["source"] = {**source, "text": "5 km"}
    duration["source"] = {**source, "text": "30 min"}
    match entry["entry_id"]:
        case "T07-WRONG-DIMENSION":
            distance["unit"] = "kg"
        case "T07-FORGED-VALUE":
            distance["value"] = 6
        case "T07-FORGED-UNIT":
            distance["unit"] = "m"
        case "T07-OMITTED":
            mention["measures"].remove(duration)
        case "T07-WRONG-SOURCE":
            distance["source"]["input_revision"] += 1
    return payload


@app.post("/internal/proposals")
def faulty_reply(entry: dict, response: Response, x_correlation_id: Annotated[str, Header()]):
    response.headers["X-Correlation-ID"] = x_correlation_id
    return proposal(entry)

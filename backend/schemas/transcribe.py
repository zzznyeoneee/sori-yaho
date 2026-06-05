from pydantic import BaseModel
from typing import Literal


class TranscribeRequest(BaseModel):
    task_id: str
    instrument: Literal["drums", "guitar"]


class TranscribeResponse(BaseModel):
    success: bool
    error: str | None = None
    task_id: str
    status: str
    midi_url: str | None = None
    musicxml_url: str | None = None

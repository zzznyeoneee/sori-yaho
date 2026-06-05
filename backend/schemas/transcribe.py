from pydantic import BaseModel
from typing import Literal


class TranscribeResponse(BaseModel):
    success: bool
    error: str | None = None
    task_id: str
    instrument: str
    midi_url: str | None = None
    musicxml_url: str | None = None

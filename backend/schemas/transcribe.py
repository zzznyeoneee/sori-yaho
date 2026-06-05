<<<<<<< HEAD
﻿from pydantic import BaseModel
=======
from pydantic import BaseModel
>>>>>>> 7c418751c71fd61627f81bd3fe4fb9a2a46d8869
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

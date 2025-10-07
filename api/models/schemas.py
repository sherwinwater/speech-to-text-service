
from pydantic import BaseModel, HttpUrl
from typing import List, Optional

class Segment(BaseModel):
    start: float
    end: float
    text: str

class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration_sec: Optional[float] = None
    segments: List[Segment] = []
    model: str

class UrlRequest(BaseModel):
    url: HttpUrl
    language: Optional[str] = None
    model_size: Optional[str] = None
    word_timestamps: Optional[bool] = None

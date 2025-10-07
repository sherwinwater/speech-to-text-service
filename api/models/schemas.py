
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field, ConfigDict

class Segment(BaseModel):
    start: float
    end: float
    text: str

class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration_sec: Optional[float] = None
    segments: List[Segment] = Field(default_factory=list)
    model: str

class UrlRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    url: HttpUrl
    language: Optional[str] = None
    model_size: Optional[str] = None
    word_timestamps: Optional[bool] = None

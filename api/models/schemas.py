
from typing import List, Optional

try:
    from pydantic import BaseModel, HttpUrl, Field, ConfigDict  # Pydantic v2
except ImportError:
    from pydantic import BaseModel, HttpUrl, Field  # type: ignore
    ConfigDict = None  # type: ignore

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
    if ConfigDict:
        model_config = ConfigDict(protected_namespaces=())
    else:
        class Config:  # type: ignore[no-redef]
            pass
    
    url: HttpUrl
    language: Optional[str] = None
    model_size: Optional[str] = None
    word_timestamps: Optional[bool] = None

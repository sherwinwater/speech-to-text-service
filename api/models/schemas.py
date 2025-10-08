from typing import List, Optional

try:
    # Pydantic v2
    from pydantic import BaseModel, Field, HttpUrl, ConfigDict
    HAS_V2 = True
except ImportError:
    # Pydantic v1 fallback
    from pydantic import BaseModel, Field, HttpUrl  # type: ignore
    HAS_V2 = False


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
    if HAS_V2:
        model_config = ConfigDict(protected_namespaces=())
    else:
        class Config:
            # for Pydantic v1
            arbitrary_types_allowed = True
            extra = "ignore"

    url: HttpUrl
    language: Optional[str] = None
    model_size: Optional[str] = None
    word_timestamps: Optional[bool] = None
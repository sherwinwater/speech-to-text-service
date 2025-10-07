
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_size: str = os.getenv("MODEL_SIZE", "small")
    compute_type: str = os.getenv("COMPUTE_TYPE", "int8")
    max_file_mb: int = int(os.getenv("MAX_FILE_MB", "30"))
    max_duration_sec: int = int(os.getenv("MAX_DURATION_SEC", "600"))
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

settings = Settings()

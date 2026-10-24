"""
WindWise Backend — Application Configuration
Reads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    # Elexon BMRS
    elexon_base_url: str = Field(
        default="https://data.elexon.co.uk/bmrs/api/v1",
        description="Elexon BMRS API base URL",
    )

    # Forecast cutoff (EPEX SPOT GB day-ahead gate closure = 09:20 UTC on D-1)
    forecast_cutoff_hour: int = Field(default=9, ge=0, le=23)
    forecast_cutoff_minute: int = Field(default=20, ge=0, le=59)

    # HTTP behaviour
    api_timeout: int = Field(default=60)

    # Cache
    cache_ttl: int = Field(default=3600)

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    # Environment
    environment: str = Field(default="development")

    model_config = {"env_file": ".env", "case_sensitive": False}

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

# EcomProfit Guard — config
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "EcomProfit Guard"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./ecomprofit.db"
    secret_key: str = "change-in-production-secret-key"
    google_client_id: str = ""
    google_client_secret: str = ""
    redirect_uri: str = "http://localhost:5173/auth/callback"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    default_profitability_threshold_pct: float = 15.0
    forecast_min_months_history: int = 6

    # Статический проект: одна таблица Google Sheets на пользователя, без смены URL в UI
    static_project_enabled: bool = True
    static_spreadsheet_id: str = "1ka36o4ggW0i0ALRhSER6qf_pbGxg2pC6zSSGaF9EE3o"
    static_sheet_acts: str = "Акты"
    static_sheet_costs: str = "Затраты"
    static_sheet_specialists: str = "TL / Специалисты"
    static_sheet_metrics: str = "Метрики"
    static_project_name: str = "Проект"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()

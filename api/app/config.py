from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database — SQLite in dev, postgres:// in prod
    DATABASE_URL: str = "sqlite:///../data/tm_data_v2.db"

    # Assets — cartella locale in dev, URL Supabase Storage in prod
    ASSETS_LOCAL_DIR: str = "../data/assets"
    ASSETS_BASE_URL: str = "http://localhost:8000"

    # Supabase (usato solo in produzione)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""

    # App
    APP_ENV: str = "development"  # "production"
    DEBUG: bool = True

    @property
    def CORS_ORIGINS(self) -> list[str]:
        """Origini CORS: sempre localhost in dev + il dominio frontend in prod."""
        origins = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:4173",
        ]
        if self.FRONTEND_URL and self.FRONTEND_URL not in origins:
            origins.append(self.FRONTEND_URL)
        return origins

    # Admin
    ADMIN_SECRET: str = ""  # Obbligatorio in produzione per endpoint admin

    # Frontend URL — usato per costruire share_url nelle sfide
    FRONTEND_URL: str = "http://localhost:5173"

    # Chiave per firmare i valori degli indizi sensibili (foto)
    # Generare con: python -c "import secrets; print(secrets.token_hex(32))"
    HINT_SIGN_KEY: str = "dev-insecure-key-change-in-production"

    # Fuzzy search
    FUZZY_SCORE_THRESHOLD: int = 55

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database/Auth
    MONGO_URI: str
    DB_NAME: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CRON_SECRET: str = ""
    # Brevo Email (API-based)
    BREVO_API_KEY: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "Autograde Toshan"
    APP_NAME: str = "AutoGrade"
    FRONTEND_URL: str = "https://autograde.toshankanwar.in"
    RESET_TOKEN_EXPIRE_MINUTES: int = 15
    # Optional SMTP fallback (keep if needed)
    SMTP_HOST: str = "smtp-relay.brevo.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # prevents crash if extra env vars exist
    )


settings = Settings()
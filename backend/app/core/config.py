from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./railway_assistant.db"
    jwt_secret: str = "CHANGE-ME-IN-LOCAL-DEV"
    access_token_minutes: int = 30
    frontend_origin: str = "http://localhost:3000"
    railkit_api_key: str = ""
    railkit_base_url: str = "https://api.railkit.in"
    railway_api_timeout_seconds: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

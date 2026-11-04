from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./railway_assistant.db"
    jwt_secret: str = "CHANGE-ME-IN-LOCAL-DEV"
    access_token_minutes: int = 30
    frontend_origin: str = "http://localhost:3000"
    railkit_api_key: str = ""
    railkit_base_url: str = "https://api.railkit.in"
    railway_api_timeout_seconds: int = 20
    # RailKit allows 600 requests per 600 s (token bucket, per ratelimit-policy
    # header). Stay a little under it so interactive searches still work while a
    # background route search runs.
    railkit_window_requests: int = 540
    railkit_window_seconds: int = 600
    # Monthly plan allowance and a reserve that background route searches will
    # not touch, so the app keeps working for the rest of the month.
    railkit_monthly_quota: int = 10000
    railkit_monthly_reserve: int = 300

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    bot_token: str
    database_url: str = "sqlite+aiosqlite:///./school_bot.db"
    schedule_url: str = "https://xn--64-vlclonee7j.xn--p1ai/timetable/m.schedule.html"
    schedule_domain: str = "https://xn--64-vlclonee7j.xn--p1ai/timetable/"
    check_interval_minutes: int = 3
    morning_notification_hour: int = 7
    morning_notification_minute: int = 0


settings = Settings()

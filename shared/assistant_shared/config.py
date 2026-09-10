"""Single place where env vars become typed settings.

Nothing else in the codebase reads os.environ, so the services run
unchanged on Fly/Railway today and on ECS/Lambda later.
"""
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


def _req(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required env var: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    redis_url: str
    database_url: str
    queue_name: str

    meta_app_secret: str
    meta_verify_token: str
    whatsapp_token: str
    whatsapp_phone_number_id: str
    graph_api_version: str

    anthropic_api_key: str
    llm_model: str

    google_credentials_file: str
    calendar_id: str

    timezone: str
    office_open: str              # "09:00"
    office_close: str             # "19:00"
    office_days: tuple[int, ...]  # 0 = Monday
    slot_minutes: int
    owner_whatsapp: str           # where handoff notifications go
    reminder_template: str        # approved WhatsApp template name

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings() -> Settings:
    return Settings(
        redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        database_url=os.environ.get("DATABASE_URL", ""),
        queue_name=os.environ.get("QUEUE_NAME", "inbound"),
        meta_app_secret=_req("META_APP_SECRET"),
        meta_verify_token=_req("META_VERIFY_TOKEN"),
        whatsapp_token=_req("WHATSAPP_TOKEN"),
        whatsapp_phone_number_id=_req("WHATSAPP_PHONE_NUMBER_ID"),
        graph_api_version=os.environ.get("GRAPH_API_VERSION", "v21.0"),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        llm_model=os.environ.get("LLM_MODEL", "claude-sonnet-5"),
        google_credentials_file=os.environ.get(
            "GOOGLE_CREDENTIALS_FILE", "/secrets/google-sa.json"
        ),
        calendar_id=os.environ.get("CALENDAR_ID", "primary"),
        timezone=os.environ.get("TIMEZONE", "Europe/Madrid"),
        office_open=os.environ.get("OFFICE_OPEN", "09:00"),
        office_close=os.environ.get("OFFICE_CLOSE", "19:00"),
        office_days=tuple(
            int(d) for d in os.environ.get("OFFICE_DAYS", "0,1,2,3,4").split(",")
        ),
        slot_minutes=int(os.environ.get("SLOT_MINUTES", "60")),
        owner_whatsapp=os.environ.get("OWNER_WHATSAPP", ""),
        reminder_template=os.environ.get("REMINDER_TEMPLATE", "appointment_reminder"),
    )

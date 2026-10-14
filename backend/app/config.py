from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    PROJECT_NAME: str = "CarePill — Smart Pill Dispenser"
    VERSION: str = "1.1.0"
    API_PREFIX: str = "/api"
    DATABASE_URL: str = "sqlite:///./pillbox.db"
    CORS_ORIGINS: List[str] = ["*"]

    # Supported Hardware Cartridge Configurations
    DEFAULT_CARTRIDGE_COUNT: int = 4
    SUPPORTED_CARTRIDGE_COUNTS: List[int] = [4, 6, 8]

    # Dispenser Safety Limits
    MAX_CORRECTION_ATTEMPTS: int = 3
    DEFAULT_PRE_DOSE_10M_MINUTES: int = 10
    DEFAULT_PRE_DOSE_5M_MINUTES: int = 5
    DEFAULT_REMINDER_MINUTES: int = 5
    DEFAULT_ESCALATION_MINUTES: int = 10

    # Notification Provider & Gateways
    # Supported modes: "simulated", "twilio", "webhook"
    NOTIFICATION_PROVIDER: str = "simulated"

    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""  # e.g. "+15551234567"

    # Twilio WhatsApp
    TWILIO_WHATSAPP_FROM: str = ""  # e.g. "whatsapp:+14155238886"
    TWILIO_WHATSAPP_TEMPLATE_SID: str = ""  # Optional Twilio Content SID (HX...)

    # Webhook Provider
    WEBHOOK_URL: str = ""

    # Device Heartbeat & Dispense Timeout (seconds)
    DEVICE_OFFLINE_THRESHOLD_SECONDS: int = 60
    TELEMETRY_STALE_THRESHOLD_SECONDS: int = 300
    DISPENSE_TIMEOUT_SECONDS: int = 30
    DEFAULT_OPERATING_MODE: str = "simulated"

    # AI Prescription Extraction
    AI_EXTRACTION_PROVIDER: str = "local_rule_engine"  # "local_rule_engine", "gemini", "openai"
    AI_API_KEY: str = ""

settings = Settings()

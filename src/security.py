import logging
import re
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from src.errors import AuthenticationError

KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]+")


def redact(value: str) -> str:
    return KEY_PATTERN.sub("[REDACTED]", value)


class SecretFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        # Do not propagate raw provider tracebacks (can include request information).
        if record.exc_info:
            record.exc_info = None
            record.exc_text = None
        return True


def configure_logging():
    for name in ("openai", "anthropic", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logger = logging.getLogger("gateway")
    if not any(isinstance(f, SecretFilter) for f in logger.filters):
        logger.addFilter(SecretFilter())
    return logger


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    openai_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    anthropic_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)

    def key_issue(self, provider: str) -> str | None:
        secret = self.openai_api_key if provider == "openai" else self.anthropic_api_key
        value = secret.get_secret_value().strip() if secret else ""
        if not value:
            return "Key not found or empty"
        upper = value.upper()
        if "YOUR_" in upper or "PASTE_" in upper or "REPLACE" in upper:
            return "Placeholder text found; replace it with the secret code"
        if "API_KEY=" in upper or "API_KEY =" in upper:
            return "Value includes a variable assignment; use only the secret code"
        if any(char in value for char in ('\"', "'", "`", "“", "”")):
            return "Extra quotation marks inside the value"
        if "..." in value or "…" in value or "*" in value:
            return "Masked or shortened key found; use the complete secret code"
        if any(char.isspace() or not char.isprintable() for char in value):
            return "Whitespace or a line break inside the key"
        if provider == "openai" and value.startswith("sk-ant-"):
            return "Anthropic key entered in the OpenAI setting"
        prefix = "sk-ant-" if provider == "anthropic" else "sk-"
        if not value.startswith(prefix):
            return "Unexpected key prefix for this provider"
        if len(value) < 23:
            return "Key is too short; use the complete secret code"
        return None

    def key_for(self, provider: str) -> str:
        if self.key_issue(provider) is not None:
            raise AuthenticationError(provider)
        secret = self.openai_api_key if provider == "openai" else self.anthropic_api_key
        return secret.get_secret_value().strip()

    def configured(self, provider: str) -> bool:
        return self.key_issue(provider) is None

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

    def key_for(self, provider: str) -> str:
        secret = self.openai_api_key if provider == "openai" else self.anthropic_api_key
        value = secret.get_secret_value().strip() if secret else ""
        prefix = "sk-ant-" if provider == "anthropic" else "sk-"
        if not value.startswith(prefix) or not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", value):
            raise AuthenticationError(provider)
        return value

    def configured(self, provider: str) -> bool:
        try:
            self.key_for(provider)
            return True
        except AuthenticationError:
            return False

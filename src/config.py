"""Resolve credentials without ever exposing their values in diagnostics."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from pydantic import SecretStr


@dataclass(frozen=True)
class Credential:
    value: SecretStr | None = field(default=None, repr=False)
    source: str = "not found"
    issue: str | None = None


def resolve_credential(name: str, secrets: Mapping, environment: Mapping) -> Credential:
    """Explicit Streamlit values win, including blank values (no stale fallback).

    Accept root-level TOML and the common [secrets]/[api_keys] grouping tables.
    No value is interpolated into a public diagnostic or exception message.
    """
    value = None
    source = "not found"
    if name in secrets:
        value, source = secrets[name], "Streamlit Secrets"
    else:
        for group in ("secrets", "api_keys"):
            table = secrets.get(group)
            if isinstance(table, Mapping) and name in table:
                value, source = table[name], f"Streamlit Secrets [{group}]"
                break
        else:
            if name in environment:
                value, source = environment[name], "server environment / .env"
    if value is None or value == "":
        return Credential(source=source, issue="Key not found or empty")
    if not isinstance(value, str):
        return Credential(source=source, issue="Key must be TOML text in straight quotation marks")
    return Credential(value=SecretStr(value), source=source)

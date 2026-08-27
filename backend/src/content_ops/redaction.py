from __future__ import annotations

import re

REDACTED = "[redacted]"

_ERROR_SECRET_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        (?P<key>
            x(?:[-_ ]?api[-_ ]?key)
            | api[-_ ]?key
            | access[-_ ]?token
            | app[-_ ]?secret
            | client[-_ ]?secret
            | secret[-_ ]?key
            | password
            | secret
        )
        [\"']?\s*(?:=|:)\s*
    )
    (?P<value>\[redacted\]|\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;)&}\]]+)
    """
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SENSITIVE_PAYLOAD_KEY_RE = re.compile(
    r"(?i)(?:api[-_ ]?key|access[-_ ]?token|app[-_ ]?secret|client[-_ ]?secret|secret|password|authorization)"
)


def redact_error(
    value: object,
    *,
    secret_values: tuple[str, ...] = (),
    max_length: int | None = None,
) -> str:
    """Keep an operator-facing error useful without exposing credentials."""
    error = str(value)
    for secret in secret_values:
        if secret:
            error = error.replace(secret, REDACTED)
    error = _ERROR_SECRET_VALUE_RE.sub(lambda match: f"{match.group('prefix')}{REDACTED}", error)
    error = _BEARER_TOKEN_RE.sub(f"Bearer {REDACTED}", error)
    return error[:max_length] if max_length is not None else error


def redact_event_payload(value: object) -> object:
    """Redact nested event payloads, including historical records at read time."""
    if isinstance(value, dict):
        return {
            str(key): REDACTED if _SENSITIVE_PAYLOAD_KEY_RE.search(str(key)) else redact_event_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_event_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_event_payload(item) for item in value]
    if isinstance(value, str):
        return redact_error(value)
    return value

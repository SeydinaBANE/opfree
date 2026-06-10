from __future__ import annotations

import re

import structlog

log = structlog.get_logger()

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[A-Z0-9]{16}")),
    ("sk_key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("connection_string", re.compile(r"(?:postgresql|mysql|mongodb|redis)://\S+")),
    ("auth_header", re.compile(r"(?:Authorization|Bearer)\s*:?\s*\S+", re.IGNORECASE)),
    ("password_value", re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE)),
]

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+(?:previous|above|all)\s+instructions?", re.IGNORECASE),
    ),
    (
        "you_are_now",
        re.compile(r"you\s+are\s+now\s+(?:a|an)\s+\w+", re.IGNORECASE),
    ),
    (
        "disregard",
        re.compile(r"disregard\s+(?:the\s+)?(?:previous|above|all)", re.IGNORECASE),
    ),
    (
        "role_tag",
        re.compile(r"</?(?:system|user|assistant)>", re.IGNORECASE),
    ),
    (
        "system_directive",
        re.compile(r"\bsystem\s*:\s*you\s+(?:must|should|are)\b", re.IGNORECASE),
    ),
]

_SYNTHESIS_REQUIRED = ("ROOT CAUSE:", "EVIDENCE:", "REMEDIATION:", "CONFIDENCE:")


def sanitize_text(text: str) -> tuple[str, list[str]]:
    hits: list[str] = []
    result = text

    for label, pattern in _SECRET_PATTERNS:
        if pattern.search(result):
            hits.append(f"secret:{label}")
            result = pattern.sub("[REDACTED]", result)

    for label, pattern in _INJECTION_PATTERNS:
        if pattern.search(result):
            hits.append(f"injection:{label}")
            result = pattern.sub("[NEUTRALIZED]", result)

    if hits:
        log.warning("sanitizer_hits", count=len(hits), hits=hits)

    return result, hits


def validate_synthesis(text: str) -> list[str]:
    return [field for field in _SYNTHESIS_REQUIRED if field not in text]

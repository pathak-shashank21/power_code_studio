from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_LANGUAGE_ORDER,
    DEFAULT_PROFILE_ORDER,
    SUPPORTED_LANGUAGES,
    SUPPORTED_PROFILES,
)


EXTENSION_TO_LANGUAGE = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".java": "java",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".php": "php",
    ".rb": "ruby",
    ".sql": "sql",
    ".vue": "typescript",
}

EXTENSION_TO_PROFILE = {
    ".tsx": "reactjs",
    ".jsx": "reactjs",
    ".vue": "vuejs",
    ".sql": "sql",
}


LANGUAGE_ALIASES = {
    "ts": "typescript",
    "py": "python",
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "c#": "csharp",
    "cs": "csharp",
    "c++": "cpp",
    "golang": "go",
    "postgres": "sql",
    "postgresql": "sql",
    "mysql": "sql",
    "sqlserver": "sql",
    "mssql": "sql",
}

PROFILE_ALIASES = {
    "node": "nodejs",
    "node.js": "nodejs",
    "node js": "nodejs",
    "express": "expressjs",
    "express js": "expressjs",
    "node express": "expressjs",
    "node express js": "expressjs",
    "nest": "nestjs",
    "nest js": "nestjs",
    "next": "nextjs",
    "next js": "nextjs",
    "react": "reactjs",
    "react js": "reactjs",
    "view js": "vuejs",
    "vue": "vuejs",
    "vue js": "vuejs",
    "laravel php": "laravel",
    "php laravel": "laravel",
    "php yii2": "yii2",
    "yii": "yii2",
    ".net": "dotnet-csharp",
    ".net c#": "dotnet-csharp",
    ".net c sharp": "dotnet-csharp",
    "asp.net": "dotnet-csharp",
    "asp.net core": "dotnet-csharp",
    "c# .net": "dotnet-csharp",
    "java": "java",
    "sql": "sql",
}


def normalize_language(value: str) -> str:
    raw = (value or "").strip().lower()
    normalized = LANGUAGE_ALIASES.get(raw, raw)
    if normalized not in SUPPORTED_LANGUAGES:
        allowed = ", ".join(DEFAULT_LANGUAGE_ORDER)
        raise ValueError(f"Unsupported language '{value}'. Supported languages: {allowed}")
    return normalized


def normalize_profile(value: str | None) -> str | None:
    if value is None:
        return None
    raw = value.strip().lower()
    if not raw:
        return None
    normalized = PROFILE_ALIASES.get(raw, raw)
    if normalized not in SUPPORTED_PROFILES:
        allowed = ", ".join(DEFAULT_PROFILE_ORDER)
        raise ValueError(f"Unsupported profile '{value}'. Supported profiles: {allowed}")
    return normalized


def profile_to_language(profile: str | None) -> str | None:
    normalized = normalize_profile(profile)
    if normalized is None:
        return None
    return SUPPORTED_PROFILES[normalized].base_language


def ensure_profile(profile: str | None, fallback_language: str) -> str:
    normalized = normalize_profile(profile)
    if normalized is not None:
        return normalized
    language = normalize_language(fallback_language)
    if language in SUPPORTED_PROFILES:
        return language
    # should not happen with current defaults but keep safe
    for key, spec in SUPPORTED_PROFILES.items():
        if spec.base_language == language:
            return key
    raise ValueError(f"No default profile found for language '{fallback_language}'.")


def pretty_language(value: str) -> str:
    return SUPPORTED_LANGUAGES[normalize_language(value)].label


def pretty_profile(value: str) -> str:
    return SUPPORTED_PROFILES[ensure_profile(value, "python")].label


def safe_json_loads(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
        raise ValueError("Expected a JSON object.")
    except Exception as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc


def strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_+-]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def detect_language_from_filename(filename: str) -> str | None:
    suffix = Path(filename).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(suffix)


def detect_profile_from_filename(filename: str) -> str | None:
    path = Path(filename)
    suffix = path.suffix.lower()
    if suffix in EXTENSION_TO_PROFILE:
        return EXTENSION_TO_PROFILE[suffix]
    lowered = filename.lower()
    if "next" in lowered:
        return "nextjs"
    if "nest" in lowered:
        return "nestjs"
    if "express" in lowered or "server" in lowered:
        return "expressjs"
    if "controller" in lowered and suffix == ".php":
        return "laravel"
    return None


def editor_mode_for_profile(profile: str | None, fallback_language: str) -> str:
    key = ensure_profile(profile, fallback_language)
    spec = SUPPORTED_PROFILES[key]
    if spec.editor_mode:
        return spec.editor_mode
    return SUPPORTED_LANGUAGES[spec.base_language].editor_mode


def humanize_elapsed_ms(elapsed_ms: int) -> tuple[float, float, str]:
    seconds = round(elapsed_ms / 1000.0, 2)
    minutes = round(elapsed_ms / 60000.0, 2)
    if minutes >= 1:
        label = f"{minutes} min ({seconds} sec)"
    else:
        label = f"{seconds} sec"
    return seconds, minutes, label

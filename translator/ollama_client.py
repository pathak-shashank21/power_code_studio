from __future__ import annotations

from typing import Any, TypeVar

import requests
from pydantic import BaseModel

from .utils import safe_json_loads

T = TypeVar("T", bound=BaseModel)


class OllamaClientError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, *, base_url: str, timeout_seconds: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def list_models(self) -> list[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=15)
            response.raise_for_status()
            payload = response.json()
            models = payload.get("models", [])
            return sorted(
                [
                    item.get("name", "")
                    for item in models
                    if isinstance(item, dict) and item.get("name")
                ]
            )
        except Exception as exc:
            raise OllamaClientError(
                f"Could not reach Ollama at {self.base_url}. Make sure Ollama is running locally."
            ) from exc

    def request_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        response_model: type[T],
    ) -> T:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": response_model.model_json_schema(),
            "options": {
                "temperature": temperature,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            raw = response.json()
            content = raw.get("message", {}).get("content", "")
            parsed = safe_json_loads(content)
            return response_model.model_validate(parsed)
        except requests.Timeout as exc:
            raise OllamaClientError(
                "Ollama timed out while processing the request. Try a smaller model or a smaller input."
            ) from exc
        except Exception as exc:
            if isinstance(exc, OllamaClientError):
                raise
            raise OllamaClientError(
                "Ollama did not return a valid structured response. Check that the selected model supports standard chat generation well."
            ) from exc

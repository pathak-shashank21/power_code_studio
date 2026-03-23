from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


TASK_TO_ROLE = {
    "translate": "translation",
    "fix": "fix",
    "review": "review",
    "assistant": "assistant",
    "assistant_generate": "assistant",
    "assistant_refactor": "assistant",
    "assistant_debug": "assistant",
    "assistant_explain": "assistant",
    "assistant_review": "review",
    "assistant_test": "assistant",
    "assistant_fix": "fix",
    "codegen": "codegen",
    "project": "project",
}


@dataclass(frozen=True)
class RoutingDecision:
    role: str
    requested_task: str
    selected_model: str
    strategy: str
    reason: str


class ModelRouter:
    def __init__(
        self,
        *,
        default_model: str,
        translation_model: str | None = None,
        fix_model: str | None = None,
        review_model: str | None = None,
        assistant_model: str | None = None,
        codegen_model: str | None = None,
        project_model: str | None = None,
    ) -> None:
        self.default_model = default_model
        self.role_models = {
            "translation": translation_model or default_model,
            "fix": fix_model or translation_model or default_model,
            "review": review_model or default_model,
            "assistant": assistant_model or default_model,
            "codegen": codegen_model or assistant_model or default_model,
            "project": project_model or assistant_model or default_model,
        }

    def available_role_models(self) -> dict[str, str]:
        return dict(self.role_models)

    def choose(
        self,
        *,
        task: str,
        requested_model: str | None,
        available_models: Iterable[str] | None = None,
        strategy: str = "auto",
    ) -> RoutingDecision:
        role = TASK_TO_ROLE.get(task, "assistant")
        available = {item for item in (available_models or []) if item}

        if strategy == "manual" and requested_model:
            chosen = requested_model
            reason = "Manual model selection was requested by the user."
        elif requested_model:
            chosen = requested_model
            reason = "A task-specific model override was supplied explicitly."
        else:
            chosen = self.role_models.get(role, self.default_model)
            reason = f"Auto routing selected the configured {role} model."

        if available and chosen not in available:
            fallback = self.default_model if self.default_model in available else sorted(available)[0]
            reason += f" Requested model '{chosen}' was unavailable, so '{fallback}' was used instead."
            chosen = fallback

        return RoutingDecision(
            role=role,
            requested_task=task,
            selected_model=chosen,
            strategy=strategy,
            reason=reason,
        )

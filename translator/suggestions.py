from __future__ import annotations

from .constants import SUPPORTED_PROFILES
from .schemas import (
    CompileCheckResult,
    DependencyMap,
    ExecutionResult,
    ProjectAnalysisResponse,
    ProjectBlueprint,
    PromptSuggestionResponse,
    SemanticReview,
    SuggestionItem,
)


def build_suggestions(
    *,
    source_check: CompileCheckResult | None,
    target_check: CompileCheckResult | None,
    execution_result: ExecutionResult | None,
    dependency_map: DependencyMap | None,
    warnings: list[str],
    semantic_review: SemanticReview | None,
    fixed_rounds: int,
    source_profile: str,
    target_profile: str,
) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []

    if target_check and target_check.available and target_check.passed is False:
        suggestions.append(
            SuggestionItem(
                severity="critical",
                category="validation",
                title="Fix target compile or syntax errors",
                detail=target_check.stderr or target_check.detail,
            )
        )
    elif target_check and target_check.available and target_check.passed is True:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="validation",
                title="Target code passed the local check",
                detail=target_check.detail,
            )
        )
    elif target_check and not target_check.available:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="validation",
                title="Install a local checker for the target language or framework",
                detail=target_check.detail,
            )
        )

    if source_check and source_check.available and source_check.passed is False:
        suggestions.append(
            SuggestionItem(
                severity="critical",
                category="validation",
                title="Repair the source snippet first",
                detail="The source code does not pass a local parse or compile check, which can lead to poor translations.",
            )
        )

    if dependency_map:
        if dependency_map.detected_frameworks:
            suggestions.append(
                SuggestionItem(
                    severity="warning",
                    category="framework",
                    title="Review framework-specific behavior",
                    detail=f"Framework hints were detected: {', '.join(dependency_map.detected_frameworks)}. Confirm lifecycle, routing, state, ORM, and environment mappings in the target profile.",
                )
            )
        if dependency_map.source_imports and not dependency_map.target_imports:
            suggestions.append(
                SuggestionItem(
                    severity="warning",
                    category="dependency",
                    title="Map dependencies explicitly",
                    detail="The source imports dependencies but the target output has no obvious imports. Add or verify target-library equivalents.",
                )
            )

    if source_profile != target_profile:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="profile",
                title="Profile conversion is active",
                detail=f"The translation mapped {SUPPORTED_PROFILES[source_profile].label} into {SUPPORTED_PROFILES[target_profile].label}. Review framework or runtime assumptions carefully.",
            )
        )

    for warning in warnings[:5]:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="translation",
                title="Review model warning",
                detail=warning,
            )
        )

    if semantic_review:
        for item in semantic_review.recommended_fixes[:3]:
            suggestions.append(
                SuggestionItem(
                    severity="info",
                    category="review",
                    title="Semantic review follow-up",
                    detail=item,
                )
            )
        for risk in semantic_review.fidelity_risks[:3]:
            suggestions.append(
                SuggestionItem(
                    severity="warning",
                    category="review",
                    title="Potential fidelity risk",
                    detail=risk,
                )
            )

    if execution_result and execution_result.attempted:
        if execution_result.available and execution_result.passed is False:
            suggestions.append(
                SuggestionItem(
                    severity="critical",
                    category="runtime",
                    title="Runtime check failed",
                    detail=execution_result.stderr or execution_result.detail,
                )
            )
        elif execution_result.available and execution_result.passed is True:
            suggestions.append(
                SuggestionItem(
                    severity="info",
                    category="runtime",
                    title="Runtime smoke check passed",
                    detail=execution_result.detail,
                )
            )

    if fixed_rounds > 0:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="translation",
                title="Compile-and-fix loop was used",
                detail=f"The translator applied {fixed_rounds} revision round(s) after local validation feedback.",
            )
        )

    return suggestions



def build_generation_suggestions(
    *,
    target_profile: str,
    blueprint: ProjectBlueprint,
    primary_check: CompileCheckResult | None,
) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []
    profile = SUPPORTED_PROFILES[target_profile]

    suggestions.append(
        SuggestionItem(
            severity="info",
            category="generation",
            title="Generated for target profile",
            detail=f"Output was shaped for {profile.label}. Follow the setup and run commands before deeper testing.",
        )
    )

    if not blueprint.files:
        suggestions.append(
            SuggestionItem(
                severity="critical",
                category="generation",
                title="No files were generated",
                detail="The model returned an empty project blueprint. Retry with a clearer prompt or a stronger model.",
            )
        )

    if len(blueprint.files) >= 8:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="generation",
                title="Review project scope",
                detail="The project contains many files for an MVP. Trim boilerplate if you want faster local iteration.",
            )
        )

    if primary_check is not None:
        if primary_check.available and primary_check.passed is True:
            suggestions.append(
                SuggestionItem(
                    severity="info",
                    category="validation",
                    title="Primary generated file passed local verification",
                    detail=primary_check.detail,
                )
            )
        elif primary_check.available and primary_check.passed is False:
            suggestions.append(
                SuggestionItem(
                    severity="critical",
                    category="validation",
                    title="Primary generated file needs repair",
                    detail=primary_check.stderr or primary_check.detail,
                )
            )
        else:
            suggestions.append(
                SuggestionItem(
                    severity="warning",
                    category="validation",
                    title="Primary generated file could not be verified locally",
                    detail=primary_check.detail,
                )
            )

    for warning in blueprint.warnings[:4]:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="generation",
                title="Project warning",
                detail=warning,
            )
        )

    for note in blueprint.architecture_notes[:3]:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="generation",
                title="Architecture note",
                detail=note,
            )
        )

    return suggestions



def build_prompt_suggestions(result: PromptSuggestionResponse) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []
    for item in result.missing_details[:4]:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="prompt",
                title="Prompt detail to add",
                detail=item,
            )
        )
    for item in result.suggestions[:4]:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="prompt",
                title="Prompt improvement",
                detail=item,
            )
        )
    return suggestions



def build_assistant_suggestions(
    *,
    primary_check: CompileCheckResult | None,
    warnings: list[str],
    next_steps: list[str],
) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []
    if primary_check is not None:
        if primary_check.available and primary_check.passed is True:
            suggestions.append(
                SuggestionItem(
                    severity="info",
                    category="assistant",
                    title="Assistant output passed a local check",
                    detail=primary_check.detail,
                )
            )
        elif primary_check.available and primary_check.passed is False:
            suggestions.append(
                SuggestionItem(
                    severity="critical",
                    category="assistant",
                    title="Assistant output needs fixing",
                    detail=primary_check.stderr or primary_check.detail,
                )
            )
        else:
            suggestions.append(
                SuggestionItem(
                    severity="warning",
                    category="assistant",
                    title="Assistant output could not be validated locally",
                    detail=primary_check.detail,
                )
            )

    for warning in warnings[:4]:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="assistant",
                title="Assistant warning",
                detail=warning,
            )
        )
    for step in next_steps[:4]:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="assistant",
                title="Suggested next step",
                detail=step,
            )
        )
    return suggestions



def build_project_analysis_suggestions(analysis: ProjectAnalysisResponse) -> list[SuggestionItem]:
    suggestions: list[SuggestionItem] = []
    if analysis.frameworks:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="architecture",
                title="Detected framework family",
                detail=", ".join(analysis.frameworks),
            )
        )
    for risk in analysis.risks[:4]:
        suggestions.append(
            SuggestionItem(
                severity="warning",
                category="architecture",
                title="Project risk",
                detail=risk,
            )
        )
    for hint in analysis.setup_hints[:4]:
        suggestions.append(
            SuggestionItem(
                severity="info",
                category="architecture",
                title="Setup hint",
                detail=hint,
            )
        )
    return suggestions

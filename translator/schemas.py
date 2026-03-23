from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .utils import normalize_language, normalize_profile


class CompileCheckResult(BaseModel):
    language: str
    available: bool = False
    passed: bool | None = None
    command: str | None = None
    detail: str
    stdout: str = ""
    stderr: str = ""


class ExecutionResult(BaseModel):
    language: str
    attempted: bool = False
    available: bool = False
    passed: bool | None = None
    command: str | None = None
    detail: str
    stdout: str = ""
    stderr: str = ""


class SuggestionItem(BaseModel):
    severity: Literal["info", "warning", "critical"] = "info"
    category: Literal[
        "translation",
        "validation",
        "dependency",
        "framework",
        "testing",
        "runtime",
        "review",
        "generation",
        "profile",
        "assistant",
        "prompt",
        "architecture",
    ] = "translation"
    title: str
    detail: str


class DependencyMap(BaseModel):
    source_imports: list[str] = Field(default_factory=list)
    target_imports: list[str] = Field(default_factory=list)
    detected_frameworks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SemanticReview(BaseModel):
    summary: str = ""
    fidelity_risks: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    recommended_fixes: list[str] = Field(default_factory=list)


class GeneratedArtifact(BaseModel):
    filename: str
    language: str
    content: str
    purpose: str


class ProjectFile(BaseModel):
    path: str
    language: str
    content: str
    purpose: str


class ProjectBlueprint(BaseModel):
    project_name: str
    summary: str
    files: list[ProjectFile] = Field(default_factory=list)
    setup_commands: list[str] = Field(default_factory=list)
    run_commands: list[str] = Field(default_factory=list)
    architecture_notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TranslationEnvelope(BaseModel):
    translated_code: str
    explanation: str = ""
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class TranslateRequest(BaseModel):
    source_code: str = Field(min_length=1)
    source_language: str
    target_language: str
    source_profile: str | None = None
    target_profile: str | None = None
    provider: Literal["ollama", "heuristic"] = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=3500, ge=256, le=32000)
    validate_source: bool = True
    validate_target: bool = True
    include_diff: bool = True
    include_semantic_review: bool = True
    generate_tests: bool = True
    auto_fix: bool = True
    max_fix_rounds: int = Field(default=2, ge=0, le=5)
    run_translated: bool = False

    @field_validator("source_language", "target_language", mode="before")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return normalize_language(value)

    @field_validator("source_profile", "target_profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: str | None) -> str | None:
        return normalize_profile(value)


class TranslateResponse(BaseModel):
    translated_code: str
    explanation: str
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    provider: str
    model: str
    source_language: str
    target_language: str
    source_profile: str
    target_profile: str
    source_check: CompileCheckResult | None = None
    target_check: CompileCheckResult | None = None
    execution_result: ExecutionResult | None = None
    dependency_map: DependencyMap | None = None
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    semantic_review: SemanticReview | None = None
    generated_artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    diff_text: str = ""
    fixed_rounds: int = 0
    elapsed_ms: int
    elapsed_seconds: float = 0.0
    elapsed_minutes: float = 0.0
    elapsed_human: str = ""


class BatchItem(BaseModel):
    job_name: str
    source_code: str = Field(min_length=1)
    source_language: str
    target_language: str
    source_profile: str | None = None
    target_profile: str | None = None

    @field_validator("source_language", "target_language", mode="before")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return normalize_language(value)

    @field_validator("source_profile", "target_profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: str | None) -> str | None:
        return normalize_profile(value)


class BatchTranslateRequest(BaseModel):
    items: list[BatchItem] = Field(min_length=1, max_length=100)
    provider: Literal["ollama", "heuristic"] = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    validate_source: bool = True
    validate_target: bool = True
    include_diff: bool = True
    include_semantic_review: bool = True
    generate_tests: bool = True
    auto_fix: bool = True
    max_fix_rounds: int = Field(default=2, ge=0, le=5)
    run_translated: bool = False


class BatchTranslateResponse(BaseModel):
    results: list[TranslateResponse]
    total_elapsed_ms: int
    total_elapsed_seconds: float = 0.0
    total_elapsed_minutes: float = 0.0


class ReviewRequest(BaseModel):
    source_code: str = Field(min_length=1)
    source_language: str
    translated_code: str = Field(min_length=1)
    target_language: str
    source_profile: str | None = None
    target_profile: str | None = None
    model: str | None = None

    @field_validator("source_language", "target_language", mode="before")
    @classmethod
    def _normalize_language(cls, value: str) -> str:
        return normalize_language(value)

    @field_validator("source_profile", "target_profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: str | None) -> str | None:
        return normalize_profile(value)


class GenerateProjectRequest(BaseModel):
    prompt: str = Field(min_length=1)
    target_profile: str
    target_language: str | None = None
    provider: Literal["ollama", "heuristic"] = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    include_tests: bool = True
    include_readme: bool = True
    include_docker: bool = False
    max_files: int = Field(default=8, ge=1, le=30)
    auto_verify_primary_file: bool = True

    @field_validator("target_profile", mode="before")
    @classmethod
    def _normalize_target_profile(cls, value: str) -> str:
        normalized = normalize_profile(value)
        if normalized is None:
            raise ValueError("target_profile is required")
        return normalized

    @field_validator("target_language", mode="before")
    @classmethod
    def _normalize_target_language(cls, value: str | None) -> str | None:
        if value in {None, ""}:
            return None
        return normalize_language(value)


class GenerateProjectResponse(BaseModel):
    provider: str
    model: str
    target_profile: str
    target_language: str
    blueprint: ProjectBlueprint
    primary_check: CompileCheckResult | None = None
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    elapsed_ms: int
    elapsed_seconds: float = 0.0
    elapsed_minutes: float = 0.0
    elapsed_human: str = ""


class ChatCodeRequest(BaseModel):
    prompt: str = Field(min_length=1)
    target_profile: str
    provider: Literal["ollama", "heuristic"] = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)

    @field_validator("target_profile", mode="before")
    @classmethod
    def _normalize_target_profile(cls, value: str) -> str:
        normalized = normalize_profile(value)
        if normalized is None:
            raise ValueError("target_profile is required")
        return normalized


class ChatCodeResponse(BaseModel):
    provider: str
    model: str
    target_profile: str
    target_language: str
    translated_code: str
    explanation: str = ""
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    primary_check: CompileCheckResult | None = None
    elapsed_ms: int
    elapsed_seconds: float = 0.0
    elapsed_minutes: float = 0.0
    elapsed_human: str = ""


class PromptSuggestionRequest(BaseModel):
    prompt: str = Field(min_length=1)
    target_profile: str | None = None

    @field_validator("target_profile", mode="before")
    @classmethod
    def _normalize_target_profile(cls, value: str | None) -> str | None:
        return normalize_profile(value)


class PromptSuggestionResponse(BaseModel):
    quality_score: int = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    improved_prompt: str


class AssistantHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AssistantEnvelope(BaseModel):
    title: str
    message: str
    code: str = ""
    filename: str = ""
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class AssistantTurnRequest(BaseModel):
    prompt: str = Field(min_length=1)
    target_profile: str
    task: Literal["generate", "refactor", "debug", "explain", "review", "test", "fix"] = "generate"
    code_context: str = ""
    history: list[AssistantHistoryMessage] = Field(default_factory=list)
    provider: Literal["ollama", "heuristic"] = "ollama"
    model: str | None = None
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)

    @field_validator("target_profile", mode="before")
    @classmethod
    def _normalize_target_profile(cls, value: str) -> str:
        normalized = normalize_profile(value)
        if normalized is None:
            raise ValueError("target_profile is required")
        return normalized


class AssistantTurnResponse(BaseModel):
    provider: str
    model: str
    task: str
    target_profile: str
    target_language: str
    title: str
    message: str
    code: str = ""
    filename: str = ""
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    primary_check: CompileCheckResult | None = None
    suggestions: list[SuggestionItem] = Field(default_factory=list)
    elapsed_ms: int
    elapsed_seconds: float = 0.0
    elapsed_minutes: float = 0.0
    elapsed_human: str = ""


class ProjectAnalysisFile(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""


class ProjectFileInsight(BaseModel):
    path: str
    language: str | None = None
    profile: str | None = None
    frameworks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProjectAnalysisRequest(BaseModel):
    files: list[ProjectAnalysisFile] = Field(min_length=1, max_length=500)


class ProjectAnalysisResponse(BaseModel):
    total_files: int
    language_counts: dict[str, int] = Field(default_factory=dict)
    profile_counts: dict[str, int] = Field(default_factory=dict)
    frameworks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    suggested_profiles: list[str] = Field(default_factory=list)
    setup_hints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    architecture_summary: str = ""
    file_insights: list[ProjectFileInsight] = Field(default_factory=list)

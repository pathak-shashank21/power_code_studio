from __future__ import annotations

import time

from .analysis import (
    analyze_project_files,
    build_dependency_map,
    build_diff_text,
    detect_frameworks,
    extract_dependencies,
)
from .config import Settings, get_settings
from .constants import DEFAULT_PROFILE_ORDER, SUPPORTED_PROFILES
from .executor import run_local_execution
from .heuristics import heuristic_translate
from .model_router import ModelRouter
from .ollama_client import OllamaClient, OllamaClientError
from .prompts import (
    build_assistant_system_prompt,
    build_assistant_user_prompt,
    build_chat_codegen_system_prompt,
    build_chat_codegen_user_prompt,
    build_fix_user_prompt,
    build_project_system_prompt,
    build_project_user_prompt,
    build_review_system_prompt,
    build_review_user_prompt,
    build_test_system_prompt,
    build_test_user_prompt,
    build_translation_system_prompt,
    build_translation_user_prompt,
)
from .schemas import (
    AssistantEnvelope,
    AssistantTurnRequest,
    AssistantTurnResponse,
    BatchTranslateRequest,
    BatchTranslateResponse,
    ChatCodeRequest,
    ChatCodeResponse,
    GenerateProjectRequest,
    GenerateProjectResponse,
    GeneratedArtifact,
    ProjectAnalysisRequest,
    ProjectAnalysisResponse,
    ProjectBlueprint,
    PromptSuggestionRequest,
    PromptSuggestionResponse,
    ReviewRequest,
    SemanticReview,
    TranslateRequest,
    TranslateResponse,
    TranslationEnvelope,
)
from .suggestions import (
    build_assistant_suggestions,
    build_generation_suggestions,
    build_project_analysis_suggestions,
    build_prompt_suggestions,
    build_suggestions,
)
from .utils import ensure_profile, humanize_elapsed_ms, profile_to_language
from .validators import run_local_check


PROMPT_CHECKLIST = [
    ("input and output examples", ["example", "sample", "input", "output"]),
    ("error handling expectations", ["error", "exception", "retry", "fallback"]),
    ("testing expectations", ["test", "pytest", "unit test", "integration test"]),
    ("data storage or database details", ["database", "postgres", "mysql", "sqlite", "mongo", "redis"]),
    ("authentication or authorization details", ["auth", "oauth", "jwt", "login", "permission", "role"]),
    ("framework or runtime version constraints", ["version", "node", "python", "java", ".net", "php"]),
    ("deployment or environment assumptions", ["docker", "deploy", "env", "production", "hosting"]),
]


class TranslationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.ollama_client = OllamaClient(
            base_url=self.settings.ollama_base_url,
            timeout_seconds=self.settings.ollama_timeout_seconds,
        )
        self.model_router = ModelRouter(
            default_model=self.settings.ollama_model,
            translation_model=self.settings.ollama_translation_model,
            fix_model=self.settings.ollama_fix_model,
            review_model=self.settings.ollama_review_model,
            assistant_model=self.settings.ollama_assistant_model,
            codegen_model=self.settings.ollama_codegen_model,
            project_model=self.settings.ollama_project_model,
        )

    def list_models(self) -> list[str]:
        return self.ollama_client.list_models()

    def list_profiles(self) -> list[dict[str, str]]:
        return [
            {
                "key": key,
                "label": spec.label,
                "base_language": spec.base_language,
                "default_filename": spec.default_filename,
                "output_kind": spec.output_kind,
            }
            for key, spec in ((key, SUPPORTED_PROFILES[key]) for key in DEFAULT_PROFILE_ORDER)
        ]


    def get_model_routing(self) -> dict[str, str]:
        return self.model_router.available_role_models()

    def resolve_model(
        self,
        *,
        task: str,
        requested_model: str | None = None,
        strategy: str = "auto",
    ) -> str:
        try:
            available_models = self.list_models()
        except Exception:
            available_models = []
        decision = self.model_router.choose(
            task=task,
            requested_model=requested_model,
            available_models=available_models,
            strategy=strategy,
        )
        return decision.selected_model

    def _translate_with_provider(
        self,
        request: TranslateRequest,
        *,
        source_profile: str,
        target_profile: str,
        source_dependencies: list[str],
        source_frameworks: list[str],
    ) -> tuple[TranslationEnvelope, str]:
        provider = request.provider
        if provider == "heuristic":
            envelope = heuristic_translate(
                request.source_code,
                request.source_language,
                request.target_language,
            )
            return envelope, "heuristic"

        if not self.settings.use_ollama:
            raise OllamaClientError("OLLAMA usage is disabled in settings.")

        model_name = self.resolve_model(task="translate", requested_model=request.model)
        envelope = self.ollama_client.request_json(
            model=model_name,
            system_prompt=build_translation_system_prompt(),
            user_prompt=build_translation_user_prompt(
                source_language=request.source_language,
                target_language=request.target_language,
                source_profile=source_profile,
                target_profile=target_profile,
                source_code=request.source_code,
                detected_dependencies=source_dependencies,
                detected_frameworks=source_frameworks,
            ),
            temperature=request.temperature,
            response_model=TranslationEnvelope,
        )
        return envelope, model_name

    def _compile_fix_loop(
        self,
        request: TranslateRequest,
        *,
        source_profile: str,
        target_profile: str,
        envelope: TranslationEnvelope,
        model_name: str,
        initial_target_check,
    ) -> tuple[TranslationEnvelope, object, int]:
        if request.provider != "ollama" or not request.auto_fix or request.max_fix_rounds <= 0:
            return envelope, initial_target_check, 0
        if not initial_target_check or initial_target_check.passed is not False:
            return envelope, initial_target_check, 0

        current = envelope
        current_check = initial_target_check
        rounds = 0
        fix_model = self.resolve_model(task="fix", requested_model=request.model)
        for _ in range(request.max_fix_rounds):
            rounds += 1
            current = self.ollama_client.request_json(
                model=fix_model,
                system_prompt=build_translation_system_prompt(),
                user_prompt=build_fix_user_prompt(
                    source_language=request.source_language,
                    target_language=request.target_language,
                    source_profile=source_profile,
                    target_profile=target_profile,
                    source_code=request.source_code,
                    current_translation=current.translated_code,
                    compiler_error=current_check.stderr or current_check.detail,
                ),
                temperature=min(request.temperature, 0.2),
                response_model=TranslationEnvelope,
            )
            current_check = run_local_check(current.translated_code, request.target_language, target_profile)
            if current_check.passed is True:
                return current, current_check, rounds
        return current, current_check, rounds

    def _generate_semantic_review(
        self,
        request: TranslateRequest,
        *,
        source_profile: str,
        target_profile: str,
        translated_code: str,
        model_name: str,
    ) -> SemanticReview | None:
        if not request.include_semantic_review:
            return None
        if request.provider == "ollama":
            review_model = self.resolve_model(task="review", requested_model=request.model)
            return self.ollama_client.request_json(
                model=review_model,
                system_prompt=build_review_system_prompt(),
                user_prompt=build_review_user_prompt(
                    source_language=request.source_language,
                    target_language=request.target_language,
                    source_profile=source_profile,
                    target_profile=target_profile,
                    source_code=request.source_code,
                    translated_code=translated_code,
                ),
                temperature=0.0,
                response_model=SemanticReview,
            )

        return SemanticReview(
            summary="Heuristic review only. Use Ollama review mode for a stronger semantic audit.",
            fidelity_risks=[
                "Cross-language runtime differences may still exist even if the syntax check passed.",
                "Framework lifecycle mapping and dependency behavior were not deeply reviewed in heuristic mode.",
            ],
            strengths=["A deterministic local validation step was applied where available."],
            recommended_fixes=["Review dependency mappings, types, framework lifecycle hooks, and runtime assumptions manually."],
        )

    def _generate_artifacts(
        self,
        request: TranslateRequest,
        *,
        target_profile: str,
        translated_code: str,
        model_name: str,
    ) -> list[GeneratedArtifact]:
        artifacts: list[GeneratedArtifact] = []
        if request.generate_tests:
            if request.provider == "ollama":
                artifacts.append(
                    self.ollama_client.request_json(
                        model=model_name,
                        system_prompt=build_test_system_prompt(),
                        user_prompt=build_test_user_prompt(
                            target_language=request.target_language,
                            target_profile=target_profile,
                            translated_code=translated_code,
                        ),
                        temperature=0.0,
                        response_model=GeneratedArtifact,
                    )
                )
            else:
                artifacts.append(
                    GeneratedArtifact(
                        filename=f"smoke_test_{request.target_language}.txt",
                        language=request.target_language,
                        purpose="manual-smoke-test",
                        content=(
                            f"Validate the translated {target_profile} output against the original behavior with representative inputs, error cases, and dependency assumptions."
                        ),
                    )
                )
        return artifacts

    def translate(self, request: TranslateRequest) -> TranslateResponse:
        started = time.perf_counter()
        source_profile = ensure_profile(request.source_profile, request.source_language)
        target_profile = ensure_profile(request.target_profile, request.target_language)

        source_dependencies = extract_dependencies(request.source_code, request.source_language)
        source_frameworks = detect_frameworks(source_dependencies, code=request.source_code)

        envelope, model_name = self._translate_with_provider(
            request,
            source_profile=source_profile,
            target_profile=target_profile,
            source_dependencies=source_dependencies,
            source_frameworks=source_frameworks,
        )

        source_check = run_local_check(request.source_code, request.source_language, source_profile) if request.validate_source else None
        target_check = run_local_check(envelope.translated_code, request.target_language, target_profile) if request.validate_target else None

        envelope, target_check, fixed_rounds = self._compile_fix_loop(
            request,
            source_profile=source_profile,
            target_profile=target_profile,
            envelope=envelope,
            model_name=model_name,
            initial_target_check=target_check,
        )

        dependency_map = build_dependency_map(
            request.source_code,
            request.source_language,
            envelope.translated_code,
            request.target_language,
        )
        diff_text = (
            build_diff_text(
                request.source_code,
                envelope.translated_code,
                request.source_language,
                request.target_language,
            )
            if request.include_diff
            else ""
        )

        execution_result = (
            run_local_execution(envelope.translated_code, request.target_language, target_profile) if request.run_translated else None
        )
        semantic_review = self._generate_semantic_review(
            request,
            source_profile=source_profile,
            target_profile=target_profile,
            translated_code=envelope.translated_code,
            model_name=model_name,
        )
        artifacts = self._generate_artifacts(
            request,
            target_profile=target_profile,
            translated_code=envelope.translated_code,
            model_name=model_name,
        )
        suggestions = build_suggestions(
            source_check=source_check,
            target_check=target_check,
            execution_result=execution_result,
            dependency_map=dependency_map,
            warnings=envelope.warnings,
            semantic_review=semantic_review,
            fixed_rounds=fixed_rounds,
            source_profile=source_profile,
            target_profile=target_profile,
        )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        elapsed_seconds, elapsed_minutes, elapsed_human = humanize_elapsed_ms(elapsed_ms)

        return TranslateResponse(
            translated_code=envelope.translated_code,
            explanation=envelope.explanation,
            warnings=envelope.warnings,
            assumptions=envelope.assumptions,
            provider=request.provider,
            model=model_name,
            source_language=request.source_language,
            target_language=request.target_language,
            source_profile=source_profile,
            target_profile=target_profile,
            source_check=source_check,
            target_check=target_check,
            execution_result=execution_result,
            dependency_map=dependency_map,
            suggestions=suggestions,
            semantic_review=semantic_review,
            generated_artifacts=artifacts,
            diff_text=diff_text,
            fixed_rounds=fixed_rounds,
            elapsed_ms=elapsed_ms,
            elapsed_seconds=elapsed_seconds,
            elapsed_minutes=elapsed_minutes,
            elapsed_human=elapsed_human,
        )

    def translate_batch(self, request: BatchTranslateRequest) -> BatchTranslateResponse:
        started = time.perf_counter()
        results: list[TranslateResponse] = []
        for item in request.items:
            results.append(
                self.translate(
                    TranslateRequest(
                        source_code=item.source_code,
                        source_language=item.source_language,
                        target_language=item.target_language,
                        source_profile=item.source_profile,
                        target_profile=item.target_profile,
                        provider=request.provider,
                        model=request.model,
                        temperature=request.temperature,
                        validate_source=request.validate_source,
                        validate_target=request.validate_target,
                        include_diff=request.include_diff,
                        include_semantic_review=request.include_semantic_review,
                        generate_tests=request.generate_tests,
                        auto_fix=request.auto_fix,
                        max_fix_rounds=request.max_fix_rounds,
                        run_translated=request.run_translated,
                    )
                )
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        elapsed_seconds, elapsed_minutes, _ = humanize_elapsed_ms(elapsed_ms)
        return BatchTranslateResponse(
            results=results,
            total_elapsed_ms=elapsed_ms,
            total_elapsed_seconds=elapsed_seconds,
            total_elapsed_minutes=elapsed_minutes,
        )

    def review_only(self, request: ReviewRequest) -> SemanticReview:
        source_profile = ensure_profile(request.source_profile, request.source_language)
        target_profile = ensure_profile(request.target_profile, request.target_language)
        model_name = self.resolve_model(task="review", requested_model=request.model)
        if not self.settings.use_ollama:
            raise OllamaClientError("OLLAMA usage is disabled in settings.")
        return self.ollama_client.request_json(
            model=model_name,
            system_prompt=build_review_system_prompt(),
            user_prompt=build_review_user_prompt(
                source_language=request.source_language,
                target_language=request.target_language,
                source_profile=source_profile,
                target_profile=target_profile,
                source_code=request.source_code,
                translated_code=request.translated_code,
            ),
            temperature=0.0,
            response_model=SemanticReview,
        )

    def generate_project(self, request: GenerateProjectRequest) -> GenerateProjectResponse:
        started = time.perf_counter()
        target_profile = request.target_profile
        target_language = request.target_language or profile_to_language(target_profile) or "typescript"
        provider = request.provider

        if provider == "heuristic":
            blueprint = ProjectBlueprint(
                project_name="local_mvp_project",
                summary="A minimal heuristic fallback project blueprint. Use Ollama for richer architecture and multi-file generation.",
                files=[],
                setup_commands=["Review the prompt and create files manually or switch to Ollama provider."],
                run_commands=[],
                architecture_notes=["Heuristic builder mode does not synthesize full projects."],
                warnings=["Switch to Ollama for real project generation."],
                assumptions=[],
            )
            primary_check = None
            model_name = "heuristic"
        else:
            if not self.settings.use_ollama:
                raise OllamaClientError("OLLAMA usage is disabled in settings.")
            model_name = self.resolve_model(task="project", requested_model=request.model)
            blueprint = self.ollama_client.request_json(
                model=model_name,
                system_prompt=build_project_system_prompt(),
                user_prompt=build_project_user_prompt(
                    prompt=request.prompt,
                    target_profile=target_profile,
                    target_language=target_language,
                    include_tests=request.include_tests,
                    include_readme=request.include_readme,
                    include_docker=request.include_docker,
                    max_files=request.max_files,
                ),
                temperature=request.temperature,
                response_model=ProjectBlueprint,
            )
            primary_check = None
            if request.auto_verify_primary_file and blueprint.files:
                primary = blueprint.files[0]
                primary_check = run_local_check(primary.content, primary.language, target_profile)

        suggestions = build_generation_suggestions(target_profile=target_profile, blueprint=blueprint, primary_check=primary_check)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        elapsed_seconds, elapsed_minutes, elapsed_human = humanize_elapsed_ms(elapsed_ms)
        return GenerateProjectResponse(
            provider=provider,
            model=model_name,
            target_profile=target_profile,
            target_language=target_language,
            blueprint=blueprint,
            primary_check=primary_check,
            suggestions=suggestions,
            elapsed_ms=elapsed_ms,
            elapsed_seconds=elapsed_seconds,
            elapsed_minutes=elapsed_minutes,
            elapsed_human=elapsed_human,
        )

    def chat_codegen(self, request: ChatCodeRequest) -> ChatCodeResponse:
        started = time.perf_counter()
        target_profile = request.target_profile
        target_language = profile_to_language(target_profile) or "typescript"
        if request.provider == "heuristic":
            envelope = TranslationEnvelope(
                translated_code=f"# Heuristic builder fallback for {target_profile}\n# Switch to Ollama for richer code generation.\n",
                explanation="Heuristic mode does not truly synthesize new code. Use Ollama for generation.",
                warnings=["Ollama is recommended for prompt-to-code generation."],
                assumptions=[],
            )
            model_name = "heuristic"
        else:
            if not self.settings.use_ollama:
                raise OllamaClientError("OLLAMA usage is disabled in settings.")
            model_name = self.resolve_model(task="codegen", requested_model=request.model)
            envelope = self.ollama_client.request_json(
                model=model_name,
                system_prompt=build_chat_codegen_system_prompt(),
                user_prompt=build_chat_codegen_user_prompt(
                    prompt=request.prompt,
                    target_profile=target_profile,
                    target_language=target_language,
                ),
                temperature=request.temperature,
                response_model=TranslationEnvelope,
            )

        primary_check = run_local_check(envelope.translated_code, target_language, target_profile)
        suggestions = build_assistant_suggestions(
            primary_check=primary_check,
            warnings=envelope.warnings,
            next_steps=["Run the generated file in the target framework or language toolchain.", "Review assumptions before production use."],
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        elapsed_seconds, elapsed_minutes, elapsed_human = humanize_elapsed_ms(elapsed_ms)
        return ChatCodeResponse(
            provider=request.provider,
            model=model_name,
            target_profile=target_profile,
            target_language=target_language,
            translated_code=envelope.translated_code,
            explanation=envelope.explanation,
            suggestions=suggestions,
            primary_check=primary_check,
            elapsed_ms=elapsed_ms,
            elapsed_seconds=elapsed_seconds,
            elapsed_minutes=elapsed_minutes,
            elapsed_human=elapsed_human,
        )

    def suggest_prompt(self, request: PromptSuggestionRequest) -> tuple[PromptSuggestionResponse, list]:
        prompt = request.prompt.strip()
        prompt_lower = prompt.lower()
        strengths: list[str] = []
        missing_details: list[str] = []
        suggestions: list[str] = []
        score = 45

        if len(prompt.split()) >= 20:
            strengths.append("The prompt already has enough raw detail to guide a model.")
            score += 12
        else:
            missing_details.append("Add more specific requirements, not just a broad request.")

        if any(word in prompt_lower for word in ["api", "endpoint", "page", "component", "service", "cli", "dashboard"]):
            strengths.append("The prompt names a concrete artifact or surface area.")
            score += 10
        else:
            missing_details.append("Name the artifact you want, such as API, page, CLI, worker, migration, or controller.")

        if any(word in prompt_lower for word in ["node", "express", "nest", "next", "react", "vue", "laravel", "yii", "java", "sql", "python", "c#", ".net"]):
            strengths.append("The prompt already signals a preferred language or framework.")
            score += 8
        elif request.target_profile:
            strengths.append("A target profile was chosen outside the prompt.")
            score += 6
        else:
            missing_details.append("Specify the language or framework you want to target.")

        for label, keywords in PROMPT_CHECKLIST:
            if any(keyword in prompt_lower for keyword in keywords):
                score += 4
            else:
                missing_details.append(f"Consider adding {label}.")

        suggestions.extend(
            [
                "State the main user flow first, then list constraints such as auth, validation, storage, and tests.",
                "Say whether you want a single primary file, a small multi-file MVP, or a project blueprint.",
                "Mention versions, runtime assumptions, and whether Docker or CI should be included.",
            ]
        )

        if request.target_profile:
            profile = SUPPORTED_PROFILES[request.target_profile]
            suggestions.append(f"Tie the prompt to {profile.label} conventions, such as {profile.translation_notes}")

        improved_prompt = prompt
        bullet_block = [
            "Goal:",
            "Primary user flow:",
            "Target language/framework:",
            "Key endpoints/pages/components:",
            "Data model or schema:",
            "Validation and error handling:",
            "Auth and permissions:",
            "Testing expectations:",
            "Deployment/runtime constraints:",
        ]
        if len(prompt.split()) < 80:
            improved_prompt = prompt.rstrip() + "\n\n" + "\n".join(f"- {line}" for line in bullet_block)

        score = max(0, min(100, score))
        response = PromptSuggestionResponse(
            quality_score=score,
            strengths=strengths[:5],
            missing_details=missing_details[:8],
            suggestions=suggestions[:8],
            improved_prompt=improved_prompt,
        )
        return response, build_prompt_suggestions(response)

    def assistant_turn(self, request: AssistantTurnRequest) -> AssistantTurnResponse:
        started = time.perf_counter()
        target_profile = request.target_profile
        target_language = profile_to_language(target_profile) or "typescript"
        history_pairs = [(item.role, item.content) for item in request.history]

        if request.provider == "heuristic":
            message = {
                "generate": "Heuristic assistant mode can outline or stub code, but Ollama is strongly recommended for real generation.",
                "refactor": "Heuristic assistant mode can only make basic suggestions. Use Ollama for strong refactors.",
                "debug": "Heuristic assistant mode can point to likely issues but cannot deeply reason about framework state.",
                "explain": "Heuristic assistant mode is okay for basic explanations.",
                "review": "Heuristic assistant mode can only provide shallow review notes.",
                "test": "Heuristic assistant mode can suggest a smoke test outline.",
                "fix": "Heuristic assistant mode can suggest basic fixes only.",
            }[request.task]
            envelope = AssistantEnvelope(
                title=f"{request.task.title()} helper",
                message=message,
                code=request.code_context if request.task == "explain" else "",
                filename=SUPPORTED_PROFILES[target_profile].default_filename,
                warnings=["Switch to Ollama for the strongest code-assistant behavior."],
                assumptions=[],
                next_steps=["Use the Ollama provider for better code generation and debugging."],
            )
            model_name = "heuristic"
        else:
            if not self.settings.use_ollama:
                raise OllamaClientError("OLLAMA usage is disabled in settings.")
            model_name = self.resolve_model(task=f"assistant_{request.task}", requested_model=request.model)
            envelope = self.ollama_client.request_json(
                model=model_name,
                system_prompt=build_assistant_system_prompt(),
                user_prompt=build_assistant_user_prompt(
                    task=request.task,
                    prompt=request.prompt,
                    target_profile=target_profile,
                    target_language=target_language,
                    code_context=request.code_context,
                    history=history_pairs,
                ),
                temperature=request.temperature,
                response_model=AssistantEnvelope,
            )

        primary_check = None
        if envelope.code.strip():
            primary_check = run_local_check(envelope.code, target_language, target_profile)
        suggestions = build_assistant_suggestions(
            primary_check=primary_check,
            warnings=envelope.warnings,
            next_steps=envelope.next_steps,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        elapsed_seconds, elapsed_minutes, elapsed_human = humanize_elapsed_ms(elapsed_ms)
        return AssistantTurnResponse(
            provider=request.provider,
            model=model_name,
            task=request.task,
            target_profile=target_profile,
            target_language=target_language,
            title=envelope.title,
            message=envelope.message,
            code=envelope.code,
            filename=envelope.filename or SUPPORTED_PROFILES[target_profile].default_filename,
            warnings=envelope.warnings,
            assumptions=envelope.assumptions,
            next_steps=envelope.next_steps,
            primary_check=primary_check,
            suggestions=suggestions,
            elapsed_ms=elapsed_ms,
            elapsed_seconds=elapsed_seconds,
            elapsed_minutes=elapsed_minutes,
            elapsed_human=elapsed_human,
        )

    def analyze_project(self, request: ProjectAnalysisRequest) -> tuple[ProjectAnalysisResponse, list]:
        analysis = analyze_project_files([(item.path, item.content) for item in request.files])
        suggestions = build_project_analysis_suggestions(analysis)
        return analysis, suggestions

from translator import (
    BatchItem,
    BatchTranslateRequest,
    ChatCodeRequest,
    GenerateProjectRequest,
    TranslateRequest,
    TranslationService,
)


def test_translate_heuristic_contains_profiles_and_elapsed() -> None:
    service = TranslationService()
    result = service.translate(
        TranslateRequest(
            source_code="function add(a, b) { return a + b; }",
            source_language="javascript",
            target_language="python",
            source_profile="nodejs",
            target_profile="python",
            provider="heuristic",
            include_semantic_review=False,
            generate_tests=False,
            auto_fix=False,
        )
    )
    assert result.elapsed_minutes >= 0
    assert result.elapsed_human
    assert result.source_profile == "nodejs"
    assert result.target_profile == "python"
    assert result.suggestions


def test_translate_batch_returns_multiple_results() -> None:
    service = TranslationService()
    response = service.translate_batch(
        BatchTranslateRequest(
            items=[
                BatchItem(job_name="a.js", source_code="function add(a, b) { return a + b; }", source_language="javascript", target_language="python", source_profile="nodejs", target_profile="python"),
                BatchItem(job_name="b.py", source_code="print('hi')", source_language="python", target_language="javascript", source_profile="python", target_profile="nodejs"),
            ],
            provider="heuristic",
            include_semantic_review=False,
            generate_tests=False,
            auto_fix=False,
        )
    )
    assert len(response.results) == 2
    assert response.total_elapsed_minutes >= 0


def test_generate_project_heuristic_fallback() -> None:
    service = TranslationService()
    response = service.generate_project(
        GenerateProjectRequest(
            prompt="Build a leave request API",
            target_profile="expressjs",
            provider="heuristic",
        )
    )
    assert response.target_profile == "expressjs"
    assert response.blueprint.warnings


def test_chat_codegen_heuristic_fallback() -> None:
    service = TranslationService()
    response = service.chat_codegen(
        ChatCodeRequest(
            prompt="Create a hello world endpoint",
            target_profile="expressjs",
            provider="heuristic",
        )
    )
    assert response.target_profile == "expressjs"
    assert "heuristic" in response.explanation.lower() or "Switch to Ollama" in response.translated_code

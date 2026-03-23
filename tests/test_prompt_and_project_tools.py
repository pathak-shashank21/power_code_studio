from translator import AssistantTurnRequest, ProjectAnalysisFile, ProjectAnalysisRequest, PromptSuggestionRequest, TranslationService


def test_prompt_suggestion_scores_basic_prompt() -> None:
    service = TranslationService()
    result, suggestions = service.suggest_prompt(PromptSuggestionRequest(prompt="Build a leave app", target_profile="expressjs"))
    assert 0 <= result.quality_score <= 100
    assert result.improved_prompt
    assert suggestions


def test_project_analysis_detects_framework_and_dependencies() -> None:
    service = TranslationService()
    analysis, suggestions = service.analyze_project(
        ProjectAnalysisRequest(
            files=[
                ProjectAnalysisFile(path="package.json", content='{"dependencies":{"express":"^4.0.0","react":"18.0.0"}}'),
                ProjectAnalysisFile(path="src/server.js", content="const express = require('express'); const app = express();"),
            ]
        )
    )
    assert analysis.total_files == 2
    assert "expressjs" in analysis.frameworks
    assert "react" in analysis.dependencies
    assert suggestions


def test_assistant_heuristic_mode_returns_warning() -> None:
    service = TranslationService()
    response = service.assistant_turn(
        AssistantTurnRequest(
            prompt="Explain this function",
            target_profile="python",
            task="explain",
            code_context="def add(a, b):\n    return a + b\n",
            provider="heuristic",
        )
    )
    assert response.model == "heuristic"
    assert response.warnings
    assert response.title

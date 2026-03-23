from translator.schemas import CompileCheckResult, ProjectBlueprint
from translator.suggestions import build_generation_suggestions


def test_generation_suggestions_include_profile_and_validation() -> None:
    suggestions = build_generation_suggestions(
        target_profile="expressjs",
        blueprint=ProjectBlueprint(
            project_name="demo",
            summary="demo",
            files=[],
            setup_commands=[],
            run_commands=[],
            architecture_notes=["Use environment variables for config."],
            warnings=["This is a minimal MVP."],
            assumptions=[],
        ),
        primary_check=CompileCheckResult(language="javascript", available=False, passed=None, detail="node missing"),
    )
    assert suggestions
    assert any(item.category == "generation" for item in suggestions)

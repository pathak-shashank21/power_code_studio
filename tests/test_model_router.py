from translator.model_router import ModelRouter


def test_router_uses_role_model_in_auto_mode():
    router = ModelRouter(
        default_model="qwen2.5-coder:7b",
        review_model="llama3.1:8b",
        assistant_model="qwen2.5-coder:14b",
    )

    decision = router.choose(task="review", requested_model=None, available_models=["qwen2.5-coder:7b", "llama3.1:8b"])

    assert decision.selected_model == "llama3.1:8b"
    assert decision.role == "review"


def test_router_falls_back_when_requested_model_missing():
    router = ModelRouter(default_model="qwen2.5-coder:7b")

    decision = router.choose(
        task="translate",
        requested_model="missing-model",
        available_models=["qwen2.5-coder:7b", "llama3.1:8b"],
        strategy="single",
    )

    assert decision.selected_model == "qwen2.5-coder:7b"
    assert "unavailable" in decision.reason.lower()

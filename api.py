from __future__ import annotations

from fastapi import FastAPI, HTTPException

from translator import (
    AssistantTurnRequest,
    BatchTranslateRequest,
    ChatCodeRequest,
    GenerateProjectRequest,
    ProjectAnalysisRequest,
    PromptSuggestionRequest,
    ReviewRequest,
    TranslateRequest,
    TranslationService,
)
from translator.constants import SUPPORTED_LANGUAGES, SUPPORTED_PROFILES
from translator.executor import run_local_execution
from translator.ollama_client import OllamaClientError
from translator.validators import run_local_check

app = FastAPI(title="Power Code Studio API", version="5.0.0")
service = TranslationService()


@app.get("/health")
def health() -> dict:
    try:
        models = service.list_models()
        return {"ok": True, "ollama_models": models, "profiles": len(SUPPORTED_PROFILES)}
    except Exception as exc:
        return {"ok": False, "message": str(exc), "profiles": len(SUPPORTED_PROFILES)}


@app.get("/models")
def models() -> dict:
    try:
        return {"models": service.list_models()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/profiles")
def profiles() -> dict:
    return {
        "profiles": service.list_profiles(),
        "languages": [
            {"key": key, "label": spec.label, "extension": spec.extension}
            for key, spec in SUPPORTED_LANGUAGES.items()
        ],
    }


@app.post("/translate")
def translate(request: TranslateRequest) -> dict:
    try:
        return service.translate(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/translate-batch")
def translate_batch(request: BatchTranslateRequest) -> dict:
    try:
        return service.translate_batch(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/review")
def review(request: ReviewRequest) -> dict:
    try:
        return service.review_only(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/generate-project")
def generate_project(request: GenerateProjectRequest) -> dict:
    try:
        return service.generate_project(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat-code")
def chat_code(request: ChatCodeRequest) -> dict:
    try:
        return service.chat_codegen(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/assistant")
def assistant(request: AssistantTurnRequest) -> dict:
    try:
        return service.assistant_turn(request).model_dump()
    except OllamaClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/prompt-suggest")
def prompt_suggest(request: PromptSuggestionRequest) -> dict:
    result, suggestions = service.suggest_prompt(request)
    return {"result": result.model_dump(), "suggestions": [item.model_dump() for item in suggestions]}


@app.post("/analyze-project")
def analyze_project(request: ProjectAnalysisRequest) -> dict:
    result, suggestions = service.analyze_project(request)
    return {"analysis": result.model_dump(), "suggestions": [item.model_dump() for item in suggestions]}


@app.post("/validate")
def validate(payload: dict) -> dict:
    code = str(payload.get("code", ""))
    language = str(payload.get("language", ""))
    profile = payload.get("profile")
    if not code.strip():
        raise HTTPException(status_code=400, detail="Field 'code' is required.")
    if not language.strip():
        raise HTTPException(status_code=400, detail="Field 'language' is required.")
    return run_local_check(code, language, profile).model_dump()


@app.post("/run")
def run(payload: dict) -> dict:
    code = str(payload.get("code", ""))
    language = str(payload.get("language", ""))
    profile = payload.get("profile")
    if not code.strip():
        raise HTTPException(status_code=400, detail="Field 'code' is required.")
    if not language.strip():
        raise HTTPException(status_code=400, detail="Field 'language' is required.")
    return run_local_execution(code, language, profile).model_dump()

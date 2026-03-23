from __future__ import annotations

import io
import json
import textwrap
import zipfile

import streamlit as st

from translator import (
    AssistantHistoryMessage,
    AssistantTurnRequest,
    BatchItem,
    BatchTranslateRequest,
    ChatCodeRequest,
    GenerateProjectRequest,
    ProjectAnalysisFile,
    ProjectAnalysisRequest,
    PromptSuggestionRequest,
    TranslateRequest,
    TranslationService,
)
from translator.constants import DEFAULT_PROFILE_ORDER, SUPPORTED_LANGUAGES, SUPPORTED_PROFILES
from translator.ollama_client import OllamaClientError
from translator.utils import (
    detect_language_from_filename,
    detect_profile_from_filename,
    editor_mode_for_profile,
    profile_to_language,
)
from translator.validators import run_local_check

try:
    from streamlit_ace import st_ace
except Exception:  # pragma: no cover - optional dependency
    st_ace = None


st.set_page_config(page_title="Power Code Studio", layout="wide")
st.title("Power Code Studio")
st.caption(
    "A stronger Ollama-first local code studio for translation, AI code generation, framework-aware project scaffolding, assistant chat, project analysis, compile checks, and fix loops."
)

service = TranslationService()

EXAMPLES = {
    "Node Express → Python": {
        "source_profile": "expressjs",
        "target_profile": "python",
        "code": textwrap.dedent(
            """
            const express = require('express');
            const app = express();
            app.use(express.json());

            app.get('/health', (req, res) => {
              res.json({ ok: true, service: 'demo-api' });
            });

            app.post('/sum', (req, res) => {
              const values = Array.isArray(req.body.values) ? req.body.values : [];
              const total = values.reduce((acc, item) => acc + Number(item || 0), 0);
              res.json({ total });
            });

            app.listen(3000, () => console.log('server running'));
            """
        ).strip(),
    },
    "React → Next": {
        "source_profile": "reactjs",
        "target_profile": "nextjs",
        "code": textwrap.dedent(
            """
            import { useMemo, useState } from 'react';

            type Product = { id: number; name: string; price: number };

            export default function App() {
              const [query, setQuery] = useState('');
              const products: Product[] = [
                { id: 1, name: 'Notebook', price: 50 },
                { id: 2, name: 'Pen', price: 10 },
              ];

              const filtered = useMemo(
                () => products.filter(p => p.name.toLowerCase().includes(query.toLowerCase())),
                [query]
              );

              return (
                <main>
                  <input value={query} onChange={(e) => setQuery(e.target.value)} />
                  <ul>
                    {filtered.map(item => <li key={item.id}>{item.name} - {item.price}</li>)}
                  </ul>
                </main>
              );
            }
            """
        ).strip(),
    },
    "SQL → Java": {
        "source_profile": "sql",
        "target_profile": "java",
        "code": textwrap.dedent(
            """
            SELECT department_id, COUNT(*) AS employee_count, AVG(salary) AS avg_salary
            FROM employees
            WHERE active = 1
            GROUP BY department_id
            ORDER BY avg_salary DESC;
            """
        ).strip(),
    },
}

if "source_code" not in st.session_state:
    st.session_state["source_code"] = EXAMPLES["Node Express → Python"]["code"]
if "source_profile" not in st.session_state:
    st.session_state["source_profile"] = EXAMPLES["Node Express → Python"]["source_profile"]
if "target_profile" not in st.session_state:
    st.session_state["target_profile"] = EXAMPLES["Node Express → Python"]["target_profile"]
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []
if "assistant_code_context" not in st.session_state:
    st.session_state["assistant_code_context"] = ""


def render_code_editor(label: str, value: str, profile: str, key: str, height: int = 440) -> str:
    st.markdown(f"**{label}**")
    mode = editor_mode_for_profile(profile, profile_to_language(profile) or "typescript")
    if st_ace is not None:
        result = st_ace(
            value=value,
            language=mode,
            theme="monokai",
            height=height,
            key=key,
            wrap=True,
            font_size=14,
            tab_size=2,
            show_print_margin=False,
            auto_update=True,
        )
        return result if result is not None else value
    return st.text_area(label, value=value, height=height, key=f"{key}_textarea")


def render_check(title: str, check_obj) -> None:
    st.markdown(f"**{title}**")
    if check_obj is None:
        st.info("Check skipped.")
        return
    if check_obj.available is False:
        st.info(check_obj.detail)
        return
    if check_obj.passed is True:
        st.success(check_obj.detail)
    elif check_obj.passed is False:
        st.error(check_obj.detail)
    else:
        st.info(check_obj.detail)
    if check_obj.command:
        st.caption(f"Command: `{check_obj.command}`")
    if check_obj.stdout:
        st.code(check_obj.stdout, language="text")
    if check_obj.stderr:
        st.code(check_obj.stderr, language="text")


def result_to_zip_bytes(files: list[tuple[str, str]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files:
            zf.writestr(name, content)
    buffer.seek(0)
    return buffer.getvalue()


def render_suggestions(items) -> None:
    if not items:
        st.info("No suggestions returned.")
        return
    for item in items:
        prefix = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(item.severity, "•")
        st.markdown(f"{prefix} **{item.title}** — {item.detail}")


with st.sidebar:
    st.header("Studio settings")
    provider = st.selectbox("Provider", ["ollama", "heuristic"], index=0)

    models: list[str] = []
    models_error = None
    ollama_ready = False
    try:
        models = service.list_models()
        ollama_ready = True
    except Exception as exc:
        models_error = str(exc)

    st.subheader("Ollama model")
    if ollama_ready:
        st.success(f"Ollama reachable • {len(models)} model(s) found")
    elif provider == "ollama":
        st.error("Ollama unreachable")

    routing_mode = st.radio("Model routing", ["auto", "single"], horizontal=True, help="Auto uses task-aware routing. Single forces one model for every task.")
    default_model = service.settings.ollama_model if service.settings.ollama_model in models else (models[0] if models else service.settings.ollama_model)
    if models:
        selected_model = st.selectbox("Local model", models, index=models.index(default_model), disabled=routing_mode == "auto")
    else:
        selected_model = st.text_input("Local model", value=service.settings.ollama_model, disabled=routing_mode == "auto")
        if models_error:
            st.info(models_error)

    if routing_mode == "auto":
        with st.expander("Task-aware model routing", expanded=False):
            routing = service.get_model_routing()
            st.caption("These role defaults can be customized in .env. Missing role-specific values automatically fall back to the default model.")
            st.json(routing)

    selected_model = selected_model if routing_mode == "single" else None

    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.1 if provider == "ollama" else 0.0, step=0.1)
    validate_source = st.checkbox("Check source locally", value=True)
    validate_target = st.checkbox("Check translated code locally", value=True)
    include_diff = st.checkbox("Include diff view", value=True)
    include_semantic_review = st.checkbox("Include semantic review", value=True)
    generate_tests = st.checkbox("Generate test artifact", value=True)
    auto_fix = st.checkbox("Compile-and-fix retry", value=True)
    run_translated = st.checkbox("Run small target smoke check", value=False)
    max_fix_rounds = st.slider("Max fix rounds", min_value=0, max_value=5, value=2)

    st.divider()
    example_name = st.selectbox("Load example", list(EXAMPLES.keys()))
    if st.button("Apply example", use_container_width=True):
        example = EXAMPLES[example_name]
        st.session_state["source_code"] = example["code"]
        st.session_state["source_profile"] = example["source_profile"]
        st.session_state["target_profile"] = example["target_profile"]
        st.rerun()


tab_translate, tab_batch, tab_builder, tab_assistant, tab_analyzer, tab_validate, tab_notes = st.tabs(
    ["Translate", "Batch / multi-file", "AI builder", "AI assistant", "Project analyzer", "Validate / check", "Notes"]
)

with tab_translate:
    left, right = st.columns([1, 1])
    with left:
        source_profile = st.selectbox(
            "Source target/profile",
            DEFAULT_PROFILE_ORDER,
            key="source_profile",
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
        )
        source_language = profile_to_language(source_profile) or "javascript"
        st.caption(f"Base language: {SUPPORTED_LANGUAGES[source_language].label}")
        source_code = render_code_editor("Source code", st.session_state["source_code"], source_profile, "source_editor")
        st.session_state["source_code"] = source_code
    with right:
        target_profile = st.selectbox(
            "Target target/profile",
            DEFAULT_PROFILE_ORDER,
            key="target_profile",
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
        )
        target_language = profile_to_language(target_profile) or "typescript"
        st.caption(f"Base language: {SUPPORTED_LANGUAGES[target_language].label}")
        translated_placeholder = st.empty()

    if st.button("Translate code", type="primary", use_container_width=True):
        if not source_code.strip():
            st.error("Paste some source code first.")
        else:
            request = TranslateRequest(
                source_code=source_code,
                source_language=source_language,
                target_language=target_language,
                source_profile=source_profile,
                target_profile=target_profile,
                provider=provider,
                model=selected_model,
                temperature=temperature,
                validate_source=validate_source,
                validate_target=validate_target,
                include_diff=include_diff,
                include_semantic_review=include_semantic_review,
                generate_tests=generate_tests,
                auto_fix=auto_fix,
                max_fix_rounds=max_fix_rounds,
                run_translated=run_translated,
            )
            try:
                result = service.translate(request)
                translated_placeholder.code(result.translated_code, language=editor_mode_for_profile(target_profile, target_language))
                st.markdown(
                    f"**Provider:** {result.provider}  \\\n**Model:** {result.model}  \\\n**Elapsed:** {result.elapsed_ms} ms = {result.elapsed_seconds} sec = {result.elapsed_minutes} min"
                )
                st.caption(f"Human readable: {result.elapsed_human}")
                st.markdown(f"**Explanation**\n\n{result.explanation or 'No explanation returned.'}")

                out_tabs = st.tabs(["Checks", "Dependencies", "Review", "Diff", "Artifacts", "Suggestions"])
                with out_tabs[0]:
                    render_check("Source check", result.source_check)
                    st.divider()
                    render_check("Translated code check", result.target_check)
                    if result.execution_result:
                        st.divider()
                        render_check("Runtime smoke check", result.execution_result)
                with out_tabs[1]:
                    st.json(result.dependency_map.model_dump() if result.dependency_map else {})
                with out_tabs[2]:
                    if result.semantic_review:
                        st.json(result.semantic_review.model_dump())
                    else:
                        st.info("Semantic review disabled.")
                with out_tabs[3]:
                    if result.diff_text:
                        st.code(result.diff_text, language="diff")
                    else:
                        st.info("Diff disabled.")
                with out_tabs[4]:
                    if result.generated_artifacts:
                        for artifact in result.generated_artifacts:
                            st.markdown(f"**{artifact.filename}** — {artifact.purpose}")
                            st.code(artifact.content, language=artifact.language)
                            st.download_button(
                                f"Download {artifact.filename}",
                                data=artifact.content.encode("utf-8"),
                                file_name=artifact.filename,
                                mime="text/plain",
                                key=f"artifact_{artifact.filename}",
                            )
                    else:
                        st.info("No artifacts generated.")
                with out_tabs[5]:
                    render_suggestions(result.suggestions)

                st.download_button(
                    "Download translated primary file",
                    data=result.translated_code.encode("utf-8"),
                    file_name=SUPPORTED_PROFILES[target_profile].default_filename.split("/")[-1],
                    mime="text/plain",
                )
                st.download_button(
                    "Download translation result JSON",
                    data=json.dumps(result.model_dump(), indent=2).encode("utf-8"),
                    file_name="translation_result.json",
                    mime="application/json",
                )
            except OllamaClientError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)

with tab_batch:
    batch_tabs = st.tabs(["Batch translation", "Prompt coach", "Prompt → project"])

    with batch_tabs[0]:
        st.subheader("Batch / multi-file translation")
        st.caption("Upload many files. The studio infers base language and profile where possible, then translates each file independently into one selected target profile.")
        uploads = st.file_uploader(
            "Upload code files",
            accept_multiple_files=True,
            type=["ts", "tsx", "py", "js", "jsx", "java", "cs", "cpp", "cc", "cxx", "go", "rs", "php", "rb", "sql", "vue"],
            key="batch_uploads",
        )
        batch_target_profile = st.selectbox(
            "Batch target profile",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="batch_target_profile",
            index=DEFAULT_PROFILE_ORDER.index("python"),
        )
        batch_fallback_profile = st.selectbox(
            "Fallback source profile",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="batch_fallback_profile",
            index=DEFAULT_PROFILE_ORDER.index("javascript"),
        )

        if st.button("Run batch translation", use_container_width=True):
            if not uploads:
                st.error("Upload at least one file first.")
            else:
                items: list[BatchItem] = []
                target_lang = profile_to_language(batch_target_profile) or "python"
                for upload in uploads:
                    raw = upload.read().decode("utf-8", errors="ignore")
                    inferred_profile = detect_profile_from_filename(upload.name)
                    inferred_language = detect_language_from_filename(upload.name)
                    source_profile_for_file = inferred_profile or batch_fallback_profile
                    source_language_for_file = inferred_language or (profile_to_language(source_profile_for_file) or "javascript")
                    items.append(
                        BatchItem(
                            job_name=upload.name,
                            source_code=raw,
                            source_language=source_language_for_file,
                            target_language=target_lang,
                            source_profile=source_profile_for_file,
                            target_profile=batch_target_profile,
                        )
                    )
                batch_request = BatchTranslateRequest(
                    items=items,
                    provider=provider,
                    model=selected_model,
                    temperature=temperature,
                    validate_source=validate_source,
                    validate_target=validate_target,
                    include_diff=include_diff,
                    include_semantic_review=include_semantic_review,
                    generate_tests=generate_tests,
                    auto_fix=auto_fix,
                    max_fix_rounds=max_fix_rounds,
                    run_translated=run_translated,
                )
                try:
                    batch_response = service.translate_batch(batch_request)
                    st.success(
                        f"Batch done: {len(batch_response.results)} job(s) in {batch_response.total_elapsed_ms} ms = {batch_response.total_elapsed_seconds} sec = {batch_response.total_elapsed_minutes} min"
                    )
                    files: list[tuple[str, str]] = []
                    for upload, result in zip(uploads, batch_response.results, strict=False):
                        target_name = upload.name.rsplit(".", 1)[0] + "_translated_" + SUPPORTED_PROFILES[batch_target_profile].default_filename.split("/")[-1]
                        files.append((target_name, result.translated_code))
                        files.append((upload.name.rsplit(".", 1)[0] + "_result.json", json.dumps(result.model_dump(), indent=2)))
                    files.append(("batch_summary.json", json.dumps(batch_response.model_dump(), indent=2)))

                    for upload, result in zip(uploads, batch_response.results, strict=False):
                        with st.expander(upload.name):
                            st.caption(f"{result.source_profile} → {result.target_profile}")
                            st.code(result.translated_code, language=editor_mode_for_profile(result.target_profile, result.target_language))
                            render_suggestions(result.suggestions[:6])

                    st.download_button(
                        "Download batch outputs ZIP",
                        data=result_to_zip_bytes(files),
                        file_name="batch_outputs.zip",
                        mime="application/zip",
                    )
                except Exception as exc:
                    st.exception(exc)

    with batch_tabs[1]:
        st.subheader("Prompt coach")
        st.caption("Strengthen your natural-language prompt before generation. This helps you get results closer to what ChatGPT or Gemini style coding workflows aim for.")
        prompt_profile = st.selectbox(
            "Intended target profile",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="prompt_profile",
            index=DEFAULT_PROFILE_ORDER.index("expressjs"),
        )
        prompt_text = st.text_area(
            "Prompt to improve",
            value="Build a leave request system.",
            height=180,
            key="prompt_text",
        )
        if st.button("Analyze prompt", use_container_width=True):
            result, suggestions = service.suggest_prompt(PromptSuggestionRequest(prompt=prompt_text, target_profile=prompt_profile))
            st.metric("Prompt quality score", result.quality_score)
            prompt_tabs = st.tabs(["Strengths", "Missing details", "Improved prompt", "Suggestions"])
            with prompt_tabs[0]:
                for item in result.strengths:
                    st.markdown(f"- {item}")
            with prompt_tabs[1]:
                for item in result.missing_details:
                    st.markdown(f"- {item}")
            with prompt_tabs[2]:
                st.code(result.improved_prompt, language="markdown")
            with prompt_tabs[3]:
                render_suggestions(suggestions)

    with batch_tabs[2]:
        st.subheader("Prompt → project")
        st.caption("Generate a compact multi-file blueprint from a strong natural-language prompt.")
        project_profile = st.selectbox(
            "Target project profile",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="project_profile",
            index=DEFAULT_PROFILE_ORDER.index("expressjs"),
        )
        project_prompt = st.text_area(
            "Project request",
            value="Create a Node Express API for employee leave requests with create/list/approve endpoints, in-memory storage, input validation, and a small README.",
            height=220,
        )
        include_tests_builder = st.checkbox("Include tests", value=True, key="include_tests_builder")
        include_readme_builder = st.checkbox("Include README", value=True, key="include_readme_builder")
        include_docker_builder = st.checkbox("Include Docker", value=False, key="include_docker_builder")
        max_files_builder = st.slider("Max files", min_value=3, max_value=20, value=8, key="max_files_builder")

        if st.button("Generate project blueprint", type="primary", use_container_width=True):
            try:
                response = service.generate_project(
                    GenerateProjectRequest(
                        prompt=project_prompt,
                        target_profile=project_profile,
                        provider=provider,
                        model=selected_model,
                        temperature=temperature,
                        include_tests=include_tests_builder,
                        include_readme=include_readme_builder,
                        include_docker=include_docker_builder,
                        max_files=max_files_builder,
                        auto_verify_primary_file=True,
                    )
                )
                st.markdown(
                    f"**Elapsed:** {response.elapsed_ms} ms = {response.elapsed_seconds} sec = {response.elapsed_minutes} min"
                )
                st.markdown(f"**Project:** {response.blueprint.project_name}")
                st.markdown(response.blueprint.summary)
                render_check("Primary file check", response.primary_check)

                zip_files: list[tuple[str, str]] = []
                file_tabs = st.tabs(["Files", "Commands", "Architecture", "Suggestions"])
                with file_tabs[0]:
                    if response.blueprint.files:
                        for project_file in response.blueprint.files:
                            st.markdown(f"**{project_file.path}** — {project_file.purpose}")
                            st.code(project_file.content, language=editor_mode_for_profile(project_profile, project_file.language))
                            zip_files.append((project_file.path, project_file.content))
                    else:
                        st.info("No files generated.")
                with file_tabs[1]:
                    st.markdown("**Setup commands**")
                    st.code("\n".join(response.blueprint.setup_commands) or "No setup commands.", language="bash")
                    st.markdown("**Run commands**")
                    st.code("\n".join(response.blueprint.run_commands) or "No run commands.", language="bash")
                with file_tabs[2]:
                    for note in response.blueprint.architecture_notes:
                        st.markdown(f"- {note}")
                    if response.blueprint.warnings:
                        st.markdown("**Warnings**")
                        for note in response.blueprint.warnings:
                            st.markdown(f"- {note}")
                with file_tabs[3]:
                    render_suggestions(response.suggestions)

                zip_files.append(("project_blueprint.json", json.dumps(response.model_dump(), indent=2)))
                st.download_button(
                    "Download generated project ZIP",
                    data=result_to_zip_bytes(zip_files),
                    file_name=f"{response.blueprint.project_name or 'generated_project'}.zip",
                    mime="application/zip",
                )
            except Exception as exc:
                st.exception(exc)

with tab_builder:
    builder_subtabs = st.tabs(["Prompt → code", "Single-file validate"])

    with builder_subtabs[0]:
        st.subheader("NLP code generation")
        st.caption("Describe what you want and generate a strong primary file for the selected target profile.")
        codegen_profile = st.selectbox(
            "Target profile for generated code",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="codegen_profile",
            index=DEFAULT_PROFILE_ORDER.index("nextjs"),
        )
        codegen_prompt = st.text_area(
            "Describe the code you want",
            value="Build a small Next.js page with a search bar, fetch-based data loading, loading/error state, and a reusable result card component.",
            height=180,
        )
        if st.button("Generate code from prompt", use_container_width=True):
            try:
                response = service.chat_codegen(
                    ChatCodeRequest(
                        prompt=codegen_prompt,
                        target_profile=codegen_profile,
                        provider=provider,
                        model=selected_model,
                        temperature=temperature,
                    )
                )
                st.markdown(
                    f"**Elapsed:** {response.elapsed_ms} ms = {response.elapsed_seconds} sec = {response.elapsed_minutes} min"
                )
                st.code(response.translated_code, language=editor_mode_for_profile(response.target_profile, response.target_language))
                st.markdown(f"**Explanation**\n\n{response.explanation}")
                render_check("Primary file check", response.primary_check)
                render_suggestions(response.suggestions)
                st.download_button(
                    "Download generated file",
                    data=response.translated_code.encode("utf-8"),
                    file_name=SUPPORTED_PROFILES[response.target_profile].default_filename.split("/")[-1],
                    mime="text/plain",
                )
            except Exception as exc:
                st.exception(exc)

    with builder_subtabs[1]:
        st.subheader("Single-file validate")
        validate_profile = st.selectbox(
            "Validation profile",
            DEFAULT_PROFILE_ORDER,
            format_func=lambda key: SUPPORTED_PROFILES[key].label,
            key="single_validate_profile",
            index=DEFAULT_PROFILE_ORDER.index("python"),
        )
        validate_code = render_code_editor(
            "Code to validate",
            "def add(a, b):\n    return a + b\n",
            validate_profile,
            "single_validate_code",
            height=260,
        )
        if st.button("Validate this file", use_container_width=True, key="single_validate_button"):
            language = profile_to_language(validate_profile) or "python"
            result = run_local_check(validate_code, language, validate_profile)
            render_check("Validation result", result)

with tab_assistant:
    st.subheader("AI assistant")
    st.caption("Use this like a local coding assistant for generate, debug, explain, refactor, review, test, or fix workflows.")
    assistant_task = st.selectbox(
        "Assistant task",
        ["generate", "refactor", "debug", "explain", "review", "test", "fix"],
        index=0,
    )
    assistant_profile = st.selectbox(
        "Target profile",
        DEFAULT_PROFILE_ORDER,
        format_func=lambda key: SUPPORTED_PROFILES[key].label,
        key="assistant_profile",
        index=DEFAULT_PROFILE_ORDER.index("reactjs"),
    )
    assistant_prompt = st.text_area(
        "Ask the assistant",
        value="Create a React page that shows employee cards with search and status filters.",
        height=150,
        key="assistant_prompt",
    )
    assistant_code_context = render_code_editor(
        "Optional code context",
        st.session_state.get("assistant_code_context", ""),
        assistant_profile,
        "assistant_code_context",
        height=260,
    )

    action_cols = st.columns([1, 1, 1])
    if action_cols[0].button("Send to assistant", type="primary", use_container_width=True):
        try:
            response = service.assistant_turn(
                AssistantTurnRequest(
                    prompt=assistant_prompt,
                    target_profile=assistant_profile,
                    task=assistant_task,
                    code_context=assistant_code_context,
                    history=[AssistantHistoryMessage(**item) for item in st.session_state["assistant_history"]],
                    provider=provider,
                    model=selected_model,
                    temperature=temperature,
                )
            )
            st.session_state["assistant_history"].append({"role": "user", "content": assistant_prompt})
            assistant_summary = response.message
            if response.code.strip():
                assistant_summary += "\n\n[Assistant returned code output.]"
            st.session_state["assistant_history"].append({"role": "assistant", "content": assistant_summary})

            st.markdown(f"### {response.title}")
            st.markdown(response.message)
            if response.code.strip():
                st.code(response.code, language=editor_mode_for_profile(response.target_profile, response.target_language))
                render_check("Assistant code check", response.primary_check)
                st.download_button(
                    "Download assistant output",
                    data=response.code.encode("utf-8"),
                    file_name=response.filename or SUPPORTED_PROFILES[assistant_profile].default_filename.split("/")[-1],
                    mime="text/plain",
                )
            render_suggestions(response.suggestions)
            if response.assumptions:
                st.markdown("**Assumptions**")
                for item in response.assumptions:
                    st.markdown(f"- {item}")
            if response.next_steps:
                st.markdown("**Next steps**")
                for item in response.next_steps:
                    st.markdown(f"- {item}")
        except Exception as exc:
            st.exception(exc)

    if action_cols[1].button("Clear chat history", use_container_width=True):
        st.session_state["assistant_history"] = []
        st.rerun()
    if action_cols[2].button("Export chat history", use_container_width=True):
        st.download_button(
            "Download assistant_history.json",
            data=json.dumps(st.session_state["assistant_history"], indent=2).encode("utf-8"),
            file_name="assistant_history.json",
            mime="application/json",
            key="assistant_history_export",
        )

    if st.session_state["assistant_history"]:
        st.markdown("**Conversation history**")
        for item in st.session_state["assistant_history"]:
            prefix = "🧑 User" if item["role"] == "user" else "🤖 Assistant"
            st.markdown(f"**{prefix}:** {item['content']}")

with tab_analyzer:
    st.subheader("Project analyzer")
    st.caption("Upload a set of project files and get a deterministic architecture summary, framework hints, dependency summary, setup hints, and risks.")
    project_uploads = st.file_uploader(
        "Upload project files for analysis",
        accept_multiple_files=True,
        type=["ts", "tsx", "js", "jsx", "json", "py", "php", "java", "cs", "go", "rs", "rb", "sql", "vue", "txt", "xml", "toml", "yml", "yaml", "md"],
        key="project_uploads",
    )
    if st.button("Analyze uploaded project", use_container_width=True):
        if not project_uploads:
            st.error("Upload some files first.")
        else:
            request = ProjectAnalysisRequest(
                files=[ProjectAnalysisFile(path=item.name, content=item.read().decode("utf-8", errors="ignore")) for item in project_uploads]
            )
            analysis, suggestions = service.analyze_project(request)
            st.markdown(f"**Total files:** {analysis.total_files}")
            st.markdown(analysis.architecture_summary)
            analyzer_tabs = st.tabs(["Overview", "Files", "Suggestions", "Download"])
            with analyzer_tabs[0]:
                st.json(
                    {
                        "language_counts": analysis.language_counts,
                        "profile_counts": analysis.profile_counts,
                        "frameworks": analysis.frameworks,
                        "dependencies": analysis.dependencies,
                        "suggested_profiles": analysis.suggested_profiles,
                        "setup_hints": analysis.setup_hints,
                        "risks": analysis.risks,
                    }
                )
            with analyzer_tabs[1]:
                for item in analysis.file_insights:
                    st.markdown(f"**{item.path}**")
                    st.caption(f"language={item.language or 'unknown'} | profile={item.profile or 'unknown'}")
                    if item.frameworks:
                        st.markdown(f"- frameworks: {', '.join(item.frameworks)}")
                    if item.dependencies:
                        st.markdown(f"- dependencies: {', '.join(item.dependencies[:12])}")
                    for note in item.notes:
                        st.markdown(f"- {note}")
            with analyzer_tabs[2]:
                render_suggestions(suggestions)
            with analyzer_tabs[3]:
                st.download_button(
                    "Download analysis JSON",
                    data=json.dumps(analysis.model_dump(), indent=2).encode("utf-8"),
                    file_name="project_analysis.json",
                    mime="application/json",
                )

with tab_validate:
    st.subheader("Validate or smoke-check code")
    check_profile = st.selectbox(
        "Profile",
        DEFAULT_PROFILE_ORDER,
        format_func=lambda key: SUPPORTED_PROFILES[key].label,
        key="validate_profile",
        index=DEFAULT_PROFILE_ORDER.index("python"),
    )
    check_language = profile_to_language(check_profile) or "python"
    check_code = render_code_editor(
        "Code to validate",
        "def hello(name):\n    return f'Hello, {name}'\n",
        check_profile,
        "validate_editor",
        height=280,
    )
    if st.button("Run local validation", use_container_width=True, key="validate_button"):
        result = run_local_check(check_code, check_language, check_profile)
        render_check("Validation result", result)

with tab_notes:
    st.subheader("What is in this studio")
    st.markdown(
        """
- Profile-aware translation across plain languages and framework targets.
- Supported targets include Python, JavaScript, TypeScript, Node.js, Express.js, NestJS, Next.js, React.js, Vue.js, PHP, Laravel, Yii2, .NET C#, Java, SQL, Go, Rust, C++, and Ruby.
- Ollama-first generation and assistant workflows.
- Compile or syntax verification where the local toolchain exists.
- Compile-and-fix retry loops for translated output.
- Batch translation with ZIP export.
- Prompt coaching to improve natural-language requests.
- Prompt-to-code and prompt-to-project generation.
- Assistant-style chat workflow for generate, debug, explain, refactor, review, test, and fix tasks.
- Deterministic project analyzer for architecture and dependency insight.
- Downloadable artifacts and JSON outputs.
        """
    )
    st.info(
        "This is a strong local-first studio, but framework-perfect builds still depend on the actual local toolchains being installed, such as Node, TypeScript, Java, .NET, PHP, Composer, or framework CLIs."
    )

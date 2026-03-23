from __future__ import annotations

from .analysis import language_pair_notes
from .constants import SUPPORTED_LANGUAGES, SUPPORTED_PROFILES


def build_translation_system_prompt() -> str:
    return (
        "You are an expert polyglot software engineer. "
        "Translate code faithfully while preserving logic, data flow, edge cases, and intent. "
        "Return only structured JSON matching the requested schema. "
        "Do not wrap output in markdown fences. "
        "If the target is a framework profile, return the most important primary file for that profile, not a full multi-file project. "
        "Prefer correctness over creativity, minimize placeholders, and include warnings when framework or dependency mapping is uncertain."
    )


def build_translation_user_prompt(
    *,
    source_language: str,
    target_language: str,
    source_profile: str,
    target_profile: str,
    source_code: str,
    detected_dependencies: list[str],
    detected_frameworks: list[str],
) -> str:
    source_profile_spec = SUPPORTED_PROFILES[source_profile]
    target_profile_spec = SUPPORTED_PROFILES[target_profile]
    target_language_spec = SUPPORTED_LANGUAGES[target_language]
    pair_notes = language_pair_notes(source_language, target_language)

    return f"""
Translate the following code.

Source language: {SUPPORTED_LANGUAGES[source_language].label}
Source profile: {source_profile_spec.label}
Target language: {target_language_spec.label}
Target profile: {target_profile_spec.label}
Detected dependencies: {', '.join(detected_dependencies) if detected_dependencies else 'none'}
Detected framework hints: {', '.join(detected_frameworks) if detected_frameworks else 'none'}

Target profile guidance:
- {target_profile_spec.translation_notes}
- {target_profile_spec.generation_notes}
- Validation scope: {target_profile_spec.validation_scope}
- Language notes: {target_language_spec.target_notes}

Pair-specific notes:
{chr(10).join('- ' + note for note in pair_notes) if pair_notes else '- No additional pair-specific notes.'}

Rules:
1. Preserve business logic and control flow.
2. Keep the output as a single primary file suitable for the target profile.
3. Do not invent APIs unless they are standard for the target profile.
4. When the source relies on a framework-specific concept, map it to the closest target concept and mention assumptions.
5. Prefer code that can pass local syntax or compile checks.
6. Do not include markdown fences.

Return JSON with:
- translated_code: the target file content only
- explanation: short but useful explanation of the mapping
- warnings: array of concrete warnings
- assumptions: array of assumptions you made

Source code:
{source_code}
""".strip()


def build_fix_user_prompt(
    *,
    source_language: str,
    target_language: str,
    source_profile: str,
    target_profile: str,
    source_code: str,
    current_translation: str,
    compiler_error: str,
) -> str:
    return f"""
Repair the translated code so it passes the target language or profile validation.

Source language: {source_language}
Target language: {target_language}
Source profile: {source_profile}
Target profile: {target_profile}

Rules:
- Keep the original intent and behavior.
- Fix only what is necessary to resolve the validation failure.
- Do not switch frameworks unless absolutely necessary.
- Return JSON only.

Compiler or validator feedback:
{compiler_error}

Original source:
{source_code}

Current translation:
{current_translation}
""".strip()


def build_review_system_prompt() -> str:
    return (
        "You are a strict code reviewer. Compare source and translated code for semantic fidelity. "
        "Return only JSON matching the requested schema. Focus on behavior, edge cases, data contracts, async logic, framework lifecycle differences, and dependency mismatches."
    )


def build_review_user_prompt(
    *,
    source_language: str,
    target_language: str,
    source_profile: str,
    target_profile: str,
    source_code: str,
    translated_code: str,
) -> str:
    return f"""
Review whether the translated code preserves the original behavior.

Source language: {source_language}
Target language: {target_language}
Source profile: {source_profile}
Target profile: {target_profile}

Return JSON with:
- summary
- fidelity_risks[]
- strengths[]
- recommended_fixes[]

Source code:
{source_code}

Translated code:
{translated_code}
""".strip()


def build_test_system_prompt() -> str:
    return (
        "You generate pragmatic test artifacts. "
        "Return JSON only. Produce a small but useful smoke or unit test file for the target code."
    )


def build_test_user_prompt(
    *,
    target_language: str,
    target_profile: str,
    translated_code: str,
) -> str:
    profile = SUPPORTED_PROFILES[target_profile]
    return f"""
Create a small test or smoke-check artifact for this translated code.

Target language: {target_language}
Target profile: {profile.label}

Return JSON with:
- filename
- language
- purpose
- content

The artifact should be realistic and runnable or at least directly useful for manual verification.

Translated code:
{translated_code}
""".strip()


def build_project_system_prompt() -> str:
    return (
        "You are a senior software architect and coding agent. "
        "Given a natural-language product request, generate a compact but production-minded project blueprint. "
        "Return only structured JSON matching the schema. "
        "The project must be locally runnable, coherent, and framework-appropriate. "
        "Prefer 4 to 10 high-value files over huge boilerplate dumps."
    )


def build_project_user_prompt(
    *,
    prompt: str,
    target_profile: str,
    target_language: str,
    include_tests: bool,
    include_readme: bool,
    include_docker: bool,
    max_files: int,
) -> str:
    profile = SUPPORTED_PROFILES[target_profile]
    language = SUPPORTED_LANGUAGES[target_language]
    return f"""
Build a project blueprint from this request.

Target profile: {profile.label}
Target language: {language.label}
Max files: {max_files}
Include tests: {include_tests}
Include README: {include_readme}
Include Docker support: {include_docker}

Profile guidance:
- {profile.generation_notes}
- Validation scope: {profile.validation_scope}
- Language notes: {language.target_notes}

Rules:
1. Return a realistic small project, not a single code snippet.
2. Each file must have a clear path, language, purpose, and content.
3. Include package manifests or equivalent only when needed.
4. Keep code coherent across files.
5. Avoid placeholders like TODO unless absolutely necessary.
6. Prefer secure defaults and clear configuration points.
7. If the request is broad, create a strong MVP slice.

Return JSON with:
- project_name
- summary
- files[] with path, language, purpose, content
- setup_commands[]
- run_commands[]
- architecture_notes[]
- warnings[]
- assumptions[]

User request:
{prompt}
""".strip()


def build_chat_codegen_system_prompt() -> str:
    return (
        "You are an expert coding assistant similar to a focused local code-generation agent. "
        "Given a natural-language request, produce one strong primary file in the requested target profile. "
        "Return JSON only. Keep the answer implementation-first, not essay-first."
    )


def build_chat_codegen_user_prompt(*, prompt: str, target_profile: str, target_language: str) -> str:
    profile = SUPPORTED_PROFILES[target_profile]
    language = SUPPORTED_LANGUAGES[target_language]
    return f"""
Generate code from this request.

Target profile: {profile.label}
Target language: {language.label}
Primary file expectation: {profile.default_filename}
Validation scope: {profile.validation_scope}

Rules:
- Produce one strong primary file only.
- Make it immediately useful.
- Prefer concrete code over explanations.
- Avoid markdown fences.

Return JSON with:
- translated_code
- explanation
- warnings[]
- assumptions[]

User request:
{prompt}
""".strip()


def build_assistant_system_prompt() -> str:
    return (
        "You are a powerful local coding assistant inside a code studio. "
        "Support tasks such as generate, refactor, debug, explain, review, test, and fix. "
        "Be precise, practical, and implementation-first. "
        "Return only JSON matching the assistant schema. "
        "If code is requested or helpful, include one strong primary file or patch-ready replacement. "
        "If the user mainly asked for explanation, code may be empty."
    )


def build_assistant_user_prompt(
    *,
    task: str,
    prompt: str,
    target_profile: str,
    target_language: str,
    code_context: str,
    history: list[tuple[str, str]],
) -> str:
    profile = SUPPORTED_PROFILES[target_profile]
    language = SUPPORTED_LANGUAGES[target_language]
    history_text = "\n".join(f"{role.upper()}: {content}" for role, content in history[-8:]) or "No prior history."
    return f"""
Assist with this coding task.

Task: {task}
Target profile: {profile.label}
Target language: {language.label}
Expected primary file: {profile.default_filename}
Validation scope: {profile.validation_scope}

Conversation history:
{history_text}

Current code context:
{code_context or 'No code context provided.'}

User request:
{prompt}

Rules:
1. Prioritize correctness and directly useful output.
2. If returning code, make it the full primary file or a precise replacement, not fragments unless the task explicitly asks for a patch.
3. Keep the message concise but useful.
4. Add warnings when framework or dependency assumptions exist.
5. Add next_steps for what the user should do next.
6. Avoid markdown fences.

Return JSON with:
- title
- message
- code
- filename
- warnings[]
- assumptions[]
- next_steps[]
""".strip()

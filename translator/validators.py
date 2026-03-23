from __future__ import annotations

import ast
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from .constants import SUPPORTED_LANGUAGES, SUPPORTED_PROFILES
from .schemas import CompileCheckResult
from .utils import ensure_profile, normalize_language, normalize_profile, profile_to_language


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def _has_rust_main(code: str) -> bool:
    return bool(re.search(r"\bfn\s+main\s*\(", code))


def _has_go_main(code: str) -> bool:
    return "package main" in code and bool(re.search(r"\bfunc\s+main\s*\(", code))


def _has_csharp_main(code: str) -> bool:
    return bool(re.search(r"\bstatic\s+void\s+Main\s*\(", code)) or "Console.Write" in code or "WebApplication.CreateBuilder" in code


def _contains_jsx(code: str) -> bool:
    return bool(re.search(r"<\/?[A-Z][A-Za-z0-9]*", code) or re.search(r"<div[\s>]", code))


def choose_filename(code: str, language: str, profile: str | None = None) -> str:
    language = normalize_language(language)
    profile_key = normalize_profile(profile) if profile else None

    if profile_key:
        default_name = SUPPORTED_PROFILES[profile_key].default_filename
        if "." in Path(default_name).name:
            return default_name

    ext = SUPPORTED_LANGUAGES[language].extension

    if language == "java":
        match = re.search(r"public\s+class\s+(\w+)", code)
        return f"{match.group(1) if match else 'Main'}{ext}"
    if language == "go":
        return f"{'main' if _has_go_main(code) else 'lib'}{ext}"
    if language == "rust":
        return f"{'main' if _has_rust_main(code) else 'lib'}{ext}"
    if language == "csharp":
        return f"{'Program' if _has_csharp_main(code) else 'Library'}{ext}"
    if profile_key == "reactjs":
        return "App.tsx"
    if profile_key == "nextjs":
        return "page.tsx"
    if profile_key == "vuejs":
        return "App.vue"
    return f"main{ext}"


def quick_syntax_check(code: str, language: str) -> CompileCheckResult:
    language = normalize_language(language)
    if language == "python":
        try:
            ast.parse(code)
            return CompileCheckResult(
                language=language,
                available=True,
                passed=True,
                command="ast.parse",
                detail="Python AST parse succeeded.",
            )
        except SyntaxError as exc:
            return CompileCheckResult(
                language=language,
                available=True,
                passed=False,
                command="ast.parse",
                detail=f"Python AST parse failed: {exc}",
                stderr=str(exc),
            )

    if language == "sql":
        return run_sql_check(code)

    return CompileCheckResult(
        language=language,
        available=True,
        passed=None,
        command="built-in parser",
        detail="No built-in parser for this language in the app. External tool check may still run.",
    )


def run_sql_check(code: str) -> CompileCheckResult:
    normalized = code.strip()
    if not normalized:
        return CompileCheckResult(language="sql", available=True, passed=False, command="sqlite3", detail="SQL input is empty.")

    try:
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        # Best-effort: some dialect-specific SQL will still fail here.
        script = normalized
        if re.match(r"^select\b", normalized, flags=re.IGNORECASE):
            script = f"EXPLAIN QUERY PLAN {normalized.rstrip(';')};"
        cur.executescript(script)
        con.close()
        return CompileCheckResult(
            language="sql",
            available=True,
            passed=True,
            command="sqlite3 in-memory executescript",
            detail="Best-effort SQLite syntax check passed.",
        )
    except sqlite3.Error as exc:
        return CompileCheckResult(
            language="sql",
            available=True,
            passed=False,
            command="sqlite3 in-memory executescript",
            detail="Best-effort SQLite syntax check failed.",
            stderr=str(exc),
        )


def _command_for(language: str, file_path: Path, code: str, profile: str | None) -> list[str] | None:
    profile_key = normalize_profile(profile) if profile else None
    if language == "python":
        return [sys.executable, "-m", "py_compile", str(file_path)]
    if language == "javascript":
        return ["node", "--check", str(file_path)] if shutil.which("node") else None
    if language == "typescript":
        if not shutil.which("tsc"):
            return None
        if profile_key in {"reactjs", "nextjs"} or file_path.suffix == ".tsx":
            return ["tsc", "--noEmit", "--pretty", "false", "--jsx", "react-jsx", str(file_path)]
        return ["tsc", "--noEmit", "--pretty", "false", str(file_path)]
    if language == "java":
        return ["javac", str(file_path)] if shutil.which("javac") else None
    if language == "csharp":
        if shutil.which("csc"):
            target = "exe" if _has_csharp_main(code) else "library"
            return ["csc", "/nologo", f"/target:{target}", str(file_path)]
        if shutil.which("mcs"):
            target = "exe" if _has_csharp_main(code) else "library"
            return ["mcs", f"-target:{target}", str(file_path)]
        return None
    if language == "cpp":
        if shutil.which("g++"):
            return ["g++", "-std=c++17", "-fsyntax-only", str(file_path)]
        if shutil.which("clang++"):
            return ["clang++", "-std=c++17", "-fsyntax-only", str(file_path)]
        return None
    if language == "go":
        if shutil.which("go"):
            if _has_go_main(code):
                return ["go", "build", str(file_path)]
            return ["gofmt", "-e", str(file_path)] if shutil.which("gofmt") else ["go", "build", str(file_path)]
        return None
    if language == "rust":
        if shutil.which("rustc"):
            crate_type = "bin" if _has_rust_main(code) else "lib"
            return ["rustc", "--edition=2021", "--crate-type", crate_type, "--emit", "metadata", str(file_path)]
        return None
    if language == "php":
        return ["php", "-l", str(file_path)] if shutil.which("php") else None
    if language == "ruby":
        return ["ruby", "-wc", str(file_path)] if shutil.which("ruby") else None
    return None


def run_local_check(code: str, language: str, profile: str | None = None, timeout_seconds: int = 25) -> CompileCheckResult:
    language = normalize_language(language)
    profile_key = ensure_profile(profile, language)

    if profile_key == "vuejs":
        return CompileCheckResult(
            language=language,
            available=False,
            passed=None,
            command=None,
            detail="Vue single-file components need the Vue compiler or Vite toolchain for full validation. The app can still generate and inspect the code.",
        )

    if language == "sql":
        return run_sql_check(code)

    filename = choose_filename(code, language, profile_key)

    with tempfile.TemporaryDirectory(prefix=f"translate_{language}_") as tmpdir:
        tmp_path = Path(tmpdir) / filename
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(code, encoding="utf-8")

        if language == "python":
            syntax_result = quick_syntax_check(code, language)
            if syntax_result.passed is False:
                return syntax_result

        if profile_key in {"reactjs", "nextjs"} and not shutil.which("tsc"):
            return CompileCheckResult(
                language=language,
                available=False,
                passed=None,
                command=None,
                detail="TSX validation requires the TypeScript compiler (tsc). Install TypeScript locally to validate React or Next primary files.",
            )

        if profile_key in {"reactjs", "nextjs"} and not _contains_jsx(code):
            # allow plain TS code too
            pass

        command = _command_for(language, tmp_path, code, profile_key)
        if not command:
            return CompileCheckResult(
                language=language,
                available=False,
                passed=None,
                command=None,
                detail=(
                    f"No local {SUPPORTED_LANGUAGES[language].compile_label.lower()} was found on this machine. "
                    f"The app can still translate, but cannot verify this target locally."
                ),
            )

        try:
            process = subprocess.run(
                command,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = _truncate(process.stdout)
            stderr = _truncate(process.stderr)
            passed = process.returncode == 0
            detail = "Local verification passed." if passed else "Local verification failed."
            return CompileCheckResult(
                language=language,
                available=True,
                passed=passed,
                command=" ".join(command),
                detail=detail,
                stdout=stdout,
                stderr=stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return CompileCheckResult(
                language=language,
                available=True,
                passed=False,
                command=" ".join(command),
                detail="Local verification timed out.",
                stdout=_truncate(exc.stdout or ""),
                stderr=_truncate(exc.stderr or ""),
            )
        except Exception as exc:
            return CompileCheckResult(
                language=language,
                available=True,
                passed=False,
                command=" ".join(command),
                detail=f"Local verification crashed: {exc}",
                stderr=str(exc),
            )

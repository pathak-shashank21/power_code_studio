from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .schemas import ExecutionResult
from .utils import ensure_profile, normalize_language
from .validators import choose_filename


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


def _script_run_command(language: str, path: Path) -> list[str] | None:
    if language == "python":
        return [sys.executable, str(path)]
    if language == "javascript" and shutil.which("node"):
        return ["node", str(path)]
    if language == "php" and shutil.which("php"):
        return ["php", str(path)]
    if language == "ruby" and shutil.which("ruby"):
        return ["ruby", str(path)]
    return None


def run_local_execution(code: str, language: str, profile: str | None = None, timeout_seconds: int = 5) -> ExecutionResult:
    language = normalize_language(language)
    profile_key = ensure_profile(profile, language)

    if profile_key in {"expressjs", "nestjs", "nextjs", "reactjs", "vuejs", "laravel", "yii2", "dotnet-csharp"}:
        return ExecutionResult(
            language=language,
            attempted=True,
            available=False,
            passed=None,
            command=None,
            detail="Runtime smoke execution for framework targets is disabled in-app. Use project generation plus the framework toolchain to run them.",
        )

    filename = choose_filename(code, language, profile_key)

    with tempfile.TemporaryDirectory(prefix=f"translate_run_{language}_") as tmpdir:
        path = Path(tmpdir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")

        command = _script_run_command(language, path)
        if not command:
            return ExecutionResult(
                language=language,
                attempted=True,
                available=False,
                passed=None,
                command=None,
                detail=(
                    "Runtime smoke execution is only supported in-app for Python, JavaScript, PHP, and Ruby. "
                    "Other languages still get compile or syntax verification."
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
            return ExecutionResult(
                language=language,
                attempted=True,
                available=True,
                passed=process.returncode == 0,
                command=" ".join(command),
                detail="Runtime smoke execution passed." if process.returncode == 0 else "Runtime smoke execution failed.",
                stdout=_truncate(process.stdout),
                stderr=_truncate(process.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                language=language,
                attempted=True,
                available=True,
                passed=False,
                command=" ".join(command),
                detail="Runtime smoke execution timed out.",
                stdout=_truncate(exc.stdout or ""),
                stderr=_truncate(exc.stderr or ""),
            )
        except Exception as exc:
            return ExecutionResult(
                language=language,
                attempted=True,
                available=True,
                passed=False,
                command=" ".join(command),
                detail=f"Runtime smoke execution crashed: {exc}",
                stderr=str(exc),
            )

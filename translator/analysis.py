from __future__ import annotations

import difflib
import re
from collections import Counter

from .schemas import DependencyMap, ProjectAnalysisResponse, ProjectFileInsight
from .utils import detect_language_from_filename, detect_profile_from_filename, normalize_language

IMPORT_PATTERNS = {
    "javascript": [
        r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"])",
        r"(?:require\(['\"]([^'\"]+)['\"]\))",
    ],
    "typescript": [
        r"(?:import\s+.*?from\s+['\"]([^'\"]+)['\"])",
        r"(?:require\(['\"]([^'\"]+)['\"]\))",
    ],
    "python": [r"^\s*import\s+([\w\.]+)", r"^\s*from\s+([\w\.]+)\s+import\s+"],
    "java": [r"^\s*import\s+([\w\.\*]+);"],
    "csharp": [r"^\s*using\s+([\w\.]+);"],
    "go": [r'^\s*import\s+"([^"]+)"', r'^\s*\t"([^"]+)"'],
    "rust": [r"^\s*use\s+([\w:]+)"],
    "php": [r"require(?:_once)?\s*\(?\s*['\"]([^'\"]+)['\"]", r"use\s+([\w\\]+);"],
    "ruby": [r"^\s*require\s+['\"]([^'\"]+)['\"]", r"^\s*require_relative\s+['\"]([^'\"]+)['\"]"],
    "sql": [],
    "cpp": [r"^\s*#include\s*[<\"]([^>\"]+)[>\"]"],
}

FRAMEWORK_HINTS = {
    "expressjs": ["express"],
    "nestjs": ["@nestjs/core", "@nestjs/common"],
    "nextjs": ["next", "next/server", "next/navigation"],
    "reactjs": ["react", "react-dom"],
    "vuejs": ["vue", "pinia", "vue-router"],
    "laravel": ["illuminate", "laravel"],
    "yii2": ["yii", "yii2"],
    "dotnet-csharp": ["microsoft.aspnetcore", "system.", "aspnetcore"],
    "spring": ["org.springframework"],
}

MANIFEST_NAMES = {"package.json", "composer.json", "requirements.txt", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "*.csproj"}


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        cleaned = item.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def extract_dependencies(code: str, language: str) -> list[str]:
    language = normalize_language(language)
    if language == "sql":
        matches = re.findall(r"(?:from|join)\s+([A-Za-z_][\w.]+)", code, flags=re.IGNORECASE)
        return _unique(matches)
    patterns = IMPORT_PATTERNS.get(language, [])
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, code, flags=re.MULTILINE))
    return _unique(matches)


def detect_frameworks(dependencies: list[str], *, code: str = "") -> list[str]:
    lowered_deps = [dep.lower() for dep in dependencies]
    lowered_code = code.lower()
    hits: list[str] = []

    for framework, markers in FRAMEWORK_HINTS.items():
        if any(marker in lowered_code for marker in markers) or any(marker in dep for dep in lowered_deps for marker in markers):
            hits.append(framework)

    if "createapp" in lowered_code or "app/page.tsx" in lowered_code:
        hits.append("nextjs")
    if "router.get(" in lowered_code or "app.use(" in lowered_code:
        hits.append("expressjs")
    if "@controller" in lowered_code or "@module" in lowered_code:
        hits.append("nestjs")
    if "<template>" in lowered_code and "<script" in lowered_code:
        hits.append("vuejs")
    if "useeffect(" in lowered_code or "usestate(" in lowered_code:
        hits.append("reactjs")

    return _unique(hits)


PACKAGE_DEP_PATTERNS = [
    ("package.json", r'"dependencies"\s*:\s*\{([^}]*)\}', r'"([^"]+)"\s*:'),
    ("package.json", r'"devDependencies"\s*:\s*\{([^}]*)\}', r'"([^"]+)"\s*:'),
    ("composer.json", r'"require"\s*:\s*\{([^}]*)\}', r'"([^"]+)"\s*:'),
    ("requirements.txt", None, r'^\s*([A-Za-z0-9_.\-]+)'),
    ("go.mod", None, r'^\s*require\s+([A-Za-z0-9_./\-]+)'),
    ("Cargo.toml", r'\[dependencies\]([\s\S]*?)(?:\n\[|$)', r'^\s*([A-Za-z0-9_\-]+)\s*='),
]


def extract_manifest_dependencies(path: str, content: str) -> list[str]:
    lowered = path.lower().split("/")[-1]
    deps: list[str] = []
    for manifest_name, section_pattern, item_pattern in PACKAGE_DEP_PATTERNS:
        if lowered != manifest_name:
            continue
        if section_pattern:
            for section in re.findall(section_pattern, content, flags=re.MULTILINE):
                deps.extend(re.findall(item_pattern, section, flags=re.MULTILINE))
        else:
            deps.extend(re.findall(item_pattern, content, flags=re.MULTILINE))
    return _unique(deps)


def build_dependency_map(source_code: str, source_language: str, translated_code: str, target_language: str) -> DependencyMap:
    source_imports = extract_dependencies(source_code, source_language)
    target_imports = extract_dependencies(translated_code, target_language)
    frameworks = detect_frameworks(source_imports + target_imports, code=source_code + "\n" + translated_code)

    notes: list[str] = []
    if source_imports and not target_imports:
        notes.append("The source imports dependencies that do not appear clearly in the target output. Verify library equivalents.")
    if frameworks:
        notes.append(f"Detected framework hints: {', '.join(frameworks)}.")
    if target_language == "sql":
        notes.append("Confirm SQL dialect assumptions, schema names, functions, CTE support, and transaction semantics.")

    return DependencyMap(
        source_imports=source_imports,
        target_imports=target_imports,
        detected_frameworks=frameworks,
        notes=notes,
    )


def build_diff_text(source_code: str, translated_code: str, source_language: str, target_language: str) -> str:
    diff = difflib.unified_diff(
        source_code.splitlines(),
        translated_code.splitlines(),
        fromfile=f"source.{normalize_language(source_language)}",
        tofile=f"translated.{normalize_language(target_language)}",
        lineterm="",
    )
    return "\n".join(diff)


def language_pair_notes(source_language: str, target_language: str) -> list[str]:
    source_language = normalize_language(source_language)
    target_language = normalize_language(target_language)
    notes: list[str] = []

    pair = (source_language, target_language)
    if pair in {
        ("javascript", "python"),
        ("typescript", "python"),
        ("python", "javascript"),
        ("python", "typescript"),
    }:
        notes.append("Pay close attention to async behavior, iterable semantics, and standard library equivalents.")
    if target_language == "java":
        notes.append("Ensure the output is wrapped in compilable classes and uses explicit types where required.")
    if target_language == "go":
        notes.append("Prefer package main and a main function for runnable snippets.")
    if target_language == "rust":
        notes.append("Use ownership-safe patterns and avoid placeholder unwrap chains unless justified.")
    if target_language == "cpp":
        notes.append("Include all necessary headers and prefer standard C++17 containers and algorithms.")
    if target_language == "sql":
        notes.append("Document SQL dialect assumptions and ensure table, column, and function names match the intended database.")
    if source_language in {"javascript", "typescript"} and target_language in {"java", "csharp", "cpp", "go", "rust"}:
        notes.append("Dynamic typing from the source must be resolved into explicit target-language types.")

    return notes


def analyze_project_files(files: list[tuple[str, str]]) -> ProjectAnalysisResponse:
    language_counts: Counter[str] = Counter()
    profile_counts: Counter[str] = Counter()
    all_frameworks: list[str] = []
    all_dependencies: list[str] = []
    setup_hints: list[str] = []
    risks: list[str] = []
    file_insights: list[ProjectFileInsight] = []

    for path, content in files:
        language = detect_language_from_filename(path)
        profile = detect_profile_from_filename(path)
        dependencies = extract_manifest_dependencies(path, content)

        if language and not dependencies:
            dependencies = extract_dependencies(content, language)

        frameworks = detect_frameworks(dependencies, code=content)
        notes: list[str] = []
        lowered = path.lower()

        if language:
            language_counts[language] += 1
        if profile:
            profile_counts[profile] += 1
        for item in frameworks:
            all_frameworks.append(item)
        for item in dependencies:
            all_dependencies.append(item)

        if lowered.endswith("package.json"):
            setup_hints.append("Run npm install or pnpm install after extracting the generated project.")
        if lowered.endswith("composer.json"):
            setup_hints.append("Run composer install for PHP framework dependencies.")
        if lowered.endswith("requirements.txt") or lowered.endswith("pyproject.toml"):
            setup_hints.append("Create a virtual environment and install Python dependencies before running checks.")
        if lowered.endswith("go.mod"):
            setup_hints.append("Run go mod tidy to synchronize module requirements.")
        if lowered.endswith("cargo.toml"):
            setup_hints.append("Run cargo check or cargo build for full Rust validation.")
        if lowered.endswith(".csproj"):
            setup_hints.append("Use dotnet restore and dotnet build for .NET validation.")
        if lowered.endswith("pom.xml") or lowered.endswith("build.gradle"):
            setup_hints.append("Run the Java build toolchain, such as mvn test or gradle build.")

        if language == "sql" and "drop table" in content.lower():
            risks.append(f"{path} contains destructive SQL operations. Review migration intent and backup strategy.")
        if any(name in lowered for name in [".env", "secret", "token"]):
            risks.append(f"{path} looks security-sensitive. Do not commit secrets or credentials.")
        if "todo" in content.lower():
            notes.append("Contains TODO markers that may indicate incomplete implementation.")
        if frameworks and not profile:
            notes.append("Framework-specific imports were detected, but the filename alone did not reveal a profile.")
        if lowered.endswith("app/page.tsx"):
            profile = profile or "nextjs"
            profile_counts[profile] += 1
        if lowered.endswith("src/app.vue"):
            profile = profile or "vuejs"
            profile_counts[profile] += 1

        file_insights.append(
            ProjectFileInsight(
                path=path,
                language=language,
                profile=profile,
                frameworks=frameworks,
                dependencies=dependencies,
                notes=notes,
            )
        )

    frameworks_unique = _unique(all_frameworks)
    dependencies_unique = _unique(all_dependencies)
    setup_hints = _unique(setup_hints)
    risks = _unique(risks)

    suggested_profiles: list[str] = []
    if any(item in frameworks_unique for item in ["nextjs", "reactjs"]):
        suggested_profiles.extend(["nextjs", "reactjs"])
    if any(item in frameworks_unique for item in ["expressjs", "nestjs"]):
        suggested_profiles.extend(["expressjs", "nestjs", "nodejs"])
    if any(item in frameworks_unique for item in ["laravel", "yii2"]):
        suggested_profiles.extend(["laravel", "yii2", "php"])
    if "dotnet-csharp" in frameworks_unique:
        suggested_profiles.append("dotnet-csharp")
    if language_counts.get("java"):
        suggested_profiles.append("java")
    if language_counts.get("sql"):
        suggested_profiles.append("sql")
    if not suggested_profiles:
        for profile, _count in profile_counts.most_common(3):
            suggested_profiles.append(profile)

    architecture_parts: list[str] = []
    if frameworks_unique:
        architecture_parts.append(f"Detected framework family: {', '.join(frameworks_unique)}.")
    if dependencies_unique:
        architecture_parts.append(f"Detected {len(dependencies_unique)} notable dependencies or imports.")
    if language_counts:
        architecture_parts.append(
            "Language mix: " + ", ".join(f"{lang}={count}" for lang, count in language_counts.most_common()) + "."
        )
    if not architecture_parts:
        architecture_parts.append("The uploaded files look like a lightweight code sample rather than a fully structured project.")

    return ProjectAnalysisResponse(
        total_files=len(files),
        language_counts=dict(language_counts),
        profile_counts=dict(profile_counts),
        frameworks=frameworks_unique,
        dependencies=dependencies_unique,
        suggested_profiles=_unique(suggested_profiles),
        setup_hints=setup_hints,
        risks=risks,
        architecture_summary=" ".join(architecture_parts),
        file_insights=file_insights,
    )

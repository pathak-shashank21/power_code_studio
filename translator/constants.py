from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSpec:
    key: str
    label: str
    extension: str
    compile_label: str
    execution_hint: str
    target_notes: str
    editor_mode: str


@dataclass(frozen=True)
class ProfileSpec:
    key: str
    label: str
    base_language: str
    default_filename: str
    translation_notes: str
    generation_notes: str
    validation_scope: str
    output_kind: str = "single_file"
    editor_mode: str | None = None


SUPPORTED_LANGUAGES: dict[str, LanguageSpec] = {
    "typescript": LanguageSpec(
        key="typescript",
        label="TypeScript",
        extension=".ts",
        compile_label="TypeScript compiler",
        execution_hint="tsc --noEmit file.ts",
        target_notes="Write clean TypeScript with explicit types where it improves correctness.",
        editor_mode="typescript",
    ),
    "python": LanguageSpec(
        key="python",
        label="Python",
        extension=".py",
        compile_label="Python compiler",
        execution_hint="python -m py_compile file.py",
        target_notes="Write idiomatic Python 3.11+ and prefer the standard library unless a dependency is necessary.",
        editor_mode="python",
    ),
    "javascript": LanguageSpec(
        key="javascript",
        label="JavaScript",
        extension=".js",
        compile_label="Node syntax check",
        execution_hint="node --check file.js",
        target_notes="Write modern JavaScript that runs in Node.js 18+ unless the profile says browser or framework code.",
        editor_mode="javascript",
    ),
    "java": LanguageSpec(
        key="java",
        label="Java",
        extension=".java",
        compile_label="javac",
        execution_hint="javac Main.java",
        target_notes="Produce compilable Java 17+ single-file code or clearly scoped class files.",
        editor_mode="java",
    ),
    "csharp": LanguageSpec(
        key="csharp",
        label="C#",
        extension=".cs",
        compile_label="C# compiler",
        execution_hint="csc Program.cs",
        target_notes="Write modern C# with clear namespaces, null-safety where relevant, and a compilable entry point when runnable.",
        editor_mode="csharp",
    ),
    "cpp": LanguageSpec(
        key="cpp",
        label="C++",
        extension=".cpp",
        compile_label="C++ syntax check",
        execution_hint="g++ -std=c++17 -fsyntax-only file.cpp",
        target_notes="Produce standard C++17 single-file code with required includes.",
        editor_mode="c_cpp",
    ),
    "go": LanguageSpec(
        key="go",
        label="Go",
        extension=".go",
        compile_label="Go build/syntax check",
        execution_hint="go build file.go",
        target_notes="Write coherent Go code with explicit packages and a main package for runnable snippets.",
        editor_mode="golang",
    ),
    "rust": LanguageSpec(
        key="rust",
        label="Rust",
        extension=".rs",
        compile_label="rustc",
        execution_hint="rustc --emit metadata file.rs",
        target_notes="Produce valid Rust 2021 code that respects ownership and type safety.",
        editor_mode="rust",
    ),
    "php": LanguageSpec(
        key="php",
        label="PHP",
        extension=".php",
        compile_label="PHP linter",
        execution_hint="php -l file.php",
        target_notes="Produce PHP 8+ code with clear classes, namespaces, and framework conventions where relevant.",
        editor_mode="php",
    ),
    "ruby": LanguageSpec(
        key="ruby",
        label="Ruby",
        extension=".rb",
        compile_label="Ruby syntax check",
        execution_hint="ruby -wc file.rb",
        target_notes="Produce idiomatic Ruby and standard library code where possible.",
        editor_mode="ruby",
    ),
    "sql": LanguageSpec(
        key="sql",
        label="SQL",
        extension=".sql",
        compile_label="SQL parser",
        execution_hint="best-effort SQLite syntax check",
        target_notes="Generate executable SQL with comments for dialect-specific assumptions.",
        editor_mode="sql",
    ),
}


SUPPORTED_PROFILES: dict[str, ProfileSpec] = {
    "python": ProfileSpec(
        key="python",
        label="Python",
        base_language="python",
        default_filename="main.py",
        translation_notes="Translate to plain Python unless a framework is explicitly required.",
        generation_notes="Prefer a runnable single-file or clean multi-file Python structure with requirements clearly stated.",
        validation_scope="py_compile",
    ),
    "javascript": ProfileSpec(
        key="javascript",
        label="JavaScript",
        base_language="javascript",
        default_filename="main.js",
        translation_notes="Translate to plain JavaScript suitable for Node unless browser APIs are explicitly required.",
        generation_notes="Prefer a clear entry file and package.json when dependencies are needed.",
        validation_scope="node --check",
    ),
    "typescript": ProfileSpec(
        key="typescript",
        label="TypeScript",
        base_language="typescript",
        default_filename="main.ts",
        translation_notes="Translate to plain TypeScript and keep types explicit where it improves correctness.",
        generation_notes="Prefer a clean tsconfig-ready structure and explicit interfaces.",
        validation_scope="tsc --noEmit",
    ),
    "nodejs": ProfileSpec(
        key="nodejs",
        label="Node.js",
        base_language="javascript",
        default_filename="index.js",
        translation_notes="Target a Node.js app or module. Use built-in Node APIs when possible and document required packages.",
        generation_notes="Produce a Node-oriented project with package.json, entry file, and environment variable guidance.",
        validation_scope="node --check for JS files",
        output_kind="project",
    ),
    "expressjs": ProfileSpec(
        key="expressjs",
        label="Node + Express.js",
        base_language="javascript",
        default_filename="src/server.js",
        translation_notes="Target an Express HTTP API or server. Keep routing, middleware, validation, and config explicit.",
        generation_notes="Return a small Express project with package.json, server/app file, routes, and environment notes.",
        validation_scope="node --check for JS files",
        output_kind="project",
    ),
    "nestjs": ProfileSpec(
        key="nestjs",
        label="NestJS",
        base_language="typescript",
        default_filename="src/app.controller.ts",
        translation_notes="Target NestJS modules, controllers, services, DTOs, and provider structure.",
        generation_notes="Return a compact NestJS project layout with module, controller, service, DTO, and bootstrap files.",
        validation_scope="tsc --noEmit for .ts files",
        output_kind="project",
    ),
    "nextjs": ProfileSpec(
        key="nextjs",
        label="Next.js",
        base_language="typescript",
        default_filename="app/page.tsx",
        translation_notes="Target modern Next.js App Router patterns unless the request clearly needs Pages Router.",
        generation_notes="Return a small Next.js project with app router files, components, and package.json. Prefer TSX.",
        validation_scope="best-effort TSX syntax check; full build requires Next toolchain",
        output_kind="project",
        editor_mode="typescript",
    ),
    "reactjs": ProfileSpec(
        key="reactjs",
        label="React.js",
        base_language="typescript",
        default_filename="src/App.tsx",
        translation_notes="Target React components, hooks, state, and props with TSX by default.",
        generation_notes="Return a compact React project with App.tsx, supporting components, and package.json.",
        validation_scope="best-effort TSX syntax check; full build requires React toolchain",
        output_kind="project",
        editor_mode="typescript",
    ),
    "vuejs": ProfileSpec(
        key="vuejs",
        label="Vue.js",
        base_language="typescript",
        default_filename="src/App.vue",
        translation_notes="Target Vue 3 composition API patterns unless the request clearly needs options API.",
        generation_notes="Return a small Vue project with App.vue, components, and package.json. Prefer script setup lang=ts.",
        validation_scope="best-effort only; full .vue validation requires Vue tooling",
        output_kind="project",
        editor_mode="html",
    ),
    "php": ProfileSpec(
        key="php",
        label="PHP",
        base_language="php",
        default_filename="index.php",
        translation_notes="Target plain PHP unless a framework is explicitly requested.",
        generation_notes="Generate PHP 8+ code with clear file structure and dependencies.",
        validation_scope="php -l",
    ),
    "laravel": ProfileSpec(
        key="laravel",
        label="PHP Laravel",
        base_language="php",
        default_filename="routes/web.php",
        translation_notes="Target Laravel controllers, routes, models, migrations, requests, and services as needed.",
        generation_notes="Return a Laravel-friendly project slice with routes, controllers, models, migrations, and config notes.",
        validation_scope="php -l for PHP files; full framework validation requires Laravel app context",
        output_kind="project",
    ),
    "yii2": ProfileSpec(
        key="yii2",
        label="PHP Yii2",
        base_language="php",
        default_filename="controllers/SiteController.php",
        translation_notes="Target Yii2 controllers, models, views, and config conventions.",
        generation_notes="Return a Yii2-friendly project slice with controller, model, view, and config guidance.",
        validation_scope="php -l for PHP files; full framework validation requires Yii2 app context",
        output_kind="project",
    ),
    "dotnet-csharp": ProfileSpec(
        key="dotnet-csharp",
        label=".NET C#",
        base_language="csharp",
        default_filename="Program.cs",
        translation_notes="Target ASP.NET Core or .NET worker/service style code depending on the request. Use minimal APIs when suitable.",
        generation_notes="Return a compact .NET project with Program.cs, controllers/services/models if needed, and csproj guidance.",
        validation_scope="csc or mcs best-effort syntax check for .cs files",
        output_kind="project",
    ),
    "java": ProfileSpec(
        key="java",
        label="Java",
        base_language="java",
        default_filename="Main.java",
        translation_notes="Target plain Java unless framework behavior is explicitly requested.",
        generation_notes="Return Java 17+ code with clear class structure and package guidance.",
        validation_scope="javac",
    ),
    "sql": ProfileSpec(
        key="sql",
        label="SQL",
        base_language="sql",
        default_filename="query.sql",
        translation_notes="Target standard SQL and call out dialect assumptions such as PostgreSQL, MySQL, SQL Server, or SQLite.",
        generation_notes="Generate runnable SQL files with schema, views, queries, or migrations depending on the request.",
        validation_scope="best-effort SQLite syntax check",
    ),
    "go": ProfileSpec(
        key="go",
        label="Go",
        base_language="go",
        default_filename="main.go",
        translation_notes="Translate to plain Go unless a framework is explicitly required.",
        generation_notes="Prefer a coherent Go module structure with package main for runnable apps.",
        validation_scope="go build",
    ),
    "rust": ProfileSpec(
        key="rust",
        label="Rust",
        base_language="rust",
        default_filename="main.rs",
        translation_notes="Translate to Rust with explicit ownership-safe patterns.",
        generation_notes="Prefer a compact Cargo-style layout and clear dependency notes.",
        validation_scope="rustc --emit metadata",
    ),
    "cpp": ProfileSpec(
        key="cpp",
        label="C++",
        base_language="cpp",
        default_filename="main.cpp",
        translation_notes="Translate to standard C++17 code.",
        generation_notes="Prefer a single-file or compact header/source layout.",
        validation_scope="g++ -fsyntax-only",
    ),
    "ruby": ProfileSpec(
        key="ruby",
        label="Ruby",
        base_language="ruby",
        default_filename="main.rb",
        translation_notes="Translate to plain Ruby unless framework behavior is explicit.",
        generation_notes="Return clean Ruby code and include Gem setup notes when needed.",
        validation_scope="ruby -wc",
    ),
}


DEFAULT_LANGUAGE_ORDER: list[str] = [
    "typescript",
    "python",
    "javascript",
    "java",
    "csharp",
    "cpp",
    "go",
    "rust",
    "php",
    "ruby",
    "sql",
]

DEFAULT_PROFILE_ORDER: list[str] = [
    "python",
    "javascript",
    "typescript",
    "nodejs",
    "expressjs",
    "nestjs",
    "nextjs",
    "reactjs",
    "vuejs",
    "php",
    "laravel",
    "yii2",
    "dotnet-csharp",
    "java",
    "sql",
    "go",
    "rust",
    "cpp",
    "ruby",
]

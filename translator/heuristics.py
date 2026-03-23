from __future__ import annotations

import ast
import re

from .schemas import TranslationEnvelope


def translate_same_language(source_code: str) -> TranslationEnvelope:
    return TranslationEnvelope(
        translated_code=source_code.strip(),
        explanation="Source and target languages are the same, so the code was returned unchanged.",
        warnings=[],
        assumptions=[],
    )


def translate_javascript_to_python(source_code: str) -> TranslationEnvelope:
    code = source_code

    code = code.replace("console.log", "print")
    code = re.sub(r"\b(let|const|var)\s+", "", code)
    code = re.sub(r"===", "==", code)
    code = re.sub(r"!==", "!=", code)
    code = re.sub(r"&&", "and", code)
    code = re.sub(r"\|\|", "or", code)
    code = code.replace("true", "True").replace("false", "False").replace("null", "None")
    code = re.sub(r"function\s+(\w+)\s*\((.*?)\)\s*\{", r"def \1(\2):", code)

    arrow_block = re.compile(r"(\w+)\s*=\s*\((.*?)\)\s*=>\s*\{\s*return\s+(.*?);\s*\}", re.DOTALL)
    code = arrow_block.sub(r"def \1(\2):\n    return \3", code)

    arrow_inline = re.compile(r"(\w+)\s*=\s*\((.*?)\)\s*=>\s*(.*?);")
    code = arrow_inline.sub(r"def \1(\2):\n    return \3", code)

    lines: list[str] = []
    indent = 0
    for raw_line in code.splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue

        closing_braces = line.count("}")
        if closing_braces:
            indent = max(0, indent - closing_braces)

        line = line.replace("{", "").replace("}", "").strip().rstrip(";")
        if not line:
            continue

        if line.startswith("else if "):
            condition = line[len("else if "):].strip()
            line = f"elif {condition}:"
        elif line == "else":
            line = "else:"
        elif line.startswith("if ") and not line.endswith(":"):
            line = f"if {line[3:].strip()}:"
        elif line.startswith("for ") and " in " not in line and not line.endswith(":"):
            line = "# Review loop manually: " + line
        elif line.startswith("while ") and not line.endswith(":"):
            line = f"while {line[6:].strip()}:"

        line = re.sub(r"^elif\s*\((.*)\):$", r"elif \1:", line)
        line = re.sub(r"^if\s*\((.*)\):$", r"if \1:", line)
        line = re.sub(r"^while\s*\((.*)\):$", r"while \1:", line)

        lines.append(("    " * indent) + line)
        indent += raw_line.count("{")

    translated = "\n".join(lines).strip()
    translated = re.sub(r"\n{3,}", "\n\n", translated)

    warnings = [
        "Heuristic mode is intentionally limited. Complex async code, classes, frameworks, and library-specific behavior may need review."
    ]

    try:
        ast.parse(translated)
    except SyntaxError as exc:
        warnings.append(f"Heuristic output may need manual fixes: {exc}")

    return TranslationEnvelope(
        translated_code=translated,
        explanation="Converted with a lightweight heuristic path for JavaScript → Python.",
        warnings=warnings,
        assumptions=["Standard syntax-only translation without framework awareness."],
    )


def translate_python_to_javascript(source_code: str) -> TranslationEnvelope:
    code = source_code
    code = re.sub(r"^def\s+(\w+)\((.*?)\):", r"function \1(\2) {", code, flags=re.MULTILINE)
    code = code.replace("True", "true").replace("False", "false").replace("None", "null")
    code = re.sub(r"\bprint\(", "console.log(", code)

    lines: list[str] = []
    indent_stack = [0]

    for raw in code.splitlines():
        if not raw.strip():
            lines.append("")
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()

        while indent < indent_stack[-1]:
            indent_stack.pop()
            lines.append(" " * indent_stack[-1] + "}")

        if line.startswith("if ") and line.endswith(":"):
            line = f"if ({line[3:-1]}) {{"
            indent_stack.append(indent + 4)
        elif line.startswith("elif ") and line.endswith(":"):
            while len(indent_stack) > 1 and indent < indent_stack[-1]:
                indent_stack.pop()
                lines.append(" " * indent_stack[-1] + "}")
            line = f"else if ({line[5:-1]}) {{"
            indent_stack.append(indent + 4)
        elif line == "else:":
            while len(indent_stack) > 1 and indent < indent_stack[-1]:
                indent_stack.pop()
                lines.append(" " * indent_stack[-1] + "}")
            line = "else {"
            indent_stack.append(indent + 4)
        elif line.startswith("while ") and line.endswith(":"):
            line = f"while ({line[6:-1]}) {{"
            indent_stack.append(indent + 4)
        elif line.startswith("return "):
            line = line + ";"
        elif line.startswith("#"):
            line = "// " + line[1:].strip()
        elif line.startswith("function ") and line.endswith("{"):
            indent_stack.append(indent + 4)
        else:
            if not line.endswith((";", "{", "}")):
                line = line + ";"

        lines.append(" " * indent + line)

    while len(indent_stack) > 1:
        indent_stack.pop()
        lines.append(" " * indent_stack[-1] + "}")

    translated = "\n".join(lines).strip()
    return TranslationEnvelope(
        translated_code=translated,
        explanation="Converted with a lightweight heuristic path for Python → JavaScript.",
        warnings=[
            "Heuristic mode is intentionally limited. Indentation-heavy logic, comprehensions, classes, and async behavior may need manual review."
        ],
        assumptions=["Node-style JavaScript output without framework mappings."],
    )


def heuristic_translate(source_code: str, source_language: str, target_language: str) -> TranslationEnvelope:
    if source_language == target_language:
        return translate_same_language(source_code)
    if source_language == "javascript" and target_language == "python":
        return translate_javascript_to_python(source_code)
    if source_language == "python" and target_language == "javascript":
        return translate_python_to_javascript(source_code)

    return TranslationEnvelope(
        translated_code=source_code.strip(),
        explanation="No heuristic path exists for this pair, so the source code was returned unchanged.",
        warnings=[
            "Use the Ollama provider for real cross-language translation. Heuristic mode only supports same-language passthrough, JavaScript → Python, and Python → JavaScript."
        ],
        assumptions=[],
    )

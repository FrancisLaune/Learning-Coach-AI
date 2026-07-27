"""Audit literal user-facing Streamlit strings for residual English terms."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = ("ui", "app.py")
VISIBLE_METHODS = {
    "title",
    "header",
    "subheader",
    "markdown",
    "write",
    "info",
    "warning",
    "error",
    "success",
    "caption",
    "metric",
    "button",
    "selectbox",
    "multiselect",
    "radio",
    "checkbox",
    "text_input",
    "number_input",
    "tabs",
}
ENGLISH_TERMS = {
    "next",
    "previous",
    "submit",
    "cancel",
    "approve",
    "reject",
    "practice",
    "assessment",
    "skill",
    "subject",
    "grade",
    "difficulty",
    "progress",
    "dashboard",
    "recommendation",
    "loading",
    "error",
    "success",
    "warning",
    "approved",
    "draft",
    "review",
    "homework",
    "student",
}
ALLOWLIST = {
    "Learning Coach AI",
    "P1",
    "P2",
    "P3",
    "P4",
    "P5",
    "Tier 1",
    "Tier 2",
    "Tier 3",
}


def visible_literals(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    output: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in VISIBLE_METHODS:
            continue
        values: list[str] = []
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                values.append(argument.value)
            elif isinstance(argument, ast.JoinedStr):
                values.append(
                    "".join(
                        str(part.value)
                        for part in argument.values
                        if isinstance(part, ast.Constant) and isinstance(part.value, str)
                    )
                )
            elif isinstance(argument, (ast.List, ast.Tuple)):
                values.extend(
                    str(item.value)
                    for item in argument.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                )
        for value in values:
            matches = sorted(
                term for term in ENGLISH_TERMS if re.search(rf"\b{re.escape(term)}\b", value, flags=re.IGNORECASE)
            )
            justified = any(token in value for token in ALLOWLIST)
            output.append(
                {
                    "file": path.relative_to(ROOT).as_posix(),
                    "line": node.lineno,
                    "text": value,
                    "english_terms": matches,
                    "justified": justified,
                }
            )
    return output


def run(paths: tuple[str, ...] = DEFAULT_PATHS) -> dict[str, Any]:
    files: list[Path] = []
    for raw in paths:
        path = ROOT / raw
        files.extend(path.rglob("*.py") if path.is_dir() else [path])
    strings = [item for path in sorted(set(files)) for item in visible_literals(path)]
    residual = [item for item in strings if item["english_terms"] and not item["justified"]]
    return {
        "files_analyzed": len(set(files)),
        "visible_strings_analyzed": len(strings),
        "residual_english_occurrences": len(residual),
        "justified_exceptions": sum(bool(item["english_terms"]) and bool(item["justified"]) for item in strings),
        "residual": residual,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result)
    raise SystemExit(1 if result["residual_english_occurrences"] else 0)


if __name__ == "__main__":
    main()

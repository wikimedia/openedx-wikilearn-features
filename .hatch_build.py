from __future__ import annotations

from pathlib import Path
from typing import Dict, List

try:
    from hatchling.builders.hooks.plugin.interface import BuildHookInterface
except ImportError:  # pragma: no cover - hatchling not required at runtime
    # Provide a minimal stub so importing this module outside hatch doesn't fail.
    class BuildHookInterface:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def initialize(self, version, build_data):
            pass


REQUIREMENTS_FILE = Path("requirements") / "base.in"


def _parse_requirements_lines(lines: List[str]) -> List[str]:
    """Return install requirements from requirement lines.

    - Strips comments and blank lines
    - Skips constraint/include directives like '-c' / '--constraint' / '-r' / '--requirement'
    - Leaves environment markers and version specifiers intact
    """
    requirements: List[str] = []
    skip_prefixes = ("-c ", "--constraint ", "-r ", "--requirement ")

    def strip_inline_comment(text: str) -> str:
        in_single = False
        in_double = False
        for idx, ch in enumerate(text):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                return text[:idx]
        return text

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if any(line.startswith(prefix) for prefix in skip_prefixes):
            continue
        line_wo_comments = strip_inline_comment(line).strip()
        if not line_wo_comments:
            continue
        requirements.append(line_wo_comments)
    return requirements


class RequirementsBuildHook(BuildHookInterface):
    """Hatch build hook that injects dependencies from requirements/base.in."""

    def initialize(self, _version: str, build_data: Dict) -> None:  # type: ignore[override]
        if not REQUIREMENTS_FILE.exists():
            return
        lines = REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
        deps = _parse_requirements_lines(lines)

        # Hatch expects dynamic deps under 'metadata' or directly in build_data depending on context.
        # We set both to be safe across hatch versions.
        build_data.setdefault("metadata", {})
        build_data["metadata"]["dependencies"] = deps
        build_data["dependencies"] = deps



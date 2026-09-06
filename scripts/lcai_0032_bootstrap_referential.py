"""CLI — LCAI-0032 bootstrap referential."""

from __future__ import annotations

import json
from pathlib import Path

from services.brevet_referential.bootstrap import bootstrap_referential


def main() -> None:
    result = bootstrap_referential()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out = Path("docs/phase6/LCAI-0032/_bootstrap_result.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

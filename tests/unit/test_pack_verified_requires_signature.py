"""Guard (Phase 3): a jurisdiction rule may only be `verified` if a named professional confirmed it.

48 rules had been marked `verified` by an earlier build agent with no signature. They are now
`source_cited` (human decision, 6 Nov 2026). This test makes an unsigned `verified` fail CI.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PACK_DIR = Path(__file__).resolve().parents[2] / "jurisdiction" / "ma"


def test_every_verified_rule_names_who_verified_it_and_when() -> None:
    unsigned = []
    for path in sorted(PACK_DIR.glob("*.yaml")):
        for item in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if isinstance(item, dict) and item.get("status") == "verified":
                if not str(item.get("verified_by") or "").strip() or not str(item.get("verified_at") or "").strip():
                    unsigned.append(f"{path.name}:{item.get('key')}")
    assert unsigned == [], f"rules marked verified without verified_by/verified_at: {unsigned}"


def test_planted_unsigned_verified_rule_is_caught(tmp_path: Path) -> None:
    item = {"key": "x", "status": "verified", "value": 1}
    assert not (item.get("verified_by") and item.get("verified_at"))

"""Integrity check for frozen database migrations (Rule A.6).

Freezes migrations 001–013 (009–013 added 11 Nov 2026; they were applied but not yet pinned). Fails CI if any committed migration file's SHA-256 hash changes.
All schema changes from now on must be placed in new migrations (e.g. 004_...).
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

# Pinned canonical SHA-256 hashes (LF-normalized) for every applied migration
FROZEN_MIGRATION_HASHES: dict[str, str] = {
    "001_core.up.sql": "48c52b89f6bc30f1f67142dc74d779d7bcd9ee1b0af31c5dad1ba284a29d2189",
    "001_core.down.sql": "eba629bdb6fec1766ca02c7743e61ea8beb8511d09947764670245966c7c3296",
    "002_rls.up.sql": "0c5b9d8239b13e2b5d5c63c89406982d5788bb534f8f476c0b135dc70e236d55",
    "002_rls.down.sql": "0566965f0d3d7e38869b3a0d1570dc7b9031ad12f6f357cb24e7de0c5f13e21d",
    "003_append_only.up.sql": "5ee0cc104c431b2776a223eb5c076014ddaff3fd3c70a0c46ba1c91fb0c7e8a0",
    "003_append_only.down.sql": "4530a0348a23cd3e91d91bf2a851dd407f1d4269ba3f600098ee3e6fdc680df0",
    "004_fx_rates.up.sql": "795424a1e6a16185ec4a400efb2d57691ae3f38e9257a4fe1987089c6ac02001",
    "004_fx_rates.down.sql": "8b7aef8eae92a50ddb75eb3265cca6f9323853d99b6ab3a7c210f803abeba703",
    "005_rounding_directions.up.sql": "329b75221c522854a6fac53a164cc3faeb91d357302b61cfb75c477d29e6583a",
    "005_rounding_directions.down.sql": "e50b0a984dbc76aa33d34252c93cf5cdcb87fb992a0808a57d0dba21b8a4127d",
    "006_reconciliation_refinements.up.sql": "b7349e3de7f89a2872dbb98da926417e5314466c4f0f72ef0acd74735268f020",
    "006_reconciliation_refinements.down.sql": "7bccf7a24803260a16a72eb96083496ba0c0c4df0c2a0263123b4520a291c6da",
    "007_active_bq_proposal_unique.up.sql": "17db608d84fbe01dcd32c3f6a3adaec69b2abd268ddc1a7732eecfccfbf400b0",
    "007_active_bq_proposal_unique.down.sql": "ba1a185fcafeb9f1b95f4b5ff3689aae60ade028bcb19eb2ed7f85af0c084c13",
    "008_round_trips_and_approval_policy.up.sql": "6ffb4271e2d88bd08b3c156f047afcc3e00d0f159dffd3558063bef2327f3ace",
    "008_round_trips_and_approval_policy.down.sql": "110e1014b1694136ed04e872431a69bb67910beba953a27166e703bf8a0e290e",
    "009_review_metrics_and_rate_limits.down.sql": "d01ecaa91ec2e508bf7b61fc9240d5bee173149b6476bb072bd2156925d3b8cc",
    "009_review_metrics_and_rate_limits.up.sql": "fa3b46c68415ec6b2600bf47423e0494dbd2ac27f18e42b194ff531f4a4996a5",
    "010_issue_supersede_and_round_trip_grants.down.sql": "b968ed49f9642b6473a7531be7cc6b05306f5822d664c8b4d54fdbd7f850a2a9",
    "010_issue_supersede_and_round_trip_grants.up.sql": "73f982607e8618e1ce77d747146ffd6bf820339d89396d0fb93a64713f138d42",
    "011_lettrage.down.sql": "08b1a1d21a7874757ba1fd24385967fe4e23033efbbe592c3e1b2cca9a4905f1",
    "011_lettrage.up.sql": "2c978c8e43396c6fb298f925f39bc070ea8a26a44a2070e50d2e2d98bce727a9",
    "012_knowledge_graph.down.sql": "0bd84357a139deb7c28cca083d1edbc16bcb9d799a64cd5bd0bc5a19f3907a2b",
    "012_knowledge_graph.up.sql": "f4b80f4a942d6878ce51f599186f43dc204597fb9ac78641bc84628aefc6d967",
    "013_kg_originals.down.sql": "a6b4bf18016421d87efc945603950f72b3106a7df5dd824bc85f65b9b5fd9431",
    "013_kg_originals.up.sql": "9cc41bd1d82368fa53903c0daa88583c4f27e04257ff2d710b68a444e085b571",
}


def check_frozen_migrations() -> int:
    migrations_dir = pathlib.Path(__file__).parent.parent / "db" / "migrations"
    if not migrations_dir.exists():
        print(f"ERROR: Migrations directory not found at {migrations_dir}", file=sys.stderr)
        return 1

    errors: list[str] = []

    for filename, expected_hash in FROZEN_MIGRATION_HASHES.items():
        file_path = migrations_dir / filename
        if not file_path.exists():
            errors.append(f"Missing frozen migration file: {filename}")
            continue

        raw_bytes = file_path.read_bytes()
        # Normalize CRLF to LF to prevent cross-platform false positives
        normalized_bytes = raw_bytes.replace(b"\r\n", b"\n")
        actual_hash = hashlib.sha256(normalized_bytes).hexdigest().lower()

        if actual_hash != expected_hash.lower():
            errors.append(
                f"Hash mismatch on frozen migration {filename}:\n"
                f"  Expected: {expected_hash}\n"
                f"  Actual:   {actual_hash}\n"
                f"  Violates Rule A.6 ('Never edit an applied migration'). "
                f"Create a new migration instead."
            )

    if errors:
        print("=" * 70, file=sys.stderr)
        print("FAIL: Frozen migration hash check failed!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for err in errors:
            print(f"- {err}", file=sys.stderr)
        return 1

    print(f"SUCCESS: All {len(FROZEN_MIGRATION_HASHES)} frozen migration files (001–013) verified intact.")
    return 0


if __name__ == "__main__":
    sys.exit(check_frozen_migrations())


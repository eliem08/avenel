"""Jurisdiction-backed VAT tax mapping and CGNC account resolution.

Enforces:
- Rule A.1: All VAT rates and deduction rules are loaded from /jurisdiction/ma/*.yaml.
- Rule A.2: No numeric literals for tax rates or thresholds outside /jurisdiction/.
- Phase 3 Item 2: Tax accounts must resolve through client_tax_mappings (approved_by required).
  If no approved mapping exists, returns None and caller raises ACCOUNT_UNMAPPED (blocking).
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from avenel.jurisdiction.loader import get_jurisdiction_pack, is_enabled_status


@dataclass(frozen=True)
class TaxRateInfo:
    code: str
    rate_value: float
    rule_key: str
    source_citation: str
    label_fr: str


@dataclass(frozen=True)
class ResolvedTaxAccount:
    account_id: uuid.UUID
    account_code: str
    label: str
    tax_code: str
    direction: str  # 'purchase', 'sale', 'fixed_asset', 'rounding'
    rate_value: float
    rule_refs: list[str]


def get_available_vat_rates(rate_date: datetime.date | None = None) -> list[TaxRateInfo]:
    """Loads all verified VAT rates from Moroccan jurisdiction pack effective on rate_date."""
    pack = get_jurisdiction_pack()
    rates: list[TaxRateInfo] = []

    standard_rule = pack.get_rule("vat.rate.standard")
    if standard_rule and is_enabled_status(standard_rule.get("status")):
        rates.append(
            TaxRateInfo(
                code="STANDARD_20",
                rate_value=float(standard_rule["value"]),
                rule_key="vat.rate.standard",
                source_citation=str(standard_rule.get("source") or ""),
                label_fr=str(standard_rule.get("label", "Taux normal")),
            )
        )

    reduced_rule = pack.get_rule("vat.rate.reduced_10")
    if reduced_rule and is_enabled_status(reduced_rule.get("status")):
        rates.append(
            TaxRateInfo(
                code="REDUCED_10",
                rate_value=float(reduced_rule["value"]),
                rule_key="vat.rate.reduced_10",
                source_citation=str(reduced_rule.get("source") or ""),
                label_fr=str(reduced_rule.get("label", "Taux réduit")),
            )
        )

    reduced_14_rule = pack.get_rule("vat.rate.reduced_14")
    if reduced_14_rule and is_enabled_status(reduced_14_rule.get("status")):
        eff_from = reduced_14_rule.get("effective_from")
        eff_to = reduced_14_rule.get("effective_to")
        is_effective = True
        if rate_date is not None:
            if eff_from and rate_date < datetime.date.fromisoformat(str(eff_from)):
                is_effective = False
            if eff_to and rate_date > datetime.date.fromisoformat(str(eff_to)):
                is_effective = False
        if is_effective:
            rates.append(
                TaxRateInfo(
                    code="REDUCED_14",
                    rate_value=float(reduced_14_rule["value"]),
                    rule_key="vat.rate.reduced_14",
                    source_citation=str(reduced_14_rule.get("source") or ""),
                    label_fr=str(reduced_14_rule.get("label", "Taux réduit transitoire")),
                )
            )

    return rates


def match_vat_rate_to_pack(rate_fraction: float, rate_date: datetime.date | None = None, tolerance: float = 0.005) -> TaxRateInfo | None:
    """Matches an extracted or calculated VAT rate against verified pack rules."""
    rates = get_available_vat_rates(rate_date)
    for r in rates:
        if abs(r.rate_value - rate_fraction) <= tolerance:
            return r
    return None


def resolve_tax_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    tax_code: str,
    direction: str,  # 'purchase', 'sale', 'fixed_asset'
    is_asset: bool = False,
) -> ResolvedTaxAccount | None:
    """Resolves the appropriate CGNC VAT account strictly from client_tax_mappings.

    Requires approved_by IS NOT NULL.
    If no approved mapping exists, returns None (raising ACCOUNT_UNMAPPED blocking issue).
    """
    if is_asset or direction == "fixed_asset":
        db_direction = "fixed_asset"
    elif direction in ("input", "purchase"):
        db_direction = "purchase"
    elif direction in ("output", "sale"):
        db_direction = "sale"
    else:
        db_direction = direction

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.account_id, ca.account_code, ca.label
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            WHERE m.tenant_id = %s
              AND m.client_entity_id = %s
              AND m.tax_code = %s
              AND m.direction = %s
              AND m.approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, tax_code, db_direction),
        )
        row = cur.fetchone()
        if not row:
            return None

        rate_info = next((r for r in get_available_vat_rates() if r.code == tax_code), None)
        rate_val = rate_info.rate_value if rate_info else 0.0
        return ResolvedTaxAccount(
            account_id=uuid.UUID(str(row[0])),
            account_code=str(row[1]),
            label=str(row[2]),
            tax_code=tax_code,
            direction=db_direction,
            rate_value=rate_val,
            rule_refs=["client_tax_mappings.approved"],
        )


def get_suggested_tax_account_default(direction: str, is_asset: bool = False) -> tuple[str, str]:
    """Returns suggested default account code and label for UI assistance only.

    NEVER applied automatically to create journal proposal lines.
    """
    if is_asset or direction == "fixed_asset":
        return "34551", "État - TVA récupérable sur immobilisations"
    elif direction in ("input", "purchase"):
        return "34552", "État - TVA récupérable sur charges"
    elif direction == "rounding":
        pack = get_jurisdiction_pack()
        rule = pack.get_rule("accounting.fx_rounding.default_account")
        code = str(rule["value"]) if rule else "6588"
        return code, "Charges / Produits d'arrondi (centimes)"
    else:
        return "4455", "État - TVA facturée"


def resolve_rounding_account(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    direction: str = "rounding_loss",
) -> tuple[uuid.UUID, str, str]:
    """Resolves rounding account from approved client_tax_mappings (direction 'rounding_loss' or 'rounding_gain')
    or falls back to pack default marked needs_expert.
    """
    target_direction = direction if direction in ("rounding_loss", "rounding_gain") else "rounding_loss"
    with conn.cursor() as cur:
        # 1. Exact direction match ('rounding_loss' or 'rounding_gain')
        cur.execute(
            """
            SELECT m.account_id, ca.account_code, ca.label
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            WHERE m.tenant_id = %s
              AND m.client_entity_id = %s
              AND m.direction = %s
              AND m.approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, target_direction),
        )
        row = cur.fetchone()
        if row:
            return uuid.UUID(str(row[0])), str(row[1]), str(row[2])

        # 2. General 'rounding' direction fallback
        cur.execute(
            """
            SELECT m.account_id, ca.account_code, ca.label
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            WHERE m.tenant_id = %s
              AND m.client_entity_id = %s
              AND m.direction = 'rounding'
              AND m.approved_by IS NOT NULL
            LIMIT 1;
            """,
            (tenant_id, client_entity_id),
        )
        row_general = cur.fetchone()
        if row_general:
            return uuid.UUID(str(row_general[0])), str(row_general[1]), str(row_general[2])

    pack = get_jurisdiction_pack()
    if target_direction == "rounding_gain":
        rule = pack.get_rule("accounting.fx_rounding.gain_account")
        default_code = str(rule["value"]) if rule else "7331"
        default_label = "Gains de change sur arrondis (centimes)"
    else:
        rule = pack.get_rule("accounting.fx_rounding.loss_account")
        default_code = str(rule["value"]) if rule else "6331"
        default_label = "Pertes de change sur arrondis (centimes)"

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, label FROM chart_accounts
            WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
            LIMIT 1;
            """,
            (tenant_id, client_entity_id, default_code),
        )
        acc_row = cur.fetchone()
        if acc_row:
            return uuid.UUID(str(acc_row[0])), default_code, str(acc_row[1])
        else:
            new_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                VALUES (%s, %s, %s, %s, %s, 'manual')
                RETURNING id;
                """,
                (new_id, tenant_id, client_entity_id, default_code, default_label),
            )
            return new_id, default_code, default_label


def seed_approved_client_tax_mappings(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    approver_id: uuid.UUID | None = None,
    include_withholding: bool = True,
) -> None:
    """Helper to seed approved tax mappings for a client entity (used for setups and testing)."""
    user_id = approver_id or uuid.uuid4()

    def _ensure_acc(code: str, label: str) -> uuid.UUID:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM chart_accounts
                WHERE tenant_id = %s AND client_entity_id = %s AND account_code = %s
                LIMIT 1;
                """,
                (tenant_id, client_entity_id, code),
            )
            row = cur.fetchone()
            if row:
                return uuid.UUID(str(row[0]))
            new_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO chart_accounts (id, tenant_id, client_entity_id, account_code, label, source)
                VALUES (%s, %s, %s, %s, %s, 'cgnc_seed')
                RETURNING id;
                """,
                (new_id, tenant_id, client_entity_id, code, label),
            )
            return new_id

    acc_34552 = _ensure_acc("34552", "État - TVA récupérable sur charges")
    acc_34551 = _ensure_acc("34551", "État - TVA récupérable sur immobilisations")
    acc_4455 = _ensure_acc("4455", "État - TVA facturée")
    acc_6588 = _ensure_acc("6588", "Charges / Produits d'arrondi (centimes)")
    acc_6331 = _ensure_acc("6331", "Pertes de change sur arrondis")
    acc_7331 = _ensure_acc("7331", "Gains de change sur arrondis")
    acc_4711 = _ensure_acc("4711", "Compte d'attente (opérations à régulariser)")
    acc_3457 = _ensure_acc("3457", "État - Retenues à la source")
    acc_6147 = _ensure_acc("6147", "Services bancaires")

    mappings = [
        ("STANDARD_20", "purchase", acc_34552),
        ("REDUCED_10", "purchase", acc_34552),
        ("REDUCED_14", "purchase", acc_34552),
        ("STANDARD_20", "fixed_asset", acc_34551),
        ("REDUCED_10", "fixed_asset", acc_34551),
        ("REDUCED_14", "fixed_asset", acc_34551),
        ("STANDARD_20", "sale", acc_4455),
        ("REDUCED_10", "sale", acc_4455),
        ("REDUCED_14", "sale", acc_4455),
        ("ROUNDING", "rounding", acc_6588),
        ("ROUNDING_LOSS", "rounding_loss", acc_6331),
        ("ROUNDING_GAIN", "rounding_gain", acc_7331),
        ("SUSPENSE", "suspense", acc_4711),
        ("BANK_FEE", "bank_fee", acc_6147),
    ]
    if include_withholding:
        mappings.append(("WITHHOLDING", "withholding", acc_3457))

    with conn.cursor() as cur:
        for tax_code, direction, acc_id in mappings:
            cur.execute(
                """
                INSERT INTO client_tax_mappings (
                    tenant_id, client_entity_id, tax_code, direction, account_id, approved_by, approved_at
                ) VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (tenant_id, client_entity_id, tax_code, direction)
                DO UPDATE SET account_id = EXCLUDED.account_id, approved_by = EXCLUDED.approved_by, approved_at = now();
                """,
                (tenant_id, client_entity_id, tax_code, direction, acc_id, user_id),
            )



# ---------------------------------------------------------------------------
# Firm-managed tax mappings (Phase 3 completion). Part K 15: tax accounts resolve only
# through approved client_tax_mappings. Human decision (6 Nov 2026): only members with a
# professional registration (expert-comptable / comptable agréé) approve a mapping; other
# write roles may propose one, which stays unapproved and is never used to build entries.
# ---------------------------------------------------------------------------

MAPPING_DIRECTIONS: tuple[str, ...] = ("purchase", "fixed_asset", "sale")
WITHHOLDING_SLOT: tuple[str, str] = ("WITHHOLDING", "withholding")


class TaxMappingError(ValueError):
    """Invalid mapping request (unknown slot or account outside the client's chart)."""


def list_mapping_slots(rate_date: datetime.date | None = None) -> list[dict[str, Any]]:
    """Every (tax_code, direction) pair the entry builder can ask for, from the pack."""
    slots: list[dict[str, Any]] = []
    for r in get_available_vat_rates(rate_date):
        for d in MAPPING_DIRECTIONS:
            slots.append({
                "tax_code": r.code, "direction": d, "rate": r.rate_value,
                "label_fr": r.label_fr, "rule_key": r.rule_key, "source": r.source_citation,
            })
    slots.append({
        "tax_code": WITHHOLDING_SLOT[0], "direction": WITHHOLDING_SLOT[1], "rate": None,
        "label_fr": "Retenue à la source sur TVA", "rule_key": None, "source": None,
    })
    return slots


def list_client_tax_mappings(
    conn: psycopg.Connection, tenant_id: uuid.UUID, client_entity_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Slots with the current mapping (approved or not) of a client company."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.tax_code, m.direction, m.account_id, ca.account_code, ca.label,
                   m.approved_by, u.full_name, m.approved_at
            FROM client_tax_mappings m
            JOIN chart_accounts ca ON ca.id = m.account_id AND ca.tenant_id = m.tenant_id
            LEFT JOIN users u ON u.id = m.approved_by
            WHERE m.tenant_id = %s AND m.client_entity_id = %s;
            """,
            (tenant_id, client_entity_id),
        )
        current = {(r[0], r[1]): r for r in cur.fetchall()}
    out = []
    for slot in list_mapping_slots():
        r = current.get((slot["tax_code"], slot["direction"]))
        out.append({
            **slot,
            "account_id": str(r[2]) if r else None,
            "account_code": r[3] if r else None,
            "account_label": r[4] if r else None,
            "approved": bool(r and r[5]),
            "approved_by_name": r[6] if r else None,
            "approved_at": r[7].isoformat() if r and r[7] else None,
        })
    return out


def set_client_tax_mapping(
    conn: psycopg.Connection,
    tenant_id: uuid.UUID,
    client_entity_id: uuid.UUID,
    tax_code: str,
    direction: str,
    account_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_is_registered_professional: bool,
) -> dict[str, Any]:
    """Creates or changes a mapping. Approved only when set by a registered professional;
    otherwise stored unapproved (and any previous approval is withdrawn, since the account changed
    or a non-professional touched it). Every change is an audit event."""
    if (tax_code, direction) not in {(s["tax_code"], s["direction"]) for s in list_mapping_slots()}:
        raise TaxMappingError(f"Code de taxe ou sens inconnu : {tax_code} / {direction}.")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT account_code FROM chart_accounts WHERE tenant_id = %s AND client_entity_id = %s AND id = %s;",
            (tenant_id, client_entity_id, account_id),
        )
        acc = cur.fetchone()
        if not acc:
            raise TaxMappingError("Ce compte n'appartient pas au plan comptable de la société.")
        approved_by = actor_id if actor_is_registered_professional else None
        cur.execute(
            """
            INSERT INTO client_tax_mappings (tenant_id, client_entity_id, tax_code, direction, account_id, approved_by, approved_at)
            VALUES (%s, %s, %s, %s, %s, %s, CASE WHEN %s::uuid IS NULL THEN NULL ELSE now() END)
            ON CONFLICT (tenant_id, client_entity_id, tax_code, direction)
            DO UPDATE SET account_id = EXCLUDED.account_id, approved_by = EXCLUDED.approved_by,
                          approved_at = EXCLUDED.approved_at
            RETURNING id;
            """,
            (tenant_id, client_entity_id, tax_code, direction, account_id, approved_by, approved_by),
        )
        mapping_id = cur.fetchone()[0]  # type: ignore[index]
        cur.execute(
            """
            INSERT INTO audit_events (tenant_id, actor_type, actor_id, action, resource_type, resource_id, data)
            VALUES (%s, 'user', %s, %s, 'client_tax_mapping', %s, %s::jsonb);
            """,
            (
                tenant_id, str(actor_id),
                "tax_mapping.approved" if approved_by else "tax_mapping.proposed",
                str(mapping_id),
                json.dumps({"client_entity_id": str(client_entity_id), "tax_code": tax_code,
                            "direction": direction, "account_code": acc[0]}),
            ),
        )
    return {"tax_code": tax_code, "direction": direction, "account_id": str(account_id),
            "account_code": acc[0], "approved": approved_by is not None}

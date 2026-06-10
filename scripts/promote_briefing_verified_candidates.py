from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"

BRIEFING_CANDIDATES_PATH = DATA_DIR / "briefing_update_candidates.csv"
MANUAL_OFFICIAL_INDICATION_EVIDENCE_PATH = DATA_DIR / "manual_official_indication_evidence.csv"
MANUAL_PROMOTION_LOG_PATH = DATA_DIR / "manual_evidence_promotion_log.csv"
PRODUCT_GAP_CANDIDATES_PATH = AUDIT_DIR / "briefing_product_gap_candidates_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "briefing_promotion_summary_latest.md"

HUONS_SOURCE_URL = (
    "https://huonsmeditech.com/layout/eng/home.php?"
    "mid=30&go=pds.list&pds_type=7&start=0&num=1288&s_key1=&s_key2=&s_que="
)
RADIESSE_FDA_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?ID=P050052S162"
RADIESSE_IFU_URL = "https://radiesse.com/professionals/practice-resources/"
ALPHA_SOURCE_URL = (
    "https://www.prnewswire.com/news-releases/"
    "alpha-aesthetics-partners-expands-presence-in-california-and-enters-colorado-through-"
    "partnership-with-preva-aesthetics-302776732.html"
)


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:length]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def append_unique(rows: list[dict[str, str]], row: dict[str, str], key_fields: list[str]) -> bool:
    key = tuple(row.get(field, "") for field in key_fields)
    for existing in rows:
        if tuple(existing.get(field, "") for field in key_fields) == key:
            return False
    rows.append(row)
    return True


def set_candidate_status(
    rows: list[dict[str, str]],
    predicate,
    status: str,
    official_query: str | None = None,
) -> list[str]:
    changed = []
    for row in rows:
        if not predicate(row):
            continue
        if row.get("status") == status and row.get("needs_official_verification") == "no":
            continue
        row["status"] = status
        row["needs_official_verification"] = "no"
        if official_query:
            row["official_query"] = official_query
        changed.append(row.get("candidate_id", ""))
    return changed


def main() -> None:
    captured_at = now_iso()
    candidate_fields, candidates = read_csv(BRIEFING_CANDIDATES_PATH)
    registration_fields, registrations = read_csv(MANUAL_OFFICIAL_INDICATION_EVIDENCE_PATH)
    promotion_fields, promotions = read_csv(MANUAL_PROMOTION_LOG_PATH)
    if not promotion_fields:
        promotion_fields = [
            "promotion_id",
            "product_id",
            "seed_record_id",
            "company_id",
            "company",
            "brand",
            "product_family_id",
            "source_key",
            "source_type",
            "field_name",
            "promoted_value",
            "source_url",
            "evidence_title",
            "confidence",
            "promoted_at",
            "note",
        ]

    summary: list[str] = []

    huons_pro_balance = next(
        (
            row
            for row in candidates
            if row.get("company") == "Huons Meditech"
            and row.get("product_id") == "prod_34f1bcd4274c"
        ),
        {},
    )
    if huons_pro_balance:
        huons_registration = {
            "product_id": "prod_34f1bcd4274c",
            "seed_record_id": "REC_0176",
            "company_id": "co_8f51008b9523",
            "company": "Huons Meditech",
            "brand": "DermaShine",
            "jurisdiction": "EU / Global",
            "regulator": "CE/MDR",
            "regulatory_pathway": "MDR certification",
            "status": "CE-MDR certified accessory claim; certificate identifier not disclosed",
            "registration_no": "",
            "approval_date": "2026-05-19",
            "expiry_date": "",
            "registered_name": "Premium 9-Pin Needle for Dermashine Pro / Balance",
            "approved_indication": "",
            "intended_use": "Disposable microneedle used in combination with Dermashine Pro and Dermashine Balance for skin booster injections.",
            "legal_manufacturer": "Huons Meditech",
            "local_holder": "",
            "source_key": "briefing_official_huons_premium_9pin_ce_mdr_20260519",
            "source_url": HUONS_SOURCE_URL,
            "source_type": "official_company_press_release",
            "evidence_title": "Huons Meditech Receives CE-MDR Approval for Aesthetic Drug Delivery System Premium 9-Pin Needle",
            "evidence_excerpt": (
                "Official Huons Meditech release says Premium 9-Pin Needle received CE-MDR "
                "certification and is used with Dermashine Pro and Dermashine Balance."
            ),
            "official_description_exact": (
                "Premium 9-Pin Needle received CE-MDR certification; Dermashine Pro and "
                "Dermashine Balance previously obtained CE-MDR certification."
            ),
            "official_description_source_field": "company_press_release",
            "field_note": "Company official release verified; regulator certificate number and certificate date remain undisclosed.",
            "checked_at": captured_at,
            "reviewed_by": "Codex",
            "review_status": "auto_cross_checked_official_company_claim",
            "confidence": "official_company_press_release_pending_certificate_id",
        }
        if append_unique(registrations, huons_registration, ["source_key", "product_id", "registered_name"]):
            summary.append("Added Huons Meditech CE-MDR registration evidence from official company release.")
        else:
            summary.append("Huons Meditech CE-MDR registration evidence already existed.")

        huons_log = {
            "promotion_id": "promo_" + short_hash("huons_premium_9pin_ce_mdr_20260519"),
            "product_id": "prod_34f1bcd4274c",
            "seed_record_id": "REC_0176",
            "company_id": "co_8f51008b9523",
            "company": "Huons Meditech",
            "brand": "DermaShine",
            "product_family_id": "",
            "source_key": "briefing_official_huons_premium_9pin_ce_mdr_20260519",
            "source_type": "official_company_press_release",
            "field_name": "registration_evidence",
            "promoted_value": "CE-MDR certification claim for Premium 9-Pin Needle accessory",
            "source_url": HUONS_SOURCE_URL,
            "evidence_title": "Huons Meditech CE-MDR approval for Premium 9-Pin Needle",
            "confidence": "official_company_press_release_pending_certificate_id",
            "promoted_at": captured_at,
            "note": "Promoted from briefing candidate; regulator certificate identifier still needs official certificate lookup.",
        }
        append_unique(promotions, huons_log, ["promotion_id"])

    radiesse_predicate = (
        lambda row: row.get("brand") == "Radiesse"
        and row.get("event_group") in {"indication_expansion", "regulatory_approval"}
        and row.get("product_id") == "prod_7bdbe15c9ffd"
    )
    radiesse_promoted = set_candidate_status(
        candidates,
        radiesse_predicate,
        "promoted",
        "Linked to existing FDA PMA S162 and official Radiesse IFU evidence.",
    )
    if radiesse_promoted or any(radiesse_predicate(row) and row.get("status") == "promoted" for row in candidates):
        if radiesse_promoted:
            summary.append(f"Linked {len(radiesse_promoted)} Radiesse briefing candidates to existing official evidence.")
        radiesse_log = {
            "promotion_id": "promo_" + short_hash("radiesse_p050052_s162_briefing_link"),
            "product_id": "prod_7bdbe15c9ffd",
            "seed_record_id": "REC_0781",
            "company_id": "co_e442ba681971",
            "company": "Merz",
            "brand": "Radiesse",
            "product_family_id": "",
            "source_key": "fda_pma_p050052_s162",
            "source_type": "official_fda_pma",
            "field_name": "briefing_candidate_status",
            "promoted_value": "briefing Radiesse indication and approval candidates linked to FDA PMA S162",
            "source_url": RADIESSE_FDA_URL,
            "evidence_title": "FDA PMA supplement P050052/S162 for Radiesse Injectable Implant",
            "confidence": "official_regulator_record",
            "promoted_at": captured_at,
            "note": f"Official IFU cross-check: {RADIESSE_IFU_URL}",
        }
        append_unique(promotions, radiesse_log, ["promotion_id"])

    rejected = set_candidate_status(
        candidates,
        lambda row: row.get("brand") == "Radiesse"
        and row.get("event_group") == "product_launch"
        and row.get("product_id") == "prod_7bdbe15c9ffd",
        "rejected_event_class",
        "Official evidence confirms indication expansion, not a product launch.",
    )
    rejected += set_candidate_status(
        candidates,
        lambda row: row.get("company") == "Huons Meditech"
        and row.get("product_id") == "prod_fad4dbfdec67",
        "rejected_product_mismatch",
        "Official source is about Premium 9-Pin Needle for Dermashine Pro / Balance, not Dermashine Duo RF.",
    )
    if rejected:
        summary.append(f"Rejected {len(rejected)} over-broad briefing candidates after official-source review.")

    huons_candidates = set_candidate_status(
        candidates,
        lambda row: row.get("company") == "Huons Meditech"
        and row.get("product_id") == "prod_34f1bcd4274c"
        and row.get("event_group") in {"regulatory_approval", "channel_coverage"},
        "promoted",
        "Verified against Huons Meditech official release; certificate identifier still pending.",
    )
    if huons_candidates:
        summary.append(f"Promoted {len(huons_candidates)} Huons briefing candidates.")

    alpha_predicate = (
        lambda row: row.get("company") == "Alpha Aesthetics"
        and row.get("event_group") == "channel_coverage"
    )
    alpha_candidates = set_candidate_status(
        candidates,
        alpha_predicate,
        "promoted",
        "Verified against PRNewswire company release sourced to Alpha Aesthetics Partners.",
    )
    if alpha_candidates or any(alpha_predicate(row) and row.get("status") == "promoted" for row in candidates):
        alpha_log = {
            "promotion_id": "promo_" + short_hash("alpha_preva_channel_20260519"),
            "product_id": "",
            "seed_record_id": "",
            "company_id": "",
            "company": "Alpha Aesthetics Partners",
            "brand": "",
            "product_family_id": "",
            "source_key": "briefing_official_alpha_preva_channel_20260519",
            "source_type": "official_company_press_release",
            "field_name": "company_market_presence",
            "promoted_value": "Partnership with Preva Aesthetics adds Denver, Colorado and Encinitas, California presence.",
            "source_url": ALPHA_SOURCE_URL,
            "evidence_title": "Alpha Aesthetics Partners expands in California and enters Colorado through Preva Aesthetics",
            "confidence": "official_company_press_release",
            "promoted_at": captured_at,
            "note": "Company not yet mapped to a master company_id; keep as company-market presence evidence lead.",
        }
        append_unique(promotions, alpha_log, ["promotion_id"])
        if alpha_candidates:
            summary.append(f"Promoted {len(alpha_candidates)} Alpha Aesthetics channel-coverage candidate.")

    product_gap_fields = [
        "company",
        "candidate_product_or_family",
        "source_count",
        "source_types",
        "source_domains",
        "confidence_mix",
        "sample_url",
        "review_status",
    ]
    _, product_gap_rows = read_csv(PRODUCT_GAP_CANDIDATES_PATH)
    gap_row = {
        "company": "Huons Meditech",
        "candidate_product_or_family": "Premium 9-Pin Needle",
        "source_count": "1",
        "source_types": "official_company_press_release",
        "source_domains": "huonsmeditech.com",
        "confidence_mix": "official_company_release; CE-MDR certificate id pending",
        "sample_url": HUONS_SOURCE_URL,
        "review_status": "needs_product_master_review",
    }
    if append_unique(product_gap_rows, gap_row, ["company", "candidate_product_or_family", "sample_url"]):
        summary.append("Added Premium 9-Pin Needle to the briefing product-gap review queue.")

    write_csv(BRIEFING_CANDIDATES_PATH, candidate_fields, candidates)
    write_csv(MANUAL_OFFICIAL_INDICATION_EVIDENCE_PATH, registration_fields, registrations)
    write_csv(MANUAL_PROMOTION_LOG_PATH, promotion_fields, promotions)
    write_csv(PRODUCT_GAP_CANDIDATES_PATH, product_gap_fields, product_gap_rows)

    promoted_count = sum(1 for row in candidates if row.get("status") == "promoted")
    remaining_unverified = sum(1 for row in candidates if row.get("status") == "candidate_unverified")
    rejected_count = sum(1 for row in candidates if row.get("status", "").startswith("rejected"))
    promoted_rows = [row for row in candidates if row.get("status") == "promoted"]
    rejected_rows = [row for row in candidates if row.get("status", "").startswith("rejected")]

    def candidate_line(row: dict[str, str]) -> str:
        identity = " / ".join(
            part
            for part in [row.get("company"), row.get("brand"), row.get("product_name"), row.get("event_group")]
            if part
        )
        return f"- {row.get('article_date')} | {identity} | {row.get('source_domain')} | {row.get('official_query')}"

    lines = [
        "# Briefing Verified Promotion Summary",
        "",
        f"Generated: {captured_at}",
        "",
        "## Actions",
        "",
        *[f"- {item}" for item in summary],
        "",
        "## Current Candidate Status",
        "",
        f"- Promoted: {promoted_count}",
        f"- Still unverified: {remaining_unverified}",
        f"- Rejected after official review: {rejected_count}",
        "",
        "## Promoted Candidates",
        "",
        *[candidate_line(row) for row in promoted_rows[:20]],
        "",
        "## Rejected Candidates",
        "",
        *[candidate_line(row) for row in rejected_rows[:20]],
        "",
        "## Remaining Gaps",
        "",
        "- Huons CE-MDR: official company source found; certificate identifier/date still needs regulator or certificate evidence.",
        "- Alpha channel coverage: official company release found; master company identity is not mapped yet.",
        "- Most commercial-performance candidates still need IR, filing, earnings transcript, or official press-release evidence before promotion.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        {
            "summary": str(SUMMARY_PATH),
            "promoted": promoted_count,
            "remaining_unverified": remaining_unverified,
            "rejected": rejected_count,
            "registration_evidence_rows": len(registrations),
            "promotion_log_rows": len(promotions),
            "product_gap_candidates": len(product_gap_rows),
        }
    )


if __name__ == "__main__":
    main()

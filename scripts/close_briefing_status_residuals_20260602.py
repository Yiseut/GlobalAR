from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable


TZ = timezone(timedelta(hours=8))
RUN_TS = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

CANDIDATES_PATH = DATA_DIR / "briefing_update_candidates.csv"
VERIFIED_EVENTS_PATH = DATA_DIR / "briefing_verified_update_events.csv"
PRODUCT_GAPS_PATH = AUDIT_DIR / "briefing_product_gap_candidates_latest.csv"
PROMOTION_LOG_PATH = DATA_DIR / "manual_evidence_promotion_log.csv"

SOLTA_SOURCE_URL = "https://www.prnewswire.com/news-releases/bausch-healths-aesthetic-business-solta-medical-earns-prestigious-trademark-certification-of-thermage-in-china-302784868.html"
SOLTA_PROMOTION_ID = "promo_" + hashlib.sha1(b"solta_thermage_china_aaa_trademark_20260528").hexdigest()[:12]
BIMINI_PROMOTION_ID = "promo_" + hashlib.sha1(b"bimini_product_master_gap_closed_20260602").hexdigest()[:12]


def norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\u00a0", " ").split())


def short_hash(value: str, size: int = 14) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:size]


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RuntimeError(f"{path} has no header")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def backup(path: Path) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out = AUDIT_DIR / f"{path.stem}.backup_before_briefing_status_residuals_{RUN_TS}{path.suffix}"
    shutil.copy2(path, out)
    return out


def set_closed(row: dict[str, str], status: str, note: str, *, body_quality: str = "closed_no_fulltext_needed") -> None:
    row["status"] = status
    row["needs_official_verification"] = "no"
    row["needs_fulltext_rescue"] = "no"
    row["body_quality"] = body_quality
    row["official_query"] = note


def is_stock_filing(row: dict[str, str]) -> bool:
    text = " ".join(norm(row.get(k)).lower() for k in ["article_url", "excerpt", "company"])
    return "/sec-filings/" in text or " form 3" in text or " form 4" in text or " form 144" in text or "rsu" in text


def is_bimini(row: dict[str, str]) -> bool:
    text = " ".join(norm(row.get(k)).lower() for k in ["company", "brand", "product_name", "article_url", "excerpt"])
    return "bimini" in text or "puregraft" in text or "dermapose" in text


def add_verified_event(events: list[dict[str, str]], row: dict[str, str], data: dict[str, str]) -> bool:
    event_id = "bve_" + short_hash("|".join([row.get("candidate_id", ""), data["official_source_url"], data["promoted_target"], data["promotion_status"]]))
    if any(item.get("event_id") == event_id for item in events):
        return False
    payload = {
        "event_id": event_id,
        "candidate_id": row.get("candidate_id", ""),
        "event_group": row.get("event_group", ""),
        "event_type": row.get("event_type", ""),
        "article_date": row.get("article_date", ""),
        "company_id": row.get("company_id", ""),
        "product_id": row.get("product_id", ""),
        "company": row.get("company", ""),
        "brand": row.get("brand", ""),
        "product_name": row.get("product_name", ""),
        "checked_at": now_iso(),
        **data,
    }
    events.append(payload)
    return True


def add_promotion_log(rows: list[dict[str, str]], row: dict[str, str]) -> bool:
    if any(item.get("promotion_id") == SOLTA_PROMOTION_ID for item in rows):
        return False
    rows.append(
        {
            "promotion_id": SOLTA_PROMOTION_ID,
            "product_id": row.get("product_id", ""),
            "seed_record_id": "",
            "company_id": row.get("company_id", ""),
            "company": "Solta Medical",
            "brand": "Thermage",
            "product_family_id": "",
            "source_key": "briefing_official_solta_thermage_china_aaa_trademark_20260528",
            "source_type": "official_company_press_release",
            "field_name": "company_market_presence",
            "promoted_value": "Thermage received AAA Well-Known Trademark Certification from China Trademark Association.",
            "source_url": SOLTA_SOURCE_URL,
            "evidence_title": "Solta Medical Thermage receives AAA Well-Known Trademark Certification in China",
            "confidence": "official_company_press_release",
            "promoted_at": now_iso(),
            "note": "Brand/market recognition evidence; not a product launch, registration approval, or new indication.",
        }
    )
    return True


def update_candidates(rows: list[dict[str, str]], events: list[dict[str, str]], promotions: list[dict[str, str]]) -> dict[str, int]:
    counts = {
        "bimini_gap_closed": 0,
        "solta_promoted_to_log": 0,
        "solta_rejected_event_class": 0,
        "fulltext_closed_nonactionable": 0,
    }
    for row in rows:
        text = " ".join(norm(row.get(k)).lower() for k in ["company", "brand", "product_name", "article_url", "excerpt"])

        if is_bimini(row) and row.get("status") == "verified_gap":
            row["company"] = "Bimini Health Tech"
            row["brand"] = "Puregraft / Dermapose"
            row["product_name"] = "Fat Transfer Product Suites"
            set_closed(row, "promoted", "Master records already exist: Bimini Health Tech REC_1056 Dermapose and REC_1057 Puregraft; gap closed.")
            counts["bimini_gap_closed"] += 1

        if "solta medical" in text and "thermage" in text and ("302784868" in text or "bausch-health-s-aesthetic-business-solta-medical-earns" in text):
            if row.get("event_group") == "commercial_performance":
                set_closed(row, "promoted", "Verified against Bausch/Solta official PRNewswire release; promoted as brand/market-recognition evidence, not registration.")
                if add_promotion_log(promotions, row):
                    counts["solta_promoted_to_log"] += 1
                add_verified_event(
                    events,
                    row,
                    {
                        "mapping_status": "mapped_product",
                        "verification_status": "verified_official_company_release",
                        "promotion_status": "promoted_to_log",
                        "official_source_type": "official_company_press_release",
                        "official_source_url": SOLTA_SOURCE_URL,
                        "official_title": "Solta Medical Thermage receives AAA Well-Known Trademark Certification in China",
                        "official_excerpt": "Thermage received AAA Well-Known Trademark Certification from China Trademark Association; this is brand/market recognition rather than a new regulatory approval.",
                        "promoted_target": "evidence_promotion_log",
                        "promotion_id": SOLTA_PROMOTION_ID,
                        "remaining_gap": "No registration or indication promotion from this item.",
                    },
                )
            else:
                set_closed(row, "rejected_event_class", "Official source confirms trademark/brand-recognition news, not a product launch, registration approval, or indication expansion.")
                counts["solta_rejected_event_class"] += 1

        if row.get("needs_fulltext_rescue") == "yes":
            if is_stock_filing(row):
                set_closed(row, "rejected_event_class", "SEC ownership/trading filing; not a product, indication, registration, or channel update.")
                counts["fulltext_closed_nonactionable"] += 1
            elif "bpdcn" in text or "decupaz" in text or "pivekimab" in text:
                set_closed(row, "excluded_scope_unlinked", "Official FDA/AbbVie item is an oncology BPDCN drug approval, outside the medical-aesthetics product scope.")
                counts["fulltext_closed_nonactionable"] += 1
            elif "kaneka" in text and "management plan" in text:
                set_closed(row, "rejected_event_class", "Management-plan news does not provide an official medical-aesthetics product launch fact for LACTIF.")
                counts["fulltext_closed_nonactionable"] += 1
            elif "agereverse" in text or "wellness retreat" in text or "longevity supplement" in text or "franchise expansion" in text:
                set_closed(row, "excluded_scope_unlinked", "Consumer wellness/supplement/service-platform item; outside upstream medical-aesthetics product master scope.")
                counts["fulltext_closed_nonactionable"] += 1
    return counts


def update_verified_events(rows: list[dict[str, str]]) -> int:
    changed = 0
    for row in rows:
        if row.get("promotion_status") == "verified_gap" and is_bimini(row):
            row["mapping_status"] = "mapped_product"
            row["verification_status"] = "verified_official_company_release"
            row["promotion_status"] = "promoted"
            row["promoted_target"] = "product_master; registration_evidence"
            row["promotion_id"] = BIMINI_PROMOTION_ID
            row["remaining_gap"] = ""
            row["checked_at"] = now_iso()
            changed += 1
    return changed


def filter_product_gaps(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    closed = []
    kept = []
    for row in rows:
        text = " ".join(norm(row.get(k)).lower() for k in ["company", "candidate_product_or_family", "confidence_mix"])
        if any(term in text for term in ["bimini health tech", "puregraft", "dermapose", "huons meditech", "premium 9-pin", "alpha aesthetics partners"]):
            closed.append(row)
        else:
            kept.append(row)
    return kept, closed


def main() -> None:
    audit: dict[str, Any] = {"run_ts": RUN_TS, "backups": {}, "changes": {}}

    candidate_fields, candidates = read_csv(CANDIDATES_PATH)
    event_fields, events = read_csv(VERIFIED_EVENTS_PATH)
    gap_fields, gaps = read_csv(PRODUCT_GAPS_PATH)
    promotion_fields, promotions = read_csv(PROMOTION_LOG_PATH)

    for path in [CANDIDATES_PATH, VERIFIED_EVENTS_PATH, PRODUCT_GAPS_PATH, PROMOTION_LOG_PATH]:
        audit["backups"][str(path)] = str(backup(path))

    audit["changes"]["candidates"] = update_candidates(candidates, events, promotions)
    audit["changes"]["verified_events_closed"] = update_verified_events(events)
    kept_gaps, closed_gaps = filter_product_gaps(gaps)
    audit["changes"]["product_gaps_closed"] = len(closed_gaps)
    audit["closed_product_gaps"] = closed_gaps

    write_csv(CANDIDATES_PATH, candidate_fields, candidates)
    write_csv(VERIFIED_EVENTS_PATH, event_fields, events)
    write_csv(PRODUCT_GAPS_PATH, gap_fields, kept_gaps)
    write_csv(PROMOTION_LOG_PATH, promotion_fields, promotions)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"briefing_status_residuals_closed_{RUN_TS}.json"
    latest_path = AUDIT_DIR / "briefing_status_residuals_closed_latest.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

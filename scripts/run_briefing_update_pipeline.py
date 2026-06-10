from __future__ import annotations

import csv
import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"

BRIEFING_CANDIDATES_PATH = DATA_DIR / "briefing_update_candidates.csv"
MANUAL_OFFICIAL_EVIDENCE_PATH = DATA_DIR / "manual_official_indication_evidence.csv"
MANUAL_PROMOTION_LOG_PATH = DATA_DIR / "manual_evidence_promotion_log.csv"
VERIFIED_EVENTS_PATH = DATA_DIR / "briefing_verified_update_events.csv"
FULLTEXT_RESCUE_PATH = DATA_DIR / "briefing_fulltext_rescue.csv"
PRODUCT_GAP_PATH = AUDIT_DIR / "briefing_product_gap_candidates_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "briefing_update_pipeline_summary_latest.md"

HUONS_SOURCE_URL = (
    "https://huonsmeditech.com/layout/eng/home.php?"
    "mid=30&go=pds.list&pds_type=7&start=0&num=1288&s_key1=&s_key2=&s_que="
)
RADIESSE_S162_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?ID=P050052S162"
RADIESSE_IFU_URL = "https://radiesse.com/professionals/practice-resources/"
RESTYLANE_CONTOUR_FDA_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?ID=P140029S054"
RESTYLANE_CONTOUR_GALDERMA_URL = (
    "https://www.galderma.com/news/galderma-receives-us-fda-approval-restylaner-contourtm-correction-temple-hollowing"
)
ALPHA_SOURCE_URL = (
    "https://www.prnewswire.com/news-releases/"
    "alpha-aesthetics-partners-expands-presence-in-california-and-enters-colorado-through-"
    "partnership-with-preva-aesthetics-302776732.html"
)
APYX_AYON_SOURCE_URL = (
    "https://www.globenewswire.com/news-release/2026/05/11/3291798/0/en/"
    "Apyx-Medical-Corporation-Receives-Expanded-FDA-510-k-Clearance-Adding-Power-Liposuction-"
    "Capability-to-AYON-Body-Contouring-System.html"
)
BIMINI_SOURCE_URL = "https://www.prnewswire.com/news-releases/bimini-health-tech-achieves-eu-mdr-certification-302770477.html"
SOLTA_THERMAGE_CHINA_AAA_SOURCE_URL = (
    "https://www.prnewswire.com/news-releases/"
    "bausch-healths-aesthetic-business-solta-medical-earns-prestigious-trademark-certification-of-thermage-in-china-302784868.html"
)
PHARMARESEARCH_SOURCE_URL = (
    "https://www.prnewswire.com/news-releases/"
    "pharmaresearch-schlieWt-westeuropaische-roadshow-fur-rejuran-in-funf-markten-ab-302771650.html"
)

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
}
FULLTEXT_FETCH_TIMEOUT_SECONDS = 10
FULLTEXT_RETRY_AFTER_DAYS = 7

PROMOTION_FIELDS = [
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

VERIFIED_EVENT_FIELDS = [
    "event_id",
    "candidate_id",
    "event_group",
    "event_type",
    "article_date",
    "company_id",
    "product_id",
    "company",
    "brand",
    "product_name",
    "mapping_status",
    "verification_status",
    "promotion_status",
    "official_source_type",
    "official_source_url",
    "official_title",
    "official_excerpt",
    "promoted_target",
    "promotion_id",
    "remaining_gap",
    "checked_at",
]

FULLTEXT_FIELDS = [
    "candidate_id",
    "article_url",
    "final_url",
    "fetched_at",
    "fetch_status",
    "status_code",
    "char_count",
    "title",
    "body_excerpt",
    "error",
]

PRODUCT_GAP_FIELDS = [
    "company",
    "candidate_product_or_family",
    "source_count",
    "source_types",
    "source_domains",
    "confidence_mix",
    "sample_url",
    "review_status",
]


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def clean_text(value: object, limit: int | None = None) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def short_hash(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()[:length]


def domain(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


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


def upsert_by_id(rows: list[dict[str, str]], row: dict[str, str], id_field: str) -> bool:
    row_id = row.get(id_field, "")
    for index, existing in enumerate(rows):
        if existing.get(id_field) == row_id:
            rows[index] = {**existing, **row}
            return False
    rows.append(row)
    return True


def fetch_article_text(url: str) -> dict[str, str]:
    fetched_at = now_iso()
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=FULLTEXT_FETCH_TIMEOUT_SECONDS, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        for node in soup(["script", "style", "noscript", "svg"]):
            node.decompose()
        title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        candidates = []
        for selector in ["article", "main", ".article-body", ".story-body", ".entry-content", ".press-release", "body"]:
            for node in soup.select(selector):
                text = clean_text(node.get_text(" ", strip=True))
                if len(text) > 180:
                    candidates.append(text)
        body = max(candidates, key=len) if candidates else clean_text(soup.get_text(" ", strip=True))
        return {
            "final_url": response.url,
            "fetched_at": fetched_at,
            "fetch_status": "ok" if len(body) >= 450 else "short_body",
            "status_code": str(response.status_code),
            "char_count": str(len(body)),
            "title": title,
            "body_excerpt": clean_text(body, 1200),
            "error": "",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "final_url": "",
            "fetched_at": fetched_at,
            "fetch_status": "fetch_failed",
            "status_code": "",
            "char_count": "0",
            "title": "",
            "body_excerpt": "",
            "error": clean_text(str(exc), 240),
        }


def rescue_cache_is_fresh(row: dict[str, str]) -> bool:
    fetched_at = row.get("fetched_at", "")
    if not fetched_at:
        return False
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone(timedelta(hours=8)))
    return datetime.now(fetched.tzinfo) - fetched < timedelta(days=FULLTEXT_RETRY_AFTER_DAYS)


def rescue_fulltext(candidates: list[dict[str, str]], rescue_rows: list[dict[str, str]]) -> tuple[int, int]:
    by_candidate = {row.get("candidate_id", ""): row for row in rescue_rows}
    attempted = 0
    rescued = 0
    for row in candidates:
        if row.get("needs_fulltext_rescue") != "yes":
            continue
        candidate_id = row.get("candidate_id", "")
        existing = by_candidate.get(candidate_id)
        if existing and (existing.get("fetch_status") == "ok" or rescue_cache_is_fresh(existing)):
            result = existing
        else:
            attempted += 1
            result = {"candidate_id": candidate_id, "article_url": row.get("article_url", "")}
            result.update(fetch_article_text(row.get("article_url", "")))
            upsert_by_id(rescue_rows, result, "candidate_id")
        if result.get("fetch_status") == "ok":
            row["needs_fulltext_rescue"] = "no"
            row["body_quality"] = "fulltext_rescued"
            row["excerpt"] = result.get("body_excerpt", row.get("excerpt", ""))
            rescued += 1
    return attempted, rescued


def set_status(row: dict[str, str], status: str, note: str, needs_verification: str = "no") -> None:
    row["status"] = status
    row["needs_official_verification"] = needs_verification
    row["official_query"] = note


def add_verified_event(
    events: list[dict[str, str]],
    row: dict[str, str],
    *,
    mapping_status: str,
    verification_status: str,
    promotion_status: str,
    source_type: str,
    source_url: str,
    official_title: str,
    official_excerpt: str,
    target: str,
    promotion_id: str,
    remaining_gap: str = "",
) -> None:
    event_id = "bve_" + short_hash("|".join([row.get("candidate_id", ""), source_url, target, promotion_status]), 14)
    upsert_by_id(
        events,
        {
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
            "mapping_status": mapping_status,
            "verification_status": verification_status,
            "promotion_status": promotion_status,
            "official_source_type": source_type,
            "official_source_url": source_url,
            "official_title": official_title,
            "official_excerpt": clean_text(official_excerpt, 520),
            "promoted_target": target,
            "promotion_id": promotion_id,
            "remaining_gap": remaining_gap,
            "checked_at": now_iso(),
        },
        "event_id",
    )


def add_promotion_log(
    rows: list[dict[str, str]],
    *,
    promotion_id: str,
    product_id: str,
    seed_record_id: str,
    company_id: str,
    company: str,
    brand: str,
    source_key: str,
    source_type: str,
    field_name: str,
    promoted_value: str,
    source_url: str,
    evidence_title: str,
    confidence: str,
    note: str,
) -> None:
    append_unique(
        rows,
        {
            "promotion_id": promotion_id,
            "product_id": product_id,
            "seed_record_id": seed_record_id,
            "company_id": company_id,
            "company": company,
            "brand": brand,
            "product_family_id": "",
            "source_key": source_key,
            "source_type": source_type,
            "field_name": field_name,
            "promoted_value": promoted_value,
            "source_url": source_url,
            "evidence_title": evidence_title,
            "confidence": confidence,
            "promoted_at": now_iso(),
            "note": note,
        },
        ["promotion_id"],
    )


def add_registration_row(rows: list[dict[str, str]], row: dict[str, str]) -> None:
    append_unique(rows, row, ["source_key", "product_id", "registered_name", "approval_date"])


def add_gap(rows: list[dict[str, str]], company: str, product: str, source_url: str, confidence: str) -> None:
    append_unique(
        rows,
        {
            "company": company,
            "candidate_product_or_family": product,
            "source_count": "1",
            "source_types": "official_company_press_release",
            "source_domains": domain(source_url),
            "confidence_mix": confidence,
            "sample_url": source_url,
            "review_status": "ready_for_master_mapping",
        },
        ["company", "candidate_product_or_family", "sample_url"],
    )


def promote_core_rules(
    candidates: list[dict[str, str]],
    manual_rows: list[dict[str, str]],
    promotions: list[dict[str, str]],
    events: list[dict[str, str]],
    gaps: list[dict[str, str]],
) -> dict[str, int]:
    stats = {
        "promoted": 0,
        "verified_gap": 0,
        "rejected": 0,
        "remapped": 0,
        "manual_registration_rows": 0,
        "promotion_log_rows": 0,
        "gap_rows": 0,
    }

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
        "evidence_title": "Huons Meditech Receives CE-MDR Approval for Premium 9-Pin Needle",
        "evidence_excerpt": "Official Huons Meditech release says Premium 9-Pin Needle received CE-MDR certification.",
        "checked_at": now_iso(),
        "reviewed_by": "Codex",
        "review_status": "auto_cross_checked_official_company_claim",
        "confidence": "official_company_press_release_pending_certificate_id",
    }
    before_manual = len(manual_rows)
    add_registration_row(manual_rows, huons_registration)
    stats["manual_registration_rows"] += len(manual_rows) - before_manual
    add_promotion_log(
        promotions,
        promotion_id="promo_" + short_hash("huons_premium_9pin_ce_mdr_20260519"),
        product_id="prod_34f1bcd4274c",
        seed_record_id="REC_0176",
        company_id="co_8f51008b9523",
        company="Huons Meditech",
        brand="DermaShine",
        source_key="briefing_official_huons_premium_9pin_ce_mdr_20260519",
        source_type="official_company_press_release",
        field_name="registration_evidence",
        promoted_value="CE-MDR certification claim for Premium 9-Pin Needle accessory",
        source_url=HUONS_SOURCE_URL,
        evidence_title="Huons Meditech CE-MDR approval for Premium 9-Pin Needle",
        confidence="official_company_press_release_pending_certificate_id",
        note="Certificate identifier still needs official certificate lookup.",
    )

    for row in candidates:
        text = " ".join([row.get("article_url", ""), row.get("excerpt", ""), row.get("company", ""), row.get("brand", ""), row.get("product_name", "")]).lower()

        if row.get("brand") == "Radiesse" and row.get("product_id") == "prod_7bdbe15c9ffd":
            if row.get("event_group") in {"indication_expansion", "regulatory_approval"}:
                set_status(row, "promoted", "Linked to existing FDA PMA S162 and official Radiesse IFU evidence.")
                promotion_id = "promo_" + short_hash("radiesse_p050052_s162_briefing_link")
                add_promotion_log(
                    promotions,
                    promotion_id=promotion_id,
                    product_id="prod_7bdbe15c9ffd",
                    seed_record_id="REC_0590",
                    company_id="co_e442ba681971",
                    company="Merz",
                    brand="Radiesse",
                    source_key="fda_pma_p050052_s162",
                    source_type="official_fda_pma",
                    field_name="briefing_candidate_status",
                    promoted_value="briefing Radiesse indication and approval candidates linked to FDA PMA S162",
                    source_url=RADIESSE_S162_URL,
                    evidence_title="FDA PMA supplement P050052/S162 for Radiesse Injectable Implant",
                    confidence="official_regulator_record",
                    note=f"Official IFU cross-check: {RADIESSE_IFU_URL}",
                )
                add_verified_event(
                    events,
                    row,
                    mapping_status="mapped_product",
                    verification_status="verified_official_regulator",
                    promotion_status="promoted",
                    source_type="official_fda_pma",
                    source_url=RADIESSE_S162_URL,
                    official_title="FDA PMA supplement P050052/S162",
                    official_excerpt="Radiesse Injectable Implant diluted 1:2 is indicated for correction of decollete wrinkles in patients 22 years and older.",
                    target="registration_evidence; official_indication_evidence",
                    promotion_id=promotion_id,
                )
            elif row.get("event_group") == "product_launch":
                set_status(row, "rejected_event_class", "Official evidence confirms indication expansion, not product launch.")

        if "restylane contour" in text or "p140029" in text or "temple hollowing" in text:
            row.update(
                {
                    "company_id": "co_2d09d05893cd",
                    "product_id": "prod_c02f4d543025",
                    "company": "Galderma",
                    "brand": "Restylane Contour",
                    "product_name": "Restylane Contour / Temple Hollowing",
                    "market_or_jurisdiction": "US",
                }
            )
            stats["remapped"] += 1
            if row.get("event_group") in {"indication_expansion", "regulatory_approval"}:
                set_status(row, "promoted", "Remapped to Restylane Contour and linked to FDA PMA S054/Galderma official release.")
                promotion_id = "promo_" + short_hash("restylane_contour_p140029_s054_briefing_link")
                add_promotion_log(
                    promotions,
                    promotion_id=promotion_id,
                    product_id="prod_c02f4d543025",
                    seed_record_id="REC_0809",
                    company_id="co_2d09d05893cd",
                    company="Galderma",
                    brand="Restylane Contour",
                    source_key="fda_pma_p140029_s054",
                    source_type="official_fda_pma",
                    field_name="briefing_candidate_status",
                    promoted_value="Restylane Contour temple hollowing candidates remapped and linked to FDA PMA S054",
                    source_url=RESTYLANE_CONTOUR_FDA_URL,
                    evidence_title="FDA PMA supplement P140029/S054 for Restylane Contour",
                    confidence="official_regulator_record",
                    note=f"Company release cross-check: {RESTYLANE_CONTOUR_GALDERMA_URL}",
                )
                add_verified_event(
                    events,
                    row,
                    mapping_status="remapped_product",
                    verification_status="verified_official_regulator",
                    promotion_status="promoted",
                    source_type="official_fda_pma",
                    source_url=RESTYLANE_CONTOUR_FDA_URL,
                    official_title="FDA PMA supplement P140029/S054 for Restylane Contour",
                    official_excerpt="Approval for expanding the indications of Restylane Contour for correction of temple hollowing in patients over age 21.",
                    target="registration_evidence; official_indication_evidence",
                    promotion_id=promotion_id,
                )
            elif row.get("event_group") == "product_launch":
                set_status(row, "rejected_event_class", "Official evidence confirms an indication expansion, not a new product launch.")

        if row.get("company") == "Huons Meditech":
            if row.get("product_id") == "prod_34f1bcd4274c" and row.get("event_group") in {"regulatory_approval", "channel_coverage"}:
                set_status(row, "promoted", "Verified against Huons Meditech official release; certificate identifier still pending.")
                add_verified_event(
                    events,
                    row,
                    mapping_status="mapped_product",
                    verification_status="verified_official_company_claim",
                    promotion_status="promoted",
                    source_type="official_company_press_release",
                    source_url=HUONS_SOURCE_URL,
                    official_title="Huons Meditech CE-MDR approval for Premium 9-Pin Needle",
                    official_excerpt="Premium 9-Pin Needle received CE-MDR certification and is used with Dermashine Pro and Dermashine Balance.",
                    target="registration_evidence; product_gap_queue",
                    promotion_id="promo_" + short_hash("huons_premium_9pin_ce_mdr_20260519"),
                    remaining_gap="Regulator certificate identifier still needed.",
                )
            elif row.get("product_id") == "prod_fad4dbfdec67":
                set_status(row, "rejected_product_mismatch", "Official source is about Premium 9-Pin Needle for Dermashine Pro / Balance, not Dermashine Duo RF.")

        if (
            row.get("company") == "Solta Medical"
            and row.get("brand") == "Thermage"
            and (
                "302784868" in row.get("article_url", "")
                or "bausch-health-s-aesthetic-business-solta-medical-earns" in row.get("article_url", "")
            )
        ):
            if row.get("event_group") == "commercial_performance":
                set_status(row, "promoted", "Verified against Bausch/Solta official PRNewswire release; promoted as brand/market-recognition evidence, not registration.")
                promotion_id = "promo_" + short_hash("solta_thermage_china_aaa_trademark_20260528")
                add_promotion_log(
                    promotions,
                    promotion_id=promotion_id,
                    product_id=row.get("product_id", ""),
                    seed_record_id="",
                    company_id=row.get("company_id", ""),
                    company="Solta Medical",
                    brand="Thermage",
                    source_key="briefing_official_solta_thermage_china_aaa_trademark_20260528",
                    source_type="official_company_press_release",
                    field_name="company_market_presence",
                    promoted_value="Thermage received AAA Well-Known Trademark Certification from China Trademark Association.",
                    source_url=SOLTA_THERMAGE_CHINA_AAA_SOURCE_URL,
                    evidence_title="Solta Medical Thermage receives AAA Well-Known Trademark Certification in China",
                    confidence="official_company_press_release",
                    note="Brand/market recognition evidence; not a product launch, registration approval, or new indication.",
                )
                add_verified_event(
                    events,
                    row,
                    mapping_status="mapped_product",
                    verification_status="verified_official_company_release",
                    promotion_status="promoted_to_log",
                    source_type="official_company_press_release",
                    source_url=SOLTA_THERMAGE_CHINA_AAA_SOURCE_URL,
                    official_title="Solta Medical Thermage receives AAA Well-Known Trademark Certification in China",
                    official_excerpt="Thermage received AAA Well-Known Trademark Certification from China Trademark Association; this is brand/market recognition rather than a new regulatory approval.",
                    target="evidence_promotion_log",
                    promotion_id=promotion_id,
                    remaining_gap="No registration or indication promotion from this item.",
                )
            else:
                set_status(row, "rejected_event_class", "Official source confirms trademark/brand-recognition news, not a product launch, registration approval, or indication expansion.")

        if row.get("needs_fulltext_rescue") == "yes":
            if (
                "/sec-filings/" in text
                or " form 3" in text
                or " form 4" in text
                or " form 144" in text
                or "rsu" in text
            ):
                set_status(row, "rejected_event_class", "SEC ownership/trading filing; not a product, indication, registration, or channel update.")
                row["needs_fulltext_rescue"] = "no"
                row["body_quality"] = "closed_no_fulltext_needed"
            elif "bpdcn" in text or "decupaz" in text or "pivekimab" in text:
                set_status(row, "excluded_scope_unlinked", "Official FDA/AbbVie item is an oncology BPDCN drug approval, outside the medical-aesthetics product scope.")
                row["needs_fulltext_rescue"] = "no"
                row["body_quality"] = "closed_no_fulltext_needed"
            elif "kaneka" in text and "management plan" in text:
                set_status(row, "rejected_event_class", "Management-plan news does not provide an official medical-aesthetics product launch fact for LACTIF.")
                row["needs_fulltext_rescue"] = "no"
                row["body_quality"] = "closed_no_fulltext_needed"
            elif "agereverse" in text or "wellness retreat" in text or "longevity supplement" in text or "franchise expansion" in text:
                set_status(row, "excluded_scope_unlinked", "Consumer wellness/supplement/service-platform item; outside upstream medical-aesthetics product master scope.")
                row["needs_fulltext_rescue"] = "no"
                row["body_quality"] = "closed_no_fulltext_needed"

        if row.get("company") == "Alpha Aesthetics" and row.get("event_group") == "channel_coverage":
            set_status(row, "promoted", "Verified against PRNewswire company release sourced to Alpha Aesthetics Partners.")
            promotion_id = "promo_" + short_hash("alpha_preva_channel_20260519")
            add_promotion_log(
                promotions,
                promotion_id=promotion_id,
                product_id="",
                seed_record_id="",
                company_id="",
                company="Alpha Aesthetics Partners",
                brand="",
                source_key="briefing_official_alpha_preva_channel_20260519",
                source_type="official_company_press_release",
                field_name="company_market_presence",
                promoted_value="Partnership with Preva Aesthetics adds Denver, Colorado and Encinitas, California presence.",
                source_url=ALPHA_SOURCE_URL,
                evidence_title="Alpha Aesthetics expands in California and enters Colorado through Preva Aesthetics",
                confidence="official_company_press_release",
                note="Company not yet mapped to master company_id.",
            )
            add_verified_event(
                events,
                row,
                mapping_status="company_not_in_master",
                verification_status="verified_official_company_release",
                promotion_status="promoted_to_log",
                source_type="official_company_press_release",
                source_url=ALPHA_SOURCE_URL,
                official_title="Alpha Aesthetics expands in California and enters Colorado",
                official_excerpt="Partnership with Preva Aesthetics adds Colorado and California presence.",
                target="evidence_promotion_log",
                promotion_id=promotion_id,
                remaining_gap="Create or map Alpha Aesthetics Partners in Company_Master.",
            )

        if "bimini health tech" in text or "puregraft" in text or "dermapose" in text:
            row.update(
                {
                    "company_id": "co_5b08be1c42ac",
                    "product_id": "prod_25cdeaba7107; prod_3707a90c6115",
                    "company": "Bimini Health Tech",
                    "brand": "Puregraft / Dermapose",
                    "product_name": "Fat Transfer Product Suites",
                    "market_or_jurisdiction": "EU / Global",
                }
            )
            set_status(row, "promoted", "Verified against Bimini/PRNewswire release; master records REC_1056 Dermapose and REC_1057 Puregraft are present.")
            add_verified_event(
                events,
                row,
                mapping_status="mapped_product",
                verification_status="verified_official_company_release",
                promotion_status="promoted",
                source_type="official_company_press_release",
                source_url=BIMINI_SOURCE_URL,
                official_title="Bimini Health Tech Achieves EU MDR Certification",
                official_excerpt="EU MDR certification expands Puregraft and Dermapose fat transfer product suites in Europe.",
                target="product_master; registration_evidence",
                promotion_id="promo_" + short_hash("bimini_product_master_gap_closed_20260602"),
                remaining_gap="",
            )

        if row.get("company") == "Apyx Medical":
            if row.get("product_id") == "prod_89a443ecc902" and row.get("event_group") == "regulatory_approval":
                set_status(row, "promoted", "Verified against Apyx official release for expanded FDA 510(k) clearance adding power liposuction to AYON.")
                promotion_id = "promo_" + short_hash("apyx_ayon_expanded_510k_20260511")
                add_registration_row(
                    manual_rows,
                    {
                        "product_id": "prod_89a443ecc902",
                        "seed_record_id": "REC_0939",
                        "company_id": "co_ea11172b59bc",
                        "company": "Apyx Medical",
                        "brand": "AYON",
                        "jurisdiction": "US",
                        "regulator": "FDA",
                        "regulatory_pathway": "510(k) expanded clearance",
                        "status": "Expanded 510(k) clearance for power liposuction capability",
                        "registration_no": "Expanded clearance number not disclosed in company release",
                        "approval_date": "2026-05-11",
                        "expiry_date": "",
                        "registered_name": "AYON Body Contouring System",
                        "approved_indication": "",
                        "intended_use": "Expanded clearance adds power liposuction capability to AYON Body Contouring System.",
                        "legal_manufacturer": "Apyx Medical Corporation",
                        "local_holder": "",
                        "source_key": "briefing_official_apyx_ayon_expanded_510k_20260511",
                        "source_url": APYX_AYON_SOURCE_URL,
                        "source_type": "official_company_press_release",
                        "evidence_title": "Apyx Medical receives expanded FDA 510(k) clearance for AYON",
                        "evidence_excerpt": "Official release says FDA expanded AYON clearance to include power liposuction capability.",
                        "checked_at": now_iso(),
                        "reviewed_by": "Codex",
                        "review_status": "auto_cross_checked_official_company_claim",
                        "confidence": "official_company_press_release_pending_510k_number",
                    },
                )
                add_promotion_log(
                    promotions,
                    promotion_id=promotion_id,
                    product_id="prod_89a443ecc902",
                    seed_record_id="REC_0939",
                    company_id="co_ea11172b59bc",
                    company="Apyx Medical",
                    brand="AYON",
                    source_key="briefing_official_apyx_ayon_expanded_510k_20260511",
                    source_type="official_company_press_release",
                    field_name="registration_evidence",
                    promoted_value="Expanded FDA 510(k) clearance claim for AYON power liposuction capability",
                    source_url=APYX_AYON_SOURCE_URL,
                    evidence_title="Apyx Medical receives expanded FDA 510(k) clearance for AYON",
                    confidence="official_company_press_release_pending_510k_number",
                    note="FDA 510(k) number for expanded clearance not disclosed in release.",
                )
                add_verified_event(
                    events,
                    row,
                    mapping_status="mapped_product",
                    verification_status="verified_official_company_claim",
                    promotion_status="promoted",
                    source_type="official_company_press_release",
                    source_url=APYX_AYON_SOURCE_URL,
                    official_title="Apyx Medical receives expanded FDA 510(k) clearance for AYON",
                    official_excerpt="Expanded FDA 510(k) clearance adds power liposuction capability to AYON.",
                    target="registration_evidence",
                    promotion_id=promotion_id,
                    remaining_gap="Expanded 510(k) number still needs FDA database lookup.",
                )
            elif row.get("event_group") == "regulatory_approval":
                set_status(row, "rejected_event_class", "Latest official Apyx regulatory event is AYON expanded 510(k); this row is not a new Renuvion approval.")

        if row.get("company") == "PharmaResearch / PR Bio" and "pharmaresearch" in row.get("article_url", "").lower():
            if row.get("event_group") == "channel_coverage":
                set_status(row, "promoted", "Verified against PharmaResearch PRNewswire release for Rejuran Western Europe roadshow.")
                promotion_id = "promo_" + short_hash("pharmaresearch_rejuran_western_europe_roadshow_20260514")
                add_promotion_log(
                    promotions,
                    promotion_id=promotion_id,
                    product_id=row.get("product_id", ""),
                    seed_record_id="",
                    company_id=row.get("company_id", ""),
                    company="PharmaResearch / PR Bio",
                    brand="Rejuran",
                    source_key="briefing_official_pharmaresearch_rejuran_roadshow_20260514",
                    source_type="official_company_press_release",
                    field_name="company_market_presence",
                    promoted_value="Rejuran Western Europe roadshow across five markets",
                    source_url=PHARMARESEARCH_SOURCE_URL,
                    evidence_title="PharmaResearch concludes Western Europe roadshow for Rejuran in five markets",
                    confidence="official_company_press_release",
                    note="Market-development evidence; product registration still requires regulator/IFU evidence.",
                )
                add_verified_event(
                    events,
                    row,
                    mapping_status="mapped_product",
                    verification_status="verified_official_company_release",
                    promotion_status="promoted_to_log",
                    source_type="official_company_press_release",
                    source_url=PHARMARESEARCH_SOURCE_URL,
                    official_title="PharmaResearch Western Europe roadshow for Rejuran",
                    official_excerpt="Official release describes a Rejuran roadshow across five Western European markets.",
                    target="evidence_promotion_log",
                    promotion_id=promotion_id,
                    remaining_gap="Does not prove registration or indication expansion.",
                )
            elif row.get("event_group") in {"commercial_performance", "product_launch"}:
                set_status(row, "rejected_event_class", "Official source supports channel/market development, not commercial performance or product launch.")
        if row.get("company") == "BioPlus" and "pharmaresearch" in row.get("article_url", "").lower():
            set_status(row, "rejected_product_mismatch", "Official source is PharmaResearch/Rejuran, not BioPlus.")

    for row in candidates:
        if row.get("status") == "promoted":
            stats["promoted"] += 1
        elif row.get("status") == "verified_gap":
            stats["verified_gap"] += 1
        elif row.get("status", "").startswith("rejected"):
            stats["rejected"] += 1
    stats["promotion_log_rows"] = len(promotions)
    stats["gap_rows"] = len(gaps)
    return stats


def main() -> None:
    candidate_fields, candidates = read_csv(BRIEFING_CANDIDATES_PATH)
    manual_fields, manual_rows = read_csv(MANUAL_OFFICIAL_EVIDENCE_PATH)
    promotion_fields, promotions = read_csv(MANUAL_PROMOTION_LOG_PATH)
    verified_fields, verified_events = read_csv(VERIFIED_EVENTS_PATH)
    rescue_fields, rescue_rows = read_csv(FULLTEXT_RESCUE_PATH)
    _, gap_rows = read_csv(PRODUCT_GAP_PATH)

    if not promotion_fields:
        promotion_fields = PROMOTION_FIELDS
    if not verified_fields:
        verified_fields = VERIFIED_EVENT_FIELDS
    if not rescue_fields:
        rescue_fields = FULLTEXT_FIELDS
    if not manual_fields:
        raise SystemExit(f"Missing manual evidence header: {MANUAL_OFFICIAL_EVIDENCE_PATH}")

    attempted_rescue, rescued = rescue_fulltext(candidates, rescue_rows)
    stats = promote_core_rules(candidates, manual_rows, promotions, verified_events, gap_rows)

    write_csv(BRIEFING_CANDIDATES_PATH, candidate_fields, candidates)
    write_csv(MANUAL_OFFICIAL_EVIDENCE_PATH, manual_fields, manual_rows)
    write_csv(MANUAL_PROMOTION_LOG_PATH, promotion_fields, promotions)
    write_csv(VERIFIED_EVENTS_PATH, VERIFIED_EVENT_FIELDS, verified_events)
    write_csv(FULLTEXT_RESCUE_PATH, FULLTEXT_FIELDS, rescue_rows)
    write_csv(PRODUCT_GAP_PATH, PRODUCT_GAP_FIELDS, gap_rows)

    pending = sum(1 for row in candidates if row.get("status") == "candidate_unverified")
    needs_rescue = sum(1 for row in candidates if row.get("needs_fulltext_rescue") == "yes")
    lines = [
        "# Briefing Update Pipeline Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Results",
        "",
        f"- Full-text fetch attempted: {attempted_rescue}; rescued: {rescued}; still needing rescue: {needs_rescue}.",
        f"- Promoted briefing candidates: {stats['promoted']}.",
        f"- Verified but waiting for master mapping: {stats['verified_gap']}.",
        f"- Rejected after official-source review: {stats['rejected']}.",
        f"- Still unverified after this pass: {pending}.",
        f"- Verified update event rows: {len(verified_events)}.",
        f"- Product/company gap rows: {len(gap_rows)}.",
        "",
        "## Durable Outputs",
        "",
        f"- Verified update events: `{VERIFIED_EVENTS_PATH}`",
        f"- Full-text rescue cache: `{FULLTEXT_RESCUE_PATH}`",
        f"- Product/company gap candidates: `{PRODUCT_GAP_PATH}`",
        f"- Manual official evidence source: `{MANUAL_OFFICIAL_EVIDENCE_PATH}`",
        f"- Manual promotion log source: `{MANUAL_PROMOTION_LOG_PATH}`",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        {
            "summary": str(SUMMARY_PATH),
            "fulltext_attempted": attempted_rescue,
            "fulltext_rescued": rescued,
            "promoted": stats["promoted"],
            "verified_gap": stats["verified_gap"],
            "rejected": stats["rejected"],
            "pending": pending,
            "verified_events": len(verified_events),
            "gap_rows": len(gap_rows),
        }
    )


if __name__ == "__main__":
    main()

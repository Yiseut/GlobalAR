#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
PRODUCT_SPEC = DATA_DIR / "product_specification_evidence.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"
REACQUIRE_QUEUE = AUDIT_DIR / "e_group_reacquire_official_source_queue_latest.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_local_spec_indication_apply_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_local_spec_indication_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_local_spec_indication_skipped_latest.csv"
CANDIDATES_CSV = AUDIT_DIR / "e_group_local_spec_indication_candidates_latest.csv"


INDICATION_FIELDS = [
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "jurisdiction",
    "regulator",
    "regulatory_pathway",
    "status",
    "registration_no",
    "approval_date",
    "expiry_date",
    "registered_name",
    "approved_indication",
    "intended_use",
    "legal_manufacturer",
    "local_holder",
    "source_key",
    "source_url",
    "source_type",
    "evidence_title",
    "evidence_excerpt",
    "official_description_exact",
    "official_description_source_field",
    "field_note",
    "checked_at",
    "reviewed_by",
    "review_status",
    "confidence",
]


GENERIC_PRODUCT_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "plus",
    "pro",
    "max",
    "body",
    "skin",
    "hair",
    "face",
    "facial",
    "deep",
    "fine",
    "light",
    "line",
    "lines",
    "system",
    "platform",
    "series",
    "family",
    "device",
    "devices",
    "laser",
    "lasers",
    "filler",
    "fillers",
    "thread",
    "threads",
    "medical",
    "aesthetic",
    "aesthetics",
    "therapy",
    "treatment",
    "treatments",
    "professional",
    "solution",
    "solutions",
}


CLINICAL_TERMS = [
    "wrinkle",
    "rhytid",
    "fold",
    "nasolabial",
    "laxity",
    "tighten",
    "lifting",
    "rejuvenation",
    "resurfacing",
    "scar",
    "acne",
    "melasma",
    "pigment",
    "vascular",
    "vein",
    "hair removal",
    "hair regrowth",
    "adiposity",
    "fat",
    "cellulite",
    "body contour",
    "contouring",
    "volume",
    "augmentation",
    "correction",
    "restore",
    "hydration",
    "vaginal",
    "vulvovaginal",
    "urinary",
    "pelvic",
    "lesion",
    "cryosurgery",
    "skin condition",
    "skin lesions",
    "skin tightening",
    "soft tissue",
    "muscle",
    "dermatological",
    "general surgical",
    "electrocoagulation",
    "hemostasis",
    "皱纹",
    "法令纹",
    "松弛",
    "紧致",
    "提升",
    "嫩肤",
    "祛斑",
    "色素",
    "血管",
    "脱毛",
    "脂肪",
    "塑形",
    "容量",
    "填充",
    "修复",
    "痤疮",
]


HARD_REJECT_FRAGMENTS = [
    "not intended to treat or diagnose",
    "candidate link can be promoted",
    "registration facts still require",
    "do not present this row as a confirmed approved indication",
    "consult the user manual for detailed information on indications",
    "indications and contraindications",
    "indications and important safety information",
    "privacy policy",
    "cookie",
    "terms of use",
    "all products at www",
    "wide range of conditions",
    "wide range of treatments",
    "range of indications",
    "multiple indications",
    "more than 100 indications",
    "approved for publishing",
    "built for beauty and designed to perform",
    "designed to perform.trusted",
    "preparation and administration",
    "in its intended use scenario",
    "likely risk associated with the use of the device",
    "adverse reactions",
    "contraindications",
    "clinical evaluation",
    "scientific papers",
    "clinical papers",
    "product features",
    "manufacturer warranty",
    "needle gauge",
    "available in",
    "source:",
    "title:",
    "literature",
    "objective of this study",
    "animal model",
]


WRONG_PATH_FRAGMENTS = [
    "ophthalmic anterior and posterior segment",
    "intraocular",
    "bony defect",
    "orthopedic",
    "orthopaedic",
    "laparoscopic",
    "urologic",
    "animal health",
    "lancing device",
    "blood collection",
    "bone graft",
    "dental implant",
]


OTHER_PRODUCT_MARKERS = {
    "emface",
    "emsculpt",
    "emsella",
    "vanquish",
    "unison",
    "skinstylus",
    "vbeam",
    "nordlys",
    "gentle pro",
    "revolax",
    "volus",
    "the chaeum",
    "hydrafil",
    "vom",
    "giselleligne",
    "stylage",
    "restylane",
    "juvederm",
    "botox",
    "dysport",
    "xeomin",
    "profhilo",
}

REJECT_URL_PARTS = [
    "/publications",
    "/clinical-papers",
    "/press-releases",
    "news-release",
    "see-it-in-action",
    "/story/",
    "/promotions/",
]


OFFICIAL_DOMAIN_HINTS = {
    "agnesmedical",
    "asclepion",
    "btl",
    "bodybybtl",
    "btlaesthetics",
    "beautyhealth",
    "bioplus",
    "breramedical",
    "bodyhealth",
    "brymill",
    "candelamedical",
    "classys",
    "cromapharma",
    "dekalaser",
    "deleo",
    "dermaheal",
    "fillmed",
    "galderma",
    "fotona",
    "inmodemd",
    "cutera",
    "cynosure",
    "lutronic",
    "venus",
    "wontech",
    "ibsa",
    "merz",
    "alma",
    "solta",
    "sciton",
    "storzmedical",
    "syneron-candela",
    "thermiva",
}


EXPLICIT_PATTERNS = [
    re.compile(r"\bindicated for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bindicated for use in\b[:\s-]*(.+)", re.I),
    re.compile(r"\bis indicated for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bare indicated for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bintended for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bis intended for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bare intended for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bis intended to\b[:\s-]*(.+)", re.I),
    re.compile(r"\bare intended to\b[:\s-]*(.+)", re.I),
    re.compile(r"\bintended use\b[:\s-]*(.+)", re.I),
    re.compile(r"\bintended purpose\b[:\s-]*(.+)", re.I),
    re.compile(r"\bapproved for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bfda cleared for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bcleared for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bfor the correction of\b[:\s-]*(.+)", re.I),
    re.compile(r"\bfor the treatment of\b[:\s-]*(.+)", re.I),
    re.compile(r"适应症[:：\s-]*(.+)", re.I),
    re.compile(r"适用于[:：\s-]*(.+)", re.I),
    re.compile(r"用于[:：\s-]*(.+)", re.I),
]

WEAK_USED_PATTERNS = [
    re.compile(r"\bis used for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bare used for\b[:\s-]*(.+)", re.I),
    re.compile(r"\bused to treat\b[:\s-]*(.+)", re.I),
    re.compile(r"\bused for\b[:\s-]*(.+)", re.I),
]


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?。；;])\s+|\s+\[\.\.\.\]\s+|\n+")
TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.I)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def squash(value: str) -> str:
    text = clean(value)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*\[\.\.\.\]\s*", " [...] ", text)
    return text.strip(" -|")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def stable_id(prefix: str, *parts: Any) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def product_tokens(row: dict[str, str]) -> set[str]:
    label = " ".join(
        [
            clean(row.get("brand")),
            clean(row.get("standard_product_name")),
            clean(row.get("registered_name")),
            clean(row.get("core_product")),
        ]
    )
    tokens = {token.casefold() for token in TOKEN_RE.findall(label)}
    return {token for token in tokens if token not in GENERIC_PRODUCT_TOKENS}


def company_domain_tokens(row: dict[str, str]) -> set[str]:
    tokens = {token.casefold() for token in TOKEN_RE.findall(clean(row.get("company")))}
    return {token for token in tokens if token not in {"inc", "llc", "ltd", "medical", "aesthetics", "pharma"}}


def source_is_official(row: dict[str, str], product: dict[str, str]) -> bool:
    confidence = clean(row.get("confidence"))
    url = clean(row.get("source_page_url"))
    low_url = url.casefold()
    if any(part in low_url for part in REJECT_URL_PARTS):
        return False
    if confidence == "official_site_spec_candidate":
        return True
    domain = domain_of(url)
    if not domain:
        return False
    domain_blob = domain.replace("-", "").replace(".", "")
    if any(hint in domain_blob for hint in OFFICIAL_DOMAIN_HINTS):
        return True
    if any(token in domain_blob for token in product_tokens(product)):
        return True
    if any(token in domain_blob for token in company_domain_tokens(product)):
        return True
    return False


def has_indication(row: dict[str, str]) -> bool:
    return bool(clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")))


def text_has_clinical_term(text: str) -> bool:
    low = text.casefold()
    return any(term in low for term in CLINICAL_TERMS)


def contains_bad_text(text: str) -> str:
    low = text.casefold()
    for fragment in HARD_REJECT_FRAGMENTS:
        if fragment in low:
            return f"bad_text:{fragment}"
    for fragment in WRONG_PATH_FRAGMENTS:
        if fragment in low:
            return f"wrong_path:{fragment}"
    return ""


def looks_truncated(text: str) -> bool:
    low = text.casefold().strip(" .;:-")
    if re.search(r"\b(gene|coagu|trea|fol|nee|hemo|differen|middermal|subcutaneou|dermatologica)$", low):
        return True
    if re.search(r"\b(coagu|fol|nee|hemo)\b", low):
        return True
    if re.search(r"\b(middle part o|dynamic wrinkles and fol|hemostasis is nee|hemo igniterf|dermatological and cannula)\b", low):
        return True
    if re.search(r"\b\d+\s*(w|g|mm|nm|mhz|hz)$", low) and not re.search(r"755|808|1064|2940|1550|1940", low):
        return True
    if re.search(r"\b(title|source|details|documents?|request|view product)\b", low):
        return True
    if low.count(";") > 2:
        return True
    return False


def owns_candidate(candidate: str, product: dict[str, str], full_text: str) -> bool:
    tokens = product_tokens(product)
    if not tokens:
        return False
    low_candidate = candidate.casefold()
    low_full = full_text.casefold()
    if any(token in low_candidate for token in tokens):
        return True
    if any(token in low_full for token in tokens):
        return True
    return False


def has_other_product_collision(candidate: str, product: dict[str, str]) -> bool:
    own = product_tokens(product)
    low = candidate.casefold()
    for marker in OTHER_PRODUCT_MARKERS:
        marker_key = marker.replace(" ", "")
        if marker_key in own:
            continue
        if marker in low:
            return True
    return False


def sentence_windows(text: str) -> list[tuple[str, bool]]:
    normalized = squash(text)
    parts = [part.strip(" -|") for part in SENTENCE_SPLIT_RE.split(normalized) if part.strip(" -|")]
    windows: list[tuple[str, bool]] = []
    for idx, part in enumerate(parts):
        strong_match = next((pattern.search(part) for pattern in EXPLICIT_PATTERNS if pattern.search(part)), None)
        weak_match = next((pattern.search(part) for pattern in WEAK_USED_PATTERNS if pattern.search(part)), None)
        if strong_match:
            windows.append((part[strong_match.start() :], True))
        elif weak_match and re.search(r"\bindications?\b|适应症", part, re.I):
            windows.append((part[weak_match.start() :], False))
    if not windows:
        strong_match = next((pattern.search(normalized) for pattern in EXPLICIT_PATTERNS if pattern.search(normalized)), None)
        if strong_match:
            windows.append((normalized[strong_match.start() : strong_match.start() + 700], True))
    return windows


def normalize_candidate(window: str) -> str:
    text = squash(window)
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^(title|source|details?)\s*:\s*", "", text, flags=re.I)
    text = text.replace(" [...] ", "; ")
    text = re.sub(r"\s+-\s+", "; ", text)
    text = re.sub(r"\s*;\s*;\s*", "; ", text)
    text = re.sub(r"\s*\|\s*", "; ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"^(for the correction of)\s+", "Indicated for correction of ", text, flags=re.I)
    text = re.sub(r"^(for the treatment of)\s+", "Indicated for treatment of ", text, flags=re.I)
    if len(text) > 620:
        text = text[:620].rsplit(" ", 1)[0].rstrip(" ,;") + "."
    if not text.endswith((".", "。")):
        text += "."
    first = text[0].upper() + text[1:] if text and text[0].isascii() else text
    return first


def extract_candidate(row: dict[str, str], product: dict[str, str]) -> tuple[str, str]:
    source_text = squash(" ".join([clean(row.get("evidence_excerpt")), clean(row.get("spec_value"))]))
    if not source_text:
        return "", "empty_text"
    bad = contains_bad_text(source_text)
    if bad:
        return "", bad
    if not source_is_official(row, product):
        return "", "source_not_official_enough"
    for window, strong in sentence_windows(source_text):
        candidate = normalize_candidate(window)
        if len(candidate) < 45:
            continue
        if len(candidate) > 680:
            continue
        if not strong and "indications" not in source_text.casefold():
            continue
        if looks_truncated(candidate):
            return "", "truncated_or_navigation_text"
        bad = contains_bad_text(candidate)
        if bad:
            return "", bad
        if not text_has_clinical_term(candidate):
            continue
        if has_other_product_collision(candidate, product):
            return "", "mentions_other_product"
        if not owns_candidate(candidate, product, source_text):
            return "", "product_token_not_near_candidate"
        if re.search(r"\b(is|are)?\s*intended for (a|an|one|single) (use|application) only\b", candidate, re.I):
            return "", "packaging_single_use_not_indication"
        return candidate, "accepted"
    return "", "no_usable_explicit_window"


def candidate_score(row: dict[str, str], candidate: str) -> int:
    score = 0
    confidence = clean(row.get("confidence"))
    query_type = clean(row.get("source_query_type"))
    if confidence == "official_site_spec_candidate":
        score += 25
    if confidence == "official_search_excerpt_spec_candidate":
        score += 12
    if "ifu" in query_type or "label" in query_type or "catalog" in query_type:
        score += 16
    if "official_page" in query_type or "product_official" in query_type:
        score += 10
    if re.search(r"\bindicated for|is indicated|are indicated|intended use|intended purpose|intended for|approved for|cleared for\b", candidate, re.I):
        score += 18
    if re.search(r"\bused for|used to|treatment of|for the treatment|for the correction\b", candidate, re.I):
        score += 8
    if ".pdf" in clean(row.get("source_page_url")).casefold():
        score += 6
    return score


def make_manual_row(product: dict[str, str], source: dict[str, str], indication: str, checked_at: str) -> dict[str, str]:
    product_id = clean(product.get("product_id"))
    source_url = clean(source.get("source_page_url"))
    source_type = clean(source.get("source_query_type")) or "product_specification_evidence"
    return {
        "product_id": product_id,
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": "Global",
        "regulator": "Official product/IFU/source text",
        "regulatory_pathway": "local product specification evidence extraction",
        "status": "Official use/indication wording extracted from existing official source text",
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": clean(product.get("registered_name") or product.get("standard_product_name") or product.get("brand")),
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("manufactured_by") or product.get("company")),
        "local_holder": clean(product.get("local_holder")),
        "source_key": stable_id("egroup_local_spec_indication", product_id, source_url, indication),
        "source_url": source_url,
        "source_type": source_type,
        "evidence_title": clean(source.get("source_title")) or f"{clean(product.get('company'))} {clean(product.get('brand'))}",
        "evidence_excerpt": clean(source.get("evidence_excerpt"))[:1200],
        "official_description_exact": indication,
        "official_description_source_field": "product_specification_evidence.evidence_excerpt",
        "field_note": (
            "Auto-promoted only when an existing official source/specification candidate contained explicit intended-use or indication wording "
            "and matched the product token. Generic SEO text, competitor mentions, packaging-only text and wrong clinical paths were skipped."
        ),
        "checked_at": checked_at,
        "reviewed_by": "auto_local_spec_indication_extraction_20260601",
        "review_status": "auto_promoted_local_official_source_indication",
        "confidence": "high_confidence_local_official_source_text",
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    product_fields, product_rows = read_csv(PRODUCT_MASTER)
    spec_fields, spec_rows = read_csv(PRODUCT_SPEC)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, queue_rows = read_csv(REACQUIRE_QUEUE)
    _ = product_fields, spec_fields

    target_seeds = {clean(row.get("seed_record_id")) for row in queue_rows if clean(row.get("seed_record_id"))}
    product_by_id = {clean(row.get("product_id")): row for row in product_rows if clean(row.get("product_id"))}
    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}

    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    existing_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")),
        )
        for row in manual_rows
    }

    spec_by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in spec_rows:
        product = product_by_id.get(clean(row.get("product_id")))
        if not product:
            continue
        seed = clean(product.get("seed_record_id"))
        if seed in target_seeds and seed not in existing_seed_with_indication:
            spec_by_seed[seed].append(row)

    accepted_by_seed: dict[str, tuple[int, dict[str, str], str]] = {}
    candidate_rows: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    skip_counter: Counter[str] = Counter()

    for seed in sorted(target_seeds):
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "product_not_found_or_excluded"})
            skip_counter["product_not_found_or_excluded"] += 1
            continue
        if seed in existing_seed_with_indication:
            skipped.append({"seed_record_id": seed, "reason": "already_has_manual_indication"})
            skip_counter["already_has_manual_indication"] += 1
            continue
        rows = spec_by_seed.get(seed, [])
        if not rows:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "no_local_spec_rows",
                }
            )
            skip_counter["no_local_spec_rows"] += 1
            continue
        best_reason = "no_candidate"
        for spec in rows:
            indication, reason = extract_candidate(spec, product)
            if not indication:
                best_reason = reason
                skip_counter[reason] += 1
                continue
            score = candidate_score(spec, indication)
            candidate_row = {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "score": str(score),
                "confidence": clean(spec.get("confidence")),
                "source_query_type": clean(spec.get("source_query_type")),
                "source_page_url": clean(spec.get("source_page_url")),
                "source_title": clean(spec.get("source_title")),
                "indication": indication,
            }
            candidate_rows.append(candidate_row)
            current = accepted_by_seed.get(seed)
            if current is None or score > current[0]:
                accepted_by_seed[seed] = (score, spec, indication)
        if seed not in accepted_by_seed:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": best_reason,
                    "local_spec_rows": str(len(rows)),
                }
            )

    new_rows: list[dict[str, str]] = []
    applied: list[dict[str, str]] = []
    for seed, (score, spec, indication) in sorted(accepted_by_seed.items(), key=lambda item: (-item[1][0], item[0])):
        product = product_by_seed[seed]
        manual = make_manual_row(product, spec, indication, checked_at)
        key = (
            clean(manual.get("product_id")),
            clean(manual.get("source_url")),
            clean(manual.get("official_description_exact")),
        )
        if key in existing_keys:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "duplicate_exact_key",
                }
            )
            skip_counter["duplicate_exact_key"] += 1
            continue
        existing_keys.add(key)
        new_rows.append(manual)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "score": str(score),
                "source_url": clean(spec.get("source_page_url")),
                "confidence": clean(spec.get("confidence")),
                "source_query_type": clean(spec.get("source_query_type")),
                "indication": indication,
            }
        )

    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_local_spec_indication_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or INDICATION_FIELDS
        for field in INDICATION_FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)
    else:
        backup_path = None

    candidate_fields = [
        "seed_record_id",
        "product_id",
        "company",
        "brand",
        "standard_product_name",
        "score",
        "confidence",
        "source_query_type",
        "source_page_url",
        "source_title",
        "indication",
    ]
    applied_fields = [
        "seed_record_id",
        "product_id",
        "company",
        "brand",
        "standard_product_name",
        "score",
        "source_url",
        "confidence",
        "source_query_type",
        "indication",
    ]
    skipped_fields = ["seed_record_id", "company", "brand", "standard_product_name", "reason", "local_spec_rows"]

    write_csv(CANDIDATES_CSV, candidate_fields, candidate_rows)
    write_csv(APPLIED_CSV, applied_fields, applied)
    write_csv(SKIPPED_CSV, skipped_fields, skipped)

    summary = {
        "checked_at": checked_at,
        "target_queue_rows": len(target_seeds),
        "candidate_rows": len(candidate_rows),
        "candidate_products": len({row["seed_record_id"] for row in candidate_rows}),
        "applied_rows": len(applied),
        "skipped_products": len(skipped),
        "backup_path": str(backup_path) if backup_path else "",
        "skip_reasons": dict(skip_counter.most_common()),
        "applied_by_confidence": dict(Counter(row["confidence"] for row in applied)),
        "applied_by_query_type": dict(Counter(row["source_query_type"] for row in applied)),
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "applied_csv": str(APPLIED_CSV),
            "skipped_csv": str(SKIPPED_CSV),
            "candidates_csv": str(CANDIDATES_CSV),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

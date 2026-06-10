#!/usr/bin/env python3
"""
Sync verified China NMPA records from the sibling registration project.

The output is intentionally a generated evidence layer. It only maps records to
existing global product_master rows and never creates new companies/products.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DEFAULT_REGISTRATION_MASTER = Path(r"E:\shared\code\registration\output\master\registration_records_master.csv")
DEFAULT_PRODUCT_MASTER = DATA_DIR / "product_master.csv"
DEFAULT_OUTPUT = DATA_DIR / "manual_nmpa_registration_evidence.csv"

EVIDENCE_FIELDS = [
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

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "for",
    "with",
    "without",
    "of",
    "in",
    "to",
    "by",
    "from",
    "or",
    "type",
    "unit",
    "units",
    "system",
    "device",
    "devices",
    "medical",
    "company",
    "co",
    "ltd",
    "limited",
    "inc",
    "gmbh",
    "sa",
    "sas",
    "ab",
    "bv",
    "llc",
    "plc",
    "corp",
    "corporation",
    "laboratoires",
    "pharma",
    "pharmaceutical",
    "pharmaceuticals",
    "biotech",
    "science",
    "technologies",
    "technology",
    "manufacturing",
    "manufacturer",
    "north",
    "america",
    "korea",
    "korean",
    "china",
    "chinese",
    "ireland",
    "sodium",
    "hyaluronate",
    "hyaluronic",
    "acid",
    "gel",
    "injection",
    "injectable",
    "filler",
    "fillers",
    "cross",
    "crosslinked",
    "linked",
    "modified",
    "pre",
    "filled",
    "syringe",
    "implants",
    "implant",
    "dermal",
    "tissue",
    "soft",
    "lidocaine",
    "volume",
    "classic",
    "line",
    "form",
    "lift",
    "deep",
    "ultra",
    "balance",
    "shape",
    "skin",
    "body",
    "face",
    "polyl",
    "poly",
    "lactic",
    "lactide",
    "pcl",
    "plla",
    "pdlla",
    "pmma",
    "cmc",
    "ha",
    "rf",
    "med",
}
COMPANY_STOPWORDS = STOPWORDS | {"q", "m", "s", "d", "l", "xc", "df", "hd", "ld", "vl", "cpt", "flx", "plus"}
PRODUCT_STRONG = {
    "aesthefill",
    "algeness",
    "artecoll",
    "bellafill",
    "belotero",
    "botox",
    "cutegel",
    "daxxify",
    "dermalax",
    "desirial",
    "dysport",
    "ellanse",
    "endymed",
    "hyabell",
    "hyafilia",
    "hutox",
    "infini",
    "intracel",
    "juvederm",
    "letybo",
    "maili",
    "monalisa",
    "olidia",
    "precise",
    "princess",
    "profhilo",
    "radiesse",
    "restylane",
    "revolax",
    "saypha",
    "sculptra",
    "thermage",
    "viscoderm",
    "volbella",
    "volift",
    "voluma",
    "volux",
    "xeomin",
    "yvoire",
}
COMPANY_STRONG = {
    "abbvie",
    "across",
    "adoderm",
    "advanced",
    "aesthetic",
    "allergan",
    "bnc",
    "cha",
    "chem",
    "croma",
    "cromapharma",
    "endymed",
    "fillmed",
    "galderma",
    "genoss",
    "ghimas",
    "hugel",
    "huons",
    "ipsen",
    "jeisys",
    "jetema",
    "kylane",
    "lg",
    "lutronic",
    "meditech",
    "merz",
    "qmed",
    "regen",
    "revance",
    "sinclair",
    "solta",
    "suneva",
    "symatese",
    "vivacy",
}
VARIANT_TERMS = {"vl", "df", "hd", "ld", "xc", "flx", "cpt", "5d", "m", "s"}
TRACK_TERMS = {
    "ha": {"hyaluronic", "dermal", "filler", "ha"},
    "pcl": {"pcl", "biostimulator"},
    "plla": {"plla", "pdlla", "biostimulator", "lactic"},
    "caha": {"calcium", "hydroxylapatite", "caha"},
    "botulinum": {"neurotoxin", "botulinum", "toxin"},
    "raw_thermage_rf": {"radiofrequency", "monopolar", "rf"},
    "raw_rf": {"radiofrequency", "rf"},
    "raw_microneedle": {"microneedle", "radiofrequency", "rf"},
    "raw_pmma": {"pmma"},
    "raw_agarose": {"agarose"},
}


def norm(value: Any) -> str:
    return str(value or "").strip()


def normalize_ascii(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return (
        text.replace("q med", "qmed")
        .replace("fill med", "fillmed")
        .replace("croma pharma", "cromapharma")
        .replace("juv derm", "juvederm")
    )


def tokens(value: str, mode: str) -> list[str]:
    stop = COMPANY_STOPWORDS if mode == "company" else STOPWORDS
    keep = COMPANY_STRONG if mode == "company" else PRODUCT_STRONG | VARIANT_TERMS
    out: list[str] = []
    for token in re.findall(r"[a-z0-9]+", normalize_ascii(value)):
        if len(token) < 2:
            continue
        if token in stop and token not in keep:
            continue
        out.append(token)
    return out


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def direct_product_blob(product: dict[str, str]) -> str:
    return " ".join(
        norm(product.get(field))
        for field in [
            "brand",
            "standard_product_name",
            "registered_name",
            "core_product",
            "feature_tags",
            "material_taxonomy_l1_cn",
            "material_taxonomy_l2_cn",
            "material_taxonomy_l3_cn",
            "material_taxonomy_path_cn",
            "technology_path_l1",
            "technology_path_l2",
        ]
    )


def direct_company_blob(product: dict[str, str]) -> str:
    return " ".join(
        norm(product.get(field))
        for field in ["company", "legal_manufacturer", "marketing_holder", "manufactured_by"]
    )


def registration_product_text(record: dict[str, str]) -> str:
    return " ".join(norm(record.get(field)) for field in ["brand", "aliases", "product_name", "official_product_name", "record_id"])


def registration_company_text(record: dict[str, str]) -> str:
    return " ".join(
        norm(record.get(field))
        for field in ["registrant", "company_short", "official_registrant", "manufacturer_group_key", "manufacturer_group"]
    )


def exact_phrase_bonus(record: dict[str, str], product_blob: str) -> int:
    for field in ["brand", "aliases", "product_name", "official_product_name"]:
        parts = [
            token
            for token in normalize_ascii(norm(record.get(field))).split()
            if token not in STOPWORDS or token in PRODUCT_STRONG or token in VARIANT_TERMS
        ]
        if len(parts) >= 2 and any(token in PRODUCT_STRONG for token in parts):
            for size in range(min(len(parts), 4), 1, -1):
                for start in range(0, len(parts) - size + 1):
                    if " ".join(parts[start : start + size]) in product_blob:
                        return 80
        if len(parts) == 1 and parts[0] in PRODUCT_STRONG and re.search(rf"\b{re.escape(parts[0])}\b", product_blob):
            return 35
    return 0


def company_phrase_hit(record: dict[str, str], company_blob: str) -> bool:
    for field in ["manufacturer_group_key", "registrant", "official_registrant", "company_short", "manufacturer_group"]:
        parts = [
            token
            for token in normalize_ascii(norm(record.get(field))).split()
            if token not in COMPANY_STOPWORDS or token in COMPANY_STRONG
        ]
        for size in range(min(len(parts), 3), 0, -1):
            for start in range(0, len(parts) - size + 1):
                phrase = " ".join(parts[start : start + size])
                if len(phrase) >= 3 and phrase in company_blob:
                    return True
    return False


def track_compatible(record: dict[str, str], product: dict[str, str]) -> int:
    terms = TRACK_TERMS.get(norm(record.get("track")))
    if not terms:
        return 0
    text = normalize_ascii(
        " ".join(
            norm(product.get(field))
            for field in [
                "commercial_path_l1",
                "commercial_path_l2",
                "material_taxonomy_l1_cn",
                "material_taxonomy_l2_cn",
                "material_taxonomy_l3_cn",
                "material_taxonomy_path_cn",
                "technology_path_l1",
                "technology_path_l2",
                "material_or_energy_source",
                "feature_tags",
            ]
        )
    )
    return 20 if any(term in text for term in terms) else 0


def build_product_index(products: list[dict[str, str]]) -> list[dict[str, Any]]:
    index = []
    for product in products:
        product_blob = normalize_ascii(direct_product_blob(product))
        company_blob = normalize_ascii(direct_company_blob(product))
        index.append(
            {
                "product": product,
                "product_tokens": set(tokens(direct_product_blob(product), "product")),
                "company_tokens": set(tokens(direct_company_blob(product), "company")),
                "product_blob": product_blob,
                "company_blob": company_blob,
                "brand_terms": set(tokens(product.get("brand", ""), "product")),
            }
        )
    return index


def score_match(record: dict[str, str], item: dict[str, Any]) -> dict[str, Any]:
    record_product_tokens = set(tokens(registration_product_text(record), "product"))
    record_company_tokens = set(tokens(registration_company_text(record), "company"))
    product_hits = sorted((record_product_tokens & item["product_tokens"]) - STOPWORDS)
    strong_hits = sorted(set(product_hits) & PRODUCT_STRONG)
    variant_hits = sorted(set(product_hits) & VARIANT_TERMS)
    company_hits = sorted((record_company_tokens & item["company_tokens"]) - COMPANY_STOPWORDS)
    phrase_bonus = exact_phrase_bonus(record, item["product_blob"])
    has_company_phrase = company_phrase_hit(record, item["company_blob"])

    score = 0
    score += 22 * len(product_hits) + 34 * len(strong_hits) + 8 * len(variant_hits)
    score += 26 * len(company_hits) + (35 if has_company_phrase else 0)
    score += phrase_bonus
    if strong_hits:
        score += 30
    if company_hits or has_company_phrase:
        score += 25
    score += track_compatible(record, item["product"])

    missing_specific = (item["brand_terms"] & (PRODUCT_STRONG | VARIANT_TERMS)) - set(product_hits) - record_product_tokens
    missing_specific = {token for token in missing_specific if token not in COMPANY_STRONG}
    if missing_specific and not phrase_bonus:
        score -= 55 * len(missing_specific)
    if not strong_hits and phrase_bonus < 80:
        score -= 45
    if not (company_hits or has_company_phrase) and phrase_bonus < 80:
        score -= 35

    return {
        "score": score,
        "product_hits": product_hits,
        "strong_hits": strong_hits,
        "company_hits": company_hits,
        "phrase_bonus": phrase_bonus,
        "company_phrase": has_company_phrase,
        "missing_specific": sorted(missing_specific),
    }


def pathway_for(record: dict[str, str]) -> str:
    record_type = norm(record.get("record_type"))
    if "药" in record_type:
        return "Drug approval"
    certificate = norm(record.get("certificate_no"))
    if "国药准字" in certificate:
        return "Drug approval"
    if "器械" in record_type or "械注" in certificate:
        return "Medical device registration"
    return record_type or "NMPA registration"


def evidence_row(record: dict[str, str], product: dict[str, str], checked_at: str) -> dict[str, str]:
    is_drug = "药" in norm(record.get("record_type")) or "国药准字" in norm(record.get("certificate_no"))
    official_scope = norm(record.get("official_scope")) or norm(record.get("scope_full")) or norm(record.get("indication_description"))
    official_indication = (
        norm(record.get("official_indication"))
        or norm(record.get("primary_indication"))
        or norm(record.get("approved_indications"))
    )
    if is_drug:
        # Drug-query fields in the China project can be less stable than the
        # structured botulinum master row; avoid importing an unrelated matched
        # drug name when the certificate-level record is already curated.
        registered_name = norm(record.get("product_name")) or norm(record.get("brand")) or norm(record.get("official_product_name"))
        legal_manufacturer = norm(record.get("registrant")) or norm(record.get("company_short")) or norm(record.get("official_registrant"))
        approval_date = norm(record.get("approval_date")) or norm(record.get("official_approval_date"))
        expiry_date = norm(record.get("valid_until")) or norm(record.get("official_valid_until"))
    else:
        registered_name = norm(record.get("official_product_name")) or norm(record.get("product_name")) or norm(record.get("brand"))
        legal_manufacturer = norm(record.get("official_registrant")) or norm(record.get("registrant")) or norm(record.get("company_short"))
        approval_date = norm(record.get("official_approval_date")) or norm(record.get("approval_date"))
        expiry_date = norm(record.get("official_valid_until")) or norm(record.get("valid_until"))
    source_title = norm(record.get("source_title"))
    source_account = norm(record.get("source_account"))
    source_url = norm(record.get("source_url"))
    official_source = norm(record.get("official_source")) or "NMPA registration project master"
    field_note = (
        "Imported from the sibling China registration project after matching to an existing global product. "
        "No China-only company or product was created in the global master."
    )
    return {
        "product_id": product.get("product_id", ""),
        "seed_record_id": product.get("seed_record_id", ""),
        "company_id": product.get("company_id", ""),
        "company": product.get("company", ""),
        "brand": product.get("brand", ""),
        "jurisdiction": "CN",
        "regulator": "NMPA",
        "regulatory_pathway": pathway_for(record),
        "status": "NMPA verified",
        "registration_no": norm(record.get("certificate_no")),
        "approval_date": approval_date,
        "expiry_date": expiry_date,
        "registered_name": registered_name,
        "approved_indication": official_indication,
        "intended_use": official_scope,
        "legal_manufacturer": legal_manufacturer,
        "local_holder": "",
        "source_key": "registration_project_nmpa_master",
        "source_url": source_url,
        "source_type": "official_nmpa_registration_project",
        "evidence_title": f"{norm(record.get('certificate_no'))} / {registered_name}",
        "evidence_excerpt": " | ".join(
            part
            for part in [
                official_source,
                source_account,
                source_title,
                norm(record.get("evidence_text"))[:300],
            ]
            if part
        ),
        "official_description_exact": official_scope,
        "official_description_source_field": "official_scope" if official_scope else "",
        "field_note": field_note,
        "checked_at": checked_at,
        "reviewed_by": "registration_project_sync",
        "review_status": "auto_cross_checked",
        "confidence": "official_regulator_record",
    }


def run(args: argparse.Namespace) -> int:
    products = load_csv(args.product_master)
    records = load_csv(args.registration_master)
    index = build_product_index(products)
    checked_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    promoted: list[dict[str, str]] = []
    audit_rows: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    verified_records = [
        record
        for record in records
        if norm(record.get("official_status")) == "verified" and norm(record.get("certificate_no"))
    ]

    for record in verified_records:
        candidates = []
        for item in index:
            result = score_match(record, item)
            if result["score"] > 0:
                candidates.append((result, item["product"]))
        candidates.sort(
            key=lambda pair: (
                pair[0]["score"],
                pair[0]["phrase_bonus"],
                len(pair[0]["strong_hits"]),
                len(pair[0]["company_hits"]),
                -len(norm(pair[1].get("brand"))),
            ),
            reverse=True,
        )
        top = candidates[0] if candidates else ({}, {})
        second_score = candidates[1][0]["score"] if len(candidates) > 1 else 0
        result, product = top
        has_product_identity = bool(result.get("strong_hits")) or int(result.get("phrase_bonus") or 0) >= 80
        has_company = bool(result.get("company_hits")) or bool(result.get("company_phrase"))
        decision = "skip_no_match"
        review_reason = ""
        if candidates:
            decision = "review"
            if not has_product_identity:
                review_reason = "missing_product_identity"
            elif not has_company and int(result.get("phrase_bonus") or 0) < 80:
                review_reason = "missing_company_confirmation"
            elif result.get("score", 0) < args.min_score:
                review_reason = "score_below_threshold"
            elif result.get("score", 0) - second_score < args.min_margin and int(result.get("phrase_bonus") or 0) < 80:
                review_reason = "ambiguous_top_match"
            if (
                result.get("score", 0) >= args.min_score
                and has_product_identity
                and (has_company or int(result.get("phrase_bonus") or 0) >= 80)
                and (
                    result.get("score", 0) - second_score >= args.min_margin
                    or int(result.get("phrase_bonus") or 0) >= 80
                    or has_company
                )
            ):
                decision = "promote"
        pair_key = (product.get("product_id", ""), norm(record.get("certificate_no")))
        if decision == "promote" and pair_key not in seen_pairs:
            promoted.append(evidence_row(record, product, checked_at))
            seen_pairs.add(pair_key)
        elif decision == "promote":
            decision = "skip_duplicate"

        audit_product = product if decision in {"promote", "skip_duplicate"} or has_product_identity else {}
        audit_rows.append(
            {
                "decision": decision,
                "review_reason": review_reason,
                "score": result.get("score", ""),
                "second_score": second_score,
                "record_id": record.get("record_id", ""),
                "track": record.get("track", ""),
                "origin": record.get("origin", ""),
                "certificate_no": record.get("certificate_no", ""),
                "nmpa_brand": record.get("brand", ""),
                "nmpa_aliases": record.get("aliases", ""),
                "nmpa_product_name": record.get("product_name", ""),
                "nmpa_registrant": record.get("registrant", ""),
                "nmpa_manufacturer_group": record.get("manufacturer_group", ""),
                "official_product_name": record.get("official_product_name", ""),
                "official_scope": record.get("official_scope", ""),
                "matched_product_id": audit_product.get("product_id", ""),
                "matched_company": audit_product.get("company", ""),
                "matched_brand": audit_product.get("brand", ""),
                "matched_product": audit_product.get("standard_product_name", ""),
                "matched_material_taxonomy_l1": audit_product.get("material_taxonomy_l1_cn", ""),
                "matched_material_taxonomy_l2": audit_product.get("material_taxonomy_l2_cn", ""),
                "matched_material_taxonomy_l3": audit_product.get("material_taxonomy_l3_cn", ""),
                "matched_material_taxonomy_path": audit_product.get("material_taxonomy_path_cn", ""),
                "product_hits": ";".join(result.get("product_hits", [])),
                "strong_hits": ";".join(result.get("strong_hits", [])),
                "company_hits": ";".join(result.get("company_hits", [])),
                "phrase_bonus": result.get("phrase_bonus", ""),
                "company_phrase": result.get("company_phrase", ""),
                "missing_specific": ";".join(result.get("missing_specific", [])),
            }
        )

    write_csv(args.output, EVIDENCE_FIELDS, promoted)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_fields = list(audit_rows[0].keys()) if audit_rows else ["decision"]
    latest_audit = AUDIT_DIR / "nmpa_registration_project_match_latest.csv"
    stamped_audit = AUDIT_DIR / f"nmpa_registration_project_match_{timestamp}.csv"
    write_csv(latest_audit, audit_fields, audit_rows)
    write_csv(stamped_audit, audit_fields, audit_rows)

    decision_counts = Counter(row["decision"] for row in audit_rows)
    track_counts = Counter(row["track"] for row in audit_rows if row["decision"] == "promote")
    company_counts = Counter(row["matched_company"] for row in audit_rows if row["decision"] == "promote")
    summary = [
        "# NMPA registration-project sync",
        "",
        f"- Generated: {checked_at}",
        f"- Registration master: `{args.registration_master}`",
        f"- Global product master: `{args.product_master}`",
        f"- Output evidence: `{args.output}`",
        f"- Verified NMPA source records scanned: {len(verified_records)}",
        f"- Promoted evidence rows: {len(promoted)}",
        f"- Review rows: {decision_counts.get('review', 0)}",
        f"- No-match rows: {decision_counts.get('skip_no_match', 0)}",
        "",
        "## Promoted by Track",
        "",
    ]
    for track, count in track_counts.most_common():
        summary.append(f"- {track or 'unknown'}: {count}")
    summary.extend(["", "## Top Matched Companies", ""])
    for company, count in company_counts.most_common(12):
        summary.append(f"- {company}: {count}")
    summary.extend(
        [
            "",
            "## Guardrail",
            "",
            "- This sync only maps to existing global product_master rows.",
            "- China-only companies/products remain out of the global master.",
            "- Review rows need human confirmation before promotion.",
            "",
            f"- Latest audit CSV: `{latest_audit}`",
            f"- Timestamped audit CSV: `{stamped_audit}`",
        ]
    )
    latest_md = AUDIT_DIR / "nmpa_registration_project_sync_latest.md"
    stamped_md = AUDIT_DIR / f"nmpa_registration_project_sync_{timestamp}.md"
    latest_md.write_text("\n".join(summary) + "\n", encoding="utf-8")
    stamped_md.write_text("\n".join(summary) + "\n", encoding="utf-8")

    print(
        {
            "verified_records": len(verified_records),
            "promoted": len(promoted),
            "decisions": dict(decision_counts),
            "output": str(args.output),
            "audit": str(latest_audit),
        }
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync NMPA evidence from registration project into generated layer.")
    parser.add_argument("--registration-master", type=Path, default=DEFAULT_REGISTRATION_MASTER)
    parser.add_argument("--product-master", type=Path, default=DEFAULT_PRODUCT_MASTER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-score", type=int, default=115)
    parser.add_argument("--min-margin", type=int, default=10)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))

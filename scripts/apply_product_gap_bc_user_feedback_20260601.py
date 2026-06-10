#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"
OPT_QUEUE = AUDIT_DIR / "product_gap_optimization_queue_latest.csv"
PRODUCT_MASTER = DATA_DIR / "product_master.csv"
MANUAL_FACT = DATA_DIR / "manual_product_fact_evidence.csv"
MANUAL_REG = DATA_DIR / "manual_official_indication_evidence.csv"


C_OVERRIDES = {
    "REC_0622_RRS_HA_LONG_LASTING": {
        "lead_official_url": "https://www.skintechpharmagroup.com/products/injectables/rrs-ha-long-lasting/",
        "lead_spec_url": "https://www.skintechpharmagroup.com/products/injectables/rrs-ha-long-lasting/",
        "lead_registration_url": "https://www.skintechpharmagroup.com/products/injectables/rrs-ha-long-lasting/",
        "jurisdiction": "EU",
        "regulator": "CE 1014 / Notified Body",
        "status": "User confirmed CE Class III claim; product-specific certificate number not captured.",
        "source_type": "user_confirmed_ce_product_page_lead",
        "confidence": "user_confirmed_ce_claim_pending_certificate_number",
    },
    "REC_0625": {
        "lead_official_url": "https://www.skintechpharmagroup.com/products/injectables/xl-hair/",
        "lead_spec_url": "https://www.skintechpharmagroup.com/products/injectables/xl-hair/",
        "lead_registration_url": "https://www.skintechpharmagroup.com/products/injectables/xl-hair/",
        "jurisdiction": "EU",
        "regulator": "CE / Notified Body",
        "status": "User confirmed CE medical-device claim; product-specific certificate number not captured.",
        "source_type": "user_confirmed_ce_product_page_lead",
        "confidence": "user_confirmed_ce_claim_pending_certificate_number",
    },
    "REC_0095": {
        "lead_official_url": "https://dsddeluxe.de/",
        "lead_spec_url": "https://dsddeluxe.de/",
        "lead_registration_url": "",
        "jurisdiction": "Global",
        "regulator": "Not applicable",
        "status": "User confirmed daily hair-care/cosmetic product; medical-device registration not required.",
        "source_type": "user_confirmed_non_device_cosmetic_status",
        "confidence": "user_confirmed_registration_not_required",
        "registration_not_required": True,
    },
    "REC_0932": {
        "lead_official_url": "https://www.caregen.com/",
        "lead_spec_url": "http://www.dermaheal.co.kr/",
        "lead_registration_url": "https://www.caregen.com/",
        "jurisdiction": "EU / KR",
        "regulator": "CE / KFDA-MFDS follow-up",
        "status": "User confirmed CE/KFDA registration claim for Aquashine; exact public certificate number not captured.",
        "source_type": "user_confirmed_ce_korea_registration_lead",
        "confidence": "user_confirmed_registration_claim_pending_number",
    },
    "REC_0964": {
        "lead_official_url": "https://www.cosmo-korea.com/",
        "lead_spec_url": "https://konepharma.co.kr/",
        "lead_registration_url": "https://www.nmpa.gov.cn/",
        "jurisdiction": "CN / EU",
        "regulator": "NMPA / CE follow-up",
        "status": "User confirmed Elravie NMPA and CE registration claim; exact public source URL/number to be resolved.",
        "source_type": "user_confirmed_nmpa_ce_registration_lead",
        "confidence": "user_confirmed_registration_claim_pending_number",
    },
    "REC_0487": {
        "lead_official_url": "https://reanzen.com/filler-device/?lang=en",
        "lead_spec_url": "https://reanzen.com/filler-device/?lang=en",
        "lead_registration_url": "https://www.reanzen.com",
        "jurisdiction": "Global / KR",
        "regulator": "Manufacturer / KFDA-MFDS follow-up",
        "status": "User confirmed Reanzen official product-line page as specification lead; registration public number not captured.",
        "source_type": "user_confirmed_official_product_spec_registration_lead",
        "confidence": "user_confirmed_official_lead_pending_registration_number",
    },
}


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_unique(rows: list[dict[str, str]], key_fields: list[str], new_rows: list[dict[str, str]]) -> int:
    existing = {tuple(clean(row.get(field)) for field in key_fields) for row in rows}
    added = 0
    for row in new_rows:
        key = tuple(clean(row.get(field)) for field in key_fields)
        if key in existing:
            continue
        rows.append(row)
        existing.add(key)
        added += 1
    return added


def product_lookup() -> dict[str, dict[str, str]]:
    _, rows = read_csv(PRODUCT_MASTER)
    by_id = {clean(row.get("product_id")): row for row in rows if clean(row.get("product_id"))}
    by_seed = {clean(row.get("seed_record_id")): row for row in rows if clean(row.get("seed_record_id"))}
    return {**by_id, **by_seed}


def infer_registration(row: dict[str, str]) -> dict[str, str]:
    seed = clean(row.get("seed_record_id"))
    override = C_OVERRIDES.get(seed, {})
    url = clean(override.get("lead_registration_url") or row.get("lead_registration_url"))
    blob = " ".join([url, clean(row.get("company")), clean(row.get("brand")), clean(row.get("standard_product_name"))]).lower()
    if override:
        return {
            "jurisdiction": clean(override.get("jurisdiction")) or "Global",
            "regulator": clean(override.get("regulator")) or "Regulatory follow-up",
            "status": clean(override.get("status")),
            "source_type": clean(override.get("source_type")) or "user_confirmed_registration_lead",
            "confidence": clean(override.get("confidence")) or "user_confirmed_registration_lead",
        }
    if "accessdata.fda.gov" in blob or "/pdf" in blob and "k" in blob:
        return {
            "jurisdiction": "US",
            "regulator": "FDA",
            "status": "User confirmed FDA candidate link; exact registration fields pending source parsing.",
            "source_type": "user_confirmed_fda_candidate_link",
            "confidence": "user_confirmed_regulator_candidate",
        }
    if any(token in blob for token in ["nmpa", "mp.weixin.qq.com"]):
        return {
            "jurisdiction": "CN",
            "regulator": "NMPA follow-up",
            "status": "User confirmed NMPA/China registration candidate link; exact official NMPA record pending source parsing.",
            "source_type": "user_confirmed_nmpa_candidate_link",
            "confidence": "user_confirmed_registration_candidate",
        }
    if any(token in blob for token in ["ce", "mdr", "eudamed", "notified", "alma-medicaldevices"]):
        return {
            "jurisdiction": "EU",
            "regulator": "CE-MDR / Notified Body follow-up",
            "status": "User confirmed CE/MDR candidate link; exact certificate number pending or not publicly available.",
            "source_type": "user_confirmed_ce_mdr_candidate_link",
            "confidence": "user_confirmed_registration_candidate",
        }
    return {
        "jurisdiction": "Global",
        "regulator": "Regulatory follow-up",
        "status": "User confirmed registration candidate link; exact public registration number pending source parsing.",
        "source_type": "user_confirmed_registration_candidate_link",
        "confidence": "user_confirmed_registration_candidate",
    }


def merged_row(row: dict[str, str]) -> dict[str, str]:
    merged = dict(row)
    override = C_OVERRIDES.get(clean(row.get("seed_record_id")), {})
    for key in ["lead_official_url", "lead_spec_url", "lead_registration_url"]:
        if clean(override.get(key)):
            merged[key] = clean(override.get(key))
    return merged


def fact_row(row: dict[str, str], product: dict[str, str], group: str, field_name: str, url: str, checked_at: str) -> dict[str, str]:
    label = {
        "official_product_page": "official product/family page",
        "official_specification_candidate": "official specification/IFU candidate",
        "registration_candidate_url": "registration candidate link",
    }.get(field_name, field_name)
    return {
        "fact_id": stable_id("pfact", "bc_feedback_20260601", product.get("product_id"), field_name, url),
        "product_id": clean(product.get("product_id")),
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "product_family_id": clean(row.get("product_family_ids")).split(",")[0].strip(),
        "standard_product_name": clean(product.get("standard_product_name")),
        "priority": "P3",
        "fact_group": field_name,
        "field_name": field_name,
        "field_value": url,
        "source_url": url,
        "evidence_title": f"{clean(product.get('company'))} / {clean(product.get('brand'))} {label}",
        "evidence_excerpt": f"{group}: user confirmed this candidate link can be promoted as system evidence lead. Exact certificates still require official regulator/IFU/certificate parsing.",
        "source_type": "official_product_page" if field_name == "official_product_page" else ("official_product_document" if field_name == "official_specification_candidate" else "user_confirmed_registration_candidate_link"),
        "confidence": "user_confirmed_official_candidate_promoted",
        "captured_at": checked_at,
        "promoted_at": checked_at,
        "review_status": "user_confirmed",
        "note": "product_gap_BC_user_feedback_20260601",
    }


def registration_row(row: dict[str, str], product: dict[str, str], checked_at: str) -> dict[str, str] | None:
    row = merged_row(row)
    seed = clean(row.get("seed_record_id"))
    override = C_OVERRIDES.get(seed, {})
    url = clean(row.get("lead_registration_url"))
    if not url and not override.get("registration_not_required"):
        return None
    inferred = infer_registration(row)
    registered_name = clean(product.get("brand")) or clean(row.get("brand")) or clean(row.get("standard_product_name"))
    return {
        "product_id": clean(product.get("product_id")),
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": inferred["jurisdiction"],
        "regulator": inferred["regulator"],
        "regulatory_pathway": "user-confirmed candidate link / regulatory status",
        "status": inferred["status"],
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": registered_name,
        "approved_indication": "",
        "intended_use": "",
        "legal_manufacturer": clean(product.get("legal_manufacturer")) or clean(product.get("company")),
        "local_holder": "",
        "source_key": stable_id("bc_reg", product.get("product_id"), url or inferred["status"], inferred["regulator"]),
        "source_url": url or clean(row.get("lead_spec_url") or row.get("lead_official_url")),
        "source_type": inferred["source_type"],
        "evidence_title": f"{registered_name} user-confirmed regulatory evidence lead",
        "evidence_excerpt": inferred["status"],
        "official_description_exact": "",
        "official_description_source_field": "",
        "field_note": "Candidate/regulatory-status evidence only; do not present as exact certificate number or approved indication until source text is parsed.",
        "checked_at": checked_at,
        "reviewed_by": "user_feedback_product_gap_BC_20260601",
        "review_status": "user_confirmed_registration_candidate_or_not_required",
        "confidence": inferred["confidence"],
    }


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    _, queue_rows = read_csv(OPT_QUEUE)
    products = product_lookup()
    target_rows = [
        merged_row(row)
        for row in queue_rows
        if clean(row.get("optimization_group")) in {"B_regulatory_leads", "C_official_url_leads"}
    ]

    fact_fields, fact_existing = read_csv(MANUAL_FACT)
    reg_fields, reg_existing = read_csv(MANUAL_REG)
    shutil.copy2(MANUAL_FACT, MANUAL_FACT.with_name(f"{MANUAL_FACT.stem}_backup_before_bc_feedback_{stamp}{MANUAL_FACT.suffix}"))
    shutil.copy2(MANUAL_REG, MANUAL_REG.with_name(f"{MANUAL_REG.stem}_backup_before_bc_feedback_{stamp}{MANUAL_REG.suffix}"))

    new_facts: list[dict[str, str]] = []
    new_regs: list[dict[str, str]] = []
    missing_products: list[str] = []
    by_group: Counter[str] = Counter()
    for row in target_rows:
        product = products.get(clean(row.get("product_id"))) or products.get(clean(row.get("seed_record_id")))
        if not product:
            missing_products.append(clean(row.get("seed_record_id")) or clean(row.get("product_id")))
            continue
        group = clean(row.get("optimization_group"))
        by_group[group] += 1
        if clean(row.get("lead_official_url")):
            new_facts.append(fact_row(row, product, group, "official_product_page", clean(row.get("lead_official_url")), checked_at))
        if clean(row.get("lead_spec_url")):
            new_facts.append(fact_row(row, product, group, "official_specification_candidate", clean(row.get("lead_spec_url")), checked_at))
        if clean(row.get("lead_registration_url")):
            new_facts.append(fact_row(row, product, group, "registration_candidate_url", clean(row.get("lead_registration_url")), checked_at))
        reg = registration_row(row, product, checked_at)
        if reg:
            new_regs.append(reg)

    added_facts = append_unique(fact_existing, ["fact_id"], new_facts)
    added_regs = append_unique(reg_existing, ["source_key"], new_regs)
    write_csv(MANUAL_FACT, fact_fields, fact_existing)
    write_csv(MANUAL_REG, reg_fields, reg_existing)

    summary = {
        "generated_at": checked_at,
        "target_rows": len(target_rows),
        "by_group": dict(by_group),
        "new_fact_candidates": len(new_facts),
        "manual_product_fact_rows_added": added_facts,
        "new_registration_candidates": len(new_regs),
        "manual_registration_rows_added": added_regs,
        "missing_products": missing_products,
        "c_overrides_applied": sorted(key for key in C_OVERRIDES if any(clean(row.get("seed_record_id")) == key for row in target_rows)),
    }
    out = AUDIT_DIR / f"product_gap_bc_user_feedback_apply_{stamp}.json"
    latest = AUDIT_DIR / "product_gap_bc_user_feedback_apply_latest.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

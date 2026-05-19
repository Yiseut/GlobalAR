"""Build a product-level verification gap queue.

This is the replacement direction for broad media crawling: read the existing
staging outputs, score product-line gaps, and produce a review queue for
product validation and product-line completion. It does not use the network and
does not promote candidate facts into master tables.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
PRODUCT_FAMILY_MASTER = DATA_DIR / "product_family_master.csv"
COMPANY_MASTER = DATA_DIR / "company_master.csv"
OFFICIAL_WEBSITE_MASTER = DATA_DIR / "official_website_master.csv"
PRODUCT_SPEC_EVIDENCE = DATA_DIR / "product_specification_evidence.csv"
REGISTRATION_EVIDENCE = DATA_DIR / "registration_evidence.csv"
OFFICIAL_INDICATION_EVIDENCE = DATA_DIR / "official_indication_evidence.csv"
MDR_CE_EVIDENCE = DATA_DIR / "mdr_ce_evidence_candidates.jsonl"


REGULATED_TRACKS = {"injectables", "ebd", "implants", "regenerative", "consumables", "surgical", "diagnostics"}


def clean(value: object) -> str:
    return str(value or "").strip()


def norm_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def compact_space(value: object) -> str:
    return re.sub(r"\s+", " ", clean(value))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows.append({str(key): clean(value) for key, value in obj.items()})
    return rows


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def pct(part: int, total: int) -> str:
    return f"{part / total * 100:.1f}%" if total else "0.0%"


def first_url(rows: list[dict[str, str]], *fields: str) -> str:
    for row in rows:
        for field in fields:
            value = clean(row.get(field))
            if value.startswith(("http://", "https://")):
                return value
    return ""


def split_ids(value: str) -> list[str]:
    return [part.strip() for part in clean(value).split(",") if part.strip()]


def company_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    output = {}
    for row in rows:
        name = clean(row.get("canonical_name") or row.get("company") or row.get("company_name") or row.get("name"))
        if name:
            output[norm_key(name)] = row
    return output


def product_company_index(products: list[dict[str, str]], company_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], Counter[str]]:
    companies = company_index(company_rows)
    company_names: dict[str, str] = {}
    product_counts: Counter[str] = Counter()
    for product in products:
        company_name = clean(product.get("company"))
        company_key = norm_key(company_name)
        if not company_key:
            continue
        product_counts[company_key] += 1
        company_names.setdefault(company_key, company_name)
    for company_key, product_count in product_counts.items():
        company = companies.setdefault(company_key, {})
        company.setdefault("company", company_names[company_key])
        company.setdefault("canonical_name", company_names[company_key])
        if not clean(company.get("product_count")):
            company["product_count"] = str(product_count)
    return companies, product_counts


def family_maps(rows: list[dict[str, str]]) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    by_record: dict[str, list[str]] = defaultdict(list)
    by_family: dict[str, dict[str, str]] = {}
    for row in rows:
        family_id = clean(row.get("product_family_id"))
        if not family_id:
            continue
        by_family[family_id] = row
        for record_id in split_ids(row.get("source_record_ids", "")):
            by_record[record_id].append(family_id)
    return by_record, by_family


def index_rows(rows: list[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = clean(row.get(field))
        if key:
            output[key].append(row)
    return output


def rows_for_product(
    by_product: dict[str, list[dict[str, str]]],
    by_seed: dict[str, list[dict[str, str]]],
    by_family: dict[str, list[dict[str, str]]],
    product_id: str,
    seed_record_id: str,
    family_ids: list[str],
) -> list[dict[str, str]]:
    seen = set()
    rows: list[dict[str, str]] = []
    for bucket in [by_product.get(product_id, []), by_seed.get(seed_record_id, [])]:
        for row in bucket:
            ident = id(row)
            if ident not in seen:
                seen.add(ident)
                rows.append(row)
    for family_id in family_ids:
        for row in by_family.get(family_id, []):
            ident = id(row)
            if ident not in seen:
                seen.add(ident)
                rows.append(row)
    return rows


def fuzzy_company_rows(rows_by_company: dict[str, list[dict[str, str]]], product: dict[str, str], fields: list[str], limit: int = 20) -> list[dict[str, str]]:
    company_key = norm_key(product.get("company"))
    rows = rows_by_company.get(company_key, [])
    tokens = [
        token
        for token in {
            norm_key(product.get("brand")),
            norm_key(product.get("standard_product_name")),
            norm_key(product.get("core_product")),
        }
        if len(token) >= 4
    ]
    if not tokens:
        return []
    matches: list[dict[str, str]] = []
    for row in rows:
        blob = norm_key(" ".join(clean(row.get(field)) for field in fields))
        if any(token in blob for token in tokens):
            matches.append(row)
            if len(matches) >= limit:
                break
    return matches


def is_weak_spec(row: dict[str, str]) -> bool:
    value = clean(row.get("spec_value"))
    excerpt = clean(row.get("evidence_excerpt"))
    if not value:
        return True
    if re.fullmatch(r"\d{1,3}\s*[A-Za-z%]?", value):
        return True
    lowered = excerpt.lower()
    if any(token in lowered for token in ["objstm", "endstream", "/type /page", "xref", "flatedecode"]):
        return True
    if "�" in excerpt:
        return True
    return False


def spec_tier(row: dict[str, str]) -> str:
    if is_weak_spec(row):
        return "C"
    confidence = clean(row.get("confidence"))
    if confidence == "official_site_spec_candidate":
        return "A"
    if confidence == "official_search_excerpt_spec_candidate":
        return "B"
    return "B"


def identity_missing(product: dict[str, str]) -> list[str]:
    required = [
        "company",
        "brand",
        "standard_product_name",
        "commercial_path_l1",
        "commercial_path_l2",
        "technology_path_l1",
        "material_or_energy_source",
    ]
    return [field for field in required if not clean(product.get(field))]


def evidence_counts(rows: list[dict[str, str]]) -> str:
    counter = Counter(clean(row.get("source_key") or row.get("confidence") or row.get("source_type")) for row in rows)
    return "; ".join(f"{key}:{value}" for key, value in counter.most_common(4) if key)


def md_cell(value: object) -> str:
    return clean(value).replace("|", "<br>").replace("\r", " ").replace("\n", " ")


def regulated_track(product: dict[str, str]) -> bool:
    return clean(product.get("commercial_path_l1")).lower() in REGULATED_TRACKS


def score_product(
    product: dict[str, str],
    company: dict[str, str],
    direct_websites: list[dict[str, str]],
    fuzzy_websites: list[dict[str, str]],
    direct_specs: list[dict[str, str]],
    fuzzy_specs: list[dict[str, str]],
    regs: list[dict[str, str]],
    indications: list[dict[str, str]],
    ce_candidates: list[dict[str, str]],
    missing_fields: list[str],
) -> tuple[int, str, list[str], str]:
    issues: list[str] = []
    score = 0
    if clean(product.get("verification_status")) == "unverified_seed":
        score += 18
        issues.append("master_unverified_seed")
    if missing_fields:
        score += 18
        issues.append("missing_identity:" + ",".join(missing_fields))
    if not direct_websites:
        score += 20
        issues.append("no_direct_official_product_or_family_url")
    if not direct_specs:
        score += 12
        issues.append("no_direct_spec_candidate")
    if regulated_track(product) and not regs:
        score += 24
        issues.append("no_registration_evidence")
    if regulated_track(product) and not indications:
        score += 12
        issues.append("no_official_indication")
    if not clean(product.get("verified_differentiator")):
        score += 8
        issues.append("no_reviewed_differentiator")

    company_priority = clean(company.get("priority_rank"))
    product_count = int(clean(company.get("product_count")) or "0") if clean(company.get("product_count")).isdigit() else 0
    try:
        priority_rank = int(float(company_priority)) if company_priority else 999
    except ValueError:
        priority_rank = 999
    if priority_rank <= 60 or product_count >= 8:
        score += 10
        issues.append("priority_company")
    if fuzzy_websites or fuzzy_specs or ce_candidates:
        score -= 6
        issues.append("has_review_leads")
    score = max(score, 0)
    if score >= 70:
        priority = "P0"
    elif score >= 50:
        priority = "P1"
    elif score >= 30:
        priority = "P2"
    else:
        priority = "P3"

    if not direct_websites and fuzzy_websites:
        action = "Review fuzzy official product/catalog/IFU URL and attach it to product/family."
    elif regulated_track(product) and not regs and ce_candidates:
        action = "Review regulator/CE/FDA candidates; promote only official certificate, IFU, FDA, EUDAMED, or label evidence."
    elif not direct_specs and fuzzy_specs:
        action = "Review A/B spec candidates and map useful rows to product/family; discard weak C rows."
    elif missing_fields:
        action = "Fix product identity fields before evidence promotion."
    elif clean(product.get("verification_status")) == "unverified_seed":
        action = "Cross-check product existence and core positioning against official product page."
    else:
        action = "Keep as lower-priority monitoring item."
    return score, priority, issues, action


def build_product_queue(args: argparse.Namespace) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    products = read_csv_rows(PRODUCT_MASTER)
    families = read_csv_rows(PRODUCT_FAMILY_MASTER)
    company_rows = read_csv_rows(COMPANY_MASTER)
    companies, company_product_counts = product_company_index(products, company_rows)
    websites = read_csv_rows(OFFICIAL_WEBSITE_MASTER)
    specs = read_csv_rows(PRODUCT_SPEC_EVIDENCE)
    registrations = read_csv_rows(REGISTRATION_EVIDENCE)
    indications = read_csv_rows(OFFICIAL_INDICATION_EVIDENCE)
    ce_candidates = read_jsonl_rows(MDR_CE_EVIDENCE)

    family_by_record, _family_by_id = family_maps(families)
    website_by_product = index_rows(websites, "product_id")
    website_by_family = index_rows(websites, "product_family_id")
    spec_by_product = index_rows(specs, "product_id")
    spec_by_family = index_rows(specs, "product_family_id")
    reg_by_product = index_rows(registrations, "product_id")
    reg_by_seed = index_rows(registrations, "seed_record_id")
    indication_by_product = index_rows(indications, "product_id")
    indication_by_seed = index_rows(indications, "seed_record_id")
    ce_by_family = index_rows(ce_candidates, "product_family_id")
    websites_by_company = index_rows(websites, "company")
    specs_by_company = index_rows(specs, "company")

    queue_rows: list[dict[str, object]] = []
    for product in products:
        family_ids = family_by_record.get(clean(product.get("seed_record_id")), [])
        company = companies.get(norm_key(product.get("company")), {})
        direct_websites = rows_for_product(website_by_product, {}, website_by_family, clean(product.get("product_id")), "", family_ids)
        direct_specs_all = rows_for_product(spec_by_product, {}, spec_by_family, clean(product.get("product_id")), "", family_ids)
        direct_specs = [row for row in direct_specs_all if spec_tier(row) in {"A", "B"}]
        fuzzy_websites = [] if direct_websites else fuzzy_company_rows(
            websites_by_company,
            product,
            ["brand", "product_family", "standard_product_name", "official_website_url", "source_title"],
            limit=8,
        )
        fuzzy_specs_all = [] if direct_specs else fuzzy_company_rows(
            specs_by_company,
            product,
            ["brand", "product_family", "standard_product_name", "source_title", "evidence_excerpt", "spec_value"],
            limit=12,
        )
        fuzzy_specs = [row for row in fuzzy_specs_all if spec_tier(row) in {"A", "B"}]
        regs = rows_for_product(reg_by_product, reg_by_seed, {}, clean(product.get("product_id")), clean(product.get("seed_record_id")), [])
        inds = rows_for_product(indication_by_product, indication_by_seed, {}, clean(product.get("product_id")), clean(product.get("seed_record_id")), [])
        ce_rows: list[dict[str, str]] = []
        for family_id in family_ids:
            ce_rows.extend(ce_by_family.get(family_id, []))
        missing_fields = identity_missing(product)
        score, priority, issues, action = score_product(
            product,
            company,
            direct_websites,
            fuzzy_websites,
            direct_specs,
            fuzzy_specs,
            regs,
            inds,
            ce_rows,
            missing_fields,
        )
        spec_tiers = Counter(spec_tier(row) for row in direct_specs_all + fuzzy_specs_all)
        company_product_count = clean(company.get("product_count"))
        queue_rows.append(
            {
                "priority": priority,
                "gap_score": score,
                "company": clean(product.get("company")),
                "company_product_count": company_product_count,
                "company_priority_rank": clean(company.get("priority_rank")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "product_id": clean(product.get("product_id")),
                "seed_record_id": clean(product.get("seed_record_id")),
                "product_family_ids": ", ".join(family_ids),
                "track": clean(product.get("commercial_path_l1")),
                "form": clean(product.get("commercial_path_l2")),
                "technology": clean(product.get("technology_path_l1")),
                "material_or_energy": clean(product.get("material_or_energy_source")),
                "verification_status": clean(product.get("verification_status")),
                "source_status": clean(product.get("source_status")),
                "direct_official_urls": len(direct_websites),
                "fuzzy_official_urls": len(fuzzy_websites),
                "direct_spec_candidates": len(direct_specs),
                "fuzzy_spec_candidates": len(fuzzy_specs),
                "spec_tier_A": spec_tiers.get("A", 0),
                "spec_tier_B": spec_tiers.get("B", 0),
                "spec_tier_C": spec_tiers.get("C", 0),
                "registration_rows": len(regs),
                "official_indication_rows": len(inds),
                "mdr_ce_candidate_rows": len(ce_rows),
                "lead_official_url": first_url(direct_websites or fuzzy_websites, "official_website_url", "source_url"),
                "lead_spec_url": first_url(direct_specs or fuzzy_specs, "source_page_url"),
                "lead_registration_url": first_url(regs or ce_rows, "source_url", "url"),
                "evidence_mix": evidence_counts(regs + inds + direct_specs[:5] + ce_rows[:5]),
                "issues": " | ".join(issues),
                "recommended_next_action": action,
            }
        )

    queue_rows.sort(key=lambda row: (str(row["priority"]), -int(row["gap_score"]), str(row["company"]).lower(), str(row["brand"]).lower()))
    if args.top_n:
        queue_rows = queue_rows[: args.top_n]

    missing_candidates = build_missing_product_candidates(products, websites, specs, args.missing_limit)
    summary = {
        "products": len(products),
        "families": len(families),
        "companies": len(company_product_counts),
        "company_index_source": "company_master.csv + product_master.csv" if company_rows else "product_master.csv derived",
        "queue_rows": len(queue_rows),
        "priority_counts": Counter(str(row["priority"]) for row in queue_rows),
        "unverified_seed": sum(1 for row in queue_rows if row["verification_status"] == "unverified_seed"),
        "no_direct_official_url": sum(1 for row in queue_rows if int(row["direct_official_urls"]) == 0),
        "no_direct_spec": sum(1 for row in queue_rows if int(row["direct_spec_candidates"]) == 0),
        "no_registration_on_regulated": sum(
            1 for row in queue_rows if str(row["track"]).lower() in REGULATED_TRACKS and int(row["registration_rows"]) == 0
        ),
        "missing_product_candidates": len(missing_candidates),
    }
    return queue_rows, missing_candidates, summary


def build_missing_product_candidates(
    products: list[dict[str, str]],
    websites: list[dict[str, str]],
    specs: list[dict[str, str]],
    limit: int,
) -> list[dict[str, object]]:
    known_company_brand = {(norm_key(row.get("company")), norm_key(row.get("brand"))) for row in products if clean(row.get("brand"))}
    known_company_product = {
        (norm_key(row.get("company")), norm_key(row.get("standard_product_name") or row.get("core_product")))
        for row in products
        if clean(row.get("standard_product_name") or row.get("core_product"))
    }
    grouped: dict[tuple[str, str], dict[str, object]] = {}

    def add_candidate(source_type: str, row: dict[str, str], name: str, url: str, confidence: str) -> None:
        company = clean(row.get("company"))
        candidate = compact_space(name)
        if not company or len(candidate) < 3:
            return
        ckey = norm_key(company)
        nkey = norm_key(candidate)
        if not nkey or (ckey, nkey) in known_company_brand or (ckey, nkey) in known_company_product:
            return
        key = (company, candidate)
        item = grouped.setdefault(
            key,
            {
                "company": company,
                "candidate_product_or_family": candidate,
                "source_types": set(),
                "source_count": 0,
                "source_domains": set(),
                "sample_url": "",
                "confidence_mix": Counter(),
                "review_status": "candidate",
            },
        )
        item["source_types"].add(source_type)  # type: ignore[index, union-attr]
        item["source_count"] = int(item["source_count"]) + 1
        if url:
            item["source_domains"].add(domain_of(url))  # type: ignore[index, union-attr]
            item["sample_url"] = item["sample_url"] or url
        item["confidence_mix"][confidence or "unknown"] += 1  # type: ignore[index, union-attr]

    for row in websites:
        if clean(row.get("entity_scope")) != "product_line":
            continue
        name = clean(row.get("standard_product_name") or row.get("product_family") or row.get("brand"))
        add_candidate("official_website_master", row, name, clean(row.get("official_website_url") or row.get("source_url")), clean(row.get("confidence")))

    for row in specs:
        name = clean(row.get("standard_product_name") or row.get("product_family") or row.get("brand"))
        if not name:
            continue
        add_candidate("product_specification_evidence", row, name, clean(row.get("source_page_url")), clean(row.get("confidence")))

    output: list[dict[str, object]] = []
    for item in grouped.values():
        confidence_mix: Counter[str] = item["confidence_mix"]  # type: ignore[assignment]
        output.append(
            {
                "company": item["company"],
                "candidate_product_or_family": item["candidate_product_or_family"],
                "source_count": item["source_count"],
                "source_types": "; ".join(sorted(item["source_types"])),  # type: ignore[arg-type]
                "source_domains": "; ".join(sorted(value for value in item["source_domains"] if value)),  # type: ignore[arg-type]
                "confidence_mix": "; ".join(f"{key}:{value}" for key, value in confidence_mix.most_common(4)),
                "sample_url": item["sample_url"],
                "review_status": item["review_status"],
            }
        )
    output.sort(key=lambda row: (-int(row["source_count"]), str(row["company"]).lower(), str(row["candidate_product_or_family"]).lower()))
    return output[:limit]


def write_summary(
    path: Path,
    queue_path: Path,
    missing_path: Path,
    summary: dict[str, object],
    queue_rows: list[dict[str, object]],
    generated_at: str,
) -> None:
    priority_counts: Counter[str] = summary["priority_counts"]  # type: ignore[assignment]
    p0_p1 = priority_counts.get("P0", 0) + priority_counts.get("P1", 0)
    total = int(summary["queue_rows"])
    top_rows = queue_rows[:20]
    lines = [
        "# Product Gap Verification Queue",
        "",
        f"Generated: {generated_at}",
        "",
        "## Executive Read",
        "",
        f"- Products in current master: {summary['products']} across {summary['companies']} companies.",
        f"- Company coverage source: {summary['company_index_source']}.",
        f"- Queue rows generated: {total}; P0/P1 review-first rows: {p0_p1}.",
        f"- Unverified seed rows in queue: {summary['unverified_seed']} ({pct(int(summary['unverified_seed']), total)}).",
        f"- Products without direct official product/family URL: {summary['no_direct_official_url']} ({pct(int(summary['no_direct_official_url']), total)}).",
        f"- Products without direct A/B spec candidate: {summary['no_direct_spec']} ({pct(int(summary['no_direct_spec']), total)}).",
        f"- Regulated products without registration evidence: {summary['no_registration_on_regulated']}.",
        f"- Possible product/family additions from existing website/spec signals: {summary['missing_product_candidates']}.",
        "",
        "## Operating Decision",
        "",
        "- Replace broad webpage/image continuation with this gap queue as the default worklist.",
        "- Promote nothing automatically: official product pages, IFU/catalogs, certificates, FDA/EUDAMED/regulator records remain review evidence until checked.",
        "- Use secondary/search-excerpt rows only as leads; do not merge them into product master without official-source confirmation.",
        "- Direct official URL/spec counts mean linked candidate evidence is present; they are not treated as reviewed facts.",
        "- Missing-product candidates are mined only from already stored website/spec signals; zero candidates is not proof that no product lines are missing.",
        "",
        "## Priority Meaning",
        "",
        "- P0: high-priority company/product with multiple blocking gaps.",
        "- P1: important product with missing direct evidence or regulated-market proof.",
        "- P2: useful review item, often with some fuzzy leads already present.",
        "- P3: lower-priority monitoring or mostly covered product.",
        "",
        "## Top Review Rows",
        "",
        "| Priority | Score | Company | Product | Track | Gaps | Next Action |",
        "|---|---:|---|---|---|---|---|",
    ]
    for row in top_rows:
        product_label = " / ".join(part for part in [str(row["brand"]), str(row["standard_product_name"])] if part)
        lines.append(
            f"| {md_cell(row['priority'])} | {md_cell(row['gap_score'])} | {md_cell(row['company'])} | {md_cell(product_label)} | "
            f"{md_cell(row['track'])} | {md_cell(row['issues'])} | {md_cell(row['recommended_next_action'])} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Product gap queue: `{queue_path.relative_to(ROOT)}`",
            f"- Candidate missing product/family rows: `{missing_path.relative_to(ROOT)}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=0, help="Limit queue rows in output; 0 keeps all products.")
    parser.add_argument("--missing-limit", type=int, default=300)
    parser.add_argument("--output-stem", default="", help="Use a fixed output suffix such as latest instead of a timestamp.")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_stem = args.output_stem or stamp
    queue_rows, missing_candidates, summary = build_product_queue(args)

    queue_path = AUDIT_DIR / f"product_gap_queue_{output_stem}.csv"
    missing_path = AUDIT_DIR / f"candidate_missing_product_lines_{output_stem}.csv"
    summary_path = AUDIT_DIR / f"product_gap_summary_{output_stem}.md"
    queue_fields = [
        "priority",
        "gap_score",
        "company",
        "company_product_count",
        "company_priority_rank",
        "brand",
        "standard_product_name",
        "product_id",
        "seed_record_id",
        "product_family_ids",
        "track",
        "form",
        "technology",
        "material_or_energy",
        "verification_status",
        "source_status",
        "direct_official_urls",
        "fuzzy_official_urls",
        "direct_spec_candidates",
        "fuzzy_spec_candidates",
        "spec_tier_A",
        "spec_tier_B",
        "spec_tier_C",
        "registration_rows",
        "official_indication_rows",
        "mdr_ce_candidate_rows",
        "lead_official_url",
        "lead_spec_url",
        "lead_registration_url",
        "evidence_mix",
        "issues",
        "recommended_next_action",
    ]
    missing_fields = [
        "company",
        "candidate_product_or_family",
        "source_count",
        "source_types",
        "source_domains",
        "confidence_mix",
        "sample_url",
        "review_status",
    ]
    write_csv(queue_path, queue_rows, queue_fields)
    write_csv(missing_path, missing_candidates, missing_fields)
    write_summary(summary_path, queue_path, missing_path, summary, queue_rows, generated_at)
    print(
        json.dumps(
            {
                "summary": str(summary_path),
                "queue": str(queue_path),
                "missing_candidates": str(missing_path),
                "products": summary["products"],
                "queue_rows": summary["queue_rows"],
                "priority_counts": dict(summary["priority_counts"]),  # type: ignore[arg-type]
                "missing_product_candidates": summary["missing_product_candidates"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

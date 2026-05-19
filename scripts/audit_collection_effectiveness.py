"""Audit whether the current collection outputs are useful.

This script is deliberately local-only: it reads generated CSV/JSONL files and
writes an evidence report plus review samples. It does not fetch websites,
call search APIs, or promote any candidate fact into master data.
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

WEBSITE_PATH = DATA_DIR / "official_website_master.csv"
MEDIA_PATH = DATA_DIR / "company_media_asset_index.csv"
SPEC_PATH = DATA_DIR / "product_specification_evidence.csv"
PROFILE_PATH = DATA_DIR / "company_profiles_bridge.json"
RUN_STATE_PATH = DATA_DIR / "continuous_run_state.json"
RUN_CONFIG_PATH = DATA_DIR / "current_verification_run.json"
RUN_LOG_PATH = DATA_DIR / "continuous_run_log.jsonl"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean(value: object) -> str:
    return str(value or "").strip()


def pct(part: int | float, total: int | float) -> str:
    if not total:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def top_counts(counter: Counter[str], limit: int = 10) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key or 'blank'}={value}" for key, value in counter.most_common(limit))


def domain_of(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return ""
    return parsed.netloc.lower().removeprefix("www.")


def is_weak_short_value(value: str) -> bool:
    text = clean(value)
    if not text:
        return True
    if re.fullmatch(r"\d{1,3}\s*[A-Za-z%]?", text):
        return True
    if re.fullmatch(r"[A-Za-z]{1,3}", text):
        return True
    return False


def looks_garbled(text: str) -> bool:
    sample = clean(text)
    if not sample:
        return True
    lowered = sample.lower()
    if any(token in lowered for token in ["objstm", "endstream", "/type /page", "xref", "flatedecode"]):
        return True
    if "�" in sample:
        return True
    visible = [char for char in sample if not char.isspace()]
    if not visible:
        return True
    control_count = sum(1 for char in visible if ord(char) < 32)
    odd_count = sum(1 for char in visible if ord(char) > 0xFFFD)
    return (control_count + odd_count) / max(len(visible), 1) > 0.02


def spec_identity(row: dict[str, str]) -> str:
    fields = ["product_id", "standard_product_name", "product_family_id", "product_family", "brand"]
    present = [field for field in fields if clean(row.get(field))]
    return "+".join(present)


def classify_spec(row: dict[str, str]) -> tuple[str, str]:
    confidence = clean(row.get("confidence"))
    source_url = clean(row.get("source_page_url"))
    value = clean(row.get("spec_value"))
    excerpt = clean(row.get("evidence_excerpt"))
    identity = spec_identity(row)
    official_site = confidence == "official_site_spec_candidate"
    official_excerpt = confidence == "official_search_excerpt_spec_candidate"
    weak_value = is_weak_short_value(value)
    garbled = looks_garbled(excerpt)
    has_identity = bool(identity)

    if garbled:
        return "C_review_noise", "garbled_or_binary_excerpt"
    if weak_value:
        return "C_review_noise", "weak_short_value"
    if not has_identity:
        return "C_review_noise", "missing_product_identity"
    if official_site:
        return "A_review_first", "official_site_with_product_context"
    if official_excerpt:
        return "B_candidate_pool", "search_excerpt_with_product_context"
    if domain_of(source_url):
        return "B_candidate_pool", "other_source_with_product_context"
    return "C_review_noise", "unclear_source"


def load_recent_finished_batches(limit: int = 40) -> list[dict[str, object]]:
    if not RUN_LOG_PATH.exists():
        return []
    events: list[dict[str, object]] = []
    with RUN_LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if '"event": "batch_finished"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(event)
    return events[-limit:]


def iso_seconds(start: str, finish: str) -> float | None:
    if not start or not finish:
        return None
    try:
        start_dt = datetime.fromisoformat(start)
        finish_dt = datetime.fromisoformat(finish)
    except ValueError:
        return None
    return max((finish_dt - start_dt).total_seconds(), 0.0)


def audit_websites(rows: list[dict[str, str]]) -> dict[str, object]:
    company_ids = {clean(row.get("company_id")) for row in rows if clean(row.get("company_id"))}
    website_ids = {clean(row.get("website_id")) for row in rows if clean(row.get("website_id"))}
    return {
        "rows": len(rows),
        "companies": len(company_ids),
        "websites": len(website_ids),
        "scope": Counter(clean(row.get("entity_scope")) for row in rows),
        "candidate": Counter(clean(row.get("official_candidate")) for row in rows),
        "confidence": Counter(clean(row.get("confidence")) for row in rows),
    }


def audit_media(rows: list[dict[str, str]], website_rows: list[dict[str, str]]) -> dict[str, object]:
    all_websites = {clean(row.get("website_id")) for row in website_rows if clean(row.get("website_id"))}
    covered_websites = {clean(row.get("website_id")) for row in rows if clean(row.get("website_id"))}
    logo_rows = [row for row in rows if clean(row.get("asset_type")) == "logo_candidate"]
    product_rows = [row for row in rows if clean(row.get("asset_type")) == "product_image_candidate"]
    downloaded_logo = [
        row
        for row in logo_rows
        if clean(row.get("review_status")) == "downloaded" and clean(row.get("local_path"))
    ]
    companies_with_logo = {clean(row.get("company")) for row in downloaded_logo if clean(row.get("company"))}
    return {
        "rows": len(rows),
        "covered_websites": len(covered_websites),
        "all_websites": len(all_websites),
        "pending_websites": max(len(all_websites - covered_websites), 0),
        "asset_type": Counter(clean(row.get("asset_type")) for row in rows),
        "status": Counter(clean(row.get("review_status")) for row in rows),
        "role": Counter(clean(row.get("asset_role")) for row in rows),
        "logo_rows": len(logo_rows),
        "downloaded_logo_rows": len(downloaded_logo),
        "companies_with_logo": len(companies_with_logo),
        "product_image_rows": len(product_rows),
        "downloaded_product_image_rows": sum(1 for row in product_rows if clean(row.get("review_status")) == "downloaded"),
    }


def audit_specs(rows: list[dict[str, str]], sample_limit: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    tier_counter: Counter[str] = Counter()
    reason_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    confidence_counter: Counter[str] = Counter()
    domain_counter: Counter[str] = Counter()
    product_context = 0
    review_samples: list[dict[str, object]] = []

    for row in rows:
        tier, reason = classify_spec(row)
        tier_counter[tier] += 1
        reason_counter[reason] += 1
        category_counter[clean(row.get("spec_category"))] += 1
        confidence_counter[clean(row.get("confidence"))] += 1
        domain_counter[domain_of(clean(row.get("source_page_url")))] += 1
        if spec_identity(row):
            product_context += 1
        if len(review_samples) < sample_limit and (tier.startswith("C") or reason != "official_site_with_product_context"):
            review_samples.append(
                {
                    "tier": tier,
                    "reason": reason,
                    "company": clean(row.get("company")),
                    "brand": clean(row.get("brand")),
                    "product_family": clean(row.get("product_family") or row.get("standard_product_name")),
                    "spec_category": clean(row.get("spec_category")),
                    "spec_name": clean(row.get("spec_name")),
                    "spec_value": clean(row.get("spec_value")),
                    "confidence": clean(row.get("confidence")),
                    "source_domain": domain_of(clean(row.get("source_page_url"))),
                    "source_page_url": clean(row.get("source_page_url")),
                    "evidence_excerpt": clean(row.get("evidence_excerpt"))[:500],
                }
            )

    return (
        {
            "rows": len(rows),
            "tier": tier_counter,
            "reason": reason_counter,
            "category": category_counter,
            "confidence": confidence_counter,
            "domain": domain_counter,
            "product_context": product_context,
        },
        review_samples,
    )


LOGO_ROLE_PRIORITY = {
    "operating_company_logo_img": 0,
    "listed_parent_logo_img": 1,
    "product_line_logo_img": 2,
    "favicon_or_touch_icon": 3,
}


def logo_score(row: dict[str, str]) -> tuple[int, int, int, str]:
    role_rank = LOGO_ROLE_PRIORITY.get(clean(row.get("asset_role")), 9)
    scope_rank = {"operating_company": 0, "listed_parent": 1, "product_line": 2}.get(clean(row.get("entity_scope")), 9)
    suffix = Path(clean(row.get("local_path")) or clean(row.get("file_name"))).suffix.lower()
    ext_rank = {".png": 0, ".webp": 1, ".jpg": 2, ".jpeg": 2, ".ico": 3, ".gif": 4, ".avif": 4, ".svg": 8}.get(suffix, 9)
    try:
        byte_rank = -int(clean(row.get("file_bytes")) or "0")
    except ValueError:
        byte_rank = 0
    return (role_rank, scope_rank, ext_rank, byte_rank, clean(row.get("asset_id")))


def audit_logo_coverage(media_rows: list[dict[str, str]], profile_payload: dict[str, object]) -> list[dict[str, object]]:
    companies = [
        clean(item.get("company"))  # type: ignore[union-attr]
        for item in profile_payload.get("companies", [])  # type: ignore[union-attr]
        if isinstance(item, dict) and clean(item.get("company"))
    ]
    by_company: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in media_rows:
        if clean(row.get("asset_type")) != "logo_candidate":
            continue
        by_company[clean(row.get("company"))].append(row)

    rows: list[dict[str, object]] = []
    for company in sorted(companies, key=str.casefold):
        candidates = by_company.get(company, [])
        downloaded = [
            row
            for row in candidates
            if clean(row.get("review_status")) == "downloaded" and clean(row.get("local_path"))
        ]
        best = sorted(downloaded, key=logo_score)[0] if downloaded else {}
        rows.append(
            {
                "company": company,
                "logo_candidates": len(candidates),
                "downloaded_logo_candidates": len(downloaded),
                "best_asset_role": clean(best.get("asset_role")) if best else "",
                "best_entity_scope": clean(best.get("entity_scope")) if best else "",
                "best_ext": Path(clean(best.get("local_path"))).suffix.lower() if best else "",
                "best_local_path": clean(best.get("local_path")) if best else "",
                "best_source_url": clean(best.get("image_url")) if best else "",
                "coverage_status": "has_downloaded_logo" if best else "missing_downloaded_logo",
            }
        )
    return rows


def build_report(
    generated_at: str,
    website_audit: dict[str, object],
    media_audit: dict[str, object],
    spec_audit: dict[str, object],
    logo_rows: list[dict[str, object]],
    recent_batches: list[dict[str, object]],
    run_state: dict[str, object],
    run_config: dict[str, object],
    sample_path: Path,
    logo_path: Path,
) -> str:
    durations = [
        value
        for value in (
            iso_seconds(clean(event.get("started_at")), clean(event.get("finished_at"))) for event in recent_batches
        )
        if value is not None and value > 0
    ]
    avg_duration = sum(durations) / len(durations) if durations else 0
    media_limit = 8
    command = clean(run_config.get("command"))
    match = re.search(r"--media-websites\s+(\d+)", command)
    if match:
        media_limit = int(match.group(1))
    pending_websites = int(media_audit["pending_websites"])
    remaining_batches = math.ceil(pending_websites / max(media_limit, 1))
    eta_hours = (remaining_batches * avg_duration / 3600) if avg_duration else 0

    tier_counter: Counter[str] = spec_audit["tier"]  # type: ignore[assignment]
    logo_ready = sum(1 for row in logo_rows if row["coverage_status"] == "has_downloaded_logo")
    total_companies = len(logo_rows)
    official_site_specs = tier_counter.get("A_review_first", 0)
    broad_candidate_specs = tier_counter.get("B_candidate_pool", 0)
    noisy_specs = tier_counter.get("C_review_noise", 0)

    recommendation = (
        "建议把当前网页扫描从“广泛继续跑”改成“缺口驱动”：logo 使用本地已下载资产先接入；"
        "产品规格只保留 A/B 级线索进入人工审核，C 级作为噪声样本，不继续为产品图片扩大下载。"
    )

    lines = [
        "# Collection Effectiveness Audit",
        "",
        f"Generated: {generated_at}",
        "",
        "## Executive Read",
        "",
        f"- Current run status: `{clean(run_state.get('last_status')) or 'unknown'}`; last batch `{clean(run_state.get('last_batch_id')) or 'n/a'}`.",
        f"- Website queue: {media_audit['covered_websites']} / {media_audit['all_websites']} website IDs have media/spec scan rows; pending {pending_websites}.",
        f"- At `--media-websites {media_limit}` and recent average batch duration {avg_duration / 60:.1f} min, rough remaining media/spec ETA is {eta_hours:.1f} hours.",
        f"- Logo usefulness: {logo_ready} / {total_companies} companies currently have at least one downloaded logo candidate.",
        f"- Spec usefulness: A={official_site_specs} review-first rows, B={broad_candidate_specs} candidate rows, C={noisy_specs} likely noisy/weak rows.",
        f"- Recommendation: {recommendation}",
        "",
        "## What The Current Pipeline Is Capturing",
        "",
        "- `official_website_master.csv`: candidate official/company/product-line URLs.",
        "- `company_media_asset_index.csv`: parsed image/logo candidates and page scan markers from those URLs.",
        "- `product_specification_evidence.csv`: regex-extracted specification candidates from official pages and search excerpts.",
        "- These are staging/review signals. They are not reviewed master facts yet.",
        "",
        "## Coverage",
        "",
        f"- Official website rows: {website_audit['rows']} across {website_audit['companies']} companies and {website_audit['websites']} website IDs.",
        f"- Website scope mix: {top_counts(website_audit['scope'])}.",
        f"- Website candidate flags: {top_counts(website_audit['candidate'])}.",
        f"- Media/spec rows: {media_audit['rows']}; status mix: {top_counts(media_audit['status'])}.",
        f"- Logo candidates: {media_audit['downloaded_logo_rows']} downloaded / {media_audit['logo_rows']} total rows.",
        f"- Product image candidates: {media_audit['downloaded_product_image_rows']} downloaded / {media_audit['product_image_rows']} total rows.",
        "",
        "## Specification Quality",
        "",
        f"- Total spec rows: {spec_audit['rows']}.",
        f"- Product-context rows: {spec_audit['product_context']} ({pct(int(spec_audit['product_context']), int(spec_audit['rows']))}).",
        f"- Tier mix: {top_counts(tier_counter)}.",
        f"- Main noise reasons: {top_counts(spec_audit['reason'])}.",
        f"- Category mix: {top_counts(spec_audit['category'])}.",
        f"- Confidence mix: {top_counts(spec_audit['confidence'])}.",
        f"- Top source domains: {top_counts(spec_audit['domain'])}.",
        "",
        "## Cost / Value Judgment",
        "",
        "- The pipeline is currently doing page fetch + HTML/spec parsing; after `--download-logos-only`, it is no longer intentionally downloading product images, but it still scans pages for logos and specs.",
        "- Logo extraction is useful as an asset-finding pass, but current coverage is incomplete and should now be normalized from existing local files rather than expanded blindly.",
        "- Spec extraction has a real candidate pool, but it mixes useful official-page rows with weak regex matches and binary/PDF noise. It needs review-tier filtering before any table promotion.",
        "- The broad media/spec queue is large enough that continuing it unchanged is a poor default unless a specific gap list justifies it.",
        "",
        "## Review Files",
        "",
        f"- Spec quality sample: `{sample_path.relative_to(ROOT)}`",
        f"- Logo coverage table: `{logo_path.relative_to(ROOT)}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-limit", type=int, default=120)
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    websites = read_csv_rows(WEBSITE_PATH)
    media = read_csv_rows(MEDIA_PATH)
    specs = read_csv_rows(SPEC_PATH)
    profile_payload = read_json(PROFILE_PATH, {})
    if not isinstance(profile_payload, dict):
        profile_payload = {}
    run_state = read_json(RUN_STATE_PATH, {})
    if not isinstance(run_state, dict):
        run_state = {}
    run_config = read_json(RUN_CONFIG_PATH, {})
    if not isinstance(run_config, dict):
        run_config = {}

    website_audit = audit_websites(websites)
    media_audit = audit_media(media, websites)
    spec_audit, spec_samples = audit_specs(specs, args.sample_limit)
    logo_rows = audit_logo_coverage(media, profile_payload)
    recent_batches = load_recent_finished_batches()

    sample_path = AUDIT_DIR / f"spec_quality_sample_{stamp}.csv"
    logo_path = AUDIT_DIR / f"logo_candidate_coverage_{stamp}.csv"
    report_path = AUDIT_DIR / f"effectiveness_audit_{stamp}.md"

    write_csv(
        sample_path,
        spec_samples,
        [
            "tier",
            "reason",
            "company",
            "brand",
            "product_family",
            "spec_category",
            "spec_name",
            "spec_value",
            "confidence",
            "source_domain",
            "source_page_url",
            "evidence_excerpt",
        ],
    )
    write_csv(
        logo_path,
        logo_rows,
        [
            "company",
            "coverage_status",
            "logo_candidates",
            "downloaded_logo_candidates",
            "best_asset_role",
            "best_entity_scope",
            "best_ext",
            "best_local_path",
            "best_source_url",
        ],
    )
    report = build_report(
        generated_at,
        website_audit,
        media_audit,
        spec_audit,
        logo_rows,
        recent_batches,
        run_state,
        run_config,
        sample_path,
        logo_path,
    )
    report_path.write_text(report, encoding="utf-8")

    print(json.dumps({"report": str(report_path), "spec_sample": str(sample_path), "logo_coverage": str(logo_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

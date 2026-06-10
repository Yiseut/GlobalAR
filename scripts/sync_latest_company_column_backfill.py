# -*- coding: utf-8 -*-
"""Sync the latest WeChat company-column profile back to the source workbook.

This script is intentionally conservative. It reads the latest briefing HTML
stem, matches it to the Plan B push history, then fills only blank master-data
fields that are safe for automatic company-column calibration:

- Companies.Positioning_CN
- Product_Lines.Verified_Product_Type_CN
- Product_Lines.Market_Channel

It does not overwrite existing source workbook values and does not insert new
product rows automatically.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BRIEFING_ROOT = Path(r"E:\shared\code\briefing_v6")
BRIEFING_OUTPUT = BRIEFING_ROOT / "output"
PLAN_B_HISTORY = BRIEFING_ROOT / "data" / "wechat_plan_b_history.jsonl"
COMPANY_STATE = BRIEFING_ROOT / "data" / "company_column_state.json"
COMPANY_RESEARCH_CACHE = BRIEFING_ROOT / "data" / "company_research_cache"
BACKFILL_OUTPUT = BRIEFING_ROOT / "output" / "company_backfill_review"
DB_PATH = DATA_DIR / "global_aesthetics.db"
LOG_DIR = DATA_DIR / "automation_logs"

ALLOWED_FIELDS = {
    ("companies", "positioning_cn"),
    ("products", "verified_product_type_cn"),
    ("products", "market_channel"),
}

PRODUCT_CHANNEL_HINTS = [
    (("Beauty Salon", "美容院"), "美容院 / Beauty Salon"),
    (("医美诊所", "美容沙龙"), "医美诊所 / 美容沙龙"),
    (("中小型医美诊所",), "中小型医美诊所 / 美容沙龙"),
    (("欧洲美容院线",), "欧洲美容院线"),
    (("院线",), "专业院线 / professional channel"),
    (("retail", "skincare"), "professional skincare / retail skincare"),
    (("药房",), "pharmacy / drugstore"),
    (("pharmacy",), "pharmacy / drugstore"),
    (("drugstore",), "pharmacy / drugstore"),
]


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "nan", "null"}:
        return ""
    return re.sub(r"\s+", " ", text)


def norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", clean(value).lower())


def safe_filename(text: str, max_len: int = 72) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "_", clean(text), flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("_")
    return (text[:max_len] or "company").strip("_")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def latest_briefing_stem(output_dir: Path) -> tuple[str, str]:
    candidates = []
    for path in output_dir.glob("全球行业资讯-*.html"):
        name = path.name
        if "_before_" in name or "before_" in name:
            continue
        stem = path.stem
        stem = re.sub(r"_selection_workbench$", "", stem)
        candidates.append((path.stat().st_mtime, str(path), stem))
    if not candidates:
        raise FileNotFoundError(f"No briefing HTML found in {output_dir}")
    _, path_text, stem = sorted(candidates, reverse=True)[0]
    return stem, path_text


def load_plan_b_history() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not PLAN_B_HISTORY.exists():
        return records
    for line in PLAN_B_HISTORY.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda item: clean(item.get("pushed_at")), reverse=True)
    return records


def load_company_state() -> dict[str, str]:
    raw = read_json(COMPANY_STATE, {})
    out: dict[str, str] = {}
    for date_key, value in (raw.get("date_to_company") or {}).items():
        if isinstance(value, dict) and clean(value.get("company")):
            out[clean(date_key)] = clean(value.get("company"))
    return out


def parse_dt(value: Any) -> datetime | None:
    text = clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:26])
    except ValueError:
        return None


def company_from_title(title: str) -> str:
    text = clean(title)
    if "｜" in text:
        return clean(text.split("｜", 1)[0])
    if "|" in text:
        return clean(text.split("|", 1)[0])
    return clean(re.split(r",|，|从 A 到 Z", text, maxsplit=1)[0])


def find_plan_b_record(briefing_stem: str) -> dict[str, Any] | None:
    for record in load_plan_b_history():
        if clean(record.get("briefing_file")) == briefing_stem:
            return record
    return None


def resolve_published_company(record: dict[str, Any]) -> tuple[str, str, str]:
    pushed_dt = parse_dt(record.get("pushed_at"))
    target_date = (pushed_dt.date() + timedelta(days=1)).isoformat() if pushed_dt else ""
    state_company = load_company_state().get(target_date, "")
    titles = [clean(x) for x in (record.get("titles") or []) if clean(x)]
    title = titles[-1] if titles else ""
    title_company = company_from_title(title)
    company = state_company or title_company
    if title_company and state_company and norm(title_company) != norm(state_company):
        company = state_company
    return company, target_date, title


def load_products(company: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT record_id, company, brand, core_product, category_l1, category_l2,
                       tech_type_std, introduction, verified_product_type_cn, market_channel
                FROM products
                WHERE company = ?
                ORDER BY record_id
                """,
                (company,),
            ).fetchall()
        ]
    finally:
        conn.close()


def load_company(company: str) -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT company, positioning_cn FROM companies WHERE company = ?",
            (company,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def find_product(products: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = norm(name)
    if not key:
        return None
    for product in products:
        fields = [product.get("record_id"), product.get("brand"), product.get("core_product")]
        if any(key == norm(field) for field in fields):
            return product
    for product in products:
        brand = norm(product.get("brand"))
        core = norm(product.get("core_product"))
        if brand and (brand in key or key in brand):
            return product
        if core and (core in key or key in core):
            return product
    return None


def normalize_product_type(value: str) -> str:
    parts = [clean(part) for part in re.split(r"/|；|;", clean(value)) if clean(part)]
    if not parts:
        return ""
    category_tokens = {
        "ebd",
        "injectables",
        "regenerative",
        "skincare",
        "consumables",
        "implants",
        "diagnostics",
        "pharma",
        "laser",
    }
    cn_parts = [part for part in parts if re.search(r"[\u4e00-\u9fff]", part)]
    tech_parts = [
        part
        for part in parts
        if not re.search(r"[\u4e00-\u9fff]", part)
        and part.strip().lower() not in category_tokens
    ]
    if cn_parts:
        return " / ".join([*cn_parts[:2], *tech_parts[:2]])
    return " / ".join(parts[:4])


def infer_channel(row: dict[str, Any], product: dict[str, Any]) -> str:
    explicit = clean(row.get("market_channel"))
    if explicit:
        return explicit
    haystack = " ".join(
        clean(x)
        for x in [
            row.get("type"),
            row.get("uses"),
            row.get("advantages"),
            product.get("introduction"),
            product.get("category_l1"),
            product.get("category_l2"),
            product.get("tech_type_std"),
        ]
        if clean(x)
    )
    lower = haystack.lower()
    for tokens, label in PRODUCT_CHANNEL_HINTS:
        if all(token.lower() in lower for token in tokens):
            return label
    return ""


def dataclass_to_dict(item: Any) -> dict[str, Any]:
    if is_dataclass(item):
        return asdict(item)
    return dict(item)


def imported_review_items(company: str) -> list[dict[str, Any]]:
    sys.path.insert(0, str(BRIEFING_ROOT))
    logging.getLogger("src.company_column").setLevel(logging.ERROR)
    logging.getLogger("company_column").setLevel(logging.ERROR)
    from src.company_backfill_review import build_review  # type: ignore

    _, items = build_review(limit=14, include_optional=True, show_resolved=False)
    rows = []
    for item in items:
        row = dataclass_to_dict(item)
        key = (clean(row.get("table")), clean(row.get("field")))
        if clean(row.get("company")) != company or key not in ALLOWED_FIELDS:
            continue
        if clean(row.get("current_value")):
            continue
        final_value = clean(row.get("suggested_value"))
        if row.get("field") == "verified_product_type_cn":
            final_value = normalize_product_type(final_value)
        if not final_value:
            continue
        row["review_decision"] = "accept"
        row["final_value"] = final_value
        row["review_note"] = "自动任务：来自已推送公众号公司百科，且目标字段为空。"
        rows.append(row)
    return rows


def cache_enrichment_items(
    *,
    company: str,
    target_date: str,
    pushed_at: str,
    title: str,
    source_html: str,
    existing_keys: set[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    cache = read_json(COMPANY_RESEARCH_CACHE / f"{safe_filename(company)}.json", {})
    draft = cache.get("article_draft") or {}
    company_row = load_company(company)
    products = load_products(company)
    rows: list[dict[str, Any]] = []

    tagline = clean(draft.get("tagline"))
    if not tagline and "｜" in title:
        tagline = clean(title.split("｜", 1)[1].split(",", 1)[0].split("，", 1)[0])
    if (
        tagline
        and not clean(company_row.get("positioning_cn"))
        and ("companies", company, "positioning_cn") not in existing_keys
    ):
        rows.append(
            {
                "status": "auto_fill",
                "action": "fill",
                "table": "companies",
                "record_key": company,
                "field": "positioning_cn",
                "field_label": "公司定位一句话",
                "current_value": "",
                "suggested_value": tagline,
                "final_value": tagline,
                "reason": "已推送公众号公司百科标题/定位可作为公司一句话定位回填。",
                "source_url": source_html,
                "source_title": title,
                "confidence": "high",
                "company": company,
                "target_date": target_date,
                "pushed_at": pushed_at,
                "review_decision": "accept",
                "review_note": "自动任务：来自已推送公众号公司百科，且目标字段为空。",
            }
        )

    for matrix_row in draft.get("product_matrix") or []:
        if not isinstance(matrix_row, dict):
            continue
        product = find_product(products, clean(matrix_row.get("name")))
        if not product:
            continue
        record_key = clean(product.get("record_id")) or clean(product.get("brand"))
        if not record_key:
            continue
        product_type = normalize_product_type(clean(matrix_row.get("type")))
        if (
            product_type
            and not clean(product.get("verified_product_type_cn"))
            and ("products", record_key, "verified_product_type_cn") not in existing_keys
        ):
            rows.append(
                {
                    "status": "auto_fill",
                    "action": "fill",
                    "table": "products",
                    "record_key": record_key,
                    "field": "verified_product_type_cn",
                    "field_label": "中文产品类型",
                    "current_value": "",
                    "suggested_value": product_type,
                    "final_value": product_type,
                    "reason": "已推送公众号公司百科产品矩阵补充中文产品类型。",
                    "source_url": source_html,
                    "source_title": title,
                    "confidence": "medium",
                    "company": company,
                    "target_date": target_date,
                    "pushed_at": pushed_at,
                    "review_decision": "accept",
                    "review_note": "自动任务：来自已推送公众号公司百科，且目标字段为空。",
                }
            )
        channel = infer_channel(matrix_row, product)
        if (
            channel
            and not clean(product.get("market_channel"))
            and ("products", record_key, "market_channel") not in existing_keys
        ):
            rows.append(
                {
                    "status": "auto_fill",
                    "action": "fill",
                    "table": "products",
                    "record_key": record_key,
                    "field": "market_channel",
                    "field_label": "市场/渠道线索",
                    "current_value": "",
                    "suggested_value": channel,
                    "final_value": channel,
                    "reason": "已推送公众号公司百科产品矩阵/产品介绍中出现渠道或使用场景线索。",
                    "source_url": source_html,
                    "source_title": title,
                    "confidence": "medium",
                    "company": company,
                    "target_date": target_date,
                    "pushed_at": pushed_at,
                    "review_decision": "accept",
                    "review_note": "自动任务：来自已推送公众号公司百科，且目标字段为空。",
                }
            )
    return rows


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in items:
        key = (clean(row.get("table")), clean(row.get("record_key")), clean(row.get("field")))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def write_decisions(payload: dict[str, Any]) -> Path:
    BACKFILL_OUTPUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company = safe_filename(payload["source"]["company"])
    path = BACKFILL_OUTPUT / f"auto_company_column_backfill_{company}_{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = BACKFILL_OUTPUT / "auto_company_column_backfill_latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_python(script: Path, *args: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(script.parent.parent),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        check=False,
    )
    return {
        "script": str(script),
        "args": list(args),
        "returncode": proc.returncode,
        "stdout": proc.stdout[-6000:],
        "stderr": proc.stderr[-6000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-sync latest pushed company-column profile to dashboard source workbook.")
    parser.add_argument("--dry-run", action="store_true", help="Create decisions and run apply dry-run only.")
    parser.add_argument("--skip-rebuild", action="store_true", help="Do not rebuild dashboard artifacts after apply.")
    parser.add_argument("--briefing-stem", default="", help="Override briefing stem, e.g. 全球行业资讯-2026-05-27_184928.")
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    latest_stem, latest_html = (args.briefing_stem, "") if args.briefing_stem else latest_briefing_stem(BRIEFING_OUTPUT)
    record = find_plan_b_record(latest_stem)
    summary: dict[str, Any] = {
        "started_at": started_at,
        "briefing_stem": latest_stem,
        "latest_html": latest_html,
        "dry_run": args.dry_run,
    }
    if not record:
        summary.update({"status": "no_plan_b_record", "message": "Latest briefing has no Plan B push history yet."})
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    company, target_date, title = resolve_published_company(record)
    if not company:
        summary.update({"status": "no_company_column", "message": "No company-column company could be resolved."})
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    imported = imported_review_items(company)
    existing_keys = {(clean(row.get("table")), clean(row.get("record_key")), clean(row.get("field"))) for row in imported}
    cache_items = cache_enrichment_items(
        company=company,
        target_date=target_date,
        pushed_at=clean(record.get("pushed_at")),
        title=title,
        source_html=latest_html,
        existing_keys=existing_keys,
    )
    items = dedupe_items([*imported, *cache_items])

    decisions_payload = {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "kind": "auto_wechat_company_column_backfill",
            "company": company,
            "target_date": target_date,
            "pushed_at": clean(record.get("pushed_at")),
            "briefing_file": latest_stem,
            "latest_html": latest_html,
            "title": title,
            "allowlist": sorted(f"{table}.{field}" for table, field in ALLOWED_FIELDS),
        },
        "review_items": items,
    }
    decisions_path = write_decisions(decisions_payload)
    summary.update(
        {
            "status": "decisions_created",
            "company": company,
            "target_date": target_date,
            "title": title,
            "decision_count": len(items),
            "decisions_path": str(decisions_path),
        }
    )
    if not items:
        summary["status"] = "no_new_blank_fields"
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    apply_script = BRIEFING_ROOT / "src" / "company_backfill_apply.py"
    apply_args = ["--decisions", str(decisions_path)]
    if args.dry_run:
        apply_args.append("--dry-run")
    apply_result = run_python(apply_script, *apply_args)
    summary["apply_result"] = apply_result
    if apply_result["returncode"] != 0:
        summary["status"] = "apply_failed"
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return apply_result["returncode"]

    if not args.dry_run and not args.skip_rebuild:
        rebuild_results = [
            run_python(ROOT / "scripts" / "build_data.py"),
            run_python(ROOT / "scripts" / "sync_company_column_profiles.py"),
            run_python(ROOT / "scripts" / "smoke_test.py"),
        ]
        summary["rebuild_results"] = rebuild_results
        if any(result["returncode"] != 0 for result in rebuild_results):
            summary["status"] = "rebuild_or_qa_failed"
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1

    summary["status"] = "ok"
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    log_path = LOG_DIR / f"company_column_backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (LOG_DIR / "company_column_backfill_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["log_path"] = str(log_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create a product-level completeness audit for one dashboard segment."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
WEB_DATA_PATH = PROJECT_DIR / "web" / "app-data.js"
DB_PATH = DATA_DIR / "global_aesthetics.db"


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_dashboard_data() -> dict[str, Any]:
    text = WEB_DATA_PATH.read_text(encoding="utf-8")
    text = re.sub(r"^window\.GLOBAL_AESTHETICS_DATA\s*=\s*", "", text).strip().rstrip(";")
    return json.loads(text)


def placeholders(count: int) -> str:
    return ",".join("?" for _ in range(count))


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def family_ids_for_records(conn: sqlite3.Connection, record_ids: list[str]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {record_id: [] for record_id in record_ids}
    rows = fetch_all(
        conn,
        f"SELECT product_family_id, source_record_ids FROM product_family_master WHERE source_record_ids IS NOT NULL",
    )
    record_set = set(record_ids)
    for row in rows:
        family_id = norm(row.get("product_family_id"))
        for record_id in [part.strip() for part in norm(row.get("source_record_ids")).split(",") if part.strip()]:
            if record_id in record_set and family_id:
                output.setdefault(record_id, []).append(family_id)
    return output


def rows_for_product_or_family(
    conn: sqlite3.Connection,
    table: str,
    product_id: str,
    family_ids: list[str],
    columns: str = "*",
) -> list[dict[str, Any]]:
    table_cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    clauses = []
    params: list[str] = []
    if product_id and "product_id" in table_cols:
        clauses.append("product_id = ?")
        params.append(product_id)
    if family_ids and "product_family_id" in table_cols:
        clauses.append(f"product_family_id IN ({placeholders(len(family_ids))})")
        params.extend(family_ids)
    if not clauses:
        return []
    return fetch_all(conn, f"SELECT {columns} FROM {table} WHERE {' OR '.join(clauses)}", tuple(params))


def fuzzy_rows(
    conn: sqlite3.Connection,
    table: str,
    company: str,
    brand: str,
    product: str,
    columns: str = "*",
    limit: int = 20,
) -> list[dict[str, Any]]:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    searchable = [col for col in ["company", "brand", "product_family", "standard_product_name", "source_title", "evidence_excerpt"] if col in cols]
    if not searchable:
        return []
    expr = " || ' ' || ".join(f"coalesce({col}, '')" for col in searchable)
    tokens = [token for token in [company, brand, product] if len(token) >= 3]
    if not tokens:
        return []
    where = " OR ".join([f"lower({expr}) LIKE ?" for _ in tokens])
    params = tuple(f"%{token.lower()}%" for token in tokens)
    return fetch_all(conn, f"SELECT {columns} FROM {table} WHERE {where} LIMIT {limit}", params)


def material_conflict(product: dict[str, Any], page_item: dict[str, Any], specs: list[dict[str, Any]]) -> str:
    text = " ".join(
        [
            norm(product.get("technology_path_l1")),
            norm(product.get("technology_path_l2")),
            norm(product.get("material_or_energy_source")),
            norm(product.get("standard_product_name")),
            norm(product.get("core_product")),
        ]
    ).lower()
    subtracks = " ".join(page_item.get("subtracks") or []).lower()
    spec_values = Counter(norm(row.get("spec_value")) for row in specs if norm(row.get("spec_name")).lower() == "composition")
    if "caha" in subtracks or "calcium" in subtracks or "羟基" in subtracks:
        if "hyaluronic acid" in text and "calcium" not in text and "caha" not in text:
            return "Product_Master material is HA while segment/subtrack implies CaHA."
    if spec_values.get("Hyaluronic Acid") and (spec_values.get("CaHA") or spec_values.get("Calcium Hydroxylapatite")):
        return "Specification candidates contain both HA and CaHA; likely adjacent-product extraction contamination."
    return ""


def score_row(row: dict[str, Any]) -> int:
    score = 0
    score += 20 if row["classification_status"] == "ok" else 0
    score += 20 if row["official_website_rows"] else 0
    score += 20 if row["registration_rows"] else 0
    score += 20 if row["official_indication_rows"] else 0
    score += 20 if row["spec_candidate_rows"] else 0
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segment", default="caha")
    parser.add_argument("--output-prefix", default="")
    args = parser.parse_args()

    data = load_dashboard_data()
    segment = next((item for item in data.get("segments", []) if item.get("code") == args.segment), None)
    if not segment:
        raise SystemExit(f"Segment not found: {args.segment}")

    record_ids = [item["record_id"] for item in segment.get("sample_products", []) if item.get("record_id")]
    page_by_record = {item["record_id"]: item for item in segment.get("sample_products", [])}
    conn = sqlite3.connect(DB_PATH)
    family_by_record = family_ids_for_records(conn, record_ids)
    products = fetch_all(
        conn,
        f"""
        SELECT product_id, seed_record_id, company, brand, standard_product_name, registered_name,
               commercial_path_l1, commercial_path_l2, technology_path_l1, technology_path_l2,
               material_or_energy_source, core_product, legal_manufacturer, marketing_holder,
               verification_status, source_status, claim_text
        FROM product_master
        WHERE seed_record_id IN ({placeholders(len(record_ids))})
        ORDER BY company, brand
        """,
        tuple(record_ids),
    )

    audit_rows: list[dict[str, Any]] = []
    indication_details: list[dict[str, Any]] = []
    registration_details: list[dict[str, Any]] = []
    source_details: list[dict[str, Any]] = []

    for product in products:
        product_id = norm(product.get("product_id"))
        record_id = norm(product.get("seed_record_id"))
        family_ids = family_by_record.get(record_id, [])
        page_item = page_by_record.get(record_id, {})
        regs = rows_for_product_or_family(conn, "registration_evidence", product_id, family_ids)
        inds = rows_for_product_or_family(conn, "official_indication_evidence", product_id, family_ids)
        specs = rows_for_product_or_family(conn, "product_specification_evidence", product_id, family_ids)
        websites = rows_for_product_or_family(conn, "official_website_master", product_id, family_ids)
        plans = rows_for_product_or_family(conn, "mdr_ce_search_plan", product_id, family_ids)
        candidates = rows_for_product_or_family(conn, "mdr_ce_evidence_candidates", product_id, family_ids)

        fuzzy_specs = fuzzy_rows(conn, "product_specification_evidence", norm(product.get("company")), norm(product.get("brand")), norm(product.get("standard_product_name")))
        fuzzy_websites = fuzzy_rows(conn, "official_website_master", norm(product.get("company")), norm(product.get("brand")), norm(product.get("standard_product_name")))
        fuzzy_sources = fuzzy_rows(conn, "company_official_source_evidence", norm(product.get("company")), norm(product.get("brand")), norm(product.get("standard_product_name")), limit=8)
        conflict = material_conflict(product, page_item, specs or fuzzy_specs)

        issues = []
        if norm(product.get("verification_status")) == "unverified_seed":
            issues.append("Product_Master remains unverified seed")
        if conflict:
            issues.append(conflict)
        if "/" in norm(product.get("standard_product_name")) and any(token in norm(product.get("standard_product_name")).lower() for token in ["intense", "stimulate"]):
            issues.append("Likely mixed product-family row; may need SKU split before indication/spec analysis.")
        if not regs:
            issues.append("No promoted registration evidence")
        if not inds:
            issues.append("No promoted official indication")
        if not websites and not fuzzy_websites:
            issues.append("No official website candidate")
        if not specs and not fuzzy_specs:
            issues.append("No spec candidate")

        classification_status = "issue" if conflict else "ok"
        audit = {
            "segment": segment.get("name"),
            "record_id": record_id,
            "product_id": product_id,
            "company": product.get("company"),
            "brand": product.get("brand"),
            "product": product.get("standard_product_name"),
            "country": page_item.get("country"),
            "page_subtracks": " | ".join(page_item.get("subtracks") or []),
            "page_positioning_indications": " | ".join(page_item.get("indications") or []),
            "product_master_tech": product.get("technology_path_l1"),
            "product_master_material": product.get("material_or_energy_source"),
            "verification_status": product.get("verification_status"),
            "source_status": product.get("source_status"),
            "classification_status": classification_status,
            "registration_rows": len(regs),
            "official_indication_rows": len(inds),
            "official_website_rows": len(websites),
            "official_website_fuzzy_rows": len(fuzzy_websites),
            "spec_candidate_rows": len(specs),
            "spec_fuzzy_rows": len(fuzzy_specs),
            "mdr_ce_plan_rows": len(plans),
            "mdr_ce_candidate_rows": len(candidates),
            "issues": "；".join(issues),
        }
        audit["completeness_score"] = score_row(audit)
        audit_rows.append(audit)

        for row in inds:
            indication_details.append(
                {
                    "record_id": record_id,
                    "company": product.get("company"),
                    "brand": product.get("brand"),
                    "country": row.get("country"),
                    "regulator": row.get("regulator"),
                    "pathway": row.get("pathway"),
                    "approval_date": row.get("approval_date"),
                    "registration_no": row.get("registration_no"),
                    "buckets": row.get("buckets"),
                    "indication": row.get("indication"),
                    "official_description_exact": row.get("official_description_exact"),
                    "official_description_source_field": row.get("official_description_source_field"),
                    "field_note": row.get("field_note"),
                    "source_url": row.get("source_url"),
                    "confidence": row.get("confidence"),
                }
            )
        for row in regs:
            registration_details.append(
                {
                    "record_id": record_id,
                    "company": product.get("company"),
                    "brand": product.get("brand"),
                    "jurisdiction": row.get("jurisdiction"),
                    "regulator": row.get("regulator"),
                    "status": row.get("status"),
                    "approval_date": row.get("approval_date"),
                    "registration_no": row.get("registration_no"),
                    "registered_name": row.get("registered_name"),
                    "approved_indication": row.get("approved_indication"),
                    "official_description_exact": row.get("official_description_exact"),
                    "official_description_source_field": row.get("official_description_source_field"),
                    "field_note": row.get("field_note"),
                    "source_url": row.get("source_url"),
                    "confidence": row.get("confidence"),
                }
            )
        for row in (websites or fuzzy_websites)[:5]:
            source_details.append(
                {
                    "record_id": record_id,
                    "company": product.get("company"),
                    "brand": product.get("brand"),
                    "source_type": "official_website_master",
                    "title": row.get("source_title"),
                    "url": row.get("official_website_url"),
                    "confidence": row.get("confidence"),
                    "review_status": row.get("review_status"),
                }
            )
        for row in fuzzy_sources[:3]:
            source_details.append(
                {
                    "record_id": record_id,
                    "company": product.get("company"),
                    "brand": product.get("brand"),
                    "source_type": "company_official_source_evidence",
                    "title": row.get("title"),
                    "url": row.get("url"),
                    "confidence": row.get("confidence"),
                    "review_status": row.get("crosscheck_status"),
                }
            )

    prefix = args.output_prefix or f"{args.segment}_lane_audit"
    csv_path = DATA_DIR / f"{prefix}.csv"
    md_path = DATA_DIR / f"{prefix}.md"
    detail_path = DATA_DIR / f"{prefix}_details.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0].keys()) if audit_rows else [])
        writer.writeheader()
        writer.writerows(audit_rows)

    detail = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "segment": {"code": segment.get("code"), "name": segment.get("name"), "evidence_scope": segment.get("evidence_scope")},
        "audit_rows": audit_rows,
        "official_indications": indication_details,
        "registrations": registration_details,
        "sources": source_details,
    }
    detail_path.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    issue_rows = [row for row in audit_rows if row["issues"]]
    scores = [row["completeness_score"] for row in audit_rows]
    lines = [
        f"# {segment.get('name')} 小赛道完整度审计",
        "",
        f"- 生成时间：{detail['generated_at']}",
        f"- 产品线：{len(audit_rows)}",
        f"- 平均完整度：{round(sum(scores) / len(scores), 1) if scores else 0}/100",
        f"- 有问题或缺口的产品：{len(issue_rows)}",
        f"- 官方适应症记录：{len(indication_details)}",
        f"- 注册证据记录：{len(registration_details)}",
        "",
        "## 产品级状态",
        "",
        "| 产品 | 主表状态 | 注册 | 官方适应症 | 官网 direct/fuzzy | 规格 direct/fuzzy | 完整度 | 主要问题 |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in audit_rows:
        lines.append(
            f"| {row['company']} / {row['brand']} / {row['product']} | {row['verification_status']} | "
            f"{row['registration_rows']} | {row['official_indication_rows']} | "
            f"{row['official_website_rows']}/{row['official_website_fuzzy_rows']} | "
            f"{row['spec_candidate_rows']}/{row['spec_fuzzy_rows']} | {row['completeness_score']} | {row['issues'] or 'OK'} |"
        )
    lines.extend(["", "## 官方适应症明细", ""])
    if indication_details:
        for row in indication_details:
            lines.append(
                f"- {row['company']} / {row['brand']} · {row['country']} · {row['regulator']} · "
                f"{row['approval_date'] or 'date n/a'} · {row['buckets'] or 'bucket n/a'} · {row['source_url']}"
            )
    else:
        lines.append("- 暂无 promoted official indication。")
    lines.extend(["", "## 结论", ""])
    lines.append("- CaHA 样本可用于子页面早审，但目前不能把候选证据都当成确定事实。")
    lines.append("- Product_Master、Registration_Evidence、Official_Indication_Evidence 的产品级联接要优先补齐，否则页面只能做赛道概览，不能做产品事实页。")
    lines.append("- 规格候选需保留候选状态，并在 UI 中显示来源和是否为直接产品匹配。")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"csv": str(csv_path), "markdown": str(md_path), "details": str(detail_path), "rows": len(audit_rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

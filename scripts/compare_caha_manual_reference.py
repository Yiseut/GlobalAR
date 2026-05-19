from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANUAL_REFERENCE_PATH = DATA_DIR / "caha_manual_reference.csv"
GAP_CSV_PATH = DATA_DIR / "caha_manual_reference_gap.csv"
GAP_MD_PATH = DATA_DIR / "caha_manual_reference_gap.md"


MANUAL_ROWS: list[dict[str, str]] = [
    {
        "brand": "Radiesse",
        "company": "Merz Pharmaceuticals",
        "country": "Germany",
        "main_components": "30% CaHA + 70% CMC",
        "packaging": "1.5 ml / 2 x 0.8 ml",
        "particle_size_um": "25-45",
        "fda_indication_manual": "面部皱纹和褶皱（如鼻唇沟）的矫正；手部体积缺失矫正和手背年轻化；成人中至重度下颌轮廓缺失改善；2026-03-31 FDA PMA S162 新增 1:2 稀释后用于 décolleté wrinkles。",
        "eu_indication_manual": "面部轮廓重塑、皱纹和褶皱填充、手部体积缺失和手背年轻化。",
        "nmpa_indication_manual": "",
        "launch_year_manual": "2004",
        "source_type": "user_manual_reference",
        "verification_status": "needs_official_field_by_field_check",
        "notes": "User screenshot plus FDA S162 official correction.",
    },
    {
        "brand": "HArmonyCa",
        "company": "Allergan Aesthetics",
        "country": "USA",
        "main_components": "CaHA + HA",
        "packaging": "",
        "particle_size_um": "25-45",
        "fda_indication_manual": "",
        "eu_indication_manual": "面部体积恢复和轮廓塑形。",
        "nmpa_indication_manual": "",
        "launch_year_manual": "2022",
        "source_type": "user_manual_reference",
        "verification_status": "needs_official_field_by_field_check",
        "notes": "Manual reference row from user screenshot.",
    },
    {
        "brand": "FaceTem",
        "company": "CGBio",
        "country": "South Korea",
        "main_components": "30% CaHA + 70% CMC",
        "packaging": "1.5 ml / 2 x 0.8 ml",
        "particle_size_um": "30",
        "fda_indication_manual": "改善成人面部皱纹和褶皱。",
        "eu_indication_manual": "",
        "nmpa_indication_manual": "",
        "launch_year_manual": "2018",
        "source_type": "user_manual_reference",
        "verification_status": "needs_official_field_by_field_check",
        "notes": "Manual reference row from user screenshot.",
    },
    {
        "brand": "Neauvia",
        "company": "Neauvia Technology / Matex Lab",
        "country": "Italy",
        "main_components": "HA + amino acids including L-proline/glycine + 0.1% CaHA",
        "packaging": "",
        "particle_size_um": "25-45",
        "fda_indication_manual": "",
        "eu_indication_manual": "面部皱纹填充、面部轮廓塑造以及改善皮肤质地。",
        "nmpa_indication_manual": "",
        "launch_year_manual": "2014",
        "source_type": "user_manual_reference",
        "verification_status": "needs_official_field_by_field_check",
        "notes": "Manual reference row from user screenshot; likely needs SKU split by Neauvia Organic product.",
    },
]


def now_cn() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower()
    text = text.replace("®", "").replace("™", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def matches_manual(row: dict[str, str], manual: dict[str, str]) -> bool:
    brand = norm(manual["brand"])
    manual_company = norm(manual["company"])
    identity_blob = norm(
        " ".join(
            row.get(key, "")
            for key in [
                "company",
                "brand",
                "product_family",
                "standard_product_name",
                "registered_name",
                "product",
                "core_product",
            ]
        )
    )
    company_blob = norm(row.get("company", ""))
    product_blob = norm(
        " ".join(
            row.get(key, "")
            for key in ["brand", "product_family", "standard_product_name", "registered_name", "product", "core_product"]
        )
    )
    if brand == "facetem":
        return "facetem" in product_blob and ("cgbio" in company_blob or "cell growth bio" in company_blob)
    if brand == "neauvia":
        return "neauvia" in product_blob and "devices" not in product_blob and "sectum" not in product_blob
    if brand and brand in product_blob:
        if not manual_company:
            return True
        manual_company_parts = [part for part in manual_company.split() if len(part) >= 4]
        return not manual_company_parts or any(part in company_blob or part in identity_blob for part in manual_company_parts)
    return False


def compact(values: list[str], limit: int = 4) -> str:
    seen: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in seen:
            seen.append(value)
    if len(seen) > limit:
        return " | ".join(seen[:limit]) + f" | +{len(seen) - limit} more"
    return " | ".join(seen)


def has_spec(specs: list[dict[str, str]], names: list[str], values: list[str] | None = None) -> bool:
    name_terms = [term.lower() for term in names]
    value_terms = [term.lower() for term in values or []]
    for row in specs:
        name_blob = " ".join([row.get("spec_name", ""), row.get("spec_category", "")]).lower()
        value_blob = row.get("spec_value", "").lower()
        if any(term in name_blob for term in name_terms):
            return True
        if value_terms and any(term in value_blob for term in value_terms):
            return True
    return False


def field_status(ok: bool, partial: bool = False) -> str:
    if ok:
        return "captured"
    if partial:
        return "partial"
    return "missing_or_unverified"


def md_cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def build() -> None:
    write_csv(MANUAL_REFERENCE_PATH, MANUAL_ROWS, list(MANUAL_ROWS[0].keys()))

    products = load_csv(DATA_DIR / "product_master.csv")
    specs = load_csv(DATA_DIR / "product_specification_evidence.csv")
    registrations = load_csv(DATA_DIR / "registration_evidence.csv")
    indications = load_csv(DATA_DIR / "official_indication_evidence.csv")

    gap_rows: list[dict[str, Any]] = []
    for manual in MANUAL_ROWS:
        matched_products = [row for row in products if matches_manual(row, manual)]
        product_ids = {row.get("product_id", "") for row in matched_products if row.get("product_id")}

        matched_specs = [
            row for row in specs
            if (row.get("product_id") and row.get("product_id") in product_ids) or matches_manual(row, manual)
        ]
        matched_regs = [
            row for row in registrations
            if (row.get("product_id") and row.get("product_id") in product_ids) or matches_manual(row, manual)
        ]
        matched_indications = [
            row for row in indications
            if (row.get("product_id") and row.get("product_id") in product_ids) or matches_manual(row, manual)
        ]

        fda_rows = [
            row for row in matched_indications + matched_regs
            if "fda" in norm(" ".join([row.get("regulator", ""), row.get("source_type", ""), row.get("jurisdiction", ""), row.get("country", "")]))
            or norm(row.get("jurisdiction")) == "us"
            or norm(row.get("country")) == "us"
        ]
        eu_rows = [
            row for row in matched_indications + matched_regs
            if any(term in norm(" ".join([row.get("regulator", ""), row.get("source_type", ""), row.get("jurisdiction", ""), row.get("country", ""), row.get("pathway", "")]))
                   for term in ["ce", "mdr", "eu", "global", "ifu"])
        ]

        status_composition = field_status(
            any(row.get("material_or_energy_source") for row in matched_products)
            or has_spec(matched_specs, ["composition", "ingredient", "material"], ["caha", "calcium hydroxylapatite", "hyaluronic acid", "cmc"])
        )
        status_packaging = field_status(has_spec(matched_specs, ["package", "packaging", "volume", "syringe"], ["1.5 ml", "0.8 ml", "ml"]))
        status_particle = field_status(has_spec(matched_specs, ["particle", "micron", "size"], ["25", "45", "30"]))
        status_fda = field_status(bool(fda_rows), bool(manual.get("fda_indication_manual")))
        status_eu = field_status(bool(eu_rows), bool(manual.get("eu_indication_manual")))
        status_nmpa = "out_of_scope_current_project" if manual.get("nmpa_indication_manual") == "" else "missing_or_unverified"
        status_launch = "missing_or_unverified" if manual.get("launch_year_manual") else "not_supplied"

        missing_fields = [
            label
            for label, status in [
                ("包装", status_packaging),
                ("粒径", status_particle),
                ("FDA官方适应症", status_fda),
                ("EU/CE官方适应症", status_eu),
                ("上市时间", status_launch),
            ]
            if status != "captured"
        ]
        gap_rows.append(
            {
                "brand": manual["brand"],
                "manual_company": manual["company"],
                "matched_product_count": len(matched_products),
                "matched_product_ids": compact(sorted(product_ids), 8),
                "current_company": compact([row.get("company", "") for row in matched_products]),
                "current_product_names": compact([row.get("standard_product_name", "") for row in matched_products]),
                "current_verification_status": compact([row.get("verification_status", "") for row in matched_products]),
                "composition_status": status_composition,
                "packaging_status": status_packaging,
                "particle_size_status": status_particle,
                "fda_indication_status": status_fda,
                "eu_indication_status": status_eu,
                "nmpa_status": status_nmpa,
                "launch_year_status": status_launch,
                "spec_rows": len(matched_specs),
                "registration_rows": len(matched_regs),
                "official_indication_rows": len(matched_indications),
                "official_indication_buckets": compact([row.get("buckets", "") for row in matched_indications]),
                "source_urls": compact(
                    [row.get("source_url", "") for row in matched_specs + matched_regs + matched_indications],
                    6,
                ),
                "missing_or_attention_fields": compact(missing_fields, 10),
            }
        )

    fields = [
        "brand",
        "manual_company",
        "matched_product_count",
        "matched_product_ids",
        "current_company",
        "current_product_names",
        "current_verification_status",
        "composition_status",
        "packaging_status",
        "particle_size_status",
        "fda_indication_status",
        "eu_indication_status",
        "nmpa_status",
        "launch_year_status",
        "spec_rows",
        "registration_rows",
        "official_indication_rows",
        "official_indication_buckets",
        "source_urls",
        "missing_or_attention_fields",
    ]
    write_csv(GAP_CSV_PATH, gap_rows, fields)

    md_lines = [
        "# CaHA 手工参考表自动化覆盖差异",
        "",
        f"- Generated: {now_cn()}",
        "- Scope: user manual CaHA overview screenshot vs current Product_Master / Registration_Evidence / Official_Indication_Evidence / product specification evidence.",
        "- Rule: 手工表只作为线索；监管事实以 FDA/CE/MDR/IFU 等官方证据为准，商品规格以官网/IFU/目录为准。",
        "",
        "| 品牌 | 当前匹配 | 规格 | FDA适应症 | EU/CE适应症 | 主要缺口 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for row in gap_rows:
        spec_status = f"成分 {row['composition_status']} / 包装 {row['packaging_status']} / 粒径 {row['particle_size_status']}"
        md_lines.append(
            "| {brand} | {matched_product_count} | {spec_status} | {fda} | {eu} | {gap} |".format(
                brand=md_cell(row["brand"]),
                matched_product_count=row["matched_product_count"],
                spec_status=md_cell(spec_status),
                fda=md_cell(row["fda_indication_status"]),
                eu=md_cell(row["eu_indication_status"]),
                gap=md_cell(row["missing_or_attention_fields"] or "OK"),
            )
        )
    md_lines.extend(
        [
            "",
            "## 关键发现",
            "",
            "- Radiesse 的 FDA 新适应症已经可以自动同步到官方适应症长表；本次已把 wording 修正为 PMA S162 的官方范围：1:2 稀释后用于 décolleté wrinkles，approval date 为 2026-03-31。",
            "- 截图里的包装、粒径、主要成分可以自动抓，但不能只从 FDA/MDR 注册库抓；需要继续从品牌官网、IFU、eIFU、产品目录抽取，并保留原文证据。",
            "- HArmonyCa、FaceTem、Neauvia 的 EU/CE 或 FDA 适应症目前大多还是手工线索或官网候选，缺少进入 Registration_Evidence/Official_Indication_Evidence 的官方监管证据。",
            "- NMPA 暂不在当前全球项目内；后续可从中国区单独仪表盘桥接到同一长表结构。",
            "- 上市时间建议拆成 first_global_launch_year、first_regulatory_approval_date、first_commercial_availability_date，避免把新闻发布时间、CE/FDA 批准时间和商业上市时间混用。",
            "",
            "## JSON Snapshot",
            "",
            "```json",
            json.dumps(gap_rows, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    GAP_MD_PATH.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"wrote {MANUAL_REFERENCE_PATH}")
    print(f"wrote {GAP_CSV_PATH}")
    print(f"wrote {GAP_MD_PATH}")


if __name__ == "__main__":
    build()

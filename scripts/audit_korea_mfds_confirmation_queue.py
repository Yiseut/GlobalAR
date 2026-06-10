"""Build a focused Korea MFDS/KFDA confirmation queue."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"
PRODUCT_MASTER = DATA_DIR / "product_master.csv"
COMPANY_MASTER = DATA_DIR / "company_master.csv"
REGISTRATION_EVIDENCE = DATA_DIR / "registration_evidence.csv"

REGULATED_TRACKS = {"Injectables", "EBD", "Implants", "Regenerative", "Consumables", "Surgical", "Diagnostics"}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def is_mfds(row: dict[str, str]) -> bool:
    blob = " ".join(clean(row.get(field)).lower() for field in ["jurisdiction", "regulator", "source_key", "source_type", "registration_no"])
    return any(token in blob for token in ["mfds", "kfda", "korea", "kr"])


def has_official_product_evidence(product: dict[str, str]) -> bool:
    source_status = clean(product.get("source_status")).lower()
    verification = clean(product.get("verification_status")).lower()
    return (
        "official_product_page" in source_status
        or "official_product_document" in source_status
        or "official_evidence_promoted" in source_status
        or verification.startswith("official_")
    )


def product_country(product: dict[str, str], company: dict[str, str]) -> str:
    country = clean(company.get("country"))
    if country:
        return country
    blob = clean(product.get("search_blob")).lower()
    if "| south korea |" in f"| {blob} |" or "south korea" in blob:
        return "South Korea"
    return ""


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    products = read_csv(PRODUCT_MASTER)
    companies = {clean(row.get("company_id")): row for row in read_csv(COMPANY_MASTER)}
    registrations = read_csv(REGISTRATION_EVIDENCE)

    regs_by_product: dict[str, list[dict[str, str]]] = {}
    for row in registrations:
        regs_by_product.setdefault(clean(row.get("product_id")), []).append(row)

    rows: list[dict[str, str]] = []
    for product in products:
        if "duplicate_of:" in clean(product.get("search_blob")).lower():
            continue
        company = companies.get(clean(product.get("company_id")), {})
        country = product_country(product, company)
        if country != "South Korea":
            continue
        if clean(product.get("commercial_path_l1")) not in REGULATED_TRACKS:
            continue
        if clean(product.get("inclusion_status")).lower() in {"deleted", "excluded"}:
            continue
        product_regs = regs_by_product.get(clean(product.get("product_id")), [])
        mfds_regs = [row for row in product_regs if is_mfds(row)]
        if mfds_regs:
            continue
        other_regs = [row for row in product_regs if clean(row.get("registration_no")) or clean(row.get("regulator"))]
        official_ready = has_official_product_evidence(product)
        if clean(product.get("verification_status")).lower() == "unverified_seed":
            priority = "P1"
            status = "需先核产品身份，再查 MFDS"
        elif official_ready:
            priority = "P3"
            status = "产品事实已核，韩国 MFDS/KFDA 具体证号未公开/待反查（非阻塞）"
        else:
            priority = "P1"
            status = "缺官网/产品身份，MFDS 暂不能核"
        rows.append(
            {
                "priority": priority,
                "status": status,
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "track": clean(product.get("commercial_path_l1")),
                "form": clean(product.get("commercial_path_l2")),
                "product_id": clean(product.get("product_id")),
                "seed_record_id": clean(product.get("seed_record_id")),
                "verification_status": clean(product.get("verification_status")),
                "official_product_evidence": "yes" if official_ready else "no",
                "other_registration_rows": str(len(other_regs)),
                "other_regulators": "; ".join(sorted({clean(row.get("regulator")) for row in other_regs if clean(row.get("regulator"))})[:6]),
                "recommended_action": "保留为低优先级监管监控项；后续机器反查 MFDS/UDI，若无公开号则保持“未公开/未抓到”，不影响产品事实。",
            }
        )

    rows.sort(key=lambda row: (row["priority"], row["company"].lower(), row["brand"].lower(), row["standard_product_name"].lower()))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = AUDIT_DIR / f"korea_mfds_confirmation_queue_{stamp}.csv"
    html_path = AUDIT_DIR / f"korea_mfds_confirmation_queue_{stamp}.html"
    latest_csv = AUDIT_DIR / "korea_mfds_confirmation_queue_latest.csv"
    latest_html = AUDIT_DIR / "korea_mfds_confirmation_queue_latest.html"
    summary_path = AUDIT_DIR / "korea_mfds_confirmation_queue_latest_summary.json"

    fields = [
        "priority",
        "status",
        "company",
        "brand",
        "standard_product_name",
        "track",
        "form",
        "product_id",
        "seed_record_id",
        "verification_status",
        "official_product_evidence",
        "other_registration_rows",
        "other_regulators",
        "recommended_action",
    ]
    write_csv(csv_path, rows, fields)
    write_csv(latest_csv, rows, fields)

    counts = Counter(row["priority"] for row in rows)
    body_rows = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(clean(row.get(field)))}</td>" for field in fields)
        + "</tr>"
        for row in rows
    )
    html_doc = f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <title>韩国 MFDS/KFDA 待核清单</title>
  <style>
    body {{ font-family: Arial, 'Microsoft YaHei', sans-serif; margin: 28px; color: #28231f; }}
    h1 {{ margin-bottom: 4px; }}
    .note {{ color: #746b63; margin-bottom: 18px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #e4ddd6; padding: 8px; vertical-align: top; }}
    th {{ background: #f7f2ee; text-align: left; }}
    tr:nth-child(even) {{ background: #fbfaf8; }}
  </style>
</head>
<body>
  <h1>韩国 MFDS/KFDA 待核清单</h1>
  <p class=\"note\">只列韩国公司、受监管产品线且当前没有 MFDS/KFDA 注册证据的项目。产品事实已核但只缺公开证号的项目降为 P3 监控，不再作为人工确认阻塞项。</p>
  <p>总数：{len(rows)}；P1：{counts.get('P1', 0)}；P2：{counts.get('P2', 0)}；P3：{counts.get('P3', 0)}</p>
  <table>
    <thead><tr>{''.join(f'<th>{html.escape(field)}</th>' for field in fields)}</tr></thead>
    <tbody>{body_rows}</tbody>
  </table>
</body>
</html>
"""
    html_path.write_text(html_doc, encoding="utf-8")
    latest_html.write_text(html_doc, encoding="utf-8")

    summary = {"rows": len(rows), "priority_counts": dict(counts), "csv": str(latest_csv), "html": str(latest_html)}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

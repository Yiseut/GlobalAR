#!/usr/bin/env python3
"""Local server for the Global Medical Aesthetics dashboard."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import re
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web"
DATA_DIR = PROJECT_DIR / "data"
DB_PATH = PROJECT_DIR / "data" / "global_aesthetics.db"
MANIFEST_PATH = PROJECT_DIR / "data" / "import_manifest.json"
STAGING_JSONL_PATH = DATA_DIR / "verification_evidence_staging.jsonl"
COMPANY_BACKGROUND_EVIDENCE_PATH = DATA_DIR / "company_background_evidence.jsonl"
COMPANY_CAPITAL_STRUCTURE_PATH = DATA_DIR / "company_capital_structure.csv"
MDR_CE_SEARCH_PLAN_PATH = DATA_DIR / "mdr_ce_search_plan.csv"

SEGMENT_META = {
    "ha": {"name": "HA / 透明质酸", "terms": ["hyaluronic", "透明质酸", "玻尿酸", "skin booster"]},
    "plla": {"name": "PLLA / PDLLA", "terms": ["plla", "pdlla", "聚乳酸", "aesthefill", "sculptra", "lanluma"]},
    "pcl": {
        "name": "PCL",
        "terms": [
            "pcl",
            "polycaprolactone",
            "liquid pcl",
            "液态pcl",
            "液体线",
            "gouri",
            "bravity",
            "ellanse",
            "miracle l",
            "miracle h",
            "miracle touch",
        ],
    },
    "caha": {
        "name": "CaHA",
        "terms": ["caha", "calciumhydroxylapatite", "hydroxylapatite", "radiesse", "harmonyca", "羟基磷灰石"],
    },
    "pn_pdrn": {"name": "PN / PDRN", "terms": ["pn", "pdrn", "polynucleotide", "聚核苷酸"]},
    "exosome": {"name": "Exosome / Regenerative", "terms": ["exosome", "外泌体", "prp", "prf", "regenerative", "再生"]},
    "botulinum": {"name": "Botulinum Toxin", "terms": ["botulinum", "bont", "toxin", "肉毒", "botox", "dysport", "innotox"]},
    "ebd": {"name": "EBD Devices", "terms": ["ebd", "laser", "rf", "hifu", "ultrasound", "设备", "射频", "超声", "激光", "微针"]},
    "threads": {"name": "Threads", "terms": ["thread", "pdo", "线雕", "线材", "提拉线"]},
    "mesotherapy": {"name": "Mesotherapy", "terms": ["mesotherapy", "meso", "中胚层", "revitalizer"]},
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def json_error(handler: BaseHTTPRequestHandler, message: str, status: int = 400) -> None:
    json_response(handler, {"ok": False, "error": message}, status=status)


def json_response(handler: BaseHTTPRequestHandler, payload: dict | list, status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def tokenize(query: str) -> list[str]:
    raw = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
    return [item for item in raw if len(item) > 1 or item in {"pcl", "ha", "rf", "pn"}]


def fts_query(query: str) -> str:
    terms = tokenize(query)
    if not terms:
        return ""
    return " OR ".join(f'"{term}"' for term in terms[:8])


def detect_segment(query: str) -> str | None:
    blob = query.lower().replace(" ", "")
    for code, meta in SEGMENT_META.items():
        for term in meta["terms"]:
            if term.lower().replace(" ", "") in blob:
                return code
    return None


def search_evidence(query: str, limit: int = 20) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = connect()
    cur = conn.cursor()
    results: list[dict] = []
    fts = fts_query(query)
    if fts:
        try:
            rows = cur.execute(
                """
                SELECT e.*, bm25(evidence_fts) AS score
                FROM evidence_fts
                JOIN evidence e ON e.id = evidence_fts.rowid
                WHERE evidence_fts MATCH ?
                  AND e.content_type NOT IN ('conference', 'social_status')
                ORDER BY score
                LIMIT ?
                """,
                (fts, limit),
            ).fetchall()
            results = [row_dict(row) for row in rows]
        except sqlite3.OperationalError:
            results = []
    if not results:
        terms = tokenize(query)
        if terms:
            clauses = []
            params: list[str | int] = []
            for term in terms[:8]:
                clauses.append("LOWER(title || ' ' || subtitle || ' ' || body || ' ' || company || ' ' || brand) LIKE ?")
                params.append(f"%{term.lower()}%")
            params.append(limit)
            rows = cur.execute(
                f"""
                SELECT * FROM evidence
                WHERE content_type NOT IN ('conference', 'social_status')
                  AND ({' OR '.join(clauses)})
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        else:
            rows = cur.execute(
                "SELECT * FROM evidence WHERE content_type NOT IN ('conference', 'social_status') ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results = [row_dict(row) for row in rows]
    conn.close()
    return results


def products_for_query(query: str, segment: str | None, limit: int = 80) -> list[dict]:
    conn = connect()
    cur = conn.cursor()
    terms = tokenize(query)
    params: list[str | int] = []
    term_clause = ""
    if terms:
        term_clause = " OR ".join(["LOWER(search_blob) LIKE ?"] * min(len(terms), 6))
        params.extend(f"%{term.lower()}%" for term in terms[:6])
    if segment and term_clause:
        where = f"segments LIKE ? AND ({term_clause})"
        params = [f"%{segment}%"] + params
    elif segment:
        where = "segments LIKE ?"
        params = [f"%{segment}%"]
    elif term_clause:
        where = term_clause
    else:
        where = "1=1"
    params.append(limit)
    rows = cur.execute(
        f"""
        SELECT record_id, company, country, region, category_l1, category_l2, tech_type_std,
               brand, core_product, fda_status, ce_status, nmpa_status, kfda_status,
               segments, search_blob
        FROM products
        WHERE {where}
        LIMIT ?
        """,
        params,
    ).fetchall()
    conn.close()
    return [row_dict(row) for row in rows]


def metric_for_query(query: str, segment: str | None, limit: int = 12) -> list[dict]:
    conn = connect()
    cur = conn.cursor()
    terms = tokenize(query)
    clauses = []
    params: list[str | int] = []
    if segment:
        clauses.append("segments LIKE ?")
        params.append(f"%{segment}%")
    for term in terms[:6]:
        clauses.append("LOWER(search_blob) LIKE ?")
        params.append(f"%{term.lower()}%")
    where = " OR ".join(clauses) if clauses else "1=1"
    params.append(limit)
    rows = cur.execute(
        f"""
        SELECT data_type, category_l1, category_l2, category_l3, geo, value, unit, year,
               source_org, report_title, url, note, confidence
        FROM market_metrics
        WHERE {where}
        ORDER BY year DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    conn.close()
    return [row_dict(row) for row in rows]


def social_sources() -> list[dict]:
    conn = connect()
    rows = conn.execute("SELECT * FROM social_sources ORDER BY platform").fetchall()
    conn.close()
    return [row_dict(row) for row in rows]


def table_count(table: str) -> int:
    if not DB_PATH.exists():
        return 0
    conn = connect()
    try:
        value = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        value = 0
    conn.close()
    return int(value)


def scalar_query(sql: str) -> int:
    if not DB_PATH.exists():
        return 0
    conn = connect()
    try:
        value = conn.execute(sql).fetchone()[0]
    except sqlite3.OperationalError:
        value = 0
    conn.close()
    return int(value)


def review_queue(limit: int = 40) -> list[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT priority_rank, company, fact_group, target_label, source_lane,
                   expected_source, status, evidence_count
            FROM verification_queue
            ORDER BY priority_rank, id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    return [row_dict(row) for row in rows]


def review_items(kind: str, status: str = "needs_review", limit: int = 40) -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = connect()
    params: list[str | int] = []
    status_clause = ""
    if status and status != "all":
        status_clause = "WHERE review_status = ?"
        params.append(status)
    params.append(limit)
    try:
        if kind == "registration":
            rows = conn.execute(
                f"""
                SELECT source_key, source_record_id, company_id, product_id, company, brand,
                       jurisdiction, evidence_type, title, url, field_candidates, excerpt,
                       review_status, confidence, merge_status
                FROM evidence_staging
                {status_clause}
                ORDER BY CASE confidence
                  WHEN 'official_api_applicant_and_product_match_unreviewed' THEN 1
                  WHEN 'official_api_applicant_match_unreviewed' THEN 2
                  WHEN 'official_api_product_name_candidate_unreviewed' THEN 3
                  ELSE 4 END,
                  company, source_record_id
                LIMIT ?
                """,
                params,
            ).fetchall()
        elif kind == "company_background":
            rows = conn.execute(
                f"""
                SELECT company_id, company, priority_rank, fact_type, field_name, field_value,
                       source_key, source_name, source_url, captured_at, confidence, review_status
                FROM company_background_evidence
                {status_clause}
                ORDER BY priority_rank, company, field_name
                LIMIT ?
                """,
                params,
            ).fetchall()
        elif kind == "capital":
            rows = conn.execute(
                f"""
                SELECT company_id, priority_rank, company, stock_code_seed, exchange_seed,
                       ticker_symbol_seed, sec_cik, sec_entity_name, sec_tickers, sec_exchanges,
                       evidence_status, source_url, captured_at, review_status, notes
                FROM company_capital_structure
                {status_clause}
                ORDER BY priority_rank, company
                LIMIT ?
                """,
                params,
            ).fetchall()
        elif kind == "ce_plan":
            rows = conn.execute(
                f"""
                SELECT plan_id, priority_rank, company_id, company, brand, product_family,
                       category_l1, tech_type, evidence_target, source_key, source_name,
                       source_url, query, expected_evidence, review_status, automation_status
                FROM mdr_ce_search_plan
                {status_clause}
                ORDER BY priority_rank, company, product_family, source_key
                LIMIT ?
                """,
                params,
            ).fetchall()
        else:
            rows = []
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    items = [row_dict(row) for row in rows]
    for item in items:
        if kind == "registration":
            try:
                item["field_candidates"] = json.loads(item.get("field_candidates") or "{}")
            except json.JSONDecodeError:
                item["field_candidates"] = {}
    return items


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def read_csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def action_status(action: str) -> tuple[str, str]:
    mapping = {
        "approve": ("approved", "approved_for_merge"),
        "reject": ("rejected", "rejected"),
        "reset": ("needs_review", "staged_only"),
    }
    return mapping.get(action, ("needs_review", "staged_only"))


def update_review_file(kind: str, payload: dict, review_status: str, merge_status: str) -> bool:
    changed = False
    if kind == "registration":
        rows = read_jsonl(STAGING_JSONL_PATH)
        for row in rows:
            if (
                row.get("source_key") == payload.get("source_key")
                and row.get("source_record_id") == payload.get("source_record_id")
                and row.get("company_id") == payload.get("company_id")
            ):
                row["review_status"] = review_status
                row["merge_status"] = merge_status
                changed = True
        if changed:
            write_jsonl(STAGING_JSONL_PATH, rows)
    elif kind == "company_background":
        rows = read_jsonl(COMPANY_BACKGROUND_EVIDENCE_PATH)
        for row in rows:
            if (
                row.get("company_id") == payload.get("company_id")
                and row.get("source_key") == payload.get("source_key")
                and row.get("field_name") == payload.get("field_name")
            ):
                row["review_status"] = review_status
                changed = True
        if changed:
            write_jsonl(COMPANY_BACKGROUND_EVIDENCE_PATH, rows)
    elif kind == "capital":
        fieldnames, rows = read_csv_rows(COMPANY_CAPITAL_STRUCTURE_PATH)
        for row in rows:
            if row.get("company_id") == payload.get("company_id"):
                row["review_status"] = review_status
                changed = True
        if changed:
            write_csv_rows(COMPANY_CAPITAL_STRUCTURE_PATH, fieldnames, rows)
    elif kind == "ce_plan":
        fieldnames, rows = read_csv_rows(MDR_CE_SEARCH_PLAN_PATH)
        for row in rows:
            if row.get("plan_id") == payload.get("plan_id"):
                row["review_status"] = review_status
                changed = True
        if changed:
            write_csv_rows(MDR_CE_SEARCH_PLAN_PATH, fieldnames, rows)
    return changed


def update_review_db(kind: str, payload: dict, review_status: str, merge_status: str) -> None:
    conn = connect()
    if kind == "registration":
        conn.execute(
            """
            UPDATE evidence_staging
            SET review_status = ?, merge_status = ?
            WHERE source_key = ? AND source_record_id = ? AND company_id = ?
            """,
            (review_status, merge_status, payload.get("source_key"), payload.get("source_record_id"), payload.get("company_id")),
        )
        conn.execute(
            """
            UPDATE registration_evidence
            SET review_status = ?
            WHERE source_key = ? AND registration_no = ? AND company_id = ?
            """,
            (review_status, payload.get("source_key"), payload.get("source_record_id"), payload.get("company_id")),
        )
    elif kind == "company_background":
        conn.execute(
            """
            UPDATE company_background_evidence
            SET review_status = ?
            WHERE company_id = ? AND source_key = ? AND field_name = ?
            """,
            (review_status, payload.get("company_id"), payload.get("source_key"), payload.get("field_name")),
        )
    elif kind == "capital":
        conn.execute("UPDATE company_capital_structure SET review_status = ? WHERE company_id = ?", (review_status, payload.get("company_id")))
    elif kind == "ce_plan":
        conn.execute("UPDATE mdr_ce_search_plan SET review_status = ? WHERE plan_id = ?", (review_status, payload.get("plan_id")))
    conn.commit()
    conn.close()


def count_by(rows: list[dict], key: str, limit: int = 8) -> list[dict]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key) or "Unknown"
        counts[value] = counts.get(value, 0) + 1
    return [{"name": key, "value": value} for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]]


def format_counts(items: list[dict]) -> str:
    return ", ".join(f"{item['name']} {item['value']}" for item in items) or "暂无"


def build_answer(query: str) -> dict:
    segment = detect_segment(query)
    segment_name = SEGMENT_META.get(segment or "", {}).get("name", "相关赛道")
    products = products_for_query(query, segment)
    metrics = metric_for_query(query, segment)
    evidence = search_evidence(query, 12)

    companies = count_by(products, "company", 8)
    countries = count_by(products, "country", 8)
    regions = count_by(products, "region", 6)
    brands = count_by(products, "brand", 8)
    subtracks = count_by(products, "category_l2", 8)
    techs = count_by(products, "tech_type_std", 8)
    regulatory = {
        "FDA": sum(1 for item in products if item.get("fda_status")),
        "CE": sum(1 for item in products if item.get("ce_status")),
        "NMPA": sum(1 for item in products if item.get("nmpa_status")),
        "KFDA": sum(1 for item in products if item.get("kfda_status")),
    }

    if products:
        top_company_text = "、".join(item["name"] for item in companies[:5])
        top_country_text = "、".join(item["name"] for item in countries[:5])
        summary = (
            f"本地底库在“{segment_name}”附近找到 {len(products)} 条未审核产品/品牌线索，"
            f"主要公司包括 {top_company_text or '待补充'}，主要来源地覆盖 {top_country_text or '待补充'}。"
        )
    else:
        summary = "当前底库没有找到足够的结构化产品记录，回答主要来自本地报告和全文检索，仍需要进一步补证。"

    market_items = []
    for metric in metrics[:5]:
        value = metric.get("value")
        unit = metric.get("unit") or ""
        label = " / ".join(x for x in [metric.get("category_l1"), metric.get("category_l2"), metric.get("category_l3")] if x)
        market_items.append(
            f"{metric.get('geo') or 'Global'} {metric.get('year') or ''} {metric.get('data_type')}: {value:g} {unit} ({metric.get('source_org') or metric.get('report_title') or 'source-stated'})"
            if isinstance(value, (int, float))
            else f"{metric.get('geo') or 'Global'} {metric.get('year') or ''} {metric.get('data_type')}: {label}"
        )

    sections = [
        {
            "title": "产业分布",
            "items": [
                f"区域分布：{format_counts(regions)}",
                f"国家/来源地：{format_counts(countries)}",
                f"监管覆盖：FDA {regulatory['FDA']} / CE {regulatory['CE']} / NMPA {regulatory['NMPA']} / KFDA {regulatory['KFDA']} 条有字段记录。",
            ],
        },
        {
            "title": "子赛道与竞争",
            "items": [
                f"高频公司：{format_counts(companies)}",
                f"高频品牌：{format_counts(brands)}",
                f"子赛道/技术线：{format_counts(subtracks)}；核心技术：{format_counts(techs)}",
            ],
        },
        {
            "title": "市场、渗透与定价",
            "items": market_items
            + [
                "当前第一稿没有审计后的全球销量、ASP 或渠道成交价字段；市占率只能按产品覆盖、监管准入和公开样本声量做相对估算。",
                "价格/市占率如需进入正式判断，应后续接入采购报告、财报拆分、渠道价格表或经销商报价证据。",
            ],
        },
    ]
    citations = [
        {
            "id": item.get("id"),
            "type": item.get("content_type"),
            "title": item.get("title"),
            "subtitle": item.get("subtitle"),
            "source": item.get("source_file"),
            "url": item.get("url"),
        }
        for item in evidence[:8]
    ]
    gaps = [
        "Workbook-derived records are seed data until cross-checked against the official source class for that fact.",
        "No audited sales/market-share fields in the master workbook.",
        "No normalized price/ASP table in the current data folder.",
        "Registration and approved indications should follow regulator records; product/commercial identity should follow company official pages or IFU.",
        "Indication heatmaps are product-text signals, not verified label-approved indications.",
    ]
    confidence = "medium" if len(products) >= 5 else "low-to-medium"
    return {
        "query": query,
        "segment": segment,
        "segment_name": segment_name,
        "summary": summary,
        "confidence": confidence,
        "sections": sections,
        "citations": citations,
        "gaps": gaps,
        "counts": {
            "products": len(products),
            "subtracks": len(subtracks),
            "market_metrics": len(metrics),
            "evidence": len(evidence),
        },
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "GlobalAestheticsDashboard/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        if path == "/api/status":
            self.handle_status()
            return
        if path == "/api/search":
            query = qs.get("q", [""])[0]
            limit = int(qs.get("limit", ["20"])[0])
            json_response(self, {"query": query, "results": search_evidence(query, limit)})
            return
        if path == "/api/review-queue":
            limit = int(qs.get("limit", ["40"])[0])
            json_response(self, {"results": review_queue(limit)})
            return
        if path == "/api/review-items":
            kind = qs.get("type", ["registration"])[0]
            status = qs.get("status", ["needs_review"])[0]
            limit = int(qs.get("limit", ["40"])[0])
            json_response(self, {"type": kind, "status": status, "results": review_items(kind, status, limit)})
            return
        if path == "/api/ask":
            query = qs.get("q", [""])[0]
            json_response(self, build_answer(query))
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path != "/api/review-action":
            json_error(self, "unknown endpoint", status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as exc:
            json_error(self, f"invalid json: {exc}", status=400)
            return
        kind = payload.get("type")
        action = payload.get("action")
        if kind not in {"registration", "company_background", "capital", "ce_plan"}:
            json_error(self, "invalid review type", status=400)
            return
        if action not in {"approve", "reject", "reset"}:
            json_error(self, "invalid action", status=400)
            return
        review_status, merge_status = action_status(action)
        changed = update_review_file(kind, payload, review_status, merge_status)
        update_review_db(kind, payload, review_status, merge_status)
        json_response(self, {"ok": True, "type": kind, "action": action, "review_status": review_status, "file_updated": changed})

    def handle_status(self) -> None:
        manifest = {}
        if MANIFEST_PATH.exists():
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        social = social_sources() if DB_PATH.exists() else []
        json_response(
            self,
            {
                "ok": DB_PATH.exists(),
                "db_path": str(DB_PATH),
                "manifest": manifest,
                "social_sources": social,
                "verification": {
                    "company_master": table_count("company_master"),
                    "product_master": table_count("product_master"),
                    "registration_evidence": table_count("registration_evidence"),
                    "evidence_staging": table_count("evidence_staging"),
                    "verification_queue": table_count("verification_queue"),
                    "official_source_registry": scalar_query("SELECT COUNT(*) FROM official_source_registry WHERE scope_status != 'external_project'"),
                    "official_source_registry_all": table_count("official_source_registry"),
                    "external_project_sources": scalar_query("SELECT COUNT(*) FROM official_source_registry WHERE scope_status = 'external_project'"),
                    "market_snapshot": table_count("market_snapshot"),
                    "company_background_evidence": table_count("company_background_evidence"),
                    "company_capital_structure": table_count("company_capital_structure"),
                    "mdr_ce_search_plan": table_count("mdr_ce_search_plan"),
                    "seed_integrity_issues": table_count("seed_integrity_issues"),
                    "seed_integrity_high_issues": scalar_query("SELECT COUNT(*) FROM seed_integrity_issues WHERE severity IN ('critical','high')"),
                },
            },
        )

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        target = (WEB_DIR / path.lstrip("/")).resolve()
        if WEB_DIR not in target.parents and target != WEB_DIR:
            self.send_error(403)
            return
        if not target.exists() or target.is_dir():
            target = WEB_DIR / "index.html"
        content = target.read_bytes()
        mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js"}:
            mime += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8790, type=int)
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Global Aesthetics Dashboard running at http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()

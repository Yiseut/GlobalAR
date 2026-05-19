from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
PRODUCT_MASTER_PATH = DATA_DIR / "product_master.csv"
OUTPUT_PATH = DATA_DIR / "news_regulatory_event_candidates.csv"
DEFAULT_BRIEFING_OUTPUT = Path(r"E:\shared\code\briefing_v6\output")


FIELDS = [
    "candidate_id",
    "article_date",
    "captured_at",
    "briefing_file",
    "article_title",
    "article_title_zh",
    "article_url",
    "article_source",
    "company_id",
    "product_id",
    "company",
    "brand",
    "product_name",
    "jurisdiction",
    "regulator",
    "event_type",
    "candidate_indication",
    "candidate_approval_date",
    "candidate_excerpt",
    "matched_alias",
    "confidence",
    "status",
    "needs_official_verification",
    "official_query",
]


GENERIC_ALIASES = {
    "ha",
    "pcl",
    "pla",
    "caha",
    "ebd",
    "rf",
    "filler",
    "fillers",
    "dermal filler",
    "ha dermal filler",
    "skin booster",
    "surgical implants",
    "pipeline",
    "skin",
    "image",
    "injectable",
    "injectables",
    "body contouring",
    "soft body filler",
    "facial rejuvenation",
    "regenerative aesthetics",
    "collagen",
    "across",
    "laser",
    "energy platform",
    "meso cocktail",
}


REGULATOR_PATTERNS = {
    "FDA": re.compile(r"\b(FDA|U\.S\. Food and Drug Administration|美国食品药品监督管理局)\b", re.I),
    "CE/MDR": re.compile(r"\b(CE mark|CE marked|MDR|EUDAMED|欧盟|CE/MDR)\b", re.I),
    "Health Canada": re.compile(r"\bHealth Canada\b|加拿大卫生部", re.I),
    "TGA": re.compile(r"\b(TGA|ARTG)\b|澳大利亚", re.I),
    "ANVISA": re.compile(r"\bANVISA\b|巴西", re.I),
    "MFDS": re.compile(r"\b(MFDS|KFDA)\b|韩国", re.I),
}


ACTION_RE = re.compile(
    r"\b(approved|approval|cleared|clearance|authorized|expanded indication|new indication|indicated for|PMA supplement|510\(k\))\b"
    r"|获批|批准|准入|新增适应症|扩大适应症|适应症获批",
    re.I,
)


EVENT_TYPE_PATTERNS = [
    ("new_or_expanded_indication", re.compile(r"new indication|expanded indication|新增适应症|扩大适应症|获批.*适应症", re.I)),
    ("approval_or_clearance", re.compile(r"approved|approval|cleared|clearance|authorized|获批|批准|准入", re.I)),
    ("official_label_or_ifu", re.compile(r"indicated for|适用于|用于", re.I)),
]


INDICATION_PATTERNS = [
    re.compile(r"FDA\s+has\s+approved\s+[^.]{0,120}?\s+for\s+the\s+([^.;\n]{5,220})", re.I),
    re.compile(r"approved\s+[^.]{0,120}?\s+for\s+the\s+([^.;\n]{5,220})", re.I),
    re.compile(r"approved\s+[^.]{0,120}?\s+for\s+([^.;\n]{5,220})", re.I),
    re.compile(r"indicated\s+for\s+([^.;\n]{5,220})", re.I),
    re.compile(r"批准[^。；\n]{0,80}?用于([^。；\n]{5,180})", re.I),
    re.compile(r"获批[^。；\n]{0,80}?用于([^。；\n]{5,180})", re.I),
    re.compile(r"用于([^。；\n]{5,180}?)(?:，|。|；)", re.I),
]


DATE_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})")


@dataclass(frozen=True)
class ProductAlias:
    product_id: str
    company_id: str
    company: str
    brand: str
    product_name: str
    alias: str
    alias_norm: str


def now_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def norm(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def normalize_match(text: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(text or "").lower()).strip()


def short_hash(text: str, length: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:length]


def source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return re.sub(r"^www\.", "", host) or ""


def clean_text(text: object, limit: int | None = None) -> str:
    value = html.unescape(norm(text))
    value = re.sub(r"[_*`#]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if limit and len(value) > limit:
        return value[: limit - 1].rstrip() + "..."
    return value


def load_product_aliases() -> list[ProductAlias]:
    if not PRODUCT_MASTER_PATH.exists():
        return []
    aliases: dict[tuple[str, str], ProductAlias] = {}
    with PRODUCT_MASTER_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            company = norm(row.get("company"))
            brand = norm(row.get("brand"))
            product_name = norm(row.get("standard_product_name") or row.get("registered_name") or row.get("core_product") or brand)
            product_id = norm(row.get("product_id"))
            company_id = norm(row.get("company_id"))
            candidates = {
                brand,
                product_name,
                norm(row.get("registered_name")),
                norm(row.get("core_product")),
                f"{brand} {product_name}".strip(),
            }
            for alias in candidates:
                alias = clean_alias(alias)
                if not alias:
                    continue
                key = (product_id, normalize_match(alias))
                aliases[key] = ProductAlias(
                    product_id=product_id,
                    company_id=company_id,
                    company=company,
                    brand=brand,
                    product_name=product_name,
                    alias=alias,
                    alias_norm=normalize_match(alias),
                )
    return sorted(aliases.values(), key=lambda item: (-len(item.alias_norm), item.company, item.brand))


def clean_alias(alias: str) -> str:
    alias = norm(alias)
    if not alias:
        return ""
    alias = re.sub(r"\s*\([^)]*\)\s*", " ", alias).strip()
    alias = re.sub(r"\s*/\s*(R&D|Pipeline|研究|管线)\b.*$", "", alias, flags=re.I).strip()
    alias_norm = normalize_match(alias)
    if alias_norm in GENERIC_ALIASES:
        return ""
    if len(alias_norm) < 4:
        return ""
    if alias_norm in {"contour", "volume", "intense", "stimulate", "organic", "advance", "across"}:
        return ""
    return alias


def has_regulatory_signal(text: str) -> bool:
    if not ACTION_RE.search(text):
        return False
    return any(pattern.search(text) for pattern in REGULATOR_PATTERNS.values())


def detect_regulator(text: str) -> tuple[str, str]:
    for regulator, pattern in REGULATOR_PATTERNS.items():
        if pattern.search(text):
            if regulator == "FDA":
                return "US", regulator
            if regulator == "CE/MDR":
                return "EU / Global", regulator
            if regulator in {"TGA", "ANVISA", "Health Canada"}:
                return regulator.replace("Health Canada", "Canada"), regulator
            if regulator == "MFDS":
                return "South Korea", regulator
            return "", regulator
    return "", ""


def detect_event_type(text: str) -> str:
    for label, pattern in EVENT_TYPE_PATTERNS:
        if pattern.search(text):
            return label
    return "regulatory_signal"


def extract_date(text: str, fallback: str = "") -> str:
    match = DATE_RE.search(text)
    if not match:
        return fallback
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def extract_indication(text: str) -> str:
    compact = clean_text(text, 3000)
    for pattern in INDICATION_PATTERNS:
        match = pattern.search(compact)
        if match:
            value = clean_text(match.group(1), 260)
            value = re.sub(r"\s+in\s+patients.*$", lambda m: m.group(0), value, flags=re.I)
            return value.strip(" .;:：，")
    return ""


def article_blocks(path: Path) -> list[dict[str, str]]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    blocks = []
    for title_node in soup.select("h4.article-title"):
        link_node = title_node.find("a", href=True)
        title = clean_text(link_node.get_text(" ", strip=True) if link_node else title_node.get_text(" ", strip=True))
        url = norm(link_node.get("href") if link_node else "")
        title_zh = ""
        date_text = ""
        body_parts = []
        cursor = title_node.find_next_sibling()
        while cursor is not None and getattr(cursor, "name", "") != "h4":
            classes = set(cursor.get("class") or [])
            if "article-title-zh" in classes:
                title_zh = clean_text(cursor.get_text(" ", strip=True))
            elif "article-meta" in classes:
                date_text = clean_text(cursor.get_text(" ", strip=True))
            elif cursor.name == "details" or "full-text-block" in classes:
                body_parts.append(clean_text(cursor.get_text(" ", strip=True), 8000))
            cursor = cursor.find_next_sibling()
        body = clean_text(" ".join([title, title_zh, *body_parts]), 12000)
        blocks.append(
            {
                "briefing_file": str(path),
                "article_title": title,
                "article_title_zh": title_zh,
                "article_url": url,
                "article_source": source_from_url(url),
                "article_date": extract_date(date_text or title or body),
                "body": body,
            }
        )
    return blocks


def briefing_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files = []
    for path in root.rglob("*.html"):
        name = path.name.lower()
        if "_wechat" in name:
            continue
        if path.stat().st_size < 500:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)


def alias_in_normalized(alias_norm: str, normalized_text: str) -> bool:
    if not alias_norm:
        return False
    if re.search(r"[\u4e00-\u9fff]", alias_norm):
        return alias_norm in normalized_text
    pattern = r"(?<![a-z0-9])" + re.escape(alias_norm) + r"(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def matched_products(article: dict[str, str], aliases: list[ProductAlias]) -> list[ProductAlias]:
    headline = " ".join([article.get("article_title", ""), article.get("article_title_zh", "")])
    headline_normalized = normalize_match(headline)
    body_normalized = normalize_match(article.get("body", ""))

    def collect(normalized: str, limit: int) -> list[ProductAlias]:
        found = []
        seen = set()
        for item in aliases:
            if item.product_id in seen:
                continue
            if alias_in_normalized(item.alias_norm, normalized):
                seen.add(item.product_id)
                found.append(item)
                if len(found) >= limit:
                    break
        return prefer_specific_aliases(found)

    headline_hits = collect(headline_normalized, 5)
    if headline_hits:
        return headline_hits

    hits = []
    seen = set()
    for item in aliases:
        if alias_in_normalized(item.alias_norm, body_normalized):
            key = item.product_id
            if key in seen:
                continue
            seen.add(key)
            hits.append(item)
            if len(hits) >= 5:
                break
    return hits


def prefer_specific_aliases(items: list[ProductAlias]) -> list[ProductAlias]:
    kept = []
    for item in items:
        broader_match = False
        for other in items:
            if other.product_id == item.product_id:
                continue
            if len(other.alias_norm) <= len(item.alias_norm):
                continue
            if item.alias_norm and alias_in_normalized(item.alias_norm, other.alias_norm):
                broader_match = True
                break
        if not broader_match:
            kept.append(item)
    return kept


def build_candidate(article: dict[str, str], product: ProductAlias, captured_at: str) -> dict[str, str]:
    text = article["body"]
    jurisdiction, regulator = detect_regulator(text)
    event_type = detect_event_type(text)
    indication = extract_indication(text)
    approval_date = extract_date(text, article.get("article_date", ""))
    excerpt = clean_text(text, 520)
    official_query_parts = [product.company, product.brand, product.product_name, regulator, indication, "official approval"]
    candidate_id = "news_" + short_hash("|".join([article.get("article_url", ""), article.get("article_title", ""), product.product_id, indication, regulator]))
    return {
        "candidate_id": candidate_id,
        "article_date": article.get("article_date", ""),
        "captured_at": captured_at,
        "briefing_file": article.get("briefing_file", ""),
        "article_title": article.get("article_title", ""),
        "article_title_zh": article.get("article_title_zh", ""),
        "article_url": article.get("article_url", ""),
        "article_source": article.get("article_source", ""),
        "company_id": product.company_id,
        "product_id": product.product_id,
        "company": product.company,
        "brand": product.brand,
        "product_name": product.product_name,
        "jurisdiction": jurisdiction,
        "regulator": regulator,
        "event_type": event_type,
        "candidate_indication": indication,
        "candidate_approval_date": approval_date,
        "candidate_excerpt": excerpt,
        "matched_alias": product.alias,
        "confidence": "news_regulatory_signal_needs_official_verification",
        "status": "candidate_unverified",
        "needs_official_verification": "yes",
        "official_query": clean_text(" ".join(part for part in official_query_parts if part), 360),
    }


def scan(root: Path, limit_files: int = 260) -> list[dict[str, str]]:
    aliases = load_product_aliases()
    captured_at = now_iso()
    rows: dict[str, dict[str, str]] = {}
    for path in briefing_files(root)[:limit_files]:
        for article in article_blocks(path):
            text = article["body"]
            if not has_regulatory_signal(text):
                continue
            for product in matched_products(article, aliases):
                row = build_candidate(article, product, captured_at)
                rows[row["candidate_id"]] = row
    return sorted(rows.values(), key=lambda row: (row.get("article_date", ""), row.get("company", ""), row.get("brand", "")), reverse=True)


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sync briefing HTML regulatory news into a structured candidate table.")
    parser.add_argument("--briefing-output", type=Path, default=DEFAULT_BRIEFING_OUTPUT)
    parser.add_argument("--limit-files", type=int, default=260)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    existing_rows: dict[str, dict[str, str]] = {}
    if args.output.exists():
        with args.output.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                candidate_id = row.get("candidate_id", "")
                if candidate_id:
                    existing_rows[candidate_id] = {field: row.get(field, "") for field in FIELDS}

    rows = scan(args.briefing_output, args.limit_files)
    new_rows = sum(1 for row in rows if row.get("candidate_id") not in existing_rows)
    merged_rows = {
        candidate_id: row
        for candidate_id, row in existing_rows.items()
        if row.get("status") not in {"candidate_unverified", ""}
    }
    for row in rows:
        merged_rows[row["candidate_id"]] = row
    output_rows = sorted(merged_rows.values(), key=lambda row: (row.get("article_date", ""), row.get("company", ""), row.get("brand", "")), reverse=True)
    write_rows(output_rows, args.output)
    regulators = {}
    for row in output_rows:
        regulators[row.get("regulator") or "Unknown"] = regulators.get(row.get("regulator") or "Unknown", 0) + 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "rows": len(output_rows),
                "scanned_rows": len(rows),
                "candidate_new_rows": new_rows,
                "regulators": regulators,
                "restylane_contour": sum(1 for row in output_rows if "restylane contour" in row.get("brand", "").lower()),
                "radiesse": sum(1 for row in output_rows if "radiesse" in row.get("brand", "").lower()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

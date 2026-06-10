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
BRIEFING_UPDATE_PATH = DATA_DIR / "briefing_update_candidates.csv"
SYNC_STATE_PATH = DATA_DIR / "briefing_news_sync_state.json"
SUMMARY_PATH = DATA_DIR / "audits" / "briefing_update_summary_latest.md"
PRODUCT_GAP_QUEUE_PATH = DATA_DIR / "audits" / "product_gap_queue_latest.csv"
DEFAULT_BRIEFING_OUTPUT = Path(r"E:\shared\code\briefing_v6\output")
SHORT_BODY_THRESHOLD = 450


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

UPDATE_FIELDS = [
    "candidate_id",
    "event_group",
    "event_type",
    "article_date",
    "company_id",
    "product_id",
    "company",
    "brand",
    "product_name",
    "market_or_jurisdiction",
    "source_domain",
    "article_url",
    "briefing_file",
    "body_quality",
    "excerpt",
    "confidence_score",
    "status",
    "needs_fulltext_rescue",
    "needs_official_verification",
    "official_query",
    "promotion_target",
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
    "booster",
    "boosters",
    "growth factor",
    "growth factors",
    "botulinum toxin",
    "botulinum toxin a",
    "breast implants",
    "microneedling device",
    "medical device",
    "device",
    "body contouring",
    "body sculpting",
    "hifu",
    "rf",
    "radiofrequency",
    "mesotherapy",
    "skin care",
    "skincare",
    "post procedure",
    "post procedure care",
    "home care",
    "professional",
    "light therapy",
    "skin analysis",
    "body contouring",
    "body sculpting",
    "body shaping",
    "facial treatment",
    "aesthetic medicine",
    "medical aesthetics",
    "身体塑形",
    "身体塑型",
    "身体雕塑",
    "体雕",
    "塑形",
    "皮肤管理",
    "水光",
    "水光针",
    "微针",
    "射频微针",
    "医美器械",
    "医疗器械",
}

GENERIC_COMPANY_ALIASES = {
    "across",
    "advance",
    "advance esthetic",
    "advance aesthetics",
    "advanced aesthetic",
    "advanced aesthetics",
    "aesthetic",
    "aesthetics",
    "esthetic",
    "esthetics",
    "medical aesthetics",
    "crown",
    "fusion",
    "image",
    "organic",
    "skin tech",
}

GENERIC_PRODUCT_TOKENS = {
    "aesthetic",
    "aesthetics",
    "body",
    "booster",
    "boosters",
    "care",
    "collagen",
    "contouring",
    "device",
    "dermal",
    "energy",
    "facial",
    "filler",
    "fillers",
    "growth",
    "ha",
    "hifu",
    "home",
    "laser",
    "light",
    "medical",
    "meso",
    "mesotherapy",
    "microneedling",
    "post",
    "procedure",
    "professional",
    "radiofrequency",
    "rf",
    "sculpting",
    "shaping",
    "skin",
    "therapy",
    "treatment",
    "ultrasound",
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
REPORT_DATE_RE = re.compile(r"全球行业资讯-(20\d{2}-\d{2}-\d{2})_")

EVENT_GROUP_PATTERNS = {
    "indication_expansion": re.compile(
        r"expanded indication|new indication|new FDA-approved use|approved use|indicated for|"
        r"approved[^.\n]{0,140}\bfor\b|获批[^。；\n]{0,80}适应症|新增适应症|扩大适应症|用于改善|用于治疗",
        re.I,
    ),
    "regulatory_approval": re.compile(
        r"\b(FDA|CE-MDR|CE mark|CE marked|MDR|MFDS|KFDA|TFDA|TGA|ANVISA|Health Canada|510\(k\)|PMA|BLA)\b"
        r"|approved|approval|cleared|clearance|authorized|certification|获批|批准|认证|注册|准入",
        re.I,
    ),
    "product_launch": re.compile(
        r"\b(launch|launches|launched|unveils|introduces|introduced|debuts|rolls out|new .*device|new .*product|enhanced .*series)\b"
        r"|推出|发布|上市|新品|新产品|新设备|亮相",
        re.I,
    ),
    "commercial_performance": re.compile(
        r"\b(revenue|sales|profit|earnings|stock|shares|growth|CAGR|market size|forecast|guidance|export|exports|Q[1-4]|IPO)\b"
        r"|增长|营收|利润|销售|股价|市场规模|出口|业绩|财报|毛利|净利",
        re.I,
    ),
    "channel_coverage": re.compile(
        r"\b(distribution|distributor|exclusive|partnership|partner|market entry|expands presence|enters [A-Z][A-Za-z]+|"
        r"overseas markets|professional channel|Europe|Southeast Asia|Lithuania|U\.S\. market)\b"
        r"|渠道|经销|分销|独家|合作|进入.*市场|海外市场|欧洲|东南亚|立陶宛",
        re.I,
    ),
}

PROMOTION_TARGETS = {
    "indication_expansion": "official_indication_evidence",
    "regulatory_approval": "registration_evidence",
    "product_launch": "product_gap_queue",
    "commercial_performance": "market_snapshot_or_company_note",
    "channel_coverage": "company_market_presence",
}

EVENT_GROUP_LABELS = {
    "indication_expansion": "new_or_expanded_indication",
    "regulatory_approval": "approval_or_clearance",
    "product_launch": "product_launch",
    "commercial_performance": "commercial_performance",
    "channel_coverage": "channel_coverage",
}

MARKET_PATTERNS = [
    ("US", re.compile(r"\b(United States|U\.S\.|US|FDA|510\(k\)|PMA)\b|美国", re.I)),
    ("EU / Global", re.compile(r"\b(Europe|European|EU|CE-MDR|CE mark|MDR|Lithuania)\b|欧洲|欧盟|立陶宛", re.I)),
    ("South Korea", re.compile(r"\b(South Korea|Korea|MFDS|KFDA|KOSDAQ|KRX)\b|韩国", re.I)),
    ("Taiwan", re.compile(r"\b(Taiwan|TFDA)\b|台湾", re.I)),
    ("Canada", re.compile(r"\b(Canada|Health Canada)\b|加拿大", re.I)),
    ("Brazil", re.compile(r"\b(Brazil|ANVISA)\b|巴西", re.I)),
    ("Australia", re.compile(r"\b(Australia|TGA|ARTG)\b|澳大利亚", re.I)),
    ("Southeast Asia", re.compile(r"\b(Southeast Asia|Thailand|Vietnam|Indonesia|Malaysia|Singapore)\b|东南亚|泰国|越南", re.I)),
]


@dataclass(frozen=True)
class ProductAlias:
    product_id: str
    company_id: str
    company: str
    brand: str
    product_name: str
    alias: str
    alias_norm: str


@dataclass(frozen=True)
class CompanyAlias:
    company_id: str
    company: str
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


def clean_company_alias(alias: str) -> str:
    alias = norm(alias)
    if not alias:
        return ""
    alias = re.sub(r"\s*\([^)]*\)\s*", " ", alias).strip()
    alias_norm = normalize_match(alias)
    if alias_norm in GENERIC_COMPANY_ALIASES:
        return ""
    if len(alias_norm) < 4:
        return ""
    return alias


def load_product_rows() -> list[dict[str, str]]:
    if not PRODUCT_MASTER_PATH.exists():
        return []
    with PRODUCT_MASTER_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_product_aliases() -> list[ProductAlias]:
    aliases: dict[tuple[str, str], ProductAlias] = {}
    for row in load_product_rows():
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


def load_company_aliases() -> list[CompanyAlias]:
    aliases: dict[tuple[str, str], CompanyAlias] = {}
    for row in load_product_rows():
        company = norm(row.get("company"))
        company_id = norm(row.get("company_id"))
        for alias in {company, norm(row.get("legal_manufacturer")), norm(row.get("marketing_holder"))}:
            alias = clean_company_alias(alias)
            if not alias:
                continue
            key = (company_id, normalize_match(alias))
            aliases[key] = CompanyAlias(company_id=company_id, company=company, alias=alias, alias_norm=normalize_match(alias))
    return sorted(aliases.values(), key=lambda item: (-len(item.alias_norm), item.company))


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


def detect_event_groups(text: str) -> list[str]:
    groups = [group for group, pattern in EVENT_GROUP_PATTERNS.items() if pattern.search(text)]
    if "indication_expansion" in groups and "regulatory_approval" not in groups:
        groups.insert(0, "regulatory_approval")
    ordered = ["indication_expansion", "regulatory_approval", "product_launch", "commercial_performance", "channel_coverage"]
    return [group for group in ordered if group in set(groups)]


def detect_market_or_jurisdiction(text: str) -> str:
    jurisdiction, regulator = detect_regulator(text)
    if jurisdiction:
        return jurisdiction
    for market, pattern in MARKET_PATTERNS:
        if pattern.search(text):
            return market
    return ""


def event_type_for_group(group: str, text: str) -> str:
    if group == "regulatory_approval":
        return detect_event_type(text)
    return EVENT_GROUP_LABELS.get(group, group)


def body_quality(article: dict[str, str]) -> str:
    return "title_or_snippet_only" if len(article.get("body", "")) < SHORT_BODY_THRESHOLD else "full_or_substantial"


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


def report_date(path: Path) -> str:
    match = REPORT_DATE_RE.search(path.name)
    return match.group(1) if match else ""


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


def briefing_files(root: Path, days: int | None = None) -> list[Path]:
    if not root.exists():
        return []
    files = []
    min_date = None
    if days:
        tz = timezone(timedelta(hours=8))
        min_date = (datetime.now(tz).date() - timedelta(days=max(days - 1, 0))).isoformat()
    for path in root.rglob("*.html"):
        name = path.name.lower()
        if "_wechat" in name:
            continue
        if "_selection_workbench" in name:
            continue
        if not path.name.startswith("全球行业资讯-"):
            continue
        if min_date and report_date(path) and report_date(path) < min_date:
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


def is_specific_product_alias(item: ProductAlias) -> bool:
    if item.alias_norm in GENERIC_ALIASES:
        return False
    if re.search(r"[\u4e00-\u9fff]", item.alias_norm):
        return len(item.alias_norm) >= 4 and item.alias_norm not in GENERIC_ALIASES
    tokens = item.alias_norm.split()
    if not tokens:
        return False
    if len(tokens) >= 2 and all(token in GENERIC_PRODUCT_TOKENS for token in tokens):
        return False
    if len(tokens) == 1 and tokens[0] in GENERIC_PRODUCT_TOKENS:
        return False
    return len(item.alias_norm) >= 5


def matched_companies(article: dict[str, str], aliases: list[CompanyAlias], limit: int = 6) -> list[CompanyAlias]:
    headline = " ".join([article.get("article_title", ""), article.get("article_title_zh", "")])
    headline_normalized = normalize_match(headline)
    body_normalized = normalize_match(article.get("body", ""))

    def collect(normalized: str, limit_count: int) -> list[CompanyAlias]:
        found = []
        seen = set()
        for item in aliases:
            if item.company_id in seen:
                continue
            if alias_in_normalized(item.alias_norm, normalized):
                seen.add(item.company_id)
                found.append(item)
                if len(found) >= limit_count:
                    break
        return found

    headline_hits = collect(headline_normalized, limit)
    if headline_hits:
        return headline_hits

    return collect(body_normalized, limit)


def matched_products(
    article: dict[str, str],
    aliases: list[ProductAlias],
    company_hits: list[CompanyAlias] | None = None,
    limit: int = 5,
) -> list[ProductAlias]:
    headline = " ".join([article.get("article_title", ""), article.get("article_title_zh", "")])
    headline_normalized = normalize_match(headline)
    body_normalized = normalize_match(article.get("body", ""))
    company_ids = {item.company_id for item in company_hits or []}

    def collect(normalized: str, require_company: bool, limit_count: int) -> list[ProductAlias]:
        hits = []
        seen = set()
        for item in aliases:
            if require_company and company_ids and item.company_id not in company_ids:
                continue
            if item.product_id in seen:
                continue
            if alias_in_normalized(item.alias_norm, normalized):
                seen.add(item.product_id)
                hits.append(item)
                if len(hits) >= limit_count:
                    break
        return prefer_specific_aliases(hits)

    headline_hits = collect(headline_normalized, False, limit)
    if company_ids and headline_hits:
        constrained = [item for item in headline_hits if item.company_id in company_ids]
        if constrained:
            return constrained
    if headline_hits:
        return [item for item in headline_hits if is_specific_product_alias(item)]

    if company_ids:
        body_hits = collect(body_normalized, True, limit)
        if body_hits:
            return body_hits

    hits = []
    seen = set()
    for item in aliases:
        if len(item.alias_norm) < 9:
            continue
        if not is_specific_product_alias(item):
            continue
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


def derive_article_subject(article: dict[str, str]) -> str:
    title = clean_text(article.get("article_title", ""))
    title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
    patterns = [
        r"\b(wins|receives|secures|gets|launches|launched|unveils|introduces|sees|expands|enters|partners|signs|returns)\b",
        r"获批|获得|推出|发布|扩张|进入|签署|营收|利润|股价|增长",
    ]
    for pattern in patterns:
        match = re.search(pattern, title, flags=re.I)
        if match and match.start() >= 2:
            return clean_text(title[: match.start()].strip(" -:：\"'“”"), 140)
    return clean_text(title, 140)


def confidence_score(
    article: dict[str, str],
    event_group: str,
    product: ProductAlias | None = None,
    company: CompanyAlias | None = None,
) -> int:
    headline = " ".join([article.get("article_title", ""), article.get("article_title_zh", "")])
    headline_norm = normalize_match(headline)
    body_norm = normalize_match(article.get("body", ""))
    text = article.get("body", "")
    score = 30
    if body_quality(article) == "full_or_substantial":
        score += 14
    if product and alias_in_normalized(product.alias_norm, headline_norm):
        score += 28
    elif product and alias_in_normalized(product.alias_norm, body_norm):
        score += 14
    if company and alias_in_normalized(company.alias_norm, headline_norm):
        score += 18
    elif company and alias_in_normalized(company.alias_norm, body_norm):
        score += 9
    if event_group in {"regulatory_approval", "indication_expansion"} and has_regulatory_signal(text):
        score += 14
    if event_group in {"commercial_performance", "channel_coverage"}:
        score += 6
    if body_quality(article) == "title_or_snippet_only":
        score = min(score, 62)
    if not product and not company:
        score = min(score, 54)
    return max(20, min(score, 95))


def official_query_for(
    article: dict[str, str],
    event_group: str,
    market: str,
    product: ProductAlias | None = None,
    company: CompanyAlias | None = None,
) -> str:
    subject = product.company if product else company.company if company else derive_article_subject(article)
    parts = [
        subject,
        product.brand if product else "",
        product.product_name if product else "",
        market,
        EVENT_GROUP_LABELS.get(event_group, event_group),
        "official source",
        "approval" if event_group in {"regulatory_approval", "indication_expansion"} else "",
    ]
    return clean_text(" ".join(part for part in parts if part), 360)


def build_update_candidate(
    article: dict[str, str],
    event_group: str,
    captured_at: str,
    product: ProductAlias | None = None,
    company: CompanyAlias | None = None,
) -> dict[str, str]:
    text = article.get("body", "")
    market = detect_market_or_jurisdiction(text)
    event_type = event_type_for_group(event_group, text)
    company_id = product.company_id if product else company.company_id if company else ""
    company_name = product.company if product else company.company if company else derive_article_subject(article)
    brand = product.brand if product else ""
    product_name = product.product_name if product else ""
    product_id = product.product_id if product else ""
    identity = "|".join(
        [
            event_group,
            article.get("article_url", ""),
            article.get("article_title", ""),
            company_id or company_name,
            product_id,
            brand,
            product_name,
        ]
    )
    return {
        "candidate_id": "briefing_" + short_hash(identity, 14),
        "event_group": event_group,
        "event_type": event_type,
        "article_date": article.get("article_date", ""),
        "company_id": company_id,
        "product_id": product_id,
        "company": company_name,
        "brand": brand,
        "product_name": product_name,
        "market_or_jurisdiction": market,
        "source_domain": article.get("article_source", ""),
        "article_url": article.get("article_url", ""),
        "briefing_file": article.get("briefing_file", ""),
        "body_quality": body_quality(article),
        "excerpt": clean_text(text, 620),
        "confidence_score": str(confidence_score(article, event_group, product, company)),
        "status": "candidate_unverified",
        "needs_fulltext_rescue": "yes" if body_quality(article) == "title_or_snippet_only" else "no",
        "needs_official_verification": "yes",
        "official_query": official_query_for(article, event_group, market, product, company),
        "promotion_target": PROMOTION_TARGETS.get(event_group, "review_queue"),
    }


def should_keep_unmatched_event(article: dict[str, str], event_group: str) -> bool:
    if event_group in {"commercial_performance", "channel_coverage", "product_launch", "regulatory_approval", "indication_expansion"}:
        title = " ".join([article.get("article_title", ""), article.get("article_title_zh", "")])
        return bool(title and article.get("article_url") and EVENT_GROUP_PATTERNS[event_group].search(title + " " + article.get("body", "")[:800]))
    return False


def scan_update_candidates(root: Path, days: int = 8, limit_files: int = 260) -> list[dict[str, str]]:
    product_aliases = load_product_aliases()
    company_aliases = load_company_aliases()
    captured_at = now_iso()
    rows: dict[str, dict[str, str]] = {}
    for path in briefing_files(root, days=days)[:limit_files]:
        for article in article_blocks(path):
            text = article["body"]
            groups = detect_event_groups(text)
            if not groups:
                continue
            company_hits = matched_companies(article, company_aliases)
            product_hits = matched_products(article, product_aliases, company_hits)
            for event_group in groups:
                if product_hits:
                    for product in product_hits:
                        company = next((item for item in company_hits if item.company_id == product.company_id), None)
                        row = build_update_candidate(article, event_group, captured_at, product=product, company=company)
                        rows[row["candidate_id"]] = row
                elif company_hits:
                    for company in company_hits[:3]:
                        row = build_update_candidate(article, event_group, captured_at, company=company)
                        rows[row["candidate_id"]] = row
                elif should_keep_unmatched_event(article, event_group):
                    row = build_update_candidate(article, event_group, captured_at)
                    rows[row["candidate_id"]] = row
    return sorted(
        rows.values(),
        key=lambda row: (row.get("article_date", ""), int(row.get("confidence_score") or 0), row.get("company", "")),
        reverse=True,
    )


def scan(root: Path, limit_files: int = 260, days: int | None = None) -> list[dict[str, str]]:
    aliases = load_product_aliases()
    company_aliases = load_company_aliases()
    captured_at = now_iso()
    rows: dict[str, dict[str, str]] = {}
    for path in briefing_files(root, days=days)[:limit_files]:
        for article in article_blocks(path):
            text = article["body"]
            if not has_regulatory_signal(text):
                continue
            company_hits = matched_companies(article, company_aliases)
            for product in matched_products(article, aliases, company_hits):
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


def read_rows(path: Path, fields: list[str]) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_id = row.get("candidate_id", "")
            if candidate_id:
                rows[candidate_id] = {field: row.get(field, "") for field in fields}
    return rows


def merge_candidate_rows(
    existing_rows: dict[str, dict[str, str]],
    scanned_rows: list[dict[str, str]],
    default_status: str = "candidate_unverified",
) -> tuple[list[dict[str, str]], int]:
    new_rows = sum(1 for row in scanned_rows if row.get("candidate_id") not in existing_rows)
    merged_rows = {
        candidate_id: row
        for candidate_id, row in existing_rows.items()
        if row.get("status") not in {default_status, ""}
    }
    for row in scanned_rows:
        previous = existing_rows.get(row["candidate_id"], {})
        if previous.get("status") not in {"", default_status, None}:
            kept = {**row, **previous}
            merged_rows[row["candidate_id"]] = kept
        else:
            merged_rows[row["candidate_id"]] = row
    return (
        sorted(
            merged_rows.values(),
            key=lambda row: (row.get("article_date", ""), int(row.get("confidence_score") or 0), row.get("company", "")),
            reverse=True,
        ),
        new_rows,
    )


def write_update_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UPDATE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in UPDATE_FIELDS})


def load_gap_priorities() -> dict[str, str]:
    priorities: dict[str, str] = {}
    if not PRODUCT_GAP_QUEUE_PATH.exists():
        return priorities
    with PRODUCT_GAP_QUEUE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            product_id = row.get("product_id", "")
            priority = row.get("priority", "")
            if product_id and priority:
                priorities[product_id] = priority
    return priorities


def count_by(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(field) or "Unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def write_summary(rows: list[dict[str, str]], new_rows: int, scanned_files: list[Path], path: Path = SUMMARY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gap_priorities = load_gap_priorities()
    p0_p1 = [
        row
        for row in rows
        if gap_priorities.get(row.get("product_id", "")) in {"P0", "P1"}
        and row.get("status") == "candidate_unverified"
    ]
    rescue = [row for row in rows if row.get("needs_fulltext_rescue") == "yes"]
    low_conf = [row for row in rows if int(row.get("confidence_score") or 0) < 60]
    official = [row for row in rows if row.get("needs_official_verification") == "yes"]

    def bullet(row: dict[str, str]) -> str:
        title = clean_text(row.get("company") or row.get("article_title"), 80)
        detail = clean_text(" / ".join(part for part in [row.get("brand"), row.get("product_name"), row.get("event_group")] if part), 100)
        source = clean_text(row.get("source_domain"), 40)
        return f"- {row.get('article_date') or 'undated'} | {title} | {detail} | score {row.get('confidence_score')} | {source}"

    lines = [
        "# Briefing Update Candidate Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Executive Read",
        "",
        f"- Scanned briefing files: {len(scanned_files)}.",
        f"- Candidate rows: {len(rows)}; newly discovered this run: {new_rows}.",
        f"- Need official verification: {len(official)}.",
        f"- Need full-text rescue: {len(rescue)}.",
        f"- Low-confidence review rows: {len(low_conf)}.",
        f"- P0/P1 product-gap overlaps: {len(p0_p1)}.",
        "",
        "## Event Mix",
        "",
    ]
    for key, value in count_by(rows, "event_group").items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Body Quality", ""])
    for key, value in count_by(rows, "body_quality").items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## P0/P1 Review Leads", ""])
    lines.extend([bullet(row) for row in p0_p1[:20]] or ["- None."])
    lines.extend(["", "## Full-Text Rescue Queue", ""])
    lines.extend([bullet(row) for row in rescue[:20]] or ["- None."])
    lines.extend(["", "## Latest Candidates", ""])
    lines.extend([bullet(row) for row in rows[:30]] or ["- None."])
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Unified candidates: `{BRIEFING_UPDATE_PATH}`",
            f"- Regulatory compatibility candidates: `{OUTPUT_PATH}`",
            f"- Sync state: `{SYNC_STATE_PATH}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_state(payload: dict[str, object]) -> None:
    SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Sync briefing HTML regulatory news into a structured candidate table.")
    parser.add_argument("--briefing-output", type=Path, default=DEFAULT_BRIEFING_OUTPUT)
    parser.add_argument("--days", type=int, default=8)
    parser.add_argument("--limit-files", type=int, default=260)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--update-output", type=Path, default=BRIEFING_UPDATE_PATH)
    parser.add_argument("--summary-output", type=Path, default=SUMMARY_PATH)
    args = parser.parse_args()

    scanned_files = briefing_files(args.briefing_output, days=args.days)[: args.limit_files]
    update_scan_rows = scan_update_candidates(args.briefing_output, days=args.days, limit_files=args.limit_files)
    update_rows, update_new_rows = merge_candidate_rows(read_rows(args.update_output, UPDATE_FIELDS), update_scan_rows)
    write_update_rows(update_rows, args.update_output)
    write_summary(update_rows, update_new_rows, scanned_files, args.summary_output)

    rows = scan(args.briefing_output, args.limit_files, days=args.days)
    existing_rows = read_rows(args.output, FIELDS)
    regulatory_new_rows = sum(1 for row in rows if row.get("candidate_id") not in existing_rows)
    merged_rows = {
        candidate_id: row
        for candidate_id, row in existing_rows.items()
        if row.get("status") not in {"candidate_unverified", ""}
    }
    for row in rows:
        previous = existing_rows.get(row["candidate_id"], {})
        if previous.get("status") not in {"", "candidate_unverified", None}:
            merged_rows[row["candidate_id"]] = {**row, **previous}
        else:
            merged_rows[row["candidate_id"]] = row
    output_rows = sorted(merged_rows.values(), key=lambda row: (row.get("article_date", ""), row.get("company", ""), row.get("brand", "")), reverse=True)
    write_rows(output_rows, args.output)
    write_state(
        {
            "last_run_at": now_iso(),
            "briefing_output": str(args.briefing_output),
            "scan_days": args.days,
            "limit_files": args.limit_files,
            "scanned_files": [
                {
                    "path": str(path),
                    "report_date": report_date(path),
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime, timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
                }
                for path in scanned_files
            ],
            "briefing_update_candidates": len(update_rows),
            "new_briefing_update_candidates": update_new_rows,
            "news_regulatory_event_candidates": len(output_rows),
            "new_news_regulatory_event_candidates": regulatory_new_rows,
            "summary_path": str(args.summary_output),
        }
    )
    regulators = {}
    for row in output_rows:
        regulators[row.get("regulator") or "Unknown"] = regulators.get(row.get("regulator") or "Unknown", 0) + 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "update_output": str(args.update_output),
                "summary_output": str(args.summary_output),
                "scanned_files": len(scanned_files),
                "update_rows": len(update_rows),
                "update_new_rows": update_new_rows,
                "rows": len(output_rows),
                "scanned_rows": len(rows),
                "candidate_new_rows": regulatory_new_rows,
                "regulators": regulators,
                "restylane_contour": sum(1 for row in output_rows if "restylane contour" in row.get("brand", "").lower()),
                "radiesse": sum(1 for row in output_rows if "radiesse" in row.get("brand", "").lower()),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

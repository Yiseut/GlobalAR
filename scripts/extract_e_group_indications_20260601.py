#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

OPT_QUEUE = AUDIT_DIR / "product_gap_optimization_queue_latest.csv"
PRODUCT_MASTER = DATA_DIR / "product_master.csv"
MANUAL_FACT = DATA_DIR / "manual_product_fact_evidence.csv"
PRODUCT_SPEC = DATA_DIR / "product_specification_evidence.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"
OFFICIAL_INDICATION = DATA_DIR / "official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_indication_extraction_summary_latest.json"
CANDIDATES_CSV = AUDIT_DIR / "e_group_indication_extraction_candidates_latest.csv"
UNCERTAIN_CSV = AUDIT_DIR / "e_group_indication_extraction_uncertain_latest.csv"
HTML_REPORT = AUDIT_DIR / "e_group_indication_extraction_review_latest.html"


INDICATION_FIELDS = [
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "jurisdiction",
    "regulator",
    "regulatory_pathway",
    "status",
    "registration_no",
    "approval_date",
    "expiry_date",
    "registered_name",
    "approved_indication",
    "intended_use",
    "legal_manufacturer",
    "local_holder",
    "source_key",
    "source_url",
    "source_type",
    "evidence_title",
    "evidence_excerpt",
    "official_description_exact",
    "official_description_source_field",
    "field_note",
    "checked_at",
    "reviewed_by",
    "review_status",
    "confidence",
]

FACT_SOURCE_TYPES = {
    "official_product_document": 35,
    "official_ifu_catalog": 35,
    "official_product_page": 28,
    "official_brand_page": 20,
    "official_specification_candidate": 16,
}

GENERIC_TOKENS = {
    "with",
    "plus",
    "deep",
    "line",
    "body",
    "skin",
    "hair",
    "filler",
    "fillers",
    "laser",
    "device",
    "medical",
    "aesthetic",
    "aesthetics",
    "thread",
    "threads",
    "face",
    "facial",
    "system",
    "platform",
    "series",
    "treatment",
    "treatments",
    "professional",
}

BLOCKED_DOMAINS = {
    "fillermarket.com",
    "medicalexpo.com",
    "pdf.medicalexpo.com",
    "aiqixie.com",
    "sigma-stat.com",
    "mitoconbiomed.in",
    "beyondmedicalaesthetics.uk",
    "azum.ua",
    "nordicms.com",
    "alliedmedica.com",
    "konepharma.co.kr",
    "cosmo-korea.com",
    "mp.weixin.qq.com",
    "homemedicallaser.com",
}

BAD_TEXT_FRAGMENTS = [
    "candidate link can be promoted",
    "registration facts still require",
    "exact certificates still require",
    "candidate/regulatory-status evidence only",
    "official page matched to a product family",
    "use for commercial product facts/specs",
    "do not present this row as a confirmed approved indication",
    "not regulatory approval",
]

GENERIC_OR_WEAK_FRAGMENTS = [
    "all products at www.",
    "not intended to treat or diagnose",
    "please consult the user manual for detailed information on indications",
    "in its intended use scenario",
    "likely risk associated with the use of the device in line with its intended use",
    "approved for publishing by the world intellectual property organization",
    "wide range of conditions",
    "more than 100 indications",
    "more than 10 medical specialties",
    "range of indications",
    "new indications",
    "multiple indications",
    "indications and important safety information",
    "indications and contraindications",
    "indications, enabling",
    "indications safely and efficiently",
    "indications faster treatments",
    "indications in more than",
    "medical indications across",
    "wide range of skin types",
    "the followingprivacy policy",
    "there has been increased interest",
    "product application, featuring",
    "built for beauty and designed to perform",
    "cleared for your safety",
    "preparation and administration",
    "官网将",
    "定位为",
]

WRONG_PATH_FRAGMENTS = [
    "ophthalmic anterior and posterior segment surgery",
    "intraocular",
    "bony defect",
    "orthopedic",
    "orthopaedic",
    "laparoscopic",
    "urologic",
    "lancing device",
    "stress urinary incontinence",
]

KEYWORD_RE = re.compile(
    r"indicat|intended|approved for|cleared for|for use in|for the correction|"
    r"for the treatment|used for|used to|designed to|treatment of|correction of|"
    r"improve the appearance|augmentation|用于|适用于|适应症|用途|治疗|改善|纠正|矫正|填充|"
    r"塑形|紧致|提升|脱毛|嫩肤|修复|皱纹|法令纹|容量",
    re.I,
)

EXPLICIT_RE = re.compile(
    r"\b(indications? for use|indications?|indicated for|is indicated|are indicated|"
    r"intended use|intended purpose|product and intended use|product application|"
    r"intended for|is intended|are intended|approved for|fda cleared for|cleared for|"
    r"for use in|for the correction|for the treatment of|medical indications?)\b|"
    r"适应症|适用于|用于",
    re.I,
)

AUTO_EXACT_RE = re.compile(
    r"\b(indications? for use\s*:|indicated for|is indicated|are indicated|"
    r"intended use\s*:|intended purpose\s*:|product and intended use|product application|"
    r"intended to be used|is intended to be used|are intended to be used|"
    r"fda cleared for|cleared for|approved for|indicated to treat|"
    r"intended for permanent reduction|medical indication\s*:|aesthetic indication\s*:|"
    r"the device is .* intended|device is indicated|device .* intended for)\b|"
    r"适应症|适用于|用于",
    re.I,
)

LABEL_RE = re.compile(
    r"\b(Indications? for Use|Indications?|Intended Use|Intended Purpose|"
    r"PRODUCT AND INTENDED USE|Product Application|Medical Indications?)\b\s*:?",
    re.I,
)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def stable_id(prefix: str, *parts: Any) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def url_domain(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def domain_blocked(domain: str) -> bool:
    return any(domain == item or domain.endswith(f".{item}") for item in BLOCKED_DOMAINS)


def normalize_text(text: str) -> str:
    text = clean(text).replace("[...]", " ")
    text = re.sub(r"#+", " ", text)
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    text = normalize_text(text)
    return [
        part.strip(" \t;:，,")
        for part in re.split(r"(?<=[.!?。！？])\s+|\s+[•·]\s+|\s+-\s+", text)
        if part.strip(" \t;:，,")
    ]


def clean_candidate_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"^(Home\s*/\s*)?Catalog\s*/\s*", "", text, flags=re.I)
    text = re.sub(r"\s+#{1,6}\s+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ;:，,")


def label_segments(text: str) -> list[str]:
    text = normalize_text(text)
    segments: list[str] = []
    for match in LABEL_RE.finditer(text):
        chunk = text[match.start() : match.start() + 720]
        cut_markers = [
            " Contraindication",
            " Composition",
            " Warnings",
            " Precautions",
            " How to use",
            " References",
            " ######",
        ]
        for marker in cut_markers:
            idx = chunk.find(marker)
            if idx > 80:
                chunk = chunk[:idx]
        segments.append(clean_candidate_text(chunk))
    return segments


def extract_indication_text(text: str) -> tuple[str, str]:
    if not text or "�" in text:
        return "", "empty_or_mojibake"
    low = text.casefold()
    if any(fragment in low for fragment in BAD_TEXT_FRAGMENTS):
        return "", "generic_candidate_note"

    labeled = [
        segment
        for segment in label_segments(text)
        if 30 <= len(segment) <= 720 and KEYWORD_RE.search(segment)
    ]
    if labeled:
        labeled.sort(key=lambda item: (1 if EXPLICIT_RE.search(item) else 0, len(item)), reverse=True)
        return labeled[0], "labeled_indication"

    scored: list[tuple[int, str]] = []
    for sentence in split_sentences(text):
        if not (25 <= len(sentence) <= 650):
            continue
        if not KEYWORD_RE.search(sentence):
            continue
        score = 0
        if EXPLICIT_RE.search(sentence):
            score += 50
        score += min(len(sentence), 260) // 10
        scored.append((score, clean_candidate_text(sentence)))
    if not scored:
        return "", "no_indication_phrase"
    scored.sort(reverse=True)
    return scored[0][1], "sentence_indication"


def tokens_from(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", clean(text).casefold())
        if len(token) >= 4 and token not in GENERIC_TOKENS
    }


def token_in_text(token: str, text: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text))


def has_target_match(product: dict[str, str], source_row: dict[str, str], extracted: str, brand_counts: Counter[tuple[str, str]]) -> bool:
    brand = clean(product.get("brand") or source_row.get("brand"))
    standard_name = clean(product.get("standard_product_name") or product.get("core_product"))
    text = " ".join(
        [
            clean(source_row.get("evidence_title")),
            clean(source_row.get("source_url")),
            clean(source_row.get("field_value")),
            extracted,
        ]
    ).casefold()
    product_tokens = tokens_from(standard_name)
    brand_tokens = tokens_from(brand)
    if any(token_in_text(token, text) for token in product_tokens):
        return True
    if any(token_in_text(token, text) for token in brand_tokens):
        return brand_counts[(clean(product.get("company")), brand)] <= 1 or not product_tokens
    return False


def conflict_brand_reason(
    product: dict[str, str],
    extracted: str,
    company_brand_tokens: dict[str, dict[str, set[str]]],
    global_brand_tokens: dict[str, set[str]],
) -> str:
    company = clean(product.get("company"))
    own_brand = clean(product.get("brand"))
    own_tokens = tokens_from(own_brand)
    text = extracted.casefold()
    for other_brand, other_tokens in company_brand_tokens.get(company, {}).items():
        if other_brand == own_brand:
            continue
        if not other_tokens:
            continue
        if any(token_in_text(token, text) for token in other_tokens) and not any(token_in_text(token, text) for token in own_tokens):
            return f"candidate_text_mentions_other_brand:{other_brand}"
    for other_brand, other_tokens in global_brand_tokens.items():
        if other_brand == own_brand:
            continue
        if not other_tokens:
            continue
        if any(token_in_text(token, text) for token in other_tokens) and not any(token_in_text(token, text) for token in own_tokens):
            return f"candidate_text_mentions_other_brand:{other_brand}"
    return ""


def auto_rejection_reason(
    product: dict[str, str],
    source_row: dict[str, str],
    extracted: str,
    extraction_reason: str,
    brand_counts: Counter[tuple[str, str]],
    company_brand_tokens: dict[str, dict[str, set[str]]],
    global_brand_tokens: dict[str, set[str]],
) -> str:
    low = extracted.casefold()
    if any(fragment in low for fragment in GENERIC_OR_WEAK_FRAGMENTS):
        return "generic_or_negative_intended_use_text"
    if "product application" in low and not re.search(r"intended|indicated|用于|适用于", low):
        return "generic_or_negative_intended_use_text"
    if any(fragment in low for fragment in WRONG_PATH_FRAGMENTS):
        return "possible_wrong_clinical_path"
    if re.search(r"(is indicated for|indicated for|is intended for|intended for)\s*$", low):
        return "incomplete_indication_text"
    if re.search(r"(indicated for improving the appearance of|is indicated for improving the appearance of)\s*$", low):
        return "incomplete_indication_text"
    domain = url_domain(clean(source_row.get("source_url")))
    if domain_blocked(domain):
        return f"blocked_or_nonofficial_domain:{domain}"
    conflict = conflict_brand_reason(product, extracted, company_brand_tokens, global_brand_tokens)
    if conflict:
        return conflict
    if not AUTO_EXACT_RE.search(extracted):
        return "not_explicit_enough"
    if not has_target_match(product, source_row, extracted, brand_counts):
        return "product_target_not_explicit"
    if extraction_reason == "sentence_indication" and len(extracted) > 560:
        return "long_sentence_needs_human_cut"
    return ""


def score_candidate(source_type: str, extracted: str, extraction_reason: str, target_match: bool) -> float:
    score = FACT_SOURCE_TYPES.get(source_type, 0)
    if extraction_reason == "labeled_indication":
        score += 35
    if AUTO_EXACT_RE.search(extracted):
        score += 25
    if target_match:
        score += 20
    score += min(len(extracted), 260) / 20
    return round(score, 2)


def make_manual_row(product: dict[str, str], source_row: dict[str, str], extracted: str, checked_at: str) -> dict[str, str]:
    product_id = clean(product.get("product_id"))
    source_url = clean(source_row.get("source_url"))
    source_type = clean(source_row.get("source_type")) or "official_product_source"
    return {
        "product_id": product_id,
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": "Global",
        "regulator": "Official product/IFU/source text",
        "regulatory_pathway": "official indication/use extraction from existing evidence",
        "status": "Official use/indication wording extracted from existing source evidence",
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": clean(product.get("registered_name") or product.get("standard_product_name") or product.get("brand")),
        "approved_indication": "",
        "intended_use": extracted,
        "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("manufactured_by") or product.get("company")),
        "local_holder": clean(product.get("local_holder")),
        "source_key": stable_id("egroup_ind", product_id, source_url, extracted),
        "source_url": source_url,
        "source_type": f"auto_extracted_{source_type}",
        "evidence_title": clean(source_row.get("evidence_title")),
        "evidence_excerpt": clean(source_row.get("evidence_excerpt"))[:1200],
        "official_description_exact": extracted,
        "official_description_source_field": "existing_official_product_evidence_excerpt",
        "field_note": (
            "Auto-extracted from existing official product/IFU/source evidence for E-group indication backfill. "
            "Treat as official product-use wording, not regulator-approved indication unless the source itself is a regulator or IFU."
        ),
        "checked_at": checked_at,
        "reviewed_by": "auto_e_group_indication_extractor_20260601",
        "review_status": "auto_extracted_official_indication",
        "confidence": "high_confidence_existing_official_source_text",
    }


def html_table(rows: list[dict[str, Any]], limit: int = 80) -> str:
    headers = ["status", "company", "brand", "reason", "source_type", "source_url", "extracted_text"]
    body = []
    for row in rows[:limit]:
        cells = []
        for header in headers:
            value = clean(row.get(header))
            if header == "source_url" and value:
                value = f'<a href="{html.escape(value)}">{html.escape(url_domain(value) or value[:80])}</a>'
            else:
                value = html.escape(value[:800])
            cells.append(f"<td>{value}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(h)}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def write_html_report(summary: dict[str, Any], promoted: list[dict[str, Any]], uncertain: list[dict[str, Any]]) -> None:
    css = """
    body{font-family:Arial,'Microsoft YaHei',sans-serif;background:#faf8f4;color:#25221f;margin:0;padding:28px}
    h1{font-size:26px;margin:0 0 8px} h2{margin-top:28px}
    .cards{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin:20px 0}
    .card{background:#fff;border:1px solid #eaded4;border-radius:8px;padding:14px}
    .num{font-size:28px;font-weight:700;color:#c45f3d}
    table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #eaded4}
    th,td{border-bottom:1px solid #f0e7df;padding:9px 10px;text-align:left;vertical-align:top;font-size:13px}
    th{background:#f7eee7}
    a{color:#0d6b61}
    .note{color:#7a6d63;line-height:1.6}
    """
    cards = "".join(
        f"<div class='card'><div class='num'>{html.escape(str(value))}</div><div>{html.escape(label)}</div></div>"
        for label, value in [
            ("E 组产品", summary["e_group_products"]),
            ("自动落库", summary["auto_promoted_products"]),
            ("不确定/需人工看", summary["uncertain_products"]),
            ("没有抽到原文", summary["no_extract_products"]),
        ]
    )
    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>E组适应症抽取复核</title><style>{css}</style></head>
<body>
<h1>E 组官方用途/适应症抽取复核</h1>
<p class="note">本页只基于现有证据表抽取；无法明确判断、产品指向冲突、非官方/分销域名或只有泛泛宣传语的内容，没有写入主库。</p>
<div class="cards">{cards}</div>
<h2>自动落库样例</h2>
{html_table(promoted, 50)}
<h2>不确定 / 未落库样例</h2>
{html_table(uncertain, 120)}
</body></html>"""
    HTML_REPORT.write_text(doc, encoding="utf-8")


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, queue_rows = read_csv(OPT_QUEUE)
    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, official_indication_rows = read_csv(OFFICIAL_INDICATION)
    _, fact_rows = read_csv(MANUAL_FACT)
    _, spec_rows = read_csv(PRODUCT_SPEC)

    product_by_id = {clean(row.get("product_id")): row for row in product_rows if clean(row.get("product_id"))}
    e_rows = [row for row in queue_rows if clean(row.get("optimization_group")) == "E_indication_backfill"]
    e_product_ids = {clean(row.get("product_id")) for row in e_rows if clean(row.get("product_id"))}
    existing_indication_product_ids = {
        clean(row.get("product_id"))
        for row in official_indication_rows
        if clean(row.get("product_id")) and clean(row.get("official_description_exact") or row.get("indication"))
    }
    existing_manual_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact") or row.get("intended_use") or row.get("approved_indication")),
        )
        for row in manual_rows
    }

    brand_counts = Counter((clean(row.get("company")), clean(row.get("brand"))) for row in product_rows if clean(row.get("brand")))
    company_brand_tokens: dict[str, dict[str, set[str]]] = defaultdict(dict)
    global_brand_tokens: dict[str, set[str]] = {}
    for row in product_rows:
        company = clean(row.get("company"))
        brand = clean(row.get("brand"))
        if company and brand:
            tokens = tokens_from(brand)
            company_brand_tokens[company][brand] = tokens
            if tokens:
                global_brand_tokens[brand] = tokens

    fact_candidates: list[dict[str, Any]] = []
    for row in fact_rows:
        product_id = clean(row.get("product_id"))
        if product_id not in e_product_ids or product_id in existing_indication_product_ids:
            continue
        source_type = clean(row.get("source_type"))
        if source_type not in FACT_SOURCE_TYPES:
            continue
        extracted, extraction_reason = extract_indication_text(clean(row.get("evidence_excerpt")))
        product = product_by_id.get(product_id, {})
        status = "candidate_found" if extracted else "no_extract"
        reason = extraction_reason
        target_match = False
        auto_block = ""
        score = 0.0
        if extracted and product:
            target_match = has_target_match(product, row, extracted, brand_counts)
            auto_block = auto_rejection_reason(
                product,
                row,
                extracted,
                extraction_reason,
                brand_counts,
                company_brand_tokens,
                global_brand_tokens,
            )
            score = score_candidate(source_type, extracted, extraction_reason, target_match)
            if auto_block:
                status = "needs_review"
                reason = auto_block
            else:
                status = "auto_promote"
                reason = extraction_reason
        fact_candidates.append(
            {
                "product_id": product_id,
                "seed_record_id": clean(product.get("seed_record_id") or row.get("seed_record_id")),
                "company": clean(product.get("company") or row.get("company")),
                "brand": clean(product.get("brand") or row.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "track": clean(product.get("commercial_path_l1")),
                "form": clean(product.get("commercial_path_l2")),
                "status": status,
                "reason": reason,
                "score": score,
                "target_match": "yes" if target_match else "no",
                "source_type": source_type,
                "source_url": clean(row.get("source_url")),
                "evidence_title": clean(row.get("evidence_title")),
                "extracted_text": extracted,
                "source_evidence_excerpt": clean(row.get("evidence_excerpt"))[:1200],
                "_source_row": row,
            }
        )

    best_by_product: dict[str, dict[str, Any]] = {}
    for candidate in fact_candidates:
        if candidate["status"] == "no_extract":
            continue
        product_id = candidate["product_id"]
        current = best_by_product.get(product_id)
        if current is None or float(candidate["score"]) > float(current["score"]):
            best_by_product[product_id] = candidate

    promoted_candidates = [
        candidate
        for candidate in best_by_product.values()
        if candidate["status"] == "auto_promote" and clean(candidate.get("extracted_text"))
    ]

    new_manual_rows: list[dict[str, str]] = []
    for candidate in promoted_candidates:
        product = product_by_id.get(candidate["product_id"], {})
        manual_row = make_manual_row(product, candidate["_source_row"], clean(candidate["extracted_text"]), checked_at)
        key = (
            clean(manual_row.get("product_id")),
            clean(manual_row.get("source_url")),
            clean(manual_row.get("official_description_exact")),
        )
        if key in existing_manual_keys:
            continue
        existing_manual_keys.add(key)
        new_manual_rows.append(manual_row)

    if new_manual_rows:
        backup = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_e_group_extract_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup)
        out_fields = manual_fields or INDICATION_FIELDS
        write_csv(MANUAL_INDICATION, out_fields, [*manual_rows, *new_manual_rows])
    else:
        backup = None

    promoted_product_ids = {row["product_id"] for row in promoted_candidates}
    uncertain: list[dict[str, Any]] = []
    candidate_rows_out: list[dict[str, Any]] = []
    for candidate in best_by_product.values():
        output = {k: v for k, v in candidate.items() if not k.startswith("_")}
        if candidate["product_id"] in promoted_product_ids:
            output["status"] = "auto_promoted"
            candidate_rows_out.append(output)
        else:
            uncertain.append(output)
            candidate_rows_out.append(output)

    no_candidate_product_ids = e_product_ids - set(best_by_product) - existing_indication_product_ids
    spec_count_by_product = Counter(clean(row.get("product_id")) for row in spec_rows if clean(row.get("product_id")) in no_candidate_product_ids)
    fact_count_by_product = Counter(clean(row.get("product_id")) for row in fact_rows if clean(row.get("product_id")) in no_candidate_product_ids)
    for product_id in sorted(no_candidate_product_ids):
        product = product_by_id.get(product_id, {})
        uncertain.append(
            {
                "product_id": product_id,
                "seed_record_id": clean(product.get("seed_record_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "track": clean(product.get("commercial_path_l1")),
                "form": clean(product.get("commercial_path_l2")),
                "status": "no_extract",
                "reason": "no_clear_official_indication_phrase_in_existing_manual_evidence",
                "score": "",
                "target_match": "",
                "source_type": "",
                "source_url": "",
                "evidence_title": "",
                "extracted_text": "",
                "source_evidence_excerpt": f"manual_fact_rows={fact_count_by_product.get(product_id, 0)}; spec_rows={spec_count_by_product.get(product_id, 0)}",
            }
        )

    output_fields = [
        "status",
        "reason",
        "score",
        "target_match",
        "product_id",
        "seed_record_id",
        "company",
        "brand",
        "standard_product_name",
        "track",
        "form",
        "source_type",
        "source_url",
        "evidence_title",
        "extracted_text",
        "source_evidence_excerpt",
    ]
    write_csv(CANDIDATES_CSV, output_fields, sorted(candidate_rows_out, key=lambda row: (row["status"], row["company"], row["brand"])))
    write_csv(UNCERTAIN_CSV, output_fields, sorted(uncertain, key=lambda row: (row["status"], row["company"], row["brand"])))

    summary = {
        "checked_at": checked_at,
        "e_group_products": len(e_product_ids),
        "already_had_indication_products": len(existing_indication_product_ids & e_product_ids),
        "candidate_rows_scanned": len(fact_candidates),
        "candidate_products_with_extract": len(best_by_product),
        "auto_promoted_products": len(promoted_product_ids),
        "new_manual_indication_rows_added": len(new_manual_rows),
        "uncertain_products": len({row["product_id"] for row in uncertain if row.get("product_id")}),
        "no_extract_products": sum(1 for row in uncertain if row.get("status") == "no_extract"),
        "by_status": dict(Counter(row.get("status") for row in [*candidate_rows_out, *uncertain])),
        "uncertain_reason_top": dict(Counter(row.get("reason") for row in uncertain).most_common(20)),
        "auto_by_track": dict(Counter(row.get("track") for row in candidate_rows_out if row.get("status") == "auto_promoted")),
        "manual_indication_backup": str(backup) if backup else "",
        "outputs": {
            "candidates_csv": str(CANDIDATES_CSV),
            "uncertain_csv": str(UNCERTAIN_CSV),
            "html_report": str(HTML_REPORT),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_html_report(
        summary,
        [row for row in candidate_rows_out if row.get("status") == "auto_promoted"],
        uncertain,
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

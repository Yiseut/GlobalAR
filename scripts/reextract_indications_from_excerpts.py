"""
Re-extract indication CANDIDATES from manual_product_fact_evidence.evidence_excerpt
for products that have NO official_indication_evidence row yet.

This does NOT touch the production indication evidence pool (which is rebuilt
from CSV by build_data.py). Instead it writes a triage CSV + a summary report
so the candidates can be reviewed and later promoted via the verification queue
or the MDR/CE triage page.

Conservative rules:
- Skip product_ids that already have any official_indication_evidence row.
- Limit to one best candidate per product.
- Only sentences 30..400 chars, containing one of the keywords list.
- Source URL must be present.
- Mojibake-flagged rows (U+FFFD) skipped.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "global_aesthetics.db"
OUT_DIR = ROOT / "data" / "audits"
OUT_CSV = OUT_DIR / "indication_candidates_derived_latest.csv"
OUT_MD = OUT_DIR / "indication_candidates_derived_latest.md"

KEYWORDS = [
    "indicated for",
    "is indicated",
    "are indicated",
    "for the treatment of",
    "intended use",
    "for use in",
    "for the temporary improvement",
    "for the correction",
    "for the augmentation",
    "is intended to",
]

TRACK_ALLOWLIST = {"Injectables", "Implants", "Regenerative", "EBD", "Skincare"}

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def is_mojibake(text: str) -> bool:
    return "�" in text


def pick_sentence(excerpt: str) -> str | None:
    if not excerpt or is_mojibake(excerpt):
        return None
    text = excerpt.replace("\n", " ").replace("[...]", " ")
    text = re.sub(r"\s+", " ", text).strip()
    # Find first sentence containing a keyword
    for sent in SENT_SPLIT.split(text):
        sent = sent.strip(" \t　")
        if 30 <= len(sent) <= 400:
            low = sent.lower()
            if any(k in low for k in KEYWORDS):
                return sent
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10**6)
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # Products that already have indication evidence — skip
    existing = {
        r[0]
        for r in cur.execute(
            "select distinct product_id from official_indication_evidence where product_id is not null"
        )
    }
    print(f"Products with existing indication evidence: {len(existing)}")

    # Build query for candidate excerpts in allowed tracks
    sql = """
    select mpf.product_id, mpf.company_id, mpf.company, mpf.brand,
           pm.standard_product_name as product_name, mpf.source_url, mpf.source_type,
           mpf.evidence_excerpt, cm.primary_track
    from manual_product_fact_evidence mpf
    join product_master pm on pm.product_id = mpf.product_id
    join company_master cm on cm.company_id = pm.company_id
    where cm.primary_track in ({})
      and mpf.evidence_excerpt is not null
      and mpf.evidence_excerpt != ''
      and length(mpf.evidence_excerpt) > 30
    """.format(",".join("?" * len(TRACK_ALLOWLIST)))

    rows = cur.execute(sql, tuple(TRACK_ALLOWLIST)).fetchall()
    print(f"Candidate excerpts in allowed tracks: {len(rows)}")

    # Group by product_id, pick best sentence per product
    by_product: dict[str, dict] = {}
    for row in rows:
        product_id, company_id, company, brand, product_name, src_url, src_type, excerpt, track = row
        if not product_id or product_id in existing:
            continue
        sent = pick_sentence(excerpt)
        if not sent:
            continue
        # Prefer rows with source_url
        if not src_url:
            continue
        cur_best = by_product.get(product_id)
        # Keep the longest informative sentence as best
        if not cur_best or len(sent) > len(cur_best["indication"]):
            by_product[product_id] = {
                "product_id": product_id,
                "company_id": company_id,
                "company": company,
                "brand": brand,
                "product": product_name,
                "indication": sent,
                "source_url": src_url,
                "source_type": src_type or "derived_company_excerpt",
                "track": track,
            }

    new_rows = list(by_product.values())[: args.limit]
    print(f"New indication candidates to insert: {len(new_rows)}")
    by_track: dict[str, int] = {}
    for r in new_rows:
        by_track[r["track"]] = by_track.get(r["track"], 0) + 1
    print("  by track:", by_track)

    if args.dry_run:
        print("\n--- Sample 5 ---")
        for r in new_rows[:5]:
            print(f"  {r['track']} / {r['company']} / {r['brand']}: {r['indication'][:160]}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "product_id", "company_id", "company", "brand", "product",
        "track", "indication", "source_url", "source_type",
        "candidate_status",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in new_rows:
            writer.writerow({
                "product_id": r["product_id"],
                "company_id": r["company_id"],
                "company": r["company"],
                "brand": r["brand"],
                "product": r["product"],
                "track": r["track"],
                "indication": r["indication"],
                "source_url": r["source_url"],
                "source_type": r["source_type"],
                "candidate_status": "pending_review",
            })

    ts = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    lines = [
        "# 适应症候选派生报告（来自已抓取 evidence_excerpt）",
        "",
        f"- 生成时间：{ts}",
        f"- 输入：manual_product_fact_evidence.evidence_excerpt（{len(rows)} 行 in 5 allowlist tracks）",
        f"- 输出：{OUT_CSV.name} · {len(new_rows)} 行候选 · 每个产品 1 条",
        f"- 排除：已经在 official_indication_evidence 里的 {len(existing)} 个产品",
        "- 规则：keyword 命中 (indicated for / for the treatment of / intended use / 等) · 30..400 字符 · 有 source_url · 不含 U+FFFD",
        "- **状态**：候选，pending_review；未写入 official_indication_evidence",
        "",
        "## 按赛道分布",
        "",
        "| Track | 当前 official_indication | 候选 +/产品 | 合并后预计 |",
        "|---|---:|---:|---:|",
    ]
    # Per-track existing counts
    existing_by_track = {}
    for r in cur.execute("""
        select cm.primary_track, count(distinct oie.product_id)
          from official_indication_evidence oie
          join product_master pm on pm.product_id = oie.product_id
          join company_master cm on cm.company_id = pm.company_id
          group by cm.primary_track
    """):
        existing_by_track[r[0]] = r[1]
    for track in sorted(by_track, key=lambda k: -by_track[k]):
        exi = existing_by_track.get(track, 0)
        new_n = by_track[track]
        lines.append(f"| {track} | {exi} | +{new_n} | {exi + new_n} |")
    lines.append("")
    lines.append("## 样例 (前 10 条)")
    lines.append("")
    for r in new_rows[:10]:
        snippet = r["indication"][:180].replace("|", "\\|")
        lines.append(f"- **{r['track']} · {r['company']} · {r['brand']}** — {snippet}")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT_CSV} ({len(new_rows)} rows)")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()

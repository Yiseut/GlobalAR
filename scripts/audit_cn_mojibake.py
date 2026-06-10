"""
CN-mojibake audit · 2-layer detection.

Layer 1: existing marker chars (same as build_data.MOJIBAKE_MARKERS).
Layer 2: U+FFFD replacement char (��) — direct evidence of failed decode.

Scans:
- company_master.canonical_name / aliases / positioning_cn / parent_company / ultimate_parent
- product_master.brand_or_family / claim_text / verified_differentiator / feature_tags
- official_indication_evidence.indication / official_description_exact
- registration_evidence.approved_indication / evidence_excerpt
- mdr_ce_evidence_candidates.title / evidence_excerpt

Writes data/audits/cn_mojibake_audit_latest.md.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "global_aesthetics.db"
OUT_DIR = ROOT / "data" / "audits"
OUT_LATEST = OUT_DIR / "cn_mojibake_audit_latest.md"

MOJIBAKE_MARKERS = {"镞", "庠", "剌", "鐨", "涓", "妯", "傛", "鍏", "鏃", "缇"}
REPLACEMENT_CHAR = "�"

CJK_RE = re.compile(r"[一-鿿]")


def layer1_markers(text: str) -> list[str]:
    return sorted({m for m in MOJIBAKE_MARKERS if m in text})


def layer2_replacement(text: str) -> bool:
    return REPLACEMENT_CHAR in text


def has_signal(text: str) -> tuple[bool, list[str], bool]:
    if not text:
        return False, [], False
    markers = layer1_markers(text)
    repl = layer2_replacement(text)
    return (len(markers) >= 2 or repl, markers, repl)


def scan_table(
    cur: sqlite3.Cursor,
    table: str,
    columns: list[str],
    label_cols: list[str],
) -> list[dict]:
    out: list[dict] = []
    cols_sql = ", ".join(label_cols + columns)
    rows = cur.execute(f"select {cols_sql} from {table}").fetchall()
    for row in rows:
        labels = row[: len(label_cols)]
        for i, col in enumerate(columns):
            text = row[len(label_cols) + i]
            if not isinstance(text, str):
                continue
            hit, markers, repl = has_signal(text)
            if not hit:
                continue
            reasons = []
            if len(markers) >= 2:
                reasons.append(f"L1 markers: {','.join(markers)}")
            if repl:
                reasons.append("L2 U+FFFD")
            excerpt = text.strip().replace("\n", " ")[:120]
            out.append(
                {
                    "table": table,
                    "column": col,
                    "labels": dict(zip(label_cols, labels)),
                    "reason": " · ".join(reasons),
                    "excerpt": excerpt,
                }
            )
    return out


def main() -> None:
    con = sqlite3.connect(DB)
    cur = con.cursor()
    findings: list[dict] = []

    findings += scan_table(
        cur,
        "company_master",
        ["canonical_name", "aliases", "positioning_cn", "parent_company", "ultimate_parent"],
        ["company_id"],
    )
    findings += scan_table(
        cur,
        "product_master",
        ["claim_text", "verified_differentiator", "feature_tags", "registered_name"],
        ["product_id", "company"],
    )
    findings += scan_table(
        cur,
        "official_indication_evidence",
        ["indication", "official_description_exact"],
        ["id", "company", "product"],
    )
    findings += scan_table(
        cur,
        "registration_evidence",
        ["approved_indication", "evidence_excerpt", "registered_name"],
        ["id", "company", "brand"],
    )
    findings += scan_table(
        cur,
        "mdr_ce_evidence_candidates",
        ["title", "evidence_excerpt"],
        ["evidence_id", "company", "brand"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    lines = [
        "# CN 编码疑似乱码审计",
        "",
        f"- 生成时间：{ts}",
        f"- 规则：L1 marker 字符 (>=2) · L2 U+FFFD 替换字符 (��)",
        f"- 疑似行数：{len(findings)}",
        "",
        "| Table | Column | Labels | Reason | Excerpt |",
        "|---|---|---|---|---|",
    ]
    for f in findings:
        label_str = " · ".join(f"{k}={v}" for k, v in f["labels"].items() if v)
        excerpt = f["excerpt"].replace("|", "\\|")
        lines.append(
            f"| {f['table']} | {f['column']} | {label_str} | {f['reason']} | {excerpt} |"
        )
    if not findings:
        lines.append("| — | — | — | — | — |")
        lines.append("")
        lines.append("当前规则未检出疑似乱码。")

    OUT_LATEST.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_LATEST} · findings={len(findings)}")


if __name__ == "__main__":
    main()

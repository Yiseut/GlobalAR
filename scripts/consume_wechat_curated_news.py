"""Consume the WeChat Plan-B push history as an implicit "user curated" signal.

Rationale (2026-06-04):
  The user's daily flow is: read briefing → tick items → push to WeChat.
  The push action ALREADY records the picks in
  `E:\\shared\\code\\briefing_v6\\data\\wechat_plan_b_history.jsonl` —
  each line carries `selected_hrefs[]` for that day.

  Treat each pushed href as a user-curated lead. Cross-reference against
  `briefing_update_candidates.csv` (produced by sync_briefing_news_events.py)
  and bump matching rows from `candidate_unverified` to `user_curated`. The
  nightly verification chain (continuous_verification) then prioritises
  these rows for source-fetch + writeback.

Inputs:
  - {briefing_v6}/data/wechat_plan_b_history.jsonl     (push history)
  - data/briefing_update_candidates.csv                 (candidate table)
  - data/wechat_curation_blocklist.txt   (optional; one URL per line —
    URLs here are NOT auto-marked curated)

Outputs:
  - data/briefing_update_candidates.csv                 (in-place status bump)
  - data/audits/wechat_curation_apply_latest.json
  - data/audits/wechat_curation_apply_latest.md
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"

DEFAULT_HISTORY = Path(r"E:\shared\code\briefing_v6\data\wechat_plan_b_history.jsonl")
CANDIDATES_PATH = DATA_DIR / "briefing_update_candidates.csv"
BLOCKLIST_PATH = DATA_DIR / "wechat_curation_blocklist.txt"
APPLY_JSON = AUDIT_DIR / "wechat_curation_apply_latest.json"
APPLY_MD = AUDIT_DIR / "wechat_curation_apply_latest.md"


def normalise_url(url: str) -> str:
    """Strip query / fragment / trailing slash for matching."""
    if not url:
        return ""
    url = url.strip()
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}{parts.path}".rstrip("/")
    return base.lower()


def load_blocklist() -> set[str]:
    if not BLOCKLIST_PATH.exists():
        return set()
    out: set[str] = set()
    for line in BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(normalise_url(line))
    return out


def load_curated_urls(history_path: Path) -> dict[str, dict]:
    """Return {normalised_url: {pushed_at, briefing_file}} from history JSONL."""
    if not history_path.exists():
        return {}
    out: dict[str, dict] = {}
    for line in history_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        pushed_at = d.get("pushed_at") or ""
        briefing_file = d.get("briefing_file") or ""
        urls: list[str] = []
        urls.extend(d.get("selected_hrefs") or [])
        headline = d.get("headline_href")
        if headline:
            urls.append(headline)
        for u in urls:
            nu = normalise_url(u)
            if not nu:
                continue
            # Keep the EARLIEST pushed_at if duplicate (first curation date)
            if nu not in out or pushed_at < out[nu]["pushed_at"]:
                out[nu] = {"pushed_at": pushed_at, "briefing_file": briefing_file}
    return out


def main(history_path: Path = DEFAULT_HISTORY) -> dict:
    curated = load_curated_urls(history_path)
    blocked = load_blocklist()
    curated_urls = set(curated.keys()) - blocked

    if not CANDIDATES_PATH.exists():
        raise SystemExit(f"candidate file missing: {CANDIDATES_PATH}")

    with CANDIDATES_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # Ensure required columns exist (additive, do not destroy existing data)
    for col in ("status", "user_curated_at", "curated_from_briefing"):
        if col not in fieldnames:
            fieldnames.append(col)

    bumped = 0
    bumped_event = Counter()
    bumped_examples: list[dict] = []
    by_status_before = Counter(r.get("status", "") for r in rows)
    for r in rows:
        u = normalise_url(r.get("article_url", ""))
        if not u or u not in curated_urls:
            continue
        meta = curated[u]
        prev_status = r.get("status", "")
        # Only promote from passive states; never demote terminal verdicts.
        if prev_status in ("candidate_unverified", ""):
            r["status"] = "user_curated"
            r["user_curated_at"] = meta["pushed_at"]
            r["curated_from_briefing"] = meta["briefing_file"]
            bumped += 1
            bumped_event[r.get("event_type", "")] += 1
            if len(bumped_examples) < 12:
                bumped_examples.append({
                    "article_date": r.get("article_date", ""),
                    "company": r.get("company", ""),
                    "brand": r.get("brand", ""),
                    "event_type": r.get("event_type", ""),
                    "confidence_score": r.get("confidence_score", ""),
                    "article_title": (r.get("article_title", "") or "")[:90],
                    "url": r.get("article_url", ""),
                })

    # Write back the CSV
    with CANDIDATES_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    by_status_after = Counter(r.get("status", "") for r in rows)

    report = {
        "ran_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "history_path": str(history_path),
        "curated_urls_total": len(curated),
        "blocked_urls": len(blocked),
        "candidate_rows_total": len(rows),
        "rows_promoted_to_user_curated": bumped,
        "promoted_by_event": dict(bumped_event),
        "status_before": dict(by_status_before),
        "status_after": dict(by_status_after),
        "examples": bumped_examples,
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    APPLY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# WeChat curated → verification queue",
        "",
        f"- Ran at: `{report['ran_at']}`",
        f"- History source: `{history_path.name}`",
        f"- Curated URLs in history: **{len(curated)}**  (blocked: {len(blocked)})",
        f"- Candidate rows total: {len(rows)}",
        f"- Newly promoted this run: **{bumped}**",
        "",
        "## Status counts",
        "",
        "| status | before | after |",
        "|---|---:|---:|",
    ]
    keys = sorted(set(by_status_before) | set(by_status_after))
    for k in keys:
        md_lines.append(f"| `{k or '(empty)'}` | {by_status_before.get(k, 0)} | {by_status_after.get(k, 0)} |")
    md_lines += ["", "## Promoted by event type", ""]
    for ev, n in bumped_event.most_common():
        md_lines.append(f"- `{ev}` — {n}")
    if bumped_examples:
        md_lines += ["", "## Examples (up to 12)", "", "| date | company / brand | event | score | title |", "|---|---|---|---:|---|"]
        for e in bumped_examples:
            md_lines.append(
                f"| {e['article_date']} | {e['company']} / {e['brand']} | {e['event_type']} | {e['confidence_score']} | {e['article_title']} |"
            )
    APPLY_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({
        "ran_at": report["ran_at"],
        "curated_urls": report["curated_urls_total"],
        "promoted": bumped,
        "status_after": report["status_after"],
        "report_md": str(APPLY_MD),
    }, ensure_ascii=False))
    return report


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Show the current verification run status.

This script reads the checkpoint/log files and prints a compact operational
status report. It does not mutate the database or workbook unless --write-md is
provided, in which case it only writes data/verification_status.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
STATE_PATH = DATA_DIR / "continuous_run_state.json"
LOG_PATH = DATA_DIR / "continuous_run_log.jsonl"
STATUS_MD_PATH = DATA_DIR / "verification_status.md"
MANIFEST_PATH = DATA_DIR / "import_manifest.json"
CURRENT_RUN_PATH = DATA_DIR / "current_verification_run.json"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"), strict=False)
    except json.JSONDecodeError:
        return {}


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad_rows = 0
    if not path.exists():
        return rows, bad_rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line, strict=False)
        except json.JSONDecodeError:
            bad_rows += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, bad_rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def now_local() -> datetime:
    return datetime.now().astimezone()


def process_rows() -> list[dict[str, Any]]:
    command = r"""
$rows = Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -like '*run_continuous_verification_batch.py*' -or
     $_.CommandLine -like '*start_quality_continuation.ps1*') -and
    ($_.CommandLine -notlike '*show_verification_status.py*')
  } |
  Select-Object ProcessId,Name,CreationDate,CommandLine
$rows | ConvertTo-Json -Depth 4 -Compress
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except Exception:
        return []
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def tracked_process(run_info: dict[str, Any]) -> dict[str, Any] | None:
    try:
        pid = int(run_info.get("pid") or 0)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    command = f"""
$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue
if ($p) {{
  [pscustomobject]@{{
    ProcessId=$p.Id
    Name=$p.ProcessName
    CreationDate=$p.StartTime.ToString('o')
  }} | ConvertTo-Json -Compress
}}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return None
    text = proc.stdout.strip()
    if not text:
        return None
    try:
        row = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(row, dict):
        return None
    row["CommandLine"] = run_info.get("command", "run_continuous_verification_batch.py")
    row["tracked_current_run"] = True
    return row


def arg_value(args: dict[str, Any], key: str, default: int) -> int:
    value = args.get(key.replace("-", "_"), args.get(key, default))
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def pending_counts() -> dict[str, Any]:
    official_plan = read_csv(DATA_DIR / "company_official_source_plan.csv")
    official_ev, official_bad = read_jsonl(DATA_DIR / "company_official_source_evidence.jsonl")
    official_plan_keys = {row.get("plan_id", "").strip() for row in official_plan if row.get("plan_id")}
    official_ev_plan_keys = {str(row.get("plan_id", "")).strip() for row in official_ev if row.get("plan_id")}
    official_ev_legacy_keys = {
        (str(row.get("company_id", "")).strip(), str(row.get("query_type", "")).strip())
        for row in official_ev
        if row.get("company_id") and row.get("query_type")
    }
    official_covered_keys = set()
    for row in official_plan:
        plan_id = row.get("plan_id", "").strip()
        legacy_key = (row.get("company_id", "").strip(), row.get("query_type", "").strip())
        if plan_id and (plan_id in official_ev_plan_keys or legacy_key in official_ev_legacy_keys):
            official_covered_keys.add(plan_id)

    mdr_plan = read_csv(DATA_DIR / "mdr_ce_search_plan.csv")
    mdr_ev, mdr_bad = read_jsonl(DATA_DIR / "mdr_ce_evidence_candidates.jsonl")
    mdr_plan_ids = {row.get("plan_id", "").strip() for row in mdr_plan if row.get("plan_id")}
    mdr_ev_ids = {str(row.get("plan_id", "")).strip() for row in mdr_ev if row.get("plan_id")}

    websites = read_csv(DATA_DIR / "official_website_master.csv")
    assets = read_csv(DATA_DIR / "company_media_asset_index.csv")
    website_ids = {row.get("website_id", "").strip() for row in websites if row.get("website_id")}
    processed_website_ids = {row.get("website_id", "").strip() for row in assets if row.get("website_id")}

    return {
        "official": {
            "total": len(official_plan_keys),
            "covered": len(official_covered_keys),
            "pending": len(official_plan_keys - official_covered_keys),
            "bad_jsonl": official_bad,
        },
        "mdr_ce": {
            "total": len(mdr_plan_ids),
            "covered": len(mdr_ev_ids),
            "pending": len(mdr_plan_ids - mdr_ev_ids),
            "bad_jsonl": mdr_bad,
        },
        "media": {
            "total": len(website_ids),
            "covered": len(processed_website_ids),
            "pending": len(website_ids - processed_website_ids),
            "bad_jsonl": 0,
        },
    }


def latest_batch_args(log_rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(log_rows):
        if row.get("event") in {"batch_started", "batch_finished", "continuous_started"}:
            args = row.get("args")
            if isinstance(args, dict):
                return args
    return {}


def continuous_batches(log_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches = []
    for row in log_rows:
        if row.get("event") != "batch_finished":
            continue
        if (row.get("run_context") or {}).get("mode") == "continuous":
            batches.append(row)
    return batches


def current_batch(log_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for index in range(len(log_rows) - 1, -1, -1):
        row = log_rows[index]
        if row.get("event") not in {"batch_started", "batch_finished"}:
            continue
        if row.get("event") == "batch_finished":
            return None
        batch_id = row.get("batch_id")
        later_finished = any(
            later.get("event") == "batch_finished" and later.get("batch_id") == batch_id
            for later in log_rows[index + 1 :]
        )
        return None if later_finished else row
    return None


def latest_stage(log_rows: list[dict[str, Any]], running_batch: dict[str, Any] | None = None) -> dict[str, Any] | None:
    scoped_rows = log_rows
    if running_batch:
        batch_id = running_batch.get("batch_id")
        for index in range(len(log_rows) - 1, -1, -1):
            row = log_rows[index]
            if row.get("event") == "batch_started" and row.get("batch_id") == batch_id:
                scoped_rows = log_rows[index + 1 :]
                break
    for row in reversed(scoped_rows):
        if row.get("stage"):
            return row
    return None


def build_report() -> tuple[str, dict[str, Any]]:
    state = read_json(STATE_PATH)
    log_rows, bad_log = read_jsonl(LOG_PATH)
    batches = continuous_batches(log_rows)
    running_batch = current_batch(log_rows)
    stage = latest_stage(log_rows, running_batch)
    processes = process_rows()
    current_run = read_json(CURRENT_RUN_PATH)
    tracked = tracked_process(current_run)
    if tracked and not any(str(row.get("ProcessId")) == str(tracked.get("ProcessId")) for row in processes):
        processes.append(tracked)
    counts = pending_counts()
    args = latest_batch_args(log_rows)
    manifest = read_json(MANIFEST_PATH)

    durations: list[float] = []
    for row in batches[-10:]:
        started = parse_dt(row.get("started_at"))
        finished = parse_dt(row.get("finished_at"))
        if started and finished:
            durations.append((finished - started).total_seconds())
    avg_seconds = sum(durations) / len(durations) if durations else None

    official_limit = arg_value(args, "official_limit", 8)
    mdr_limit = arg_value(args, "mdr_limit", 8)
    media_limit = arg_value(args, "media_websites", 4)
    remaining_batches = max(
        math.ceil(counts["official"]["pending"] / official_limit),
        math.ceil(counts["mdr_ce"]["pending"] / mdr_limit),
        math.ceil(counts["media"]["pending"] / media_limit),
    )
    pause_seconds = float(args.get("pause_seconds") or 0)
    eta_seconds = remaining_batches * ((avg_seconds or 0) + pause_seconds) if avg_seconds else None

    last_finished = parse_dt(state.get("last_finished_at"))
    last_started = parse_dt(state.get("last_started_at"))
    freshness = (now_local() - last_finished).total_seconds() if last_finished else None
    batch_duration = (last_finished - last_started).total_seconds() if last_finished and last_started else None

    manifest_summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    last_summary = manifest_summary or (state.get("last_summary") if isinstance(state.get("last_summary"), dict) else {})
    last_delta = state.get("last_summary_delta") if isinstance(state.get("last_summary_delta"), dict) else {}

    status = "running" if any("run_continuous_verification_batch.py" in str(row.get("CommandLine", "")) for row in processes) else "not running"
    interrupted_batch = running_batch if status == "not running" else None
    display_running_batch = running_batch if status == "running" else None
    queued = any("start_quality_continuation.ps1" in str(row.get("CommandLine", "")) for row in processes)

    lines = [
        "# Verification Status",
        "",
        f"Generated: {now_local().isoformat(timespec='seconds')}",
        f"Runtime: {status}" + ("; quality continuation queued" if queued else ""),
        f"Processes: {', '.join(str(row.get('ProcessId')) for row in processes) or 'none'}",
        f"Current run started: {current_run.get('started_at', 'n/a')}",
        f"Current run stdout: {current_run.get('stdout_log', 'n/a')}",
        "",
        "## Last Completed Batch",
        f"- Batch: {state.get('last_batch_id', 'n/a')} (no. {state.get('batch_no', 'n/a')})",
        f"- Status: {state.get('last_status', 'n/a')}",
        f"- Finished: {state.get('last_finished_at', 'n/a')} ({fmt_duration(freshness)} ago)",
        f"- Duration: {fmt_duration(batch_duration)}",
        f"- Progress units: {state.get('last_progress_units', 'n/a')}",
        "",
        "## Current Batch",
        f"- Running batch: {display_running_batch.get('batch_id') if display_running_batch else 'none'}",
        f"- Started: {display_running_batch.get('started_at') if display_running_batch else 'n/a'}",
        f"- Interrupted batch: {interrupted_batch.get('batch_id') if interrupted_batch else 'none'}",
        f"- Interrupted started: {interrupted_batch.get('started_at') if interrupted_batch else 'n/a'}",
        f"- Last stage event: {stage.get('stage') if stage else 'n/a'} / {stage.get('status') if stage else 'n/a'}",
        "",
        "## Current Totals",
        f"- Latest snapshot: {manifest.get('generated_at', 'n/a')}",
        f"- Official-source evidence: {last_summary.get('company_official_source_evidence', 'n/a')}",
        f"- Official website master: {last_summary.get('official_website_master', 'n/a')}",
        f"- Company website links: {last_summary.get('company_official_website', 'n/a')}",
        f"- Media assets: {last_summary.get('company_media_asset_index', 'n/a')}",
        f"- Product specification evidence: {last_summary.get('product_specification_evidence', 'n/a')}",
        f"- MDR/CE search plan: {last_summary.get('mdr_ce_search_plan', 'n/a')}",
        f"- MDR/CE evidence candidates: see data/mdr_ce_evidence_candidates.jsonl",
        f"- Data quality high issues: {last_summary.get('data_quality_high_issues', 'n/a')}",
        "",
        "## Last Batch Delta",
        f"- Official-source evidence: +{last_delta.get('company_official_source_evidence', 0)}",
        f"- Official websites: +{last_delta.get('official_website_master', 0)}",
        f"- Company website links: +{last_delta.get('company_official_website', 0)}",
        f"- Media assets: +{last_delta.get('company_media_asset_index', 0)}",
        f"- Product specs: +{last_delta.get('product_specification_evidence', 0)}",
        f"- MDR/CE plan rows: +{last_delta.get('mdr_ce_search_plan', 0)}",
        "",
        "## Pending Queue Estimate",
        f"- Official-source queue: {counts['official']['covered']} / {counts['official']['total']} covered; {counts['official']['pending']} pending",
        f"- MDR/CE queue: {counts['mdr_ce']['covered']} / {counts['mdr_ce']['total']} covered; {counts['mdr_ce']['pending']} pending",
        f"- Media/spec website queue: {counts['media']['covered']} / {counts['media']['total']} covered; {counts['media']['pending']} pending",
        f"- Estimated batches remaining at current limits: {remaining_batches}",
        f"- Average recent batch duration: {fmt_duration(avg_seconds)}",
        f"- Rough ETA at current limits: {fmt_duration(eta_seconds)}",
        "",
        "## Notes",
        f"- JSONL parse skips: log={bad_log}, official={counts['official']['bad_jsonl']}, mdr_ce={counts['mdr_ce']['bad_jsonl']}",
        "- ETA is approximate because new official URLs can expand the media/spec queue.",
    ]
    report = "\n".join(lines) + "\n"
    raw = {
        "state": state,
        "processes": processes,
        "pending_counts": counts,
        "running_batch": running_batch,
        "latest_stage": stage,
        "avg_batch_seconds": avg_seconds,
        "remaining_batches": remaining_batches,
        "eta_seconds": eta_seconds,
    }
    return report, raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print machine-readable status.")
    parser.add_argument("--write-md", action="store_true", help="Write data/verification_status.md.")
    args = parser.parse_args()

    report, raw = build_report()
    if args.write_md:
        STATUS_MD_PATH.write_text(report, encoding="utf-8")
    if args.json:
        print(json.dumps(raw, ensure_ascii=False, indent=2))
    else:
        print(report)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    main()

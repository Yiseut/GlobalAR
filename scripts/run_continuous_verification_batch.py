#!/usr/bin/env python3
"""Run resumable verification batches.

This is the project-level loop for ongoing data completion. It intentionally
does not require interactive confirmation between routine collection stages.
Each batch appends a compact log, rebuilds the database/front-end snapshot,
syncs the source workbook, and finishes with smoke checks when possible. The
same entrypoint can run once or keep looping with checkpoints.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_data import DATA_DIR, MANIFEST_PATH, PROJECT_DIR


LOG_PATH = DATA_DIR / "continuous_run_log.jsonl"
STATE_PATH = DATA_DIR / "continuous_run_state.json"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def append_log(record: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def tail(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text[-limit:] if len(text) > limit else text


def run_command(name: str, command: list[str], timeout: int, required: bool = True) -> dict[str, Any]:
    started = time.time()
    record: dict[str, Any] = {
        "stage": name,
        "command": command,
        "started_at": now(),
        "required": required,
        "status": "running",
    }
    print(f"[{name}] {' '.join(command)}", flush=True)
    try:
        proc = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        record.update(
            {
                "status": "ok" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "stdout_tail": tail(proc.stdout),
                "stderr_tail": tail(proc.stderr),
            }
        )
    except subprocess.TimeoutExpired as exc:
        record.update(
            {
                "status": "timeout",
                "returncode": None,
                "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
                "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
                "error": f"timeout after {timeout}s",
            }
        )
    record["finished_at"] = now()
    record["duration_seconds"] = round(time.time() - started, 2)
    append_log(record)
    print(f"[{name}] {record['status']} ({record['duration_seconds']}s)", flush=True)
    if required and record["status"] != "ok":
        raise RuntimeError(f"Required stage failed: {name}")
    return record


def manifest_summary() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    payload = read_json(MANIFEST_PATH)
    return payload.get("summary", {})


def parse_stdout_payload(stage_record: dict[str, Any]) -> dict[str, Any]:
    """Best-effort parser for stage commands that print one JSON object."""
    text = str(stage_record.get("stdout_tail") or "")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def stage_progress_units(stage_record: dict[str, Any]) -> int:
    payload = parse_stdout_payload(stage_record)
    units = 0
    for key in ("records_added", "appended_rows", "candidate_new_rows"):
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            units += max(0, int(value))
    return units


def summary_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, int]:
    keys = (
        "company_official_source_evidence",
        "official_website_master",
        "company_official_website",
        "company_media_asset_index",
        "product_specification_evidence",
        "registration_evidence",
        "evidence_staging",
        "mdr_ce_search_plan",
        "news_regulatory_event_candidates",
        "market_metrics",
    )
    delta: dict[str, int] = {}
    for key in keys:
        before_value = before.get(key)
        after_value = after.get(key)
        if isinstance(before_value, bool) or isinstance(after_value, bool):
            continue
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            change = int(after_value) - int(before_value)
            if change:
                delta[key] = change
    return delta


def batch_progress_units(batch_record: dict[str, Any]) -> int:
    stage_units = sum(stage_progress_units(stage) for stage in batch_record.get("stages", []))
    positive_summary_units = sum(max(0, value) for value in batch_record.get("summary_delta", {}).values())
    return stage_units + positive_summary_units


def build_commands(args: argparse.Namespace) -> list[dict[str, Any]]:
    py = sys.executable
    commands: list[dict[str, Any]] = []
    media_websites = 0 if args.skip_media_assets else args.media_websites
    media_page_fetches = 0 if args.skip_media_assets else args.media_page_fetches
    skip_image_downloads = args.skip_image_downloads or args.skip_media_assets
    if not args.skip_briefing_sync:
        commands.append(
            {
                "name": "sync_briefing_news_events",
                "command": [py, "scripts\\sync_briefing_news_events.py", "--limit-files", str(args.news_limit)],
                "timeout": args.news_stage_timeout,
                "required": False,
            }
        )
    commands.extend(
        [
            {
                "name": "sync_isaps_market_metrics",
                "command": [py, "scripts\\sync_isaps_market_metrics.py"],
                "timeout": 120,
                "required": False,
            },
            {
                "name": "build_data_initial",
                "command": [py, "scripts\\build_data.py"],
                "timeout": args.build_timeout,
                "required": True,
            },
            {
                "name": "build_official_source_plans",
                "command": [py, "scripts\\build_official_source_plans.py", "--limit-companies", "0"],
                "timeout": 180,
                "required": True,
            },
        ]
    )
    commands.extend(
        [
        {
            "name": "collect_company_official_sources",
            "command": [
                py,
                "scripts\\collect_company_official_sources.py",
                "--limit",
                str(args.official_limit),
                "--num-results",
                str(args.search_results),
                "--timeout",
                str(args.search_timeout),
                "--sleep",
                str(args.search_sleep),
            ],
            "timeout": args.official_timeout,
            "required": False,
        },
        {
            "name": "collect_fda_openfda_incremental",
            "command": [
                py,
                "scripts\\collect_fda_openfda_incremental.py",
                "--companies",
                str(args.fda_companies),
                "--aliases",
                str(args.fda_aliases),
                "--per-alias-limit",
                str(args.fda_per_alias_limit),
                "--product-terms",
                str(args.fda_product_terms),
                "--timeout",
                str(args.fda_timeout),
                "--sleep",
                str(args.fda_sleep),
                "--skip-existing-companies",
            ],
            "timeout": args.fda_stage_timeout,
            "required": False,
        },
        {
            "name": "build_mdr_ce_plan",
            "command": [
                py,
                "scripts\\build_mdr_ce_plan.py",
                "--companies",
                str(args.mdr_plan_companies),
                "--families-per-company",
                str(args.mdr_families_per_company),
            ],
            "timeout": 180,
            "required": True,
        },
        {
            "name": "collect_mdr_ce_sources",
            "command": [
                py,
                "scripts\\collect_mdr_ce_sources.py",
                "--limit",
                str(args.mdr_limit),
                "--num-results",
                str(args.search_results),
                "--timeout",
                str(args.search_timeout),
                "--sleep",
                str(args.search_sleep),
            ],
            "timeout": args.mdr_timeout,
            "required": False,
        },
        {
            "name": "build_company_media_assets",
            "command": [
                py,
                "scripts\\build_company_media_assets.py",
                "--limit-websites",
                str(media_websites),
                "--max-images-per-site",
                str(args.media_images_per_site),
                "--max-pages-per-site",
                str(args.media_pages_per_site),
                "--max-page-fetches",
                str(media_page_fetches),
                "--timeout",
                str(args.media_timeout),
                "--sleep",
                str(args.media_sleep),
            ]
            + (["--skip-image-downloads"] if skip_image_downloads else [])
            + (["--download-logos-only"] if args.download_logos_only else [])
            + (["--target-spec-gaps"] if args.target_spec_gaps else []),
            # Product photos and broad page fetches can explode the queue. Product-gap
            # mode keeps generated official/spec tables current without crawling.
            "timeout": args.media_stage_timeout,
            "required": False,
        },
        {
            "name": "build_data_final",
            "command": [py, "scripts\\build_data.py"],
            "timeout": args.build_timeout,
            "required": True,
        },
        {
            "name": "build_progress_reports",
            "command": [py, "scripts\\build_progress_reports.py"],
            "timeout": 180,
            "required": True,
        },
        ]
    )
    if args.product_gap_audit:
        commands.append(
            {
                "name": "audit_product_gap_queue",
                "command": [py, "scripts\\audit_product_gap_queue.py", "--output-stem", "latest"],
                "timeout": 180,
                "required": False,
            }
        )
    if not args.skip_excel_sync:
        commands.append(
            {
                "name": "sync_excel_background_sheets",
                "command": [py, "scripts\\apply_seed_cleanup.py", "sync-background"],
                "timeout": args.excel_timeout,
                "required": False,
            }
        )
    if not args.skip_smoke:
        commands.append(
            {
                "name": "smoke_test",
                "command": [py, "scripts\\smoke_test.py"],
                "timeout": 180,
                "required": True,
            }
        )
    return commands


def run_one_batch(args: argparse.Namespace, run_context: dict[str, Any] | None = None) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = read_json(STATE_PATH)
    batch_no = int(state.get("batch_no") or 0) + 1
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    starting_summary = manifest_summary()
    batch_record: dict[str, Any] = {
        "batch_id": batch_id,
        "batch_no": batch_no,
        "started_at": now(),
        "args": vars(args),
        "run_context": run_context or {},
        "starting_summary": starting_summary,
        "stages": [],
        "status": "running",
    }
    append_log({"event": "batch_started", **batch_record})
    print(json.dumps({"batch_id": batch_id, "batch_no": batch_no, "started_at": batch_record["started_at"]}, ensure_ascii=False))

    try:
        for spec in build_commands(args):
            try:
                result = run_command(spec["name"], spec["command"], spec["timeout"], spec["required"])
            except RuntimeError as exc:
                if not args.continue_on_required_error:
                    raise
                result = {"stage": spec["name"], "status": "required_failed_but_continued", "error": str(exc), "finished_at": now()}
                append_log(result)
            batch_record["stages"].append(result)
        batch_record["status"] = "completed"
    except Exception as exc:  # noqa: BLE001
        batch_record["status"] = "failed"
        batch_record["error"] = str(exc)
    batch_record["finished_at"] = now()
    batch_record["summary"] = manifest_summary()
    batch_record["summary_delta"] = summary_delta(starting_summary, batch_record["summary"])
    batch_record["progress_units"] = batch_progress_units(batch_record)
    write_json(
        STATE_PATH,
        {
            "batch_no": batch_no,
            "last_batch_id": batch_id,
            "last_status": batch_record["status"],
            "last_started_at": batch_record["started_at"],
            "last_finished_at": batch_record["finished_at"],
            "last_summary": batch_record["summary"],
            "last_summary_delta": batch_record["summary_delta"],
            "last_progress_units": batch_record["progress_units"],
            "last_run_context": batch_record["run_context"],
        },
    )
    append_log({"event": "batch_finished", **batch_record})
    print(json.dumps(batch_record, ensure_ascii=False, indent=2))
    return batch_record


def run_continuous(args: argparse.Namespace) -> int:
    max_batches = args.max_batches if args.max_batches and args.max_batches > 0 else 1_000_000
    stalled_batches = 0
    completed_batches = 0
    append_log(
        {
            "event": "continuous_started",
            "started_at": now(),
            "max_batches": max_batches,
            "stop_after_stalled_batches": args.stop_after_stalled_batches,
            "pause_seconds": args.pause_seconds,
            "args": vars(args),
        }
    )
    print(
        json.dumps(
            {
                "event": "continuous_started",
                "max_batches": max_batches,
                "stop_after_stalled_batches": args.stop_after_stalled_batches,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    last_status = "completed"
    stop_reason = "max_batches_reached"
    for loop_index in range(1, max_batches + 1):
        batch_record = run_one_batch(args, {"mode": "continuous", "loop_index": loop_index})
        last_status = batch_record["status"]
        progress_units = int(batch_record.get("progress_units") or 0)
        if last_status != "completed":
            stop_reason = "batch_failed"
            break
        completed_batches += 1
        if progress_units <= 0:
            stalled_batches += 1
        else:
            stalled_batches = 0
        append_log(
            {
                "event": "continuous_checkpoint",
                "finished_at": now(),
                "loop_index": loop_index,
                "batch_id": batch_record["batch_id"],
                "progress_units": progress_units,
                "stalled_batches": stalled_batches,
                "summary_delta": batch_record.get("summary_delta", {}),
            }
        )
        if args.stop_after_stalled_batches > 0 and stalled_batches >= args.stop_after_stalled_batches:
            stop_reason = "no_new_records"
            break
        if loop_index < max_batches and args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    append_log(
        {
            "event": "continuous_finished",
            "finished_at": now(),
            "completed_batches": completed_batches,
            "last_status": last_status,
            "stop_reason": stop_reason,
        }
    )
    print(
        json.dumps(
            {
                "event": "continuous_finished",
                "completed_batches": completed_batches,
                "last_status": last_status,
                "stop_reason": stop_reason,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return 0 if last_status == "completed" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-limit", type=int, default=25)
    parser.add_argument("--mdr-limit", type=int, default=20)
    parser.add_argument("--fda-companies", type=int, default=8)
    parser.add_argument("--mdr-plan-companies", type=int, default=0, help="Priority-company cap for MDR/CE plan. 0 means all companies.")
    parser.add_argument("--mdr-families-per-company", type=int, default=0, help="Per-company family cap for MDR/CE plan. 0 means all families.")
    parser.add_argument("--media-websites", type=int, default=12)
    parser.add_argument("--media-page-fetches", type=int, default=8)
    parser.add_argument("--media-images-per-site", type=int, default=2)
    parser.add_argument("--media-pages-per-site", type=int, default=1)
    parser.add_argument("--search-results", type=int, default=3)
    parser.add_argument("--search-timeout", type=int, default=70)
    parser.add_argument("--search-sleep", type=float, default=0.1)
    parser.add_argument("--official-timeout", type=int, default=2400)
    parser.add_argument("--mdr-timeout", type=int, default=2100)
    parser.add_argument("--fda-aliases", type=int, default=4)
    parser.add_argument("--fda-per-alias-limit", type=int, default=3)
    parser.add_argument("--fda-product-terms", type=int, default=4)
    parser.add_argument("--fda-timeout", type=int, default=25)
    parser.add_argument("--fda-sleep", type=float, default=0.08)
    parser.add_argument("--fda-stage-timeout", type=int, default=900)
    parser.add_argument("--media-timeout", type=int, default=6)
    parser.add_argument("--media-sleep", type=float, default=0.02)
    parser.add_argument("--media-stage-timeout", type=int, default=180)
    parser.add_argument("--skip-media-assets", action="store_true", help="Keep generated official/spec tables but skip broad website media/page crawling.")
    parser.add_argument("--skip-image-downloads", action="store_true")
    parser.add_argument("--download-logos-only", action="store_true")
    parser.add_argument("--target-spec-gaps", action="store_true", help="Prioritize official product pages with missing or weak specification coverage.")
    parser.add_argument("--product-gap-audit", action="store_true", help="Write the latest product verification gap queue after each batch.")
    parser.add_argument("--news-limit", type=int, default=45)
    parser.add_argument("--news-stage-timeout", type=int, default=180)
    parser.add_argument("--build-timeout", type=int, default=300)
    parser.add_argument("--excel-timeout", type=int, default=300)
    parser.add_argument("--skip-briefing-sync", action="store_true")
    parser.add_argument("--skip-excel-sync", action="store_true")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--continue-on-required-error", action="store_true")
    parser.add_argument("--continuous", action="store_true", help="Keep running checkpointed batches until stopped.")
    parser.add_argument("--max-batches", type=int, default=0, help="Maximum batches for --continuous; 0 means no practical cap.")
    parser.add_argument("--pause-seconds", type=float, default=5.0, help="Sleep between continuous batches.")
    parser.add_argument(
        "--stop-after-stalled-batches",
        type=int,
        default=5,
        help="Stop continuous mode after this many completed batches add no records; 0 disables.",
    )
    return parser.parse_args()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    args = parse_args()
    if args.continuous:
        raise SystemExit(run_continuous(args))
    batch_record = run_one_batch(args)
    if batch_record["status"] != "completed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a focused MDR/CE continuation loop.

The general continuous runner also touches official-source, FDA, media and
briefing lanes. This runner keeps the CE/MDR backlog moving after those queues
are already saturated: build the full fact-based plan, collect candidates,
rebuild generated artifacts, audit, and smoke-test.
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


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUN_LOG_PATH = DATA_DIR / "mdr_ce_continuation_log.jsonl"
CURRENT_RUN_PATH = DATA_DIR / "current_mdr_ce_run.json"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def append_log(record: dict[str, Any]) -> None:
    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def tail(text: str, limit: int = 5000) -> str:
    text = text or ""
    return text[-limit:] if len(text) > limit else text


def parse_json_payload(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_command(name: str, command: list[str], timeout: int, required: bool = True) -> dict[str, Any]:
    started = time.time()
    record: dict[str, Any] = {
        "stage": name,
        "command": command,
        "started_at": now(),
        "status": "running",
        "required": required,
    }
    print(f"[{name}] {' '.join(command)}", flush=True)
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
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
                "payload": parse_json_payload(proc.stdout),
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
                "payload": {},
            }
        )
    record["finished_at"] = now()
    record["duration_seconds"] = round(time.time() - started, 2)
    append_log(record)
    print(f"[{name}] {record['status']} ({record['duration_seconds']}s)", flush=True)
    if required and record["status"] != "ok":
        raise RuntimeError(f"Required stage failed: {name}")
    return record


def run_batch(args: argparse.Namespace, batch_index: int, run_id: str) -> dict[str, Any]:
    py = sys.executable
    stages: list[dict[str, Any]] = []
    batch: dict[str, Any] = {
        "event": "batch_started",
        "run_id": run_id,
        "batch_index": batch_index,
        "started_at": now(),
        "status": "running",
    }
    append_log(batch)
    write_json(CURRENT_RUN_PATH, {**batch, "args": vars(args)})

    try:
        stages.append(
            run_command(
                "build_mdr_ce_plan",
                [py, "scripts\\build_mdr_ce_plan.py", "--companies", "0", "--families-per-company", "0"],
                args.build_timeout,
                True,
            )
        )
        stages.append(
            run_command(
                "collect_mdr_ce_sources",
                [
                    py,
                    "scripts\\collect_mdr_ce_sources.py",
                    "--limit",
                    str(args.limit),
                    "--num-results",
                    str(args.num_results),
                    "--timeout",
                    str(args.search_timeout),
                    "--sleep",
                    str(args.search_sleep),
                ],
                args.collect_timeout,
                False,
            )
        )
        stages.append(run_command("build_data", [py, "scripts\\build_data.py"], args.build_timeout, True))
        stages.append(run_command("build_progress_reports", [py, "scripts\\build_progress_reports.py"], 180, True))
        stages.append(
            run_command(
                "audit_product_gap_queue",
                [py, "scripts\\audit_product_gap_queue.py", "--output-stem", "latest"],
                180,
                False,
            )
        )
        if args.sync_every and batch_index % args.sync_every == 0:
            stages.append(run_command("sync_excel_background", [py, "scripts\\apply_seed_cleanup.py", "sync-background"], args.excel_timeout, False))
            stages.append(run_command("sync_excel_ce_plan", [py, "scripts\\apply_seed_cleanup.py", "sync-ce-plan"], args.excel_timeout, False))
        stages.append(run_command("smoke_test", [py, "scripts\\smoke_test.py"], 180, True))
        status = "completed"
    except Exception as exc:  # noqa: BLE001
        status = "failed"
        batch["error"] = str(exc)

    collect_payload = {}
    for stage in stages:
        if stage.get("stage") == "collect_mdr_ce_sources":
            collect_payload = stage.get("payload") or {}
            break
    records_added = int(collect_payload.get("records_added") or 0)
    batch.update(
        {
            "event": "batch_finished",
            "status": status,
            "finished_at": now(),
            "records_added": records_added,
            "records_total": collect_payload.get("records_total"),
            "queries_run": collect_payload.get("queries_run"),
            "stages": stages,
        }
    )
    append_log(batch)
    write_json(CURRENT_RUN_PATH, {**batch, "args": vars(args)})
    print(json.dumps({k: batch.get(k) for k in ["run_id", "batch_index", "status", "queries_run", "records_added", "records_total"]}, ensure_ascii=False))
    return batch


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-batches", type=int, default=60)
    parser.add_argument("--limit", type=int, default=30, help="MDR/CE plan rows per batch. 0 means all remaining pending rows.")
    parser.add_argument("--num-results", type=int, default=6)
    parser.add_argument("--search-timeout", type=int, default=45)
    parser.add_argument("--search-sleep", type=float, default=0.4)
    parser.add_argument("--collect-timeout", type=int, default=2400)
    parser.add_argument("--build-timeout", type=int, default=480)
    parser.add_argument("--excel-timeout", type=int, default=600)
    parser.add_argument("--pause-seconds", type=float, default=20)
    parser.add_argument("--stop-after-empty", type=int, default=5)
    parser.add_argument("--sync-every", type=int, default=10, help="Sync Excel every N completed batches. 0 disables loop sync.")
    args = parser.parse_args()

    run_id = f"mdr_ce_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    empty_batches = 0
    append_log({"event": "run_started", "run_id": run_id, "started_at": now(), "args": vars(args)})
    write_json(CURRENT_RUN_PATH, {"event": "run_started", "run_id": run_id, "started_at": now(), "args": vars(args), "status": "running"})
    last_batch: dict[str, Any] = {}
    for batch_index in range(1, max(1, args.max_batches) + 1):
        last_batch = run_batch(args, batch_index, run_id)
        if last_batch.get("status") != "completed":
            break
        if int(last_batch.get("records_added") or 0) <= 0:
            empty_batches += 1
        else:
            empty_batches = 0
        if args.stop_after_empty and empty_batches >= args.stop_after_empty:
            break
        if batch_index < args.max_batches and args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    finished = {
        "event": "run_finished",
        "run_id": run_id,
        "finished_at": now(),
        "last_status": last_batch.get("status", "unknown"),
        "last_records_added": last_batch.get("records_added", 0),
        "empty_batches": empty_batches,
    }
    append_log(finished)
    write_json(CURRENT_RUN_PATH, {**finished, "args": vars(args), "status": "finished"})
    print(json.dumps(finished, ensure_ascii=False, indent=2))
    raise SystemExit(0 if last_batch.get("status") == "completed" else 1)


if __name__ == "__main__":
    main()

# Global Aesthetics Dashboard - Continuation Handoff

Updated: 2026-05-19 15:07 +08:00

## Current State

The project is in product-gap verification mode. The dashboard treats
`..\全球医美企业库_标准化版v4.xlsx` as an unverified seed workbook, not as final
truth.

The already-running verification process is still the older 01:12 run and is
healthy, but it was launched before the product-gap switch:

- Runtime: running
- Process: `43924` (`cmd.exe`)
- Current run started: 2026-05-19 01:12:57 +08:00
- Current stdout log:
  `data\continuous_verification_20260519_011257.log`
- Last completed batch checked: `batch_20260519_150027`, no. 1501
- Last completed at: 2026-05-19 15:06:22 +08:00
- Current batch at handoff: none
- Watchdog status: repeatedly confirms "Main verification task is already running."

Do not stop the runner just because an old Codex conversation is slow or stuck.
Only stop it if the user explicitly wants to pause the data collection process.
Future starts through `scripts\start_continuous_verification.ps1` now skip broad
media/page crawling and refresh the product-gap queue instead.

## Latest Counts

- Companies: 372
- Product families: 967
- Products: 977
- Official-source evidence: 27,110
- Official website master rows: 19,992
- Company website links: 372
- Media assets: 6,802
- Product specification evidence: 31,624
- MDR/CE search plan rows: 789
- Registration evidence rows: 410
- Promoted product-master evidence rows: 121
- Promoted registration evidence rows: 168
- Data quality high issues: 0

## Queue Snapshot

- Official-source queue: 3,706 / 3,706 covered, 0 pending
- MDR/CE queue: 789 / 789 covered, 0 pending
- Media/spec website queue in the old running process: 3,913 / 19,992 covered,
  16,084 pending
- Old-process estimated batches remaining at current limits: about 2,011
- Old-process recent average batch duration: about 5m 54s
- Old-process rough ETA at current limits: about 215 hours

ETA is approximate because new official URLs can expand the media/spec queue.
It is mainly useful as evidence that the old broad crawl is too expensive.

## Product Gap Queue

- Latest queue summary: `data\audits\product_gap_summary_latest.md`
- Latest queue CSV: `data\audits\product_gap_queue_latest.csv`
- Current queue rows: 977 products across 372 companies
- Review-first rows: P0 103, P1 658, P2 37, P3 179
- Unverified seed products: 849
- Regulated products without registration evidence: 767
- Existing stored website/spec signals did not expose unmapped product-line
  additions, so true product-line supplementation should use targeted catalog,
  IFU, and official product-page checks from the P0/P1 queue.

## How To Continue In A New Chat

Start the new Codex conversation in:

```text
E:\shared\Documents\data\global_aesthetics_dashboard
```

Suggested first message:

```text
请先读取 PROJECT_HANDOFF.md 和 README.md，然后运行当前核验状态检查，继续这个 global_aesthetics_dashboard 项目。
```

Then run:

```powershell
python scripts\show_verification_status.py
python scripts\audit_product_gap_queue.py --output-stem latest
```

If the dashboard UI needs checking:

```powershell
python server.py --port 8790
```

Open:

```text
http://127.0.0.1:8790/
```

## Operating Rules To Preserve

- Regulator facts require regulator, certificate, label, or IFU evidence.
- Product and specification facts require official company, brand, product,
  IFU, catalog, or official PDF evidence.
- Secondary media and databases are only cross-check leads.
- China NMPA stays outside this global project because the China dashboard
  covers it separately.
- Automatic collection goes into staging/review structures first.
- Promote facts into master tables only after review-worthy evidence is present.
- Rebuild `data\global_aesthetics.db`, `web\app-data.js`, progress artifacts,
  and the source Excel sheets after successful batches.
- Run `python scripts\smoke_test.py` after rebuilds when the local server is up.

## If The Old Conversation Is Stuck

Close or stop the old Codex conversation from the app UI if possible. The
project runner itself is separate and, at this handoff, appears to be running
normally. A stuck conversation does not automatically mean the verification
runner should be killed.

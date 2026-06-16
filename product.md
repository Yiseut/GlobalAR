# Global Aesthetics 数据产品说明

更新日期：2026-06-16 +08:00

本项目是全球医美上游行业数据库和 Dashboard。源 Excel、自动采集证据池、网页候选池、规格候选池都应视为 seed / review material，不是自动成立的最终事实。

## 核心原则

- `..\全球医美企业库_标准化版v4.xlsx` 是可编辑线索库，不是唯一事实源。
- 长期修复应写回源 CSV / JSONL / Excel，再运行 `scripts\build_data.py` 重建。不要把直接修改 `data\global_aesthetics.db` 当成 durable fix。
- 监管事实以监管机构、证书、label、IFU 等官方证据为准。
- 产品、规格、技术路线、公司关系、财务口径，以官方公司页、品牌页、产品页、IFU、catalog、PDF、年报、IR 材料为准。
- 二级网页、搜索摘要、媒体、marketplace、宽泛网页抓取只能产生候选，不应直接提升为 master fact。
- reference/review 队列里的 blank `company_id` 不自动等于错误；只有核心 master 表或已提升事实需要该关系时，才应视为发布阻断问题。
- SQLite 当前不声明式定义外键，外键一致性由 guardrail 脚本在每次 build 后验证。

## 2026-06-16 修补经验

- 不要把所有 warning 强行清零。需要区分：
  - failure：会阻断发布或破坏分析可信度。
  - warning/backlog：可以解释、可以分享，但必须持续跟踪。
- `company_financial_metrics` 里的 `Galderma` 可以安全映射，因为 `company_master` 已有 canonical `Galderma`，稳定 ID 为 `co_2d09d05893cd`，且 listed identity 语境一致。
- 剩余 financial/listed blank `company_id` 不是同一类问题：
  - `El.En. Group` 有 stock-code 候选，但还需要确认财务实体和当前公司实体是否应合并。
  - Waldencast / Obagi 需要先确认 listed parent 与 operating company 的关系口径。
  - Novartis 需要先处理 stale / questionable ticker 和是否 in-scope。
- `registration_evidence` 中的 `needs_review` / `manual_new_product_candidate` 是审核 backlog，不是 build 失败。处理路径应是 promote、merge、exclude 或 verified unavailable。
- 跨公司 SKU/family mismatch 如果来自源 Excel 的 `duplicate_of` 或 `duplicate_non_primary`，可能是 parent/affiliate trace，不能直接当作 ownership 错误。
- public company 的 `aesthetics_revenue_pct` 不能用 total revenue 推断，只能来自 segment disclosure、年报注释、IR 材料，或明确标记 `not_disclosed` / `unavailable_verified`。
- 源文本里的 NUL 字节会污染 CSV 和 SQLite 文本字段。build 逻辑应在写出生成 CSV 和 SQLite 前清理 `\x00`。
- 规格、容量、包装单位不等于独立产品。比如 `3mL` 应放在规格/包装或说明字段里，不能单独建成 product / family。
- 产品 owner 需要拆成不同角色，不要只填一个公司名：`legal_manufacturer`、`brand_owner`、`marketing_holder`、`distributor` 可以逐步补齐；`relationship_type` 用来记录 own brand、licensed、distributed、affiliate 等关系。
- 手工补产品线优先走 `data\manual_product_line_supplement.csv` 这种 supplement 层，避免直接改生成后的 master CSV 或 SQLite。含英文逗号的字段，如 `Humedix Co., Ltd.` 和长 `Introduction`，必须用 CSV 引号包住。

## 每次 Build 后固定运行的指令

每次新增抓取、手工补源、修复源 CSV/JSONL/Excel，或修改 `scripts\build_data.py` 后，都运行下面这组命令：

```powershell
Set-Location 'E:\shared\Documents\data\global_aesthetics_dashboard'

# 若改过手工 supplement CSV，先确认列没有被逗号切歪
Import-Csv data\manual_product_line_supplement.csv | Select-Object -First 3

python scripts\build_data.py
python scripts\repair_integrity_residuals_20260615.py
python scripts\repair_reference_key_hygiene_20260615.py
python scripts\build_data_quality_backlog_queues_20260616.py
python scripts\validate_database_guardrails_20260616.py
python scripts\v4_acceptance_self_check.py
python scripts\audit_data_usability.py
```

其中两个 repair 脚本默认是 dry-run。健康状态应是没有 planned repair work。如果 dry-run 发现还有可机械修复的问题，先看对应 `data\audits\*_latest.csv/json`，确认不是需要人工判断的实体解析问题，再运行：

```powershell
python scripts\repair_integrity_residuals_20260615.py --apply
python scripts\repair_reference_key_hygiene_20260615.py --apply
python scripts\build_data.py
python scripts\build_data_quality_backlog_queues_20260616.py
python scripts\validate_database_guardrails_20260616.py
python scripts\v4_acceptance_self_check.py
python scripts\audit_data_usability.py
```

如果这次改动会影响本地 Dashboard UI，还要做 UI smoke test。服务需要单独窗口或后台进程运行：

```powershell
# PowerShell A
Set-Location 'E:\shared\Documents\data\global_aesthetics_dashboard'
python server.py --port 8790
```

```powershell
# PowerShell B
Set-Location 'E:\shared\Documents\data\global_aesthetics_dashboard'
python scripts\smoke_test.py
```

## 验收信号

每次 build 后，至少确认：

- `scripts\validate_database_guardrails_20260616.py` 输出 `Ready to share`，且 `failure_count = 0`。
- `scripts\v4_acceptance_self_check.py` 输出 `overall_passed = true`。
- `scripts\audit_data_usability.py` 没有 missing owner/status rows。
- `data\audits\database_guardrail_validation_latest.md` 中：
  - `foreign_key_orphans` 为空。
  - NUL-byte 检查为空。
  - core owner mismatch 为 0。
  - promoted fact traceability 为 0。
- `data\audits\data_quality_backlog_queue_summary_latest.md` 中的 backlog 数量可以解释，不出现新类型的未分类 warning。

## 2026-06-16 已知非阻断 Warning

这些 warning 当前不阻断 v4 acceptance，但必须通过 backlog 队列持续推进：

- `listed_company_batch` 还有 6 条 blank `company_id`。
- `company_financial_metrics` 在 Galderma 映射后还有 4 条 blank `company_id`。
- `registration_evidence` 还有 120 条 review backlog。
- 6 条 duplicate/affiliate SKU-family 跨公司 trace 已确认为源 `duplicate_of` 逻辑，不按错误处理。
- public company 的 `aesthetics_revenue_pct` 还有 21 家待补强。
- SQLite 没有声明式外键，当前靠 guardrail 脚本验证约束。

## Backlog 队列

不要让 warning 长期停留在口头说明里。新 warning 应进入 queue 或 guardrail report。

- `data\audits\entity_resolution_review_queue_latest.csv`
  - 跟踪 listed / financial blank `company_id`。
  - `candidate_company_id` 只是候选，不是自动映射结果。
  - 需要按 listed entity、operating company、parent/affiliate 关系做审核。
- `data\audits\registration_review_queue_latest.csv`
  - 跟踪 `needs_review` 和 `manual_new_product_candidate`。
  - 处理动作应落到 promote、merge、exclude、source review、verified unavailable。
- `data\audits\aesthetics_revenue_pct_collection_queue_latest.csv`
  - 跟踪 public company aesthetics revenue share 缺口。
  - 只能基于 segment evidence 或明确未披露判断补值。

## 后续抓取和元数据库更新注意事项

- 新抓取证据先进入 staging/review 层，不直接写 master。
- 每条可提升证据都要保留 source URL、source type、captured_at、confidence、review_status。
- 不确定的公司实体关系不要为了消除 blank ID 而硬填；应保留 blank，并写明 unresolved 原因。
- 财务数据要区分 total company revenue、aesthetics revenue、segment revenue、market cap、valuation snapshot，不要混用。
- listed parent、operating subsidiary、brand owner、manufacturer、marketing holder 是不同实体角色，不能只凭名字相似合并。
- 监管注册号、适应症、intended use、legal manufacturer、local holder 必须保留长表事实，不要只回填到产品主表后丢失来源。
- 如果某类人工例外已确认合理，要把例外条件写进 guardrail，使它未来保持 warning 或 accepted exception，而不是每次重新报错。
- 如果某类 warning 变成高频问题，要新增专门 queue 文件，并在本文件补充口径。

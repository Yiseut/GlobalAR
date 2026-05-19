# Global Aesthetics Dashboard

本地仪表盘现在把 `全球医美企业库_标准化版v4.xlsx` 视为 `unverified seed`：它是待核验线索库，不是唯一事实源。

## 启动

双击 `Open-Global-Dashboard.bat`，或在本目录运行：

```powershell
python scripts\build_data.py
python server.py --port 8790
```

然后打开：

```text
http://127.0.0.1:8790/
```

## 核验工作流

1. `scripts\build_data.py` 生成本地数据库、前端数据快照和核验队列。
2. 头部公司规则：`Companies` 按 `Product_Count` 前 30，加上已上市且产品数较高的公司。
3. 当前阶段只做 FDA 与 MDR/CE；中国 NMPA UDI/注册查询由单独的中国区仪表盘覆盖，不进入本项目队列。
4. 自动采集只进入 `evidence_staging` 和 `registration_evidence`，状态保持 `needs_review`。
5. 人工审核通过后，才应合并到 `company_master`、`product_master` 或正式注册事实字段。

## 源表清洗

原始 Excel 可以作为后续项目继续复用，但修改前必须先备份。确定性清洗统一走脚本：

```powershell
python scripts\apply_seed_cleanup.py cleanup
python scripts\build_data.py
python scripts\apply_seed_cleanup.py sync-audit
```

- `cleanup` 会备份 `全球医美企业库_标准化版v4.xlsx`，再写回可机械确认的修正，例如稳定 `Product_UUID`、公司名大小写合并、缺失 `Core_Product` 的品牌回填、公司/品牌派生统计刷新。
- `sync-audit` 会把最新 `data\seed_integrity_issues.csv` 写回源表的 `Seed_Integrity_Issues` sheet，同时保留 `Cleanup_Log`。
- 不确定的事实不硬填，只保留在审计问题里等待人工核验。

可先运行 FDA 510(k) 官方 API 采集：

```powershell
python scripts\collect_verification_evidence.py --companies 5 --per-alias-limit 5
python scripts\build_data.py
```

第二次 `build_data.py` 会把 `data\verification_evidence_staging.jsonl` 导入数据库和 Dashboard。

## 数据层

- `company_master`：公司标准名、别名、母公司、上市代码、交易所映射、审核状态。
- `company_geo`：公司城市/国家级地图落点，优先城市坐标，缺失时使用国家中心点并保留 `precision`。
- `product_master`：品牌-产品-技术路线拆分，保留 claim 与 verified differentiator 两层。
- `seed_integrity_issues`：原始 seed 完整性审计问题，不直接修改 Excel。
- `registration_evidence`：按国家/监管机构的长表注册证据。
- `market_snapshot`：股票动态字段占位，和静态 Excel 解耦。
- `official_source_registry`：当前项目展示 FDA、EUDAMED/MDR/CE 以及后续 roadmap 入口；NMPA 标记为外部中国项目，不在当前 Dashboard 展示。
- `verification_queue`：头部公司的公司背景、产品映射、FDA 和 MDR/CE 核验任务。
- `evidence_staging`：自动采集到、但尚未人工审核的证据。

## 输入与生成物

- 主线索库：`..\全球医美企业库_标准化版v4.xlsx`
- 会议/参展：`..\医美行业会议信息.xlsx`、`..\Global Major Congress 2025.xlsx`
- 市场指标：`..\医美行业数据\yanmei_macro_stats.csv`、`..\医美行业数据\医美行业数据.xlsx`
- 报告文本：`..\医美行业数据\*.md`、`..\行业报告\*.md`

生成物：

- `data\global_aesthetics.db`
- `web\app-data.js`
- `data\import_manifest.json`
- `data\verification_evidence_staging.jsonl`
- `data\seed_integrity_issues.csv`
- `data\seed_integrity_report.md`
- `data\seed_integrity_summary.json`
- `web\world.geojson`：本地化低精度世界底图，用于首屏企业星图。

## 验证

```powershell
python scripts\smoke_test.py
```

`smoke_test.py` 需要本地服务运行，以便同时验证 Dashboard API。

## MDSAP 口径

MDSAP 是单一质量体系审核项目，不是直接销售许可证。它覆盖的参与监管方包括澳洲 TGA、巴西 ANVISA、Health Canada、日本 MHLW/PMDA、美国 FDA；但各市场销售仍需要对应市场授权或注册，例如澳洲 ARTG、巴西 ANVISA、加拿大 MDL、日本 PMDA/MHLW、美国 FDA 510(k)/PMA/listing 等。

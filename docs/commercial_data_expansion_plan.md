# 全球医美商业数据扩展计划

更新时间：2026-07-07

## 目标骨架

商业格局模块先不继续扩前端，先把数据层改成四根骨架：

1. 治疗数量：国家 × 年份 × 赛道/项目。
2. 公司收入：公司 × 年份 × 地区/赛道/产品线收入。
3. 渠道密度：国家/城市 × 品牌/赛道 × provider、clinic、distributor 覆盖。
4. 宏观需求：国家 × 年份 × 人口、收入、老龄化、医生/医疗资源等解释变量。

市场报告和社媒搜索只作为预测或热度 proxy，不再作为确定性商业事实主干。

## 当前缺口

第一轮扩容后，`v3-market-intelligence` 快照中商业数值指标已从 220 条扩到 1909 条：

- 医美治疗数量：1670 条，主干来自 ISAPS 2020-2024，另有 ASPS 2024 美国 procedure trend 55 条。
- 市场规模：39 条。
- 增长率：23 条。
- 市场份额：11 条。
- 销量：1 条。
- 来源陈述型指标：165 条。

当前已把 ISAPS 2020-2024 接入同一张 `data/isaps_market_metrics.csv` 主干表，并修正 2024 国家页漏抽问题。ISAPS 主干现有 1758 行：2024 年 558 行、2023 年 390 行、2022 年 285 行、2021 年 255 行、2020 年 270 行，其中治疗数量 1608 行、医生数量 150 行。

已用 Scrapling 采集 ASPS 与 The Aesthetic Society 官方统计入口，下载 96 个官方统计 PDF：ASPS 70 个、The Aesthetic Society 26 个。ASPS 2024 procedure trend 已抽取到 `data/asps_market_metrics.csv`，当前 55 行已进入 market metrics；ASPS average fee / regional / age / gender PDF 和 The Aesthetic Society 2020-2023 PDF 已落地，下一步按同一套 source label 继续抽表。

第二轮和企业 Top 15 补查用 Scrapling 做了地区级来源发现，覆盖韩国、台湾、香港、巴西、英国、德国、日本、法国、西班牙、意大利、以色列、美国、瑞士、捷克、加拿大、波兰和瑞典。已保存 36 个官方/协会入口、472 条发现记录，下载 49 个来源文件，落到 `data/audits/commercial_geo_market_source_discovery_latest.csv`。企业数量排名前 15 的国家/地区已经全部有至少一个行业数据入口，其中 USA/UK 是可直接进入治疗量主干的硬统计口径，德国/西班牙/意大利是治疗量候选待 QA，其余多为渠道密度、医生 denominator、协会 context 或需求 proxy。初步分流如下：

- 英国 BAAPS 2020-2025 annual audit 已作为 source-labeled UK lane 接入 `data/baaps_market_metrics.csv`：外科 current-year 覆盖 2020、2021、2023、2024、2025，非手术覆盖 2022-2025；2022 外科暂不从百分比倒推。
- 德国 DGÄPC 2020-2025 statistics PDF 已完成 metric QA：方法为 DGÄPC 成员机构患者标准化问卷，治疗项目是偏好/需求百分比而非全国 procedure count，因此不进入治疗量主干，可保留为德国需求 proxy。
- 巴西 SBCP `Pesquisas` 页公开 2025 demography/censo flipbook 及历史 Censo/ISAPS 链接；2025 Censo 已完成结构 QA，主题是整形外科医生数量与城市/州地缘经济画像，page 4 的 27 个州级医生数已接入渠道密度明细，不作为治疗量。
- 香港 DATA.GOV.HK / DH Cap. 633 CSV 已按国家/地区聚合成 licensed day procedure centre 与 private hospital denominator，进入 `data/commercial_channel_density_detail.csv`，联系方式字段不进入前台。
- 台湾 MOHW 核准施行特定美容医学手术医疗机构 PDF 已按国家/县市接入渠道密度明细：2025-06-30 快照共 435 家核准机构，另保留 3 个明确为 0 的离岛县市。
- 台湾 MOHW 医疗机构与人员 open-data ODS 已按县市聚合成 2024-12-31 全医疗机构数和西医师数，作为总体医疗供给底盘，不替代医美专用机构覆盖。
- 日本 MHLW 美容医疗现状材料 page 5 已接入 2019-2022 JSAPS 调查对象机构数与回答机构数，作为日本本地调查覆盖框架；医生专科人数仍待抽表。
- 西班牙 SECPRE 2022 报告的 2021 外科手术数量表已完成手工 QA，并以 SECPRE surgical-only source lane 接入 `data/europe_association_market_metrics.csv`；患者结构/性别年龄等仍保留为未推广背景。
- 意大利 AICPE observatory 老入口目前不可用，可读转载明确引用 ISAPS 2020；其中 2020 total 与主表 Italy 2020 ISAPS 行一致，先保留为协会解读/交叉核验，不重复写入治疗量主干；2019 只在重启官方 ISAPS 2019 backfill 时再考虑。
- 更适合作为渠道密度 proxy：巴西 CFM 医疗人口统计、SBCP surgeon locator；香港 DATA.GOV.HK day procedure centre CSV、台湾 MOHW 美容医学核准机构 PDF 和台湾医疗机构/人员 ODS 已先落地为机构 denominator。
- 日本 MHLW 美容医疗资料和医疗信息网适合做医师/机构密度 proxy；法国 CNOM atlas 和 SOFCEP 页面适合做医生/外科医生 denominator 与协会 context。
- 瑞士 FMH 医师统计和 Swiss Plastic Surgery 适合做外科医生 denominator 与协会 context；捷克 NRPZS 和 Czech Society of Plastic Surgery 适合做 provider/channel proxy。
- 加拿大 CIHI physician specialty、CSPS 和 CSAPS surgeon locator 适合做 physician denominator、协会 context 与 surgeon-density proxy；波兰 NIL/PTChPRiE、瑞典 Socialstyrelsen/SPKF/SFEP 适合做国家医师/外科医生 denominator 与协会/locator proxy。
- 更适合作为需求/热度 proxy：韩国 MOHW 外国患者统计和 KHISS/KHIDI 统计入口、香港 Consumer Council medical beauty 投诉/监管信号、以色列协会新闻/调查和 IMAJ 专题 context。

2020 至今已经足够支撑近周期趋势。2015-2019 的 ISAPS 疫情前基线不再作为主线阻断项；如果官方 PDF 容易获得，可作为 optional backfill，否则优先补 2020 至今更细的美国协会口径、公司收入、渠道密度和宏观解释变量。

## 数据源优先级

### 第一阶段：治疗数量时间轴

目标：在 ISAPS 2020-2024 国家-年份-赛道主干上，补 2020 至今更细的美国项目、费用、区域和 billing 口径。

优先源：

- ISAPS Global Survey：全球和国家层面的手术、非手术、注射类、面部年轻化等治疗数量。
- ASPS Plastic Surgery Statistics：美国手术/微创/项目/区域/费用深挖。
- The Aesthetic Society Procedural Statistics：美国私营审美外科和 billing/价值口径补充。
- BAAPS Annual Audit：英国 2020-2025 美容外科 audit 口径，已单独做 UK source lane；当前 92 行进入治疗量时间轴。
- DGÄPC Statistics：德国 2020-2025 统计 PDF 已定性为 patient-survey demand proxy，不作为治疗量事实主干。
- SBCP Pesquisas/Censo：巴西协会研究页和 2025 demography/censo flipbook，2025 版已作为 surgeon-demography/channel-density denominator 落地；历史 Censo 只在需要疫情前行业结构对照时再补。
- SECPRE 2022：西班牙医美外科报告，Table 1 已作为 2021 surgical-only procedure volume 接入；其他患者结构与调查项暂不进治疗量主干。
- AICPE / SICPRE：意大利协会 commentary 目前作为 ISAPS 交叉核验和国家协会语境，不作为新的治疗量口径覆盖主干。

建模原则：

- 保留 `source_org` 和 `report_title`，不要把 ASPS、Aesthetic Society、ISAPS 的美国 totals 静默合并。
- `category_l1/category_l2/category_l3` 保持赛道/项目粒度，产品材料留给产品页。
- 每条数值都必须有 `year`、`geo`、`unit`、`confidence`、`note`。

### 第二阶段：公司收入与估值

目标：补 `公司 × 年份 × 地区/赛道收入`，避免用公司总收入假装医美收入。

优先源：

- SEC EDGAR Companyfacts：美股公司总收入、利润、权益、EPS，当前已有一部分。
- 公司 IR 报告和 earnings materials：用于提取 aesthetic segment、region revenue、product-line revenue。
- OPEN DART：韩国 Hugel、Medytox、Daewoong、Classys、PharmaResearch 等。
- EDINET：日本相关上市公司。

建模原则：

- `company_total` 和 `aesthetic_segment` 必须分开。
- 地区收入、赛道收入和产品线收入必须带口径备注。
- 估值只作为快照，不覆盖财务报表事实。

### 第三阶段：渠道密度 Proxy

目标：补市场进入后的商业覆盖，而不是产品注册进入。

优先源：

- 品牌 provider locator：国家/城市/品牌覆盖。
- Enrichment providers：Clay、ZoomInfo、Apollo、HG Insights 等，用于诊所、连锁、分销商、公司 firmographics。
- CMS Open Payments：美国公司-医生触达和 KOL/payment proxy。
- 国家/地区官方机构目录：巴西 CFM/SBCP 医师与协会会员入口；香港 licensed day procedure centres 与台湾 MOHW 美容医学核准机构已完成第一版聚合。
- 日本 MHLW：美容医疗相关医师资料和全国医疗信息网。
- 法国 CNOM / SOFCEP：医生人口统计和 qualified surgeon context。
- 瑞士 FMH、捷克 NRPZS、加拿大 CIHI/CSAPS、波兰 NIL/PTChPRiE、瑞典 Socialstyrelsen/SPKF/SFEP：优先补 Top 15 企业国家的 physician/provider/channel density proxy。

建模原则：

- 默认只存机构/城市/品牌覆盖，不把个人联系方式放入 dashboard。
- 渠道密度是 proxy，不能当销量。
- provider locator 和 enrichment provider 的覆盖偏差必须写入 `note` 或 `confidence`。

### 第四阶段：宏观需求与热度 Proxy

目标：解释“为什么某国潜力高”，不直接替代商业规模。

优先源：

- World Bank WDI：人口、GDP per capita、城市化、老龄化。
- OECD Health Statistics：医生密度、医疗支出、医疗资源。
- 韩国 MOHW/KHISS：外国患者、医疗旅游和健康产业统计，作为跨境需求与 specialty demand proxy。
- 香港 Consumer Council：medical beauty 投诉和监管信号，只作为 consumer/risk heat proxy。
- 以色列 Plastic and Aesthetic Surgery Society / IMAJ：协会调查、新闻、specialty context，只作为热度或 context proxy。
- UN Comtrade：EBD/设备/耗材进口 proxy，需 HS code caveat。
- Google Trends / social search：消费者兴趣热度。
- 市场报告 archive：forecast、CAGR、market size secondary evidence。

建模原则：

- 宏观变量是解释变量。
- 搜索热度和社媒热度是 relative index。
- 市场报告继续保留矛盾组和来源口径，不覆盖主干事实。

## 已落地文件

- `data/commercial_data_source_registry.csv`：数据源 registry。
- `data/audits/commercial_data_collection_backlog_latest.csv`：采集 backlog。
- `data/isaps_market_metrics.csv`：ISAPS 2020-2024 国家-年份-赛道治疗数量主干。
- `data/asps_market_metrics.csv`：ASPS 2024 美国 procedure trend 主干，当前 55 行。
- `data/baaps_market_metrics.csv`：BAAPS UK annual audit source-labeled 治疗量，当前 92 行。
- `data/europe_association_market_metrics.csv`：欧洲协会 source-labeled 指标，当前包含 SECPRE Spain 2021 surgical-only procedure volume。
- `data/commercial_channel_density_detail.csv`：渠道/医生 denominator 明细，当前包含 SBCP Brazil 2025 州级整形外科医生数 27 行、香港 DH Cap. 633 国家/地区 licensed day procedure centre 与 private hospital denominator、台湾 MOHW 国家/县市核准美容医学机构 denominator、台湾 MOHW 全医疗机构/西医师 denominator、日本 MHLW/JSAPS 调查覆盖框架。
- `data/audits/commercial_phase1_official_source_inventory_latest.csv`：Scrapling 采集到的 ASPS / Aesthetic Society 官方统计来源清单。
- `data/audits/commercial_geo_market_source_discovery_latest.csv`：Scrapling 采集到的地区级官方/协会来源发现清单。
- `scripts/sync_isaps_market_metrics.py`：ISAPS PDF 抽取与合并脚本。
- `scripts/collect_phase1_official_stats_sources.py`：Scrapling 官方统计入口采集与 PDF 下载脚本。
- `scripts/collect_geo_market_source_discovery.py`：Scrapling 地区级来源发现与官方文件下载脚本。
- `scripts/extract_asps_market_metrics.py`：ASPS procedure trend PDF 抽取脚本。
- `scripts/extract_channel_density_detail.py`：统一生成渠道/医生 denominator 明细，当前覆盖 Brazil SBCP、Hong Kong DH、Taiwan MOHW 与 Japan MHLW survey frame。
- `scripts/validate_commercial_data_expansion.py`：检查 registry、backlog 与当前商业快照缺口。

## 下一步

第一批中 `cdp1_isaps_schema_lock`、`cdp1_isaps_2023_backfill`、`cdp1_isaps_2022_2020_backfill` 已完成。下一步不强求 2015-2019，先补 2020 至今更高信息密度的数据：

1. 接 ASPS 2024 和 2020-2023 历史年份，单独作为美国 ASPS 口径。
2. 接 The Aesthetic Society 2020 至今统计，单独作为美国私营/审美外科口径。
3. BAAPS 2020-2025 UK audit 与 SECPRE Spain 2021 surgical-only 已接入；AICPE Italy 与 DGÄPC Germany 已完成 QA，分别作为 ISAPS 交叉核验和需求 proxy，不重复入治疗量主干；SBCP Brazil 2025 已作为州级医生 denominator 接入渠道密度明细。
4. 补 SEC/IR 的 aesthetic segment、region revenue、product-line revenue，避免用公司总收入替代医美收入。
5. 设计 provider locator / enrichment 的渠道覆盖表，先做品牌-城市-机构密度 proxy；香港 DH、台湾 MOHW、台湾医疗机构/人员 ODS 和日本 MHLW survey frame 已接入，下一批优先把日本医生专科人数、巴西/日本 provider locator、法国、瑞士、捷克、加拿大、波兰、瑞典官方机构/医师入口继续接成国家级渠道 proxy。
6. 韩国 MOHW/KHISS 和以色列协会/IMAJ 先作为 medical tourism、specialty demand 或 heat/context proxy，不与 ISAPS 治疗量合并。

ASPS 2024 已完成 procedure trend 抽取；下一步先抽 ASPS 2024 average fee / regional split，再回填 ASPS 2020、2022、2023 procedure trend。若 2021 仍无独立官方 ASPS 统计 PDF，应在 backlog 中保留 `verified_unavailable_or_no_dedicated_report` 口径，而不是强求补齐。

这样商业页的市场数据立方会从“横截面矩阵”升级成“国家-年份-赛道”的时间序列矩阵。

# Global Aesthetics Dashboard · v2

Light-only redesign sitting alongside the existing dashboard. Original `web/` is
untouched; a snapshot lives at `web_backup_20260520/` as belt-and-suspenders.

## Entry

- **Overview · http://127.0.0.1:8790/v2/index.html**

## Information architecture

| 类 | 页面 | 状态 | 价值 |
|---|---|---|---|
| 总览 | `index.html` | ✓ 已实现 | Hero + 8 KPI 卡 + 3 编辑视角 + 赛道环形图 |
| 情报视角 | `regulatory-pulse.html` | ✓ 已实现 | **新视角** · FDA/CE 时间线 + 通道分类 + Top 公司 |
| 情报视角 | `geo-deep-dive.html` | ✓ 已实现 | **新视角** · 韩国因子 + 区域 × 赛道堆叠 |
| 情报视角 | `capital-map.html` | ✓ 已实现 | **新视角** · 估值带 + 交易所 + 上市主体 |
| 情报视角 | `tracks.html` | ◎ stub | L1 × L2 矩阵 + 技术路线树 + sub-track 时序 |
| 情报视角 | `indications.html` | ◎ stub | 适应症 buckets + 产品 × 适应症矩阵 |
| 情报视角 | `technology-tree.html` | ◎ stub | classification_layer JSON 三层树 |
| 企业证据 | `companies.html` | ◎ stub | 372 公司表 + 价值链定位 + 母子结构 |
| 企业证据 | `evidence.html` | ◎ stub | 证据漏斗 + 公司证据完整度热图 + 审核队列 |
| 下钻 | `topic.html` | ◎ stub | 单赛道下钻：`?segment=ebd\|injectables\|...` |

## Design system

### Colors — Aestra 5-base extended

- **Base**: oxblood `#520E0D` · slate `#233245` · sand `#CEB59C` · bone `#E0D6CA`
- **Light paper surface**: `#F6EEDE` (page) / `#FFFCF5` (card)
- **8 pastel washes**: peach · rose · gold-soft · gold-warm · blue-ice · blue-mute · cream · khaki (one per card corner)
- **10 categorical (chart)**: EBD / Injectables / Skincare / Regen / Consum / Implants / Diagnostics / Surgical / Pharma / Services — derived from base palette, cross-family alternation
- **NO dark page backgrounds.** Dark only as in-card accent (e.g. a chip, an italic numeral).

### Type

- **Title**: Noto Serif SC ExtraLight (200)
- **Italic accent numerals**: Newsreader Italic 400
- **Body / labels / table numbers**: Inter 400 / 500 / 600

### Components in `styles.css`

`.topbar` · `.rail` · `.page-hero` · `.eyebrow-chip` · `.filter-row .filter-pill` · `.kpi-grid .kpi-cell` (with 8 wash classes) · `.editorial-row .editorial-block` · `.chart-card` · `.bar-row` · `.donut-row` · `.col-chart .col` · `.table-card table` · `.pill-tag.pill-{track}`

## Data layer

All pages load `../app-data.js` (the unchanged data snapshot from the existing
build pipeline). The KPI cards `data-bind` to `window.GLOBAL_AESTHETICS_DATA.summary[*]`.

## What's next

Phase 2 — replace the 6 stub pages with real implementations. The stub registry
in `_stub.html` already documents the planned modules for each.

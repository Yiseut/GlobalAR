import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "E:/shared/Documents/data/global_aesthetics_dashboard/outputs/globe_company_locations_20260605";
const dbPath = "E:/shared/Documents/data/global_aesthetics_dashboard/data/global_aesthetics.db";
const xlsxPath = `${outputDir}/global_aesthetics_company_globe_locations_20260605.xlsx`;
const dataPath = `${outputDir}/globe_company_locations_data.json`;

const trackOrder = [
  "EBD",
  "Injectables",
  "Skincare",
  "Regenerative",
  "Implants",
  "Consumables",
  "Diagnostics",
  "Surgical",
  "Pharma",
];

const trackDisplay = {
  EBD: "EBD / 光电",
  Injectables: "Injectables / 注射",
  Skincare: "Cosmeceutical / 功能性护肤品",
  Regenerative: "Regenerative / 再生",
  Implants: "Implants / 植入物",
  Consumables: "Consumables / 耗材",
  Diagnostics: "Diagnostics / 诊断",
  Surgical: "Surgical / 外科",
  Pharma: "Pharma / 药物",
};

function colLetter(n) {
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - m) / 26);
  }
  return s;
}

function writeMatrix(sheet, startRow, startCol, matrix) {
  if (!matrix.length || !matrix[0].length) return;
  sheet.getRangeByIndexes(startRow, startCol, matrix.length, matrix[0].length).values = matrix;
}

function setColumnWidths(sheet, widths, rowCount) {
  widths.forEach((width, idx) => {
    sheet.getRangeByIndexes(0, idx, Math.max(rowCount, 1), 1).format.columnWidthPx = width;
  });
}

await fs.mkdir(outputDir, { recursive: true });
const raw = await fs.readFile(dataPath, "utf8");
const payload = JSON.parse(raw);
const { summary, rows, track_stats: trackStats } = payload;

const workbook = Workbook.create();
const detail = workbook.worksheets.getOrAdd("企业定位清单", { renameFirstIfOnlyNewSpreadsheet: true });
detail.showGridLines = false;

const baseHeaders = [
  "company_id",
  "企业 / Company",
  "地球仪点位 / Globe Pin",
  "城市 / City",
  "国家 / Country",
  "区域 / Region",
  "纬度 / Latitude",
  "经度 / Longitude",
  "定位精度 / Geo Precision",
  "总部位置 / HQ Location",
  "主赛道 / Primary Track",
  "主赛道Key / Primary Track Key",
  "覆盖赛道数 / Track Count",
  "覆盖赛道清单 / Track List",
  "赛道Key清单 / Track Keys",
  "产品数 / Products",
  "地球仪产品数 / Globe Products",
  "品牌数 / Brands",
  "归属 / Ownership",
  "股票代码 / Stock Code",
  "交易所 / Exchange",
  "Ticker",
  "监管通道 / Regulatory Channels",
  "优先级 / Priority Rank",
  "核验状态 / Verification",
  "Review Status",
  "Source Status",
];
const trackHeaders = trackOrder.map(track => `${trackDisplay[track]} 产品数`);
const headers = [...baseHeaders, ...trackHeaders];
const matrix = [
  headers,
  ...rows.map(row => [
    row.company_id,
    row.company,
    row.pin_label,
    row.city,
    row.country,
    row.region,
    row.latitude,
    row.longitude,
    row.geo_precision,
    row.location_full,
    row.primary_track,
    row.primary_track_raw,
    row.track_count,
    row.track_list,
    row.track_list_raw,
    row.product_count,
    row.globe_product_count,
    row.brand_count,
    row.ownership,
    row.stock_code,
    row.exchange,
    row.ticker_symbol,
    row.regulatory_channels,
    row.priority_rank,
    row.verification_status,
    row.review_status,
    row.source_status,
    ...trackOrder.map(track => row[`track_${track}`] || 0),
  ]),
];

writeMatrix(detail, 0, 0, matrix);
const detailRange = detail.getRangeByIndexes(0, 0, matrix.length, headers.length);
detailRange.format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
detail.getRangeByIndexes(0, 0, 1, headers.length).format = {
  fill: "#233245",
  font: { bold: true, color: "#FFFFFF" },
  wrapText: true,
};
detail.getRangeByIndexes(1, 6, rows.length, 2).setNumberFormat("0.0000");
detail.getRangeByIndexes(1, 12, rows.length, 1).setNumberFormat("0");
detail.getRangeByIndexes(1, 15, rows.length, 3).setNumberFormat("0");
detail.getRangeByIndexes(1, baseHeaders.length, rows.length, trackHeaders.length).setNumberFormat("0");
setColumnWidths(detail, [
  140, 210, 180, 130, 140, 140, 95, 95, 105, 230, 190, 130, 105, 310, 210,
  90, 115, 85, 115, 125, 100, 95, 190, 85, 120, 110, 110,
  ...trackHeaders.map(() => 128),
], matrix.length);
detail.freezePanes.freezeRows(1);
detail.freezePanes.freezeColumns(2);
const lastCol = colLetter(headers.length);
const table = detail.tables.add(`A1:${lastCol}${matrix.length}`, true, "CompanyGlobeLocationTable");
table.style = "TableStyleMedium2";
table.showFilterButton = true;
table.showBandedColumns = false;

const stats = workbook.worksheets.add("赛道统计");
stats.showGridLines = false;
const statsHeaders = ["赛道Key / Track Key", "显示名称 / Display", "产品数 / Products", "企业数 / Companies"];
const statsMatrix = [
  statsHeaders,
  ...trackStats.map(row => [row.track_raw, row.track_display, row.product_count, row.company_count]),
];
writeMatrix(stats, 0, 0, statsMatrix);
stats.getRangeByIndexes(0, 0, 1, statsHeaders.length).format = {
  fill: "#233245",
  font: { bold: true, color: "#FFFFFF" },
};
stats.getRangeByIndexes(1, 2, trackStats.length, 2).setNumberFormat("0");
stats.getRangeByIndexes(0, 0, statsMatrix.length, statsHeaders.length).format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
setColumnWidths(stats, [140, 240, 120, 120], statsMatrix.length);
stats.freezePanes.freezeRows(1);
const statsTable = stats.tables.add(`A1:D${statsMatrix.length}`, true, "TrackStatsTable");
statsTable.style = "TableStyleMedium2";
statsTable.showFilterButton = true;

const guide = workbook.worksheets.add("字段说明");
guide.showGridLines = false;
const guideRows = [
  ["项目 / Item", "说明 / Description"],
  ["导出时间 / Exported at", summary.exported_at],
  ["数据源 / Source DB", summary.db_path],
  ["企业数 / Companies", summary.company_count],
  ["有地球仪经纬度的企业 / Companies with globe coordinates", summary.mapped_geo_count],
  ["城市级定位 / City precision", summary.city_precision_count],
  ["国家级定位 / Country precision", summary.country_precision_count],
  ["产品数口径 / Product count rule", "来自 product_master 的未排除产品行；同时保留地球仪产品数字段用于核对。"],
  ["赛道数口径 / Track count rule", "按 company_id 下 product_master.commercial_path_l1 的不同赛道计数。"],
  ["Skincare 呈现名 / Skincare display", "数据库 key 仍为 Skincare；面向客户呈现为 Cosmeceutical / 功能性护肤品。"],
  ["定位精度 / Geo precision", "city 表示页面使用城市经纬度；country 表示页面退到国家中心点。"],
  ["多赛道企业 / Multi-track companies", summary.multi_track_companies],
  ["产品总数 / Products total", summary.product_count],
  ["地球仪产品总数 / Globe products total", summary.globe_product_count],
];
writeMatrix(guide, 0, 0, guideRows);
guide.getRangeByIndexes(0, 0, 1, 2).format = {
  fill: "#233245",
  font: { bold: true, color: "#FFFFFF" },
};
guide.getRangeByIndexes(0, 0, guideRows.length, 2).format.borders = { preset: "all", style: "thin", color: "#D9E1E8" };
setColumnWidths(guide, [260, 720], guideRows.length);
guide.getRangeByIndexes(0, 1, guideRows.length, 1).format.wrapText = true;
guide.freezePanes.freezeRows(1);

const inspect = await workbook.inspect({
  kind: "table",
  range: "企业定位清单!A1:AJ8",
  include: "values",
  tableMaxRows: 8,
  tableMaxCols: 36,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});

for (const sheetName of ["企业定位清单", "赛道统计", "字段说明"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  const previewBytes = new Uint8Array(await preview.arrayBuffer());
  await fs.writeFile(`${outputDir}/preview_${sheetName}.png`, previewBytes);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(xlsxPath);

console.log(JSON.stringify({
  xlsxPath,
  summary,
  inspect: inspect.ndjson,
  errors: errors.ndjson,
}, null, 2));

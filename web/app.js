const DATA = window.GLOBAL_AESTHETICS_DATA || {};
const RAW_SEGMENTS = DATA.segments || [];
const MATERIAL_TAXONOMY = DATA.material_taxonomy_structure || {};
const $ = (id) => document.getElementById(id);
let activeTaxonomyL1Id = "";

const MATERIAL_LABELS = {
  ha: "玻尿酸 / HA",
  plla: "PLA",
  pcl: "PCL",
  caha: "CaHA",
  pn_pdrn: "PN / PDRN",
  exosome: "外泌体 / Exosomes",
  botulinum: "肉毒毒素",
  ebd: "光电设备 / EBD",
  threads: "线材 / Threads",
  mesotherapy: "中胚层 / Mesotherapy",
};

const TRACK_GROUPS = [
  {
    id: "injectables",
    name: "注射材料 / Injectables",
    note: "Filler / Skin Booster / Biostimulator",
    blockNote: "HA · PLA/PLLA · PCL · CaHA",
    insight: "以 HA 为基本盘，PLLA / PCL / CaHA 决定再生刺激与高客单升级空间。",
    color: "#DA7756",
    segments: ["ha", "plla", "pcl", "caha"],
    featured: {
      ha: ["Filler / 交联填充剂", "Skin Booster / 无交联水光", "中胚层 HA 复配液", "HA 主成分复配"],
      plla: ["注射型 PLLA", "PDLLA / 复合微球"],
      pcl: ["液态 PCL", "PCL 微球填充剂"],
      caha: ["CaHA 微球填充剂", "HA + CaHA 复合填充剂"],
    },
  },
  {
    id: "ebd",
    name: "光电设备 / EBD",
    note: "Energy-based devices",
    blockNote: "射频 · 激光/IPL · 超声/HIFU · 冷冻 · 电磁 · 等离子",
    insight: "产品量最大，竞争从设备品类扩张转向适应症、能量平台与监管证据对比。",
    color: "#4A7C8E",
    segments: ["ebd"],
    featured: {
      ebd: ["射频 / RF", "激光 / Laser / IPL", "超声 / Ultrasound / HIFU", "冷冻 / Cryolipolysis", "电磁 / EMS", "等离子 / Plasma", "磨削 / Hydradermabrasion"],
    },
  },
  {
    id: "regenerative",
    name: "再生修复 / Regenerative",
    note: "PN / PDRN / Exosome",
    blockNote: "PN/PDRN · 外泌体 · PRP/PRF · 生长因子",
    insight: "增长叙事强，但证据分层明显，需要把获批用途、原料与营销概念拆开看。",
    color: "#7BA99C",
    segments: ["pn_pdrn", "exosome"],
    featured: {
      pn_pdrn: ["PN 制剂", "PDRN 制剂", "PN/PDRN 复合制剂", "PN/PDRN 原料/API"],
      exosome: ["外泌体制剂", "PRP / PRF", "生长因子 / 细胞因子", "条件培养基 / 分泌组"],
    },
  },
  {
    id: "toxin",
    name: "肉毒毒素",
    note: "Botulinum toxin",
    blockNote: "冻干粉针 · 即用液体 · 长效/新剂型",
    insight: "准入门槛高，真正的差异来自剂型、持续时间、生产体系与地区注册路径。",
    color: "#B87333",
    segments: ["botulinum"],
    featured: {
      botulinum: ["冻干粉针", "即用液体剂型", "长效 / 新剂型"],
    },
  },
  {
    id: "threads",
    name: "线材 / Threads",
    note: "PDO / PCL / PLLA threads",
    blockNote: "PDO · PCL · PLLA · Cog/Matrix",
    insight: "供给长尾明显，应优先按材料、结构与医生端场景判断竞争强度。",
    color: "#9A8C73",
    segments: ["threads"],
    featured: {
      threads: ["PDO 线", "PCL 线", "PLLA 线", "Cog / Matrix 结构"],
    },
  },
  {
    id: "mesotherapy",
    name: "中胚层 / Mesotherapy",
    note: "Cocktail / HA solution / injector",
    blockNote: "复配注射液 · HA复配 · 生物活性成分 · 注射耗材",
    insight: "复配与设备耗材交织，最需要区分医疗器械、化妆品与临床宣称边界。",
    color: "#6E9F88",
    segments: ["mesotherapy"],
    featured: {
      mesotherapy: ["复配注射液 / Cocktail", "HA 基底复配液 / HA-based cocktail", "生物活性成分复配", "注射设备 / 针头耗材"],
    },
  },
];

const GEO_VIEWBOX = { width: 1000, height: 520 };
const GEO_REGION_COLORS = {
  Asia: "#f4b66a",
  "Asia-Pacific": "#f0c56d",
  Europe: "#78c6b3",
  "North America": "#7eb6ff",
  "South America": "#d78a6d",
  Oceania: "#caa56a",
  Africa: "#d4cf82",
  "Middle East": "#e2b35d",
  Other: "#b9aa88",
  Global: "#f0d38a",
};
const GEO_TRACK_COLORS = {
  Injectables: "#d97757",
  EBD: "#4f8db2",
  Regenerative: "#70a58e",
  Implants: "#b5915a",
  Skincare: "#9b7bc0",
  Surgical: "#b87359",
  Consumables: "#8f9a66",
  Services: "#7d8793",
  Diagnostics: "#6a9fb5",
  Pharma: "#c08a4a",
};
const GEO_COUNTRY_ALIASES = {
  US: "USA",
  "United States": "USA",
  "United States of America": "USA",
  UK: "England",
  "United Kingdom": "England",
  UAE: "United Arab Emirates",
  Korea: "South Korea",
  "Republic of Korea": "South Korea",
};
let geoMetric = "products";
let geoWorldData = null;
let geoLeafletMap = null;
let geoLeafletMarkerLayer = null;
let geoLeafletCountryLayer = null;
let geoLeafletHomeZoom = 2.25;
let geoCountryDetailMap = null;
const GEO_LEAFLET_HOME = {
  center: [18, 5],
  zoom: 2.25,
  bounds: [
    [-56, -168],
    [74, 178],
  ],
};
const GEO_COORDINATE_OVERRIDES = new Map(
  Object.entries({
    "Monaco|Monaco": { lat: 43.7384, lon: 7.4246 },
    "Nice|France": { lat: 43.7102, lon: 7.2620 },
    "Biot|France": { lat: 43.6286, lon: 7.0969 },
    "Valbonne|France": { lat: 43.6419, lon: 7.0088 },
    "Mougins|France": { lat: 43.6007, lon: 6.9954 },
    "Mandelieu-la-Napoule|France": { lat: 43.5464, lon: 6.9384 },
  }),
);
const COUNTRY_DETAIL_BBOX_OVERRIDES = new Map(
  Object.entries({
    USA: { minLon: -125.2, maxLon: -66.7, minLat: 24.0, maxLat: 49.7 },
    France: { minLon: -5.3, maxLon: 9.8, minLat: 41.1, maxLat: 51.3 },
  }),
);
const geoFeatureByCountry = new Map();
const geoFilters = {
  track: "all",
  region: "all",
  listing: "all",
  evidence: "all",
};
const geoZoom = {
  scale: 1,
  x: 0,
  y: 0,
  dragging: false,
  dragStartX: 0,
  dragStartY: 0,
  startX: 0,
  startY: 0,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function geoCoordinateKey(item) {
  return `${String(item?.city || "").trim()}|${String(item?.country || "").trim()}`;
}

function geoCoordinates(item) {
  const override = GEO_COORDINATE_OVERRIDES.get(geoCoordinateKey(item));
  const lat = Number(override?.lat ?? item?.lat);
  const lon = Number(override?.lon ?? item?.lon);
  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

function hasCjk(value) {
  return /[\u3400-\u9fff]/.test(String(value || ""));
}

function bilingualParts(value) {
  const text = String(value ?? "").trim();
  if (!text) return { zh: "", en: "" };
  if (!/[A-Za-z]/.test(text) || !hasCjk(text) || !/\s\/\s/.test(text)) return { zh: text, en: "" };
  const parts = text.split(/\s+\/\s+/).map((part) => part.trim()).filter(Boolean);
  if (parts.length < 2) return { zh: text, en: "" };
  const left = parts[0];
  const rightParts = parts.slice(1);
  const right = rightParts.join(" / ");
  const leftCjk = hasCjk(left);
  const rightCjk = rightParts.some(hasCjk);
  const leftLatin = /[A-Za-z]/.test(left);
  const rightLatin = rightParts.some((part) => /[A-Za-z]/.test(part));
  if (leftCjk && rightLatin && !rightCjk) return { zh: left, en: right };
  if (parts.length === 2 && rightCjk && leftLatin && !leftCjk && !/[A-Za-z]/.test(parts[1])) return { zh: parts[1], en: left };
  return { zh: text, en: "" };
}

function bilingualMarkup(value, className = "") {
  const parts = bilingualParts(value);
  if (!parts.en) return `<span class="bilingual ${className}"><span class="bilingual-zh">${escapeHtml(parts.zh)}</span></span>`;
  return `
    <span class="bilingual ${className}">
      <span class="bilingual-zh">${escapeHtml(parts.zh)}</span>
      <span class="bilingual-en">${escapeHtml(parts.en)}</span>
    </span>
  `;
}

function shouldAutoBilingualText(text) {
  const value = String(text || "").trim();
  if (!value.includes(" / ")) return false;
  if (bilingualParts(value).en) return true;
  return value.split(/\s*·\s*/).some((part) => Boolean(bilingualParts(part).en));
}

function bilingualSpan(parts) {
  const span = document.createElement("span");
  span.className = "bilingual auto-bilingual";
  const zh = document.createElement("span");
  zh.className = "bilingual-zh";
  zh.textContent = parts.zh;
  const en = document.createElement("span");
  en.className = "bilingual-en";
  en.textContent = parts.en;
  span.append(zh, en);
  return span;
}

function autoBilingualNode(value) {
  const text = String(value || "").trim();
  const parts = bilingualParts(text);
  if (parts.en) return bilingualSpan(parts);
  const tokens = text.split(/(\s*·\s*)/);
  const fragment = document.createDocumentFragment();
  let changed = false;
  tokens.forEach((token) => {
    const tokenParts = bilingualParts(token.trim());
    if (tokenParts.en) {
      fragment.appendChild(bilingualSpan(tokenParts));
      changed = true;
    } else {
      fragment.appendChild(document.createTextNode(token));
    }
  });
  return changed ? fragment : null;
}

function applyBilingualLayout(root = document.body) {
  if (!root) return;
  const skipTags = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "OPTION", "SELECT", "SVG", "CANVAS", "CODE", "PRE"]);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = node.parentElement;
      if (!parent || skipTags.has(parent.tagName) || parent.closest(".bilingual, .leaflet-container")) return NodeFilter.FILTER_REJECT;
      return shouldAutoBilingualText(node.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    const text = node.nodeValue || "";
    const leading = text.match(/^\s*/)?.[0] || "";
    const trailing = text.match(/\s*$/)?.[0] || "";
    const replacement = autoBilingualNode(text.trim());
    if (!replacement) return;
    node.replaceWith(document.createTextNode(leading), replacement, document.createTextNode(trailing));
  });
}

function fmt(value) {
  return Number(value || 0).toLocaleString("en-US");
}

function formatUpdatedAt(value) {
  const text = String(value || "").trim();
  if (!text) return "-";
  return text.replace("T", " ").replace(/([+-]\d{2}:?\d{2}|Z)$/, " $1");
}

function displayCountryCount(summary) {
  const total = Number(summary.countries || 0);
  const hasTaiwanRegion = (DATA.geo_companies || []).some((row) => row.country === "Taiwan")
    || (DATA.country_distribution || []).some((row) => row.name === "Taiwan");
  return hasTaiwanRegion && total > 0 ? total - 1 : total;
}

const HEATMAP_PALETTE = [
  "#e6f1fb",
  "#b5d4f4",
  "#85b7eb",
  "#5aa0de",
  "#378add",
  "#1e72c4",
  "#185fa5",
  "#0c4d8a",
  "#0c447c",
  "#042c53",
];

const HEATMAP_ZERO_COLOR = "#fbfdff";

function activeHeatPalette(maxOrCount) {
  const peak = Math.max(1, Number(maxOrCount || 1));
  const count =
    peak <= 1
      ? 4
      : peak <= 3
        ? 5
        : peak <= 6
          ? 7
          : peak <= 12
            ? 8
            : HEATMAP_PALETTE.length;
  return HEATMAP_PALETTE.slice(0, Math.max(1, Math.min(count, HEATMAP_PALETTE.length)));
}

function heatPaletteForValues(distinctValues) {
  const count = distinctValues.length;
  if (!count) return activeHeatPalette(1);
  const peak = Math.max(1, distinctValues[count - 1]);
  const size =
    count <= 1
      ? 4
      : count <= 2
        ? 5
        : count <= 3
          ? 6
          : count <= 4
            ? 7
            : count <= 6
              ? 8
              : HEATMAP_PALETTE.length;
  const cappedSize = peak <= 3 ? Math.min(size, 5) : peak <= 6 ? Math.min(size, 7) : size;
  return HEATMAP_PALETTE.slice(0, Math.max(1, Math.min(cappedSize, HEATMAP_PALETTE.length)));
}

function buildHeatScale(values = []) {
  const distinct = Array.from(
    new Set(
      (values || [])
        .map((value) => Number(value || 0))
        .filter((value) => Number.isFinite(value) && value > 0),
    ),
  ).sort((a, b) => a - b);
  const palette = heatPaletteForValues(distinct);
  const rankByValue = new Map(distinct.map((value, index) => [value, index]));
  const max = distinct[distinct.length - 1] || 1;
  const rankFor = (numeric) => {
    if (!numeric || !distinct.length) return -1;
    if (rankByValue.has(numeric)) return rankByValue.get(numeric);
    const index = distinct.findIndex((value) => numeric <= value);
    return index === -1 ? distinct.length - 1 : index;
  };
  const indexFor = (numeric) => {
    const rank = rankFor(Number(numeric || 0));
    if (rank < 0) return -1;
    if (distinct.length === 1) return Math.min(2, palette.length - 1);
    return Math.min(palette.length - 1, Math.max(0, Math.ceil((rank / (distinct.length - 1)) * (palette.length - 1))));
  };
  return {
    distinct,
    palette,
    max,
    indexFor,
    colorFor(value) {
      const index = indexFor(value);
      return index < 0 ? HEATMAP_ZERO_COLOR : palette[index];
    },
    ratioFor(value) {
      const index = indexFor(value);
      return index < 0 ? 0 : (index + 1) / palette.length;
    },
  };
}

function isHeatScale(input) {
  return Boolean(input && typeof input === "object" && Array.isArray(input.palette) && typeof input.colorFor === "function");
}

function ensureHeatScale(scaleOrMax) {
  return isHeatScale(scaleOrMax) ? scaleOrMax : buildHeatScale([Number(scaleOrMax || 1)]);
}

function heatMeta(value, scaleOrMax) {
  const numeric = Number(value || 0);
  const scale = ensureHeatScale(scaleOrMax);
  if (!numeric) return { index: -1, ratio: 0, color: HEATMAP_ZERO_COLOR, palette: scale.palette };
  const index = scale.indexFor(numeric);
  const ratio = scale.ratioFor(numeric);
  const color = scale.colorFor(numeric);
  return { index, ratio, color, palette: scale.palette };
}

function heatRatio(value, scaleOrMax) {
  return heatMeta(value, scaleOrMax).ratio;
}

function heatColor(value, scaleOrMax) {
  return heatMeta(value, scaleOrMax).color;
}

function hexLuminance(hex) {
  const value = String(hex || "").replace("#", "");
  const rgb = [0, 2, 4].map((start) => parseInt(value.slice(start, start + 2), 16) || 0);
  const [r, g, b] = rgb.map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function heatTextColor(value, scaleOrMax) {
  const color = heatColor(value, scaleOrMax);
  if (!Number(value || 0)) return "transparent";
  return hexLuminance(color) < 0.42 ? "#ffffff" : "#172033";
}

function heatCellStyle(value, scaleOrMax) {
  const ratio = heatRatio(value, scaleOrMax);
  const alpha = 0.1 + ratio * 0.5;
  const lift = 2 + Math.round(ratio * 6);
  const spread = 4 + Math.round(ratio * 8);
  return `--heat:${Math.round(ratio * 100)};--heat-bg:${heatColor(value, scaleOrMax)};--heat-fg:${heatTextColor(value, scaleOrMax)};--heat-shadow:rgba(59,138,221,${alpha.toFixed(2)});--heat-lift:${lift}px;--heat-spread:${spread}px`;
}

function heatmapLegendMarkup(scaleOrMax) {
  const palette = isHeatScale(scaleOrMax) ? scaleOrMax.palette : activeHeatPalette(scaleOrMax);
  return `
    <div class="heatmap-scale" style="--heat-steps:${palette.length}" aria-label="热力色阶">
      <span>低</span>
      ${palette.map((color) => `<i style="--scale-color:${color}"></i>`).join("")}
      <span>高</span>
    </div>
  `;
}

function matrixLabel(value) {
  const text = String(value || "").trim();
  const labels = {
    "Manufacturer IFU": "厂家 IFU",
    Portfolio: "产品组合",
    Brand: "品牌",
    "North America": "北美",
    "Asia-Pacific": "亚太",
    Europe: "欧洲",
    Global: "全球",
    Unknown: "未分类",
  };
  return labels[text] || text;
}

function formatValuation(usdM) {
  const value = Number(usdM || 0);
  if (!value) return "估值待补 / Valuation pending";
  if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}T`;
  if (value >= 1000) return `$${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}B`;
  return `$${value.toFixed(value >= 100 ? 0 : 1)}M`;
}

function valuationBand(usdM) {
  const value = Number(usdM || 0);
  if (!value) return "market cap pending";
  if (value >= 100000) return "mega cap";
  if (value >= 10000) return "large cap";
  if (value >= 2000) return "mid cap";
  if (value >= 300) return "small cap";
  return "micro cap";
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function displayName(segment) {
  return MATERIAL_LABELS[segment.code] || segment.name;
}

function visibleSegments() {
  return RAW_SEGMENTS.filter((item) => item.code !== "other" && item.products > 0);
}

function segmentByCode(code) {
  return RAW_SEGMENTS.find((item) => item.code === code && item.products > 0);
}

function subtrackSlice(segment, name) {
  return (segment?.subtrack_slices || []).find((item) => item.name === name);
}

const MATERIAL_CARD_SUBTRACK_RENAMES = {
  "Skin Booster / 水光": "Skin Booster / 无交联水光",
  "Mesotherapy HA": "中胚层 HA 复配液",
  "复合配方": "HA 主成分复配",
  "HA 复配溶液": "HA 基底复配液 / HA-based cocktail",
};

const MATERIAL_CARD_SUBTRACK_EXCLUDES = new Set([
  "身体用 PLLA 制剂",
  "身体胶原刺激",
  "线材 / 提拉",
  "PCL 线材",
  "稀释/超稀释 CaHA 用法",
]);

function materialCardSubtrackName(name) {
  const text = String(name || "").trim();
  if (!text || MATERIAL_CARD_SUBTRACK_EXCLUDES.has(text)) return "";
  return MATERIAL_CARD_SUBTRACK_RENAMES[text] || text;
}

function segmentUrl(code, subtrack = "") {
  const query = new URLSearchParams({ segment: code });
  if (subtrack) query.set("subtrack", subtrack);
  return `./topic.html?${query.toString()}`;
}

function groupTotals(group) {
  const segments = group.segments.map(segmentByCode).filter(Boolean);
  const companies = new Set();
  segments.forEach((segment) => (segment.top_companies || []).forEach((item) => companies.add(item.name)));
  return {
    products: segments.reduce((sum, segment) => sum + Number(segment.products || 0), 0),
    segments: segments.length,
    subtracks: segments.reduce((sum, segment) => sum + Number(segment.subtrack_count || 0), 0),
    companies: companies.size || segments.reduce((sum, segment) => sum + Number(segment.companies || 0), 0),
  };
}

function groupSubtrackHeatRows(group) {
  return group.segments
    .map(segmentByCode)
    .filter(Boolean)
    .flatMap((segment) => {
      const sourceRows = (segment.subtrack_slices?.length ? segment.subtrack_slices : segment.top_subtracks) || [];
      const configuredOrder = group.featured?.[segment.code] || [];
      const order = new Map(configuredOrder.map((name, index) => [name, index]));
      const aggregated = new Map();
      sourceRows.forEach((row) => {
        const name = materialCardSubtrackName(row.name);
        const value = Number(row.products ?? row.value ?? row.total ?? 0);
        if (!name || value <= 0) return;
        const current = aggregated.get(name) || { segment, name, value: 0 };
        current.value += value;
        aggregated.set(name, current);
      });
      return Array.from(aggregated.values())
        .sort((a, b) => {
          const orderA = order.has(a.name) ? order.get(a.name) : 1000;
          const orderB = order.has(b.name) ? order.get(b.name) : 1000;
          if (orderA !== orderB) return orderA - orderB;
          return b.value - a.value;
        });
    });
}

function maxValue(items) {
  return Math.max(1, ...items.map((item) => Number(item.value || 0)));
}

function percent(part, total) {
  const denominator = Number(total || 0);
  if (!denominator) return 0;
  return clamp(Math.round((Number(part || 0) / denominator) * 100), 0, 100);
}

function taxonomyL1Rows() {
  return (MATERIAL_TAXONOMY.l1 || []).filter((item) => item && Number(item.products || item.value || 0) > 0);
}

function hasMaterialTaxonomyStructure() {
  return taxonomyL1Rows().length > 0;
}

function selectedTaxonomyL1() {
  const rows = taxonomyL1Rows();
  if (!rows.length) return null;
  const query = new URLSearchParams(window.location.search);
  const requested = query.get("l1");
  if (!activeTaxonomyL1Id && requested && rows.some((item) => item.id === requested)) {
    activeTaxonomyL1Id = requested;
  }
  if (!activeTaxonomyL1Id || !rows.some((item) => item.id === activeTaxonomyL1Id)) {
    activeTaxonomyL1Id = rows[0].id;
  }
  return rows.find((item) => item.id === activeTaxonomyL1Id) || rows[0];
}

function updateTaxonomyUrl(l1Id) {
  if (!l1Id || !window.history?.replaceState) return;
  const url = new URL(window.location.href);
  url.searchParams.set("l1", l1Id);
  window.history.replaceState({}, "", url);
}

function activateTaxonomyL1(l1Id, options = {}) {
  if (!l1Id) return;
  activeTaxonomyL1Id = l1Id;
  updateTaxonomyUrl(l1Id);
  renderSegments();
  renderSegmentDeepDive();
  applyBilingualLayout($("segmentGrid"));
  applyBilingualLayout($("segmentDeepDive"));
  if (options.scroll) {
    window.requestAnimationFrame(() => scrollToHashTarget("#segmentDeepDive", "smooth"));
  }
}

function taxonomyShareLabel(value, total) {
  return `${percent(value, total)}%`;
}

function taxonomyProductTitle(item) {
  return [item.brand, item.product].filter(Boolean).join(" / ") || item.company || item.record_id || "Product";
}

function taxonomyShortText(value, limit = 150) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function taxonomyFeatureTags(item) {
  const raw = [item.feature_tags]
    .filter(Boolean)
    .join(",");
  const seen = new Set();
  return raw
    .split(/[,;，；|]/)
    .map((tag) => {
      const value = tag.trim();
      if (value === "Neurotoxin") return "肉毒毒素";
      if (value.includes("Neurotoxin") && value.includes("零复合蛋白肉毒")) return "零复合蛋白肉毒";
      return value;
    })
    .filter((tag) => {
      const key = tag.toLowerCase();
      if (!tag || seen.has(key) || key === "needs_verification") return false;
      seen.add(key);
      return true;
    })
    .slice(0, 5);
}

function taxonomySampleMarkup(samples = []) {
  const rows = samples || [];
  return (
    rows
      .map((item) => {
        const meta = [item.company, item.country, item.l3 || item.family, item.market_channel].filter(Boolean).join(" / ");
        const note = taxonomyShortText(item.differentiator || item.intro || "", 150);
        const tags = taxonomyFeatureTags(item);
        return `
          <div class="taxonomy-sample-row">
            <strong>${escapeHtml(taxonomyProductTitle(item))}</strong>
            <span>${escapeHtml(meta)}</span>
            ${note ? `<p>${escapeHtml(note)}</p>` : ""}
            ${tags.length ? `<div class="taxonomy-sample-tags">${tags.map((tag) => `<em>${escapeHtml(tag)}</em>`).join("")}</div>` : ""}
          </div>
        `;
      })
      .join("") || `<p class="empty-state small">暂无样例产品</p>`
  );
}

function taxonomyCompactName(value = "") {
  const text = String(value || "").trim();
  if (!text) return "未分类";
  const arrow = text.split(/\s*(?:→|>)\s*/).pop();
  return (arrow || text).trim();
}

function taxonomyItemL3(item) {
  return item.l3 || item.family || item.product_type_cn || "未分类";
}

function taxonomyFilteredSamples(row, activeL3 = "") {
  const rows = row?.samples || [];
  if (!activeL3) return rows;
  return rows.filter((item) => taxonomyItemL3(item) === activeL3);
}

function taxonomyCountRows(samples = [], getter, limit = 8) {
  const counts = new Map();
  samples.forEach((item) => {
    const value = getter(item);
    if (!value) return;
    counts.set(value, (counts.get(value) || 0) + 1);
  });
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => Number(b.value || 0) - Number(a.value || 0) || a.name.localeCompare(b.name, "zh-CN"))
    .slice(0, limit);
}

function taxonomyDistinctCount(samples = [], getter) {
  return new Set(samples.map(getter).filter(Boolean)).size;
}

function taxonomyL3Rows(row) {
  const explicit = (row?.top_l3 || []).filter((item) => item?.name && Number(item.value || 0) > 0);
  if (explicit.length) return explicit;
  return taxonomyCountRows(row?.samples || [], taxonomyItemL3, 12);
}

function taxonomyRankMarkup(rows = [], options = {}) {
  const items = rows.filter((item) => Number(item.value || 0) > 0).slice(0, options.limit || 8);
  const max = maxValue(items);
  const total = Number(options.total || 0) || items.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
  return (
    items
      .map((item) => {
        const width = Math.max(4, (Number(item.value || 0) / max) * 100);
        const share = percent(item.value, total);
        const label = options.compact ? taxonomyCompactName(item.name) : item.name;
        const attrs = options.tab ? ` type="button" data-taxonomy-l3-tab="${escapeHtml(item.name)}"` : "";
        const tag = options.tab ? "button" : "div";
        return `
          <${tag} class="taxonomy-rank-row${options.active === item.name ? " is-active" : ""}"${attrs} title="${escapeHtml(item.name)} / ${fmt(item.value)}">
            <span>${escapeHtml(label)}</span>
            <i><b style="width:${width}%"></b></i>
            <strong>${fmt(item.value)}<em>${share}%</em></strong>
          </${tag}>
        `;
      })
      .join("") || `<p class="empty-state small">${escapeHtml(options.empty || "暂无结构信号")}</p>`
  );
}

function taxonomyTagCloudRows(samples = [], limit = 14) {
  const counts = new Map();
  samples.forEach((item) => {
    taxonomyFeatureTags(item).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return Array.from(counts.entries())
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => Number(b.value || 0) - Number(a.value || 0) || a.name.localeCompare(b.name, "zh-CN"))
    .slice(0, limit);
}

function taxonomyTagKey(value = "") {
  return String(value || "").trim().toLowerCase();
}

function taxonomySamplesByTag(samples = [], tag = "") {
  const key = taxonomyTagKey(tag);
  if (!key) return samples;
  return samples.filter((item) => taxonomyFeatureTags(item).some((value) => taxonomyTagKey(value) === key));
}

function taxonomyTagCloudMarkup(rows = [], activeTag = "") {
  const activeKey = taxonomyTagKey(activeTag);
  return (
    rows
      .map(
        (item) => `
          <button class="taxonomy-tag-button${taxonomyTagKey(item.name) === activeKey ? " is-active" : ""}" type="button" data-taxonomy-tag-filter="${escapeHtml(item.name)}" title="查看关联产品：${escapeHtml(item.name)}">
            <span>${escapeHtml(item.name)}</span><b>${fmt(item.value)}</b>
          </button>
        `,
      )
      .join("") || `<p class="empty-state small">暂无关键词信号</p>`
  );
}

function taxonomyOverlayStats(row, samples, activeL3 = "") {
  if (!activeL3) {
    return {
      products: Number(row.products || samples.length || 0),
      companies: Number(row.companies || taxonomyDistinctCount(samples, (item) => item.company)),
      brands: Number(row.brands || taxonomyDistinctCount(samples, (item) => item.brand)),
      countries: Number(row.countries || taxonomyDistinctCount(samples, (item) => item.country)),
    };
  }
  return {
    products: samples.length,
    companies: taxonomyDistinctCount(samples, (item) => item.company),
    brands: taxonomyDistinctCount(samples, (item) => item.brand),
    countries: taxonomyDistinctCount(samples, (item) => item.country),
  };
}

function taxonomyOverlayInner(parent, row, activeL3 = "", activeTag = "") {
  const samples = taxonomyFilteredSamples(row, activeL3);
  const indexSamples = taxonomySamplesByTag(samples, activeTag);
  const allSamples = row.samples || [];
  const l3Rows = taxonomyL3Rows(row);
  const stats = taxonomyOverlayStats(row, samples, activeL3);
  const companies = taxonomyCountRows(samples, (item) => item.company, 8);
  const countries = taxonomyCountRows(samples, (item) => item.country, 8);
  const brands = taxonomyCountRows(samples, (item) => item.brand, 8);
  const tags = taxonomyTagCloudRows(samples);
  const topL3 = activeL3 ? { name: activeL3, value: samples.length } : l3Rows[0];
  const topCompany = companies[0];
  const topCountry = countries[0];
  const tabRows = l3Rows.slice(0, 14);
  const activeLabel = activeL3 ? taxonomyCompactName(activeL3) : "全部子类别";
  const isSliceView = Boolean(activeL3);
  const indexLabel = activeTag ? `标签：${activeTag}` : activeLabel;
  return `
    <div class="taxonomy-overlay-shell" style="--segment:${parent.color || "var(--brand)"}" data-active-l3="${escapeHtml(activeL3)}" data-active-tag="${escapeHtml(activeTag)}">
      ${
        isSliceView
          ? ""
          : `
            <div class="taxonomy-overlay-summary">
              <span><b>${fmt(stats.products)}</b><em>产品索引</em></span>
              <span><b>${fmt(stats.companies)}</b><em>企业</em></span>
              <span><b>${fmt(stats.brands)}</b><em>品牌</em></span>
              <span><b>${fmt(stats.countries)}</b><em>国家</em></span>
            </div>
            <div class="taxonomy-l3-tabs" role="tablist" aria-label="三级子类切片">
              <button class="is-active" type="button" data-taxonomy-l3-tab="">
                <span>全貌</span><b>${fmt(row.products || allSamples.length)}</b>
              </button>
              ${tabRows
                .map(
                  (item) => `
                    <button type="button" data-taxonomy-l3-tab="${escapeHtml(item.name)}">
                      <span>${escapeHtml(taxonomyCompactName(item.name))}</span><b>${fmt(item.value)}</b>
                    </button>
                  `,
                )
                .join("")}
            </div>
            <div class="taxonomy-overlay-readout">
              <article>
                <span>当前切片</span>
                <strong>${escapeHtml(activeLabel)}</strong>
                <em>二级赛道全貌</em>
              </article>
              <article>
                <span>主导子类</span>
                <strong>${escapeHtml(topL3 ? taxonomyCompactName(topL3.name) : "待补")}</strong>
                <em>${topL3 ? `${fmt(topL3.value)} 条产品索引` : "暂无"}</em>
              </article>
              <article>
                <span>代表企业</span>
                <strong>${escapeHtml(topCompany?.name || "待补")}</strong>
                <em>${topCompany ? `${fmt(topCompany.value)} 条产品索引` : "暂无"}</em>
              </article>
              <article>
                <span>主要国家</span>
                <strong>${escapeHtml(topCountry?.name || "待补")}</strong>
                <em>${topCountry ? `${fmt(topCountry.value)} 条产品索引` : "暂无"}</em>
              </article>
            </div>
          `
      }
      <div class="taxonomy-overlay-dashboard">
        ${
          isSliceView
            ? ""
            : `
              <section class="taxonomy-analysis-panel is-wide">
                <div class="taxonomy-panel-head">
                  <h3>三级结构</h3>
                  <span>材料 / 机制 / 形态切片</span>
                </div>
                <div class="taxonomy-rank-list">${taxonomyRankMarkup(l3Rows, { total: row.products || allSamples.length, compact: true, tab: true, active: activeL3, limit: 12 })}</div>
              </section>
            `
        }
        <section class="taxonomy-analysis-panel">
          <div class="taxonomy-panel-head">
            <h3>厂家分布</h3>
            <span>${escapeHtml(activeLabel)}</span>
          </div>
          <div class="taxonomy-rank-list">${taxonomyRankMarkup(companies, { total: stats.products, empty: "当前切片暂无厂家信号" })}</div>
        </section>
        <section class="taxonomy-analysis-panel">
          <div class="taxonomy-panel-head">
            <h3>国家分布</h3>
            <span>${escapeHtml(activeLabel)}</span>
          </div>
          <div class="taxonomy-rank-list">${taxonomyRankMarkup(countries, { total: stats.products, empty: "当前切片暂无国家信号" })}</div>
        </section>
        <section class="taxonomy-analysis-panel">
          <div class="taxonomy-panel-head">
            <h3>品牌分布</h3>
            <span>${escapeHtml(activeLabel)}</span>
          </div>
          <div class="taxonomy-rank-list">${taxonomyRankMarkup(brands, { total: stats.products, empty: "当前切片暂无品牌信号" })}</div>
        </section>
        <section class="taxonomy-analysis-panel">
          <div class="taxonomy-panel-head">
            <h3>特征标签</h3>
            <span>${escapeHtml(activeLabel)}</span>
          </div>
          <div class="taxonomy-chip-cloud taxonomy-signal-cloud">${taxonomyTagCloudMarkup(tags, activeTag)}</div>
        </section>
      </div>
      <details class="taxonomy-index-drawer" ${activeTag ? "open" : ""}>
        <summary>
          <span>产品索引</span>
        <b>${escapeHtml(indexLabel)} · ${fmt(indexSamples.length)} 条</b>
      </summary>
      ${
        activeTag
          ? `
            <div class="taxonomy-index-filter">
              <span>已关联标签 <b>${escapeHtml(activeTag)}</b></span>
              <button type="button" data-taxonomy-tag-filter="">显示全部</button>
            </div>
          `
          : ""
      }
      <div class="taxonomy-sample-list taxonomy-index-list">${taxonomySampleMarkup(indexSamples)}</div>
    </details>
    </div>
  `;
}

function wireTaxonomyOverlay(parent, row) {
  const body = $("resultBody");
  const shell = body?.querySelector(".taxonomy-overlay-shell");
  if (!shell) return;
  shell.addEventListener("click", (event) => {
    const tag = event.target.closest("[data-taxonomy-tag-filter]");
    if (tag) {
      event.preventDefault();
      event.stopPropagation();
      const activeL3 = shell.dataset.activeL3 || "";
      const nextTag = tag.dataset.taxonomyTagFilter || "";
      shell.outerHTML = taxonomyOverlayInner(parent, row, activeL3, nextTag);
      const nextShell = body.querySelector(".taxonomy-overlay-shell");
      if (nextShell) {
        applyBilingualLayout(nextShell);
        wireTaxonomyOverlay(parent, row);
        if (nextTag) nextShell.querySelector(".taxonomy-index-drawer")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      return;
    }
    const tab = event.target.closest("[data-taxonomy-l3-tab]");
    if (!tab) return;
    const nextL3 = tab.dataset.taxonomyL3Tab || "";
    shell.outerHTML = taxonomyOverlayInner(parent, row, nextL3);
    const nextShell = body.querySelector(".taxonomy-overlay-shell");
    if (nextShell) {
      applyBilingualLayout(nextShell);
      wireTaxonomyOverlay(parent, row);
    }
  });
}

function openTaxonomyL2Overlay(l1Id, l2Id, activeL3 = "") {
  const parent = taxonomyL1Rows().find((item) => item.id === l1Id);
  const row = (parent?.l2 || []).find((item) => item.id === l2Id);
  if (!parent || !row) return;
  const title = [parent.name, row.name, activeL3 ? taxonomyCompactName(activeL3) : ""].filter(Boolean).join(" / ");
  openOverlay(title, taxonomyOverlayInner(parent, row, activeL3));
  wireTaxonomyOverlay(parent, row);
}

function firstMetric(rows) {
  return (rows || []).filter(Boolean).sort((a, b) => Number(b.value || b.products || b.total || 0) - Number(a.value || a.products || a.total || 0))[0];
}

function renderBars(id, items, options = {}) {
  const node = $(id);
  if (!node) return;
  const max = maxValue(items || []);
  const color = options.color || "var(--brand)";
  node.innerHTML = (items || [])
    .slice(0, options.limit || 10)
    .map((item) => {
      const width = Math.max(3, (Number(item.value || 0) / max) * 100);
      const barColor = item.color || color;
      return `
        <div class="bar-row" title="${escapeHtml(zhLabel(item.name))} ${fmt(item.value)}">
          <span>${escapeHtml(zhLabel(item.name))}</span>
          <div class="bar-track"><i class="bar-fill" style="--w:${width}%;--bar:${barColor}"></i></div>
          <span class="bar-value">${fmt(item.value)}</span>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无数据 / No data</p>`;
}

const REGION_ZH_NAMES = {
  Europe: "欧洲",
  "Asia-Pacific": "亚太",
  "North America": "北美",
  "Middle East": "中东",
  "Latin America": "拉美",
  Africa: "非洲",
  Oceania: "大洋洲",
  Other: "其他",
  Unknown: "未分类",
};

function orderedRegionRows(items) {
  return (items || [])
    .filter((item) => item && Number(item.value || 0) > 0)
    .slice()
    .sort((a, b) => {
      const aOther = /^(other|unknown|unclassified)$/i.test(String(a.name || ""));
      const bOther = /^(other|unknown|unclassified)$/i.test(String(b.name || ""));
      if (aOther !== bOther) return aOther ? 1 : -1;
      return Number(b.value || 0) - Number(a.value || 0);
    });
}

function renderRegionFunnelChart(id, items, options = {}) {
  const node = $(id);
  if (!node) return;
  const rows = orderedRegionRows(items).slice(0, options.limit || 8);
  const max = maxValue(rows);
  node.classList.remove("bar-list", "compact");
  node.classList.add("region-funnel");
  node.innerHTML = rows
    .map((item) => {
      const value = Number(item.value || 0);
      const width = clamp((value / max) * 100, 14, 100);
      const name = geoUiLabel(item.name);
      const zh = REGION_ZH_NAMES[name] || zhLabel(name);
      const label = zh && zh !== name
        ? `<span>${escapeHtml(zh)}<em>${escapeHtml(name)}</em></span>`
        : `<span>${escapeHtml(name)}</span>`;
      return `
        <div class="region-funnel-row" title="${escapeHtml(name)} ${fmt(value)}">
          <div class="region-funnel-label">${label}</div>
          <div class="region-funnel-bar"><i style="--w:${width}%"></i></div>
          <strong>${fmt(value)}</strong>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无数据 / No data</p>`;
}

function renderCountryRankingBars(id, items, options = {}) {
  const node = $(id);
  if (!node) return;
  const rows = (items || []).filter((item) => item && Number(item.value || 0) > 0).slice(0, options.limit || 8);
  const max = maxValue(rows);
  node.classList.remove("bar-list", "compact");
  node.classList.add("country-rank-bars");
  node.innerHTML = rows
    .map((item) => {
      const value = Number(item.value || 0);
      const width = clamp((value / max) * 100, 5, 100);
      const name = geoUiLabel(item.name);
      return `
        <div class="country-rank-row" title="${escapeHtml(name)} ${fmt(value)}">
          <span>${escapeHtml(name)}</span>
          <div class="country-rank-track"><i style="--w:${width}%"></i></div>
          <strong>${fmt(value)}</strong>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">No data</p>`;
}

function blueprintItems() {
  const summary = DATA.summary || {};
  const hierarchy = DATA.product_hierarchy?.summary || {};
  const geo = DATA.geo_summary || {};
  const officialIndications = DATA.official_indication_analysis || {};
  const base = DATA.analysis_blueprint || [];
  const additions = [
    { name: "产品家族", value: hierarchy.families || summary.product_families, unit: "族" },
    { name: "官方证据", value: summary.company_official_source_evidence, unit: "条" },
    { name: "官方适应症", value: officialIndications.rows || summary.official_indication_rows, unit: "条" },
    { name: "MDR/CE 路径", value: summary.mdr_ce_search_plan, unit: "条" },
    { name: "城市点位", value: geo.unique_geo_points || (DATA.geo_points || []).length, unit: "点" },
    { name: "上市主体", value: summary.public_companies, unit: "家" },
  ];
  const byName = new Map();
  [...base, ...additions].forEach((item) => {
    if (Number(item.value || 0) > 0 && !byName.has(item.name)) byName.set(item.name, item);
  });
  return Array.from(byName.values()).slice(0, 12);
}

function renderBlueprint() {
  const node = $("analysisBlueprint");
  if (!node) return;
  node.innerHTML = blueprintItems()
    .map((item, index) => {
      const palette = ["var(--brand)", "var(--c-gold)", "var(--c-ocean)", "var(--c-sage)", "var(--c-plum)", "var(--c-clay)"];
      const color = palette[index % palette.length];
      const score = Math.max(10, Math.min(100, Number(item.value || 0)));
      return `
        <article class="lens-card" style="--lens:${color};--score:${score}%">
          <span>${escapeHtml(item.name)}</span>
          <strong>${fmt(item.value)}<em>${escapeHtml(item.unit || "")}</em></strong>
          <i class="lens-meter"><b></b></i>
        </article>
      `;
    })
    .join("") || `<p class="empty-state">暂无数据 / No data</p>`;
}

function completionRows() {
  const summary = DATA.summary || {};
  const hierarchy = DATA.product_hierarchy?.summary || {};
  const workbench = DATA.verification_workbench || {};
  const background = workbench.company_background || {};
  const mdr = workbench.mdr_ce_plan || {};
  const promotion = workbench.evidence_promotion || {};
  const registration = DATA.registration_evidence || {};
  const officialPlan = summary.company_official_source_plan || background.official_source_plan_rows || 0;
  const officialEvidence = summary.company_official_source_evidence || background.official_source_evidence_rows || 0;
  const mdrCandidates = summary.mdr_ce_evidence_candidates || mdr.candidate_rows || 0;
  const qualityIssues = Number(summary.data_quality_high_issues || 0);
  return [
    {
      title: "产品基础盘",
      status: "已覆盖",
      value: fmt(summary.product_master || summary.products),
      unit: "条产品",
      progress: 100,
      note: `${fmt(summary.company_master || summary.companies)} 家公司，${fmt(hierarchy.families || summary.product_families)} 个产品家族`,
    },
    {
      title: "官方来源",
      status: "已收录",
      value: fmt(officialPlan),
      unit: "条来源",
      progress: 100,
      note: `官网、年报、交易所与政策源：${fmt(officialEvidence)} 条`,
    },
    {
      title: "FDA 证据",
      status: "美国市场",
      value: fmt((registration.official_api_rows || 0) + (promotion.fda_rows || 0)),
      unit: "条记录",
      progress: percent(registration.official_api_rows || summary.registration_evidence, summary.product_master || summary.products),
      note: "美国 FDA / openFDA 公开记录，用于观察准入节奏",
    },
    {
      title: "MDR / CE",
      status: "欧洲路径",
      value: fmt(promotion.mdr_ce_rows || 0),
      unit: "条已核记录",
      progress: 100,
      note: `线索池 ${fmt(mdrCandidates)} 条已按规则归档；已确认 ${fmt(promotion.registration_rows_promoted || 0)} 条`,
    },
    {
      title: "上市主体",
      status: "可展示",
      value: fmt(summary.market_snapshot),
      unit: "个快照",
      progress: 100,
      note: `${fmt(summary.public_companies)} 家上市相关主体`,
    },
    {
      title: "数据质量",
      status: qualityIssues ? "待复核" : "清洁",
      value: fmt(qualityIssues),
      unit: "高风险问题",
      progress: qualityIssues ? 35 : 100,
      note: `质量问题 ${fmt(summary.data_quality_issues)} 条，高风险 ${fmt(summary.data_quality_high_issues)} 条`,
    },
  ];
}

function renderSourceCompletionPanel() {
  const node = $("sourceCompletionPanel");
  if (!node) return;
  const rows = completionRows();
  node.innerHTML = `
    <div class="completion-head">
      <div>
        <span>数据状态</span>
        <h3>核心赛道、区域、企业与监管证据已进入可读视图</h3>
      </div>
      <em>${escapeHtml(DATA.generated_at || "")}</em>
    </div>
    <div class="completion-grid">
      ${rows
        .map(
          (item) => `
            <article class="completion-card ${item.progress >= 100 ? "is-complete" : "is-running"}" style="--progress:${item.progress}%">
              <div class="completion-top">
                <span>${escapeHtml(item.title)}</span>
                <b>${escapeHtml(item.status)}</b>
              </div>
              <strong>${escapeHtml(item.value)}<em>${escapeHtml(item.unit)}</em></strong>
              <i class="completion-meter"><b></b></i>
              <p>${escapeHtml(item.note)}</p>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function currentEvidenceFunnel() {
  const summary = DATA.summary || {};
  const registration = DATA.registration_evidence || {};
  const mdr = DATA.verification_workbench?.mdr_ce_plan || {};
  const promotion = DATA.verification_workbench?.evidence_promotion || {};
  const officialIndications = DATA.official_indication_analysis || {};
  const products = summary.product_master || summary.products || 0;
  const fdaRows = registration.official_api_rows || summary.registration_evidence || 0;
  const mdrCandidates = summary.mdr_ce_evidence_candidates || mdr.candidate_rows || 0;
  const mdrReviewReady = mdr.review_ready || 0;
  return [
    { name: "产品基础盘", value: products, note: "可按材料、公司、品牌、区域继续下钻" },
    { name: "已确认产品事实", value: promotion.product_master_promoted || summary.evidence_promoted_product_master || 0, note: "来自官方或监管来源的确认信息" },
    { name: "官方适应症", value: officialIndications.rows || summary.official_indication_rows || 0, note: "按产品、国家、监管机构与获批内容记录" },
    { name: "FDA / openFDA", value: fdaRows, note: "美国公开监管记录" },
    { name: "MDR / CE 待人工核验", value: mdrReviewReady, note: `${fmt(mdrCandidates)} 条候选池已按政策归档，不再追逐公开证书号` },
    { name: "MDR / CE 已确认", value: promotion.mdr_ce_rows || mdr.promoted_rows || 0, note: "可作为监管分析证据" },
    { name: "NMPA 独立项目", value: 0, note: "中国区由独立仪表盘承接" },
  ];
}

function currentRegulatoryMix() {
  const summary = DATA.summary || {};
  const registration = DATA.registration_evidence || {};
  const mdr = DATA.verification_workbench?.mdr_ce_plan || {};
  const promotion = DATA.verification_workbench?.evidence_promotion || {};
  return [
    { name: "FDA / openFDA 已确认", value: registration.official_api_rows || summary.registration_evidence || 0 },
    { name: "FDA 线索", value: registration.seed_rows || 0 },
    { name: "MDR / CE 待人工核验", value: mdr.review_ready || 0 },
    { name: "MDR / CE 已确认", value: promotion.mdr_ce_rows || mdr.promoted_rows || 0 },
    { name: "官方适应症", value: DATA.official_indication_analysis?.rows || summary.official_indication_rows || 0 },
    { name: "MDSAP 质量体系", value: 0 },
    { name: "NMPA 独立项目", value: 0 },
  ];
}

function renderIndicationTiles(rows, heatScale, limit = 8) {
  const items = (rows || []).slice(0, limit);
  return (
    items
      .map((item) => {
        const label = `${item.name} / ${fmt(item.value)}`;
        return `
          <div class="deep-indication-tile" style="${heatCellStyle(item.value, heatScale)}" title="${escapeHtml(label)}">
            <b>${escapeHtml(item.name)}</b>
            <strong>${fmt(item.value)}</strong>
          </div>
        `;
      })
      .join("") || `<p class="empty-state small">暂无适应症信号 / No indication signals</p>`
  );
}

function renderSegmentDeepDive() {
  const node = $("segmentDeepDive");
  if (!node) return;
  if (hasMaterialTaxonomyStructure()) {
    const selected = selectedTaxonomyL1();
    if (!selected) return;
    const l2Rows = (selected.l2 || []).filter((item) => Number(item.products || 0) > 0);
    const total = Number(selected.products || 0) || l2Rows.reduce((sum, item) => sum + Number(item.products || 0), 0) || 1;
    const heatScale = buildHeatScale(l2Rows.map((item) => item.products));
    const max = maxValue(l2Rows.map((item) => ({ value: item.products })));
    node.innerHTML = `
      <div class="taxonomy-deep-head" style="--segment:${selected.color || "var(--brand)"}">
        <div class="deep-head">
          <div>
            <span>一级赛道</span>
            <h3>${escapeHtml(selected.name)}</h3>
          </div>
          <p>${fmt(selected.products)} 条产品线 · ${fmt(selected.l2_count)} 个二级类目 · ${fmt(selected.companies)} 家企业 · ${fmt(selected.countries)} 个国家/地区</p>
        </div>
        <div class="taxonomy-summary-strip">
          <span><b>${taxonomyShareLabel(selected.products, MATERIAL_TAXONOMY.total_products)}</b><em>全库占比</em></span>
          <span><b>${fmt(selected.brands)}</b><em>品牌</em></span>
          <span><b>${fmt(selected.top_regions?.length || 0)}</b><em>区域信号</em></span>
        </div>
      </div>
      <div class="taxonomy-l2-layout">
        <div class="taxonomy-l2-bars">
          ${l2Rows
            .map((row) => {
              const width = Math.max(4, (Number(row.products || 0) / max) * 100);
              return `
                <button class="taxonomy-l2-bar" type="button" data-taxonomy-l2-open="${escapeHtml(row.id)}" data-taxonomy-l1-open="${escapeHtml(selected.id)}" title="${escapeHtml(`${row.name} / ${fmt(row.products)}`)}">
                  <span>${escapeHtml(row.name)}</span>
                  <i><b style="width:${width}%"></b></i>
                  <strong>${fmt(row.products)}</strong>
                </button>
              `;
            })
            .join("")}
        </div>
        <div class="taxonomy-l2-grid">
          ${l2Rows
            .slice(0, 12)
            .map((row) => {
              const share = Math.round(Number(row.share_of_l1 || 0) * 100);
              const l3Tags = (row.top_l3 || []).slice(0, 4);
              return `
                <article class="taxonomy-l2-card" role="button" tabindex="0" data-taxonomy-l2-open="${escapeHtml(row.id)}" data-taxonomy-l1-open="${escapeHtml(selected.id)}" style="${heatCellStyle(row.products, heatScale)}">
                  <div class="taxonomy-l2-card-title">
                    <strong>${escapeHtml(row.name)}</strong>
                    <span>${share}%</span>
                  </div>
                  <div class="taxonomy-l2-metrics">
                    <span><b>${fmt(row.products)}</b><em>产品线</em></span>
                    <span><b>${fmt(row.companies)}</b><em>企业</em></span>
                    <span><b>${fmt(row.countries)}</b><em>国家</em></span>
                  </div>
                  <div class="taxonomy-chip-cloud">
                    ${
                      l3Tags.length
                        ? l3Tags
                            .map(
                              (item) => `
                                <button class="taxonomy-l3-chip" type="button" data-taxonomy-l3-open="${escapeHtml(item.name)}" data-taxonomy-l2-open="${escapeHtml(row.id)}" data-taxonomy-l1-open="${escapeHtml(selected.id)}">
                                  <span>${escapeHtml(taxonomyCompactName(item.name))}</span><b>${fmt(item.value)}</b>
                                </button>
                              `,
                            )
                            .join("")
                        : `<span>三级待补<b>0</b></span>`
                    }
                  </div>
                </article>
              `;
            })
            .join("")}
        </div>
      </div>
    `;
    node.querySelectorAll("[data-taxonomy-l3-open]").forEach((element) => {
      element.addEventListener("click", (event) => {
        event.stopImmediatePropagation();
        event.stopPropagation();
        openTaxonomyL2Overlay(element.dataset.taxonomyL1Open, element.dataset.taxonomyL2Open, element.dataset.taxonomyL3Open);
      });
    });
    node.querySelectorAll("[data-taxonomy-l2-open]:not([data-taxonomy-l3-open])").forEach((element) => {
      element.addEventListener("click", () => openTaxonomyL2Overlay(element.dataset.taxonomyL1Open, element.dataset.taxonomyL2Open));
      element.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        openTaxonomyL2Overlay(element.dataset.taxonomyL1Open, element.dataset.taxonomyL2Open);
      });
    });
    return;
  }
  const segments = visibleSegments().sort((a, b) => Number(b.products || 0) - Number(a.products || 0));
  const totalProducts = segments.reduce((sum, item) => sum + Number(item.products || 0), 0) || 1;
  const indicationHeatScale = buildHeatScale(segments.flatMap((segment) => (segment.top_indications || []).map((item) => item.value)));
  node.innerHTML = `
    <div class="deep-track-grid">
      ${segments
        .map((segment) => {
          const share = Math.round((Number(segment.products || 0) / totalProducts) * 100);
          return `
            <article class="deep-track-card" style="--segment:${segment.color}">
              <div class="deep-track-title">
                <a href="${segmentUrl(segment.code)}">${escapeHtml(displayName(segment))}</a>
                <span>${share}%</span>
              </div>
              <p>${escapeHtml(segment.subtitle || "")}</p>
              <div class="deep-indication-panel">
                <h4>${bilingualMarkup("适应症分布 / Indication Distribution")}</h4>
                <div class="deep-indication-grid">
                  ${renderIndicationTiles(segment.top_indications, indicationHeatScale, 8)}
                </div>
              </div>
            </article>
          `;
        })
        .join("")}
    </div>
  `;
}

function strategicCards() {
  const summary = DATA.summary || {};
  const hierarchy = DATA.product_hierarchy?.summary || {};
  const topSegment = firstMetric(visibleSegments().map((item) => ({ ...item, value: item.products })));
  const topSubtrack = firstMetric(DATA.subtrack_distribution || []);
  const topIndication = firstMetric(DATA.indication_distribution || []);
  const officialIndication = firstMetric(DATA.official_indication_analysis?.top_buckets || []);
  const topCountry = firstMetric(DATA.country_distribution || []);
  const topRegion = firstMetric(DATA.region_distribution || []);
  const topCompany = firstMetric((DATA.company_matrix || []).map((item) => ({ name: item.company, value: item.total })));
  const regionTotal = (DATA.region_distribution || []).reduce((sum, item) => sum + Number(item.value || 0), 0);
  const countryTotal = (DATA.country_distribution || []).reduce((sum, item) => sum + Number(item.value || 0), 0);
  const topSegmentShare = topSegment ? percent(topSegment.value, summary.products) : 0;
  const topCountryShare = topCountry ? percent(topCountry.value, countryTotal) : 0;
  const topRegionShare = topRegion ? percent(topRegion.value, regionTotal) : 0;
  const publicLead = (DATA.public_companies || [])[0];
  return [
    {
      title: "赛道集中度",
      value: topSegment ? `${displayName(topSegment)} · ${topSegmentShare}%` : "-",
      note: topSubtrack ? `最大二级子赛道：${topSubtrack.name} · ${fmt(topSubtrack.value)} 条产品线` : "等待子赛道数据",
      tags: [`${fmt(summary.subtrack_signals)} 条子赛道信号`, `${fmt(hierarchy.brands_with_multiple_families || summary.brands_with_multiple_families)} 个多产品家族品牌`],
    },
    {
      title: "区域能力密度",
      value: topCountry ? `${zhLabel(topCountry.name)} · ${topCountryShare}%` : "-",
      note: topRegion ? `领先区域：${zhLabel(topRegion.name)} · ${topRegionShare}%` : "等待区域数据",
      tags: [`${fmt(summary.countries)} 个国家`, `${fmt(summary.mapped_companies || summary.companies)} 家已定位企业`],
    },
    {
      title: "企业产品宽度",
      value: topCompany ? `${topCompany.name} · ${fmt(topCompany.value)} 条` : "-",
      note: publicLead ? `上市主体样本包括 ${publicLead.company}、${publicLead.stock || "代码待补"}` : "按企业产品线宽度观察平台型、收购型和专科型玩家",
      tags: [`${fmt(summary.public_companies)} 家上市相关主体`, `${fmt(summary.company_capital_structure)} 条资本结构`],
    },
    {
      title: "适应症宽度",
      value: officialIndication ? `${officialIndication.name} · ${fmt(officialIndication.value)}` : topIndication ? `${topIndication.name} · ${fmt(topIndication.value)}` : "-",
      note: officialIndication ? "优先读取官方获批适应症" : "等待官方适应症扩展",
      tags: [`${fmt(DATA.official_indication_analysis?.rows || summary.official_indication_rows)} 条官方适应症`, `${fmt(summary.registration_evidence)} 条注册证据`],
    },
  ];
}

function renderStrategicAngles() {
  const node = $("strategicAngles");
  if (!node) return;
  node.innerHTML = `
    <div class="strategic-head">
      <div>
        <span>分析视角</span>
        <h3>从产品、区域、企业、适应症四条线看竞争格局</h3>
      </div>
    </div>
    <div class="strategic-grid">
      ${strategicCards()
        .map(
          (card) => `
            <article class="strategic-card">
              <span>${escapeHtml(card.title)}</span>
              <strong>${escapeHtml(card.value)}</strong>
              <p>${escapeHtml(card.note)}</p>
              <div class="strategic-tags">
                ${card.tags.map((tag) => `<em>${escapeHtml(tag)}</em>`).join("")}
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderFunnel(id, items, color) {
  const node = $(id);
  if (!node) return;
  const rows = items || [];
  const max = maxValue(rows);
  node.innerHTML = rows
    .map((item, index) => {
      const width = Math.max(4, (Number(item.value || 0) / max) * 100);
      return `
        <div class="funnel-row" style="--funnel:${color};--w:${width}%">
          <span class="funnel-index">${index + 1}</span>
          <div class="funnel-copy">
            <strong>${escapeHtml(item.name)}</strong>
            <em>${escapeHtml(zhEvidenceNote(item.note))}</em>
          </div>
          <b>${fmt(item.value)}</b>
          <i></i>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无数据 / No data</p>`;
}

function renderTimeline(id, rows, color) {
  const node = $(id);
  if (!node) return;
  const items = rows || [];
  const max = Math.max(1, ...items.map((item) => Number(item.total || 0)));
  node.innerHTML = items
    .map((item) => {
      const total = Number(item.total || 0);
      const width = Math.max(4, (total / max) * 100);
      const fda = total ? (Number(item.fda || 0) / total) * 100 : 0;
      const ce = total ? (Number(item.ce || 0) / total) * 100 : 0;
      const nmpa = total ? (Number(item.nmpa || 0) / total) * 100 : 0;
      const launch = Math.max(0, 100 - fda - ce - nmpa);
      return `
        <div class="timeline-row" title="${escapeHtml(item.year)} ${fmt(total)}">
          <span>${escapeHtml(item.year)}</span>
          <div class="timeline-track" style="--w:${width}%;--topic:${color}">
            <i class="timeline-total"></i>
            <b style="--s:${fda}%;--c:${color}"></b>
            <b style="--s:${ce}%;--c:var(--c-gold)"></b>
            <b style="--s:${nmpa}%;--c:var(--c-sage)"></b>
            <b style="--s:${launch}%;--c:var(--c-ocean)"></b>
          </div>
          <strong>${fmt(total)}</strong>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无年份线索</p>`;
}

function renderHeatmap(id, heatmap, color = "var(--brand)", rowLabel = "信号") {
  const node = $(id);
  if (!node) return;
  const columns = heatmap?.columns || [];
  const rows = heatmap?.rows || [];
  const heatScale = buildHeatScale(rows.flatMap((row) => columns.map((column) => row.values?.[column] || 0)));
  const head = `
    <div class="matrix-head nature-heatmap-head">
      <div class="matrix-name">${escapeHtml(matrixLabel(rowLabel))}</div>
      ${columns.map((column) => `<div class="matrix-label">${escapeHtml(matrixLabel(column))}</div>`).join("")}
    </div>
  `;
  const body = rows
    .map((row) => {
      const visibleTotal = columns.reduce((sum, column) => sum + Number(row.values?.[column] || 0), 0);
      const rowTotal = visibleTotal || Number(row.total || 0);
      const cells = columns
        .map((column) => {
          const value = row.values?.[column] || 0;
          const label = `${row.name} / ${column} / ${fmt(value)}`;
          return `
            <div class="matrix-cell">
              <span class="heat-cell heatmap-tile ${value ? "has-value" : "is-zero"}" style="${heatCellStyle(value, heatScale)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
                ${value ? fmt(value) : ""}
              </span>
            </div>
          `;
        })
        .join("");
      return `
        <div class="matrix-row nature-heatmap-row">
          <div class="matrix-name" title="${escapeHtml(`${row.name} 汇总 ${fmt(rowTotal)}`)}">
            <strong>${escapeHtml(row.name)}</strong>
            <em aria-label="行汇总">${fmt(rowTotal)}</em>
          </div>
          ${cells}
        </div>
      `;
    })
    .join("");
  node.innerHTML = rows.length
    ? `${heatmapLegendMarkup(heatScale)}<div class="matrix-grid nature-heatmap-grid crystal-heatmap-grid" style="--matrix-cols:${columns.length};--matrix-row-min:132px;--matrix-row-col:188px;--matrix-col-min:42px;--matrix-col-max:58px">${head}${body}</div>`
    : `<p class="empty-state">暂无官方适应症记录</p>`;
}

function projectGeo(lon, lat) {
  const x = ((Number(lon) + 180) / 360) * GEO_VIEWBOX.width;
  const y = ((90 - Number(lat)) / 180) * GEO_VIEWBOX.height;
  return {
    x: clamp(x, 0, GEO_VIEWBOX.width),
    y: clamp(y, 0, GEO_VIEWBOX.height),
    xp: clamp((x / GEO_VIEWBOX.width) * 100, 0, 100),
    yp: clamp((y / GEO_VIEWBOX.height) * 100, 0, 100),
  };
}

function geoPathFromRing(ring) {
  return ring
    .map((coord, index) => {
      const point = projectGeo(coord[0], coord[1]);
      return `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
    })
    .join(" ") + "Z";
}

function geoPathFromGeometry(geometry) {
  if (!geometry) return "";
  if (geometry.type === "Polygon") {
    return geometry.coordinates.map(geoPathFromRing).join(" ");
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates.flatMap((polygon) => polygon.map(geoPathFromRing)).join(" ");
  }
  return "";
}

function canonicalCountryName(country) {
  const text = String(country || "").trim();
  return GEO_COUNTRY_ALIASES[text] || text;
}

function countryFeatureKey(country) {
  return canonicalCountryName(country).toLowerCase();
}

function countryDataKey(country) {
  const text = String(country || "").trim();
  const reverse = Object.entries(GEO_COUNTRY_ALIASES).find(([, mapped]) => mapped === text);
  return reverse?.[0] || text;
}

function indexWorldFeatures(geojson) {
  geoFeatureByCountry.clear();
  (geojson.features || []).forEach((feature) => {
    const name = feature.properties?.name || feature.id || "";
    if (!name) return;
    geoFeatureByCountry.set(countryFeatureKey(name), feature);
  });
}

function findCountryFeature(country) {
  return geoFeatureByCountry.get(countryFeatureKey(country));
}

function countryDataSet() {
  return new Set((DATA.geo_companies || []).map((item) => countryFeatureKey(item.country)).filter(Boolean));
}

function renderWorldMap(geojson) {
  const svg = $("worldMapSvg");
  if (!svg) return;
  geoWorldData = geojson;
  indexWorldFeatures(geojson);
  const countriesWithData = countryDataSet();
  const paths = (geojson.features || [])
    .map((feature) => {
      const d = geoPathFromGeometry(feature.geometry);
      const name = feature.properties?.name || feature.id || "";
      const hasData = countriesWithData.has(countryFeatureKey(name));
      return d
        ? `<path d="${d}" class="${hasData ? "has-geo-data" : ""}" data-country="${escapeHtml(name)}" tabindex="${hasData ? "0" : "-1"}" aria-label="${escapeHtml(name)}"></path>`
        : "";
    })
    .join("");
  svg.innerHTML = `
    <defs>
      <linearGradient id="landGlow" x1="0%" x2="100%" y1="0%" y2="100%">
        <stop offset="0%" stop-color="#dfe9de" stop-opacity="0.98" />
        <stop offset="48%" stop-color="#b9d8ce" stop-opacity="0.92" />
        <stop offset="100%" stop-color="#ead2b7" stop-opacity="0.9" />
      </linearGradient>
    </defs>
    <g class="world-land">${paths}</g>
  `;
  svg.querySelectorAll("path.has-geo-data").forEach((path) => {
    const country = countryDataKey(path.dataset.country || "");
    path.addEventListener("click", () => {
      const aggregate = countryAggregatesForCurrentFilters().find((item) => countryFeatureKey(item.country) === countryFeatureKey(country));
      if (aggregate) openGeoCountry(aggregate);
    });
    path.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        path.click();
      }
    });
  });
}

function renderFallbackWorldMap() {
  const svg = $("worldMapSvg");
  if (!svg) return;
  svg.innerHTML = `
    <path d="M108 175 C158 110 256 118 316 152 C364 180 374 234 332 268 C280 310 168 292 118 248 C88 222 82 194 108 175Z"></path>
    <path d="M278 312 C338 290 388 324 402 376 C420 440 350 486 304 448 C266 418 238 336 278 312Z"></path>
    <path d="M470 156 C542 100 682 104 772 156 C842 196 858 280 784 318 C690 366 536 332 468 274 C420 232 424 188 470 156Z"></path>
    <path d="M662 322 C718 300 786 330 804 384 C822 438 750 462 696 434 C650 410 626 350 662 322Z"></path>
    <path d="M784 392 C846 374 922 400 940 442 C952 474 898 492 846 472 C802 456 758 414 784 392Z"></path>
  `;
}

function geoColor(region) {
  return GEO_REGION_COLORS[region] || GEO_REGION_COLORS.Global;
}

function geoHash(value) {
  return String(value || "").split("").reduce((sum, char) => sum + char.charCodeAt(0), 0);
}

function geoMetricValue(item) {
  return geoMetric === "companies" ? Number(item.company_count || 0) : Number(item.product_count || 0);
}

function geoMetricUnit() {
  return geoMetric === "companies" ? "家企业" : "条产品线";
}

function geoTrackColor(track) {
  return GEO_TRACK_COLORS[track] || GEO_REGION_COLORS.Other;
}

function addGeoBaseTiles(map) {
  if (!map || !window.L) return null;
  let fallbackAdded = false;
  const primaryTiles = L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxNativeZoom: 19,
    maxZoom: 22,
    attribution: "&copy; OpenStreetMap &copy; CARTO",
  }).addTo(map);
  primaryTiles.on("tileerror", () => {
    if (fallbackAdded) return;
    fallbackAdded = true;
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxNativeZoom: 19,
      maxZoom: 22,
      attribution: "&copy; OpenStreetMap",
    }).addTo(map);
  });
  return primaryTiles;
}

function geoZoomTargets() {
  return ["worldMapSvg", "geoPointLayer", "geoLabelLayer"]
    .map($)
    .filter(Boolean)
    .concat([...document.querySelectorAll(".map-grid-lines")]);
}

function clampGeoZoomPan() {
  const stage = $("geoMapStage");
  if (!stage || geoZoom.scale <= 1.001) {
    geoZoom.x = 0;
    geoZoom.y = 0;
    return;
  }
  const rect = stage.getBoundingClientRect();
  const overflowX = rect.width * (geoZoom.scale - 1);
  const overflowY = rect.height * (geoZoom.scale - 1);
  geoZoom.x = clamp(geoZoom.x, -overflowX, 0);
  geoZoom.y = clamp(geoZoom.y, -overflowY, 0);
}

function applyGeoZoom() {
  clampGeoZoomPan();
  const transform = `translate(${geoZoom.x.toFixed(1)}px, ${geoZoom.y.toFixed(1)}px) scale(${geoZoom.scale.toFixed(4)})`;
  geoZoomTargets().forEach((node) => {
    node.style.transformOrigin = "0 0";
    node.style.transform = transform;
  });
  const layer = $("geoPointLayer");
  if (layer) {
    layer.style.setProperty("--dot-counter", (1 / geoZoom.scale).toFixed(4));
    layer.style.setProperty("--dot-hover-counter", (1.8 / geoZoom.scale).toFixed(4));
  }
  const stage = $("geoMapStage");
  if (stage) stage.classList.toggle("is-zoomed", geoZoom.scale > 1.01);
  setText("geoZoomLevel", `${Math.round(geoZoom.scale * 100)}%`);
  hideGeoTooltip();
}

function zoomGeoAt(clientX, clientY, nextScale) {
  const stage = $("geoMapStage");
  if (!stage) return;
  const rect = stage.getBoundingClientRect();
  const localX = clientX - rect.left;
  const localY = clientY - rect.top;
  const beforeX = (localX - geoZoom.x) / geoZoom.scale;
  const beforeY = (localY - geoZoom.y) / geoZoom.scale;
  geoZoom.scale = clamp(nextScale, 1, 5);
  geoZoom.x = localX - beforeX * geoZoom.scale;
  geoZoom.y = localY - beforeY * geoZoom.scale;
  applyGeoZoom();
}

function resetGeoZoom() {
  if (geoLeafletMap) {
    fitLeafletGeoHome();
    return;
  }
  geoZoom.scale = 1;
  geoZoom.x = 0;
  geoZoom.y = 0;
  applyGeoZoom();
}

function splitList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

const ZH_LABELS = {
  "All tracks": "全部赛道 / All tracks",
  "All regions": "全部区域 / All regions",
  "All companies": "全部企业 / All companies",
  "All evidence": "全部证据 / All evidence",
  "全部赛道": "全部赛道 / All tracks",
  "全部区域": "全部区域 / All regions",
  "全部企业": "全部企业 / All companies",
  "全部证据": "全部证据 / All evidence",
  Injectables: "注射材料 / Injectables",
  EBD: "光电设备 / EBD",
  Skincare: "皮肤护理 / Skincare",
  Regenerative: "再生修复 / Regenerative",
  Implants: "植入物 / Implants",
  Surgical: "手术器械 / Surgical",
  Consumables: "耗材 / Consumables",
  Threads: "线材 / Threads",
  Toxin: "肉毒毒素",
  Neurotoxin: "肉毒毒素",
  Fillers: "填充剂 / Fillers",
  Diagnostics: "诊断检测 / Diagnostics",
  Pharma: "药品 / Pharma",
  "North America": "北美 / North America",
  Europe: "欧洲 / Europe",
  "Asia-Pacific": "亚太 / Asia-Pacific",
  "Middle East": "中东 / Middle East",
  "Latin America": "拉美 / Latin America",
  Africa: "非洲 / Africa",
  Oceania: "大洋洲 / Oceania",
  Global: "全球 / Global",
  "United States": "美国 / United States",
  USA: "美国 / USA",
  Brazil: "巴西 / Brazil",
  Japan: "日本 / Japan",
  Australia: "澳大利亚 / Australia",
  "Asia Pacific": "亚太 / Asia Pacific",
  Other: "其他 / Other",
  Unknown: "未分类 / Unknown",
  FDA: "FDA 证据 / FDA evidence",
  CE: "CE/MDR 证据 / CE/MDR evidence",
  MDSAP: "MDSAP 质量体系 / MDSAP QMS",
  NMPA: "NMPA 证据 / NMPA evidence",
  ANVISA: "ANVISA 证据 / ANVISA evidence",
  TGA: "TGA/ARTG 证据 / TGA/ARTG evidence",
  ARTG: "TGA/ARTG 证据 / TGA/ARTG evidence",
  PMDA: "PMDA/MHLW 证据 / PMDA/MHLW evidence",
  MFDS: "MFDS 证据 / MFDS evidence",
  MDR: "MDR/CE 证据 / MDR/CE evidence",
  listed: "已上市企业 / Listed companies",
  queued: "待核验 / Queued",
  backlog: "待补充 / Backlog",
  verified: "已核验 / Verified",
  "unverified seed": "待核验线索 / Unverified lead",
};

function zhLabel(value) {
  const text = String(value || "").trim();
  return ZH_LABELS[text] || text;
}

const GEO_UI_LABELS = {
  "All tracks": "All tracks",
  "All regions": "All regions",
  "All companies": "All companies",
  "All evidence": "All evidence",
  "全部赛道": "All tracks",
  "全部区域": "All regions",
  "全部企业": "All companies",
  "全部证据": "All evidence",
  Injectables: "Injectables",
  EBD: "EBD",
  Skincare: "Skincare",
  Regenerative: "Regenerative",
  Implants: "Implants",
  Surgical: "Surgical",
  Consumables: "Consumables",
  Threads: "Threads",
  Toxin: "Botulinum toxin",
  Neurotoxin: "Botulinum toxin",
  Fillers: "Fillers",
  Diagnostics: "Diagnostics",
  Pharma: "Pharma",
  Services: "Services",
  "North America": "North America",
  Europe: "Europe",
  "Asia-Pacific": "Asia-Pacific",
  "Middle East": "Middle East",
  "Latin America": "Latin America",
  Africa: "Africa",
  Oceania: "Oceania",
  Global: "Global",
  "United States": "United States",
  USA: "USA",
  Brazil: "Brazil",
  Japan: "Japan",
  Australia: "Australia",
  "Asia Pacific": "Asia Pacific",
  Other: "Other",
  Unknown: "Unclassified",
  FDA: "FDA evidence",
  CE: "CE/MDR evidence",
  MDSAP: "MDSAP QMS",
  NMPA: "NMPA evidence",
  ANVISA: "ANVISA evidence",
  TGA: "TGA/ARTG evidence",
  ARTG: "TGA/ARTG evidence",
  PMDA: "PMDA/MHLW evidence",
  MFDS: "MFDS evidence",
  MDR: "MDR/CE evidence",
  listed: "Listed companies",
  queued: "Queued",
  backlog: "Backlog",
  verified: "Verified",
  "unverified seed": "Unverified lead",
};

function geoUiLabel(value) {
  const text = String(value || "").trim();
  return GEO_UI_LABELS[text] || text;
}

const GEO_MAP_LABELS = {
  "All tracks": "全部赛道",
  "All regions": "全部区域",
  "All companies": "全部企业",
  "All evidence": "全部证据",
  "全部赛道": "全部赛道",
  "全部区域": "全部区域",
  "全部企业": "全部企业",
  "全部证据": "全部证据",
  Injectables: "注射材料",
  EBD: "光电设备",
  Skincare: "皮肤护理",
  Regenerative: "再生修复",
  Implants: "植入物",
  Surgical: "手术器械",
  Consumables: "耗材",
  Threads: "线材",
  Toxin: "肉毒毒素",
  Neurotoxin: "肉毒毒素",
  Fillers: "填充剂",
  Diagnostics: "诊断/检测",
  Pharma: "药品",
  Services: "Services",
  "North America": "北美",
  Europe: "欧洲",
  "Asia-Pacific": "亚太",
  "Middle East": "中东",
  "Latin America": "拉美",
  Africa: "非洲",
  Oceania: "大洋洲",
  Global: "全球",
  Other: "其他",
  Unknown: "未分类",
  FDA: "FDA 证据",
  CE: "CE/MDR 证据",
  listed: "已上市企业",
  verified: "已核验",
  "unverified seed": "待核验线索",
};

function geoMapLabel(value) {
  const text = String(value || "").trim();
  return GEO_MAP_LABELS[text] || text;
}

function geoCompanyTags(company) {
  return [geoMapLabel(company.primary_track), company.regulatory_channels, company.stock_code]
    .filter(Boolean)
    .join(" / ");
}

function geoProductLineText(count) {
  return `${fmt(count)} 条产品线`;
}

function geoCompanyCountText(count) {
  return `${fmt(count)} 家企业`;
}

function geoBilingual(zh, en, className = "") {
  return bilingualMarkup(`${zh} / ${en}`, className);
}

function geoBilingualLabel(value) {
  const zh = geoMapLabel(value);
  const en = geoUiLabel(value);
  if (!en || zh === en) return escapeHtml(zh);
  return geoBilingual(zh, en);
}

function geoMiniStat(kind, value, zh, en) {
  return `
    <span class="geo-mini-stat geo-mini-${escapeHtml(kind)}" title="${escapeHtml(`${zh} / ${en}`)}">
      <i aria-hidden="true"></i>
      <em>${fmt(value || 0)}</em>
    </span>
  `;
}

function companyProfileHref(company) {
  return `./company-profile.html?company=${encodeURIComponent(company || "")}`;
}

function geoCompactMetricsHtml(item) {
  return `
    ${geoMiniStat("company", item.company_count, "企业", "Companies")}
    ${geoMiniStat("product", item.product_count, "产品线", "Product lines")}
  `;
}

function geoCompanyMiniMetricsHtml(company) {
  return geoMiniStat("product", company.products, "产品线", "Product lines");
}

function geoTrackChipHtml(name, value) {
  return `
    <li class="geo-track-chip" style="--geo-color:${geoTrackColor(name)}">
      <i aria-hidden="true"></i>
      <strong>${geoBilingualLabel(name)}</strong>
      <span>${fmt(value)}</span>
    </li>
  `;
}

function zhList(value) {
  return splitList(value).map(zhLabel).join(" / ");
}

function companyTags(company) {
  return [zhLabel(company.primary_track), company.regulatory_channels, company.stock_code, zhLabel(company.review_status)]
    .filter(Boolean)
    .join(" / ");
}

function productLineText(count) {
  return `${fmt(count)} 条产品线 / product lines`;
}

function companyCountText(count) {
  return `${fmt(count)} 家企业 / companies`;
}

function zhEvidenceNote(value) {
  return String(value || "")
    .replaceAll("Product_Lines", "产品线表")
    .replaceAll("QMS", "质量体系")
    .replaceAll("MDSAP仅作质量体系审核", "MDSAP 仅作质量体系审核");
}

function countValues(items, field) {
  const counts = new Map();
  (items || []).forEach((item) => {
    const value = item[field] || "Unknown";
    counts.set(value, (counts.get(value) || 0) + 1);
  });
  return [...counts.entries()]
    .filter(([value]) => value && value !== "Unknown")
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function setSelectOptions(id, allLabel, rows, selectedValue = "all", labeler = zhLabel) {
  const node = $(id);
  if (!node) return;
  node.innerHTML = [
    `<option value="all">${escapeHtml(labeler(allLabel))}</option>`,
    ...rows.map(([value, count]) => `<option value="${escapeHtml(value)}">${escapeHtml(labeler(value))} (${fmt(count)})</option>`),
  ].join("");
  node.value = selectedValue;
}

function isListedGeoCompany(item) {
  return Boolean(item.stock_code) || String(item.ownership || "").toLowerCase() === "public";
}

function geoCompanyEvidence(item) {
  return splitList(item.regulatory_channels).map((channel) => channel.toUpperCase());
}

function geoCompanyPassesFilters(item) {
  if (geoFilters.track !== "all" && (item.primary_track || "Unknown") !== geoFilters.track) return false;
  if (geoFilters.region !== "all" && (item.region || "Unknown") !== geoFilters.region) return false;
  if (geoFilters.listing === "listed" && !isListedGeoCompany(item)) return false;
  if (geoFilters.evidence !== "all" && !geoCompanyEvidence(item).includes(geoFilters.evidence)) return false;
  return true;
}

function aggregateGeoCompanies(companies) {
  const groups = new Map();
  (companies || []).forEach((company) => {
    const coords = geoCoordinates(company);
    if (!coords) return;
    const label = `${company.city || company.country || "Unknown"}, ${company.country || "Unknown"}`.replace(/^,\s*/, "");
    const key = `${label}|${coords.lat.toFixed(3)}|${coords.lon.toFixed(3)}`;
    if (!groups.has(key)) {
      groups.set(key, {
        name: label,
        city: company.city,
        country: company.country,
        region: company.region,
        lat: coords.lat,
        lon: coords.lon,
        precision: company.precision,
        company_count: 0,
        product_count: 0,
        companies: [],
        track_counts: new Map(),
        regulatory_channels: new Set(),
      });
    }
    const group = groups.get(key);
    const products = Number(company.products || 0);
    group.company_count += 1;
    group.product_count += products;
    group.companies.push({
      company: company.company,
      products,
      brands: Number(company.brands || 0),
      stock_code: company.stock_code,
      primary_track: company.primary_track,
      regulatory_channels: company.regulatory_channels,
      review_status: company.review_status,
    });
    if (company.primary_track) group.track_counts.set(company.primary_track, (group.track_counts.get(company.primary_track) || 0) + products);
    geoCompanyEvidence(company).forEach((channel) => group.regulatory_channels.add(channel));
  });
  return [...groups.values()]
    .map((group) => {
      group.companies.sort((a, b) => Number(b.products || 0) - Number(a.products || 0) || String(a.company || "").localeCompare(b.company || ""));
      group.track_counts = [...group.track_counts.entries()].sort((a, b) => b[1] - a[1]);
      group.regulatory_channels = [...group.regulatory_channels].sort().join(", ");
      return group;
    })
    .sort((a, b) => b.company_count - a.company_count || b.product_count - a.product_count || a.name.localeCompare(b.name));
}

function dominantTrack(trackCounts) {
  const first = (trackCounts || [])[0];
  return first ? first[0] : "";
}

function geoMarkerColor(item) {
  return geoTrackColor(dominantTrack(item.track_counts)) || geoColor(item.region);
}

function aggregateGeoCountries(companies) {
  const groups = new Map();
  (companies || []).forEach((company) => {
    const coords = geoCoordinates(company);
    if (!coords) return;
    const country = company.country || "Unknown";
    const key = countryFeatureKey(country);
    if (!groups.has(key)) {
      groups.set(key, {
        name: country,
        country,
        region: company.region,
        lat_weighted: 0,
        lon_weighted: 0,
        weight: 0,
        lat: coords.lat,
        lon: coords.lon,
        company_count: 0,
        product_count: 0,
        listed_count: 0,
        companies: [],
        track_counts: new Map(),
        regulatory_channels: new Set(),
        precision: "country_aggregate",
      });
    }
    const group = groups.get(key);
    const products = Math.max(1, Number(company.products || 0));
    group.company_count += 1;
    group.product_count += Number(company.products || 0);
    group.listed_count += isListedGeoCompany(company) ? 1 : 0;
    group.lat_weighted += coords.lat * products;
    group.lon_weighted += coords.lon * products;
    group.weight += products;
    group.companies.push({
      company: company.company,
      city: company.city,
      country: company.country,
      lat: coords.lat,
      lon: coords.lon,
      products: Number(company.products || 0),
      brands: Number(company.brands || 0),
      stock_code: company.stock_code,
      primary_track: company.primary_track,
      regulatory_channels: company.regulatory_channels,
      review_status: company.review_status,
    });
    if (company.primary_track) group.track_counts.set(company.primary_track, (group.track_counts.get(company.primary_track) || 0) + Number(company.products || 0));
    geoCompanyEvidence(company).forEach((channel) => group.regulatory_channels.add(channel));
  });
  return [...groups.values()]
    .map((group) => {
      if (group.weight) {
        group.lat = group.lat_weighted / group.weight;
        group.lon = group.lon_weighted / group.weight;
      }
      group.city_points = aggregateGeoCompanies(group.companies);
      group.companies.sort((a, b) => Number(b.products || 0) - Number(a.products || 0) || String(a.company || "").localeCompare(b.company || ""));
      group.track_counts = [...group.track_counts.entries()].sort((a, b) => b[1] - a[1]);
      group.regulatory_channels = [...group.regulatory_channels].sort().join(", ");
      group.dominant_track = dominantTrack(group.track_counts);
      group.listed_share = group.company_count ? group.listed_count / group.company_count : 0;
      group.name = group.country;
      return group;
    })
    .sort((a, b) => geoMetricValue(b) - geoMetricValue(a) || b.product_count - a.product_count || a.country.localeCompare(b.country));
}

function countryAggregatesForCurrentFilters() {
  return aggregateGeoCountries((DATA.geo_companies || []).filter(geoCompanyPassesFilters));
}

function currentCountryAggregate(country) {
  const key = countryFeatureKey(country);
  return countryAggregatesForCurrentFilters().find((item) => countryFeatureKey(item.country) === key);
}

function positionGeoItems(items, options = {}) {
  const jitter = options.jitter !== false;
  const buckets = new Map();
  const leafletItems = [...items].sort(
    (a, b) => geoMetricValue(a) - geoMetricValue(b) || String(a.name || "").localeCompare(String(b.name || "")),
  );
  leafletItems.forEach((item) => {
    const coords = geoCoordinates(item);
    if (!coords) return;
    const key = `${coords.lat.toFixed(2)}|${coords.lon.toFixed(2)}`;
    if (!buckets.has(key)) buckets.set(key, []);
    buckets.get(key).push(item);
  });
  buckets.forEach((bucket) => {
    bucket
      .sort((a, b) => geoMetricValue(b) - geoMetricValue(a))
      .forEach((item, index) => {
        const coords = geoCoordinates(item);
        if (!coords) return;
        const point = projectGeo(coords.lon, coords.lat);
        const count = bucket.length;
        const angle = ((index / Math.max(1, count)) * Math.PI * 2) + geoHash(item.name || item.company) * 0.011;
        const radius = jitter && count > 1 ? Math.min(24, 5 + Math.sqrt(count) * 3.2) * (0.55 + (index % 4) * 0.22) : 0;
        item._x = point.xp;
        item._y = point.yp;
        item._jx = Math.cos(angle) * radius;
        item._jy = Math.sin(angle) * radius;
      });
  });
  return items;
}

function sizeGeoItem(item, maxMetric) {
  const metric = geoMetricValue(item);
  if (item.precision === "country_aggregate") return clamp(9 + Math.sqrt(metric || 1) * 1.1, 12, 30);
  return clamp(3.5 + Math.sqrt(metric || 1) * 0.72, 4.5, 14);
}

function relaxGeoItemPositions(items, maxMetric) {
  items.forEach((item) => {
    item._size = sizeGeoItem(item, maxMetric);
    item._jx = Number(item._jx || 0);
    item._jy = Number(item._jy || 0);
  });
  for (let iteration = 0; iteration < 10; iteration += 1) {
    for (let i = 0; i < items.length; i += 1) {
      for (let j = i + 1; j < items.length; j += 1) {
        const a = items[i];
        const b = items[j];
        const ax = (a._x / 100) * GEO_VIEWBOX.width + a._jx;
        const ay = (a._y / 100) * GEO_VIEWBOX.height + a._jy;
        const bx = (b._x / 100) * GEO_VIEWBOX.width + b._jx;
        const by = (b._y / 100) * GEO_VIEWBOX.height + b._jy;
        const dx = bx - ax;
        const dy = by - ay;
        const distance = Math.max(1, Math.hypot(dx, dy));
        const target = (a._size + b._size) * 0.5 + 15;
        if (distance >= target) continue;
        const push = (target - distance) * 0.42;
        const nx = dx / distance;
        const ny = dy / distance;
        a._jx = clamp(a._jx - nx * push, -74, 74);
        a._jy = clamp(a._jy - ny * push, -54, 54);
        b._jx = clamp(b._jx + nx * push, -74, 74);
        b._jy = clamp(b._jy + ny * push, -54, 54);
      }
    }
  }
  return items;
}

function geoTooltipHtml(item) {
  const tracks = (item.track_counts || [])
    .slice(0, 2)
    .map(([name, value]) => `${geoMapLabel(name)} ${fmt(value)}`)
    .join(" / ");
  const topCompanies = (item.companies || [])
    .slice(0, 3)
    .map((company) => (typeof company === "string" ? company : company.company))
    .filter(Boolean)
    .join(", ");
  const fallbackCompanies = `<span class="bilingual"><span class="bilingual-zh">暂无公司</span><span class="bilingual-en">No companies</span></span>`;
  return `
    <strong>${escapeHtml(item.name || item.city || item.country || "")}</strong>
    <span class="geo-tooltip-metrics">${geoCompactMetricsHtml(item)}</span>
    <em>${topCompanies ? escapeHtml(topCompanies) : fallbackCompanies}</em>
    <small>${escapeHtml(tracks || item.regulatory_channels || "")}${item.listed_count ? ` · 上市 ${fmt(item.listed_count)} / Listed ${fmt(item.listed_count)}` : ""}</small>
  `;
}

function showGeoTooltip(item, node) {
  const tooltip = $("geoTooltip");
  const stage = $("geoMapStage");
  if (!tooltip || !stage) return;
  tooltip.innerHTML = geoTooltipHtml(item);
  tooltip.hidden = false;
  const rect = stage.getBoundingClientRect();
  const pointRect = node.getBoundingClientRect();
  const x = clamp(pointRect.left - rect.left + pointRect.width / 2, 92, rect.width - 92);
  const y = clamp(pointRect.top - rect.top - 10, 74, rect.height - 20);
  tooltip.style.left = `${x}px`;
  tooltip.style.top = `${y}px`;
}

function hideGeoTooltip() {
  const tooltip = $("geoTooltip");
  if (tooltip) tooltip.hidden = true;
}

function openGeoCluster(item) {
  const companies = (item.companies || [])
    .slice(0, 10)
    .map((company) => {
      if (typeof company === "string") {
        return `
          <li class="country-company-item">
            <a class="country-company-link" href="${companyProfileHref(company)}" title="${escapeHtml(`打开公司介绍 / Open company profile: ${company}`)}">
              <strong>${escapeHtml(company)}</strong>
            </a>
          </li>
        `;
      }
      const tags = [geoMapLabel(company.primary_track), company.stock_code].filter(Boolean).join(" · ");
      return `
        <li class="country-company-item">
          <a class="country-company-link" href="${companyProfileHref(company.company)}" title="${escapeHtml(`打开公司介绍 / Open company profile: ${company.company}`)}">
            <strong>${escapeHtml(company.company)}</strong>
          </a>
          <span>${geoCompanyMiniMetricsHtml(company)}${tags ? `<em>${escapeHtml(tags)}</em>` : ""}</span>
        </li>
      `;
    })
    .join("");
  const tracks = (item.track_counts || [])
    .slice(0, 6)
    .map(([name, value]) => geoTrackChipHtml(name, value))
    .join("");
  openOverlay(
    item.name || "Location",
    `
      <div class="country-detail-side">
        <div class="country-detail-side-head">
          <span>${item.precision === "city" ? geoBilingual("城市", "City") : geoBilingual("国家定位点", "Country point")}</span>
          <strong>${escapeHtml(item.name || "")}</strong>
          <em class="geo-side-metrics">
            ${geoCompactMetricsHtml(item)}
            ${item.listed_count ? geoMiniStat("public", item.listed_count, "上市企业", "Public companies") : ""}
          </em>
        </div>
        <div class="country-detail-side-grid">
          <article>
            <h4>${geoBilingual("企业", "Companies")}</h4>
            <ul>${companies || `<li>${geoBilingual("暂无企业", "No mapped companies")}</li>`}</ul>
          </article>
          <article>
            <h4>${geoBilingual("赛道", "Tracks")}</h4>
            <ul>${tracks || `<li>${geoBilingual("暂无赛道摘要", "No track summary")}</li>`}</ul>
          </article>
        </div>
      </div>
    `,
  );
}

function forEachGeometryCoord(geometry, callback) {
  if (!geometry) return;
  if (geometry.type === "Polygon") {
    geometry.coordinates.forEach((ring) => ring.forEach(callback));
  } else if (geometry.type === "MultiPolygon") {
    geometry.coordinates.forEach((polygon) => polygon.forEach((ring) => ring.forEach(callback)));
  }
}

function pointInRing(lon, lat, ring = []) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i] || [];
    const [xj, yj] = ring[j] || [];
    const intersects = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / ((yj - yi) || 1e-9) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function pointInPolygon(lon, lat, polygon = []) {
  if (!polygon.length || !pointInRing(lon, lat, polygon[0])) return false;
  return !polygon.slice(1).some((ring) => pointInRing(lon, lat, ring));
}

function pointInGeometry(lon, lat, geometry) {
  if (!geometry) return false;
  if (geometry.type === "Polygon") return pointInPolygon(lon, lat, geometry.coordinates || []);
  if (geometry.type === "MultiPolygon") return (geometry.coordinates || []).some((polygon) => pointInPolygon(lon, lat, polygon));
  return false;
}

function countryAggregateAtLatLng(latlng) {
  if (!latlng) return null;
  const lon = Number(latlng.lng);
  const lat = Number(latlng.lat);
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  return countryAggregatesForCurrentFilters().find((aggregate) => {
    const feature = findCountryFeature(aggregate.country);
    return feature && pointInGeometry(lon, lat, feature.geometry);
  });
}

function geometryBBox(geometry) {
  const bbox = { minLon: Infinity, maxLon: -Infinity, minLat: Infinity, maxLat: -Infinity };
  forEachGeometryCoord(geometry, ([lon, lat]) => {
    bbox.minLon = Math.min(bbox.minLon, lon);
    bbox.maxLon = Math.max(bbox.maxLon, lon);
    bbox.minLat = Math.min(bbox.minLat, lat);
    bbox.maxLat = Math.max(bbox.maxLat, lat);
  });
  if (!Number.isFinite(bbox.minLon)) return null;
  return bbox;
}

function projectToCountryView(lon, lat, bbox, width = 680, height = 360, pad = 24) {
  const lonSpan = Math.max(0.1, bbox.maxLon - bbox.minLon);
  const latSpan = Math.max(0.1, bbox.maxLat - bbox.minLat);
  const scale = Math.min((width - pad * 2) / lonSpan, (height - pad * 2) / latSpan);
  const mapWidth = lonSpan * scale;
  const mapHeight = latSpan * scale;
  const xOffset = (width - mapWidth) / 2;
  const yOffset = (height - mapHeight) / 2;
  const x = xOffset + (lon - bbox.minLon) * scale;
  const y = yOffset + (bbox.maxLat - lat) * scale;
  return {
    x: clamp(x, pad / 3, width - pad / 3),
    y: clamp(y, pad / 3, height - pad / 3),
    xp: clamp((x / width) * 100, 0, 100),
    yp: clamp((y / height) * 100, 0, 100),
  };
}

function countryPathFromRing(ring, bbox) {
  return ring
    .map((coord, index) => {
      const point = projectToCountryView(coord[0], coord[1], bbox);
      return `${index ? "L" : "M"}${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
    })
    .join(" ") + "Z";
}

function ringBBox(ring = []) {
  const bbox = { minLon: Infinity, maxLon: -Infinity, minLat: Infinity, maxLat: -Infinity };
  ring.forEach(([lon, lat]) => {
    bbox.minLon = Math.min(bbox.minLon, lon);
    bbox.maxLon = Math.max(bbox.maxLon, lon);
    bbox.minLat = Math.min(bbox.minLat, lat);
    bbox.maxLat = Math.max(bbox.maxLat, lat);
  });
  return Number.isFinite(bbox.minLon) ? bbox : null;
}

function bboxIntersects(a, b) {
  if (!a || !b) return false;
  return a.minLon <= b.maxLon && a.maxLon >= b.minLon && a.minLat <= b.maxLat && a.maxLat >= b.minLat;
}

function countryPathFromGeometry(geometry, bbox, clipBBox = null) {
  if (!geometry || !bbox) return "";
  if (geometry.type === "Polygon") {
    const outer = ringBBox(geometry.coordinates?.[0] || []);
    if (clipBBox && !bboxIntersects(outer, clipBBox)) return "";
    return geometry.coordinates
      .filter((ring, index) => index === 0 || !clipBBox || bboxIntersects(ringBBox(ring), clipBBox))
      .map((ring) => countryPathFromRing(ring, bbox))
      .join(" ");
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates
      .filter((polygon) => !clipBBox || bboxIntersects(ringBBox(polygon?.[0] || []), clipBBox))
      .flatMap((polygon) => polygon.map((ring) => countryPathFromRing(ring, bbox)))
      .join(" ");
  }
  return "";
}

function countryDetailBBox(country, feature, fallbackBBox) {
  const canonicalCountry = canonicalCountryName(country?.country || country);
  const countryKey = countryFeatureKey(country?.country || country);
  return (
    COUNTRY_DETAIL_BBOX_OVERRIDES.get(country?.country) ||
    COUNTRY_DETAIL_BBOX_OVERRIDES.get(canonicalCountry) ||
    COUNTRY_DETAIL_BBOX_OVERRIDES.get(countryKey) ||
    geometryBBox(feature?.geometry) ||
    fallbackBBox
  );
}

function countryDetailBoundsFromBBox(bbox) {
  if (!bbox) return null;
  return [
    [bbox.minLat, bbox.minLon],
    [bbox.maxLat, bbox.maxLon],
  ];
}

function countryMapTooltipHtml(city) {
  const topCompanies = (city.companies || [])
    .slice(0, 3)
    .map((company) => company.company)
    .filter(Boolean)
    .join(", ");
  const tracks = (city.track_counts || [])
    .slice(0, 2)
    .map(([name, value]) => `${geoMapLabel(name)} ${fmt(value)}`)
    .join(" / ");
  return `
    <strong>${escapeHtml(city.name || city.city || city.country)}</strong>
    <span>${geoCompanyCountText(city.company_count)} · ${geoProductLineText(city.product_count)}</span>
    ${topCompanies ? `<em>${escapeHtml(topCompanies)}</em>` : ""}
    ${tracks ? `<small>${escapeHtml(tracks)}</small>` : ""}
  `;
}

function countryCityDetailHtml(city) {
  const companies = (city.companies || [])
    .slice(0, 14)
    .map((company) => {
      const tags = [geoMapLabel(company.primary_track), company.stock_code].filter(Boolean).join(" · ");
      return `
        <li class="country-company-item">
          <a class="country-company-link" href="${companyProfileHref(company.company)}" title="${escapeHtml(`打开公司介绍 / Open company profile: ${company.company}`)}">
            <strong>${escapeHtml(company.company)}</strong>
          </a>
          <span>${geoCompanyMiniMetricsHtml(company)}${tags ? `<em>${escapeHtml(tags)}</em>` : ""}</span>
        </li>
      `;
    })
    .join("");
  const tracks = (city.track_counts || [])
    .slice(0, 6)
    .map(([name, value]) => geoTrackChipHtml(name, value))
    .join("");
  return `
    <div class="country-detail-side-head">
      <span>${city.city ? geoBilingual("城市", "City") : geoBilingual("国家定位点", "Country point")}</span>
      <strong>${escapeHtml(city.name || city.city || city.country)}</strong>
      <em class="geo-side-metrics">${geoCompactMetricsHtml(city)}</em>
    </div>
    <div class="country-detail-side-grid">
      <article>
        <h4>${geoBilingual("企业", "Companies")}</h4>
        <ul>${companies || `<li>${geoBilingual("暂无企业", "No mapped companies")}</li>`}</ul>
      </article>
      <article>
        <h4>${geoBilingual("赛道", "Tracks")}</h4>
        <ul>${tracks || `<li>${geoBilingual("暂无赛道摘要", "No track summary")}</li>`}</ul>
      </article>
    </div>
  `;
}

function countryOverviewHtml(country) {
  const topCompanies = (country.companies || [])
    .slice(0, 12)
    .map((company) => `
      <li class="country-company-item">
        <a class="country-company-link" href="${companyProfileHref(company.company)}" title="${escapeHtml(`打开公司介绍 / Open company profile: ${company.company}`)}">
          <strong>${escapeHtml(company.company)}</strong>
        </a>
        <span>${geoCompanyMiniMetricsHtml(company)}${company.city ? `<em>${escapeHtml(company.city)}</em>` : ""}</span>
      </li>
    `)
    .join("");
  const tracks = (country.track_counts || [])
    .slice(0, 6)
    .map(([name, value]) => geoTrackChipHtml(name, value))
    .join("");
  return `
    <div class="country-detail-side-head">
      <span>${geoBilingual("国家", "Country")}</span>
      <strong>${escapeHtml(country.country)}</strong>
      <em class="geo-side-metrics">
        ${geoCompactMetricsHtml(country)}
        ${geoMiniStat("city", country.city_points?.length || 0, "城市点", "City dots")}
      </em>
    </div>
    <div class="country-detail-side-grid">
      <article>
        <h4>${geoBilingual("企业", "Companies")}</h4>
        <ul>${topCompanies || `<li>${geoBilingual("暂无企业", "No mapped companies")}</li>`}</ul>
      </article>
      <article>
        <h4>${geoBilingual("赛道", "Tracks")}</h4>
        <ul>${tracks || `<li>${geoBilingual("暂无赛道摘要", "No track summary")}</li>`}</ul>
      </article>
    </div>
  `;
}

function renderCountryDetailMap(country, cities, selectedIndex = -1) {
  if (geoWorldData && !geoFeatureByCountry.size) indexWorldFeatures(geoWorldData);
  const feature = findCountryFeature(country.country);
  const maxMetric = Math.max(1, ...cities.map(geoMetricValue));
  const validCoords = cities.map(geoCoordinates).filter(Boolean);
  const validLons = validCoords.map((coords) => coords.lon);
  const validLats = validCoords.map((coords) => coords.lat);
  const fallbackBBox = {
    minLon: (validLons.length ? Math.min(...validLons) : 0) - 1,
    maxLon: (validLons.length ? Math.max(...validLons) : 1) + 1,
    minLat: (validLats.length ? Math.min(...validLats) : 0) - 1,
    maxLat: (validLats.length ? Math.max(...validLats) : 1) + 1,
  };
  const activeBBox = countryDetailBBox(country, feature, fallbackBBox);
  const path = feature && activeBBox ? countryPathFromGeometry(feature.geometry, activeBBox, activeBBox) : "";
  const dots = cities
    .map((city, index) => {
      const coords = geoCoordinates(city);
      if (!coords) return "";
      const point = projectToCountryView(coords.lon, coords.lat, activeBBox);
      const metric = geoMetricValue(city);
      const size = clamp(14 + Math.sqrt(metric || 1) * 2.6, 16, 46);
      return `
        <button class="country-city-dot ${index === selectedIndex ? "active" : ""}" type="button" data-country-city-index="${index}"
          style="left:${point.xp.toFixed(2)}%;top:${point.yp.toFixed(2)}%;--dot-size:${size.toFixed(1)}px;--geo-color:${geoMarkerColor(city)};--geo-ratio:${clamp((metric / maxMetric) * 100, 20, 100).toFixed(1)}%"
          aria-label="${escapeHtml(city.name)} ${geoCompanyCountText(city.company_count)} ${geoProductLineText(city.product_count)}"></button>
      `;
    })
    .join("");
  return `
    <div id="countryDetailMapShell" class="country-detail-map country-static-map-card">
      <div id="countryLeafletMap" class="country-leaflet-map" aria-label="${escapeHtml(country.country)} local map"></div>
      <div class="country-detail-static-map">
        <svg viewBox="0 0 680 360" preserveAspectRatio="none" role="img" aria-label="${escapeHtml(country.country)} detail map">
          <defs>
            <linearGradient id="countryLandGlow" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stop-color="#e4eee5" />
              <stop offset="100%" stop-color="#c6e1d8" />
            </linearGradient>
          </defs>
          ${path ? `<path class="country-detail-land" d="${path}"></path>` : `<rect class="country-detail-land fallback" x="80" y="46" width="520" height="260" rx="28"></rect>`}
        </svg>
        <div class="country-detail-dot-layer">${dots}</div>
      </div>
    </div>
  `;
}

function destroyCountryDetailMap() {
  if (!geoCountryDetailMap) return;
  geoCountryDetailMap.remove();
  geoCountryDetailMap = null;
}

function countryDetailMarkerStyle(city, maxMetric, active = false) {
  const metric = geoMetricValue(city);
  const ratio = clamp(metric / Math.max(1, maxMetric), 0, 1);
  return {
    radius: clamp(5 + Math.sqrt(metric || 1) * 2.2, 6, 18) + (active ? 2 : 0),
    color: "#ffffff",
    weight: active ? 3 : 1.8,
    fillColor: geoMarkerColor(city),
    fillOpacity: active ? 0.96 : clamp(0.68 + ratio * 0.22, 0.72, 0.92),
    opacity: 0.98,
    className: "leaflet-country-detail-dot",
  };
}

function mountCountryDetailMap(country, cities, selectedIndex = -1, onSelect = () => {}) {
  const mapNode = $("countryLeafletMap");
  const shell = $("countryDetailMapShell");
  if (!mapNode || !window.L) return null;
  destroyCountryDetailMap();
  geoCountryDetailMap = L.map(mapNode, {
    zoomControl: false,
    attributionControl: true,
    scrollWheelZoom: true,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
  });
  addGeoBaseTiles(geoCountryDetailMap);
  L.control.zoom({ position: "bottomright" }).addTo(geoCountryDetailMap);
  if (shell) shell.classList.add("uses-leaflet");

  const feature = findCountryFeature(country.country);
  const validCities = cities.map((city) => ({ city, coords: geoCoordinates(city) })).filter((item) => item.coords);
  const fallbackBBox = validCities.length
    ? {
        minLon: Math.min(...validCities.map((item) => item.coords.lon)) - 0.9,
        maxLon: Math.max(...validCities.map((item) => item.coords.lon)) + 0.9,
        minLat: Math.min(...validCities.map((item) => item.coords.lat)) - 0.9,
        maxLat: Math.max(...validCities.map((item) => item.coords.lat)) + 0.9,
      }
    : null;
  const activeBBox = countryDetailBBox(country, feature, fallbackBBox);
  if (feature) {
    L.geoJSON(feature, {
      interactive: false,
      style: {
        color: "rgba(91, 123, 154, 0.34)",
        weight: 1.2,
        fillColor: "#dfeee8",
        fillOpacity: 0.08,
      },
    }).addTo(geoCountryDetailMap);
  }

  const maxMetric = Math.max(1, ...cities.map(geoMetricValue));
  const markers = cities.map((city, index) => {
    const coords = geoCoordinates(city);
    if (!coords) return null;
    const marker = L.circleMarker([coords.lat, coords.lon], countryDetailMarkerStyle(city, maxMetric, index === selectedIndex));
    marker.bindTooltip(
      countryMapTooltipHtml(city),
      { className: "leaflet-geo-tooltip map-hover-tooltip country-map-tooltip", direction: "top", sticky: true, opacity: 1 },
    );
    marker.on("click", (event) => {
      L.DomEvent.stopPropagation(event);
      onSelect(index);
    });
    marker.addTo(geoCountryDetailMap);
    return marker;
  });

  const fitToContent = () => {
    geoCountryDetailMap.invalidateSize();
    const countryBounds = countryDetailBoundsFromBBox(activeBBox);
    if (countryBounds) {
      geoCountryDetailMap.fitBounds(countryBounds, { padding: [18, 18], maxZoom: 7.5, animate: false });
    } else if (validCities.length === 1) {
      geoCountryDetailMap.setView([validCities[0].coords.lat, validCities[0].coords.lon], 7, { animate: false });
    } else if (feature) {
      geoCountryDetailMap.fitBounds(L.geoJSON(feature).getBounds(), { padding: [30, 30], animate: false });
    }
  };
  setTimeout(fitToContent, 0);

  const setActive = (index) => {
    markers.forEach((marker, markerIndex) => {
      if (marker) marker.setStyle(countryDetailMarkerStyle(cities[markerIndex], maxMetric, markerIndex === index));
    });
    if (markers[index]) markers[index].bringToFront().openTooltip();
  };
  if (selectedIndex >= 0) setActive(selectedIndex);
  return { setActive };
}

function sameGeoCityPoint(city, seed) {
  if (!city || !seed) return false;
  const sameCountry = countryFeatureKey(city.country) === countryFeatureKey(seed.country);
  const cityName = String(city.city || city.name || "").toLowerCase();
  const seedName = String(seed.city || seed.name || "").toLowerCase();
  const sameName = cityName && seedName && cityName === seedName;
  const cityCoords = geoCoordinates(city);
  const seedCoords = geoCoordinates(seed);
  const sameLat = cityCoords && seedCoords && Math.abs(cityCoords.lat - seedCoords.lat) < 0.02;
  const sameLon = cityCoords && seedCoords && Math.abs(cityCoords.lon - seedCoords.lon) < 0.02;
  return sameCountry && (sameName || (sameLat && sameLon));
}

function openGeoCountry(country, selectedCitySeed = null) {
  const cities = positionGeoItems([...(country.city_points || [])], { jitter: false });
  const selectedIndex = selectedCitySeed ? cities.findIndex((city) => sameGeoCityPoint(city, selectedCitySeed)) : -1;
  destroyCountryDetailMap();
  const cityRows = cities
    .slice(0, 30)
    .map((city, index) => `
      <button class="country-city-row ${index === selectedIndex ? "active" : ""}" type="button" data-country-city-index="${index}" aria-label="${escapeHtml(city.name)} ${fmt(city.company_count)} companies ${fmt(city.product_count)} product lines">
        <strong>${escapeHtml(city.name)}</strong>
        <span>${geoCompactMetricsHtml(city)}</span>
      </button>
    `)
    .join("");
  openOverlay(
    country.country || "Country Distribution",
    `
      <div class="country-detail-shell">
        <div class="country-detail-kpis">
          <span><strong>${fmt(country.product_count)}</strong><em>${geoBilingual("产品线", "Product lines")}</em></span>
          <span><strong>${fmt(country.company_count)}</strong><em>${geoBilingual("企业", "Companies")}</em></span>
          <span><strong>${fmt(country.city_points?.length || 0)}</strong><em>${geoBilingual("城市点", "City dots")}</em></span>
          <span><strong>${fmt(country.listed_count || 0)}</strong><em>${geoBilingual("上市企业", "Public companies")}</em></span>
        </div>
        <div class="country-detail-layout">
          <div class="country-detail-map-wrap">
            ${renderCountryDetailMap(country, cities, selectedIndex)}
            <aside id="geoCountryDetailSide" class="country-detail-side country-detail-map-card">
              ${selectedIndex >= 0 ? countryCityDetailHtml(cities[selectedIndex]) : countryOverviewHtml(country)}
            </aside>
          </div>
          <div class="country-city-list">${cityRows}</div>
        </div>
      </div>
    `,
  );
  const side = $("geoCountryDetailSide");
  let detailMapControl = null;
  const selectCity = (index) => {
    const city = cities[Number(index)];
    if (city && side) side.innerHTML = countryCityDetailHtml(city);
    document.querySelectorAll("[data-country-city-index]").forEach((item) => item.classList.toggle("active", Number(item.getAttribute("data-country-city-index")) === Number(index)));
    if (detailMapControl) detailMapControl.setActive(Number(index));
  };
  document.querySelectorAll("[data-country-city-index]").forEach((node) => {
    node.addEventListener("click", () => {
      selectCity(Number(node.getAttribute("data-country-city-index")));
    });
  });
  requestAnimationFrame(() => {
    detailMapControl = mountCountryDetailMap(country, cities, selectedIndex, selectCity);
    if (selectedIndex >= 0) selectCity(selectedIndex);
  });
}

function openGeoCountryForItem(item) {
  const aggregate = currentCountryAggregate(item.country);
  if (aggregate) {
    openGeoCountry(aggregate, item);
    return;
  }
  openGeoCluster(item);
}

function isLeafletGeoActive() {
  return Boolean(geoLeafletMap && geoLeafletMarkerLayer);
}

function geoLeafletFitZoom(mapNode) {
  const width = mapNode?.clientWidth || $("geoMapStage")?.clientWidth || window.innerWidth || 1280;
  const coverWidthZoom = Math.log2(width / 256);
  return clamp(Math.floor(coverWidthZoom * 4) / 4, GEO_LEAFLET_HOME.zoom, 2.5);
}

function fitLeafletGeoHome() {
  if (!geoLeafletMap) return;
  geoLeafletMap.setMinZoom(1.5);
  geoLeafletMap.fitBounds(GEO_LEAFLET_HOME.bounds, { padding: [2, 2], animate: false });
  geoLeafletHomeZoom = geoLeafletMap.getZoom();
  geoLeafletMap.setMinZoom(geoLeafletHomeZoom);
}

function initLeafletGeoMap() {
  const mapNode = $("leafletGeoMap");
  const stage = $("geoMapStage");
  if (!mapNode || !stage || !window.L) return false;
  geoLeafletHomeZoom = geoLeafletFitZoom(mapNode);
  if (!geoLeafletMap) {
    geoLeafletMap = L.map(mapNode, {
      center: GEO_LEAFLET_HOME.center,
      zoom: geoLeafletHomeZoom,
      minZoom: 1.5,
      maxZoom: 22,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      maxBounds: [[-85, -180], [85, 180]],
      maxBoundsViscosity: 0.6,
      zoomControl: false,
      attributionControl: true,
    });
    addGeoBaseTiles(geoLeafletMap);
    L.control.zoom({ position: "bottomright" }).addTo(geoLeafletMap);
    geoLeafletMarkerLayer = L.layerGroup().addTo(geoLeafletMap);
    geoLeafletMap.on("resize", () => {
      fitLeafletGeoHome();
    });
    geoLeafletMap.on("click", (event) => {
      const aggregate = countryAggregateAtLatLng(event.latlng);
      if (aggregate) openGeoCountry(aggregate);
    });
  }
  stage.classList.add("uses-leaflet");
  setTimeout(() => {
    geoLeafletMap.invalidateSize();
    fitLeafletGeoHome();
  }, 0);
  return true;
}

function renderLeafletCountryLayer(geojson = geoWorldData) {
  if (!isLeafletGeoActive() || !window.L || !geojson) return;
  if (geoLeafletCountryLayer) {
    geoLeafletMap.removeLayer(geoLeafletCountryLayer);
    geoLeafletCountryLayer = null;
  }
  const aggregates = new Map(countryAggregatesForCurrentFilters().map((item) => [countryFeatureKey(item.country), item]));
  if (!aggregates.size) return;
  geoLeafletCountryLayer = L.geoJSON(geojson, {
    filter: (feature) => aggregates.has(countryFeatureKey(feature?.properties?.name || feature?.id || "")),
    style: {
      color: "rgba(74, 124, 142, 0.0)",
      weight: 0,
      fillColor: "#ffffff",
      fillOpacity: 0.01,
      interactive: true,
    },
    onEachFeature: (feature, layer) => {
      const name = feature?.properties?.name || feature?.id || "";
      const aggregate = aggregates.get(countryFeatureKey(name));
      if (!aggregate) return;
      layer.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        openGeoCountry(aggregate);
      });
      layer.on("mouseover", () => {
        layer.setStyle({ fillOpacity: 0.06, color: "rgba(74, 124, 142, 0.16)", weight: 1 });
      });
      layer.on("mouseout", () => {
        layer.setStyle({ fillOpacity: 0.01, color: "rgba(74, 124, 142, 0.0)", weight: 0 });
      });
    },
  }).addTo(geoLeafletMap);
  geoLeafletCountryLayer.bringToBack();
  if (typeof geoLeafletMarkerLayer.bringToFront === "function") geoLeafletMarkerLayer.bringToFront();
}

function geoLeafletRadius(item) {
  return sizeGeoItem(item, 1) * (geoMetric === "companies" ? 0.72 : 0.82);
}

function renderLeafletGeoPoints() {
  if (!isLeafletGeoActive()) return;
  if (geoWorldData) renderLeafletCountryLayer(geoWorldData);
  const layer = $("geoPointLayer");
  const labelLayer = $("geoLabelLayer");
  const filteredCompanies = (DATA.geo_companies || []).filter(geoCompanyPassesFilters);
  const items = aggregateGeoCompanies(filteredCompanies);
  renderGeoStats(filteredCompanies, items);
  geoLeafletMarkerLayer.clearLayers();
  hideGeoTooltip();
  if (labelLayer) labelLayer.innerHTML = "";
  if (layer) layer.innerHTML = "";
  if (!items.length) {
    if (layer) layer.innerHTML = `<div class="geo-empty">${geoBilingual("当前筛选无定位企业", "No mapped companies under current filters")}</div>`;
    return;
  }
  const maxMetric = Math.max(1, ...items.map(geoMetricValue));
  items.forEach((item) => {
    const coords = geoCoordinates(item);
    if (!coords) return;
    const metric = geoMetricValue(item);
    const color = geoMarkerColor(item);
    const radius = clamp(geoLeafletRadius(item), 5, 18);
    const marker = L.circleMarker([coords.lat, coords.lon], {
      radius,
      color: "#ffffff",
      weight: 1.8,
      fillColor: color,
      fillOpacity: clamp(0.68 + (metric / maxMetric) * 0.22, 0.72, 0.92),
      opacity: 0.96,
      bubblingMouseEvents: false,
      className: "leaflet-company-dot",
    });
    marker.bindTooltip(geoTooltipHtml(item), {
      className: "leaflet-geo-tooltip map-hover-tooltip",
      direction: "top",
      sticky: true,
      opacity: 1,
    });
    marker.on("mouseover", () => {
      marker.bringToFront();
      marker.setStyle({ weight: 2.6, fillOpacity: 0.96 });
    });
    marker.on("mouseout", () => {
      marker.setStyle({ weight: 1.8, fillOpacity: clamp(0.68 + (metric / maxMetric) * 0.22, 0.72, 0.92) });
    });
    marker.on("click", (event) => {
      L.DomEvent.stopPropagation(event);
      marker.closeTooltip();
      openGeoCountryForItem(item);
    });
    marker.addTo(geoLeafletMarkerLayer);
  });
}

function renderGeoPoints() {
  if (isLeafletGeoActive()) {
    renderLeafletGeoPoints();
    return;
  }
  const layer = $("geoPointLayer");
  const labelLayer = $("geoLabelLayer");
  if (!layer || !labelLayer) return;
  const filteredCompanies = (DATA.geo_companies || []).filter(geoCompanyPassesFilters);
  const sourcePoints = aggregateGeoCompanies(filteredCompanies);
  const items = positionGeoItems(sourcePoints, { jitter: false });
  renderGeoStats(filteredCompanies, items);
  if (!items.length) {
    layer.innerHTML = `<div class="geo-empty">${geoBilingual("当前筛选无定位企业", "No mapped companies under current filters")}</div>`;
    labelLayer.innerHTML = "";
    hideGeoTooltip();
    return;
  }
  const maxMetric = Math.max(1, ...items.map(geoMetricValue));
  layer.innerHTML = items
    .map((item, index) => {
      const metric = geoMetricValue(item);
      const size = sizeGeoItem(item, maxMetric);
      const intensity = clamp((metric / maxMetric) * 100, 34, 100);
      const color = geoMarkerColor(item);
      return `
        <button class="geo-point geo-city-dot"
          type="button"
          style="left:${item._x.toFixed(3)}%;top:${item._y.toFixed(3)}%;--jx:0px;--jy:0px;--geo-size:${size.toFixed(1)}px;--geo-intensity:${intensity.toFixed(1)}%;--geo-z:${Math.max(8, Math.round(size * 2))};--geo-color:${color};--geo-delay:${(index % 13) * 0.12}s"
          aria-label="${escapeHtml(item.name)} ${geoCompanyCountText(item.company_count)} ${geoProductLineText(item.product_count)}"></button>
      `;
    })
    .join("");

  layer.querySelectorAll(".geo-point").forEach((node, index) => {
    const item = items[index];
    node.addEventListener("mouseenter", () => showGeoTooltip(item, node));
    node.addEventListener("focus", () => showGeoTooltip(item, node));
    node.addEventListener("mouseleave", hideGeoTooltip);
    node.addEventListener("blur", hideGeoTooltip);
    node.addEventListener("click", () => openGeoCluster(item));
  });

  labelLayer.innerHTML = "";
}

function renderGeoStats(filteredCompanies = null, filteredPoints = null) {
  const summary = DATA.geo_summary || {};
  if (!filteredCompanies || !filteredPoints) {
    setText("geoMappedCompanies", fmt(summary.mapped_companies));
    setText("geoCityPrecision", fmt(summary.city_precision));
    setText("geoCountryFallback", fmt(summary.country_precision));
    setText("geoUniquePoints", fmt(summary.unique_geo_points));
    return;
  }
  setText("geoMappedCompanies", fmt(filteredCompanies.length));
  setText("geoCityPrecision", fmt(filteredCompanies.filter((item) => item.precision === "city").length));
  setText("geoCountryFallback", fmt(filteredCompanies.filter((item) => item.precision !== "city").length));
  setText("geoUniquePoints", fmt(filteredPoints.length));
}

function renderGeoTrackLegend() {
  const node = $("geoTrackLegend");
  if (!node) return;
  const companies = DATA.geo_companies || [];
  const rows = countValues(companies, "primary_track")
    .filter(([track]) => track && track !== "Unknown")
    .sort((a, b) => b[1] - a[1]);
  const keys = rows.map(([track]) => [geoMapLabel(track), geoTrackColor(track)]);
  node.innerHTML = `
    <div class="map-legend-copy">
      <strong>颜色=赛道</strong>
      <span>大小=${geoMetric === "companies" ? "企业数" : "产品线"}</span>
    </div>
    <div class="map-track-buttons">
      ${keys
        .map(
          ([label, color]) => `
            <span class="map-track-key" style="--track-color:${color}">
              <i></i><span>${escapeHtml(label)}</span>
            </span>
          `,
        )
        .join("")}
    </div>
  `;
}

function wireGeoMetricControls() {
  document.querySelectorAll("[data-geo-metric]").forEach((button) => {
    button.classList.toggle("active", button.dataset.geoMetric === geoMetric);
    button.addEventListener("click", () => {
      geoMetric = button.dataset.geoMetric || "products";
      document.querySelectorAll("[data-geo-metric]").forEach((item) => item.classList.toggle("active", item === button));
      renderGeoTrackLegend();
      renderGeoPoints();
    });
  });
}

function renderGeoFilterControls() {
  const companies = DATA.geo_companies || [];
  setSelectOptions("geoTrackFilter", "All tracks", countValues(companies, "primary_track"), geoFilters.track, geoMapLabel);
  setSelectOptions("geoRegionFilter", "All regions", countValues(companies, "region"), geoFilters.region, geoMapLabel);
  setSelectOptions(
    "geoListingFilter",
    "All companies",
    [["listed", companies.filter(isListedGeoCompany).length]],
    geoFilters.listing,
    geoMapLabel,
  );
  setSelectOptions(
    "geoEvidenceFilter",
    "All evidence",
    [
      ["FDA", companies.filter((item) => geoCompanyEvidence(item).includes("FDA")).length],
      ["CE", companies.filter((item) => geoCompanyEvidence(item).includes("CE")).length],
    ],
    geoFilters.evidence,
    geoMapLabel,
  );
  renderGeoTrackLegend();
}

function wireGeoFilterControls() {
  [
    ["geoTrackFilter", "track"],
    ["geoRegionFilter", "region"],
    ["geoListingFilter", "listing"],
    ["geoEvidenceFilter", "evidence"],
  ].forEach(([id, key]) => {
    const node = $(id);
    if (!node) return;
    node.addEventListener("change", () => {
      geoFilters[key] = node.value || "all";
      if (key === "track") renderGeoTrackLegend();
      renderGeoPoints();
    });
  });
}

function isGeoStageControl(target) {
  return Boolean(target.closest(".geo-point, path.has-geo-data, .map-zoom-tools, .map-track-legend, button, select, input, a"));
}

function wireGeoZoomControls() {
  const stage = $("geoMapStage");
  const reset = $("geoResetZoom");
  if (reset && !reset.dataset.geoResetWired) {
    reset.addEventListener("click", resetGeoZoom);
    reset.dataset.geoResetWired = "1";
  }
  if (!stage || isLeafletGeoActive()) return;
  if (stage.dataset.geoZoomWired) return;
  stage.dataset.geoZoomWired = "1";
  stage.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const multiplier = Math.exp(-event.deltaY * 0.0013);
      zoomGeoAt(event.clientX, event.clientY, geoZoom.scale * multiplier);
    },
    { passive: false },
  );
  stage.addEventListener("pointerdown", (event) => {
    if (event.button !== 0 || geoZoom.scale <= 1.01 || isGeoStageControl(event.target)) return;
    geoZoom.dragging = true;
    geoZoom.dragStartX = event.clientX;
    geoZoom.dragStartY = event.clientY;
    geoZoom.startX = geoZoom.x;
    geoZoom.startY = geoZoom.y;
    stage.classList.add("is-dragging");
    stage.setPointerCapture?.(event.pointerId);
  });
  stage.addEventListener("pointermove", (event) => {
    if (!geoZoom.dragging) return;
    geoZoom.x = geoZoom.startX + event.clientX - geoZoom.dragStartX;
    geoZoom.y = geoZoom.startY + event.clientY - geoZoom.dragStartY;
    applyGeoZoom();
  });
  const stopDrag = (event) => {
    if (!geoZoom.dragging) return;
    geoZoom.dragging = false;
    stage.classList.remove("is-dragging");
    stage.releasePointerCapture?.(event.pointerId);
  };
  stage.addEventListener("pointerup", stopDrag);
  stage.addEventListener("pointercancel", stopDrag);
  window.addEventListener("resize", applyGeoZoom);
  applyGeoZoom();
}

function renderGeoMap() {
  if (!$("geoMapStage")) return;
  const usingLeaflet = initLeafletGeoMap();
  renderGeoStats();
  renderGeoFilterControls();
  wireGeoMetricControls();
  wireGeoFilterControls();
  wireGeoZoomControls();
  renderGeoPoints();
  fetch("./world.geojson")
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((geojson) => {
      renderWorldMap(geojson);
      if (usingLeaflet) renderLeafletCountryLayer(geojson);
    })
    .catch(renderFallbackWorldMap);
}

function renderKpis() {
  const summary = DATA.summary || {};
  setText("generatedAt", formatUpdatedAt(DATA.generated_at));
  setText("kpiProducts", fmt(summary.products));
  setText("kpiCompanies", fmt(summary.companies));
  setText("kpiBrands", fmt(summary.brands));
  setText("kpiCountries", fmt(displayCountryCount(summary)));
  setText("kpiIndications", fmt(summary.indication_signals));
  setText("kpiSubtracks", fmt(summary.subtrack_signals));
  setText("kpiPublic", fmt(summary.public_companies));
}

function renderSeedNotice() {
  const node = $("seedNoticeStats");
  if (!node) return;
  const summary = DATA.summary || {};
  const workbench = DATA.verification_workbench || {};
  const registration = DATA.registration_evidence || {};
  const background = workbench.company_background || {};
  const cePlan = workbench.mdr_ce_plan || {};
  const stats = [
    [`${fmt(summary.company_official_source_evidence || background.official_source_evidence_rows || 0)}`, "官方来源"],
    [`${fmt(registration.official_api_rows || summary.registration_evidence || 0)}`, "FDA/注册记录"],
    [`${fmt(DATA.official_indication_analysis?.rows || summary.official_indication_rows || 0)}`, "官方适应症"],
    [`${fmt(summary.mdr_ce_search_plan || cePlan.rows || 0)}`, "MDR/CE 路径"],
  ];
  node.innerHTML = stats.map(([value, label]) => `<b>${value}</b><span>${label}</span>`).join("");
}

function renderSegments() {
  const node = $("segmentGrid");
  if (!node) return;
  if (hasMaterialTaxonomyStructure()) {
    const rows = taxonomyL1Rows();
    const selected = selectedTaxonomyL1();
    node.innerHTML = rows
      .map((group) => {
        const active = selected?.id === group.id;
        const heatRows = (group.top_l2 || []).slice(0, 8);
        const cardHeatScale = buildHeatScale(heatRows.map((row) => row.products || row.value));
        const topL2Names = heatRows.slice(0, 4).map((row) => row.name).join(" · ");
        const heatCells = heatRows
          .map((row) => {
            const label = `${group.name} / ${row.name} / ${fmt(row.products || row.value)}`;
            return `
              <a class="subtrack-heat-cell taxonomy-preview-cell" href="#segmentDeepDive" data-taxonomy-l1="${escapeHtml(group.id)}" style="${heatCellStyle(row.products || row.value, cardHeatScale)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
                <span>${escapeHtml(group.name)}</span>
                <b>${escapeHtml(row.name)}</b>
                <strong>${fmt(row.products || row.value)}</strong>
              </a>
            `;
          })
          .join("");
        return `
          <article class="track-group-card taxonomy-l1-card ${active ? "is-active" : ""}" id="taxonomy-${escapeHtml(group.id)}" style="--segment:${group.color || "var(--brand)"}">
            <a class="group-main taxonomy-l1-trigger" href="#segmentDeepDive" data-taxonomy-l1="${escapeHtml(group.id)}" aria-current="${active ? "true" : "false"}">
              <div>
                <h4>${escapeHtml(group.name)}</h4>
              </div>
              <span class="group-arrow">→</span>
            </a>
            <div class="segment-metrics group-metrics">
              <span class="metric-chip"><strong>${fmt(group.products)}</strong><span>产品线</span></span>
              <span class="metric-chip block-chip"><strong>${escapeHtml(topL2Names || "二级待补")}</strong><span>二级类目</span></span>
              <span class="metric-chip"><strong>${fmt(group.l2_count)}</strong><span>二级数</span></span>
            </div>
            <div class="subtrack-heat-shell" aria-label="${escapeHtml(group.name)} secondary taxonomy distribution">
              <div class="subtrack-heat-grid">
                ${heatCells}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
    node.querySelectorAll("[data-taxonomy-l1]").forEach((element) => {
      element.addEventListener("click", (event) => {
        event.preventDefault();
        activateTaxonomyL1(element.dataset.taxonomyL1, { scroll: true });
      });
    });
    return;
  }
  const groupRows = TRACK_GROUPS.map((group) => ({ group, heatRows: groupSubtrackHeatRows(group) }));
  node.innerHTML = groupRows.map(({ group, heatRows }) => {
      const totals = groupTotals(group);
      const firstSegment = group.segments.map(segmentByCode).find(Boolean);
      const groupHref = group.segments.length > 1 ? segmentUrl(group.id) : firstSegment ? segmentUrl(firstSegment.code) : "#segments";
      const cardHeatScale = buildHeatScale(heatRows.map((row) => row.value));
      const heatCells = heatRows
        .map((row) => {
          const parent = displayName(row.segment);
          const label = `${parent} / ${row.name} / ${fmt(row.value)}`;
          return `
            <a class="subtrack-heat-cell" href="${segmentUrl(row.segment.code, row.name)}" style="${heatCellStyle(row.value, cardHeatScale)}" title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
              <span>${bilingualMarkup(parent, "heat-parent-label")}</span>
              <b>${bilingualMarkup(row.name, "heat-subtrack-label")}</b>
              <strong>${fmt(row.value)}</strong>
            </a>
          `;
        })
        .join("");
      return `
        <article class="track-group-card" id="group-${group.id}" style="--segment:${group.color}">
          <a class="group-main" href="${groupHref}">
            <div>
              <h4>${bilingualMarkup(group.name, "group-title-bilingual")}</h4>
            </div>
            <span class="group-arrow">→</span>
          </a>
          <div class="segment-metrics group-metrics">
            <span class="metric-chip"><strong>${fmt(totals.products)}</strong><span>${bilingualMarkup("产品线 / Product lines")}</span></span>
            <span class="metric-chip block-chip"><strong>${escapeHtml(group.blockNote || group.note || "")}</strong><span>${bilingualMarkup("细分板块 / Blocks")}</span></span>
            <span class="metric-chip"><strong>${fmt(totals.subtracks)}</strong><span>${bilingualMarkup("子赛道 / Sub-tracks")}</span></span>
          </div>
          <div class="subtrack-heat-shell" aria-label="${escapeHtml(group.name)} bottom-level subtracks heatmap">
            <div class="subtrack-heat-grid">
              ${heatCells}
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderDonut(id) {
  const node = $(id);
  if (!node) return;
  const taxonomyRows = hasMaterialTaxonomyStructure() ? taxonomyL1Rows() : [];
  const rows = taxonomyRows.length ? taxonomyRows : visibleSegments();
  const total = rows.reduce((sum, item) => sum + Number(item.products || item.value || 0), 0) || 1;
  const compact = node.classList.contains("compact-donut");
  let cursor = 0;
  const slices = rows
    .map((item) => {
      const start = cursor;
      cursor += (Number(item.products || item.value || 0) / total) * 100;
      return `${item.color} ${start.toFixed(2)}% ${cursor.toFixed(2)}%`;
    })
    .join(",");
  const legend = rows
    .slice(0, 8)
    .map(
      (item) => `
        <li><span><i style="--item-color:${item.color}"></i><b>${escapeHtml(taxonomyRows.length ? item.name : compact ? compactLegendName(item) : displayName(item))}</b></span><strong>${fmt(item.products || item.value)}</strong></li>
      `,
    )
    .join("");
  node.innerHTML = `<div class="donut" style="--slices:${slices}"></div><ul class="legend-list">${legend}</ul>`;
}

function compactLegendName(segment) {
  const name = displayName(segment);
  const parts = bilingualParts(name);
  return parts.zh || name;
}

function matrixCellTooltip(row, segment, value) {
  const examples = (row.examples?.[segment.code] || []).filter(Boolean);
  if (examples.length) {
    const item = examples[0];
    return typeof item === "string" ? item : item.label || [item.brand, item.product, item.manufacturer || item.holder].filter(Boolean).join(" / ");
  }
  return `${row.company} / ${segment.name} / ${fmt(value)} 条产品线`;
}

function showMatrixTooltip(cell) {
  const tooltip = $("matrixHoverTooltip");
  const wrap = $("companyMatrix");
  if (!tooltip || !wrap) return;
  const text = cell.dataset.tooltip || "";
  tooltip.innerHTML = `<i></i><span>${escapeHtml(text).replace(/\n/g, "<br />")}</span>`;
  tooltip.hidden = false;
  const wrapRect = wrap.getBoundingClientRect();
  const cellRect = cell.getBoundingClientRect();
  const tooltipRect = tooltip.getBoundingClientRect();
  const left = clamp(cellRect.right - wrapRect.left + 10, 8, Math.max(8, wrapRect.width - tooltipRect.width - 8));
  const top = clamp(cellRect.top - wrapRect.top + cellRect.height / 2 - tooltipRect.height / 2, 8, Math.max(8, wrapRect.height - tooltipRect.height - 8));
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function hideMatrixTooltip() {
  const tooltip = $("matrixHoverTooltip");
  if (tooltip) tooltip.hidden = true;
}

function renderMatrix() {
  const node = $("companyMatrix");
  if (!node) return;
  const headers = visibleSegments().map((item) => ({ code: item.code, name: displayName(item), color: item.color }));
  const rows = (DATA.company_matrix || []).slice(0, 24);
  const heatScale = buildHeatScale(rows.flatMap((row) => headers.map((h) => row.segments?.[h.code] || 0)));
  const columnTotals = new Map(
    headers.map((item) => [item.code, rows.reduce((sum, row) => sum + Number(row.segments?.[item.code] || 0), 0)]),
  );
  const head = `
    <div class="matrix-head">
      <div class="matrix-name matrix-corner">企业 / Company</div>
      ${headers
        .map(
          (item) => `
            <div class="matrix-label">
              <span>${escapeHtml(item.name)}</span>
              <em>${fmt(columnTotals.get(item.code) || 0)}</em>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
  const body = rows
    .map((row) => {
      const coveredSegments = headers.reduce((sum, item) => sum + (Number(row.segments?.[item.code] || 0) > 0 ? 1 : 0), 0);
      const cells = headers
        .map((item) => {
          const value = row.segments?.[item.code] || 0;
          const tooltip = matrixCellTooltip(row, item, value);
          return `
            <div class="matrix-cell">
              ${
                value
                  ? `<button class="heat-cell heatmap-tile has-value" type="button" style="${heatCellStyle(value, heatScale)}" data-tooltip="${escapeHtml(tooltip)}" aria-label="${escapeHtml(tooltip)}">${fmt(value)}</button>`
                  : `<span class="heat-cell heatmap-tile is-zero" style="${heatCellStyle(value, heatScale)}" aria-hidden="true"></span>`
              }
            </div>
          `;
        })
        .join("");
      return `
        <div class="matrix-row">
          <div class="matrix-name">
            <strong>${escapeHtml(row.company)}</strong>
            <span class="matrix-row-badges" title="${escapeHtml(`${fmt(row.total)} product lines; ${fmt(coveredSegments)} covered tracks`)}">
              <em>${fmt(row.total)}</em>
              <em class="coverage-badge">${fmt(coveredSegments)}赛道</em>
            </span>
          </div>
          ${cells}
        </div>
      `;
    })
    .join("");
  node.innerHTML = `
    <div class="matrix-title">
      <h3>企业 × 产品形态覆盖 / Company × Product-Form Coverage</h3>
    </div>
    ${heatmapLegendMarkup(heatScale)}
    <div class="matrix-grid nature-heatmap-grid company-product-matrix crystal-heatmap-grid" style="--matrix-cols:${headers.length};--matrix-row-min:204px;--matrix-row-col:276px;--matrix-col-min:42px;--matrix-col-max:58px">${head}${body}</div>
    <div id="matrixHoverTooltip" class="matrix-hover-tooltip" hidden></div>
  `;
  node.querySelectorAll(".heat-cell.has-value").forEach((cell) => {
    cell.addEventListener("mouseenter", () => showMatrixTooltip(cell));
    cell.addEventListener("focus", () => showMatrixTooltip(cell));
    cell.addEventListener("mouseleave", hideMatrixTooltip);
    cell.addEventListener("blur", hideMatrixTooltip);
  });
}

const MARKET_TYPE_LABELS = {
  procedures_total: "治疗数量",
  procedure_count: "治疗数量",
  market_size: "市场规模",
  market_size_forecast: "预测规模",
  market_forecast: "预测规模",
  CAGR: "年复合增长",
  cagr: "年复合增长",
  market_share: "市场份额",
  product_share_HA_revitalizers: "产品份额",
  product_share: "产品份额",
  market_growth: "增长排序",
  procedure_volume: "治疗数量",
  estimated_plastic_surgeons: "医生数",
  investment: "投资额",
  device_units: "设备销量",
};

const MARKET_UNIT_LABELS = {
  cases: "例",
  procedures: "例",
  surgeons: "名医生",
  "million USD": "百万美元",
  "usd million": "百万美元",
  "billion USD": "十亿美元",
  "usd billion": "十亿美元",
  "USD Billion": "十亿美元",
  "%": "%",
  rank: "排名",
};
const MARKET_TYPE_DISPLAY_LABELS = {
  治疗数量: "治疗数量 / Treatments",
  市场规模: "市场规模 / Market size",
  预测规模: "预测规模 / Forecast size",
  年复合增长: "年复合增长 / CAGR",
  市场份额: "市场份额 / Market share",
  产品份额: "产品份额 / Product share",
  增长排序: "增长排序 / Growth ranking",
  医生数: "医生数 / Surgeons",
  投资额: "投资额 / Investment",
  设备销量: "设备销量 / Device units",
};

function marketTypeLabel(item) {
  const key = String(item.type || item.data_type || "").trim();
  if (MARKET_TYPE_LABELS[key]) return MARKET_TYPE_LABELS[key];
  if (/forecast/i.test(key)) return "预测规模";
  if (/cagr|compound/i.test(key)) return "年复合增长";
  if (/share/i.test(key)) return "市场份额";
  if (/procedure|case/i.test(key)) return "治疗数量";
  if (/market|size/i.test(key)) return "市场规模";
  return zhLabel(key || "市场指标");
}

function marketTypeDisplayLabel(item) {
  const label = marketTypeLabel(item);
  return MARKET_TYPE_DISPLAY_LABELS[label] || zhLabel(label);
}

function marketUnitLabel(unit) {
  const text = String(unit || "").trim();
  return MARKET_UNIT_LABELS[text] || MARKET_UNIT_LABELS[text.toLowerCase()] || text;
}

function marketValueText(item) {
  if (item.value === null || item.value === undefined || item.value === "") return marketTypeLabel(item);
  const unit = marketUnitLabel(item.unit);
  const value = fmt(item.value);
  return unit === "%" ? `${value}%` : `${value}${unit ? ` ${unit}` : ""}`;
}

function marketCategoryLabel(item) {
  const raw = String(item.category || item.category_l1 || item.category_l2 || item.category_l3 || "").trim();
  if (!raw || raw.toLowerCase() === "total") return "综合市场";
  const text = raw
    .replace(/all procedures/gi, "全部项目")
    .replace(/surgical procedures/gi, "外科手术")
    .replace(/non-surgical procedures/gi, "非手术项目")
    .replace(/injectables/gi, "注射项目")
    .replace(/facial rejuvenation/gi, "面部年轻化")
    .replace(/other non-surgical/gi, "其他非手术")
    .replace(/workforce/gi, "医生供给")
    .replace(/aesthetic medicine/gi, "医美市场")
    .replace(/medical aesthetics/gi, "医疗美容")
    .replace(/mesotherapy products/gi, "中胚层产品")
    .replace(/botulinum toxin/gi, "肉毒毒素")
    .replace(/hyaluronic acid/gi, "玻尿酸")
    .replace(/calcium hydroxylapatite/gi, "CaHA")
    .replace(/poly-l-lactic acid/gi, "PLLA")
    .replace(/hair removal/gi, "脱毛")
    .replace(/chemical peel/gi, "化学换肤")
    .replace(/non-surgical skin tightening/gi, "非手术紧肤")
    .replace(/non-surgical fat reduction/gi, "非手术减脂")
    .replace(/tattoo removal/gi, "纹身去除")
    .replace(/dermal filler/gi, "填充剂")
    .replace(/skin tightening devices/gi, "紧肤设备")
    .replace(/cheek augmentation/gi, "面颊填充/塑形");
  return zhLabel(text);
}

function marketDefinition(item) {
  const type = marketTypeLabel(item);
  if (type === "治疗数量") return "年度调查或报告统计的治疗/手术数量，需注意是否包含外科与非外科项目。";
  if (type === "医生数") return "协会或公开报告估算的整形外科医生数量，用于观察地区供给与市场承载能力。";
  if (type === "市场规模") return "报告口径下某区域或细分品类在对应年份的市场收入、销售额或规模。";
  if (type === "预测规模") return "研究机构对未来年份市场规模的预测，适合看空间，不等同于已发生销售额。";
  if (type === "年复合增长") return "预测区间的复合年增长率，非单一年份同比增长。";
  if (type === "市场份额" || type === "产品份额") return "某区域、产品形态或细分赛道在报告定义市场中的占比。";
  if (type === "投资额") return "公开报告或调研口径中的市场投入、支出或资本开支指标。";
  return "公开报告、调研或资料库提取的市场观察指标，展示时需同时保留来源与口径。";
}

function marketSourceText(item) {
  return [item.source, item.title].filter(Boolean).join(" · ") || "来源待补充 / Source pending";
}

function marketMetricScore(item) {
  const source = String(item.source || item.title || "").toLowerCase();
  const year = Number.parseInt(String(item.year || "").match(/\d{4}/)?.[0] || "0", 10);
  let score = item.value !== null && item.value !== undefined ? 50 : 0;
  if (item.url) score += 35;
  if (/isaps|asps/.test(source)) score += 55;
  if (/grand view|gminsights|imarc|precedence|astute|globenewswire|sns insider|data m|triton/.test(source)) score += 25;
  if (/forecast|cagr|share|growth/i.test(String(item.type || ""))) score += 10;
  if (year >= 2025) score += 12;
  else if (year >= 2023) score += 6;
  return score;
}

function isBroadAestheticMarket(item) {
  const text = [item.category, item.title, item.source].filter(Boolean).join(" ").toLowerCase();
  return /(aesthetic medicine|medical aesthetics|医美市场|医疗美容)/.test(text);
}

function selectMarketMetrics(limit = 10) {
  const pool = (DATA.market_metrics || [])
    .map((item, index) => ({ ...item, _index: index, _score: marketMetricScore(item) }))
    .filter((item) => item.value !== null && item.value !== undefined)
    .sort((a, b) => {
      const ay = Number.parseInt(String(a.year || "").match(/\d{4}/)?.[0] || "0", 10);
      const by = Number.parseInt(String(b.year || "").match(/\d{4}/)?.[0] || "0", 10);
      return b._score - a._score || by - ay || a._index - b._index;
    });
  const picked = [];
  const seen = new Set();
  const addWhere = (count, predicate) => {
    pool.forEach((item) => {
      if (picked.length >= limit || count <= 0 || seen.has(item._index) || !predicate(item)) return;
      picked.push(item);
      seen.add(item._index);
      count -= 1;
    });
  };
  addWhere(3, (item) => /isaps|asps/i.test(String(item.source || "")) && marketTypeLabel(item) === "治疗数量");
  addWhere(1, (item) => marketTypeLabel(item) === "市场规模" && isBroadAestheticMarket(item) && /全球|global/i.test(String(item.geo || "")) && Number(item.year || 0) <= 2026);
  addWhere(1, (item) => marketTypeLabel(item) === "预测规模" || (marketTypeLabel(item) === "市场规模" && isBroadAestheticMarket(item) && /全球|global/i.test(String(item.geo || "")) && Number(item.year || 0) >= 2032));
  addWhere(1, (item) => marketTypeLabel(item) === "市场规模" && !isBroadAestheticMarket(item) && /全球|global/i.test(String(item.geo || "")) && Number(item.year || 0) <= 2026);
  addWhere(1, (item) => marketTypeLabel(item) === "年复合增长");
  addWhere(2, (item) => marketTypeLabel(item) === "市场份额" || marketTypeLabel(item) === "产品份额");
  addWhere(1, (item) => ["投资额", "设备销量"].includes(marketTypeLabel(item)));
  addWhere(limit - picked.length, (item) => !seen.has(item._index));
  return picked.slice(0, limit);
}

const MARKET_COUNTRY_META = {
  "United States": { zh: "美国", region: "North America", x: 20, y: 45 },
  Brazil: { zh: "巴西", region: "Latin America", x: 34, y: 70 },
  Japan: { zh: "日本", region: "Asia-Pacific", x: 84, y: 44 },
  Italy: { zh: "意大利", region: "Europe", x: 52, y: 43 },
  Germany: { zh: "德国", region: "Europe", x: 50, y: 38 },
  Mexico: { zh: "墨西哥", region: "North America", x: 20, y: 56 },
  India: { zh: "印度", region: "Asia-Pacific", x: 71, y: 54 },
  Turkiye: { zh: "土耳其", region: "Europe / Middle East", x: 57, y: 46 },
  France: { zh: "法国", region: "Europe", x: 48, y: 42 },
  "Chinese Taipei": { zh: "中国台湾", region: "Asia-Pacific", x: 79, y: 51 },
  Spain: { zh: "西班牙", region: "Europe", x: 46, y: 46 },
  Greece: { zh: "希腊", region: "Europe", x: 54, y: 47 },
  Argentina: { zh: "阿根廷", region: "Latin America", x: 32, y: 80 },
  Colombia: { zh: "哥伦比亚", region: "Latin America", x: 27, y: 63 },
  Thailand: { zh: "泰国", region: "Asia-Pacific", x: 75, y: 58 },
  Australia: { zh: "澳大利亚", region: "Asia-Pacific", x: 83, y: 78 },
  "South Korea": { zh: "韩国", region: "Asia-Pacific", x: 82, y: 43 },
};

function marketSourceLabel(item) {
  return [item.source, item.year].filter(Boolean).join(" · ") || "Source pending";
}

function marketShortValue(value, unit = "") {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (String(unit).trim() === "%") return `${number.toFixed(number >= 10 ? 0 : 1)}%`;
  if (number >= 1000000) return `${(number / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}万`;
  if (number >= 10000) return `${(number / 10000).toLocaleString("zh-CN", { maximumFractionDigits: 1 })}万`;
  return fmt(number);
}

function isProcedureMetric(item) {
  return marketTypeLabel(item) === "治疗数量" && Number.isFinite(Number(item.value));
}

function isGlobalGeo(item) {
  return /^(global|全球)$/i.test(String(item.geo || "").trim());
}

function isCountryTotalProcedure(item) {
  const category = String(item.category || "").toLowerCase();
  return isProcedureMetric(item)
    && !isGlobalGeo(item)
    && /all procedures/.test(category)
    && /country total|total surgical and non-surgical|total procedures|total$/i.test(category);
}

function marketProcedurePool() {
  const isapsRows = (DATA.market_metrics || []).filter(
    (item) => isProcedureMetric(item) && /isaps|asps/i.test([item.source, item.title, item.source_file].filter(Boolean).join(" ")),
  );
  const latestYear = Math.max(...isapsRows.map((item) => Number.parseInt(item.year || "0", 10)).filter(Boolean));
  return isapsRows.filter((item) => Number.parseInt(item.year || "0", 10) === latestYear);
}

function findGlobalProcedure(pool, pattern) {
  return pool.find((item) => isGlobalGeo(item) && pattern.test(String(item.category || "")));
}

function marketProcedureInsights() {
  const pool = marketProcedurePool();
  const total = findGlobalProcedure(pool, /all procedures/i);
  const surgical = findGlobalProcedure(pool, /^surgical procedures/i);
  const nonsurgical = findGlobalProcedure(pool, /^non-surgical procedures/i);
  const countries = pool
    .filter(isCountryTotalProcedure)
    .map((item) => ({ ...item, _meta: MARKET_COUNTRY_META[item.geo] || null }))
    .filter((item) => item._meta)
    .sort((a, b) => Number(b.value || 0) - Number(a.value || 0));
  return {
    pool,
    year: total?.year || surgical?.year || nonsurgical?.year || countries[0]?.year || "",
    source: total?.source || surgical?.source || nonsurgical?.source || countries[0]?.source || "ISAPS",
    total,
    surgical,
    nonsurgical,
    countries,
  };
}

function marketProcedureStack(total, surgical, nonsurgical) {
  const totalValue = Number(total?.value || 0) || Number(surgical?.value || 0) + Number(nonsurgical?.value || 0);
  if (!totalValue) return "";
  const sValue = Number(surgical?.value || 0);
  const nValue = Number(nonsurgical?.value || 0);
  const sPct = Math.max(0, Math.min(100, (sValue / totalValue) * 100));
  const nPct = Math.max(0, Math.min(100, (nValue / totalValue) * 100));
  return `
    <div class="market-procedure-stack" title="${escapeHtml(`Surgical ${fmt(sValue)} / Non-surgical ${fmt(nValue)}`)}">
      <div class="market-stack-track">
        <i class="surgical" style="--w:${sPct}%"></i>
        <i class="nonsurgical" style="--w:${nPct}%"></i>
      </div>
      <div class="market-stack-legend">
        <span><b></b>外科手术<em>Surgical</em><strong>${marketShortValue(sValue)}</strong></span>
        <span><b></b>非外科治疗<em>Non-surgical</em><strong>${marketShortValue(nValue)}</strong></span>
      </div>
    </div>
  `;
}

function marketProcedureMap(countries) {
  if (!countries.length) return "";
  const maxValue = Math.max(...countries.map((item) => Number(item.value || 0)));
  const dots = countries
    .slice(0, 12)
    .map((item) => {
      const meta = item._meta;
      const value = Number(item.value || 0);
      const size = 8 + Math.sqrt(value / Math.max(maxValue, 1)) * 19;
      const label = `${meta.zh} / ${item.geo}: ${fmt(value)} treatments`;
      return `
        <span class="market-map-dot" style="--x:${meta.x}%;--y:${meta.y}%;--s:${size}px" title="${escapeHtml(label)}">
          <i></i>
        </span>
      `;
    })
    .join("");
  return `
    <div class="market-procedure-map" aria-label="Top country treatment count map">
      <div class="market-map-grid"></div>
      ${dots}
    </div>
  `;
}

function marketCountryBars(countries) {
  const top = countries.slice(0, 6);
  const maxValue = Math.max(...top.map((item) => Number(item.value || 0)), 1);
  return `
    <div class="market-country-bars">
      ${top
        .map((item) => {
          const meta = item._meta || { zh: item.geo };
          const width = Math.max(8, (Number(item.value || 0) / maxValue) * 100);
          return `
            <div class="market-country-row" title="${escapeHtml(`${meta.zh} / ${item.geo}: ${fmt(item.value)} treatments`)}">
              <span><strong>${escapeHtml(meta.zh)}</strong><em>${escapeHtml(item.geo)}</em></span>
              <i><b style="--w:${width}%"></b></i>
              <strong>${escapeHtml(marketShortValue(item.value))}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderMarketMetricsPanel() {
  const { total, surgical, nonsurgical, countries, year, source } = marketProcedureInsights();
  if (!total && !countries.length) {
    return selectMarketMetrics(6)
      .map((item) => {
        const value = escapeHtml(marketValueText(item));
        const tooltip = escapeHtml(marketMetricTooltip(item));
        const tag = item.url ? "a" : "div";
        const href = item.url ? ` href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer"` : "";
        return `
          <${tag} class="metric-row market-metric-row"${href} data-tooltip="${tooltip}" title="${tooltip}">
            <span class="metric-main">
              <strong>${value}</strong>
              <em>${escapeHtml(marketTypeDisplayLabel(item))}</em>
            </span>
            <span class="metric-meta">
              <b>${escapeHtml(zhLabel(item.geo || "Global"))} · ${escapeHtml(item.year || "")}</b>
              <small>${escapeHtml(item.source || "来源待补充 / Source pending")}</small>
            </span>
          </${tag}>
        `;
      })
      .join("") || `<p class="empty-state">暂无数据 / No data</p>`;
  }
  return `
    <div class="market-visual-panel">
      <div class="market-procedure-hero" title="${escapeHtml(marketMetricTooltip(total || countries[0]))}">
        <span>治疗数量<em>Treatments</em></span>
        <strong>${escapeHtml(marketShortValue(total?.value || countries.reduce((sum, item) => sum + Number(item.value || 0), 0)))}</strong>
        <small>${escapeHtml([zhLabel(total?.geo || "Global"), year, source].filter(Boolean).join(" · "))}</small>
      </div>
      ${marketProcedureStack(total, surgical, nonsurgical)}
      ${marketProcedureMap(countries)}
      ${marketCountryBars(countries)}
    </div>
  `;
}

function marketMetricTooltip(item) {
  return [
    `定义 / Definition：${marketDefinition(item)}`,
    `范围 / Scope：${marketCategoryLabel(item)} / ${zhLabel(item.geo || "Global")} / ${item.year || "年份待补充 / Year pending"}`,
    `来源 / Source：${marketSourceText(item)}`,
    item.confidence ? `置信度 / Confidence：${item.confidence}` : "",
    item.url ? `链接 / Link：${item.url}` : "链接待补 / Public link pending",
    item.source_file ? `文件 / File：${item.source_file}` : "",
    item.note ? `备注 / Note：${item.note}` : "",
  ]
    .filter(Boolean)
    .join("\n");
}

function caseStatMarkup(label, value, note = "") {
  return `
    <div class="company-case-stat">
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
      ${note ? `<em>${escapeHtml(note)}</em>` : ""}
    </div>
  `;
}

function caseStatusLabel(value = "") {
  const text = String(value || "").toLowerCase();
  if (text.includes("manual_reference")) return "官网组合样本";
  return "组合分析";
}

function caseTitleLabel(value = "") {
  const text = String(value || "");
  const lower = text.toLowerCase();
  if (lower.includes("brand") && lower.includes("portfolio")) return "品牌 × 产品组合";
  if (lower.includes("portfolio") && lower.includes("indication")) return "组合 × 应用方向";
  if (lower.includes("portfolio") && lower.includes("area")) return "组合 × 治疗部位";
  return text.replace(/\bcommercial indication signals\b/gi, "应用方向").replace(/\btreatment-area signals\b/gi, "治疗部位");
}

function renderCompanyPortfolioCases() {
  const node = $("companyPortfolioCases");
  if (!node) return;
  const cases = DATA.company_portfolio_cases || [];
  if (!cases.length) {
    node.innerHTML = `<p class="empty-state">暂无公司组合分析样板 / No company portfolio case yet</p>`;
    return;
  }
  node.innerHTML = cases
    .map((item, index) => {
      const coverage = item.database_coverage || {};
      const ce = item.ce_license_summary || [];
      const ceTotal = ce.reduce((sum, row) => sum + Number(row.count || 0), 0);
      const portfolios = item.portfolio_summary || [];
      const focusChips = ["品牌组合", "CE / IFU", "规格字段", "应用热力图"];
      const portfolioMarkup = portfolios
        .map(
          (portfolio) => `
            <div class="company-case-portfolio">
              <strong>${escapeHtml(portfolio.name || "")}</strong>
              <span>${escapeHtml(portfolio.definition || "")}</span>
            </div>
          `,
        )
        .join("");
      const ceMarkup = ce
        .map(
          (row) => `
            <div class="company-case-ce">
              <strong>${escapeHtml(row.class || "")}</strong>
              <span>${escapeHtml(row.ce_mark || "")}</span>
              <em>${fmt(row.count || 0)}</em>
            </div>
          `,
        )
        .join("");
      return `
        <article class="company-case" data-company="${escapeHtml(item.company || "")}">
          <div class="company-case-head">
            <div>
              <span>${escapeHtml(caseStatusLabel(item.status))}</span>
              <h4>${escapeHtml(item.company || item.title || "公司组合")}</h4>
              <div class="company-case-focus">
                ${focusChips.map((chip) => `<b>${escapeHtml(chip)}</b>`).join("")}
              </div>
            </div>
            <div class="company-case-stats">
              ${caseStatMarkup("产品组合", fmt((item.portfolio_summary || []).length))}
              ${caseStatMarkup("品牌映射", fmt(coverage.reference_brand_rows || (item.brand_portfolio_heatmap?.rows || []).length), `${fmt(coverage.matched_reference_brands || 0)} 已入库`)}
              ${caseStatMarkup("CE 单元", fmt(ceTotal), ce.map((row) => `${row.class} ${row.count}`).join(" · "))}
              ${caseStatMarkup("官网规格", fmt(coverage.trusted_product_spec_rows || 0), "包装 / 成分 / 浓度")}
              ${caseStatMarkup("官方适应症", fmt(coverage.official_indication_rows || 0), "监管长表")}
            </div>
          </div>
          <div class="company-case-split">
            <section>
              <h5>组合结构</h5>
              <div class="company-case-portfolios">${portfolioMarkup}</div>
            </section>
            <section>
              <h5>CE / IFU</h5>
              <div class="company-case-ce-list">${ceMarkup || `<p class="empty-state">暂无 CE/IFU 线索</p>`}</div>
            </section>
          </div>
          <div class="company-case-heatmaps">
            <section>
              <h5>${escapeHtml(caseTitleLabel(item.brand_portfolio_heatmap?.title || "品牌 × 产品组合"))}</h5>
              <div id="caseHeatmap-${index}-brand" class="matrix-wrap case-heatmap"></div>
            </section>
            <section>
              <h5>${escapeHtml(caseTitleLabel(item.portfolio_indication_heatmap?.title || "组合 × 应用方向"))}</h5>
              <p>官网资料图口径，不等同监管获批。</p>
              <div id="caseHeatmap-${index}-indications" class="matrix-wrap case-heatmap wide-case-heatmap"></div>
            </section>
            <section>
              <h5>${escapeHtml(caseTitleLabel(item.portfolio_area_heatmap?.title || "组合 × 治疗部位"))}</h5>
              <p>按治疗部位聚合，用于观察组合覆盖宽度。</p>
              <div id="caseHeatmap-${index}-areas" class="matrix-wrap case-heatmap wide-case-heatmap"></div>
            </section>
          </div>
        </article>
      `;
    })
    .join("");
  cases.forEach((item, index) => {
    renderHeatmap(`caseHeatmap-${index}-brand`, item.brand_portfolio_heatmap, "var(--c-sage)", item.brand_portfolio_heatmap?.row_label || "Brand");
    renderHeatmap(`caseHeatmap-${index}-indications`, item.portfolio_indication_heatmap, "var(--brand)", item.portfolio_indication_heatmap?.row_label || "Portfolio");
    renderHeatmap(`caseHeatmap-${index}-areas`, item.portfolio_area_heatmap, "var(--c-ocean)", item.portfolio_area_heatmap?.row_label || "Portfolio");
  });
}

function marketNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function marketRatioText(value) {
  const number = marketNumber(value);
  if (number === null || number <= 0) return "—";
  return number >= 100 ? number.toFixed(0) : number.toFixed(1);
}

function marketPriceText(item) {
  const price = marketNumber(item?.price);
  if (price === null || price <= 0) return "—";
  const currency = String(item.currency || "").trim();
  const digits = price >= 1000 ? 0 : price >= 100 ? 1 : 2;
  return `${currency ? `${currency} ` : ""}${price.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })}`;
}

function marketChangeMarkup(value) {
  const number = marketNumber(value);
  if (number === null) return `<span class="market-change muted">—</span>`;
  const className = number > 0 ? "positive" : number < 0 ? "negative" : "muted";
  const sign = number > 0 ? "+" : "";
  return `<span class="market-change ${className}">${sign}${number.toFixed(2)}%</span>`;
}

function marketSourceShort(item) {
  const status = String(item?.snapshot_status || "");
  if (status.includes("carried_forward")) return "Yahoo · 估值沿用";
  if (status === "valuation_fetched") return "实时估值";
  if (status.includes("missing")) return "仅价格";
  if (status.includes("failed")) return "待补";
  return item?.source || "来源待补";
}

function marketCompactDate(value) {
  const formatted = formatUpdatedAt(value);
  const match = formatted.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}:\d{2})/);
  return match ? `${match[2]}-${match[3]} ${match[4]}` : formatted;
}

function listedMarketRows(limit = 10) {
  return (DATA.market_snapshot?.cards || [])
    .slice()
    .sort((a, b) => {
      const capDelta = (marketNumber(b.market_cap_usd_m) || 0) - (marketNumber(a.market_cap_usd_m) || 0);
      if (capDelta) return capDelta;
      return String(a.company || "").localeCompare(String(b.company || ""));
    })
    .slice(0, limit);
}

function listedMarketTooltip(item) {
  const lines = [
    `${item.company || ""} · ${item.stock_code || item.ticker_symbol || ""}`,
    `Market cap: ${formatValuation(item.market_cap_usd_m)}`,
    `Revenue: ${formatValuation(item.revenue_usd_m)} · Gross margin: ${marketRatioText(item.gross_margin_pct)}%`,
    `Price: ${marketPriceText(item)} · Change: ${String(item.day_change_pct || "—")} %`,
    `PE: ${marketRatioText(item.pe_ratio)} · P/S: ${marketRatioText(item.ps_ratio)}`,
    `Source: ${item.source || "Source pending"}`,
    `Updated: ${formatUpdatedAt(item.as_of)}`,
  ];
  return lines.filter(Boolean).join("\n");
}

function renderRankLists() {
  const publicNode = $("publicCompanies");
  if (publicNode) {
    const rows = listedMarketRows(10);
    const withValuation = rows.filter((item) => marketNumber(item.market_cap_usd_m));
    const withPrice = rows.filter((item) => marketNumber(item.price));
    const latest = rows
      .map((item) => String(item.as_of || ""))
      .filter(Boolean)
      .sort()
      .pop();
    publicNode.innerHTML = rows.length
      ? `
        <div class="listed-market-summary">
          <span><strong>${fmt(DATA.summary?.public_companies || rows.length)}</strong><em>上市主体<br />Listed entities</em></span>
          <span><strong>${fmt(withValuation.length)}</strong><em>估值可用<br />Valuation</em></span>
          <span><strong>${fmt(withPrice.length)}</strong><em>价格可用<br />Price</em></span>
          <span><strong>${escapeHtml(marketCompactDate(latest))}</strong><em>更新时间<br />Updated</em></span>
        </div>
        <div class="listed-market-table" role="table" aria-label="Listed company market snapshot">
          <div class="listed-market-row listed-market-head" role="row">
            <span>公司<br /><em>Company</em></span>
            <span>估值<br /><em>Market cap</em></span>
            <span>PE</span>
            <span>PS</span>
            <span>股价<br /><em>Price</em></span>
            <span>涨跌<br /><em>Change</em></span>
            <span>来源<br /><em>Source</em></span>
          </div>
          ${rows
            .map((item, index) => {
              const sourceLabel = marketSourceShort(item);
              const url = item.source_url ? ` href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer"` : "";
              const tag = item.source_url ? "a" : "div";
              const tooltip = escapeHtml(listedMarketTooltip(item));
              return `
                <${tag} class="listed-market-row" role="row"${url} title="${tooltip}">
                  <span class="listed-company">
                    <b>${index + 1}</b>
                    <strong>${escapeHtml(item.company || "-")}</strong>
                    <em>${escapeHtml(item.stock_code || item.ticker_symbol || "")}</em>
                  </span>
                  <span class="listed-valuation">
                    <strong>${escapeHtml(formatValuation(item.market_cap_usd_m))}</strong>
                    <em>${escapeHtml(valuationBand(item.market_cap_usd_m))}</em>
                  </span>
                  <span>${escapeHtml(marketRatioText(item.pe_ratio))}</span>
                  <span>${escapeHtml(marketRatioText(item.ps_ratio))}</span>
                  <span>${escapeHtml(marketPriceText(item))}</span>
                  <span>${marketChangeMarkup(item.day_change_pct)}</span>
                  <span class="listed-source">${escapeHtml(sourceLabel)}</span>
                </${tag}>
              `;
            })
            .join("")}
        </div>
      `
      : `<p class="empty-state">暂无数据 / No data</p>`;
  }

  const metricNode = $("marketMetrics");
  if (metricNode) {
    metricNode.innerHTML = renderMarketMetricsPanel();
  }
}

function renderVerificationWorkbench() {
  const workbench = DATA.verification_workbench || {};
  const summary = DATA.summary || {};
  const registration = DATA.registration_evidence || {};
  const market = DATA.market_snapshot || {};

  const statusNode = $("verificationStatus");
  if (statusNode) {
    const rows = [
      { label: "产品数据 / Product data", value: fmt(summary.product_master || 0), note: "产品基础盘 / Product base" },
      { label: "公司主体 / Company entities", value: fmt(summary.company_master || 0), note: "企业归集 / Company grouping" },
      { label: "注册证据 / Regulatory evidence", value: fmt(summary.registration_evidence || 0), note: "监管来源优先 / Regulator sources first" },
      { label: "来源规则 / Source rules", value: fmt(summary.source_authority_rules || 0), note: "官方来源优先 / Official-source priority" },
      { label: "数据问题 / Data issues", value: fmt(summary.data_quality_issues || 0), note: `${fmt(summary.data_quality_high_issues || 0)} 高风险 / high-risk` },
      { label: "已采集证据 / Collected evidence", value: fmt(summary.evidence_staging || 0), note: "交叉检查 / Cross-check" },
    ];
    statusNode.innerHTML = rows
      .map(
        (item) => `
          <div class="verification-row">
            <span>${escapeHtml(item.label)}</span>
            <strong>${escapeHtml(item.value)}</strong>
            <em>${escapeHtml(item.note)}</em>
          </div>
        `,
      )
      .join("");
  }

  const queueNode = $("topCompanyQueue");
  if (queueNode) {
    queueNode.innerHTML = (workbench.top_companies || [])
      .slice(0, 8)
      .map(
        (item) => `
          <div class="rank-row verification-rank">
            <span>${fmt(item.rank)}</span>
            <strong>${escapeHtml(item.company)}</strong>
            <em>${escapeHtml(item.stock || item.track || item.country || "")}</em>
          </div>
        `,
      )
      .join("") || `<p class="empty-state">暂无队列</p>`;
  }

  const snapshotNode = $("marketSnapshot");
  if (snapshotNode) {
    snapshotNode.innerHTML = (market.cards || [])
      .slice(0, 7)
      .map((item) => {
        const valuation = formatValuation(item.market_cap_usd_m);
        const band = valuationBand(item.market_cap_usd_m);
        return `
          <div class="snapshot-row">
            <strong>${escapeHtml(item.company)}</strong>
            <span>${escapeHtml(valuation)}</span>
            <em>${escapeHtml(["估值", item.stock_code, band, item.as_of].filter(Boolean).join(" / "))}</em>
          </div>
        `;
      })
      .join("") || `<p class="empty-state">暂无股票映射</p>`;
  }
}

function renderDataUsabilityLedger() {
  const usability = DATA.verification_workbench?.data_usability || {};
  const summary = usability.summary || {};
  const statusNode = $("dataUsabilityStatus");
  if (statusNode) {
    const cards = [
      ["已盘点行", summary.audited_rows || 0, `${fmt(summary.audited_tables || 0)} 张表`],
      ["已可用/参考", summary.usable_or_reference_rows || 0, "主数据或参考层"],
      ["真待处理", summary.planned_or_review_rows || 0, "只保留需要人工收口的残留项"],
      ["缺负责人", summary.missing_owner_or_status_rows || 0, summary.every_row_has_status_and_owner ? "无缺口" : "需处理"],
    ];
    statusNode.innerHTML = cards
      .map(
        ([label, value, note]) => `
          <div class="briefing-news-stat">
            <strong>${fmt(value)}</strong>
            <span>${escapeHtml(label)}</span>
            <em>${escapeHtml(note)}</em>
          </div>
        `,
      )
      .join("");
  }

  const queueNode = $("dataUsabilityQueues");
  if (queueNode) {
    const rows = usability.ledger_preview || [];
    queueNode.innerHTML = rows
      .filter((item) => Number(item.planned_or_review_rows || 0) > 0)
      .slice(0, 12)
      .map((item) => {
        const owner = item.top_planned_responsible_module || item.top_responsible_module || "";
        const statusText = item.top_planned_status || item.top_operational_status || "";
        return `
          <article class="verified-event">
            <div>
              <span class="verified-badge">
                <b>${fmt(item.planned_or_review_rows || 0)} 真待处理行</b>
              </span>
              <h4>${escapeHtml(item.source_table || "Data table")}</h4>
              <p>${escapeHtml(statusText)}</p>
              <em>${escapeHtml(owner)}</em>
            </div>
          </article>
        `;
      })
      .join("") || `<p class="empty-state">暂无线索队列</p>`;
  }
}

const BRIEFING_EVENT_LABELS = {
  regulatory_approval: "注册获批 / Regulatory",
  indication_expansion: "适应症拓展 / Indication",
  product_launch: "产品上市 / Launch",
  commercial_performance: "商业表现 / Commercial",
  channel_coverage: "渠道覆盖 / Channel",
};

function selectOptionsFromCounts(counts = [], allLabel = "全部 / All") {
  const entries = Array.isArray(counts) ? counts : Object.entries(counts).map(([name, value]) => ({ name, value }));
  return [`<option value="">${escapeHtml(allLabel)}</option>`]
    .concat(entries.map((item) => {
      const name = item.name || item[0] || "";
      const value = item.value || item[1] || 0;
      const label = BRIEFING_EVENT_LABELS[name] || VERIFIED_PROMOTION_LABELS?.[name] || VERIFIED_MAPPING_LABELS?.[name] || name;
      return `<option value="${escapeHtml(name)}">${escapeHtml(label)} (${fmt(value)})</option>`;
    }))
    .join("");
}

function renderBriefingNewsWatch() {
  const watch = DATA.verification_workbench?.briefing_update_candidates || {};
  const rows = watch.candidate_preview || [];
  const statusNode = $("briefingNewsStatus");
  if (statusNode) {
    const cards = [
      ["候选线索", watch.rows || 0, "日报发现层"],
      ["高置信", watch.high_confidence || 0, "仍需官方确认"],
      ["当前待补正文", watch.needs_fulltext_rescue || 0, "仅统计本轮"],
      ["发现层待筛", watch.needs_official_verification || 0, "定期周更处理"],
    ];
    statusNode.innerHTML = cards
      .map(
        ([label, value, note]) => `
          <div class="briefing-news-stat">
            <strong>${fmt(value)}</strong>
            <span>${escapeHtml(label)}</span>
            <em>${escapeHtml(note)}</em>
          </div>
        `,
      )
      .join("");
  }

  const eventSelect = $("briefingEventFilter");
  const statusSelect = $("briefingStatusFilter");
  const rescueSelect = $("briefingRescueFilter");
  if (eventSelect && eventSelect.dataset.ready !== "1") {
    eventSelect.innerHTML = selectOptionsFromCounts(watch.by_event_group, "全部事件 / All events");
    eventSelect.dataset.ready = "1";
  }
  if (statusSelect && statusSelect.dataset.ready !== "1") {
    statusSelect.innerHTML = selectOptionsFromCounts(watch.by_status, "全部状态 / All status");
    statusSelect.dataset.ready = "1";
  }
  if (rescueSelect && rescueSelect.dataset.ready !== "1") {
    rescueSelect.innerHTML = `
      <option value="">全部正文状态 / All body states</option>
      <option value="yes">需补正文 / Needs rescue</option>
      <option value="no">正文可用 / Body usable</option>
    `;
    rescueSelect.dataset.ready = "1";
  }

  const selectedEvent = eventSelect?.value || "";
  const selectedStatus = statusSelect?.value || "";
  const selectedRescue = rescueSelect?.value || "";
  const filtered = rows.filter((item) => {
    if (selectedEvent && item.event_group !== selectedEvent) return false;
    if (selectedStatus && item.status !== selectedStatus) return false;
    if (selectedRescue && item.needs_fulltext_rescue !== selectedRescue) return false;
    return true;
  });
  const node = $("briefingCandidates");
  if (node) {
    node.innerHTML = filtered
      .map((item) => {
        const title = [item.company, item.brand, item.product_name].filter(Boolean).join(" / ") || item.article_title || "Briefing lead";
        const meta = [
          BRIEFING_EVENT_LABELS[item.event_group] || item.event_group,
          item.market_or_jurisdiction,
          item.source_domain,
          item.article_date,
        ].filter(Boolean).join(" · ");
        const score = Number(item.confidence_score || 0);
        const rescue = item.needs_fulltext_rescue === "yes" ? "需补正文" : "正文可用";
        const url = item.article_url || "";
        const tagClass = score >= 75 ? "high" : score < 60 ? "low" : "mid";
        return `
          <article class="briefing-candidate">
            <div>
              <span class="briefing-candidate-tags">
                <b class="${tagClass}">score ${fmt(score)}</b>
                <b>${escapeHtml(rescue)}</b>
                <b>${escapeHtml(item.promotion_target || "review_queue")}</b>
              </span>
              <h4>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>` : escapeHtml(title)}</h4>
              <p>${escapeHtml(item.excerpt || "")}</p>
              <em>${escapeHtml(meta)}</em>
            </div>
          </article>
        `;
      })
      .join("") || `<p class="empty-state">No briefing candidates for this filter.</p>`;
  }

  [eventSelect, statusSelect, rescueSelect].forEach((select) => {
    if (!select || select.dataset.wired === "1") return;
    select.dataset.wired = "1";
    select.addEventListener("change", renderBriefingNewsWatch);
  });
}

const VERIFIED_PROMOTION_LABELS = {
  promoted: "已入注册/适应症表",
  promoted_to_log: "已入商业/渠道日志",
  verified_gap: "已核验待建主档",
};

const VERIFIED_MAPPING_LABELS = {
  mapped_product: "已映射产品",
  company_not_in_master: "公司待建档",
  product_not_in_master: "产品待建档",
  remapped_gap: "已纠偏为缺口",
};

function renderBriefingVerifiedUpdates() {
  const verified = DATA.verification_workbench?.briefing_verified_updates || {};
  const rows = verified.event_preview || [];
  const gaps = verified.product_gap_candidates || {};
  const watch = DATA.verification_workbench?.briefing_update_candidates || {};
  const statusNode = $("briefingVerifiedStatus");
  if (statusNode) {
    const cards = [
      ["已核验事件", verified.rows || 0, "官方源确认"],
      ["已晋升", verified.promoted || 0, "入库或日志"],
      ["主档缺口", verified.verified_gap || 0, (verified.verified_gap || 0) ? "待处理" : "已清零"],
      ["当前待补正文", watch.needs_fulltext_rescue || 0, (watch.needs_fulltext_rescue || 0) ? "待补抓" : "已清零"],
    ];
    statusNode.innerHTML = cards
      .map(
        ([label, value, note]) => `
          <div class="briefing-news-stat">
            <strong>${fmt(value)}</strong>
            <span>${escapeHtml(label)}</span>
            <em>${escapeHtml(note)}</em>
          </div>
        `,
      )
      .join("");
  }

  const promotionSelect = $("verifiedPromotionFilter");
  const mappingSelect = $("verifiedMappingFilter");
  const sourceSelect = $("verifiedSourceFilter");
  if (promotionSelect && promotionSelect.dataset.ready !== "1") {
    promotionSelect.innerHTML = selectOptionsFromCounts(verified.by_promotion_status, "全部晋升状态 / All promotion");
    promotionSelect.dataset.ready = "1";
  }
  if (mappingSelect && mappingSelect.dataset.ready !== "1") {
    mappingSelect.innerHTML = selectOptionsFromCounts(verified.by_mapping_status, "全部映射状态 / All mapping");
    mappingSelect.dataset.ready = "1";
  }
  if (sourceSelect && sourceSelect.dataset.ready !== "1") {
    sourceSelect.innerHTML = selectOptionsFromCounts(verified.by_source_type, "全部官方来源 / All sources");
    sourceSelect.dataset.ready = "1";
  }

  const selectedPromotion = promotionSelect?.value || "";
  const selectedMapping = mappingSelect?.value || "";
  const selectedSource = sourceSelect?.value || "";
  const filtered = rows.filter((item) => {
    if (selectedPromotion && item.promotion_status !== selectedPromotion) return false;
    if (selectedMapping && item.mapping_status !== selectedMapping) return false;
    if (selectedSource && item.official_source_type !== selectedSource) return false;
    return true;
  });
  const node = $("briefingVerifiedEvents");
  if (node) {
    node.innerHTML = filtered
      .map((item) => {
        const title = [item.company, item.brand, item.product_name].filter(Boolean).join(" / ") || item.official_title || "Verified update";
        const meta = [
          BRIEFING_EVENT_LABELS[item.event_group] || item.event_group,
          item.article_date,
          item.official_source_type,
          item.promoted_target,
        ].filter(Boolean).join(" · ");
        const promotion = VERIFIED_PROMOTION_LABELS[item.promotion_status] || item.promotion_status || "已核验";
        const mapping = VERIFIED_MAPPING_LABELS[item.mapping_status] || item.mapping_status || "映射待确认";
        const statusClass = item.promotion_status === "verified_gap" ? "gap" : item.promotion_status === "promoted" ? "promoted" : "log";
        const sourceUrl = item.official_source_url || "";
        return `
          <article class="verified-event ${statusClass}">
            <div>
              <span class="briefing-candidate-tags">
                <b class="high">${escapeHtml(promotion)}</b>
                <b>${escapeHtml(mapping)}</b>
                <b>${escapeHtml(item.verification_status || "official_checked")}</b>
              </span>
              <h4>${sourceUrl ? `<a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>` : escapeHtml(title)}</h4>
              <p>${escapeHtml(item.official_excerpt || "")}</p>
              ${item.remaining_gap ? `<p class="verified-gap-note">${escapeHtml(item.remaining_gap)}</p>` : ""}
              <em>${escapeHtml(meta)}</em>
            </div>
          </article>
        `;
      })
      .join("") || `<p class="empty-state">No verified briefing updates for this filter.</p>`;
  }

  const gapNode = $("briefingProductGaps");
  if (gapNode) {
    const gapRows = gaps.preview || [];
    gapNode.innerHTML = gapRows.length
      ? `
        <div class="product-gap-title">Product / company master gaps</div>
        <div class="product-gap-list">
          ${gapRows
            .map((item) => {
              const url = item.sample_url || "";
              const title = `${item.company || "Unknown"} / ${item.candidate_product_or_family || "Gap"}`;
              return `
                <a class="product-gap-item" href="${escapeHtml(url || "#")}" ${url ? 'target="_blank" rel="noreferrer"' : ""}>
                  <strong>${escapeHtml(title)}</strong>
                  <span>${escapeHtml(item.review_status || "")}</span>
                </a>
              `;
            })
            .join("")}
        </div>
      `
      : "";
  }

  [promotionSelect, mappingSelect, sourceSelect].forEach((select) => {
    if (!select || select.dataset.wired === "1") return;
    select.dataset.wired = "1";
    select.addEventListener("change", renderBriefingVerifiedUpdates);
  });
}

function openOverlay(title, html) {
  const overlay = $("resultOverlay");
  const titleNode = $("resultTitle");
  const body = $("resultBody");
  if (!overlay || !titleNode || !body) return;
  titleNode.textContent = title;
  body.innerHTML = html;
  applyBilingualLayout(titleNode);
  applyBilingualLayout(body);
  overlay.hidden = false;
  document.body.classList.add("overlay-open");
}

function closeOverlay() {
  const overlay = $("resultOverlay");
  try {
    destroyCountryDetailMap();
  } catch (error) {
    geoCountryDetailMap = null;
    console.warn("Country detail map cleanup failed", error);
  } finally {
    if (overlay) overlay.hidden = true;
    document.body.classList.remove("overlay-open");
  }
}

function reviewTitle(item, type) {
  if (type === "registration") return item.title || [item.company, item.brand, item.source_record_id].filter(Boolean).join(" / ");
  if (type === "company_background") return `${item.company || ""} / ${item.field_name || ""}`;
  if (type === "capital") return `${item.company || ""} / ${item.stock_code_seed || "unlisted seed"}`;
  if (type === "ce_plan") return `${item.company || ""} / ${item.product_family || ""}`;
  return item.company || "Review item";
}

function reviewMeta(item, type) {
  if (type === "registration") {
    const f = item.field_candidates || {};
    return ["regulator-sourced", item.confidence, f.match_reason, f.applicant_match ? `applicant ${f.applicant_match}` : "", item.merge_status].filter(Boolean).join(" / ");
  }
  if (type === "company_background") return ["official/company-source tier", item.source_name, item.confidence, item.fact_type].filter(Boolean).join(" / ");
  if (type === "capital") return ["securities-source tier", item.evidence_status, item.sec_entity_name, item.notes].filter(Boolean).join(" / ");
  if (type === "ce_plan") return ["official CE path", item.source_name, item.evidence_target, item.automation_status].filter(Boolean).join(" / ");
  return "";
}

function reviewBody(item, type) {
  if (type === "registration") {
    const f = item.field_candidates || {};
    return [item.excerpt, f.registered_name ? `registered name: ${f.registered_name}` : "", f.registration_no ? `registration: ${f.registration_no}` : "", f.query_term ? `query: ${f.query_mode} / ${f.query_term}` : ""]
      .filter(Boolean)
      .map(escapeHtml)
      .join("<br />");
  }
  if (type === "company_background") return escapeHtml(item.field_value || "");
  if (type === "capital") return escapeHtml([item.sec_tickers, item.sec_exchanges, item.source_url].filter(Boolean).join(" / "));
  if (type === "ce_plan") return escapeHtml([item.query, item.expected_evidence].filter(Boolean).join(" / "));
  return "";
}

function reviewPayload(item, type, action) {
  const base = { type, action };
  if (type === "registration") return { ...base, source_key: item.source_key, source_record_id: item.source_record_id, company_id: item.company_id };
  if (type === "company_background") return { ...base, company_id: item.company_id, source_key: item.source_key, field_name: item.field_name };
  if (type === "capital") return { ...base, company_id: item.company_id };
  if (type === "ce_plan") return { ...base, plan_id: item.plan_id };
  return base;
}

function renderReviewItems(type, rows) {
  const node = $("reviewItems");
  if (!node) return;
  node.innerHTML = (rows || [])
    .map((item, index) => `
      <article class="review-item" data-review-index="${index}">
        <div>
          <span class="confidence">${escapeHtml(item.review_status || "needs_review")}</span>
          <h4>${escapeHtml(reviewTitle(item, type))}</h4>
          <p>${reviewBody(item, type)}</p>
          <em>${escapeHtml(reviewMeta(item, type))}</em>
        </div>
        <div class="review-actions">
          <span class="read-only-badge">交叉检查 / Cross-check</span>
        </div>
      </article>
    `)
    .join("") || `<p class="empty-state">No review items for this filter.</p>`;
  applyBilingualLayout(node);
}

async function loadReviewItems() {
  const type = $("reviewType")?.value || "registration";
  const status = $("reviewStatus")?.value || "all";
  const node = $("reviewItems");
  if (node) node.innerHTML = `<div class="loading">Loading review items...</div>`;
  const response = await fetch(`/api/review-items?type=${encodeURIComponent(type)}&status=${encodeURIComponent(status)}&limit=30`);
  const payload = await response.json();
  renderReviewItems(type, payload.results || []);
}

async function submitReviewAction(payload) {
  const response = await fetch("/api/review-action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    openOverlay("Review action", `<p class="empty-state">${escapeHtml(result.error || "Failed")}</p>`);
    return;
  }
  loadReviewItems();
}

function wireInteractions() {
  document.addEventListener(
    "click",
    (event) => {
      if (!event.target?.closest?.("[data-close-overlay]")) return;
      event.preventDefault();
      event.stopPropagation();
      closeOverlay();
    },
    true,
  );
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeOverlay();
  });
}

function topbarOffset() {
  const topbar = document.querySelector(".topbar");
  return topbar ? Math.ceil(topbar.getBoundingClientRect().height + 14) : 76;
}

function samePageHashFromLink(link) {
  if (!link) return "";
  const url = new URL(link.getAttribute("href") || "", window.location.href);
  const here = new URL(window.location.href);
  if (url.origin !== here.origin || url.pathname !== here.pathname || !url.hash) return "";
  return url.hash;
}

function normalizedPagePath(pathname) {
  return String(pathname || "").replace(/\/index\.html$/i, "/");
}

function linkTargetsCurrentPage(link) {
  if (!link) return false;
  const url = new URL(link.getAttribute("href") || "", window.location.href);
  const here = new URL(window.location.href);
  return url.origin === here.origin && normalizedPagePath(url.pathname) === normalizedPagePath(here.pathname) && !url.hash;
}

function setActiveTopNav(hash) {
  const targetHash = hash || "#overview";
  document.querySelectorAll(".material-nav a, .function-rail a").forEach((link) => {
    const isActive = linkTargetsCurrentPage(link) || samePageHashFromLink(link) === targetHash;
    link.classList.toggle("active", isActive);
    if (isActive) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function currentScrollTop() {
  return window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0;
}

function scrollPageTo(top, behavior = "smooth") {
  const nextTop = Math.max(0, Number(top || 0));
  if (typeof window.scrollTo === "function") {
    window.scrollTo({ top: nextTop, behavior });
    return;
  }
  document.documentElement.scrollTop = nextTop;
  document.body.scrollTop = nextTop;
}

function scrollToHashTarget(hash, behavior = "smooth") {
  if (!hash) return false;
  const target = document.querySelector(hash);
  if (!target) return false;
  const top = target.getBoundingClientRect().top + currentScrollTop() - topbarOffset();
  scrollPageTo(top, behavior);
  setActiveTopNav(hash);
  return true;
}

function wireTopNavigation() {
  const navs = [...document.querySelectorAll(".material-nav, .function-rail nav")];
  if (!navs.length || navs.every((nav) => nav.dataset.wired === "1")) return;
  navs.forEach((nav) => {
    if (nav.dataset.wired === "1") return;
    nav.dataset.wired = "1";
    nav.addEventListener("click", (event) => {
      const link = event.target.closest("a");
      const hash = samePageHashFromLink(link);
      if (!hash) return;
      event.preventDefault();
      window.history.pushState(null, "", hash);
      scrollToHashTarget(hash);
    });
  });

  let ticking = false;
  const updateActiveFromScroll = () => {
    ticking = false;
    const currentHash = window.location.hash;
    const currentTarget = currentHash ? document.querySelector(currentHash) : null;
    if (currentTarget) {
      const rect = currentTarget.getBoundingClientRect();
      const offset = topbarOffset();
      if (rect.top <= offset + 140 && rect.bottom >= offset - 20) {
        setActiveTopNav(currentHash);
        return;
      }
    }
    const probe = currentScrollTop() + topbarOffset() + 28;
    const hashes = navs
      .flatMap((nav) => [...nav.querySelectorAll("a")])
      .map(samePageHashFromLink)
      .filter(Boolean)
      .filter((hash, index, list) => list.indexOf(hash) === index);
    let active = "#overview";
    let activeOffset = -Infinity;
    hashes.forEach((hash) => {
      const target = document.querySelector(hash);
      if (target && target.offsetTop <= probe && target.offsetTop > activeOffset + 8) {
        active = hash;
        activeOffset = target.offsetTop;
      }
    });
    setActiveTopNav(active);
  };
  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateActiveFromScroll);
    },
    { passive: true },
  );
  window.addEventListener("popstate", () => scrollToHashTarget(window.location.hash || "#overview", "auto"));
  updateActiveFromScroll();
}

function restoreInitialHashPosition() {
  const hash = window.location.hash;
  if (!hash) {
    setActiveTopNav("#overview");
    return;
  }
  window.requestAnimationFrame(() => {
    window.setTimeout(() => scrollToHashTarget(hash, "auto"), 80);
  });
}

function init() {
  renderKpis();
  renderSeedNotice();
  renderGeoMap();
  renderSegments();
  renderSegmentDeepDive();
  renderBlueprint();
  renderSourceCompletionPanel();
  renderStrategicAngles();
  renderFunnel("globalEvidenceFunnel", currentEvidenceFunnel(), "var(--brand)");
  renderTimeline("globalApprovalTimeline", DATA.registration_evidence?.timeline || [], "var(--brand)");
  renderBars("globalRegulatoryMix", currentRegulatoryMix(), { color: "var(--brand)", limit: 8 });
  renderDonut("segmentDonut");
  renderRegionFunnelChart("regionBars", DATA.region_distribution || [], { limit: 7 });
  renderCountryRankingBars("countryBars", DATA.country_distribution || [], { limit: 7 });
  renderBars("indicationCoverage", DATA.indication_distribution || [], { color: "var(--brand)", limit: 8 });
  renderBars("officialIndicationCoverage", DATA.official_indication_analysis?.top_buckets || [], { color: "var(--c-ocean)", limit: 8 });
  renderHeatmap("officialIndicationHeatmap", DATA.official_indication_analysis?.by_regulator_heatmap, "var(--c-ocean)", "官方适应症");
  renderBars("subtrackCoverage", DATA.subtrack_distribution || [], { color: "var(--c-gold)", limit: 8 });
  renderMatrix();
  renderCompanyPortfolioCases();
  renderVerificationWorkbench();
  renderDataUsabilityLedger();
  renderBriefingNewsWatch();
  renderBriefingVerifiedUpdates();
  renderRankLists();
  applyBilingualLayout();
  wireInteractions();
  wireTopNavigation();
  restoreInitialHashPosition();
}

init();

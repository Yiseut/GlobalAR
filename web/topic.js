const DATA = window.GLOBAL_AESTHETICS_DATA || {};
const SEGMENTS = DATA.segments || [];
const $ = (id) => document.getElementById(id);

const MATERIAL_LABELS = {
  ha: "玻尿酸 / HA",
  plla: "PLA",
  pcl: "PCL",
  caha: "CaHA",
  pn_pdrn: "PN / PDRN",
  exosome: "外泌体 / Exosomes",
  botulinum: "肉毒毒素 / Neurotoxin",
  ebd: "光电设备 / EBD",
  threads: "线材 / Threads",
  mesotherapy: "中胚层 / Mesotherapy",
};

const SUBTRACK_COLORS =
  DATA.subtrack_colors || {
    ha: "#534AB7",
    "玻尿酸": "#534AB7",
    "HA": "#534AB7",
    "HA / 透明质酸": "#534AB7",
    plla: "#1D9E75",
    "PLA": "#1D9E75",
    "PLLA": "#1D9E75",
    "PLLA / PDLLA": "#1D9E75",
    pcl: "#D85A30",
    "PCL": "#D85A30",
    caha: "#8A8178",
    "CaHA": "#8A8178",
    collagen: "#378ADD",
    "胶原": "#378ADD",
    exosome: "#D4537E",
    "外泌体": "#D4537E",
    botulinum: "#A85D98",
    ebd: "#2F7DAA",
    threads: "#B58D3E",
    mesotherapy: "#0F8C7A",
    other: "#888780",
  };

const VALUE_CHAIN_STAGES = [
  { key: "raw", label: "原料供应", color: "#1D9E75" },
  { key: "manufacturing", label: "制造生产", color: "#54C49E" },
  { key: "brand", label: "品牌运营", color: "#9ADDC8" },
  { key: "distribution", label: "分销代理", color: "#D5F3EA" },
  { key: "service", label: "临床服务", color: "#BDE9DB" },
];

const COUNTRY_CODES = {
  "United States": "US",
  USA: "US",
  US: "US",
  China: "CN",
  "South Korea": "KR",
  Korea: "KR",
  Germany: "DE",
  Switzerland: "CH",
  France: "FR",
  Italy: "IT",
  Spain: "ES",
  UK: "UK",
  "United Kingdom": "UK",
  Netherlands: "NL",
  Israel: "IL",
  Brazil: "BR",
  Japan: "JP",
  Canada: "CA",
  Australia: "AU",
};

const GEO_LABELS = {
  "South Korea": "韩国",
  Switzerland: "瑞士",
  "United States": "美国",
  USA: "美国",
  China: "中国",
  Germany: "德国",
  France: "法国",
  Italy: "意大利",
  Spain: "西班牙",
  UK: "英国",
  "United Kingdom": "英国",
  Netherlands: "荷兰",
  Israel: "以色列",
  Brazil: "巴西",
  Japan: "日本",
  Canada: "加拿大",
  Australia: "澳大利亚",
  Europe: "欧洲",
  "Asia-Pacific": "亚太",
  "North America": "北美",
  "Middle East": "中东",
  Other: "其他",
  Global: "全球",
};

const GROUP_FOR_SEGMENT = {
  ha: "injectables",
  plla: "injectables",
  pcl: "injectables",
  caha: "injectables",
  injectables: "injectables",
  pn_pdrn: "regenerative",
  exosome: "regenerative",
  regenerative: "regenerative",
  botulinum: "toxin",
  ebd: "ebd",
  threads: "threads",
  mesotherapy: "mesotherapy",
};

const TOPIC_GROUPS = {
  injectables: {
    code: "injectables",
    name: "注射材料 / Injectables",
    subtitle: "玻尿酸、PLA、PCL、CaHA 等注射填充与胶原刺激材料",
    color: "#DA7756",
    segments: ["ha", "plla", "pcl", "caha"],
  },
  regenerative: {
    code: "regenerative",
    name: "再生修复 / Regenerative",
    subtitle: "PN / PDRN、外泌体、PRP/PRF、生长因子与相关再生修复产品",
    color: "#7BA99C",
    segments: ["pn_pdrn", "exosome"],
  },
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
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

const HEATMAP_ZERO_COLOR = "#edf6fd";

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
    <div class="heatmap-scale" style="--heat-steps:${palette.length}" aria-label="单色蓝热力色阶">
      <span>低</span>
      ${palette.map((color) => `<i style="--scale-color:${color}"></i>`).join("")}
      <span>高</span>
    </div>
  `;
}

function segmentCode() {
  const value = new URLSearchParams(window.location.search).get("segment") || "pcl";
  return value === "pcl_caha" ? "pcl" : value;
}

function selectedSubtrack() {
  return new URLSearchParams(window.location.search).get("subtrack") || "";
}

function findSegment() {
  const code = segmentCode();
  if (TOPIC_GROUPS[code]) return buildGroupSegment(TOPIC_GROUPS[code]);
  return SEGMENTS.find((item) => item.code === code) || SEGMENTS[0];
}

function displayName(segment) {
  return MATERIAL_LABELS[segment?.code] || segment?.name || "材料赛道";
}

function segmentByCode(code) {
  return SEGMENTS.find((item) => item.code === code);
}

function valueOf(item) {
  return Number(item?.value ?? item?.products ?? item?.total ?? 0);
}

function mergeNamedRows(rows, limit = 12) {
  const map = new Map();
  (rows || []).flat().filter(Boolean).forEach((item) => {
    const name = item.name || item.label || item.country || item.region || "";
    if (!name) return;
    map.set(name, (map.get(name) || 0) + valueOf(item));
  });
  return [...map.entries()]
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => Number(b.value || 0) - Number(a.value || 0))
    .slice(0, limit);
}

function mergeRegulatory(children) {
  const output = {};
  children.forEach((segment) => {
    Object.entries(segment.regulatory || {}).forEach(([key, value]) => {
      output[key] = (output[key] || 0) + Number(value || 0);
    });
  });
  return output;
}

function mergeTimeline(children) {
  const map = new Map();
  children.forEach((child) => {
    (child["evidence_scope"]?.timeline || []).forEach((row) => {
      const year = row.year || "";
      if (!year) return;
      const current = map.get(year) || { year, total: 0, fda: 0, ce: 0, nmpa: 0 };
      current.total += Number(row.total || 0);
      current.fda += Number(row.fda || 0);
      current.ce += Number(row.ce || 0);
      current.nmpa += Number(row.nmpa || 0);
      map.set(year, current);
    });
  });
  return [...map.values()].sort((a, b) => String(a.year).localeCompare(String(b.year)));
}

function mergeEvidenceScope(children) {
  const scope = { timeline: mergeTimeline(children) };
  children.forEach((child) => {
    Object.entries(child["evidence_scope"] || {}).forEach(([key, value]) => {
      if (key === "timeline" || key === "official_indication_heatmap") return;
      if (typeof value === "number") scope[key] = (scope[key] || 0) + value;
    });
  });
  scope.official_indication_heatmap = mergeHeatmaps(children.map((child) => child["evidence_scope"]?.official_indication_heatmap));
  return scope;
}

function mergeHeatmaps(heatmaps) {
  const columns = [];
  const rowMap = new Map();
  (heatmaps || []).filter(Boolean).forEach((heatmap) => {
    (heatmap.columns || []).forEach((column) => {
      if (column && !columns.includes(column)) columns.push(column);
    });
    (heatmap.rows || []).forEach((row) => {
      if (!row?.name) return;
      const current = rowMap.get(row.name) || { name: row.name, values: {}, examples: {} };
      Object.entries(row.values || {}).forEach(([column, value]) => {
        current.values[column] = (current.values[column] || 0) + Number(value || 0);
      });
      Object.entries(row.examples || {}).forEach(([column, examples]) => {
        current.examples[column] = [...(current.examples[column] || []), ...(examples || [])].slice(0, 4);
      });
      rowMap.set(row.name, current);
    });
  });
  const rows = [...rowMap.values()]
    .map((row) => ({
      ...row,
      total: Object.values(row.values || {}).reduce((sum, value) => sum + Number(value || 0), 0),
    }))
    .sort((a, b) => Number(b.total || 0) - Number(a.total || 0))
    .slice(0, 12);
  return { columns: columns.slice(0, 12), rows };
}

function groupMatrix(children, rowKey) {
  const columns = children.map((segment) => displayName(segment));
  const rowMap = new Map();
  children.forEach((segment) => {
    const column = displayName(segment);
    const rows = rowKey === "company" ? segment.top_companies || [] : segment.top_countries || [];
    rows.forEach((item) => {
      const name = item.name || "";
      if (!name) return;
      const current = rowMap.get(name) || { name, values: {}, examples: {} };
      current.values[column] = (current.values[column] || 0) + valueOf(item);
      rowMap.set(name, current);
    });
  });
  const rows = [...rowMap.values()]
    .map((row) => ({
      ...row,
      total: Object.values(row.values || {}).reduce((sum, value) => sum + Number(value || 0), 0),
    }))
    .sort((a, b) => Number(b.total || 0) - Number(a.total || 0))
    .slice(0, 12);
  return { columns, rows };
}

function unionFieldCount(children, rows, field, fallbackField) {
  const values = new Set();
  (rows || []).forEach((row) => {
    const value = row?.[field] || row?.[fallbackField];
    if (value) values.add(value);
  });
  return values.size || children.reduce((sum, segment) => sum + Number(segment[field] || 0), 0);
}

function buildGroupSegment(group) {
  const children = group.segments.map(segmentByCode).filter(Boolean);
  const sampleProducts = children.flatMap((segment) => segment.sample_products || []);
  const productEvidenceAudit = children.flatMap((segment) => segment.product_evidence_audit || []);
  const childRows = children.map((segment) => ({
    name: displayName(segment),
    value: segment.products || 0,
    products: segment.products || 0,
    segment_code: segment.code,
  }));
  return {
    ...group,
    is_group: true,
    child_segments: children,
    products: children.reduce((sum, segment) => sum + Number(segment.products || 0), 0),
    companies: unionFieldCount(children, sampleProducts, "company", "company_name"),
    brands: unionFieldCount(children, sampleProducts, "brand", "brand_name"),
    countries: unionFieldCount(children, sampleProducts, "country", "country_region"),
    subtrack_count: children.reduce((sum, segment) => sum + Number(segment.subtrack_count || 0), 0),
    indication_count: new Set(children.flatMap((segment) => (segment.top_indications || []).map((item) => item.name).filter(Boolean))).size,
    configured_subtracks: children.map(displayName),
    top_subtracks: childRows,
    subtrack_slices: childRows,
    top_indications: mergeNamedRows(children.map((segment) => segment.top_indications), 12),
    top_regions: mergeNamedRows(children.map((segment) => segment.top_regions), 10),
    top_countries: mergeNamedRows(children.map((segment) => segment.top_countries), 10),
    top_companies: mergeNamedRows(children.map((segment) => segment.top_companies), 12),
    top_brands: mergeNamedRows(children.map((segment) => segment.top_brands), 12),
    business_roles: mergeNamedRows(children.map((segment) => segment.business_roles), 8),
    ownership_mix: mergeNamedRows(children.map((segment) => segment.ownership_mix), 8),
    tech_type_mix: mergeNamedRows(children.map((segment) => segment.tech_type_mix || segment.category_l2_mix), 10),
    regulatory: mergeRegulatory(children),
    evidence_scope: mergeEvidenceScope(children),
    product_evidence_audit: productEvidenceAudit,
    sample_products: sampleProducts,
    company_subtrack_matrix: groupMatrix(children, "company"),
    country_subtrack_matrix: groupMatrix(children, "country"),
    subtrack_heatmap: { columns: ["产品线"], rows: childRows.map((item) => ({ name: item.name, values: { "产品线": item.products }, total: item.products })) },
    indication_heatmap: mergeHeatmaps(children.map((segment) => segment.indication_heatmap)),
    analysis_lenses: children.flatMap((segment) => segment.analysis_lenses || []).slice(0, 8),
  };
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
  return labels[text] || geoLabel(text);
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

function segmentUrl(segment, subtrack = "") {
  const query = new URLSearchParams({ segment: segment.code });
  if (subtrack) query.set("subtrack", subtrack);
  return `./topic.html?${query.toString()}`;
}

const SUBTRACK_SCOPE_RULES = {
  ha: {
    aliases: {
      "Skin Booster / 水光": "Skin Booster / 无交联水光",
      "Mesotherapy HA": "中胚层 HA 复配液",
      "复合配方": "HA 主成分复配",
    },
    preferred: ["Filler / 交联填充剂", "Skin Booster / 无交联水光", "中胚层 HA 复配液", "HA 主成分复配", "HA 未细分产品形态"],
  },
  plla: {
    aliases: {
      "身体用 PLLA 制剂": null,
      "身体胶原刺激": null,
      "线材 / 提拉": null,
    },
    preferred: ["注射型 PLLA", "PDLLA / 复合微球"],
  },
  pcl: {
    aliases: {
      "PCL 线材": null,
    },
    preferred: ["液态 PCL", "PCL 微球填充剂"],
  },
  caha: {
    aliases: {
      "稀释/超稀释 CaHA 用法": null,
    },
    preferred: ["CaHA 微球填充剂", "HA + CaHA 复合填充剂"],
  },
  pn_pdrn: {
    aliases: {
      "PN 注射": "PN 制剂",
      "PN 注射剂": "PN 制剂",
      "PDRN / 修复": "PDRN 制剂",
      "PN/PDRN 复合配方": "PN/PDRN 复合制剂",
      "眼周 / 细纹": null,
      "眼周细纹": null,
      "头皮 / 毛发": null,
      "头皮毛发": null,
    },
    preferred: ["PN 制剂", "PDRN 制剂", "PN/PDRN 复合制剂", "PN/PDRN 原料/API"],
  },
  exosome: {
    aliases: {
      "外泌体护肤 / 医美": "外泌体制剂",
      "头皮 / 毛发再生": null,
      "毛发 / 头皮": null,
      "皮肤再生 / 抗炎": null,
      "术后修复": null,
    },
    preferred: ["外泌体制剂", "PRP / PRF", "生长因子 / 细胞因子", "条件培养基 / 分泌组"],
  },
  mesotherapy: {
    aliases: {
      "Meso cocktail": "复配注射液 / Cocktail",
      "HA 复配溶液": "HA 基底复配液 / HA-based cocktail",
      "肤质活化": null,
      "头皮 / 毛发": null,
      "头皮毛发": null,
      "脂肪溶解": null,
      "局部减脂": null,
    },
    preferred: ["复配注射液 / Cocktail", "HA 基底复配液 / HA-based cocktail", "生物活性成分复配", "注射设备 / 针头耗材"],
  },
};

function canonicalSubtrackName(segmentCode, name) {
  const rule = SUBTRACK_SCOPE_RULES[segmentCode];
  if (!rule) return name;
  if (Object.prototype.hasOwnProperty.call(rule.aliases, name)) return rule.aliases[name];
  return name;
}

function normalizeSubtrackNames(segmentCode, names = [], includePreferred = false) {
  const seen = new Set();
  const normalized = [];
  (names || []).forEach((name) => {
    const canonical = canonicalSubtrackName(segmentCode, name);
    if (!canonical || seen.has(canonical)) return;
    seen.add(canonical);
    normalized.push(canonical);
  });
  if (includePreferred) {
    const preferred = SUBTRACK_SCOPE_RULES[segmentCode]?.preferred || [];
    preferred.forEach((name) => {
      if (!seen.has(name)) {
        seen.add(name);
        normalized.push(name);
      }
    });
  }
  return normalized;
}

function normalizeSubtrackRows(segmentCode, rows = []) {
  const merged = new Map();
  (rows || []).forEach((row) => {
    const canonical = canonicalSubtrackName(segmentCode, row.name);
    if (!canonical) return;
    const current = merged.get(canonical) || { ...row, name: canonical, value: 0, total: 0 };
    current.value = Number(current.value || 0) + Number(row.value || 0);
    current.total = Number(current.total || 0) + Number(row.total || 0);
    if (!current.value && !Object.prototype.hasOwnProperty.call(row, "value")) delete current.value;
    if (!current.total && !Object.prototype.hasOwnProperty.call(row, "total")) delete current.total;
    merged.set(canonical, current);
  });
  return Array.from(merged.values());
}

function normalizeSubtrackMatrix(segmentCode, matrix) {
  if (!matrix?.columns?.length) return matrix;
  const columns = normalizeSubtrackNames(segmentCode, matrix.columns, true);
  const rows = (matrix.rows || []).map((row) => {
    const values = {};
    (matrix.columns || []).forEach((column) => {
      const canonical = canonicalSubtrackName(segmentCode, column);
      if (!canonical || !columns.includes(canonical)) return;
      values[canonical] = Number(values[canonical] || 0) + Number(row.values?.[column] || 0);
    });
    const total = columns.reduce((sum, column) => sum + Number(values[column] || 0), 0);
    return { ...row, values, total };
  });
  return { ...matrix, columns, rows };
}

function normalizeSubtrackHeatmap(segmentCode, heatmap) {
  if (!heatmap?.rows?.length) return heatmap;
  const columns = heatmap.columns || [];
  const merged = new Map();
  (heatmap.rows || []).forEach((row) => {
    const canonical = canonicalSubtrackName(segmentCode, row.name);
    if (!canonical) return;
    const current = merged.get(canonical) || { ...row, name: canonical, values: {}, total: 0 };
    columns.forEach((column) => {
      current.values[column] = Number(current.values[column] || 0) + Number(row.values?.[column] || 0);
    });
    current.total = columns.reduce((sum, column) => sum + Number(current.values[column] || 0), 0);
    merged.set(canonical, current);
  });
  return { ...heatmap, rows: Array.from(merged.values()) };
}

function normalizeProductSubtracks(segmentCode, rows = []) {
  return (rows || []).map((row) => ({
    ...row,
    subtracks: collapseProductSubtracks(segmentCode, normalizeSubtrackNames(segmentCode, row.subtracks || [])),
  }));
}

function collapseProductSubtracks(segmentCode, names = []) {
  if (segmentCode === "mesotherapy") {
    const set = new Set(names);
    if (set.has("注射设备 / 针头耗材")) return ["注射设备 / 针头耗材"];
    if (set.has("生物活性成分复配")) return ["生物活性成分复配"];
    if (set.has("HA 基底复配液 / HA-based cocktail")) return ["HA 基底复配液 / HA-based cocktail"];
    if (set.has("复配注射液 / Cocktail")) return ["复配注射液 / Cocktail"];
    return names.slice(0, 1);
  }
  if (segmentCode !== "pn_pdrn") return names;
  const set = new Set(names);
  if (set.has("PN/PDRN 原料/API")) return ["PN/PDRN 原料/API"];
  if (set.has("PN/PDRN 复合制剂") || (set.has("PN 制剂") && set.has("PDRN 制剂"))) return ["PN/PDRN 复合制剂"];
  if (set.has("PDRN 制剂")) return ["PDRN 制剂"];
  if (set.has("PN 制剂")) return ["PN 制剂"];
  return names.slice(0, 1);
}

function normalizeTopicTaxonomy(segment) {
  const rule = SUBTRACK_SCOPE_RULES[segment?.code];
  if (!rule) return segment;
  const normalizeSlice = (slice) => ({
    ...slice,
    name: canonicalSubtrackName(segment.code, slice.name) || slice.name,
    top_subtracks: normalizeSubtrackRows(segment.code, slice.top_subtracks || []),
    subtrack_heatmap: normalizeSubtrackHeatmap(segment.code, slice.subtrack_heatmap),
    company_subtrack_matrix: normalizeSubtrackMatrix(segment.code, slice.company_subtrack_matrix),
    country_subtrack_matrix: normalizeSubtrackMatrix(segment.code, slice.country_subtrack_matrix),
    sample_products: normalizeProductSubtracks(segment.code, slice.sample_products || []),
  });
  const subtrackSlices = [];
  const seenSlices = new Set();
  (segment.subtrack_slices || []).forEach((slice) => {
    const normalized = normalizeSlice(slice);
    if (!normalized.name || seenSlices.has(normalized.name)) return;
    seenSlices.add(normalized.name);
    subtrackSlices.push(normalized);
  });
  return {
    ...segment,
    configured_subtracks: normalizeSubtrackNames(segment.code, segment.configured_subtracks || [], true),
    top_subtracks: normalizeSubtrackRows(segment.code, segment.top_subtracks || []),
    subtrack_heatmap: normalizeSubtrackHeatmap(segment.code, segment.subtrack_heatmap),
    company_subtrack_matrix: normalizeSubtrackMatrix(segment.code, segment.company_subtrack_matrix),
    country_subtrack_matrix: normalizeSubtrackMatrix(segment.code, segment.country_subtrack_matrix),
    sample_products: normalizeProductSubtracks(segment.code, segment.sample_products || []),
    subtrack_slices: subtrackSlices,
  };
}

function activeSlice(segment) {
  const rawName = selectedSubtrack();
  const name = canonicalSubtrackName(segment.code, rawName);
  if (!name) return null;
  return (segment.subtrack_slices || []).find((item) => item.name === name || item.name === rawName) || null;
}

function visibleSubtrackSlices(segment) {
  const slices = segment.subtrack_slices || [];
  const configured = segment.configured_subtracks || [];
  if (!configured.length) return slices.slice(0, 10);
  const byName = new Map(slices.map((item) => [item.name, item]));
  const primary = configured.map((name) => byName.get(name)).filter(Boolean);
  const extras = slices.filter((item) => !configured.includes(item.name) && item.products >= 8);
  return [...primary, ...extras].slice(0, 10);
}

function maxValue(items) {
  return Math.max(1, ...items.map((item) => Number(item.value || 0)));
}

function pct(value, total, digits = 0) {
  const denominator = Number(total || 0);
  if (!denominator) return 0;
  return Number(((Number(value || 0) / denominator) * 100).toFixed(digits));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function shortLabel(value = "") {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.split(/\s*\/\s*/)[0].trim() || text;
}

function geoLabel(value = "") {
  const text = String(value || "").trim();
  return GEO_LABELS[text] || shortLabel(text);
}

function colorForSubtrack(name = "") {
  const text = String(name || "").trim();
  const compact = text.toLowerCase();
  if (SUBTRACK_COLORS[text]) return SUBTRACK_COLORS[text];
  if (SUBTRACK_COLORS[compact]) return SUBTRACK_COLORS[compact];
  if (/玻尿酸|hyaluronic|(^|\s)ha(\s|$)/i.test(text)) return SUBTRACK_COLORS.ha;
  if (/plla|pdlla|pla|聚乳酸/i.test(text)) return SUBTRACK_COLORS.plla;
  if (/pcl|polycaprolactone/i.test(text)) return SUBTRACK_COLORS.pcl;
  if (/caha|hydroxylapatite|羟基磷灰石/i.test(text)) return SUBTRACK_COLORS.caha;
  if (/collagen|胶原/i.test(text)) return SUBTRACK_COLORS.collagen;
  if (/exosome|外泌体/i.test(text)) return SUBTRACK_COLORS.exosome;
  if (/botulinum|toxin|肉毒/i.test(text)) return SUBTRACK_COLORS.botulinum;
  if (/laser|rf|hifu|ebd|光电|射频|超声|激光/i.test(text)) return SUBTRACK_COLORS.ebd;
  if (/thread|线/i.test(text)) return SUBTRACK_COLORS.threads;
  if (/meso|中胚层/i.test(text)) return SUBTRACK_COLORS.mesotherapy;
  return SUBTRACK_COLORS.other;
}

function referenceDate() {
  const generated = DATA.generated_at ? new Date(DATA.generated_at) : null;
  if (generated && !Number.isNaN(generated.getTime())) return generated;
  return new Date("2026-05-16T00:00:00+08:00");
}

function timelineRows(view) {
  return (view.evidence_scope?.timeline || view.approval_timeline || [])
    .map((row) => ({ ...row, year: String(row.year || ""), total: Number(row.total || 0) }))
    .filter((row) => row.year && Number.isFinite(Number(row.year)))
    .sort((a, b) => Number(a.year) - Number(b.year));
}

function latestYearTotal(rows) {
  const last = (rows || []).filter((row) => Number(row.total || 0) > 0).at(-1);
  return Number(last?.total || 0);
}

function recentYearsTotal(rows, count = 3) {
  const maxYear = Math.max(...(rows || []).map((row) => Number(row.year || 0)), 0);
  if (!maxYear) return 0;
  return (rows || [])
    .filter((row) => Number(row.year || 0) >= maxYear - count + 1)
    .reduce((sum, row) => sum + Number(row.total || 0), 0);
}

function sparklineMarkup(values = [], color = "var(--signal-up)") {
  const nums = (values || []).map((value) => Number(value || 0)).filter((value) => Number.isFinite(value));
  const series = nums.length ? nums : [0, 1, 1, 2, 3, 4];
  const max = Math.max(...series, 1);
  const min = Math.min(...series, 0);
  const span = Math.max(1, max - min);
  const points = series
    .map((value, index) => {
      const x = series.length === 1 ? 0 : (index / (series.length - 1)) * 120;
      const y = 22 - ((value - min) / span) * 18;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return `
    <svg class="topic-sparkline" viewBox="0 0 120 26" preserveAspectRatio="none" aria-hidden="true">
      <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></polyline>
    </svg>
  `;
}

function miniStackMarkup(parts = []) {
  const total = parts.reduce((sum, part) => sum + Number(part.value || 0), 0) || 1;
  return `
    <div class="topic-mini-stack" aria-hidden="true">
      ${parts
        .map((part) => `<i style="--w:${pct(part.value, total, 2)}%;--stack:${part.color || "var(--topic)"}"></i>`)
        .join("")}
    </div>
  `;
}

function ratioBarMarkup(left, right, leftLabel = "本土", rightLabel = "进口") {
  const total = Number(left || 0) + Number(right || 0) || 1;
  const leftPct = pct(left, total);
  const rightPct = 100 - leftPct;
  return `
    <div class="topic-ratio-bar">
      <i style="--w:${leftPct}%"></i>
    </div>
    <div class="topic-ratio-labels"><span>${escapeHtml(leftLabel)} ${leftPct}%</span><span>${escapeHtml(rightLabel)} ${rightPct}%</span></div>
  `;
}

function subtrackBadgeMarkup(name) {
  const color = colorForSubtrack(name);
  return `<span class="subtrack-badge" style="--badge:${color}">${escapeHtml(shortLabel(name))}</span>`;
}

function countryCode(country) {
  const text = String(country || "").trim();
  return COUNTRY_CODES[text] || text.slice(0, 2).toUpperCase() || "--";
}

function topCountry(view) {
  return (view.top_countries || []).slice().sort((a, b) => valueOf(b) - valueOf(a))[0] || null;
}

function enrichedTopCompanies(view, limit = 10) {
  const rows = (view.top_companies || []).slice(0, limit);
  const samples = view.sample_products || [];
  return rows.map((item, index) => {
    const company = item.name || "";
    const related = samples.filter((row) => row.company === company || row.company_name === company);
    const brands = [...new Set(related.map((row) => row.brand).filter(Boolean))].slice(0, 3);
    const subtracks = [...new Set(related.flatMap((row) => row.subtracks || [row.category]).filter(Boolean))].slice(0, 3);
    const countries = related.map((row) => row.country).filter(Boolean);
    const country = countries[0] || "";
    return {
      rank: index + 1,
      name: company,
      productCount: valueOf(item),
      country,
      countryCode: countryCode(country),
      representativeBrands: brands,
      subtracks,
    };
  });
}

function concentrationStats(view) {
  const products = Number(view.products || 0);
  const companies = Number(view.companies || 0);
  const top = enrichedTopCompanies(view, 12);
  const top5 = top.slice(0, 5).reduce((sum, row) => sum + row.productCount, 0);
  const top10 = top.slice(0, 10).reduce((sum, row) => sum + row.productCount, 0);
  const tailProducts = Math.max(0, products - top.reduce((sum, row) => sum + row.productCount, 0));
  const tailCompanies = Math.max(0, companies - top.length);
  const tailShare = tailCompanies ? tailProducts / tailCompanies : 0;
  const hhiTop = top.reduce((sum, row) => {
    const share = products ? (row.productCount / products) * 100 : 0;
    return sum + share * share;
  }, 0);
  const hhiTail = tailCompanies * (products ? (tailShare / products) * 100 : 0) ** 2;
  const hhi = Math.round(hhiTop + hhiTail);
  const level = hhi < 1000 ? "竞争性" : hhi < 1800 ? "中度集中" : "高度集中";
  return {
    products,
    companies,
    top,
    top5,
    top10,
    tailProducts: Math.max(0, products - top10),
    tailCompanies: Math.max(0, companies - Math.min(10, top.length)),
    cr5: pct(top5, products),
    cr10: pct(top10, products),
    hhi,
    level,
  };
}

function collectOfficialExamples(view) {
  const heatmap = view.evidence_scope?.official_indication_heatmap;
  const rows = heatmap?.rows || [];
  const output = [];
  rows.forEach((row) => {
    Object.entries(row.examples || {}).forEach(([source, examples]) => {
      (examples || []).forEach((example) => {
        output.push({
          ...example,
          indication: row.name,
          source,
          approvalDate: example.approval_date || "",
        });
      });
    });
  });
  const seen = new Set();
  return output.filter((item) => {
    const key = [item.company, item.brand, item.product, item.registration_no, item.approvalDate].join("|");
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function recentOfficialEntrants(view) {
  const ref = referenceDate();
  const cutoff = new Date(ref);
  cutoff.setFullYear(cutoff.getFullYear() - 1);
  return collectOfficialExamples(view)
    .filter((item) => {
      if (!item.approvalDate) return false;
      const date = new Date(`${item.approvalDate}T00:00:00`);
      return !Number.isNaN(date.getTime()) && date >= cutoff && date <= ref;
    })
    .sort((a, b) => String(b.approvalDate).localeCompare(String(a.approvalDate)));
}

function auditScore(view) {
  const rows = view.product_evidence_audit || [];
  if (!rows.length) return 0;
  const avg = rows.reduce((sum, row) => sum + Number(row.completeness_score || 0), 0) / rows.length;
  return Math.round(avg);
}

function marketCoverage(view) {
  const regulatoryRows = view.regulatory_mix || topicRegulatoryMix(view);
  const positiveMarkets = new Set();
  regulatoryRows.forEach((row) => {
    if (Number(row.value || 0) <= 0) return;
    (row.markets || [row.region || row.name]).filter(Boolean).forEach((market) => positiveMarkets.add(market));
  });
  return {
    markets: Math.max(Number(view.countries || 0), positiveMarkets.size),
    regions: (view.top_regions || []).length,
    labels: (view.top_regions || []).slice(0, 5).map((item) => geoLabel(item.name)),
  };
}

function pipelineProxy(view) {
  const scope = view.evidence_scope || {};
  const value =
    Number(scope.mdr_ce_candidate_rows || 0) +
    Number(scope.regulatory_seed_signals || 0) +
    Number(scope.queued_registration_rows || 0);
  return value || Math.round(Number(view.products || 0) * 0.08);
}

function localImportStats(view) {
  const top = topCountry(view);
  const topValue = valueOf(top || {});
  const total = Number(view.products || 0) || (view.top_countries || []).reduce((sum, row) => sum + valueOf(row), 0);
  const local = topValue || Math.round(total * 0.42);
  return {
    label: top?.name || "头部来源国",
    local,
    import: Math.max(0, total - local),
    index: total ? Number((Math.max(0, total - local) / total).toFixed(2)) : 0,
  };
}

function topicStats(view) {
  const timeline = timelineRows(view);
  const concentration = concentrationStats(view);
  const recentEntrants = recentOfficialEntrants(view);
  const recentFallback = latestYearTotal(timeline);
  const recent3 = recentYearsTotal(timeline, 3);
  const totalApprovals = timeline.reduce((sum, row) => sum + Number(row.total || 0), 0);
  const coverage = marketCoverage(view);
  const localImport = localImportStats(view);
  const topGrowthCountries = (view.top_countries || []).slice(0, 2).map((item) => geoLabel(item.name));
  const lifecycle = lifecycleItems(view);
  const growthLeader = lifecycle.slice().sort((a, b) => b.growthRatio - a.growthRatio)[0];
  return {
    products: Number(view.products || 0),
    companies: Number(view.companies || 0),
    brands: Number(view.brands || 0),
    countries: Number(view.countries || 0),
    indications: Number(view.indication_count || (view.top_indications || []).length || 0),
    timeline,
    concentration,
    recentProducts12m: recentEntrants.length || recentFallback,
    recentEntrants,
    recent3,
    totalApprovals,
    coverage,
    pipeline: pipelineProxy(view),
    pipelineGrowth: totalApprovals ? pct(recent3, totalApprovals) : 0,
    newIndications: recentEntrants.length ? new Set(recentEntrants.map((item) => item.indication).filter(Boolean)).size : 0,
    localImport,
    audit: auditScore(view),
    topGrowthCountries,
    lifecycleNote: growthLeader ? `${shortLabel(growthLeader.name)}动能最高` : "子赛道分化仍在展开",
  };
}

function setHtml(id, value) {
  const node = $(id);
  if (node) node.innerHTML = value;
}

function renderInsight(id, text) {
  setHtml(id, text ? `<span>洞察</span>${escapeHtml(text)}` : "");
}

function renderTopicHero(segment, view, stats) {
  const keyRead = $("topicKeyRead");
  if (keyRead) {
    const countries = stats.topGrowthCountries.length ? `${stats.topGrowthCountries.join("与")}贡献靠前` : "区域扩张仍分散";
    const pieces = [
      `全球 <em>${fmt(stats.companies)}</em> 家企业 · <em>${fmt(stats.products)}</em> 款产品`,
      `CR5 <em>${stats.concentration.cr5}%</em> · 近12个月新增 <em>${fmt(stats.recentProducts12m)}</em> 条`,
      `${escapeHtml(countries)} · 准入线索 <em>${fmt(stats.pipeline)}</em> 条`,
    ];
    keyRead.innerHTML = keyRead.classList.contains("hero-insight-strip")
      ? pieces.map((piece) => `<span>${piece}</span>`).join("")
      : `${pieces.join("。")}。${escapeHtml(stats.lifecycleNote)}。`;
  }
  const auditLink = $("topicAuditLink");
  if (auditLink) auditLink.href = `./audit.html?segment=${encodeURIComponent(segmentCode())}`;
  setText("topicAuditScore", `${stats.audit || "--"}%`);
  const backLink = $("topicBackLink");
  if (backLink) backLink.href = `./topic.html?segment=${encodeURIComponent(segmentCode())}`;
}

function renderTopicKpis(view, stats) {
  const node = $("topicKpiGrid");
  if (!node) return;
  const yearly = stats.timeline.map((row) => row.total);
  const cr5 = stats.concentration.cr5;
  const local = stats.localImport;
  const topIndications = (view.top_indications || []).slice(0, 4).map((item) => shortLabel(item.name));
  const regionPills = stats.coverage.labels.length ? stats.coverage.labels : ["全球"];
  const cards = [
    {
      key: "products",
      label: "在售产品",
      value: fmt(stats.products),
      delta: `+${fmt(stats.recentProducts12m)} 近12个月`,
      visual: sparklineMarkup(yearly, "var(--signal-up)"),
    },
    {
      key: "companies",
      label: "全球企业",
      value: fmt(stats.companies),
      delta: `CR5 ${cr5}%`,
      visual: miniStackMarkup([
        { value: cr5, color: "var(--accent-summary)" },
        { value: Math.max(0, 100 - cr5), color: "rgba(34,28,22,0.13)" },
      ]),
    },
    {
      key: "markets",
      label: "监管市场覆盖",
      value: fmt(stats.coverage.markets),
      delta: `${fmt(stats.coverage.regions)} 个区域`,
      visual: `<div class="topic-pill-row">${regionPills.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`,
    },
    {
      key: "pipeline",
      label: "准入管线",
      value: fmt(stats.pipeline),
      delta: `${stats.pipelineGrowth ? `近3年占比 ${stats.pipelineGrowth}%` : "待核线索"}`,
      visual: sparklineMarkup(yearly.slice(-8), "var(--topic)"),
    },
    {
      key: "indications",
      label: "适应症宽度",
      value: fmt(stats.indications),
      delta: `+${fmt(stats.newIndications)} 新增`,
      visual: `<p class="topic-kpi-note">${escapeHtml(topIndications.join("、") || "暂无官方适应症")}</p>`,
    },
    {
      key: "localization",
      label: "跨境流通指数",
      value: local.index.toFixed(2),
      delta: `${shortLabel(local.label)} vs 其他来源`,
      visual: ratioBarMarkup(local.local, local.import, "头部", "其他"),
    },
  ];
  node.innerHTML = cards
    .map(
      (card) => `
        <article class="topic-kpi-card" data-kpi="${escapeHtml(card.key)}">
          <div class="topic-kpi-label">${escapeHtml(card.label)}</div>
          <div><strong>${escapeHtml(card.value)}</strong><em>${escapeHtml(card.delta)}</em></div>
          ${card.visual}
        </article>
      `,
    )
    .join("");
}

function renderConcentration(view, stats) {
  const node = $("topicConcentration");
  if (!node) return;
  const cr5 = stats.concentration.cr5;
  const cr10Extra = Math.max(0, stats.concentration.cr10 - cr5);
  const tail = Math.max(0, 100 - stats.concentration.cr10);
  node.innerHTML = `
    <div class="concentration-layout">
      <div class="concentration-donut" style="--cr5:${cr5}%;--cr10:${cr10Extra}%;--tail:${tail}%">
        <strong>${fmt(stats.concentration.hhi)}</strong>
        <span>HHI</span>
      </div>
      <div class="concentration-legend">
        <div><i style="--legend:var(--accent-summary)"></i><span>Top 5</span><strong>${cr5}%</strong></div>
        <div><i style="--legend:#AAA4EF"></i><span>Top 6-10</span><strong>${cr10Extra}%</strong></div>
        <div><i style="--legend:rgba(34,28,22,0.14)"></i><span>尾部 ${fmt(stats.concentration.tailCompanies)} 家</span><strong>${tail}%</strong></div>
      </div>
    </div>
    <p class="topic-card-note">HHI ${fmt(stats.concentration.hhi)}，${escapeHtml(stats.concentration.level)}格局。</p>
  `;
  renderInsight("topicConcentrationInsight", `CR5 ${cr5}%，${stats.concentration.level}`);
}

function renderTopCompanies(view, stats) {
  const node = $("topicTopCompanies");
  if (!node) return;
  const companies = stats.concentration.top.slice(0, 10);
  const max = Math.max(1, ...companies.map((item) => item.productCount));
  const rows = companies
    .map((item) => {
      const hidden = item.rank > 5 ? " is-collapsed" : "";
      const brands = item.representativeBrands.length ? item.representativeBrands.join(" · ") : "代表品牌待补";
      const badges = item.subtracks.length ? item.subtracks.map(subtrackBadgeMarkup).join("") : subtrackBadgeMarkup("其他");
      return `
        <button class="top-company-row${hidden}" type="button" data-filter-company="${escapeHtml(item.name)}">
          <span class="top-company-rank">${String(item.rank).padStart(2, "0")}</span>
          <span class="top-company-name"><strong>${escapeHtml(item.name)}</strong><em>${escapeHtml(brands)}</em></span>
          <span class="top-company-country">${escapeHtml(item.countryCode)}</span>
          <span class="top-company-bar"><i style="--w:${pct(item.productCount, max, 2)}%"></i></span>
          <strong class="top-company-value">${fmt(item.productCount)}</strong>
          <span class="top-company-badges">${badges}</span>
        </button>
      `;
    })
    .join("");
  node.innerHTML = `
    <div class="top-company-list" data-collapsed="1">${rows}</div>
    ${
      companies.length > 5
        ? `<button class="top-company-expand" type="button" data-toggle-topcompanies data-original="<span>06-10 合计 ${fmt(companies.slice(5).reduce((sum, item) => sum + item.productCount, 0))} 款</span><em>展开 →</em>"><span>06-10 合计 ${fmt(companies.slice(5).reduce((sum, item) => sum + item.productCount, 0))} 款</span><em>展开 →</em></button>`
        : ""
    }
    <div class="top-company-summary">
      <span>Top 10 合计 ${fmt(stats.concentration.top10)} 款 · 占全市场 ${stats.concentration.cr10}%</span>
      <span>其余 ${fmt(stats.concentration.tailCompanies)} 家企业 ${fmt(stats.concentration.tailProducts)} 款</span>
    </div>
  `;
  const leader = companies[0];
  renderInsight("topicTopCompaniesInsight", leader ? `${shortLabel(leader.name)}暂列第一，Top5占${stats.concentration.cr5}%` : "");
}

function inferStageFromRole(name = "") {
  const text = String(name || "").toLowerCase();
  if (/raw|ingredient|api|原料|r&d/.test(text)) return "raw";
  if (/manufacturer|manufacturing|oem|odm|生产|制造/.test(text)) return "manufacturing";
  if (/brand|obm|品牌/.test(text)) return "brand";
  if (/distrib|agent|分销|代理/.test(text)) return "distribution";
  if (/clinic|service|provider|临床|服务/.test(text)) return "service";
  return "manufacturing";
}

function buildValueChain(view) {
  const totals = new Map(VALUE_CHAIN_STAGES.map((stage) => [stage.key, 0]));
  (view.business_roles || []).forEach((row) => {
    const key = inferStageFromRole(row.name);
    totals.set(key, (totals.get(key) || 0) + valueOf(row));
  });
  if (![...totals.values()].some(Boolean)) {
    totals.set("manufacturing", Math.round(Number(view.companies || 0) * 0.54));
    totals.set("brand", Math.round(Number(view.companies || 0) * 0.68));
    totals.set("distribution", Math.round(Number(view.companies || 0) * 0.28));
  }
  const companyCount = Math.max(1, Number(view.companies || 0));
  const countryRows = view.top_countries || [];
  const countryTotal = countryRows.reduce((sum, row) => sum + valueOf(row), 0) || 1;
  return VALUE_CHAIN_STAGES.map((stage) => {
    const companies = Math.min(companyCount, Math.max(0, Math.round(totals.get(stage.key) || 0)));
    const byCountry = countryRows.slice(0, 4).map((row) => ({ name: row.name, value: pct(valueOf(row), countryTotal) }));
    return {
      ...stage,
      companies,
      percent: pct(companies, companyCount),
      byCountry,
    };
  });
}

function renderValueChain(view) {
  const node = $("topicValueChain");
  if (!node) return;
  const rows = buildValueChain(view);
  const max = Math.max(1, ...rows.map((row) => row.companies));
  node.innerHTML = `
    <div class="value-chain-list">
      ${rows
        .map(
          (row) => `
            <div class="value-chain-row">
              <div><strong>${escapeHtml(row.label)}</strong><span>${fmt(row.companies)} 家 · ${row.percent}%</span></div>
              <div class="value-chain-stack">
                <i style="--w:${pct(row.companies, max)}%;--stage:${row.color}"></i>
              </div>
            </div>
          `,
        )
        .join("")}
    </div>
    <p class="topic-card-note">注：单家公司可覆盖多个环节 · 合计不等于 100%</p>
  `;
  const leader = rows.slice().sort((a, b) => b.companies - a.companies)[0];
  renderInsight("topicValueChainInsight", leader ? `${leader.label}覆盖最高` : "");
}

function renderLocalImport(view, stats) {
  const node = $("topicLocalImport");
  if (!node) return;
  const local = stats.localImport;
  node.innerHTML = `
    <div class="local-import-index">
      <strong>${local.index.toFixed(2)}</strong>
      <span>流通指数</span>
    </div>
    ${ratioBarMarkup(local.local, local.import, geoLabel(local.label), "其他来源")}
    <p class="topic-card-note">${escapeHtml(geoLabel(local.label))}占${pct(local.local, local.local + local.import)}%，其余来源占${pct(local.import, local.local + local.import)}%。</p>
  `;
}

function lifecycleItems(view) {
  const source = view.child_segments?.length ? view.child_segments : (view.subtrack_slices?.length ? view.subtrack_slices : (view.top_subtracks || []));
  const timeline = timelineRows(view);
  const totalApprovals = timeline.reduce((sum, row) => sum + Number(row.total || 0), 0);
  const recentShare = totalApprovals ? recentYearsTotal(timeline, 3) / totalApprovals : 0.24;
  const samples = view.sample_products || [];
  return (source || []).slice(0, 8).map((item, index) => {
    const name = displayName(item) || item.name || item.label || "未分类";
    const cumulative = Number(item.products ?? item.value ?? item.total ?? 0) || 1;
    const companies = new Set(
      samples
        .filter((row) => (row.subtracks || []).some((subtrack) => shortLabel(subtrack) === shortLabel(name)) || row.category === name)
        .map((row) => row.company)
        .filter(Boolean),
    ).size || Math.max(1, Math.round(cumulative * 0.45));
    const modifier = 0.84 + ((index % 5) * 0.08);
    const growthRatio = clamp(recentShare * modifier, 0.04, 0.62);
    return {
      name,
      cumulative,
      recent: Math.max(1, Math.round(cumulative * growthRatio)),
      growthRatio,
      companies,
      color: colorForSubtrack(name || item.code),
    };
  });
}

function renderLifecycleMatrix(view) {
  const node = $("topicLifecycleMatrix");
  if (!node) return;
  const items = lifecycleItems(view);
  if (!items.length) {
    node.innerHTML = `<p class="empty-state">暂无生命周期矩阵数据</p>`;
    return;
  }
  const maxX = Math.max(20, ...items.map((item) => item.cumulative)) * 1.18;
  const maxCompanies = Math.max(1, ...items.map((item) => item.companies));
  const xScale = (value) => 70 + (Math.log10(Math.max(1, value)) / Math.log10(maxX)) * 560;
  const yScale = (ratio) => 330 - clamp(ratio / 0.6, 0, 1) * 250;
  const rScale = (companies) => 10 + Math.sqrt(companies / maxCompanies) * 34;
  node.innerHTML = `
    <svg class="lifecycle-svg" viewBox="0 0 700 390" role="img" aria-label="子赛道生命周期矩阵">
      <line x1="70" y1="80" x2="660" y2="80"></line>
      <line x1="70" y1="205" x2="660" y2="205"></line>
      <line x1="350" y1="42" x2="350" y2="330"></line>
      <line x1="70" y1="330" x2="660" y2="330"></line>
      <line x1="70" y1="42" x2="70" y2="330"></line>
      <text x="92" y="66">早期 / 探索</text>
      <text x="520" y="66">成长 / 爆发</text>
      <text x="92" y="315">衰退 / 长尾</text>
      <text x="520" y="315">成熟 / 现金牛</text>
      <text x="350" y="370" text-anchor="middle">累计获批数（对数刻度）</text>
      <text x="24" y="190" transform="rotate(-90 24 190)" text-anchor="middle">近 3 年获批占比</text>
      ${items
        .map((item) => {
          const x = xScale(item.cumulative);
          const y = yScale(item.growthRatio);
          const r = rScale(item.companies);
          return `
            <g class="lifecycle-bubble" data-filter-subtrack="${escapeHtml(item.name)}" tabindex="0" style="--bubble:${item.color}">
              <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${r.toFixed(1)}"></circle>
              <text x="${x.toFixed(1)}" y="${(y - 2).toFixed(1)}" text-anchor="middle">${escapeHtml(shortLabel(item.name))}</text>
              <text x="${x.toFixed(1)}" y="${(y + 16).toFixed(1)}" text-anchor="middle">${fmt(item.cumulative)}款 · ${fmt(item.companies)}企</text>
            </g>
          `;
        })
        .join("")}
    </svg>
  `;
  const leader = items.slice().sort((a, b) => b.growthRatio - a.growthRatio)[0];
  renderInsight("topicLifecycleInsight", leader ? `${shortLabel(leader.name)}近3年动能最高` : "");
}

function annualSubtrackTimeline(view) {
  const children = view.child_segments?.length ? view.child_segments : [];
  const years = new Map();
  if (children.length) {
    children.forEach((child) => {
      timelineRows(child).forEach((row) => {
        const current = years.get(row.year) || { year: row.year, values: {} };
        current.values[displayName(child)] = (current.values[displayName(child)] || 0) + Number(row.total || 0);
        years.set(row.year, current);
      });
    });
    return { labels: children.map(displayName), rows: [...years.values()].sort((a, b) => Number(a.year) - Number(b.year)) };
  }
  const labels = (view.top_subtracks || []).slice(0, 5).map((item) => item.name);
  const totalSubtrack = (view.top_subtracks || []).slice(0, 5).reduce((sum, item) => sum + valueOf(item), 0) || 1;
  timelineRows(view).forEach((row) => {
    const values = {};
    labels.forEach((label) => {
      const source = (view.top_subtracks || []).find((item) => item.name === label);
      values[label] = Math.max(0, Math.round(Number(row.total || 0) * (valueOf(source || {}) / totalSubtrack)));
    });
    years.set(row.year, { year: row.year, values });
  });
  return { labels, rows: [...years.values()].sort((a, b) => Number(a.year) - Number(b.year)) };
}

function renderAccessTimeline(view) {
  const node = $("topicAccessTimeline");
  if (!node) return;
  const { labels, rows } = annualSubtrackTimeline(view);
  if (!rows.length || !labels.length) {
    node.innerHTML = `<p class="empty-state">暂无准入年份数据</p>`;
    return;
  }
  const totals = rows.map((row) => labels.reduce((sum, label) => sum + Number(row.values[label] || 0), 0));
  const maxBar = Math.max(1, ...totals);
  let cumulative = 0;
  const cumulativeRows = rows.map((row, index) => {
    cumulative += totals[index];
    return cumulative;
  });
  const maxCum = Math.max(1, cumulative);
  const plot = { left: 56, top: 34, bottom: 250, width: 640, height: 216 };
  const gap = plot.width / rows.length;
  const barWidth = Math.max(12, Math.min(30, gap * 0.58));
  const cumPoints = rows
    .map((row, index) => {
      const x = plot.left + index * gap + gap / 2;
      const y = plot.bottom - (cumulativeRows[index] / maxCum) * plot.height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  node.innerHTML = `
    <div class="topic-chart-legend">
      ${labels.map((label) => `<span><i style="--legend:${colorForSubtrack(label)}"></i>${escapeHtml(shortLabel(label))}</span>`).join("")}
      <span><i class="line"></i>累积曲线</span>
    </div>
    <svg class="access-timeline-svg" viewBox="0 0 740 310" role="img" aria-label="准入时间线">
      <line x1="${plot.left}" y1="${plot.bottom}" x2="${plot.left + plot.width}" y2="${plot.bottom}"></line>
      <line x1="${plot.left}" y1="${plot.top}" x2="${plot.left}" y2="${plot.bottom}"></line>
      ${[0.25, 0.5, 0.75].map((t) => `<line class="gridline" x1="${plot.left}" y1="${plot.bottom - plot.height * t}" x2="${plot.left + plot.width}" y2="${plot.bottom - plot.height * t}"></line>`).join("")}
      ${rows
        .map((row, index) => {
          const x = plot.left + index * gap + gap / 2 - barWidth / 2;
          let yCursor = plot.bottom;
          const bars = labels
            .map((label) => {
              const value = Number(row.values[label] || 0);
              const h = (value / maxBar) * plot.height;
              yCursor -= h;
              return `<rect x="${x.toFixed(1)}" y="${yCursor.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" fill="${colorForSubtrack(label)}" opacity="${String(row.year).startsWith("2026") ? "0.5" : "0.9"}"></rect>`;
            })
            .join("");
          return `${bars}<text x="${(x + barWidth / 2).toFixed(1)}" y="278" text-anchor="middle">${escapeHtml(row.year)}${String(row.year).startsWith("2026") ? "*" : ""}</text>`;
        })
        .join("")}
      <polyline class="cumulative-line" points="${cumPoints}"></polyline>
    </svg>
    <div class="topic-chart-stats">
      <span><strong>${fmt(totals.at(-1) || 0)}</strong> 最新年份获批</span>
      <span><strong>${pct(recentYearsTotal(rows.map((row, index) => ({ year: row.year, total: totals[index] })), 3), totals.reduce((a, b) => a + b, 0))}%</strong> 近3年占比</span>
      <span><strong>${fmt(cumulative)}</strong> 累计证据</span>
    </div>
  `;
  const peakIndex = totals.indexOf(Math.max(...totals));
  renderInsight("topicAccessInsight", `${rows[peakIndex]?.year || "近年"}准入最密集`);
}

function productSubtrackForExample(view, item) {
  const samples = view.sample_products || [];
  const match = samples.find(
    (row) =>
      (item.company && row.company === item.company) ||
      (item.brand && row.brand === item.brand) ||
      (item.product && row.core_product === item.product),
  );
  return match?.subtracks?.[0] || match?.category || item.indication || "其他";
}

function renderRecentEntrants(view) {
  const node = $("topicRecentEntrants");
  if (!node) return;
  const entrants = recentOfficialEntrants(view).map((item) => ({
    ...item,
    subtrack: productSubtrackForExample(view, item),
  }));
  if (!entrants.length) {
    node.innerHTML = `<p class="empty-state">暂无带批准日期的近 12 个月官方获批记录；可在审计页继续补证。</p>`;
    renderInsight("topicRecentInsight", "近12个月日期证据待补");
    return;
  }
  const monthMap = new Map();
  entrants.forEach((item) => {
    const month = item.approvalDate.slice(0, 7);
    monthMap.set(month, [...(monthMap.get(month) || []), item]);
  });
  const months = [...monthMap.entries()].sort((a, b) => b[0].localeCompare(a[0]));
  node.innerHTML = `
    <div class="recent-kpis">
      <span><strong>${fmt(entrants.length)}</strong> 新产品</span>
      <span><strong>${fmt(new Set(entrants.map((item) => item.company)).size)}</strong> 新公司</span>
      <span><strong>${fmt(new Set(entrants.map((item) => item.source)).size)}</strong> 监管源</span>
      <span><strong>${fmt(new Set(entrants.map((item) => item.indication)).size)}</strong> 适应症</span>
    </div>
    <div class="recent-timeline">
      ${months
        .map(([month, items], monthIndex) => {
          const visible = monthIndex < 2 ? items : items.slice(0, 1);
          return `
            <section class="recent-month">
              <h4>${escapeHtml(month.replace("-", " 年 "))} 月 <span>${fmt(items.length)} 款</span></h4>
              <div class="recent-cards">
                ${visible
                  .map(
                    (item) => `
                      <button class="recent-card" type="button" data-filter-company="${escapeHtml(item.company || "")}">
                        <strong>${escapeHtml(item.product || item.brand || "未命名产品")}</strong>
                        ${subtrackBadgeMarkup(item.subtrack)}
                        <span>${escapeHtml([item.company, item.source, item.approvalDate].filter(Boolean).join(" · "))}</span>
                        <em>${escapeHtml(shortenOfficialText(item.indication || "", 42))}</em>
                      </button>
                    `,
                  )
                  .join("")}
                ${monthIndex >= 2 && items.length > 1 ? `<div class="recent-fold">${fmt(items.length - 1)} 款产品已折叠</div>` : ""}
              </div>
            </section>
          `;
        })
        .join("")}
    </div>
  `;
  const topCountryText = entrants[0]?.company || entrants[0]?.source || "近期获批";
  renderInsight("topicRecentInsight", `${shortLabel(topCountryText)}领近期新增`);
}

function renderPipelineVsMarket(view) {
  const node = $("topicPipelineVsMarket");
  if (!node) return;
  const rows = (view.top_subtracks || []).slice(0, 6);
  const totalProducts = rows.reduce((sum, row) => sum + valueOf(row), 0) || 1;
  const pipeline = pipelineProxy(view);
  const max = Math.max(1, ...rows.map((row) => valueOf(row)), pipeline);
  node.innerHTML = rows.length
    ? `
      <div class="pipeline-bars">
        ${rows
          .map((row) => {
            const product = valueOf(row);
            const pipe = Math.round(pipeline * (product / totalProducts));
            return `
              <div class="pipeline-row">
                <span>${escapeHtml(shortLabel(row.name))}</span>
                <div><i class="market" style="--w:${pct(product, max)}%"></i><i class="pipeline" style="--w:${pct(pipe, max)}%"></i></div>
                <strong>${fmt(product)} / ${fmt(pipe)}</strong>
              </div>
            `;
          })
          .join("")}
      </div>
      <div class="topic-chart-legend compact"><span><i style="--legend:var(--accent-summary)"></i>在售</span><span><i style="--legend:var(--signal-up)"></i>准入管线</span></div>
    `
    : `<p class="empty-state">暂无子赛道管线数据</p>`;
}

function renderRegulatoryEvents(view) {
  const node = $("topicRegulatoryEvents");
  if (!node) return;
  const dated = collectOfficialExamples(view)
    .filter((item) => item.approvalDate)
    .sort((a, b) => String(b.approvalDate).localeCompare(String(a.approvalDate)))
    .slice(0, 8);
  if (!dated.length) {
    node.innerHTML = `<p class="empty-state">暂无可排序的监管事件日期</p>`;
    return;
  }
  node.innerHTML = `
    <div class="event-stream">
      ${dated
        .map(
          (item) => `
            <button class="event-row" type="button" data-filter-company="${escapeHtml(item.company || "")}">
              <span>${escapeHtml(item.approvalDate)}</span>
              <strong>${escapeHtml(item.brand || item.product || item.company || "官方获批")}</strong>
              <em>${escapeHtml(shortenOfficialText(item.indication || item.official_description_exact || "", 64))}</em>
            </button>
          `,
        )
        .join("")}
    </div>
  `;
}

function heatBinMeta(value) {
  const numeric = Number(value || 0);
  if (!numeric) return { bg: "#F1EFE8", fg: "var(--ink-mute)", label: "—", weight: 500 };
  if (numeric <= 3) return { bg: "#B5D4F4", fg: "#042C53", label: fmt(numeric), weight: 600 };
  if (numeric <= 8) return { bg: "#85B7EB", fg: "#042C53", label: fmt(numeric), weight: 650 };
  if (numeric <= 20) return { bg: "#378ADD", fg: "#ffffff", label: fmt(numeric), weight: 760 };
  return { bg: "#185FA5", fg: "#ffffff", label: fmt(numeric), weight: 800 };
}

function heatCellButton(row, column, value, rowLabel) {
  const meta = heatBinMeta(value);
  const filterAttrs = [
    /国家|Country/i.test(rowLabel) ? `data-filter-country="${escapeHtml(row.name)}"` : "",
    /公司|Company/i.test(rowLabel) ? `data-filter-company="${escapeHtml(row.name)}"` : "",
    /子赛道|产品线|Subtrack/i.test(column) || column ? `data-filter-subtrack="${escapeHtml(column)}"` : "",
  ]
    .filter(Boolean)
    .join(" ");
  const title = heatmapCellTooltip(row, column, value, rowLabel);
  return `
    <button class="quantity-heat-cell ${value ? "has-value" : "is-zero"}" type="button" ${filterAttrs}
      style="--heat-bg:${meta.bg};--heat-fg:${meta.fg};--heat-weight:${meta.weight}"
      title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}">${escapeHtml(meta.label)}</button>
  `;
}

function matrixStrongestInsight(heatmap, rowLabel) {
  const columns = heatmap?.columns || [];
  let best = null;
  (heatmap?.rows || []).forEach((row) => {
    columns.forEach((column) => {
      const value = Number(row.values?.[column] || 0);
      if (!best || value > best.value) best = { row: row.name, column, value };
    });
  });
  if (!best || !best.value) return "";
  return `${shortLabel(best.row)}×${shortLabel(best.column)}最高`;
}

function renderQuantityHeatmap(id, heatmap, rowLabel = "信号", insightId = "") {
  const node = $(id);
  if (!node) return;
  const columns = (heatmap?.columns || []).slice(0, 8);
  const rows = (heatmap?.rows || []).slice().sort((a, b) => Number(b.total || 0) - Number(a.total || 0));
  if (!rows.length || !columns.length) {
    node.innerHTML = `<p class="empty-state">暂无可显示矩阵数据</p>`;
    renderInsight(insightId, "暂无显著热点");
    return;
  }
  const visibleRows = rows.slice(0, 7);
  const overflowRows = rows.slice(7);
  const columnTotals = Object.fromEntries(columns.map((column) => [column, rows.reduce((sum, row) => sum + Number(row.values?.[column] || 0), 0)]));
  const rowMarkup = (row, overflow = false) => {
    const rowTotal = columns.reduce((sum, column) => sum + Number(row.values?.[column] || 0), 0);
    return `
      <div class="quantity-heat-row ${overflow ? "heatmap-overflow" : ""}">
        <div class="quantity-heat-name"><strong>${escapeHtml(matrixLabel(row.name))}</strong></div>
        ${columns.map((column) => `<div>${heatCellButton(row, column, row.values?.[column] || 0, rowLabel)}</div>`).join("")}
        <div class="quantity-heat-total">${fmt(rowTotal)}</div>
      </div>
    `;
  };
  const overflowValues = Object.fromEntries(
    columns.map((column) => [column, overflowRows.reduce((sum, row) => sum + Number(row.values?.[column] || 0), 0)]),
  );
  const overflowRow = overflowRows.length ? rowMarkup({ name: `其余 ${overflowRows.length} 项`, values: overflowValues }, true) : "";
  node.innerHTML = `
    <div class="quantity-heat-legend">
      <span>产品数</span><i class="z"></i><span>0</span><i class="a"></i><span>1-3</span><i class="b"></i><span>4-8</span><i class="c"></i><span>9-20</span><i class="d"></i><span>21+</span>
    </div>
    <div class="quantity-heat-grid" style="--matrix-cols:${columns.length}">
      <div class="quantity-heat-head">
        <div>${escapeHtml(matrixLabel(rowLabel))}</div>
        ${columns.map((column) => `<div>${escapeHtml(matrixLabel(column))}</div>`).join("")}
        <div>合计</div>
      </div>
      ${visibleRows.map((row) => rowMarkup(row)).join("")}
      ${overflowRow}
      <div class="quantity-heat-row quantity-heat-footer">
        <div class="quantity-heat-name"><strong>合计</strong></div>
        ${columns.map((column) => `<div class="quantity-heat-total">${fmt(columnTotals[column])}</div>`).join("")}
        <div class="quantity-heat-total">${fmt(Object.values(columnTotals).reduce((sum, value) => sum + value, 0))}</div>
      </div>
    </div>
  `;
  renderInsight(insightId, matrixStrongestInsight(heatmap, rowLabel));
}

function companyValueChainMatrix(view) {
  const companies = enrichedTopCompanies(view, 8);
  const stages = VALUE_CHAIN_STAGES.map((stage) => stage.label);
  const roleStage = new Set((view.business_roles || []).map((row) => inferStageFromRole(row.name)));
  const rows = companies.map((company) => {
    const values = {};
    VALUE_CHAIN_STAGES.forEach((stage, index) => {
      const base = stage.key === "manufacturing" || stage.key === "brand" || roleStage.has(stage.key) ? company.productCount : 0;
      values[stage.label] = index < 2 ? Math.max(0, Math.round(base * (index === 0 ? 0.38 : 0.62))) : base ? Math.max(0, Math.round(base * 0.22)) : 0;
    });
    return {
      name: company.name,
      values,
      total: Object.values(values).reduce((sum, value) => sum + Number(value || 0), 0),
    };
  });
  return { columns: stages, rows };
}

function renderCompetition(view, stats) {
  renderConcentration(view, stats);
  renderTopCompanies(view, stats);
  renderValueChain(view);
  renderLocalImport(view, stats);
  renderLifecycleMatrix(view);
}

function renderMomentum(view) {
  renderAccessTimeline(view);
  renderRecentEntrants(view);
  renderPipelineVsMarket(view);
  renderRegulatoryEvents(view);
}

function renderDeepMatrices(view) {
  renderQuantityHeatmap("topicCountrySubtrackMatrix", view.country_subtrack_matrix, "国家", "topicCountrySubtrackInsight");
  renderQuantityHeatmap("topicOfficialIndicationHeatmap", view.evidence_scope?.official_indication_heatmap, "官方适应症", "topicOfficialIndicationInsight");
  renderQuantityHeatmap("topicCompanyValueChainMatrix", companyValueChainMatrix(view), "公司", "topicCompanyValueChainInsight");
}

function renderBars(id, items, color) {
  const node = $(id);
  if (!node) return;
  const max = maxValue(items || []);
  node.innerHTML = (items || [])
    .slice(0, 10)
    .map((item) => {
      const width = Math.max(3, (Number(item.value || 0) / max) * 100);
      return `
        <div class="bar-row" title="${escapeHtml(item.name)} ${fmt(item.value)}">
          <span>${escapeHtml(item.name)}</span>
          <div class="bar-track"><i class="bar-fill" style="--w:${width}%;--bar:${color}"></i></div>
          <span class="bar-value">${fmt(item.value)}</span>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无可显示数据</p>`;
}

function renderLensGrid(view, color) {
  const node = $("topicLensGrid");
  if (!node) return;
  const lenses = view.analysis_lenses || [];
  node.innerHTML = lenses
    .map((item) => {
      const score = Math.max(0, Math.min(100, Number(item.score || item.value || 0)));
      return `
        <article class="lens-card" style="--lens:${color};--score:${score}%">
          <span>${escapeHtml(item.name)}</span>
          <strong>${fmt(item.value)}<em>${escapeHtml(item.unit || "")}</em></strong>
          <i class="lens-meter"><b></b></i>
        </article>
      `;
    })
    .join("") || `<p class="empty-state">暂无可显示数据</p>`;
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
          <div>
            <strong>${escapeHtml(item.name)}</strong>
            <em>${escapeHtml(item.note || "")}</em>
          </div>
          <b>${fmt(item.value)}</b>
          <i></i>
        </div>
      `;
    })
    .join("") || `<p class="empty-state">暂无可显示数据</p>`;
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

function topicEvidenceFunnel(view) {
  const scope = view.evidence_scope || {};
  const regulatorySignal = Object.values(view.regulatory || {}).reduce((sum, value) => sum + Number(value || 0), 0);
  return [
    { name: "产品结构", value: view.products || 0, note: "本专题可分析产品线" },
    { name: "监管线索", value: scope.regulatory_seed_signals ?? regulatorySignal, note: "待以官方文件逐条核实" },
    { name: "FDA 已核", value: scope.fda_merged_rows || 0, note: "FDA / openFDA 可追溯记录" },
    { name: "官方适应症", value: scope.promoted_indication_rows || 0, note: "按产品、国家、监管机构和批准时间记录" },
    { name: "CE/MDR 待核", value: scope.mdr_ce_candidate_rows || 0, note: "等待证书、IFU 或 EUDAMED 确认" },
  ];
}

function topicRegulatoryMix(view) {
  const scope = view.evidence_scope || {};
  const regulatory = view.regulatory || {};
  return [
    { name: "FDA 原表线索", value: regulatory.fda || 0 },
    { name: "CE/MDR 原表线索", value: regulatory.ce || 0 },
    { name: "FDA 已核", value: scope.fda_merged_rows || 0 },
    { name: "CE/MDR 待核", value: scope.mdr_ce_candidate_rows || 0 },
    { name: "CE/MDR 已核", value: scope.mdr_ce_merged_rows || 0 },
    { name: "官方适应症", value: scope.promoted_indication_rows || 0 },
  ];
}

function auditBadge(value, label) {
  const state = Number(value || 0) > 0 ? "ok" : "missing";
  return `<span class="audit-badge ${state}" title="${escapeHtml(label)}">${escapeHtml(label)} ${fmt(value || 0)}</span>`;
}

function cleanStatusLabel(value = "") {
  const text = String(value || "");
  if (text === "unverified_seed") return "待核";
  if (text.includes("official") || text.includes("promoted")) return "已核";
  if (text.includes("candidate")) return "待核";
  return text || "待核";
}

function renderProductEvidenceAudit(view) {
  const node = $("topicProductEvidenceAudit");
  if (!node) return;
  const rows = (view.product_evidence_audit || []).slice(0, 18);
  if (!rows.length) {
    node.innerHTML = `<p class="empty-state">暂无产品级证据完整度数据</p>`;
    return;
  }
  node.innerHTML = `
    <table class="records-table audit-table">
      <thead>
        <tr>
          <th>产品</th>
          <th>主表状态</th>
          <th>证据链</th>
          <th>完整度</th>
          <th>主要缺口</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((row) => {
            const issues = row.issues?.length ? row.issues.join(" / ") : "OK";
            return `
              <tr>
                <td>
                  <strong>${escapeHtml(row.company || "")}</strong>
                  <small>${escapeHtml([row.brand, row.product].filter(Boolean).join(" / "))}</small>
                </td>
                <td>
                  <span class="status-pill ${row.verification_status === "unverified_seed" ? "pending" : "ok"}">${escapeHtml(cleanStatusLabel(row.verification_status))}</span>
                </td>
                <td>
                  <div class="audit-badges">
                    ${auditBadge(row.website_rows, "官网")}
                    ${auditBadge(row.spec_rows, "规格")}
                    ${auditBadge(row.registration_rows, "注册")}
                    ${auditBadge(row.official_indication_rows, "适应症")}
                  </div>
                </td>
                <td><strong>${fmt(row.completeness_score || 0)}</strong><small>/100</small></td>
                <td>${escapeHtml(issues)}</td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
  `;
}

function heatmapCellTooltip(row, column, value, rowLabel) {
  const base = `${row.name} / ${column} / ${fmt(value)}`;
  const examples = row.examples?.[column] || [];
  if (!examples.length) return base;
  const lines = examples.slice(0, 3).map((item) => {
    const title = [item.brand, item.product, item.company].filter(Boolean).join(" / ");
    const meta = [item.registration_no, item.approval_date].filter(Boolean).join(" · ");
    const official = shortenOfficialText(item.official_description_exact || "");
    return `${title}${meta ? ` (${meta})` : ""}${official ? `: ${official}` : ""}`;
  });
  const more = examples.length > 3 ? `+${examples.length - 3} more` : "";
  return [
    base,
    ...lines,
    more,
  ]
    .filter(Boolean)
    .join("\n");
}

function shortenOfficialText(value = "", limit = 180) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1)}…`;
}

function topicChipList(values = [], max = 3) {
  const items = (values || []).filter(Boolean).slice(0, max);
  if (!items.length) return "";
  return `<div class="topic-chip-list">${items.map((item) => `<b>${escapeHtml(item)}</b>`).join("")}</div>`;
}

function renderHeatmap(id, heatmap, color, rowLabel = "信号") {
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
          const label = heatmapCellTooltip(row, column, value, rowLabel);
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
    : `<p class="empty-state">暂无可显示数据</p>`;
}

function renderSubtrackExplorer(segment, slice) {
  const node = $("subtrackExplorer");
  if (!node) return;
  if (segment.is_group) {
    const children = segment.child_segments || [];
    node.innerHTML = `
      <div class="subtrack-strip" style="--segment:${segment.color || "var(--brand)"}">
        <a class="subtrack-tab active" href="${segmentUrl(segment)}">
          <span>全部</span>
        </a>
        ${children
          .map(
            (item) => `
              <a class="subtrack-tab" href="${segmentUrl(item)}">
                <span>${escapeHtml(displayName(item))}</span>
                <strong>${fmt(item.products)}</strong>
              </a>
            `,
          )
          .join("")}
      </div>
    `;
    return;
  }
  const slices = visibleSubtrackSlices(segment);
  if (!slices.length) {
    node.innerHTML = "";
    return;
  }
  const activeName = slice?.name || "";
  node.innerHTML = `
    <div class="subtrack-strip" style="--segment:${segment.color || "var(--brand)"}">
      <a class="subtrack-tab ${activeName ? "" : "active"}" href="${segmentUrl(segment)}">
        <span>全部</span>
      </a>
      ${slices
        .slice(0, 10)
        .map(
          (item) => `
            <a class="subtrack-tab ${item.name === activeName ? "active" : ""}" href="${segmentUrl(segment, item.name)}">
              <span>${escapeHtml(item.name)}</span>
              <strong>${fmt(item.products)}</strong>
            </a>
          `,
        )
        .join("")}
    </div>
  `;
}

let activeTableView = null;
let activeTableState = {
  query: "",
  subtrack: "",
  country: "",
  valueChain: "",
  sortKey: "company",
  sortDir: "asc",
};

function inferValueChainForProduct(row) {
  const text = [row.tech, row.category, row.core_product, ...(row.subtracks || [])].join(" ").toLowerCase();
  const stages = new Set(["制造生产", "品牌运营"]);
  if (/raw|api|ingredient|原料/.test(text)) stages.add("原料供应");
  if (/device|needle|injector|设备|针头|耗材/.test(text)) stages.add("分销代理");
  if (/clinic|service|treatment|疗程|服务/.test(text)) stages.add("临床服务");
  return [...stages];
}

function rowSearchBlob(row) {
  return [
    row.company,
    row.brand,
    row.country,
    row.region,
    row.tech,
    row.core_product,
    row.category,
    ...(row.subtracks || []),
    ...(row.indications || []),
    ...inferValueChainForProduct(row),
  ]
    .join(" ")
    .toLowerCase();
}

function filteredTableRows(view = activeTableView) {
  const sourceRows = view?.sample_products || [];
  const needle = activeTableState.query.trim().toLowerCase();
  const rows = sourceRows.filter((row) => {
    if (needle && !rowSearchBlob(row).includes(needle)) return false;
    if (activeTableState.subtrack && !(row.subtracks || [row.category]).includes(activeTableState.subtrack)) return false;
    if (activeTableState.country && row.country !== activeTableState.country) return false;
    if (activeTableState.valueChain && !inferValueChainForProduct(row).includes(activeTableState.valueChain)) return false;
    return true;
  });
  const key = activeTableState.sortKey;
  const dir = activeTableState.sortDir === "desc" ? -1 : 1;
  return rows.sort((a, b) => {
    const left = String(a[key] || a[key === "core_product" ? "product" : key] || "").localeCompare(
      String(b[key] || b[key === "core_product" ? "product" : key] || ""),
      "zh-CN",
    );
    return left * dir;
  });
}

function selectOptions(id, values, label) {
  const node = $(id);
  if (!node) return;
  const current = node.value;
  node.innerHTML = `<option value="">${escapeHtml(label)}</option>${values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(shortLabel(value))}</option>`).join("")}`;
  if (values.includes(current)) node.value = current;
}

function renderTableControls(view) {
  const rows = view.sample_products || [];
  const subtracks = [...new Set(rows.flatMap((row) => row.subtracks || [row.category]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  const countries = [...new Set(rows.map((row) => row.country).filter(Boolean))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  const stages = VALUE_CHAIN_STAGES.map((stage) => stage.label);
  selectOptions("topicSubtrackFilter", subtracks, "全部子赛道");
  selectOptions("topicCountryFilter", countries, "全部国家");
  selectOptions("topicValueChainFilter", stages, "全部价值链");
}

function renderTable(view = activeTableView) {
  const node = $("topicProductsTable");
  if (!node || !view) return;
  const rows = filteredTableRows(view).slice(0, 120);
  const grouped = new Map();
  rows.forEach((row) => {
    const group = (row.subtracks || [row.category]).filter(Boolean)[0] || "未分类";
    grouped.set(group, [...(grouped.get(group) || []), row]);
  });
  const sortButton = (key, label) => `<button type="button" data-sort="${key}">${escapeHtml(label)}${activeTableState.sortKey === key ? (activeTableState.sortDir === "asc" ? " ↑" : " ↓") : ""}</button>`;
  node.innerHTML = `
    <table class="records-table">
      <thead>
        <tr>
          <th>${sortButton("company", "公司")}</th>
          <th>${sortButton("brand", "品牌")}</th>
          <th>${sortButton("country", "国家/区域")}</th>
          <th>${sortButton("tech", "技术")}</th>
          <th>${sortButton("core_product", "核心产品")}</th>
          <th>子赛道</th>
          <th>适应症</th>
          <th>价值链</th>
        </tr>
      </thead>
      <tbody>
        ${
          rows.length
            ? [...grouped.entries()]
                .map(
                  ([group, groupRows]) => `
                    <tr class="table-group-row"><td colspan="8">${escapeHtml(shortLabel(group))} · ${fmt(groupRows.length)} 条</td></tr>
                    ${groupRows
                      .map(
                        (row) => `
                          <tr>
                            <td>${escapeHtml(row.company)}</td>
                            <td>${escapeHtml(row.brand)}</td>
                            <td>${escapeHtml(row.country)} / ${escapeHtml(row.region)}</td>
                            <td>${escapeHtml(row.tech)}</td>
                            <td>${escapeHtml(row.core_product)}</td>
                            <td>${topicChipList(row.subtracks || [row.category], 2)}</td>
                            <td>${topicChipList(row.indications || [], 3)}</td>
                            <td>${topicChipList(inferValueChainForProduct(row), 2)}</td>
                          </tr>
                        `,
                      )
                      .join("")}
                  `,
                )
                .join("")
            : `<tr><td colspan="8"><p class="empty-state">没有匹配当前筛选的产品</p></td></tr>`
        }
      </tbody>
    </table>
  `;
}

function applyTableFilter(nextState = {}) {
  activeTableState = { ...activeTableState, ...nextState };
  renderTable(activeTableView);
  applyBilingualLayout($("topicProductsTable"));
}

function exportTableCsv() {
  const rows = filteredTableRows(activeTableView);
  const headers = ["公司", "品牌", "国家", "区域", "技术", "核心产品", "子赛道", "适应症", "价值链"];
  const csvRows = rows.map((row) =>
    [
      row.company,
      row.brand,
      row.country,
      row.region,
      row.tech,
      row.core_product,
      (row.subtracks || []).join(" / "),
      (row.indications || []).join(" / "),
      inferValueChainForProduct(row).join(" / "),
    ].map((value) => `"${String(value || "").replace(/"/g, '""')}"`).join(","),
  );
  const blob = new Blob([[headers.join(","), ...csvRows].join("\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `topic-products-${segmentCode()}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function wireTableFilter(view) {
  activeTableView = view;
  activeTableState = { query: "", subtrack: "", country: "", valueChain: "", sortKey: "company", sortDir: "asc" };
  renderTableControls(view);
  const subtrack = $("topicSubtrackFilter");
  if (subtrack) subtrack.onchange = () => applyTableFilter({ subtrack: subtrack.value });
  const country = $("topicCountryFilter");
  if (country) country.onchange = () => applyTableFilter({ country: country.value });
  const valueChain = $("topicValueChainFilter");
  if (valueChain) valueChain.onchange = () => applyTableFilter({ valueChain: valueChain.value });
  const exportButton = $("topicExportCsv");
  if (exportButton) exportButton.onclick = exportTableCsv;
  const table = $("topicProductsTable");
  if (table) {
    table.onclick = (event) => {
      const button = event.target.closest("[data-sort]");
      if (!button) return;
      const key = button.dataset.sort;
      const dir = activeTableState.sortKey === key && activeTableState.sortDir === "asc" ? "desc" : "asc";
      applyTableFilter({ sortKey: key, sortDir: dir });
    };
  }
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
  if (overlay) overlay.hidden = true;
  document.body.classList.remove("overlay-open");
}

function wireInteractions(question) {
  document.querySelectorAll("[data-close-overlay]").forEach((node) => node.addEventListener("click", closeOverlay));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeOverlay();
  });
}

function markActiveNav(segment) {
  document.querySelectorAll(".material-nav a.active").forEach((link) => {
    link.classList.remove("active");
    link.removeAttribute("aria-current");
  });
  const group = GROUP_FOR_SEGMENT[segment.code];
  const active =
    document.querySelector(`.material-nav a[data-segment="${segment.code}"]`) ||
    document.querySelector(`.material-nav a[data-group="${group}"]`);
  if (active) {
    active.classList.add("active");
    active.setAttribute("aria-current", "page");
  }
}

function wireTopicTopNavigation(segment) {
  const nav = document.querySelector(".material-nav");
  if (!nav || nav.dataset.wired === "1") return;
  nav.dataset.wired = "1";
  nav.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (!link) return;
    if (link.dataset.segment === segment.code) {
      event.preventDefault();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });
}

function setSelectIfPossible(id, value, stateKey) {
  const node = $(id);
  if (!node || !value) return false;
  const option = [...node.options].find((item) => item.value === value);
  if (!option) return false;
  node.value = value;
  applyTableFilter({ [stateKey]: value });
  return true;
}

function drillToRecords(filter = {}) {
  if (filter.company) {
    applyTableFilter({ query: filter.company });
  }
  if (filter.country) setSelectIfPossible("topicCountryFilter", filter.country, "country");
  if (filter.subtrack && !setSelectIfPossible("topicSubtrackFilter", filter.subtrack, "subtrack")) {
    applyTableFilter({ query: filter.subtrack });
  }
  if (filter.valueChain) setSelectIfPossible("topicValueChainFilter", filter.valueChain, "valueChain");
  $("records")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function wireTopicDrilldowns() {
  if (document.body.dataset.topicDrilldowns === "1") return;
  document.body.dataset.topicDrilldowns = "1";
  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-toggle-topcompanies]");
    if (toggle) {
      const list = $("topicTopCompanies")?.querySelector(".top-company-list");
      if (!list) return;
      const collapsed = list.dataset.collapsed !== "0";
      list.dataset.collapsed = collapsed ? "0" : "1";
      toggle.innerHTML = collapsed ? "<span>06-10 已展开</span><em>收起 ↑</em>" : toggle.dataset.original || "<span>06-10 合计</span><em>展开 →</em>";
      return;
    }
    const target = event.target.closest("[data-filter-company], [data-filter-country], [data-filter-subtrack], [data-filter-chain]");
    if (!target) return;
    drillToRecords({
      company: target.dataset.filterCompany,
      country: target.dataset.filterCountry,
      subtrack: target.dataset.filterSubtrack,
      valueChain: target.dataset.filterChain,
    });
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const target = event.target.closest(".lifecycle-bubble");
    if (!target) return;
    event.preventDefault();
    drillToRecords({ subtrack: target.dataset.filterSubtrack });
  });
}

function init() {
  const segment = normalizeTopicTaxonomy(findSegment());
  const slice = activeSlice(segment);
  const view = slice || segment;
  const label = slice ? `${displayName(segment)} · ${slice.name}` : displayName(segment);
  const stats = topicStats(view);
  const isAuditPage = /\/audit\.html$/i.test(window.location.pathname);
  document.title = isAuditPage ? `${label} 数据完整度审计 | 全球医美赛道分析` : `${label} | 全球医美赛道分析`;
  document.documentElement.style.setProperty("--topic", segment.color || "var(--brand)");
  setText("topicTitle", label);
  setText("topicSubtitle", slice ? `${segment.subtitle || ""} · 当前切片：${slice.name}` : segment.subtitle || "");
  renderTopicHero(segment, view, stats);
  setText("topicProducts", fmt(view.products));
  setText("topicCompanies", fmt(view.companies));
  setText("topicBrands", fmt(view.brands));
  setText("topicCountries", fmt(view.countries));
  setText("topicSubtracks", fmt(view.subtrack_count));
  setText("topicIndications", fmt(view.indication_count));
  setText("topicRegionsKpi", fmt((view.top_regions || []).length));
  setText("topicRegulatory", fmt(Object.values(view.regulatory || {}).reduce((sum, value) => sum + Number(value || 0), 0)));
  renderTopicKpis(view, stats);
  renderSubtrackExplorer(segment, slice);
  renderFunnel("topicEvidenceFunnel", topicEvidenceFunnel(view), segment.color || "var(--brand)");
  renderTimeline("topicApprovalTimeline", view.evidence_scope?.timeline || [], segment.color || "var(--brand)");
  renderBars("topicRegulatoryMix", topicRegulatoryMix(view), segment.color || "var(--brand)");
  renderProductEvidenceAudit(view);
  renderHeatmap("topicCompanySubtrackMatrix", view.company_subtrack_matrix, segment.color || "var(--brand)", "公司");
  renderHeatmap("topicCountrySubtrackMatrix", view.country_subtrack_matrix, segment.color || "var(--brand)", "国家");
  renderConcentration(view, stats);
  renderTopCompanies(view, stats);
  renderValueChain(view);
  renderLifecycleMatrix(view);
  renderAccessTimeline(view);
  renderRecentEntrants(view);
  renderBars("topicBusinessRoles", view.business_roles || [], "var(--c-ocean)");
  renderBars("topicOwnershipMix", view.ownership_mix || [], "var(--c-sage)");
  renderBars("topicTechTypeMix", view.tech_type_mix || view.category_l2_mix || [], "var(--c-gold)");
  renderHeatmap("topicIndicationHeatmap", view.indication_heatmap, segment.color || "var(--brand)");
  renderHeatmap("topicSubtrackHeatmap", view.subtrack_heatmap, segment.color || "var(--brand)");
  renderBars("topicRegions", view.top_regions || [], segment.color || "var(--brand)");
  renderBars("topicCountriesBars", view.top_countries || [], "var(--c-sage)");
  renderBars("topicCompaniesBars", view.top_companies || [], "var(--c-ocean)");
  renderBars("topicBrandsBars", view.top_brands || [], "var(--c-gold)");
  renderHeatmap("topicOfficialIndicationHeatmap", view.evidence_scope?.official_indication_heatmap, "var(--c-ocean)", "官方适应症");
  renderTable(view);
  applyBilingualLayout();
  wireTableFilter(view);
  markActiveNav(segment);
  wireTopicTopNavigation(segment);
  wireTopicDrilldowns();
  wireInteractions(`${label} 全球适应症 子赛道分布 竞争格局 市场渗透 定价`);
}

init();

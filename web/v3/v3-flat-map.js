/* =========================================================================
   v3 · 全球医美企业星图 (Flat Map · Leaflet)
   - 学 codex 原版 web/index.html line 86-122 的"全球医美企业星图"
   - 用 v3 设计 token (Aestra Soft + Mist) 重新着色：浅米底图 + petal/mist 赛道色
   - 4 个 select 筛选（赛道/区域/上市/证据）+ toggle 按产品线/企业数
   - 数据：window.GLOBAL_AESTHETICS_DATA.geo_companies
   ========================================================================= */
(function () {
  "use strict";

  const TRACK_COLORS = {
    EBD: "#8E3A3A",
    Injectables: "#6B5A75",
    Skincare: "#D9AE91",
    Regenerative: "#A8B59A",
    Implants: "#CFB58E",
    Consumables: "#5A6878",
    Diagnostics: "#C76B68",
    Surgical: "#8C7B91",
    Pharma: "#EC9B73",
    Services: "#C8B8D0",
  };

  const TRACK_LABEL_ZH = {
    EBD: "光电 EBD",
    Injectables: "注射 Injectables",
    Skincare: "功能性护肤品 Cosmeceutical",
    Regenerative: "再生 Regenerative",
    Implants: "植入物 Implants",
    Consumables: "耗材 Consumables",
    Diagnostics: "诊断 Diagnostics",
    Surgical: "外科 Surgical",
    Pharma: "药物 Pharma",
    Services: "服务 Services",
  };

  const REGION_LABEL_ZH = {
    "North America": "北美 North America",
    "Europe": "欧洲 Europe",
    "Asia Pacific": "亚太 Asia Pacific",
    "Asia-Pacific": "亚太 Asia-Pacific",
    "Latin America": "拉美 Latin America",
    "Middle East": "中东 Middle East",
    "Africa": "非洲 Africa",
    "Oceania": "大洋洲 Oceania",
    "MENA": "中东北非 MENA",
  };

  let map = null;
  let markerLayer = null;
  let metric = "products";
  const filters = { track: "all", region: "all", listing: "all", evidence: "all" };

  /* ============ helpers ============ */
  function $ (id) { return document.getElementById(id); }
  function fmt (n) { return Number(n || 0).toLocaleString("en-US"); }
  function escapeHtml (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[ch]);
  }
  function countValues (arr, field) {
    const counter = new Map();
    arr.forEach(item => {
      const k = item[field];
      if (!k) return;
      counter.set(k, (counter.get(k) || 0) + 1);
    });
    return Array.from(counter.entries()).sort((a, b) => b[1] - a[1]);
  }

  /* ============ filtering + aggregation ============ */
  function companyMatchesFilters (c) {
    if (filters.track !== "all" && (c.primary_track || "Unknown") !== filters.track) return false;
    if (filters.region !== "all" && (c.region || "Unknown") !== filters.region) return false;
    if (filters.listing === "listed" && c.ownership !== "Public") return false;
    if (filters.evidence !== "all") {
      const ev = String(c.regulatory_channels || "").toUpperCase();
      if (!ev.includes(filters.evidence)) return false;
    }
    return true;
  }

  function aggregateByCity (companies) {
    const groups = new Map();
    companies.forEach(c => {
      if (typeof c.lat !== "number" || typeof c.lon !== "number") return;
      const cityKey = c.city || c.country || "Unknown";
      const key = `${cityKey}|${c.country || ""}|${c.lat.toFixed(3)}|${c.lon.toFixed(3)}`;
      if (!groups.has(key)) {
        groups.set(key, {
          city: cityKey,
          country: c.country,
          region: c.region,
          lat: c.lat,
          lon: c.lon,
          companies: [],
          tracks: {},
          n_products: 0,
          n_listed: 0,
        });
      }
      const g = groups.get(key);
      g.companies.push(c);
      g.n_products += Number(c.products || 0);
      if (c.ownership === "Public") g.n_listed += 1;
      const t = c.primary_track || "Unknown";
      g.tracks[t] = (g.tracks[t] || 0) + 1;
    });
    return Array.from(groups.values()).map(g => {
      g.n_companies = g.companies.length;
      const sorted = Object.entries(g.tracks).sort((a, b) => b[1] - a[1]);
      g.dominant_track = sorted.length ? sorted[0][0] : "Unknown";
      g.track_breakdown = sorted;
      return g;
    });
  }

  function metricValue (city) {
    return metric === "companies" ? city.n_companies : city.n_products;
  }

  function radius (city, maxMetric) {
    const v = metricValue(city);
    const r = 3.6 + Math.sqrt(v || 1) * (metric === "companies" ? 1.45 : 0.92);
    return Math.max(5, Math.min(20, r));
  }

  /* ============ UI rendering ============ */
  function setSelectOptions (sel, allLabel, options, current, labelMap) {
    if (!sel) return;
    sel.innerHTML = "";
    const optAll = document.createElement("option");
    optAll.value = "all";
    optAll.textContent = allLabel;
    if (current === "all") optAll.selected = true;
    sel.appendChild(optAll);
    options.forEach(([key, count]) => {
      if (!key || key === "Unknown") return;
      const opt = document.createElement("option");
      opt.value = key;
      opt.textContent = `${labelMap ? labelMap(key) : key}  ·  ${count}`;
      if (key === current) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function renderFilters () {
    const data = window.GLOBAL_AESTHETICS_DATA;
    const companies = data.geo_companies || [];
    setSelectOptions(
      $("flatTrackFilter"),
      "全部赛道 · All tracks",
      countValues(companies, "primary_track"),
      filters.track,
      k => TRACK_LABEL_ZH[k] || k,
    );
    setSelectOptions(
      $("flatRegionFilter"),
      "全部区域 · All regions",
      countValues(companies, "region"),
      filters.region,
      k => REGION_LABEL_ZH[k] || k,
    );
    setSelectOptions(
      $("flatListingFilter"),
      "全部企业 · All companies",
      [["listed", companies.filter(c => c.ownership === "Public").length]],
      filters.listing,
      () => "已上市 · Listed",
    );
    setSelectOptions(
      $("flatEvidenceFilter"),
      "全部证据 · All evidence",
      [
        ["FDA", companies.filter(c => String(c.regulatory_channels || "").toUpperCase().includes("FDA")).length],
        ["CE", companies.filter(c => String(c.regulatory_channels || "").toUpperCase().includes("CE")).length],
      ],
      filters.evidence,
      k => `${k} · 已注册`,
    );
  }

  function renderLegend () {
    const node = $("flatMapLegendKeys");
    if (!node) return;
    const data = window.GLOBAL_AESTHETICS_DATA.geo_companies || [];
    const rows = countValues(data, "primary_track").filter(([t]) => t && t !== "Unknown");
    node.innerHTML = rows.map(([track, count]) => `
      <span class="track-key" style="--track-color:${TRACK_COLORS[track] || "#888"}">
        <i></i>
        <span class="nm">${escapeHtml(TRACK_LABEL_ZH[track] || track)}</span>
        <small>${count}</small>
      </span>`).join("");
    const labelEl = $("flatMapMetricLabel");
    if (labelEl) labelEl.textContent = metric === "companies" ? "企业数" : "产品线";
  }

  function tooltipHtml (city) {
    // Stacked track-composition bar from the full breakdown
    const breakdown = (city.track_breakdown || []).filter(([, n]) => n > 0);
    const total = breakdown.reduce((s, [, n]) => s + n, 0) || 1;
    const segs = breakdown.map(([name, n]) =>
      `<span class="seg" style="flex:${n};--seg-color:${escapeHtml(TRACK_COLORS[name] || "#b85957")}" title="${escapeHtml(TRACK_LABEL_ZH[name] || name)} · ${n}"></span>`
    ).join("");
    const legend = breakdown.slice(0, 3).map(([name, n]) =>
      `<span class="key" style="--seg-color:${escapeHtml(TRACK_COLORS[name] || "#b85957")}"><i></i>${escapeHtml(TRACK_LABEL_ZH[name] || name)}<b>${n}</b></span>`
    ).join("");
    const top = city.companies
      .slice()
      .sort((a, b) => (b.products || 0) - (a.products || 0))
      .slice(0, 3)
      .map(c => c.company)
      .filter(Boolean)
      .join(" · ");
    return `
      <div class="flat-tooltip" style="--tooltip-accent:${escapeHtml(TRACK_COLORS[city.dominant_track] || "#b85957")}">
        <button class="tip-close flat-tooltip-close" type="button" aria-label="关闭">×</button>
        <strong>${escapeHtml(city.city)}${city.country ? ` · ${escapeHtml(city.country)}` : ""}</strong>
        <div class="metrics"><b>${city.n_companies}</b> 企业 · <b>${city.n_products}</b> 产品线${city.n_listed ? ` · <b>${city.n_listed}</b> 上市` : ""}</div>
        <div class="ft-stack">${segs}</div>
        <div class="ft-legend">${legend}</div>
        ${top ? `<div class="ft-top">${escapeHtml(top)}</div>` : ""}
        <div class="ft-hint">点击圆点 → 查看该城市企业</div>
      </div>`;
  }

  function renderStats (filtered, cities) {
    if ($("flatMapCompanies")) $("flatMapCompanies").textContent = fmt(filtered.length);
    if ($("flatMapCities")) $("flatMapCities").textContent = fmt(cities.length);
    const countries = new Set(filtered.map(c => c.country).filter(Boolean));
    if ($("flatMapCountries")) $("flatMapCountries").textContent = fmt(countries.size);
    const products = filtered.reduce((s, c) => s + Number(c.products || 0), 0);
    if ($("flatMapProducts")) $("flatMapProducts").textContent = fmt(products);
  }

  function renderMarkers () {
    if (!map) return;
    const data = window.GLOBAL_AESTHETICS_DATA;
    const filtered = (data.geo_companies || []).filter(companyMatchesFilters);
    const cities = aggregateByCity(filtered);
    renderStats(filtered, cities);
    markerLayer.clearLayers();
    if (!cities.length) return;
    const maxMetric = Math.max(1, ...cities.map(metricValue));
    cities.forEach(city => {
      const r = radius(city, maxMetric);
      const color = TRACK_COLORS[city.dominant_track] || "#7d8793";
      const baseOpacity = 0.74 + (metricValue(city) / maxMetric) * 0.18;
      const marker = L.circleMarker([city.lat, city.lon], {
        radius: r,
        weight: 1.4,
        color: "#f7f1e6",
        fillColor: color,
        fillOpacity: Math.min(0.92, baseOpacity),
        opacity: 0.95,
        className: "flat-city-dot",
        bubblingMouseEvents: false,
      });
      marker.bindTooltip(tooltipHtml(city), {
        className: "flat-leaflet-tooltip",
        direction: "top",
        interactive: true,
        sticky: true,
        opacity: 1,
        offset: [0, -4],
      });
      marker.on("tooltipopen", (evt) => {
        const tooltipEl = evt.tooltip && evt.tooltip.getElement ? evt.tooltip.getElement() : null;
        const closeBtn = tooltipEl && tooltipEl.querySelector(".flat-tooltip-close");
        if (!closeBtn || closeBtn.dataset.wired === "1") return;
        closeBtn.dataset.wired = "1";
        closeBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          marker.closeTooltip();
        });
      });
      marker.on("mouseover", () => {
        marker.bringToFront();
        marker.setStyle({ weight: 2.4, fillOpacity: 0.96 });
      });
      marker.on("mouseout", () => marker.setStyle({ weight: 1.4, fillOpacity: Math.min(0.92, baseOpacity) }));
      marker.on("click", () => openCityDrill(city));
      marker.addTo(markerLayer);
    });
  }

  function openCityDrill (city) {
    // Prefer the shared V3DrillPanel if it exists; otherwise jump to companies.html
    if (window.V3DrillPanel && typeof window.V3DrillPanel.open === "function") {
      window.V3DrillPanel.open({
        stamp: "City · 地图下钻",
        title: `${city.city}${city.country ? " · " + city.country : ""}`,
        sub: `${city.region || ""} · 主赛道 ${TRACK_LABEL_ZH[city.dominant_track] || city.dominant_track}`,
        summary: [
          { k: "Companies", v: city.n_companies },
          { k: "Products",  v: city.n_products },
          { k: "Listed",    v: city.n_listed },
        ],
        rows: city.companies
          .slice()
          .sort((a, b) => (b.products || 0) - (a.products || 0))
          .map(c => ({
            company_id: c.company_id,
            name: c.company,
            hint: `${c.primary_track || "—"} · ${c.ownership || "—"} · ${c.products || 0} prod`,
            color: TRACK_COLORS[c.primary_track] || "#888",
          })),
      });
      return;
    }
    // Fallback: 跳转 companies 页过滤
    const ids = city.companies.map(c => c.company_id).filter(Boolean).join(",");
    if (ids) window.location.href = `./companies.html?ids=${encodeURIComponent(ids)}`;
  }

  /* ============ controls wiring ============ */
  function wireControls () {
    document.querySelectorAll("[data-flat-metric]").forEach(btn => {
      btn.addEventListener("click", () => {
        metric = btn.dataset.flatMetric || "products";
        document.querySelectorAll("[data-flat-metric]").forEach(b => b.classList.toggle("active", b === btn));
        renderLegend();
        renderMarkers();
      });
    });
    [
      ["flatTrackFilter", "track"],
      ["flatRegionFilter", "region"],
      ["flatListingFilter", "listing"],
      ["flatEvidenceFilter", "evidence"],
    ].forEach(([id, key]) => {
      const sel = $(id);
      if (!sel) return;
      sel.addEventListener("change", () => {
        filters[key] = sel.value;
        renderMarkers();
      });
    });
  }

  /* ============ init ============ */
  function init () {
    const stage = $("flatMapStage");
    if (!stage) return;
    map = L.map(stage, {
      center: [22, 12],
      zoom: 2,
      minZoom: 1.5,
      maxZoom: 9,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      worldCopyJump: false,
      maxBounds: [[-78, -180], [85, 200]],
      maxBoundsViscosity: 0.7,
      zoomControl: false,
      attributionControl: true,
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxNativeZoom: 19,
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap &copy; CARTO",
    }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    setTimeout(() => map.invalidateSize(), 80);
    renderFilters();
    renderLegend();
    renderMarkers();
    wireControls();
  }

  function ready (attempts) {
    attempts = attempts || 0;
    if (window.L && window.GLOBAL_AESTHETICS_DATA && Array.isArray(window.GLOBAL_AESTHETICS_DATA.geo_companies)) {
      init();
      return;
    }
    if (attempts > 200) {
      console.warn("[v3 flat-map] Leaflet or geo_companies missing after 20s");
      return;
    }
    setTimeout(() => ready(attempts + 1), 100);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => ready(0));
  } else {
    ready(0);
  }
})();

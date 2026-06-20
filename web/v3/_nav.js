/* Shared topbar + left rail · v3 dashboard
 * Usage:  <header id="topbar"></header>  <aside id="rail"></aside>
 *         <script src="./_nav.js" data-active="overview"></script>
 *
 * v3 changes from v2:
 *  - .rail-section-title gets the oxblood bullet via CSS ::before
 *  - .topbar nav order matches v3 IA (overview · 3 lenses · 6 deep-dives)
 *  - Active state visuals come from styles.css (.rail a.active gets lavender bg)
 */
(function () {
  const script = document.currentScript;
  const active = script && script.dataset && script.dataset.active;
  const appData = window.GLOBAL_AESTHETICS_DATA || {};
  const summary = appData.summary || {};

  function fmtCount (value, suffix) {
    if (value === null || value === undefined || value === "") return "";
    const text = typeof value === "number" ? value.toLocaleString("en-US") : String(value);
    return suffix ? `${text}${suffix}` : text;
  }

  function itemCount (item) {
    if (item.countKey && summary[item.countKey] !== undefined) {
      return fmtCount(summary[item.countKey], item.countSuffix || "");
    }
    return item.count || "";
  }

  // —— Topbar 是「产业品类」入口（不重复左 rail 的「分析视角」）——
  // 医美 9 大商业品类，中英对照
  const topNav = [
    { id: "topic-injectables",  href: "./topic.html?segment=injectables",  zh: "注射剂",        en: "Injectables" },
    { id: "topic-ebd",          href: "./topic.html?segment=ebd",          zh: "能量源设备",    en: "EBD" },
    { id: "topic-regenerative", href: "./topic.html?segment=regenerative", zh: "再生",          en: "Regen" },
    { id: "topic-implants",     href: "./topic.html?segment=implants",     zh: "植入物",        en: "Implants" },
    { id: "topic-skincare",     href: "./topic.html?segment=skincare",     zh: "功能性护肤品",  en: "Cosmeceutical" },
    { id: "topic-consumables",  href: "./topic.html?segment=consumables",  zh: "耗材",          en: "Consumables" },
    { id: "topic-diagnostics",  href: "./topic.html?segment=diagnostics",  zh: "诊断",          en: "Diagnostics" },
    { id: "topic-surgical",     href: "./topic.html?segment=surgical",     zh: "外科",          en: "Surgical" },
    { id: "topic-pharma",       href: "./topic.html?segment=pharma",       zh: "药物",          en: "Pharma" },
  ];

  const railSections = [
    {
      title: "情报视角",
      items: [
        { id: "project-overview", href: "./project-overview.html", zh: "项目总览", count: "roadmap" },
        { id: "overview",   href: "./index.html",            zh: "总览",     count: null },
        { id: "regulatory", href: "./regulatory-pulse.html", zh: "监管脉搏", countKey: "registration_evidence" },
        { id: "capital",    href: "./capital-map.html",      zh: "资本地图", count: "61" },
        { id: "market-intelligence", href: "./market-intelligence.html", zh: "商业格局", countKey: "commercial_claims" },
        { id: "cross",      href: "./cross-analysis.html",   zh: "交叉分析", count: "4 lens" },
        { id: "deep",       href: "./deep-dive.html",        zh: "深度图谱", count: "L1·L2·L3" },
        { id: "operations", href: "./operations.html",       zh: "运营视角", count: "backlog" },
      ],
    },
    {
      title: "企业与产品",
      items: [
        { id: "companies",        href: "./companies.html",         zh: "公司列表",   countKey: "company_master" },
        { id: "companies-matrix", href: "./companies-matrix.html",  zh: "企业矩阵",   count: "platform" },
        { id: "indications",      href: "./indications.html",       zh: "适应症星图", countKey: "indication_signals" },
        { id: "technology",       href: "./technology-tree.html",   zh: "技术树",     count: "267" },
        // —— 2026-06-02 evidence / evidence-queue-mdr 入口已下架：
        //     依据 audits/v4_acceptance_self_check_latest.md Overall passed:True
        //     + audits/staging_duplicate_close_20260602_latest.json + MDR/CE policy_closed
        //     页面文件保留作审计回滚 (web/v3/evidence.html · evidence-queue-mdr.html)
      ],
    },
  ];

  // —— Topbar ——
  const topbar = document.getElementById("topbar");
  if (topbar) {
    topbar.classList.add("topbar");
    topbar.innerHTML = `
      <a class="brand" href="./index.html">
        <img src="./assets/aestrat_logo.png" alt="Aestrat" class="brand-logo" />
        <span class="brand-cn">全球医美情报</span>
      </a>
      <nav aria-label="产业品类导航">
        ${topNav.map(item => `
          <a href="${item.href}" class="${item.id === active ? "active" : ""}"${item.title ? ` title="${item.title}"` : ""}>
            <span class="nav-zh">${item.zh}</span>
            <span class="nav-en">${item.en}</span>
          </a>
        `).join("")}
      </nav>
      <button class="global-search-trigger" id="global-search-trigger" type="button" aria-label="全局搜索产品、公司与证据">
        <span class="search-mark">⌕</span>
        <span>搜索</span>
      </button>
      <div class="topbar-asof" id="topbar-asof" title="数据快照时间 / Data as-of timestamp">
        <span class="asof-lbl">数据截至 · AS OF</span>
        <span class="asof-ts">—</span>
      </div>
    `;

    // Read data-as-of.json once on page load (no polling — per user spec).
    // Show only the timestamp (the products/companies counts are surfaced
    // later in the page itself; topbar shouldn't repeat them).
    const setAsOf = (value) => {
      const ts = (value || "").replace("T", " ").slice(0, 16);
      const el = document.getElementById("topbar-asof");
      if (el && ts) el.querySelector(".asof-ts").textContent = ts;
    };
    if (appData.generated_at) {
      setAsOf(appData.generated_at);
    } else {
      fetch("./data-as-of.json", { cache: "no-store" })
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setAsOf(d.as_of); })
        .catch(() => { /* silent — keep placeholder */ });
    }
    initGlobalSearch();
  }

  // —— Global search —— product / company / evidence lookup from v3-search.js
  const searchState = {
    data: null,
    loadPromise: null,
    selected: null,
    results: [],
  };

  function initGlobalSearch () {
    const trigger = document.getElementById("global-search-trigger");
    if (trigger) trigger.addEventListener("click", () => openGlobalSearch());
    document.addEventListener("keydown", (event) => {
      const key = String(event.key || "").toLowerCase();
      const target = event.target;
      const isTyping = target && /^(input|textarea|select)$/i.test(target.tagName || "");
      if ((event.ctrlKey || event.metaKey) && key === "k") {
        event.preventDefault();
        openGlobalSearch();
      } else if (!isTyping && key === "/") {
        event.preventDefault();
        openGlobalSearch();
      } else if (key === "escape") {
        closeGlobalSearch();
      }
    });
  }

  function openGlobalSearch () {
    const overlay = ensureSearchOverlay();
    overlay.hidden = false;
    document.body.classList.add("global-search-open");
    const input = overlay.querySelector("#global-search-input");
    const meta = overlay.querySelector("#global-search-meta");
    const detail = overlay.querySelector("#global-search-detail");
    if (meta) meta.textContent = "搜索索引加载中";
    if (detail) detail.innerHTML = "";
    ensureSearchData()
      .then(data => {
        prepareSearchData(data);
        renderSearchResults((input && input.value) || "");
        if (input) input.focus();
      })
      .catch(() => {
        if (meta) meta.textContent = "搜索索引加载失败";
      });
  }

  function closeGlobalSearch () {
    const overlay = document.getElementById("global-search-overlay");
    if (overlay) overlay.hidden = true;
    document.body.classList.remove("global-search-open");
  }

  function ensureSearchData () {
    if (window.V3_SEARCH_DATA) {
      searchState.data = window.V3_SEARCH_DATA;
      return Promise.resolve(window.V3_SEARCH_DATA);
    }
    if (searchState.loadPromise) return searchState.loadPromise;
    searchState.loadPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `./v3-search.js?v=${Date.now()}`;
      script.async = true;
      script.onload = () => {
        if (window.V3_SEARCH_DATA) {
          searchState.data = window.V3_SEARCH_DATA;
          resolve(window.V3_SEARCH_DATA);
        } else {
          reject(new Error("v3 search data missing"));
        }
      };
      script.onerror = reject;
      document.head.appendChild(script);
    });
    return searchState.loadPromise;
  }

  function ensureSearchOverlay () {
    let overlay = document.getElementById("global-search-overlay");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.id = "global-search-overlay";
    overlay.className = "global-search-overlay";
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="global-search-backdrop" data-search-close></div>
      <section class="global-search-panel" role="dialog" aria-modal="true" aria-labelledby="global-search-title">
        <div class="global-search-head">
          <div>
            <div class="global-search-kicker">Global Search</div>
            <h2 id="global-search-title">产品与企业检索</h2>
          </div>
          <button type="button" class="global-search-close" data-search-close aria-label="关闭搜索">×</button>
        </div>
        <label class="global-search-input-wrap">
          <span class="search-mark">⌕</span>
          <input id="global-search-input" type="search" autocomplete="off" placeholder="Revolax / Across / HA filler / FDA..." />
        </label>
        <div class="global-search-meta" id="global-search-meta"></div>
        <div class="global-search-body">
          <div class="global-search-results" id="global-search-results" role="list"></div>
          <aside class="global-search-detail" id="global-search-detail"></aside>
        </div>
      </section>
    `;
    document.body.appendChild(overlay);
    overlay.querySelectorAll("[data-search-close]").forEach(el => {
      el.addEventListener("click", closeGlobalSearch);
    });
    const input = overlay.querySelector("#global-search-input");
    if (input) {
      input.addEventListener("input", () => renderSearchResults(input.value || ""));
    }
    return overlay;
  }

  function prepareSearchData (data) {
    if (!data || data._prepared) return;
    const items = Array.isArray(data.items) ? data.items : [];
    items.forEach((item, index) => {
      item._index = index;
      item._titleNorm = normalizeSearchText(item.title);
      item._searchNorm = normalizeSearchText([
        item.title,
        item.brand,
        item.product_name,
        item.registered_name,
        item.company,
        item.country,
        item.track,
        item.subtrack,
        item.material_path,
        item.technology,
        item.legal_manufacturer,
        item.brand_owner,
        item.marketing_holder,
        item.distributor,
        item.relationship_type,
        item.search_text,
      ].filter(Boolean).join(" | "));
      item._tokens = Array.from(new Set(item._searchNorm.split(/[^a-z0-9\u4e00-\u9fff]+/).filter(Boolean)));
    });
    data._prepared = true;
  }

  function renderSearchResults (query) {
    const data = searchState.data || window.V3_SEARCH_DATA || {};
    const items = Array.isArray(data.items) ? data.items : [];
    const q = normalizeSearchText(query);
    const resultsEl = document.getElementById("global-search-results");
    const metaEl = document.getElementById("global-search-meta");
    const detailEl = document.getElementById("global-search-detail");
    if (!resultsEl || !metaEl || !detailEl) return;

    if (!q) {
      const counts = data.counts || {};
      metaEl.textContent = [
        fmtCount(counts.products || 0, " 产品"),
        fmtCount(counts.families || 0, " 产品族"),
        fmtCount(counts.companies || 0, " 企业"),
      ].join(" · ");
      resultsEl.innerHTML = "";
      detailEl.innerHTML = `<div class="global-search-empty">输入关键词后显示匹配结果</div>`;
      searchState.results = [];
      searchState.selected = null;
      return;
    }

    const scored = items
      .map(item => ({ item, ...scoreSearchItem(item, q) }))
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score || typeWeight(b.item.type) - typeWeight(a.item.type))
      .slice(0, 18);
    const directCount = scored.filter(row => row.direct).length;
    searchState.results = scored.map(row => row.item);
    searchState.selected = scored[0] ? scored[0].item : null;

    if (!scored.length) {
      metaEl.textContent = `0 results · ${query}`;
      resultsEl.innerHTML = `<div class="global-search-empty">当前索引没有匹配项</div>`;
      detailEl.innerHTML = `<div class="global-search-empty">未见产品、企业或证据命中</div>`;
      return;
    }

    metaEl.textContent = directCount
      ? `${directCount} 个精确/直接命中 · ${scored.length} 个结果`
      : `未找到精确命中 · 显示 ${scored.length} 个近似结果`;
    resultsEl.innerHTML = scored.map((row, idx) => renderSearchCard(row.item, idx, idx === 0, row.direct)).join("");
    resultsEl.querySelectorAll("[data-search-result]").forEach(el => {
      el.addEventListener("click", () => {
        const index = Number(el.getAttribute("data-result-index"));
        searchState.selected = searchState.results[index];
        resultsEl.querySelectorAll("[data-search-result]").forEach(node => node.classList.remove("selected"));
        el.classList.add("selected");
        renderSearchDetail(searchState.selected);
      });
    });
    renderSearchDetail(searchState.selected);
  }

  function renderSearchCard (item, index, selected, direct) {
    const evidence = item.evidence || {};
    const typeLabel = typeName(item.type);
    const evidenceLabel = evidenceLabelFor(item);
    const subtitle = [item.company, item.country, item.track, item.subtrack].filter(Boolean).join(" · ");
    return `
      <button type="button" class="global-search-card ${selected ? "selected" : ""}" data-search-result data-result-index="${index}" role="listitem">
        <span class="search-card-topline">
          <span class="search-type">${esc(typeLabel)}</span>
          <span class="search-evidence ${esc(evidence.level || "seed")}">${esc(evidenceLabel || "")}</span>
          ${direct ? `<span class="search-direct">命中</span>` : ""}
        </span>
        <strong>${esc(item.title || "Unnamed")}</strong>
        <span>${esc(subtitle || item.product_name || item.material_path || "")}</span>
      </button>
    `;
  }

  function renderSearchDetail (item) {
    const detailEl = document.getElementById("global-search-detail");
    if (!detailEl) return;
    if (!item) {
      detailEl.innerHTML = `<div class="global-search-empty">选择一个结果查看证据</div>`;
      return;
    }
    const evidence = item.evidence || {};
    const evidenceLabel = evidenceLabelFor(item);
    const rows = [
      ["公司", item.company],
      ["国家/地区", [item.country, item.region].filter(Boolean).join(" · ")],
      ["集团/母公司", item.parent_company],
      ["赛道", [item.track, item.subtrack].filter(Boolean).join(" · ")],
      ["产品名", item.product_name],
      ["注册名", item.registered_name],
      ["法定制造商", item.legal_manufacturer || item.manufactured_by],
      ["品牌权属", item.brand_owner],
      ["上市/持证主体", item.marketing_holder || item.local_holder],
      ["经销/代理", item.distributor],
      ["关系类型", item.relationship_type],
      ["材料/技术", item.material_path || item.technology],
      ["核验状态", item.verification_status],
      ["审阅状态", item.review_status],
    ].filter(([, value]) => value);
    const evidenceRows = Array.isArray(evidence.samples) ? evidence.samples : [];
    detailEl.innerHTML = `
      <div class="search-detail-kicker">${esc(typeName(item.type))}</div>
      <h3>${esc(item.title || "Unnamed")}</h3>
      <div class="search-detail-sub">${esc([item.company, item.country].filter(Boolean).join(" · "))}</div>
      <div class="search-verdict ${esc(evidence.level || "seed")}">
        <strong>${esc(evidenceLabel || "证据状态")}</strong>
        <span>${esc(evidence.note || "")}</span>
      </div>
      <dl class="search-detail-fields">
        ${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}
      </dl>
      ${item.claim_text ? `<p class="search-claim">${esc(item.claim_text)}</p>` : ""}
      ${renderEvidenceSamples(evidenceRows, evidence)}
    `;
  }

  function renderEvidenceSamples (samples, evidence) {
    if (!samples.length) {
      return `<div class="search-evidence-list empty">当前结果未连接注册证据样本</div>`;
    }
    return `
      <div class="search-evidence-list">
        <div class="search-evidence-head">
          <span>注册/官方证据</span>
          <small>${fmtCount(evidence.registration_count || samples.length, " 条")}</small>
        </div>
        ${samples.map(sample => `
          <article>
            <div class="evidence-line">
              <strong>${esc([sample.jurisdiction, sample.regulator].filter(Boolean).join(" · ") || sample.source_type || "Evidence")}</strong>
              ${sample.registration_no ? `<span>${esc(sample.registration_no)}</span>` : ""}
            </div>
            <p>${esc(sample.status || sample.evidence_title || "")}</p>
            <div class="evidence-meta">
              <span>${esc(sample.review_status || sample.confidence || "")}</span>
              ${sample.source_url ? `<a href="${escAttr(sample.source_url)}" target="_blank" rel="noopener">source</a>` : ""}
            </div>
          </article>
        `).join("")}
      </div>
    `;
  }

  function scoreSearchItem (item, q) {
    const text = item._searchNorm || "";
    const title = item._titleNorm || "";
    const tokens = item._tokens || [];
    let score = 0;
    let direct = false;
    if (title === q) {
      score += 140;
      direct = true;
    } else if (title.startsWith(q)) {
      score += 115;
      direct = true;
    } else if (title.includes(q)) {
      score += 100;
      direct = true;
    }
    if (text.includes(q)) {
      score += direct ? 20 : 80;
      direct = true;
    }
    if (!direct && q.length >= 4) {
      score += fuzzySearchScore(q, tokens);
    }
    if (score > 0) {
      score += typeWeight(item.type);
      const level = (item.evidence && item.evidence.level) || "";
      if (level === "strong") score += 6;
      if (level === "source") score += 3;
    }
    return { score, direct };
  }

  function fuzzySearchScore (q, tokens) {
    let best = 0;
    tokens.forEach(token => {
      if (!token || token.length < 4) return;
      let score = 0;
      if (token.startsWith(q.slice(0, Math.min(q.length, 5)))) {
        score = Math.max(score, 34 - Math.abs(token.length - q.length));
      }
      const prefix = commonPrefix(q, token);
      if (prefix >= 4) score = Math.max(score, 18 + prefix * 2);
      const overlap = ngramOverlap(q, token, 4);
      if (overlap >= 2 && prefix >= 3) score = Math.max(score, 12 + overlap * 4);
      if (best < score) best = score;
    });
    return best;
  }

  function commonPrefix (a, b) {
    let i = 0;
    const max = Math.min(a.length, b.length);
    while (i < max && a[i] === b[i]) i += 1;
    return i;
  }

  function ngramOverlap (a, b, size) {
    if (a.length < size || b.length < size) return 0;
    const grams = new Set();
    for (let i = 0; i <= a.length - size; i += 1) grams.add(a.slice(i, i + size));
    let overlap = 0;
    for (let i = 0; i <= b.length - size; i += 1) {
      if (grams.has(b.slice(i, i + size))) overlap += 1;
    }
    return overlap;
  }

  function normalizeSearchText (value) {
    return String(value || "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function typeName (type) {
    return { product: "产品", family: "产品族", company: "企业" }[type] || "结果";
  }

  function typeWeight (type) {
    return { product: 12, family: 8, company: 5 }[type] || 0;
  }

  function evidenceLabelFor (item) {
    const evidence = item.evidence || {};
    const label = evidence.label || "";
    if (item.type === "family" && label === "产品族") return "系列定位";
    if (item.type === "company" && label === "企业主数据") return "主数据";
    return label;
  }

  function esc (value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[ch]);
  }

  function escAttr (value) {
    return esc(value).replace(/`/g, "&#96;");
  }

  // —— Global animations (scoped here so EVERY page gets them — without this,
  //    older pages without their own IntersectionObserver stay at opacity:0
  //    forever because the global CSS hides .block / .page-hero / .kpi-cell
  //    until they receive the .in-view class.)
  function runGlobalAnimations () {
    // a) Stagger fade-in via IntersectionObserver
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.05, rootMargin: "0px 0px -40px 0px" });
      document.querySelectorAll(
        ".block, .page-hero, .kpi-cell, .editorial-block, .l1-card"
      ).forEach(el => observer.observe(el));
    } else {
      // Fallback for ancient browsers — just show everything
      document.querySelectorAll(
        ".block, .page-hero, .kpi-cell, .editorial-block, .l1-card"
      ).forEach(el => el.classList.add("in-view"));
    }

    // b) Auto-detect: any .num element without explicit data-count-up that's
    //    a pure numeric → add the attribute so count-up animates uniformly
    //    across every page (covers hardcoded numbers in stat-rows, KPI deltas,
    //    findings, etc.)
    document.querySelectorAll(".num, .value, [data-bind]").forEach(el => {
      if (el.hasAttribute("data-count-up")) return;
      const raw = (el.textContent || "").trim();
      // Pure integer (with optional comma separators) — e.g. "977", "1,182"
      if (/^\d{1,3}(,\d{3})+$/.test(raw) || /^\d+$/.test(raw)) {
        el.setAttribute("data-count-up", raw.replace(/,/g, ""));
      }
    });

    // c) Count-up on any element with data-count-up (idempotent — pages that
    //    already wire their own count-up will set the same final text twice,
    //    which is fine)
    document.querySelectorAll("[data-count-up]").forEach(el => {
      if (el.dataset.cuStarted) return;     // already animated
      el.dataset.cuStarted = "1";
      const tgt = Number(el.getAttribute("data-count-up"));
      if (!Number.isFinite(tgt)) return;
      const duration = 1100;
      const startTime = performance.now();
      function frame (now) {
        const p = Math.min(1, (now - startTime) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const v = Math.round(tgt * eased);
        el.textContent = v.toLocaleString("en-US");
        if (p < 1) requestAnimationFrame(frame);
        else el.textContent = tgt.toLocaleString("en-US");
      }
      requestAnimationFrame(frame);
    });
  }

  // Run after the rail/topbar render so observed elements exist
  requestAnimationFrame(runGlobalAnimations);

  // —— Left rail ——
  const rail = document.getElementById("rail");
  if (rail) {
    rail.classList.add("rail");
    rail.innerHTML = railSections.map(sec => `
      <div class="rail-section">
        <div class="rail-section-title">${sec.title}</div>
        ${sec.items
          .map(item => `
          <a href="${item.href}" class="${item.id === active ? "active" : ""}">
            <span>${item.zh}</span>
            ${itemCount(item) ? `<small>${itemCount(item)}</small>` : ""}
          </a>
        `).join("")}
      </div>
    `).join("");
  }

  const copyReplacements = [
    ["待补具体适应症", "未明确适应症"],
  ];

  function normalizeDisplayText (root) {
    if (!root) return;
    const clean = (value) => {
      let txt = value || "";
      copyReplacements.forEach(([from, to]) => {
        txt = txt.split(from).join(to);
      });
      return txt;
    };
    const visitElement = (el) => {
      ["title", "aria-label"].forEach(attr => {
        const value = el.getAttribute && el.getAttribute(attr);
        if (!value) return;
        const next = clean(value);
        if (next !== value) el.setAttribute(attr, next);
      });
    };
    const visitText = (node) => {
      const txt = clean(node.nodeValue || "");
      if (txt !== node.nodeValue) node.nodeValue = txt;
    };

    if (root.nodeType === Node.TEXT_NODE) {
      visitText(root);
      return;
    }

    if (root.nodeType !== Node.ELEMENT_NODE && root !== document.body) return;
    if (root.nodeType === Node.ELEMENT_NODE) visitElement(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      visitText(node);
      node = walker.nextNode();
    }
    if (root.querySelectorAll) root.querySelectorAll("[title], [aria-label]").forEach(visitElement);
  }

  function startCopyNormalizer () {
    normalizeDisplayText(document.body);
    const observer = new MutationObserver(records => {
      records.forEach(record => {
        if (record.type === "characterData") normalizeDisplayText(record.target);
        record.addedNodes.forEach(node => normalizeDisplayText(node));
      });
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  if (document.body) requestAnimationFrame(startCopyNormalizer);
})();

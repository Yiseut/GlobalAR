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

  // —— Topbar 是「产业品类」入口（不重复左 rail 的「分析视角」）——
  // 医美 8 大商业品类，中英对照
  const topNav = [
    { id: "topic-injectables",  href: "./topic.html?segment=injectables",  zh: "注射剂",        en: "Injectables" },
    { id: "topic-ebd",          href: "./topic.html?segment=ebd",          zh: "能量源设备",    en: "EBD" },
    { id: "topic-regenerative", href: "./topic.html?segment=regenerative", zh: "再生",          en: "Regen" },
    { id: "topic-implants",     href: "./topic.html?segment=implants",     zh: "植入物",        en: "Implants" },
    { id: "topic-skincare",     href: "./topic.html?segment=skincare",     zh: "功能性护肤品",  en: "Cosmeceutical" },
    { id: "topic-consumables",  href: "./topic.html?segment=consumables",  zh: "耗材",          en: "Consumables" },
    { id: "topic-diagnostics",  href: "./topic.html?segment=diagnostics",  zh: "诊断",          en: "Diagnostics" },
    { id: "topic-surgical",     href: "./topic.html?segment=surgical",     zh: "外科",          en: "Surgical" },
  ];

  const railSections = [
    {
      title: "情报视角",
      items: [
        { id: "overview",   href: "./index.html",            zh: "总览",     count: null },
        { id: "regulatory", href: "./regulatory-pulse.html", zh: "监管脉搏", count: "567" },
        { id: "geo",        href: "./geo-deep-dive.html",    zh: "地域深掘", count: "38 国" },
        { id: "capital",    href: "./capital-map.html",      zh: "资本地图", count: "61" },
        { id: "tracks",     href: "./tracks.html",           zh: "赛道结构", count: "10 L1" },
        { id: "cross",      href: "./cross-analysis.html",   zh: "交叉分析", count: "4 lens" },
        { id: "deep",       href: "./deep-dive.html",        zh: "深度下钻", count: "L1·L2·L3" },
      ],
    },
    {
      title: "企业与产品",
      items: [
        { id: "companies",        href: "./companies.html",         zh: "公司列表",   count: "362" },
        { id: "companies-matrix", href: "./companies-matrix.html",  zh: "企业矩阵",   count: "platform" },
        { id: "indications",      href: "./indications.html",       zh: "适应症星图", count: "1,236" },
        { id: "technology",       href: "./technology-tree.html",   zh: "技术树",     count: "286" },
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
      <div class="topbar-asof" id="topbar-asof" title="数据快照时间 / Data as-of timestamp">
        <span class="asof-lbl">数据截至 · AS OF</span>
        <span class="asof-ts">—</span>
      </div>
    `;

    // Read data-as-of.json once on page load (no polling — per user spec).
    // Show only the timestamp (the products/companies counts are surfaced
    // later in the page itself; topbar shouldn't repeat them).
    fetch("./data-as-of.json", { cache: "no-store" })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return;
        const ts = (d.as_of || "").replace("T", " ").slice(0, 16);
        const el = document.getElementById("topbar-asof");
        if (el) el.querySelector(".asof-ts").textContent = ts;
      })
      .catch(() => { /* silent — keep placeholder */ });
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
            ${item.count ? `<small>${item.count}</small>` : ""}
          </a>
        `).join("")}
      </div>
    `).join("");
  }
})();

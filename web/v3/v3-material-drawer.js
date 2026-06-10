/* v3 Material drawer · L1 → L2 (+L3 pills) drill for index.html landscape.
 *
 * Click an L1 card on the overview landscape → opens a side drawer showing
 * every L2 sub-track inside that L1, each with (products / companies /
 * countries) KPIs and a row of L3 pills with counts.
 *
 * Pattern reuses .v3-l2-drawer styles for Aestra-Soft visual consistency
 * across all v3 drawers (L2 / Indication / Cell / now Material).
 *
 * Usage: V3MaterialDrawer.show({ l1: "注射类" });
 * Data source: window.V3_MATERIAL_LANDSCAPE.l1_cards[].
 */
(function () {
  if (window.V3MaterialDrawer && window.V3MaterialDrawer.__installed) return;

  const TRACK_COLORS = {
    EBD: "#8E3A3A", Injectables: "#6B5A75", Skincare: "#D9AE91",
    Regenerative: "#A8B59A", Consumables: "#5A6878", Implants: "#CFB58E",
    Diagnostics: "#C76B68", Surgical: "#8C7B91", Pharma: "#EC9B73", Services: "#C8B8D0",
  };
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
  })[ch]);

  let backdropEl = null;
  let drawerEl = null;
  let lastFocus = null;

  function ensureDom () {
    if (backdropEl) return;
    backdropEl = document.createElement("div");
    backdropEl.className = "v3-l2-backdrop";
    backdropEl.addEventListener("click", close);
    drawerEl = document.createElement("aside");
    drawerEl.className = "v3-l2-drawer v3-material-drawer";
    drawerEl.setAttribute("role", "dialog");
    drawerEl.setAttribute("aria-modal", "true");
    drawerEl.setAttribute("aria-label", "材料赛道详情");
    drawerEl.addEventListener("click", e => e.stopPropagation());
    document.body.appendChild(backdropEl);
    document.body.appendChild(drawerEl);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawerEl.classList.contains("show")) close();
    });
  }

  function renderL2Panel (l2, accent) {
    const l3Html = (l2.l3_list || []).map(x =>
      `<span class="mt-l3-pill" title="${esc(x.name)} · ${x.n_products} 款">
         <span class="mt-l3-name">${esc(x.name)}</span>
         <span class="mt-l3-n">${x.n_products}</span>
       </span>`
    ).join("");
    return `
      <article class="mt-l2-panel" style="--accent:${accent};">
        <header class="mt-l2-head">
          <h4 class="mt-l2-name">${esc(l2.name)}</h4>
          <span class="mt-l2-share">${l2.share_pct.toFixed(1)}%</span>
        </header>
        <div class="mt-l2-kpis">
          <div class="kpi"><span class="v">${l2.n_products}</span><span class="k">产品线</span></div>
          <div class="kpi"><span class="v">${l2.n_companies}</span><span class="k">企业</span></div>
          <div class="kpi"><span class="v">${l2.n_countries}</span><span class="k">国家</span></div>
        </div>
        ${l3Html ? `<div class="mt-l3-pills">${l3Html}</div>` : ""}
      </article>
    `;
  }

  function renderL2Detail (l1, l2, accent) {
    // L3 breakdown — bar-style intensity
    const maxL3 = Math.max(1, ...(l2.l3_list || []).map(x => x.n_products));
    const l3Bars = (l2.l3_list || []).map(x => {
      const pct = (x.n_products / maxL3 * 100).toFixed(1);
      return `
        <div class="mtd-l3-row">
          <span class="mtd-l3-name">${esc(x.name)}</span>
          <span class="mtd-l3-bar"><span class="mtd-l3-fill" style="width:${pct}%; --accent:${accent};"></span></span>
          <span class="mtd-l3-n">${x.n_products}</span>
        </div>
      `;
    }).join("") || `<div class="mtd-empty">无 L3 细分数据</div>`;

    const coList = (l2.companies || []).map(co => `
      <button class="mtd-co" type="button" data-company-id="${esc(co.company_id)}"
              title="打开 ${esc(co.name)} 完整产品库 ↗">
        <span class="mtd-co-name">${esc(co.name)}</span>
        ${co.country ? `<span class="mtd-co-country">${esc(co.country)}</span>` : ""}
        <span class="mtd-co-n">${co.n_products}</span>
      </button>
    `).join("");
    const coTail = l2.more_companies
      ? `<span class="mtd-co-more">+${l2.more_companies} 家未列示</span>` : "";

    const prodList = (l2.products || []).map(p => `
      <li class="mtd-prod">
        <button type="button" class="mtd-prod-name" data-company-id="${esc(p.company_id)}"
                title="打开 ${esc(p.company)} 完整产品库 ↗">
          ${esc(p.name)}
          <span class="mtd-prod-arrow" aria-hidden="true">↗</span>
        </button>
        <div class="mtd-prod-meta">
          ${p.brand ? `<span class="mtd-prod-chip">${esc(p.brand)}</span>` : ""}
          ${p.l3 ? `<span class="mtd-prod-chip">${esc(p.l3)}</span>` : ""}
          <span class="mtd-prod-co">${esc(p.company)}</span>
        </div>
        ${p.registered_name ? `<div class="mtd-prod-reg">REGISTERED  ${esc(p.registered_name)}</div>` : ""}
      </li>
    `).join("");

    return `
      <div class="v3-l2-head" style="--track-accent:${accent};">
        <button class="v3-l2-close" type="button" aria-label="关闭">×</button>
        <span class="v3-l2-stamp" style="color:${accent};border-color:${accent}66;">材料 L2 · drill-down</span>
        <h2 class="v3-l2-title">
          <span class="l1" style="color:var(--muted); font-size:14px;">${esc(l1)}</span>
          <span class="sep">/</span>
          <span class="l2" style="color:${accent};">${esc(l2.name)}</span>
        </h2>
        <div class="v3-l2-sub">
          ${l2.n_products} 条产品线 · ${l2.n_companies} 家企业 · ${l2.n_countries} 个国家 · 占 L1 ${l2.share_pct.toFixed(1)}%
        </div>
      </div>
      <div class="v3-l2-body mtd-body">
        <section class="mtd-section">
          <h3 class="mtd-sec-title">L3 细分 <span class="mtd-sec-sub">${(l2.l3_list || []).length} 个</span></h3>
          <div class="mtd-l3-list">${l3Bars}</div>
        </section>
        <section class="mtd-section">
          <h3 class="mtd-sec-title">企业 <span class="mtd-sec-sub">${l2.n_companies} 家 · 按产品数 desc</span></h3>
          <div class="mtd-co-list">${coList}${coTail}</div>
        </section>
        <section class="mtd-section">
          <h3 class="mtd-sec-title">产品线 <span class="mtd-sec-sub">${l2.n_products} 款</span></h3>
          <ul class="mtd-prod-list">${prodList}</ul>
        </section>
      </div>
    `;
  }

  function show (cfg) {
    if (!window.V3_MATERIAL_LANDSCAPE) {
      console.warn("V3_MATERIAL_LANDSCAPE not loaded");
      return;
    }
    const l1 = cfg.l1;
    const l2Name = cfg.l2;
    const card = window.V3_MATERIAL_LANDSCAPE.l1_cards.find(c => c.name === l1);
    if (!card) { console.warn(`L1 not found: ${l1}`); return; }

    ensureDom();
    lastFocus = document.activeElement;
    const accent = TRACK_COLORS[card.dom_commercial_l1] || "var(--accent-2)";

    if (l2Name) {
      // ── L2 mode: detailed L2 view (L3 breakdown + companies + products) ──
      const l2 = card.l2_list.find(x => x.name === l2Name);
      if (!l2) { console.warn(`L2 not found: ${l1} / ${l2Name}`); return; }
      drawerEl.innerHTML = renderL2Detail(l1, l2, accent);
    } else {
      // ── L1 mode: existing L2 panel grid view ──
      drawerEl.innerHTML = `
        <div class="v3-l2-head" style="--track-accent:${accent};">
          <button class="v3-l2-close" type="button" aria-label="关闭">×</button>
          <span class="v3-l2-stamp" style="color:${accent};border-color:${accent}66;">材料 L1 · drill-down</span>
          <h2 class="v3-l2-title">
            <span class="l1" style="color:${accent};">${esc(card.name)}</span>
          </h2>
          <div class="v3-l2-sub">
            ${card.n_products} 条产品线 ·
            ${card.l2_count} 个二级类目 ·
            ${card.n_companies} 家企业 ·
            ${card.n_countries} 个国家/地区
          </div>
        </div>
        <div class="v3-l2-body mt-l2-body">
          ${card.l2_list.map(l2 => renderL2Panel(l2, accent)).join("")}
        </div>
      `;
      // Make L2 panels clickable too — drill to L2 detail
      setTimeout(() => {
        drawerEl.querySelectorAll(".mt-l2-panel").forEach((panel, i) => {
          panel.style.cursor = "pointer";
          panel.addEventListener("click", () => {
            show({ l1, l2: card.l2_list[i].name });
          });
        });
      }, 0);
    }

    drawerEl.querySelector(".v3-l2-close").addEventListener("click", close);

    // Wire company-name buttons → V3CompanyDetail
    drawerEl.querySelectorAll("[data-company-id]").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const cid = btn.getAttribute("data-company-id");
        if (cid && window.V3CompanyDetail) {
          close();
          setTimeout(() => window.V3CompanyDetail.show(cid, { source: "material-drawer" }), 50);
        }
      });
    });

    requestAnimationFrame(() => {
      backdropEl.classList.add("show");
      drawerEl.classList.add("show");
      drawerEl.scrollTop = 0;
      const closer = drawerEl.querySelector(".v3-l2-close");
      if (closer) closer.focus();
    });
    document.documentElement.style.overflow = "hidden";
  }

  function close () {
    if (!drawerEl) return;
    backdropEl.classList.remove("show");
    drawerEl.classList.remove("show");
    document.documentElement.style.overflow = "";
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) {} }
  }

  window.V3MaterialDrawer = { show, close, __installed: true };
})();

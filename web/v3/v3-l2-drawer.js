/* v3 L2 drawer · in-place drill-down for L2 cards on topic.html
 *
 * Opens an overlay listing the companies in a given L1 × L2 cell, with each
 * company's brands → products → registration evidence. Click a company name
 * in the drawer to escalate into the single-company V3CompanyDetail drawer.
 *
 * Usage:
 *   window.V3L2Drawer.show({ l1: "Implants", l2: "Tissue Matrix" });
 *   window.V3L2Drawer.close();
 *
 * Data source: window.V3_L2_DETAIL (built by scripts/_v3_build_l2_detail.py).
 * Returns silently if data not loaded.
 */
(function () {
  if (window.V3L2Drawer && window.V3L2Drawer.__installed) return;

  const TRACK_COLORS = {
    EBD: "#8E3A3A",
    Injectables: "#6B5A75",
    Skincare: "#D9AE91",
    Regenerative: "#A8B59A",
    Consumables: "#5A6878",
    Implants: "#CFB58E",
    Diagnostics: "#C76B68",
    Surgical: "#8C7B91",
    Pharma: "#EC9B73",
    Services: "#C8B8D0",
  };

  let backdropEl = null;
  let drawerEl = null;
  let lastFocus = null;

  function esc (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({
      "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
    })[ch]);
  }

  function ensureDom () {
    if (backdropEl) return;
    backdropEl = document.createElement("div");
    backdropEl.className = "v3-l2-backdrop";
    backdropEl.addEventListener("click", close);

    drawerEl = document.createElement("aside");
    drawerEl.className = "v3-l2-drawer";
    drawerEl.setAttribute("role", "dialog");
    drawerEl.setAttribute("aria-modal", "true");
    drawerEl.setAttribute("aria-label", "L2 子赛道详情");
    drawerEl.addEventListener("click", e => e.stopPropagation());

    document.body.appendChild(backdropEl);
    document.body.appendChild(drawerEl);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawerEl.classList.contains("show")) close();
    });
  }

  function renderRegRow (r) {
    const reg = r.regulator || r.jurisdiction || "—";
    return `
      <li class="v3-l2-reg">
        <span class="r-regulator" data-reg="${esc(reg)}">${esc(reg)}</span>
        ${r.number ? `<span class="r-no">${esc(r.number)}</span>` : ""}
        ${r.date ? `<span class="r-date">${esc(r.date)}</span>` : ""}
        ${r.pathway ? `<span class="r-pw">${esc(r.pathway)}</span>` : ""}
        ${r.status ? `<span class="r-status">${esc(r.status)}</span>` : ""}
      </li>
    `;
  }

  function renderProduct (p) {
    const flagHtml = p.flag === "tier1"
      ? `<span class="flag-chip" title="经检索 FDA / EU / NMPA 未找到 registered_name，可定期复查">?</span>`
      : p.flag === "tier2"
        ? `<span class="flag-dot" title="经核公开渠道无适应症（外文 2A/2B 常态）"></span>`
        : "";

    const regs = p.registrations || [];
    const hasRegs = regs.length > 0;
    const showRegName = p.registered_name && p.registered_name !== p.name;
    const lcName = (p.name || "").toLowerCase();
    const showTech = p.tech_l2 && !lcName.includes((p.tech_l2 || "").toLowerCase().slice(0, 12));
    const showMat = p.material && p.material !== p.tech_l2
      && !lcName.includes((p.material || "").toLowerCase().slice(0, 12));

    // Collapsed default: ONE-LINE credentials = first reg chip + cert# + date.
    // Anything else (more regs, registered name, tech/mat chips, pathway/status)
    // moves into the expanded body and is shown only after the user clicks.
    const first = regs[0];
    const collapsedReg = first ? `
      <ul class="v3-l2-regs collapsed">
        ${renderRegRow(first)}
      </ul>
    ` : `<div class="v3-l2-noreg">— 暂无注册证据 —</div>`;

    const moreRegs = regs.length > 1
      ? `<span class="prod-more-pill">+${regs.length - 1} 证</span>` : "";
    const hasExtras = (regs.length > 1) || showRegName || showTech || showMat
      || (first && (first.pathway || first.status));
    const chevron = hasExtras
      ? `<span class="prod-chevron" aria-hidden="true">▾</span>` : "";

    const expandedBody = hasExtras ? `
      <div class="prod-expand">
        ${(showTech || showMat) ? `
          <div class="prod-chips">
            ${showTech ? `<span class="prod-meta">${esc(p.tech_l2)}</span>` : ""}
            ${showMat ? `<span class="prod-meta">${esc(p.material)}</span>` : ""}
          </div>` : ""}
        ${showRegName ? `<div class="prod-regname">${esc(p.registered_name)}</div>` : ""}
        ${regs.length > 1 ? `
          <ul class="v3-l2-regs full">
            ${regs.slice(1).map(renderRegRow).join("")}
          </ul>` : ""}
      </div>
    ` : "";

    return `
      <li class="v3-l2-prod${hasExtras ? " is-expandable" : ""}" data-flag="${p.flag || ""}">
        <div class="prod-head">
          <span class="prod-name">${esc(p.name)}</span>${flagHtml}
          ${moreRegs}
          ${chevron}
        </div>
        ${collapsedReg}
        ${expandedBody}
      </li>
    `;
  }

  // Click handler is wired after the drawer's HTML is inserted (see `show`).
  function wireExpand (root) {
    root.querySelectorAll(".v3-l2-prod.is-expandable").forEach(li => {
      const head = li.querySelector(".prod-head");
      head.addEventListener("click", () => {
        li.classList.toggle("expanded");
      });
      head.style.cursor = "pointer";
    });
  }

  function renderBrand (b) {
    return `
      <div class="v3-l2-brand">
        <div class="brand-head">
          <span class="brand-name">${esc(b.brand)}</span>
          ${b.brand_role ? `<span class="brand-role">${esc(b.brand_role)}</span>` : ""}
          <span class="brand-count">${b.products.length} 产品</span>
        </div>
        <ul class="v3-l2-prods">
          ${b.products.map(renderProduct).join("")}
        </ul>
      </div>
    `;
  }

  function renderCompany (c, accent) {
    const totalSkus = c.brands.reduce((s, b) => s + b.products.length, 0);
    const ownership = c.ownership || "—";
    const country = c.country || "";
    const role = c.business_role || "";
    return `
      <article class="v3-l2-co">
        <header class="co-head">
          <div class="co-title">
            <button class="co-name" type="button" data-company-id="${esc(c.company_id)}"
                    title="打开 ${esc(c.name)} 完整产品库" style="--track-accent:${accent};">
              ${esc(c.name)}
              <span class="co-name-arrow" aria-hidden="true">↗</span>
            </button>
            <div class="co-sub">
              ${country ? `<span>${esc(country)}</span>` : ""}
              ${role ? `<span class="pill">${esc(role)}</span>` : ""}
              <span class="pill ownership ${ownership.toLowerCase()}">${esc(ownership)}</span>
              <span class="co-count">${totalSkus} 产品 · ${c.brands.length} 品牌</span>
            </div>
          </div>
        </header>
        <div class="co-body">
          ${c.brands.map(renderBrand).join("")}
        </div>
      </article>
    `;
  }

  function show ({ l1, l2 }) {
    if (!window.V3_L2_DETAIL) {
      console.warn("V3_L2_DETAIL not loaded; cannot show L2 drawer");
      return;
    }
    const l1Node = window.V3_L2_DETAIL[l1];
    if (!l1Node || !l1Node[l2]) {
      console.warn(`V3_L2_DETAIL has no data for ${l1} / ${l2}`);
      return;
    }
    const companies = l1Node[l2];

    ensureDom();
    lastFocus = document.activeElement;
    const accent = TRACK_COLORS[l1] || "var(--accent-2)";
    const totalProducts = companies.reduce(
      (s, c) => s + c.brands.reduce((bs, b) => bs + b.products.length, 0),
      0
    );

    drawerEl.innerHTML = `
      <div class="v3-l2-head" style="--track-accent:${accent};">
        <button class="v3-l2-close" type="button" aria-label="关闭">×</button>
        <span class="v3-l2-stamp" style="color:${accent};border-color:${accent}66;">L2 · drill-down</span>
        <h2 class="v3-l2-title">
          <span class="l1">${esc(l1)}</span>
          <span class="sep">/</span>
          <span class="l2">${esc(l2)}</span>
        </h2>
        <div class="v3-l2-sub">${companies.length} 家公司 · ${totalProducts} 个产品 · 含注册证据</div>
      </div>
      <div class="v3-l2-body">
        ${companies.map(c => renderCompany(c, accent)).join("")}
      </div>
    `;

    drawerEl.querySelector(".v3-l2-close").addEventListener("click", close);
    wireExpand(drawerEl);

    // Each company "co-name" button drills into single-company V3CompanyDetail.
    drawerEl.querySelectorAll(".co-name[data-company-id]").forEach(btn => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-company-id");
        if (cid && window.V3CompanyDetail) {
          // Close this drawer first, then open the company one
          close();
          // Give it a tick so DOM cleanup completes
          setTimeout(() => window.V3CompanyDetail.show(cid, { source: "l2-drawer" }), 50);
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
    if (lastFocus && lastFocus.focus) {
      try { lastFocus.focus(); } catch (e) {}
    }
  }

  window.V3L2Drawer = { show, close, __installed: true };
})();

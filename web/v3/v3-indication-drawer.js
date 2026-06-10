/* v3 Indication drawer · in-place drill-down for indication bucket rows
 *
 * Sister of V3L2Drawer. Opens an overlay listing companies that have
 * official_indication_evidence tagged with this bucket, with brands → products →
 * indication evidence rows + registration evidence. Click company name to
 * escalate into single-company V3CompanyDetail drawer.
 *
 * Usage: window.V3IndicationDrawer.show({ bucket: "皱纹" });
 *
 * Data source: window.V3_INDICATION_DETAIL
 *   (built by scripts/_v3_build_indication_detail.py).
 */
(function () {
  if (window.V3IndicationDrawer && window.V3IndicationDrawer.__installed) return;

  // Use the v3 L2 drawer styles (.v3-l2-drawer etc.) — same visual language.
  // We add a different stamp ("Indication · drill-down") and an extra
  // "indication evidence" block per product (which L2 drawer doesn't show).

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
    drawerEl.className = "v3-l2-drawer v3-ind-drawer";
    drawerEl.setAttribute("role", "dialog");
    drawerEl.setAttribute("aria-modal", "true");
    drawerEl.setAttribute("aria-label", "适应症详情");
    drawerEl.addEventListener("click", e => e.stopPropagation());

    document.body.appendChild(backdropEl);
    document.body.appendChild(drawerEl);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawerEl.classList.contains("show")) close();
    });
  }

  function renderEvidence (rows) {
    if (!rows || !rows.length) return "";
    return `
      <div class="v3-l2-ind-block">
        <div class="ind-block-label">官方适应症证据 · ${rows.length} 条</div>
        <ul class="v3-l2-ind-list">
          ${rows.slice(0, 4).map(e => `
            <li>
              <span class="ind-evidence-reg">${esc(e.regulator || e.country || "—")}</span>
              ${e.year ? `<span class="ind-evidence-yr">${esc(e.year)}</span>` : ""}
              ${e.indication_text ? `<span class="ind-evidence-text">"${esc(e.indication_text)}"</span>` : ""}
              ${e.source_url ? `<a class="ind-evidence-src" href="${esc(e.source_url)}" target="_blank" rel="noopener">原文 ↗</a>` : ""}
            </li>
          `).join("")}
          ${rows.length > 4 ? `<li class="ind-evidence-more">+ 还有 ${rows.length - 4} 条同样指向该 bucket</li>` : ""}
        </ul>
      </div>
    `;
  }

  function renderRegRow (r) {
    const reg = r.regulator || r.jurisdiction || "—";
    return `
      <li class="v3-l2-reg">
        <span class="r-regulator" data-reg="${esc(reg)}">${esc(reg)}</span>
        ${r.number ? `<span class="r-no">${esc(r.number)}</span>` : ""}
        ${r.date ? `<span class="r-date">${esc(r.date)}</span>` : ""}
        ${r.pathway ? `<span class="r-pw">${esc(r.pathway)}</span>` : ""}
      </li>
    `;
  }

  function renderProduct (p) {
    const flagHtml = p.flag === "tier1"
      ? `<span class="flag-chip" title="经检索 FDA / EU / NMPA 未找到 registered_name，可定期复查">?</span>`
      : p.flag === "tier2"
        ? `<span class="flag-dot" title="经核公开渠道无适应症（外文 2A/2B 常态）"></span>`
        : "";
    const showRegName = p.registered_name && p.registered_name !== p.name;
    const regs = p.registrations || [];
    const indEv = p.indication_evidence || [];

    // Collapsed default: name + first reg chip (one-line credentials).
    // The indication evidence block (key for this drawer) AND the rest move
    // into the expanded body, shown only after click.
    const first = regs[0];
    const collapsedReg = first ? `
      <ul class="v3-l2-regs collapsed">
        ${renderRegRow(first)}
      </ul>
    ` : `<div class="v3-l2-noreg">— 该产品暂无 reg evidence —</div>`;

    const indCountPill = indEv.length
      ? `<span class="prod-more-pill">${indEv.length} 适应症证据</span>` : "";
    const moreRegsPill = regs.length > 1
      ? `<span class="prod-more-pill">+${regs.length - 1} 证</span>` : "";

    const hasExtras = indEv.length > 0 || regs.length > 1 || showRegName;
    const chevron = hasExtras
      ? `<span class="prod-chevron" aria-hidden="true">▾</span>` : "";

    const expandedBody = hasExtras ? `
      <div class="prod-expand">
        ${showRegName ? `<div class="prod-regname">${esc(p.registered_name)}</div>` : ""}
        ${renderEvidence(indEv)}
        ${regs.length > 1 ? `
          <ul class="v3-l2-regs full">
            ${regs.slice(1, 5).map(renderRegRow).join("")}
            ${regs.length > 5 ? `<li class="v3-l2-reg-more">+ 还有 ${regs.length - 5} 条 reg</li>` : ""}
          </ul>` : ""}
      </div>
    ` : "";

    return `
      <li class="v3-l2-prod${hasExtras ? " is-expandable" : ""}" data-flag="${p.flag || ""}">
        <div class="prod-head">
          <span class="prod-name">${esc(p.name)}</span>${flagHtml}
          ${indCountPill}${moreRegsPill}
          ${chevron}
        </div>
        ${collapsedReg}
        ${expandedBody}
      </li>
    `;
  }

  function wireExpand (root) {
    root.querySelectorAll(".v3-l2-prod.is-expandable").forEach(li => {
      const head = li.querySelector(".prod-head");
      head.addEventListener("click", () => li.classList.toggle("expanded"));
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
              ${c.country ? `<span>${esc(c.country)}</span>` : ""}
              ${c.business_role ? `<span class="pill">${esc(c.business_role)}</span>` : ""}
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

  function show ({ bucket }) {
    if (!window.V3_INDICATION_DETAIL) {
      console.warn("V3_INDICATION_DETAIL not loaded");
      return;
    }
    const companies = window.V3_INDICATION_DETAIL[bucket];
    if (!companies || !companies.length) {
      console.warn(`V3_INDICATION_DETAIL has no data for bucket=${bucket}`);
      return;
    }

    ensureDom();
    lastFocus = document.activeElement;
    const accent = "var(--accent-2)";
    const totalProducts = companies.reduce(
      (s, c) => s + c.brands.reduce((bs, b) => bs + b.products.length, 0),
      0
    );

    drawerEl.innerHTML = `
      <div class="v3-l2-head" style="--track-accent:${accent};">
        <button class="v3-l2-close" type="button" aria-label="关闭">×</button>
        <span class="v3-l2-stamp" style="color:${accent};border-color:rgba(184,89,87,0.4);">Indication · drill-down</span>
        <h2 class="v3-l2-title">
          <span class="l1">适应症</span>
          <span class="sep">/</span>
          <span class="l2">${esc(bucket)}</span>
        </h2>
        <div class="v3-l2-sub">${companies.length} 家公司 · ${totalProducts} 个产品 · 含官方适应症证据 + 注册证据</div>
      </div>
      <div class="v3-l2-body">
        ${companies.map(c => renderCompany(c, accent)).join("")}
      </div>
    `;

    drawerEl.querySelector(".v3-l2-close").addEventListener("click", close);
    wireExpand(drawerEl);

    drawerEl.querySelectorAll(".co-name[data-company-id]").forEach(btn => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-company-id");
        if (cid && window.V3CompanyDetail) {
          close();
          setTimeout(() => window.V3CompanyDetail.show(cid, { source: "indication-drawer" }), 50);
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

  window.V3IndicationDrawer = { show, close, __installed: true };
})();

/* v3 Cell drawer · single-cell drill for companies-matrix.html
 *
 * Click a non-zero cell in the company × material-L2 heatmap →
 * opens a side drawer listing every product the company has in that
 * specific material_l2 bucket. Click "查看完整产品库 ↗" or any product
 * row to escalate into V3CompanyDetail (the multi-brand single-company
 * drawer). Closes on ESC / backdrop click / × button.
 *
 * Usage:
 *   V3CellDrawer.show({
 *     companyId, companyName, country, ownership, primaryTrack,
 *     l2Name, l2GroupL1, n, products
 *   });
 *
 * Reuses the .v3-l2-drawer / .v3-l2-co CSS so it matches the existing
 * L2 drawer pattern (Aestra Soft language, no new tokens).
 */
(function () {
  if (window.V3CellDrawer && window.V3CellDrawer.__installed) return;

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
    drawerEl.className = "v3-l2-drawer v3-cell-drawer";
    drawerEl.setAttribute("role", "dialog");
    drawerEl.setAttribute("aria-modal", "true");
    drawerEl.setAttribute("aria-label", "矩阵单元详情");
    drawerEl.addEventListener("click", e => e.stopPropagation());

    document.body.appendChild(backdropEl);
    document.body.appendChild(drawerEl);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawerEl.classList.contains("show")) close();
    });
  }

  function renderProduct (p) {
    const flagHtml = p.flag === "tier1"
      ? `<span class="flag-chip" title="经检索 FDA / EU / NMPA 未找到 registered_name，可定期复查">?</span>`
      : p.flag === "tier2"
        ? `<span class="flag-dot" title="经核公开渠道无适应症（外文 2A/2B 常态）"></span>`
        : "";
    return `
      <li class="v3-l2-prod">
        <div class="prod-head">
          <span class="prod-name">${esc(p.name)}</span>${flagHtml}
          ${p.brand && p.brand !== p.name ? `<span class="prod-meta">${esc(p.brand)}</span>` : ""}
        </div>
        ${p.registered_name ? `<div class="prod-regname">${esc(p.registered_name)}</div>` : ""}
      </li>
    `;
  }

  function show (cfg) {
    const accent = TRACK_COLORS[cfg.l2GroupL1] || TRACK_COLORS[cfg.primaryTrack] || "var(--accent-2)";
    ensureDom();
    lastFocus = document.activeElement;

    drawerEl.innerHTML = `
      <div class="v3-l2-head" style="--track-accent:${accent};">
        <button class="v3-l2-close" type="button" aria-label="关闭">×</button>
        <span class="v3-l2-stamp" style="color:${accent};border-color:${accent}66;">Cell · drill-down</span>
        <h2 class="v3-l2-title">
          <button class="cm-co-name v3-cell-co" type="button" data-company-id="${esc(cfg.companyId)}" title="打开 ${esc(cfg.companyName)} 完整产品库 ↗">
            ${esc(cfg.companyName)}
            <span class="co-name-arrow" aria-hidden="true">↗</span>
          </button>
          <span class="sep">·</span>
          <span class="l2">${esc(cfg.l2Name)}</span>
        </h2>
        <div class="v3-l2-sub">
          ${cfg.n} 款产品 ·
          ${cfg.l2GroupL1 ? `<span style="color:${accent};font-weight:500;">${esc(cfg.l2GroupL1)}</span>` : ""}
          ${cfg.country ? ` · ${esc(cfg.country)}` : ""}
          ${cfg.ownership ? ` · ${esc(cfg.ownership)}` : ""}
        </div>
      </div>
      <div class="v3-l2-body">
        <article class="v3-l2-co">
          <ul class="v3-l2-prods v3-cell-prods">
            ${(cfg.products || []).map(renderProduct).join("")}
          </ul>
        </article>
      </div>
    `;

    drawerEl.querySelector(".v3-l2-close").addEventListener("click", close);

    // Click company name in header → escalate to full company drawer
    const coBtn = drawerEl.querySelector(".v3-cell-co");
    if (coBtn) {
      coBtn.addEventListener("click", () => {
        const cid = coBtn.getAttribute("data-company-id");
        if (cid && window.V3CompanyDetail) {
          close();
          setTimeout(() => window.V3CompanyDetail.show(cid, { source: "cell-drawer" }), 50);
        }
      });
    }

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

  window.V3CellDrawer = { show, close, __installed: true };
})();

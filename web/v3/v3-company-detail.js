/* =========================================================================
   v3 · Shared Company Detail Drawer
   --------------------------------------------------------------------------
   A single drawer component that any v3 page can open to inspect a company's
   brand → family → SKU portfolio tree.

   Usage:
     window.V3CompanyDetail.show(companyId);
     window.V3CompanyDetail.show(companyId, { source: "regulatory-pulse" });
     window.V3CompanyDetail.close();

   Requires loaded ahead of this script (any order):
     window.V3_PRODUCT_TREE_BY_COMPANY    (v3-product-tree.js)
     window.V3_COMPANIES_DATA              (v3-companies.js)  - optional
     window.GLOBAL_AESTHETICS_DATA         (app-data.js)       - optional

   This script is idempotent — including it twice is harmless.
   ========================================================================= */
(function () {
  if (window.V3CompanyDetail && window.V3CompanyDetail.__installed) return;

  const TRACK_COLORS = {
    "EBD":"#8E3A3A","Injectables":"#6B5A75","Skincare":"#D9AE91",
    "Regenerative":"#A8B59A","Consumables":"#5A6878","Implants":"#CFB58E",
    "Diagnostics":"#C76B68","Surgical":"#8C7B91","Pharma":"#EC9B73","Services":"#C8B8D0",
  };
  const displayTrack = (track) => track === "Skincare" ? "Cosmeceutical" : track;

  // ---- 1. inject styles once ----
  const STYLE_ID = "v3-company-detail-style";
  if (!document.getElementById(STYLE_ID)) {
    const css = `
      .v3-cd-backdrop{position:fixed;inset:0;background:rgba(58,51,64,0.32);backdrop-filter:blur(2px);
        opacity:0;pointer-events:none;transition:opacity .22s ease;z-index:9000;}
      .v3-cd-backdrop.show{opacity:1;pointer-events:auto;}
      .v3-cd-drawer{position:fixed;top:0;right:0;height:100vh;width:min(640px,92vw);
        background:var(--surface-2,#fdfaf2);color:var(--ink,#3a3340);
        box-shadow:-12px 0 40px rgba(58,51,64,0.22), -2px 0 8px rgba(58,51,64,0.08);
        transform:translateX(100%);transition:transform .28s cubic-bezier(.4,0,.2,1);
        z-index:9001;display:flex;flex-direction:column;
        font-family:var(--f-body,'Lora',serif);}
      .v3-cd-drawer.show{transform:translateX(0);}
      .v3-cd-head{padding:24px 28px 18px;border-bottom:1px solid var(--hairline-2,rgba(80,60,70,0.10));
        position:relative;flex-shrink:0;}
      .v3-cd-stamp{font-family:var(--f-mono,'DM Mono',monospace);font-size:10.5px;letter-spacing:0.14em;
        text-transform:uppercase;color:var(--muted,#6a5d68);display:inline-block;padding:3px 10px;
        border:1px solid var(--hairline,rgba(80,60,70,0.18));border-radius:99px;}
      .v3-cd-title{font-family:var(--f-display,'Marcellus',serif);font-size:30px;line-height:1.1;
        color:var(--ink,#3a3340);margin:12px 0 4px;font-weight:400;letter-spacing:-0.01em;}
      .v3-cd-sub{font-family:var(--f-body,'Lora',serif);font-size:13px;color:var(--muted,#6a5d68);
        font-style:italic;letter-spacing:0.02em;}
      .v3-cd-close{position:absolute;top:20px;right:22px;width:32px;height:32px;border-radius:50%;
        border:1px solid var(--hairline,rgba(80,60,70,0.18));background:transparent;color:var(--ink,#3a3340);
        font-size:18px;line-height:1;cursor:pointer;transition:all .15s ease;}
      .v3-cd-close:hover{background:var(--accent,#b85957);color:#fff;border-color:var(--accent,#b85957);}
      .v3-cd-meta-row{display:flex;flex-wrap:wrap;gap:18px;margin-top:14px;
        font-family:var(--f-mono,'DM Mono',monospace);font-size:11px;letter-spacing:0.08em;
        color:var(--ink-2,#524656);text-transform:uppercase;}
      .v3-cd-meta-row .cell{display:flex;flex-direction:column;gap:2px;}
      .v3-cd-meta-row .cell .k{font-size:9.5px;color:var(--muted,#6a5d68);letter-spacing:0.14em;}
      .v3-cd-meta-row .cell .v{font-size:13.5px;font-family:var(--f-body,'Lora',serif);font-style:italic;
        font-weight:500;color:var(--ink,#3a3340);text-transform:none;letter-spacing:0.01em;}
      .v3-cd-meta-row .cell .v .num{font-family:var(--f-serif-it,'Newsreader',serif);font-weight:500;
        font-size:18px;font-style:italic;color:var(--accent,#b85957);}
      .v3-cd-toolbar{padding:14px 28px 10px;border-bottom:1px solid var(--hairline-2,rgba(80,60,70,0.10));
        display:flex;gap:12px;align-items:center;flex-shrink:0;}
      .v3-cd-search{flex:1;height:34px;padding:0 14px;border:1px solid var(--hairline,rgba(80,60,70,0.18));
        border-radius:99px;background:var(--surface-3,#fff);color:var(--ink,#3a3340);
        font-family:var(--f-body,'Lora',serif);font-size:13px;outline:none;
        transition:border-color .15s ease;}
      .v3-cd-search:focus{border-color:var(--accent,#b85957);}
      .v3-cd-toggle{padding:6px 14px;border:1px solid var(--hairline,rgba(80,60,70,0.18));
        border-radius:99px;background:transparent;color:var(--ink-2,#524656);
        font-family:var(--f-mono,'DM Mono',monospace);font-size:10.5px;letter-spacing:0.08em;
        text-transform:uppercase;cursor:pointer;transition:all .15s ease;}
      .v3-cd-toggle:hover{background:var(--ink,#3a3340);color:#fff;border-color:var(--ink,#3a3340);}
      .v3-cd-body{flex:1;overflow-y:auto;padding:20px 28px 32px;}
      .v3-cd-empty{padding:48px 0;text-align:center;color:var(--muted,#6a5d68);font-style:italic;
        font-family:var(--f-body,'Lora',serif);font-size:13px;}

      /* ---- Brand block ---- */
      .v3-cd-brand{margin-bottom:22px;border-radius:6px;background:var(--surface-3,#fff);
        border:1px solid var(--hairline-2,rgba(80,60,70,0.10));overflow:hidden;}
      .v3-cd-brand-head{display:flex;align-items:center;gap:10px;padding:12px 16px;
        background:linear-gradient(180deg, var(--surface,#f7f1e6) 0%, var(--surface-3,#fff) 100%);
        border-bottom:1px solid var(--hairline-2,rgba(80,60,70,0.10));cursor:pointer;user-select:none;}
      .v3-cd-brand-head .caret{font-family:var(--f-mono,'DM Mono',monospace);font-size:10px;
        color:var(--muted,#6a5d68);width:12px;transition:transform .2s ease;}
      .v3-cd-brand.collapsed .v3-cd-brand-head .caret{transform:rotate(-90deg);}
      .v3-cd-brand-head .name{font-family:var(--f-display,'Marcellus',serif);font-size:18px;
        color:var(--ink,#3a3340);font-weight:400;letter-spacing:0.01em;flex:1;}
      .v3-cd-brand-head .role{font-family:var(--f-mono,'DM Mono',monospace);font-size:9.5px;
        letter-spacing:0.14em;text-transform:uppercase;padding:2px 8px;
        border:1px solid var(--hairline,rgba(80,60,70,0.18));border-radius:99px;color:var(--muted,#6a5d68);}
      .v3-cd-brand-head .counts{font-family:var(--f-mono,'DM Mono',monospace);font-size:11px;
        letter-spacing:0.08em;color:var(--ink-2,#524656);}
      .v3-cd-brand-head .counts em{font-family:var(--f-serif-it,'Newsreader',serif);font-style:italic;
        font-weight:500;color:var(--accent,#b85957);font-size:14px;margin-right:2px;}
      .v3-cd-brand.collapsed .v3-cd-families{display:none;}

      /* ---- Family row ---- */
      .v3-cd-family{padding:10px 16px;border-bottom:1px dashed var(--hairline-2,rgba(80,60,70,0.10));}
      .v3-cd-family:last-child{border-bottom:none;}
      .v3-cd-family-head{display:flex;align-items:flex-start;gap:8px;cursor:pointer;user-select:none;
        margin-bottom:4px;}
      .v3-cd-family-head .caret{font-family:var(--f-mono,'DM Mono',monospace);font-size:10px;
        color:var(--muted,#6a5d68);width:10px;margin-top:4px;transition:transform .2s ease;flex-shrink:0;}
      .v3-cd-family.collapsed .v3-cd-family-head .caret{transform:rotate(-90deg);}
      .v3-cd-family-head .nm{font-family:var(--f-body,'Lora',serif);font-size:14px;color:var(--ink,#3a3340);
        font-weight:500;line-height:1.35;flex:1;}
      .v3-cd-family-head .sku-ct{font-family:var(--f-mono,'DM Mono',monospace);font-size:10px;
        color:var(--muted,#6a5d68);letter-spacing:0.06em;flex-shrink:0;margin-top:3px;}
      .v3-cd-family-meta{display:flex;flex-wrap:wrap;gap:6px;margin-left:18px;margin-bottom:8px;}
      .v3-cd-chip{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;
        font-family:var(--f-mono,'DM Mono',monospace);font-size:9.5px;letter-spacing:0.08em;
        text-transform:uppercase;border-radius:3px;border:1px solid currentColor;
        color:var(--muted,#6a5d68);background:var(--surface,#f7f1e6);
        max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
      .v3-cd-chip:hover{max-width:none;cursor:help;}
      .v3-cd-chip.l1{color:var(--track-color, var(--ink,#3a3340));background:rgba(184,89,87,0.06);}
      .v3-cd-chip .label{opacity:0.62;font-size:8.5px;margin-right:2px;}
      .v3-cd-family.collapsed .v3-cd-skus{display:none;}

      /* ---- SKU rows ---- */
      .v3-cd-skus{margin-left:18px;border-left:1px solid var(--hairline-2,rgba(80,60,70,0.10));
        padding-left:14px;}
      .v3-cd-sku{padding:6px 0;border-bottom:1px dotted var(--hairline-2,rgba(80,60,70,0.10));}
      .v3-cd-sku:last-child{border-bottom:none;}
      .v3-cd-sku .sku-name{font-family:var(--f-body,'Lora',serif);font-size:13px;color:var(--ink,#3a3340);
        line-height:1.4;font-weight:500;}
      .v3-cd-sku .sku-name .model{font-family:var(--f-mono,'DM Mono',monospace);font-size:10.5px;
        font-style:normal;font-weight:400;color:var(--muted,#6a5d68);margin-left:6px;letter-spacing:0.04em;}
      .v3-cd-sku .sku-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:3px;
        font-family:var(--f-mono,'DM Mono',monospace);font-size:10px;color:var(--muted,#6a5d68);
        letter-spacing:0.04em;line-height:1.4;}
      .v3-cd-sku .sku-meta .k{opacity:0.65;}
      .v3-cd-sku .sku-meta .v{color:var(--ink-2,#524656);}
      .v3-cd-sku .sku-diff{margin-top:4px;font-family:var(--f-body,'Lora',serif);font-size:12px;
        color:var(--ink-2,#524656);font-style:italic;line-height:1.45;opacity:0.85;
        max-height:3.6em;overflow:hidden;}

      /* ---- Highlighting on search ---- */
      .v3-cd-hl{background:rgba(236,155,115,0.32);color:var(--ink,#3a3340);padding:0 2px;border-radius:2px;}

      /* small screen ---- */
      @media (max-width: 720px){
        .v3-cd-drawer{width:100vw;}
        .v3-cd-head{padding:18px 20px 14px;}
        .v3-cd-toolbar{padding:12px 20px 8px;}
        .v3-cd-body{padding:16px 20px 24px;}
        .v3-cd-title{font-size:24px;}
      }
    `;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    document.head.appendChild(el);
  }

  // ---- 2. DOM scaffold (lazily appended on first show) ----
  let backdropEl = null;
  let drawerEl = null;
  let lastFocus = null;
  let currentCompanyId = null;

  function ensureDom () {
    if (backdropEl) return;
    backdropEl = document.createElement("div");
    backdropEl.className = "v3-cd-backdrop";
    backdropEl.addEventListener("click", close);

    drawerEl = document.createElement("aside");
    drawerEl.className = "v3-cd-drawer";
    drawerEl.setAttribute("role", "dialog");
    drawerEl.setAttribute("aria-modal", "true");
    drawerEl.setAttribute("aria-label", "公司详情");
    // Prevent backdrop click bubbling when clicking inside drawer
    drawerEl.addEventListener("click", e => e.stopPropagation());

    document.body.appendChild(backdropEl);
    document.body.appendChild(drawerEl);

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && drawerEl.classList.contains("show")) close();
    });
  }

  // ---- 3. Lookup company meta from any available data source ----
  function lookupCompany (companyId) {
    // Try V3_COMPANIES_DATA.companies first (companies.html)
    const cd = window.V3_COMPANIES_DATA;
    if (cd && Array.isArray(cd.companies)) {
      const c = cd.companies.find(x => x.id === companyId || x.company_id === companyId);
      if (c) return c;
    }
    // Try GLOBAL_AESTHETICS_DATA.geo_companies (used by globe + most v3 pages)
    const gd = window.GLOBAL_AESTHETICS_DATA;
    if (gd && Array.isArray(gd.geo_companies)) {
      const c = gd.geo_companies.find(x => x.company_id === companyId);
      if (c) return c;
    }
    // Try other common shapes (regulatory-pulse top companies, capital-map etc.)
    if (gd) {
      for (const key of ["regulatory_top_companies", "capital_companies", "evidence_top_companies"]) {
        const arr = gd[key];
        if (Array.isArray(arr)) {
          const c = arr.find(x => x.company_id === companyId);
          if (c) return c;
        }
      }
    }
    return null;
  }

  // ---- 4. Build markup ----
  function escapeHtml (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({
      "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
    })[ch]);
  }

  function render (companyId) {
    const tree = (window.V3_PRODUCT_TREE_BY_COMPANY || {})[companyId] || [];
    const meta = lookupCompany(companyId) || {};
    const name = meta.name || meta.company || companyId;
    const country = meta.country || "";
    const city = meta.city || "";
    const region = meta.region || "";
    const primaryTrack = meta.primary_track || "";
    const ownership = meta.ownership || "—";
    const stockCode = meta.stock_code || "";
    const products = meta.products || meta.product_count || tree.reduce((s, b) => s + b.sku_count, 0);
    const brands = meta.brands || meta.brand_count || tree.length;
    const accent = TRACK_COLORS[primaryTrack] || "var(--accent)";

    const subLine = [city, country].filter(Boolean).join(", ") +
      (region ? ` · ${region}` : "") +
      (primaryTrack ? ` · ${displayTrack(primaryTrack)}` : "");

    const metaCells = `
      <div class="v3-cd-meta-row">
        <div class="cell"><span class="k">Products</span><span class="v"><span class="num">${products}</span> SKUs</span></div>
        <div class="cell"><span class="k">Brands</span><span class="v"><span class="num">${brands}</span></span></div>
        <div class="cell"><span class="k">Ownership</span><span class="v">${escapeHtml(ownership)}${stockCode ? ` · <span style="font-family:var(--f-mono);font-size:11px;font-style:normal;">${escapeHtml(stockCode)}</span>` : ""}</span></div>
      </div>
    `;

    let bodyHtml;
    if (!tree.length) {
      bodyHtml = `<div class="v3-cd-empty">product_master 暂无该公司产品记录</div>`;
    } else {
      bodyHtml = tree.map((brand, bi) => {
        const brandName = brand.brand || "(no brand)";
        const role = brand.brand_role || "";
        const famHtml = brand.families.map((fam, fi) => {
          const trackColor = TRACK_COLORS[fam.l1] || "var(--ink-2)";
          const chips = [];
          if (fam.l1) chips.push(`<span class="v3-cd-chip l1" title="${escapeHtml(displayTrack(fam.l1))}" style="--track-color:${trackColor};color:${trackColor};border-color:${trackColor};background:${trackColor}11;"><span class="label">L1</span>${escapeHtml(displayTrack(fam.l1))}</span>`);
          if (fam.l2) chips.push(`<span class="v3-cd-chip" title="${escapeHtml(fam.l2)}"><span class="label">L2</span>${escapeHtml(fam.l2)}</span>`);
          if (fam.tech) chips.push(`<span class="v3-cd-chip" title="${escapeHtml(fam.tech)}"><span class="label">Tech</span>${escapeHtml(fam.tech)}</span>`);
          if (fam.countries) chips.push(`<span class="v3-cd-chip" title="${escapeHtml(fam.countries)}"><span class="label">In</span>${escapeHtml(fam.countries)}</span>`);

          const skusHtml = fam.skus.map(sku => {
            const meta = [];
            if (sku.tech_l2 && sku.tech_l2 !== fam.tech) meta.push(`<span><span class="k">Tech L2</span> <span class="v">${escapeHtml(sku.tech_l2)}</span></span>`);
            if (sku.material && sku.material !== fam.material) meta.push(`<span><span class="k">Material</span> <span class="v">${escapeHtml(sku.material)}</span></span>`);
            if (sku.registered_name && sku.registered_name !== sku.name) meta.push(`<span><span class="k">Registered</span> <span class="v">${escapeHtml(sku.registered_name)}</span></span>`);
            if (sku.tags) meta.push(`<span><span class="k">Tags</span> <span class="v">${escapeHtml(sku.tags)}</span></span>`);
            // Tier 1 — registered_name missing across reg evidence → oxblood "?" chip
            // Tier 2 — indication marked unavailable_verified → small 5px dark-red dot
            const flagHtml = sku.flag === "tier1"
              ? `<span class="flag-chip" title="经检索 FDA / EU / NMPA 未找到 registered_name，可定期复查">?</span>`
              : sku.flag === "tier2"
                ? `<span class="flag-dot" title="经核公开渠道无适应症（外文 2A/2B 常态）"></span>`
                : "";
            return `
              <div class="v3-cd-sku" data-flag="${sku.flag || ""}" data-search="${escapeHtml((sku.name + " " + (sku.model_or_sku || "") + " " + (sku.tags || "") + " " + (sku.differentiator || "")).toLowerCase())}">
                <div class="sku-name">${escapeHtml(sku.name)}${sku.model_or_sku ? `<span class="model">${escapeHtml(sku.model_or_sku)}</span>` : ""}${flagHtml}</div>
                ${meta.length ? `<div class="sku-meta">${meta.join("")}</div>` : ""}
                ${sku.differentiator ? `<div class="sku-diff">${escapeHtml(sku.differentiator)}</div>` : ""}
              </div>
            `;
          }).join("");

          return `
            <div class="v3-cd-family" data-search="${escapeHtml((fam.family + " " + (fam.l1 || "") + " " + (fam.l2 || "") + " " + (fam.tech || "")).toLowerCase())}">
              <div class="v3-cd-family-head">
                <span class="caret">▼</span>
                <span class="nm">${escapeHtml(fam.family || "(unnamed family)")}</span>
                <span class="sku-ct">${fam.sku_count} SKU${fam.sku_count > 1 ? "s" : ""}</span>
              </div>
              <div class="v3-cd-family-meta">${chips.join("")}</div>
              <div class="v3-cd-skus">${skusHtml}</div>
            </div>
          `;
        }).join("");

        return `
          <div class="v3-cd-brand" data-search="${escapeHtml((brandName + " " + role).toLowerCase())}">
            <div class="v3-cd-brand-head">
              <span class="caret">▼</span>
              <span class="name">${escapeHtml(brandName)}</span>
              ${role ? `<span class="role">${escapeHtml(role)}</span>` : ""}
              <span class="counts"><em>${brand.family_count}</em>fam · <em>${brand.sku_count}</em>sku</span>
            </div>
            <div class="v3-cd-families">${famHtml}</div>
          </div>
        `;
      }).join("");
    }

    drawerEl.innerHTML = `
      <div class="v3-cd-head">
        <button class="v3-cd-close" type="button" aria-label="关闭">×</button>
        <span class="v3-cd-stamp" style="color:${accent};border-color:${accent}66;">Company · drill-down</span>
        <h2 class="v3-cd-title">${escapeHtml(name)}</h2>
        <div class="v3-cd-sub">${escapeHtml(subLine || "—")}</div>
        ${metaCells}
      </div>
      <div class="v3-cd-toolbar">
        <input type="search" class="v3-cd-search" placeholder="搜索品牌 / 产品族 / SKU…" aria-label="搜索" />
        <button class="v3-cd-toggle" data-action="expand">全展开</button>
        <button class="v3-cd-toggle" data-action="collapse">全折叠</button>
      </div>
      <div class="v3-cd-body">${bodyHtml}</div>
    `;

    // ---- Wire interactions ----
    drawerEl.querySelector(".v3-cd-close").addEventListener("click", close);

    drawerEl.querySelectorAll(".v3-cd-brand-head").forEach(head => {
      head.addEventListener("click", () => {
        head.closest(".v3-cd-brand").classList.toggle("collapsed");
      });
    });
    drawerEl.querySelectorAll(".v3-cd-family-head").forEach(head => {
      head.addEventListener("click", () => {
        head.closest(".v3-cd-family").classList.toggle("collapsed");
      });
    });

    drawerEl.querySelector(".v3-cd-toggle[data-action='expand']").addEventListener("click", () => {
      drawerEl.querySelectorAll(".v3-cd-brand, .v3-cd-family").forEach(el => el.classList.remove("collapsed"));
    });
    drawerEl.querySelector(".v3-cd-toggle[data-action='collapse']").addEventListener("click", () => {
      drawerEl.querySelectorAll(".v3-cd-brand, .v3-cd-family").forEach(el => el.classList.add("collapsed"));
    });

    // Search filter — matches brand / family / SKU; collapses non-matching ancestors
    const searchEl = drawerEl.querySelector(".v3-cd-search");
    searchEl.addEventListener("input", () => {
      const q = searchEl.value.trim().toLowerCase();
      if (!q) {
        drawerEl.querySelectorAll(".v3-cd-brand, .v3-cd-family, .v3-cd-sku").forEach(el => {
          el.style.display = "";
        });
        return;
      }
      drawerEl.querySelectorAll(".v3-cd-brand").forEach(brand => {
        const brandHay = brand.dataset.search || "";
        let brandMatch = brandHay.includes(q);
        let anyFamMatch = false;
        brand.querySelectorAll(".v3-cd-family").forEach(fam => {
          const famHay = fam.dataset.search || "";
          let famMatch = famHay.includes(q);
          let anySkuMatch = false;
          fam.querySelectorAll(".v3-cd-sku").forEach(sku => {
            const skuHay = sku.dataset.search || "";
            const skuMatch = skuHay.includes(q) || famMatch || brandMatch;
            sku.style.display = skuMatch ? "" : "none";
            if (skuMatch) anySkuMatch = true;
          });
          const showFam = famMatch || anySkuMatch || brandMatch;
          fam.style.display = showFam ? "" : "none";
          if (showFam) anyFamMatch = true;
          if (showFam) fam.classList.remove("collapsed");
        });
        const showBrand = brandMatch || anyFamMatch;
        brand.style.display = showBrand ? "" : "none";
        if (showBrand) brand.classList.remove("collapsed");
      });
    });
  }

  // ---- 5. Public API ----
  function show (companyId, opts = {}) {
    if (!companyId) {
      console.warn("[v3-company-detail] show() called with empty companyId");
      return;
    }
    ensureDom();
    currentCompanyId = companyId;
    lastFocus = document.activeElement;
    render(companyId);
    requestAnimationFrame(() => {
      backdropEl.classList.add("show");
      drawerEl.classList.add("show");
      const searchEl = drawerEl.querySelector(".v3-cd-search");
      if (searchEl && !opts.skipFocus) {
        // Focus search after transition completes
        setTimeout(() => searchEl.focus(), 300);
      }
    });
  }

  function close () {
    if (!drawerEl) return;
    drawerEl.classList.remove("show");
    backdropEl.classList.remove("show");
    currentCompanyId = null;
    if (lastFocus && typeof lastFocus.focus === "function") {
      try { lastFocus.focus(); } catch (e) { /* ignore */ }
    }
  }

  // ---- 6. Helper: resolve company_id from a display name ----
  function buildNameIndex () {
    const idx = new Map();
    const cd = window.V3_COMPANIES_DATA;
    if (cd && cd.companies) {
      cd.companies.forEach(c => {
        const key = (c.name || "").toLowerCase().trim();
        if (key) idx.set(key, c.company_id);
      });
    }
    const gd = window.GLOBAL_AESTHETICS_DATA;
    if (gd && gd.geo_companies) {
      gd.geo_companies.forEach(c => {
        const key = (c.company || c.name || "").toLowerCase().trim();
        if (key && !idx.has(key)) idx.set(key, c.company_id);
      });
    }
    return idx;
  }

  function resolveCompanyId (rawName, index) {
    if (!rawName) return null;
    const idx = index || buildNameIndex();
    const lower = rawName.toLowerCase().trim();
    if (idx.has(lower)) return idx.get(lower);

    // collect candidate strings to try in order
    const candidates = [];
    // first segment before " / ", " · ", " — "
    candidates.push(lower.split(/[/·—]/)[0].trim());
    // content inside parens — e.g. "AbbVie (Allergan Aesthetics)" → "allergan aesthetics"
    const parenMatch = lower.match(/\(([^)]+)\)/);
    if (parenMatch) {
      candidates.push(parenMatch[1].trim());
      candidates.push(parenMatch[1].split(/[/·—]/)[0].trim());
    }
    // strip parens entirely
    candidates.push(lower.replace(/\([^)]*\)/g, "").trim());
    // first word(s) — useful for "AbbVie ..." → "abbvie"
    candidates.push(lower.split(/[\s/·—(]/)[0]);

    for (const cand of candidates) {
      if (!cand) continue;
      if (idx.has(cand)) return idx.get(cand);
    }
    // permissive prefix/contains match (last resort) — try each candidate
    for (const cand of candidates) {
      if (!cand || cand.length < 3) continue;
      for (const [k, v] of idx) {
        if (!k) continue;
        if (k.startsWith(cand) || cand.startsWith(k) || k.includes(cand)) return v;
      }
    }
    return null;
  }

  /**
   * Auto-wire all rows in a given table (or container) by matching the company
   * name found in the specified cell.
   *
   *   V3CompanyDetail.attachToTable(".table-card table tbody tr", {nameCellSelector: "td:nth-child(2)"});
   */
  function attachToTable (rowSelector, opts = {}) {
    const nameCellSel = opts.nameCellSelector || "td:nth-child(2)";
    const root = opts.root || document;
    const index = buildNameIndex();
    root.querySelectorAll(rowSelector).forEach(row => {
      if (row.dataset.companyId) {
        const cid = row.dataset.companyId;
        if (cid) attachClick(row, cid);
        return;
      }
      const cell = row.querySelector(nameCellSel);
      if (!cell) return;
      const raw = cell.textContent.trim();
      const cid = resolveCompanyId(raw, index);
      if (!cid) return;
      row.dataset.companyId = cid;
      attachClick(row, cid);
    });
  }

  function attachClick (el, companyId) {
    if (el.dataset.v3cdWired) return;
    el.dataset.v3cdWired = "1";
    el.classList.add("co-row");
    if (!el.hasAttribute("tabindex")) el.setAttribute("tabindex", "0");
    if (!el.hasAttribute("role")) el.setAttribute("role", "button");
    el.style.cursor = "pointer";
    el.addEventListener("click", () => show(companyId));
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); show(companyId); }
    });
  }

  window.V3CompanyDetail = {
    __installed: true,
    show: show,
    close: close,
    current: () => currentCompanyId,
    resolveCompanyId: resolveCompanyId,
    attachToTable: attachToTable,
    attachClick: attachClick,
  };
})();

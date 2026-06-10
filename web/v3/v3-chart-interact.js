/* =========================================================================
   v3 · Shared chart-interactivity primitives
   --------------------------------------------------------------------------
   Two singletons:
     V3Tooltip       hover tooltip with v3 Aestra Soft styling
     V3DrillPanel    right-side panel that lists clickable rows.
                     Each row cascades to V3CompanyDetail when company_id given.

   Usage:
     V3Tooltip.attach(el, () => ({ title: "...", lines: ["...", "..."] }));
     V3DrillPanel.open({
        stamp: "Chart · drill",
        title: "EBD · 480 products",
        sub:   "172 companies · top tracks: ...",
        rows:  [{company_id, name, hint, color, badge}, ...],
     });

   Both modules are idempotent (safe to include on every page that already
   includes them via topic.html / cross-analysis.html DOM scaffolding).
   ========================================================================= */
(function () {
  if (window.V3DrillPanel && window.V3DrillPanel.__installed) return;

  // ------------------------------------------------------------------
  // CSS — inject once
  // ------------------------------------------------------------------
  const STYLE_ID = "v3-chart-interact-style";
  if (!document.getElementById(STYLE_ID)) {
    const css = `
      /* ===== Tooltip ===== */
      .v3-tip {
        position: fixed;
        z-index: 9500;
        pointer-events: auto;
        opacity: 0;
        transform: translateY(7px) scale(0.985);
        transition:
          opacity .18s cubic-bezier(.22,1,.36,1),
          transform .18s cubic-bezier(.22,1,.36,1);
        width: min(338px, calc(100vw - 24px));
        max-width: 338px;
        color: var(--ink, #3a3340);
        background:
          radial-gradient(circle at 14% 4%, rgba(255,255,255,0.95), transparent 44%),
          linear-gradient(155deg, rgba(255, 253, 248, 0.80), rgba(248, 242, 233, 0.66));
        backdrop-filter: blur(26px) saturate(155%);
        -webkit-backdrop-filter: blur(26px) saturate(155%);
        font-family: var(--f-body, 'Lora', serif);
        font-size: 12px;
        line-height: 1.42;
        padding: 15px 16px 14px;
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.72);
        box-shadow:
          0 26px 54px rgba(58, 51, 64, 0.18),
          0 9px 22px rgba(58, 51, 64, 0.10),
          inset 0 1px 0 rgba(255, 255, 255, 0.9),
          inset 0 0 0 1px rgba(80, 60, 70, 0.05);
        letter-spacing: 0.01em;
        overflow: hidden;
        isolation: isolate;
      }
      .v3-tip::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: -1;
        background:
          linear-gradient(160deg, rgba(255,255,255,0.55), transparent 46%),
          radial-gradient(circle at 96% 92%, rgba(184,89,87,0.10), transparent 48%);
      }
      .v3-tip.show {
        opacity: 1;
        transform: translateY(0) scale(1);
      }
      .v3-tip .tip-close {
        position: absolute;
        top: 9px;
        right: 9px;
        width: 22px;
        height: 22px;
        border: 1px solid rgba(80, 60, 70, 0.16);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.55);
        color: var(--muted, #6a5d68);
        font-size: 14px;
        line-height: 18px;
        cursor: pointer;
        display: grid;
        place-items: center;
        transition: transform .16s cubic-bezier(.22,1,.36,1), background .16s ease, color .16s ease;
      }
      .v3-tip .tip-close:hover {
        transform: scale(1.05);
        background: var(--accent, #b85957);
        border-color: var(--accent, #b85957);
        color: #fff;
      }
      .v3-tip .tip-head {
        padding-right: 28px;
      }
      .v3-tip .tip-title {
        font-family: var(--f-display, 'Marcellus', serif);
        font-size: 15.5px;
        line-height: 1.16;
        margin-bottom: 3px;
        letter-spacing: 0.02em;
        color: var(--ink, #3a3340);
        font-weight: 500;
      }
      .v3-tip .tip-subtitle {
        font-family: var(--f-sans, 'Inter', sans-serif);
        font-size: 11px;
        color: var(--muted, #6a5d68);
        letter-spacing: 0.02em;
      }
      .v3-tip .tip-body {
        margin-top: 9px;
        color: var(--ink-2, #524656);
        font-family: var(--f-body, 'Lora', serif);
        font-size: 12px;
      }
      .v3-tip .tip-metrics {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin-top: 12px;
      }
      .v3-tip .tip-metric {
        min-width: 0;
        padding: 8px 9px 7px;
        border-radius: 11px;
        background: rgba(255, 255, 255, 0.5);
        border: 1px solid rgba(80, 60, 70, 0.07);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
      }
      .v3-tip .tip-metric .metric-value {
        display: block;
        font-family: var(--f-sans, 'DM Sans', sans-serif);
        font-feature-settings: "tnum" 1;
        font-size: 18px;
        line-height: 1;
        color: var(--metric-color, var(--ink, #3a3340));
        font-weight: 600;
        letter-spacing: -0.01em;
      }
      .v3-tip .tip-metric .metric-label {
        display: block;
        margin-top: 5px;
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 8.7px;
        color: var(--muted, #6a5d68);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      /* ===== Stacked composition bar (track / category occupancy) ===== */
      .v3-tip .tip-stack {
        display: flex;
        height: 10px;
        margin-top: 12px;
        border-radius: 99px;
        overflow: hidden;
        background: rgba(80, 60, 70, 0.08);
        box-shadow: inset 0 0 0 1px rgba(80, 60, 70, 0.05);
      }
      .v3-tip .tip-stack .seg {
        height: 100%;
        min-width: 2px;
        background: var(--seg-color, #b85957);
      }
      .v3-tip .tip-stack-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 5px 13px;
        margin-top: 9px;
      }
      .v3-tip .tip-stack-legend .key {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 10px;
        letter-spacing: 0.02em;
        color: var(--ink-2, #524656);
      }
      .v3-tip .tip-stack-legend .key i {
        width: 9px;
        height: 9px;
        border-radius: 3px;
        background: var(--seg-color, #b85957);
        flex-shrink: 0;
      }
      .v3-tip .tip-stack-legend .key b {
        font-weight: 600;
        color: var(--ink, #3a3340);
        margin-left: 1px;
      }
      .v3-tip .tip-bars {
        display: grid;
        gap: 7px;
        margin-top: 12px;
      }
      .v3-tip .tip-bar {
        display: grid;
        grid-template-columns: minmax(70px, 1fr) 64px minmax(20px, auto);
        align-items: center;
        gap: 8px;
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 9px;
        color: var(--ink-2, #524656);
        letter-spacing: 0.05em;
      }
      .v3-tip .tip-bar-track {
        height: 5px;
        border-radius: 99px;
        background: rgba(80, 60, 70, 0.10);
        overflow: hidden;
      }
      .v3-tip .tip-bar-fill {
        display: block;
        height: 100%;
        width: var(--bar-pct, 0%);
        border-radius: inherit;
        background: var(--bar-color, #b85957);
      }
      .v3-tip .tip-line {
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 10.5px;
        letter-spacing: 0.04em;
        color: var(--ink-2, #524656);
        margin-top: 6px;
      }
      .v3-tip .tip-line em {
        font-family: var(--f-sans, 'DM Sans', sans-serif);
        font-style: normal;
        color: var(--accent-2, #8E3A3A);
        font-size: 13px;
        font-weight: 600;
        margin-right: 4px;
      }
      .v3-tip .tip-hint {
        margin-top: 11px;
        padding-top: 9px;
        border-top: 1px solid rgba(80, 60, 70, 0.12);
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 9px;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--muted, #6a5d68);
        font-style: normal;
      }
      @media (max-width: 560px) {
        .v3-tip {
          width: min(310px, calc(100vw - 20px));
          padding: 14px;
        }
        .v3-tip .tip-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .v3-tip .tip-bar { grid-template-columns: minmax(64px, 1fr) 56px minmax(18px, auto); }
      }

      /* ===== DrillPanel — shared with xa-drill / td-drill visual ===== */
      .v3-dp-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(58,51,64,0.22);
        backdrop-filter: blur(1.5px);
        opacity: 0;
        pointer-events: none;
        transition: opacity .2s ease;
        z-index: 9300;
      }
      .v3-dp-backdrop.show { opacity: 1; pointer-events: auto; }
      .v3-dp {
        position: fixed;
        top: 0;
        right: 0;
        height: 100vh;
        width: min(440px, 92vw);
        background: var(--surface-2, #fdfaf2);
        color: var(--ink, #3a3340);
        border-left: 1px solid var(--hairline, rgba(80,60,70,0.18));
        box-shadow: -10px 0 36px rgba(58,51,64,0.18);
        transform: translateX(100%);
        transition: transform .26s cubic-bezier(.4,0,.2,1);
        z-index: 9301;
        display: flex;
        flex-direction: column;
        font-family: var(--f-body, 'Lora', serif);
      }
      .v3-dp.show { transform: translateX(0); }
      .v3-dp .head {
        padding: 22px 26px 14px;
        border-bottom: 1px solid var(--hairline-2, rgba(80,60,70,0.10));
        position: relative;
      }
      .v3-dp .head .stamp {
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 10.5px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--muted, #6a5d68);
        padding: 3px 10px;
        border: 1px solid var(--hairline, rgba(80,60,70,0.18));
        border-radius: 99px;
        display: inline-block;
      }
      .v3-dp .head h3 {
        font-family: var(--f-display, 'Marcellus', serif);
        font-size: 22px;
        line-height: 1.2;
        margin: 10px 0 4px;
        font-weight: 400;
        color: var(--ink, #3a3340);
      }
      .v3-dp .head .sub {
        font-family: var(--f-body, 'Lora', serif);
        font-style: italic;
        font-size: 12.5px;
        color: var(--muted, #6a5d68);
      }
      .v3-dp .close-btn {
        position: absolute;
        top: 18px;
        right: 20px;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 1px solid var(--hairline, rgba(80,60,70,0.18));
        background: transparent;
        color: var(--ink, #3a3340);
        font-size: 16px;
        line-height: 1;
        cursor: pointer;
        transition: all .15s ease;
      }
      .v3-dp .close-btn:hover {
        background: var(--accent, #b85957);
        color: #fff;
        border-color: var(--accent, #b85957);
      }
      .v3-dp .body {
        flex: 1;
        overflow-y: auto;
        padding: 14px 22px 26px;
      }
      .v3-dp .body .empty {
        padding: 32px 0;
        text-align: center;
        font-style: italic;
        color: var(--muted, #6a5d68);
        font-family: var(--f-body, 'Lora', serif);
        font-size: 13px;
      }
      .v3-dp .body .row {
        display: flex;
        gap: 10px;
        align-items: center;
        padding: 8px 4px;
        border-bottom: 1px dashed var(--hairline-2, rgba(80,60,70,0.10));
        cursor: pointer;
        transition: background-color .12s ease;
      }
      .v3-dp .body .row:hover { background: rgba(184,89,87,0.04); }
      .v3-dp .body .row.noclick { cursor: default; }
      .v3-dp .body .row.noclick:hover { background: transparent; }
      .v3-dp .body .row .sw {
        width: 6px;
        height: 26px;
        border-radius: 2px;
        flex-shrink: 0;
        background: var(--row-color, var(--accent, #b85957));
      }
      .v3-dp .body .row .nm {
        flex: 1;
        font-family: var(--f-body, 'Lora', serif);
        font-size: 13px;
        color: var(--ink, #3a3340);
        font-weight: 500;
      }
      .v3-dp .body .row .nm small {
        display: block;
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 10px;
        color: var(--muted, #6a5d68);
        letter-spacing: 0.04em;
        margin-top: 2px;
        font-weight: 400;
      }
      .v3-dp .body .row .badge {
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 10px;
        padding: 2px 6px;
        border-radius: 3px;
        background: var(--surface-3, #fff);
        border: 1px solid var(--hairline, rgba(80,60,70,0.18));
        color: var(--ink-2, #524656);
        letter-spacing: 0.04em;
      }
      .v3-dp .body .summary-strip {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        padding: 10px 6px 14px;
        border-bottom: 1px solid var(--hairline-2, rgba(80,60,70,0.10));
        margin-bottom: 8px;
      }
      .v3-dp .body .summary-strip .cell {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .v3-dp .body .summary-strip .cell .k {
        font-family: var(--f-mono, 'DM Mono', monospace);
        font-size: 9.5px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted, #6a5d68);
      }
      .v3-dp .body .summary-strip .cell .v {
        font-family: var(--f-serif-it, 'Newsreader', serif);
        font-style: italic;
        font-weight: 500;
        font-size: 20px;
        color: var(--accent, #b85957);
      }

      /* Cursor hint on every chart element we wire */
      [data-v3-interactive="1"] { cursor: pointer; }

      /* SVG hit-testing — make donut slices catch hover/click on their stroked ring */
      .donut-slice, .reg-slice, .exch-slice {
        pointer-events: visibleStroke;
        cursor: pointer;
      }
    `;
    const el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    document.head.appendChild(el);
  }

  // ------------------------------------------------------------------
  // Tooltip
  // ------------------------------------------------------------------
  let tipEl = null;
  let activeTipAnchor = null;
  let dismissedAnchor = null;
  let hideTimer = null;
  function clearTipHide () {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }
  function ensureTip () {
    if (tipEl) return tipEl;
    tipEl = document.createElement("div");
    tipEl.className = "v3-tip";
    tipEl.setAttribute("role", "tooltip");
    tipEl.addEventListener("mouseenter", clearTipHide);
    tipEl.addEventListener("mouseleave", () => scheduleHideTip(120));
    tipEl.addEventListener("click", (evt) => {
      const btn = evt.target && evt.target.closest ? evt.target.closest(".tip-close") : null;
      if (!btn) return;
      evt.preventDefault();
      evt.stopPropagation();
      dismissedAnchor = activeTipAnchor;
      hideTip();
    });
    document.body.appendChild(tipEl);
    return tipEl;
  }

  function renderTipMetrics (metrics) {
    if (!metrics || !metrics.length) return "";
    return `<div class="tip-metrics">${metrics.map(m => {
      const value = m.value != null ? m.value : (m.v != null ? m.v : "");
      const label = m.label != null ? m.label : (m.k != null ? m.k : "");
      const color = m.color ? ` style="--metric-color:${escAttr(m.color)}"` : "";
      return `<div class="tip-metric"${color}><span class="metric-value">${esc(value)}</span><span class="metric-label">${esc(label)}</span></div>`;
    }).join("")}</div>`;
  }

  function renderTipBars (bars) {
    if (!bars || !bars.length) return "";
    return `<div class="tip-bars">${bars.map(b => {
      const pctRaw = Number(b.pct != null ? b.pct : b.value);
      const pct = Number.isFinite(pctRaw) ? Math.max(0, Math.min(100, pctRaw)) : 0;
      const label = b.label != null ? b.label : (b.k != null ? b.k : "");
      const value = b.valueLabel != null ? b.valueLabel : (b.value != null ? b.value : "");
      const color = b.color || "#f7b3a8";
      return `
        <div class="tip-bar">
          <span>${esc(label)}</span>
          <span class="tip-bar-track"><span class="tip-bar-fill" style="--bar-pct:${pct.toFixed(1)}%;--bar-color:${escAttr(color)}"></span></span>
          <span>${esc(value)}</span>
        </div>
      `;
    }).join("")}</div>`;
  }

  function renderTipStack (stack) {
    if (!stack || !stack.length) return "";
    const items = stack
      .map(s => ({
        label: s.label != null ? s.label : (s.k != null ? s.k : ""),
        value: Number(s.value != null ? s.value : (s.n != null ? s.n : 0)) || 0,
        color: s.color || "#b85957",
      }))
      .filter(s => s.value > 0);
    if (!items.length) return "";
    const total = items.reduce((a, b) => a + b.value, 0) || 1;
    const segs = items.map(s =>
      `<span class="seg" style="flex:${s.value};--seg-color:${escAttr(s.color)}" title="${escAttr(s.label)} · ${s.value}"></span>`
    ).join("");
    const legend = items.slice(0, 3).map(s =>
      `<span class="key" style="--seg-color:${escAttr(s.color)}"><i></i>${esc(s.label)}<b>${esc(s.value)}</b></span>`
    ).join("");
    return `<div class="tip-stack">${segs}</div><div class="tip-stack-legend">${legend}</div>`;
  }

  function showTip (cfg, x, y, anchor) {
    if (dismissedAnchor && anchor && dismissedAnchor === anchor) return;
    clearTipHide();
    activeTipAnchor = anchor || activeTipAnchor;
    const t = ensureTip();
    const subtitle = cfg.subtitle || cfg.sub || cfg.kicker || "";
    let html = "";
    html += `<button class="tip-close" type="button" aria-label="关闭">×</button>`;
    if (cfg.title || subtitle) {
      html += `<div class="tip-head">`;
      if (cfg.title) html += `<div class="tip-title">${esc(cfg.title)}</div>`;
      if (subtitle) html += `<div class="tip-subtitle">${esc(subtitle)}</div>`;
      html += `</div>`;
    }
    html += renderTipMetrics(cfg.metrics || cfg.summary);
    html += renderTipStack(cfg.stack || cfg.composition);
    html += renderTipBars(cfg.bars || cfg.series);
    if (cfg.body) html += `<div class="tip-body">${esc(cfg.body)}</div>`;
    if (cfg.lines && cfg.lines.length) {
      html += cfg.lines.map(l => `<div class="tip-line">${l}</div>`).join("");
    }
    if (cfg.hint) html += `<div class="tip-hint">${esc(cfg.hint)}</div>`;
    t.innerHTML = html;
    positionTip(x, y);
    t.classList.add("show");
  }

  function positionTip (x, y) {
    if (!tipEl) return;
    const margin = 14;
    const w = tipEl.offsetWidth;
    const h = tipEl.offsetHeight;
    let left = x + margin;
    let top  = y + margin;
    if (left + w > window.innerWidth - 8)  left = x - margin - w;
    if (top  + h > window.innerHeight - 8) top  = y - margin - h;
    if (left < 8) left = 8;
    if (top  < 8) top  = 8;
    tipEl.style.left = left + "px";
    tipEl.style.top  = top + "px";
  }

  function hideTip () {
    clearTipHide();
    if (tipEl) tipEl.classList.remove("show");
    activeTipAnchor = null;
  }

  function scheduleHideTip (delay) {
    clearTipHide();
    hideTimer = setTimeout(hideTip, delay == null ? 140 : delay);
  }

  /**
   * Attach a hover tooltip to one element.
   *   getContent: () => {title, lines:[], hint?}  or string
   */
  function attachTooltip (el, getContent) {
    if (!el || el.dataset.v3TipWired === "1") return;
    el.dataset.v3TipWired = "1";
    el.dataset.v3Interactive = "1";
    el.addEventListener("mouseenter", (e) => {
      const c = typeof getContent === "function" ? getContent(el) : getContent;
      if (!c) return;
      const cfg = (typeof c === "string") ? { title: c } : c;
      showTip(cfg, e.clientX, e.clientY, el);
    });
    el.addEventListener("mousemove", (e) => {
      if (dismissedAnchor && dismissedAnchor === el) return;
      positionTip(e.clientX, e.clientY);
    });
    el.addEventListener("mouseleave", () => {
      if (dismissedAnchor === el) dismissedAnchor = null;
      scheduleHideTip(120);
    });
    el.addEventListener("blur", hideTip);
    el.addEventListener("click", hideTip);   // dismiss on click; drill panel takes over
  }

  function attachTooltipToAll (selector, getContent, root) {
    (root || document).querySelectorAll(selector).forEach(el => attachTooltip(el, getContent));
  }

  window.V3Tooltip = {
    attach: attachTooltip,
    attachAll: attachTooltipToAll,
    show: (cfg, x, y) => showTip(cfg, x, y, null),
    hide: hideTip,
  };

  // ------------------------------------------------------------------
  // DrillPanel
  // ------------------------------------------------------------------
  let panelEl = null;
  let backdropEl = null;
  function ensurePanel () {
    if (panelEl) return panelEl;
    backdropEl = document.createElement("div");
    backdropEl.className = "v3-dp-backdrop";
    backdropEl.addEventListener("click", closePanel);

    panelEl = document.createElement("aside");
    panelEl.className = "v3-dp";
    panelEl.setAttribute("role", "dialog");
    panelEl.setAttribute("aria-label", "chart drill-down");
    panelEl.innerHTML = `
      <div class="head">
        <button class="close-btn" type="button" aria-label="关闭">×</button>
        <span class="stamp" id="v3dp-stamp">Chart · drill</span>
        <h3 id="v3dp-title">—</h3>
        <div class="sub" id="v3dp-sub">—</div>
      </div>
      <div class="body" id="v3dp-body"></div>
    `;
    document.body.appendChild(backdropEl);
    document.body.appendChild(panelEl);
    panelEl.querySelector(".close-btn").addEventListener("click", closePanel);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && panelEl.classList.contains("show")) closePanel();
    });
    return panelEl;
  }

  function openPanel (cfg) {
    ensurePanel();
    document.getElementById("v3dp-stamp").textContent = cfg.stamp || "Chart · drill";
    document.getElementById("v3dp-title").textContent = cfg.title || "—";
    document.getElementById("v3dp-sub").textContent = cfg.sub || "";

    const body = document.getElementById("v3dp-body");
    let html = "";
    if (cfg.summary && cfg.summary.length) {
      html += `<div class="summary-strip">${cfg.summary.map(s =>
        `<div class="cell"><span class="k">${esc(s.k)}</span><span class="v">${esc(s.v)}</span></div>`
      ).join("")}</div>`;
    }
    if (!cfg.rows || !cfg.rows.length) {
      html += `<div class="empty">${esc(cfg.empty || "该切片暂无具体记录")}</div>`;
    } else {
      html += cfg.rows.map(r => {
        const noclick = !r.company_id ? "noclick" : "";
        const dataCid = r.company_id ? `data-company-id="${esc(r.company_id)}"` : "";
        return `
          <div class="row ${noclick}" ${dataCid}>
            <span class="sw" style="--row-color:${r.color || "var(--accent)"}; background:${r.color || "var(--accent)"};"></span>
            <span class="nm">${esc(r.name)}${r.hint ? `<small>${esc(r.hint)}</small>` : ""}</span>
            ${r.badge ? `<span class="badge">${esc(r.badge)}</span>` : ""}
          </div>
        `;
      }).join("");
    }
    body.innerHTML = html;
    body.querySelectorAll(".row[data-company-id]").forEach(row => {
      row.addEventListener("click", () => {
        const cid = row.getAttribute("data-company-id");
        if (cid && window.V3CompanyDetail) window.V3CompanyDetail.show(cid);
      });
    });

    requestAnimationFrame(() => {
      backdropEl.classList.add("show");
      panelEl.classList.add("show");
    });
  }

  function closePanel () {
    if (panelEl) panelEl.classList.remove("show");
    if (backdropEl) backdropEl.classList.remove("show");
  }

  window.V3DrillPanel = {
    __installed: true,
    open: openPanel,
    close: closePanel,
  };

  // ------------------------------------------------------------------
  // Helpers
  // ------------------------------------------------------------------
  function esc (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({
      "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"
    })[ch]);
  }
  function escAttr (s) {
    return String(s == null ? "" : s).replace(/[<>"'`;{}]/g, "");
  }
})();

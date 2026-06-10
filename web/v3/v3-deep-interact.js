/* Shared cross-linking helpers for v3 deep-dive + cross-analysis pivot.
 * Builds "jump to filtered page" affordances so a drilled-into cell can hop
 * to companies.html / topic.html with the filter pre-applied via URL params.
 *
 * window.V3Link
 *   .topicHref(segment)                 -> "./topic.html?segment=ebd"
 *   .companiesHref({track,ownership,ids,q})
 *   .segmentForTrack(trackName)         -> topic segment id or null
 *   .segmentForMaterial(text)           -> topic material segment id or null
 *   .jumpBar(cfg) -> HTMLElement (a row of jump buttons + filter chips)
 */
(function () {
  const TRACK_SEGMENT = {
    EBD: "ebd", Injectables: "injectables", Regenerative: "regenerative",
    Skincare: "skincare", Implants: "implants", Consumables: "consumables",
    Diagnostics: "diagnostics", Surgical: "surgical",
  };
  // material keyword → finer topic segment (server SEGMENT_META keys)
  const MATERIAL_RULES = [
    [/透明质酸|玻尿酸|\bHA\b|skin ?booster|水光/i, "ha"],
    [/PLLA|PDLLA|聚乳酸/i, "plla"],
    [/PCL|聚己内酯|液态|童颜/i, "pcl"],
    [/CaHA|羟基磷灰石|radiesse|harmonyca/i, "caha"],
    [/PN|PDRN|聚核苷酸|polynucleotide/i, "pn_pdrn"],
    [/外泌体|exosome|再生|PRP|PRF/i, "exosome"],
    [/肉毒|botulinum|toxin/i, "botulinum"],
    [/线|thread|埋线|提拉/i, "threads"],
    [/中胚层|mesotherapy|美塑/i, "mesotherapy"],
    [/激光|laser|射频|\bRF\b|超声|HIFU|IPL|光电|能量|microneedl|微针/i, "ebd"],
  ];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, ch =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[ch]));
  }

  const V3Link = {
    TRACK_SEGMENT,
    topicHref(seg) { return "./topic.html?segment=" + encodeURIComponent(seg); },
    segmentForTrack(t) { return TRACK_SEGMENT[t] || null; },
    segmentForMaterial(text) {
      const s = String(text || "");
      for (const [re, seg] of MATERIAL_RULES) if (re.test(s)) return seg;
      return null;
    },
    companiesHref({ track, ownership, ids, q } = {}) {
      const p = new URLSearchParams();
      if (track) p.set("track", track);
      if (ownership) p.set("ownership", ownership);
      if (q) p.set("q", q);
      if (ids && ids.length) p.set("ids", Array.from(new Set(ids.filter(Boolean))).join(","));
      const qs = p.toString();
      return "./companies.html" + (qs ? "?" + qs : "");
    },
    /* cfg: { segment, segmentLabel, track, ownership, ids, count, chips:[{k,v}] } */
    jumpBar(cfg) {
      cfg = cfg || {};
      const bar = document.createElement("div");
      bar.className = "v3-jumpbar";
      const btns = [];
      if (cfg.segment) {
        btns.push(`<a class="v3-jump" href="${esc(this.topicHref(cfg.segment))}">
          <span class="ic">↗</span> 子赛道页 · ${esc(cfg.segmentLabel || cfg.segment)}</a>`);
      }
      const ids = cfg.ids || [];
      const uniq = Array.from(new Set(ids.filter(Boolean)));
      if (uniq.length || cfg.track || cfg.ownership) {
        const href = this.companiesHref({ track: cfg.track, ownership: cfg.ownership, ids: uniq });
        const n = uniq.length || cfg.count || "";
        btns.push(`<a class="v3-jump primary" href="${esc(href)}">
          <span class="ic">☰</span> 公司列表${n ? " · " + n + " 家" : ""}</a>`);
      }
      const chips = (cfg.chips || []).filter(c => c && c.v)
        .map(c => `<span class="v3-jump-chip"><b>${esc(c.k)}</b> ${esc(c.v)}</span>`).join("");
      bar.innerHTML =
        (chips ? `<div class="v3-jump-chips">${chips}</div>` : "") +
        `<div class="v3-jump-btns">${btns.join("")}</div>`;
      return bar;
    },
  };

  window.V3Link = V3Link;
})();

const COMPANY_DATA = window.COMPANY_PROFILE_DATA || { companies: [], summary: {}, letters: {} };

const companyProfiles = Array.isArray(COMPANY_DATA.companies) ? COMPANY_DATA.companies : [];
const bySlug = new Map(companyProfiles.map((item) => [item.slug, item]));
const byName = new Map(companyProfiles.map((item) => [normalizeKey(item.company), item]));

const alphaOrder = ["全部", "#", ..."ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("")];
let activeLetter = "全部";

function $(id) {
  return document.getElementById(id);
}

function normalizeKey(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function fmt(value) {
  const num = Number(value || 0);
  return Number.isFinite(num) ? num.toLocaleString("en-US") : "0";
}

function label(zh, en) {
  return `<span class="bilingual"><span class="bilingual-zh">${escapeHtml(zh)}</span><span class="bilingual-en">${escapeHtml(en)}</span></span>`;
}

function profileHref(profile) {
  return `./company-profile.html?company=${encodeURIComponent(profile.company)}`;
}

function companyInitials(profile) {
  const words = String(profile.company || "")
    .replace(/[^A-Za-z0-9\s]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return "#";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 2).map((word) => word[0]).join("").toUpperCase();
}

function renderCompanyLogo(profile, className) {
  const logo = profile.media?.logo || "";
  const initials = companyInitials(profile);
  return `
    <span class="${className} company-logo-mark ${logo ? "has-logo" : "is-placeholder"}" aria-hidden="true">
      ${logo ? `<img src="${escapeHtml(logo)}" alt="" />` : `<span>${escapeHtml(initials)}</span>`}
    </span>
  `;
}

function compactText(value, fallback = "-") {
  const text = String(value || "").trim();
  return text || fallback;
}

function topPairs(pairs, limit = 8) {
  return (Array.isArray(pairs) ? pairs : []).filter(([name]) => name && name !== "Unknown").slice(0, limit);
}

function heatColor(value, max) {
  if (!value || !max) return { bg: "#eef6fc", dark: false };
  const palette = ["#e7f3fb", "#cde7f8", "#aad4f0", "#80bee8", "#57a5dc", "#2d87c6", "#1769a7", "#0c4a7d"];
  let usable = palette.length;
  if (max <= 1) usable = 2;
  else if (max <= 3) usable = 3;
  else if (max <= 8) usable = 5;
  else if (max <= 20) usable = 6;
  const index = Math.max(0, Math.min(usable - 1, Math.ceil((value / max) * usable) - 1));
  return { bg: palette[index], dark: index >= 5 };
}

function splitBilingualSlash(value) {
  const text = String(value || "").trim();
  if (!text.includes("/")) return `<strong>${escapeHtml(text)}</strong>`;
  const [zh, ...rest] = text.split("/");
  return `<strong>${escapeHtml(zh.trim())}</strong><em>${escapeHtml(rest.join("/").trim())}</em>`;
}

function initDirectory() {
  const summaryNode = $("companyProfileSummary");
  const alphabetNode = $("companyAlphabet");
  const listNode = $("companyProfileList");
  if (!summaryNode || !alphabetNode || !listNode) return;

  const summary = COMPANY_DATA.summary || {};
  summaryNode.innerHTML = [
    ["企业", "Companies", summary.companies],
    ["已生成介绍", "Profiles Ready", summary.briefing_ready],
    ["含 Logo", "With Logos", summary.with_logos || 0],
    ["复杂组合", "Complex Portfolios", summary.complex_portfolios],
  ]
    .map(
      ([zh, en, value]) => `
        <article class="profile-stat-card">
          <span>${label(zh, en)}</span>
          <strong>${fmt(value)}</strong>
        </article>
      `,
    )
    .join("");

  alphabetNode.innerHTML = alphaOrder
    .map((letter) => {
      const count = letter === "全部" ? companyProfiles.length : COMPANY_DATA.letters?.[letter] || 0;
      return `<button class="${letter === activeLetter ? "active" : ""}" data-letter="${escapeHtml(letter)}">${escapeHtml(letter)}<span>${fmt(count)}</span></button>`;
    })
    .join("");

  alphabetNode.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-letter]");
    if (!button) return;
    activeLetter = button.dataset.letter || "全部";
    initDirectory();
  });

  const filtered = companyProfiles.filter((profile) => activeLetter === "全部" || profile.letter === activeLetter);
  const grouped = filtered.reduce((acc, profile) => {
    const letter = profile.letter || "#";
    if (!acc[letter]) acc[letter] = [];
    acc[letter].push(profile);
    return acc;
  }, {});
  const letters = Object.keys(grouped).sort((a, b) => alphaOrder.indexOf(a) - alphaOrder.indexOf(b));

  listNode.innerHTML = letters
    .map(
      (letter) => `
        <section class="profile-letter-section">
          <div class="profile-letter-head"><strong>${escapeHtml(letter)}</strong><span>${fmt(grouped[letter].length)}</span></div>
          <div class="profile-card-grid">
            ${grouped[letter].map(renderDirectoryCard).join("")}
          </div>
        </section>
      `,
    )
    .join("");
}

function renderDirectoryCard(profile) {
  const hasImage = profile.media?.covers?.length || profile.media?.products?.length;
  const hasLogo = Boolean(profile.media?.logo);
  const badge = profile.briefing_ready ? "A-Z" : profile.portfolio_complex ? "Matrix" : "";
  return `
    <a class="company-directory-card ${hasImage ? "has-media" : ""} ${hasLogo ? "has-logo" : ""}" href="${profileHref(profile)}">
      <div class="company-card-head">
        ${renderCompanyLogo(profile, "company-card-logo")}
        <div class="company-card-title">
          <span class="company-card-kicker">${escapeHtml(profile.primary_track || profile.region || "Company")}</span>
          <h3>${escapeHtml(profile.company)}</h3>
          <p>${escapeHtml([profile.country, profile.region].filter(Boolean).join(" · ") || profile.location || "")}</p>
        </div>
      </div>
      <div class="company-card-bottom">
        <span>${fmt(profile.product_count)} ${escapeHtml(profile.product_count === 1 ? "line" : "lines")}</span>
        ${badge ? `<em>${escapeHtml(badge)}</em>` : ""}
      </div>
    </a>
  `;
}

function findProfileFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const raw = params.get("company") || params.get("slug") || "";
  const decoded = decodeURIComponent(raw).trim();
  if (!decoded) return byName.get("skintech") || companyProfiles[0];
  return bySlug.get(decoded) || byName.get(normalizeKey(decoded)) || companyProfiles.find((item) => item.company === decoded);
}

function initProfilePage() {
  const root = $("companyProfilePage");
  if (!root) return;
  const profile = findProfileFromUrl();
  if (!profile) {
    root.innerHTML = `<section class="card lift empty-state"><h1>${label("未找到公司", "Company Not Found")}</h1><a href="./company-profiles.html">${label("返回公司介绍库", "Back to Company Profiles")}</a></section>`;
    return;
  }
  document.title = `${profile.company} | Company Profile`;
  root.innerHTML = `
    ${renderCompanyHero(profile)}
    ${renderCompanyFacts(profile)}
    ${renderCompanyPortfolio(profile)}
    ${renderCompanyProducts(profile)}
  `;
}

function renderCompanyHero(profile) {
  const cover = profile.media?.covers?.[0] || profile.media?.products?.[0] || "";
  const gallery = (profile.media?.products || []).slice(0, 5);
  const intro = profile.intro || {};
  return `
    <section class="company-detail-hero">
      <div class="company-detail-copy">
        <div class="company-detail-brand-row">
          ${renderCompanyLogo(profile, "company-hero-logo")}
          <div class="company-detail-title">
            <div class="eyebrow">${escapeHtml(profile.letter)} · 2026</div>
            <h1>${escapeHtml(profile.company)}</h1>
          </div>
        </div>
        <p class="profile-intro"><span>${escapeHtml(intro.zh || "")}</span><span>${escapeHtml(intro.en || "")}</span></p>
        <div class="profile-chip-row">
          ${profile.briefing_ready ? `<span>${label("专栏已生成", "Column Ready")}</span>` : ""}
          ${profile.portfolio_complex ? `<span>${label("组合分析", "Portfolio Analysis")}</span>` : ""}
          ${profile.stock_code ? `<span>${escapeHtml(profile.stock_code)}</span>` : ""}
        </div>
      </div>
      <div class="company-detail-media">
        ${
          cover
            ? `<img class="company-cover-image" src="${escapeHtml(cover)}" alt="${escapeHtml(profile.company)}" />`
            : `<div class="company-cover-placeholder">${escapeHtml(profile.primary_track || "Company")}</div>`
        }
        ${gallery.length ? `<div class="company-image-strip">${gallery.map((src) => `<img src="${escapeHtml(src)}" alt="" />`).join("")}</div>` : ""}
      </div>
    </section>
  `;
}

function renderCompanyFacts(profile) {
  const facts = [
    ["国家/地区", "Country / Region", [profile.country, profile.region].filter(Boolean).join(" · ")],
    ["城市", "Location", profile.location],
    ["主赛道", "Primary Track", profile.primary_track],
    ["产品线", "Product Lines", profile.product_count],
    ["品牌数", "Brands", profile.brand_count],
    ["企业属性", "Ownership", profile.ownership],
    ["业务角色", "Business Role", profile.business_role],
    ["母公司", "Parent Company", profile.parent_company],
  ].filter(([, , value]) => value !== "" && value !== undefined && value !== null);
  return `
    <section class="company-fact-grid">
      ${facts
        .map(
          ([zh, en, value]) => `
          <article class="company-fact-card">
            <span>${label(zh, en)}</span>
            <strong>${escapeHtml(value)}</strong>
          </article>
        `,
        )
        .join("")}
    </section>
  `;
}

function renderCompanyPortfolio(profile) {
  const products = profile.products || [];
  if (!products.length) return "";
  const trackPairs = topPairs(profile.summary?.tracks, 8);
  const formPairs = topPairs(profile.summary?.forms, 12);
  return `
    <section class="company-profile-section">
      <div class="section-head split-head">
        <h2>${label("产品组合", "Product Portfolio")}</h2>
        <a class="ghost-link" href="./company-profiles.html">${label("公司目录", "Directory")}</a>
      </div>
      <div class="profile-track-strip">
        ${trackPairs.map(([name, count]) => `<span>${escapeHtml(name)}<strong>${fmt(count)}</strong></span>`).join("")}
      </div>
      ${
        profile.portfolio_complex
          ? renderBrandFormHeatmap(profile)
          : `<div class="simple-portfolio-note">${label("产品线较集中，保留产品卡片视图", "Focused portfolio, shown as product cards")}</div>`
      }
      <div class="profile-form-grid">
        ${formPairs
          .map(([name, count]) => {
            const heat = heatColor(count, formPairs[0]?.[1] || count);
            return `<div class="profile-form-tile ${heat.dark ? "dark" : ""}" style="--heat-bg:${heat.bg}">${splitBilingualSlash(name)}<span>${fmt(count)}</span></div>`;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderBrandFormHeatmap(profile) {
  const products = profile.products || [];
  const rows = topNames(products, "brand", 14);
  const cols = topNames(products, "category_l2", 10);
  if (!rows.length || !cols.length) return "";
  const counts = new Map();
  let max = 0;
  products.forEach((product) => {
    const row = compactText(product.brand, "Unknown");
    const col = compactText(product.category_l2, "Unknown");
    if (!rows.includes(row) || !cols.includes(col)) return;
    const key = `${row}||${col}`;
    const next = (counts.get(key) || 0) + 1;
    counts.set(key, next);
    max = Math.max(max, next);
  });
  return `
    <div class="company-heatmap-card">
      <div class="company-heatmap-title">${label("品牌 × 产品形态", "Brand x Product Form")}</div>
      <div class="company-mini-heatmap" style="--cols:${cols.length}">
        <div class="company-heat-corner">${label("品牌", "Brand")}</div>
        ${cols.map((col) => `<div class="company-heat-head">${splitBilingualSlash(col)}</div>`).join("")}
        ${rows
          .map((row) => {
            const rowTotal = cols.reduce((sum, col) => sum + (counts.get(`${row}||${col}`) || 0), 0);
            return `
              <div class="company-heat-row-head"><strong>${escapeHtml(row)}</strong><span>${fmt(rowTotal)}</span></div>
              ${cols
                .map((col) => {
                  const value = counts.get(`${row}||${col}`) || 0;
                  const heat = heatColor(value, max);
                  return `<div class="company-heat-cell ${value ? "has-value" : ""} ${heat.dark ? "dark" : ""}" style="--heat-bg:${heat.bg}" title="${escapeHtml(`${row} / ${col} / ${value}`)}">${value ? fmt(value) : ""}</div>`;
                })
                .join("")}
            `;
          })
          .join("")}
      </div>
    </div>
  `;
}

function topNames(products, field, limit) {
  const counts = new Counter();
  products.forEach((product) => counts.add(compactText(product[field], "Unknown")));
  return counts.entries().filter(([name]) => name !== "Unknown").slice(0, limit).map(([name]) => name);
}

class Counter {
  constructor() {
    this.map = new Map();
  }
  add(key) {
    this.map.set(key, (this.map.get(key) || 0) + 1);
  }
  entries() {
    return Array.from(this.map.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }
}

function renderCompanyProducts(profile) {
  const products = (profile.products || []).slice(0, 36);
  if (!products.length) return "";
  const images = profile.media?.products || [];
  return `
    <section class="company-profile-section">
      <div class="section-head">
        <h2>${label("核心产品线", "Product Lines")}</h2>
      </div>
      <div class="company-product-grid">
        ${products
          .map((product, index) => {
            const image = images[index % images.length];
            return `
              <article class="company-product-card ${image ? "" : "no-image"}">
                ${image ? `<img src="${escapeHtml(image)}" alt="" />` : ""}
                <div>
                  <span>${escapeHtml(product.category_l2 || product.category_l1 || "Product")}</span>
                  <h3>${escapeHtml(product.brand || product.core_product || "Product")}</h3>
                  <p>${escapeHtml(product.core_product || product.tech_type_std || "")}</p>
                  <div class="product-meta-row">
                    ${product.tech_type_std ? `<em>${escapeHtml(product.tech_type_std)}</em>` : ""}
                    ${product.ce_status ? `<em>CE</em>` : ""}
                    ${product.fda_510k_number ? `<em>FDA</em>` : ""}
                  </div>
                </div>
              </article>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

document.addEventListener("DOMContentLoaded", () => {
  initDirectory();
  initProfilePage();
});

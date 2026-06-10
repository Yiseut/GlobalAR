/* Shared topbar + left rail · v2 dashboard
 * Usage:  <div id="topbar"></div>  <aside id="rail"></aside>
 *         <script src="./_nav.js" data-active="overview"></script>
 */
(function () {
  const script = document.currentScript;
  const active = script && script.dataset && script.dataset.active;

  const topNav = [
    { id: "overview",  href: "./index.html",            zh: "总览",    en: "Overview" },
    { id: "tracks",    href: "./tracks.html",           zh: "赛道",    en: "Tracks" },
    { id: "regulatory",href: "./regulatory-pulse.html", zh: "监管脉搏",en: "Regulatory" },
    { id: "capital",   href: "./capital-map.html",      zh: "资本地图",en: "Capital" },
    { id: "geo",       href: "./geo-deep-dive.html",    zh: "地域深掘",en: "Geo" },
    { id: "companies", href: "./companies.html",        zh: "公司",    en: "Companies" },
    { id: "evidence",  href: "./evidence.html",         zh: "证据库",  en: "Evidence" },
  ];

  const railSections = [
    {
      title: "情报视角",
      en: "INTELLIGENCE LENSES",
      items: [
        { id: "overview",       href: "./index.html",            zh: "总览",     count: null },
        { id: "tracks",         href: "./tracks.html",           zh: "赛道结构", count: "10 L1" },
        { id: "regulatory",     href: "./regulatory-pulse.html", zh: "监管脉搏", count: "411" },
        { id: "capital",        href: "./capital-map.html",      zh: "资本地图", count: "61" },
        { id: "geo",            href: "./geo-deep-dive.html",    zh: "地域深掘", count: "38 国" },
      ],
    },
    {
      title: "企业与证据",
      en: "COMPANY & EVIDENCE",
      items: [
        { id: "companies", href: "./companies.html",        zh: "公司列表",  count: "372" },
        { id: "indications", href: "./indications.html",    zh: "适应症星图", count: "958" },
        { id: "technology",  href: "./technology-tree.html",zh: "技术树",     count: "—" },
        { id: "evidence",    href: "./evidence.html",       zh: "证据库",     count: "19,992" },
      ],
    },
    {
      title: "子赛道",
      en: "L1 SUB-TRACKS",
      items: [
        { id: "topic-ebd",          href: "./topic.html?segment=ebd",         zh: "光电 EBD",        count: "480" },
        { id: "topic-injectables",  href: "./topic.html?segment=injectables", zh: "注射 Injectables",count: "328" },
        { id: "topic-regenerative", href: "./topic.html?segment=regenerative",zh: "再生 Regen",      count: "28" },
        { id: "topic-skincare",     href: "./topic.html?segment=skincare",    zh: "护肤 Skincare",   count: "79" },
      ],
    },
  ];

  // —— render topbar ——
  const topbar = document.getElementById("topbar");
  if (topbar) {
    topbar.className = "topbar";
    topbar.innerHTML = `
      <a class="brand" href="./index.html">
        <span class="seal">研</span>
        <span>全球医美情报</span>
        <small>Aesthetic Reflections</small>
      </a>
      <nav aria-label="主导航">
        ${topNav.map(item => `
          <a href="${item.href}" class="${item.id === active ? "active" : ""}">
            <span>${item.zh}</span>
          </a>
        `).join("")}
      </nav>
    `;
  }

  // —— render left rail ——
  const rail = document.getElementById("rail");
  if (rail) {
    rail.className = "rail";
    rail.innerHTML = railSections.map(sec => `
      <div class="rail-section">
        <div class="rail-section-title">${sec.title}</div>
        ${sec.items.map(item => `
          <a href="${item.href}" class="${item.id === active ? "active" : ""}">
            <span>${item.zh}</span>
            ${item.count ? `<small>${item.count}</small>` : ""}
          </a>
        `).join("")}
      </div>
    `).join("");
  }
})();

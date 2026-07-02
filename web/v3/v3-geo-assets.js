(function () {
  const FLAGS = {
  "Albania": "assets/geo/flags/albania.png",
  "Algeria": "assets/geo/flags/algeria.png",
  "Angola": "assets/geo/flags/angola.png",
  "Argentina": "assets/geo/flags/argentina.png",
  "Armenia": "assets/geo/flags/armenia.png",
  "Australia": "assets/geo/flags/australia.png",
  "Austria": "assets/geo/flags/austria.png",
  "Azerbaijan": "assets/geo/flags/azerbaijan.png",
  "Bahrain": "assets/geo/flags/bahrain.png",
  "Bangladesh": "assets/geo/flags/bangladesh.png",
  "Belgium": "assets/geo/flags/belgium.png",
  "Bolivia": "assets/geo/flags/bolivia.png",
  "Brazil": "assets/geo/flags/brazil.png",
  "Bulgaria": "assets/geo/flags/bulgaria.png",
  "Burkina Faso": "assets/geo/flags/burkina-faso.png",
  "Cambodia": "assets/geo/flags/cambodia.png",
  "Cameroon": "assets/geo/flags/cameroon.png",
  "Canada": "assets/geo/flags/canada.png",
  "Chad": "assets/geo/flags/chad.png",
  "Chile": "assets/geo/flags/chile.png",
  "China": "assets/geo/flags/china.png",
  "Colombia": "assets/geo/flags/colombia.png",
  "Costa Rica": "assets/geo/flags/costa-rica.png",
  "Cote d'Ivoire": "assets/geo/flags/cote-d-ivoire.png",
  "Croatia": "assets/geo/flags/croatia.png",
  "Cuba": "assets/geo/flags/cuba.png",
  "Cyprus": "assets/geo/flags/cyprus.png",
  "Czech Republic": "assets/geo/flags/czech-republic.png",
  "Democratic Republic of the Congo": "assets/geo/flags/democratic-republic-of-the-congo.png",
  "Denmark": "assets/geo/flags/denmark.png",
  "Dominican Republic": "assets/geo/flags/dominican-republic.png",
  "Ecuador": "assets/geo/flags/ecuador.png",
  "Egypt": "assets/geo/flags/egypt.png",
  "El Salvador": "assets/geo/flags/el-salvador.png",
  "Estonia": "assets/geo/flags/estonia.png",
  "Ethiopia": "assets/geo/flags/ethiopia.png",
  "Finland": "assets/geo/flags/finland.png",
  "France": "assets/geo/flags/france.png",
  "Georgia": "assets/geo/flags/georgia.png",
  "Germany": "assets/geo/flags/germany.png",
  "Ghana": "assets/geo/flags/ghana.png",
  "Greece": "assets/geo/flags/greece.png",
  "Guatemala": "assets/geo/flags/guatemala.png",
  "Guyana": "assets/geo/flags/guyana.png",
  "Haiti": "assets/geo/flags/haiti.png",
  "Honduras": "assets/geo/flags/honduras.png",
  "Hungary": "assets/geo/flags/hungary.png",
  "Iceland": "assets/geo/flags/iceland.png",
  "India": "assets/geo/flags/india.png",
  "Indonesia": "assets/geo/flags/indonesia.png",
  "Iran": "assets/geo/flags/iran.png",
  "Iraq": "assets/geo/flags/iraq.png",
  "Ireland": "assets/geo/flags/ireland.png",
  "Israel": "assets/geo/flags/israel.png",
  "Italy": "assets/geo/flags/italy.png",
  "Jamaica": "assets/geo/flags/jamaica.png",
  "Japan": "assets/geo/flags/japan.png",
  "Jordan": "assets/geo/flags/jordan.png",
  "Kazakhstan": "assets/geo/flags/kazakhstan.png",
  "Kenya": "assets/geo/flags/kenya.png",
  "Kyrgyzstan": "assets/geo/flags/kyrgyzstan.png",
  "Laos": "assets/geo/flags/laos.png",
  "Latvia": "assets/geo/flags/latvia.png",
  "Lithuania": "assets/geo/flags/lithuania.png",
  "Madagascar": "assets/geo/flags/madagascar.png",
  "Malaysia": "assets/geo/flags/malaysia.png",
  "Mali": "assets/geo/flags/mali.png",
  "Mexico": "assets/geo/flags/mexico.png",
  "Moldova": "assets/geo/flags/moldova.png",
  "Montenegro": "assets/geo/flags/montenegro.png",
  "Morocco": "assets/geo/flags/morocco.png",
  "Mozambique": "assets/geo/flags/mozambique.png",
  "Myanmar": "assets/geo/flags/myanmar.png",
  "Nepal": "assets/geo/flags/nepal.png",
  "Netherlands": "assets/geo/flags/netherlands.png",
  "New Zealand": "assets/geo/flags/new-zealand.png",
  "Nicaragua": "assets/geo/flags/nicaragua.png",
  "Niger": "assets/geo/flags/niger.png",
  "Nigeria": "assets/geo/flags/nigeria.png",
  "North Korea": "assets/geo/flags/north-korea.png",
  "Norway": "assets/geo/flags/norway.png",
  "Oman": "assets/geo/flags/oman.png",
  "Pakistan": "assets/geo/flags/pakistan.png",
  "Panama": "assets/geo/flags/panama.png",
  "Papua New Guinea": "assets/geo/flags/papua-new-guinea.png",
  "Paraguay": "assets/geo/flags/paraguay.png",
  "Peru": "assets/geo/flags/peru.png",
  "Philippines": "assets/geo/flags/philippines.png",
  "Poland": "assets/geo/flags/poland.png",
  "Portugal": "assets/geo/flags/portugal.png",
  "Qatar": "assets/geo/flags/qatar.png",
  "Romania": "assets/geo/flags/romania.png",
  "Russia": "assets/geo/flags/russia.png",
  "Saudi Arabia": "assets/geo/flags/saudi-arabia.png",
  "Senegal": "assets/geo/flags/senegal.png",
  "Serbia": "assets/geo/flags/serbia.png",
  "Singapore": "assets/geo/flags/singapore.png",
  "Slovakia": "assets/geo/flags/slovakia.png",
  "Slovenia": "assets/geo/flags/slovenia.png",
  "South Africa": "assets/geo/flags/south-africa.png",
  "South Korea": "assets/geo/flags/south-korea.png",
  "Spain": "assets/geo/flags/spain.png",
  "Sri Lanka": "assets/geo/flags/sri-lanka.png",
  "Sudan": "assets/geo/flags/sudan.png",
  "Suriname": "assets/geo/flags/suriname.png",
  "Sweden": "assets/geo/flags/sweden.png",
  "Switzerland": "assets/geo/flags/switzerland.png",
  "Syria": "assets/geo/flags/syria.png",
  "Tajikistan": "assets/geo/flags/tajikistan.png",
  "Tanzania": "assets/geo/flags/tanzania.png",
  "Thailand": "assets/geo/flags/thailand.png",
  "Turkey": "assets/geo/flags/turkey.png",
  "Turkmenistan": "assets/geo/flags/turkmenistan.png",
  "Uganda": "assets/geo/flags/uganda.png",
  "Ukraine": "assets/geo/flags/ukraine.png",
  "United Kingdom": "assets/geo/flags/united-kingdom.png",
  "United States": "assets/geo/flags/united-states.png",
  "Uruguay": "assets/geo/flags/uruguay.png",
  "Uzbekistan": "assets/geo/flags/uzbekistan.png",
  "Venezuela": "assets/geo/flags/venezuela.png",
  "Vietnam": "assets/geo/flags/vietnam.png",
  "Yemen": "assets/geo/flags/yemen.png",
  "Zambia": "assets/geo/flags/zambia.png"
};
  const MAPS = {
  "world": "assets/geo/maps/world.svg",
  "asia": "assets/geo/maps/asia.svg",
  "europe": "assets/geo/maps/europe.svg",
  "africa": "assets/geo/maps/africa.svg",
  "north-america": "assets/geo/maps/north-america.svg",
  "south-america": "assets/geo/maps/south-america.svg",
  "oceania": "assets/geo/maps/oceania.svg",
  "continents": "assets/geo/maps/continents.svg"
};
  const ALIASES = {
  "US": "United States",
  "USA": "United States",
  "United States of America": "United States",
  "UK": "United Kingdom",
  "Britain": "United Kingdom",
  "Great Britain": "United Kingdom",
  "Korea": "South Korea",
  "Republic of Korea": "South Korea",
  "Korea, Republic of": "South Korea",
  "Chinese Taipei": "Taiwan",
  "Czechia": "Czech Republic",
  "Turkiye": "Turkey",
  "UAE": "United Arab Emirates",
  "Cote d’Ivoire": "Cote d'Ivoire",
  "Côte d'Ivoire": "Cote d'Ivoire",
  "Democratic Republic Congo": "Democratic Republic of the Congo"
};

  function esc(value) {
    return String(value || "").replace(/[&<>"']/g, ch => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[ch]);
  }

  function canonicalCountry(value) {
    const text = String(value || "").trim();
    return ALIASES[text] || text;
  }

  function flagUrl(country) {
    const key = canonicalCountry(country);
    return FLAGS[key] || null;
  }

  function flagHTML(country, className) {
    const url = flagUrl(country);
    if (!url) return "";
    const label = canonicalCountry(country);
    const cls = className || "geo-flag";
    return `<img class="${esc(cls)}" src="${esc(url)}" alt="${esc(label)} flag" loading="lazy" decoding="async">`;
  }

  function mapUrl(key) {
    return MAPS[key] || null;
  }

  window.V3_GEO_ASSETS = { flags: FLAGS, maps: MAPS, aliases: ALIASES, canonicalCountry, flagUrl, flagHTML, mapUrl };
})();

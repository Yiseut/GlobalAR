import {dashboardUrl} from "./utils.mjs";
import {loadPlaywright} from "./load-playwright.mjs";

const fail = (message, details = {}) => {
  console.error(JSON.stringify({ok: false, message, ...details}, null, 2));
  process.exit(1);
};

const response = await fetch(`${dashboardUrl}?video-preflight=${Date.now()}`).catch((error) => {
  fail("Dashboard URL is not reachable", {url: dashboardUrl, error: error.message});
});

if (!response.ok) {
  fail("Dashboard returned a non-200 response", {url: dashboardUrl, status: response.status});
}

const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless: true});
const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await page.goto(`${dashboardUrl}?video-preflight=${Date.now()}`, {waitUntil: "domcontentloaded", timeout: 45000});
  await page.waitForLoadState("networkidle", {timeout: 18000}).catch(() => {});
  await page.waitForSelector("#leafletGeoMap", {timeout: 15000});
  await page.waitForFunction(() => {
    const tracks = document.querySelector("#geoTrackFilter");
    const regions = document.querySelector("#geoRegionFilter");
    const dots = document.querySelectorAll(".leaflet-company-dot, .geo-point").length;
    return tracks?.querySelector('option[value="Injectables"]') && regions?.querySelector('option[value="Asia-Pacific"]') && dots > 20;
  }, {timeout: 20000});

  const info = await page.evaluate(() => ({
    title: document.title,
    kpiProducts: document.querySelector("#kpiProducts")?.textContent?.trim(),
    kpiCompanies: document.querySelector("#kpiCompanies")?.textContent?.trim(),
    dots: document.querySelectorAll(".leaflet-company-dot, .geo-point").length,
    hasSouthKorea: Boolean(typeof currentCountryAggregate === "function" && currentCountryAggregate("South Korea")),
    mapRect: (() => {
      const rect = document.querySelector("#geoMapStage")?.getBoundingClientRect();
      return rect ? {width: Math.round(rect.width), height: Math.round(rect.height)} : null;
    })(),
  }));

  if (!info.hasSouthKorea) {
    fail("South Korea drilldown target is unavailable under current data", {info});
  }
  if (errors.length) {
    console.warn(JSON.stringify({ok: true, warning: "Console errors were observed", errors: errors.slice(0, 8)}, null, 2));
  }
  console.log(JSON.stringify({ok: true, url: dashboardUrl, info}, null, 2));
} finally {
  await browser.close();
}

import {loadPlaywright} from "./load-playwright.mjs";
import {dashboardUrl} from "./utils.mjs";
import {installTextureRoutes, installV3VideoHooks, scrollToGlobe, waitForGlobeReady} from "./browser-helpers.mjs";

const fail = (message, details = {}) => {
  console.error(JSON.stringify({ok: false, message, ...details}, null, 2));
  process.exit(1);
};

const response = await fetch(`${dashboardUrl}?video-preflight=${Date.now()}`).catch((error) => {
  fail("Dashboard URL is not reachable", {url: dashboardUrl, error: error.message});
});
if (!response.ok) fail("Dashboard returned a non-200 response", {url: dashboardUrl, status: response.status});

const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless: true});
const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});

try {
  await installTextureRoutes(page);
  await installV3VideoHooks(page);
  await page.goto(`${dashboardUrl}?video-preflight=${Date.now()}`, {waitUntil: "domcontentloaded", timeout: 70000});
  await waitForGlobeReady(page);
  await scrollToGlobe(page);
  await page.waitForTimeout(1200);

  const before = await page.screenshot({type: "png", timeout: 0});
  await page.waitForTimeout(1600);
  const after = await page.screenshot({type: "png", timeout: 0});
  let diff = 0;
  for (let i = 0; i < Math.min(before.length, after.length); i += 137) {
    if (before[i] !== after[i]) diff += 1;
  }

  await page.evaluate(() => window.__videoShowCountryDrawer("United States of America"));
  await page.waitForSelector("#countryDrawer.show", {timeout: 12000});
  const allerganRows = await page.locator("#countryDrawer .drawer-list .row", {hasText: "Allergan"}).count();
  if (!allerganRows) fail("Allergan row is missing in the USA country drawer.");

  const info = await page.evaluate(() => {
    const companies = window.__videoAllCompanies || [];
    const usa = companies.filter((c) => c.country === "USA");
    const countries = new Set(companies.map((c) => c.country));
    const cities = new Set(companies.map((c) => `${c.city}|${c.country}`));
    const allergan = companies.find((c) => c.company === "Allergan");
    return {
      title: document.title,
      companies: companies.length,
      countries: countries.size,
      cities: cities.size,
      usaCompanies: usa.length,
      usaProducts: usa.reduce((sum, c) => sum + (c.products || 0), 0),
      usaCities: new Set(usa.map((c) => c.city)).size,
      allergan,
      canvas: Boolean(document.querySelector("#globe-stage canvas")),
    };
  });

  if (diff < 25) fail("Globe rotation/cloud movement was not visually detectable.", {diff, info});
  if (info.companies !== 366 || info.countries !== 37 || info.cities !== 196) {
    fail("Current page data does not match the locked narration scope.", {info});
  }

  console.log(JSON.stringify({ok: true, url: dashboardUrl, rotationDiff: diff, info, warnings: errors.slice(0, 6)}, null, 2));
} finally {
  await browser.close();
}

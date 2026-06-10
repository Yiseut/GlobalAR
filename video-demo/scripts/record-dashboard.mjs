import fs from "node:fs/promises";
import path from "node:path";
import {dashboardUrl, recordingPath} from "./utils.mjs";
import {loadPlaywright} from "./load-playwright.mjs";

const WIDTH = 1920;
const HEIGHT = 1080;

const ensureDir = async (filePath) => {
  await fs.mkdir(path.dirname(filePath), {recursive: true});
};

const timed = () => {
  const started = Date.now();
  return {
    elapsed: () => (Date.now() - started) / 1000,
    waitUntil: async (seconds) => {
      const wait = Math.max(0, seconds * 1000 - (Date.now() - started));
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));
    },
  };
};

const injectPresenterLayer = async (page) => {
  await page.evaluate(() => {
    const style = document.createElement("style");
    style.id = "videoDemoPresenterStyles";
    style.textContent = `
      #videoDemoCursor {
        position: fixed;
        z-index: 2147483000;
        left: 0;
        top: 0;
        width: 30px;
        height: 30px;
        margin-left: -15px;
        margin-top: -15px;
        border-radius: 999px;
        border: 2px solid rgba(255,255,255,0.96);
        background: rgba(217,119,87,0.86);
        box-shadow: 0 10px 28px rgba(31,27,23,0.26), 0 0 0 7px rgba(217,119,87,0.14);
        pointer-events: none;
        transform: translate(1560px, 210px) scale(0.86);
        transition: transform 700ms cubic-bezier(.16, 1, .3, 1), opacity 300ms ease;
      }
      .videoDemoPulse {
        position: fixed;
        z-index: 2147482999;
        width: 28px;
        height: 28px;
        margin-left: -14px;
        margin-top: -14px;
        border-radius: 999px;
        border: 2px solid rgba(217,119,87,0.78);
        pointer-events: none;
        animation: videoDemoPulse 850ms cubic-bezier(.16, 1, .3, 1) forwards;
      }
      @keyframes videoDemoPulse {
        from { opacity: .9; transform: scale(.7); }
        to { opacity: 0; transform: scale(4.2); }
      }
    `;
    document.head.appendChild(style);
    const cursor = document.createElement("div");
    cursor.id = "videoDemoCursor";
    document.body.appendChild(cursor);
    window.__videoDemoMoveCursor = ({x, y, duration = 700, scale = 1}) => {
      cursor.style.transitionDuration = `${duration}ms, 300ms`;
      cursor.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
    };
    window.__videoDemoPulse = ({x, y}) => {
      const pulse = document.createElement("div");
      pulse.className = "videoDemoPulse";
      pulse.style.left = `${x}px`;
      pulse.style.top = `${y}px`;
      document.body.appendChild(pulse);
      window.setTimeout(() => pulse.remove(), 900);
    };
  });
};

const moveCursor = async (page, x, y, duration = 700, scale = 1) => {
  await page.evaluate((payload) => window.__videoDemoMoveCursor?.(payload), {x, y, duration, scale});
  await page.waitForTimeout(duration + 60);
};

const pulse = async (page, x, y) => {
  await page.evaluate((payload) => window.__videoDemoPulse?.(payload), {x, y});
};

const smoothScrollToMap = async (page) => {
  await page.evaluate(() => {
    const map = document.querySelector(".global-map-stage");
    const topbar = document.querySelector(".topbar")?.getBoundingClientRect().height || 0;
    const target = map ? map.getBoundingClientRect().top + window.scrollY - topbar - 32 : 520;
    window.scrollTo({top: Math.max(0, target), behavior: "smooth"});
  });
};

const selectValue = async (page, selector, value, cursorX, cursorY) => {
  await moveCursor(page, cursorX, cursorY, 520, 1);
  await pulse(page, cursorX, cursorY);
  await page.selectOption(selector, value);
  await page.waitForTimeout(900);
};

const flyTo = async (page, lat, lng, zoom, duration = 1.6) => {
  await page.evaluate(({lat, lng, zoom, duration}) => {
    try {
      if (typeof geoLeafletMap !== "undefined" && geoLeafletMap) {
        geoLeafletMap.flyTo([lat, lng], zoom, {duration});
      }
    } catch {
      // The recording remains useful even if Leaflet flyTo is unavailable.
    }
  }, {lat, lng, zoom, duration});
};

const openCountry = async (page, country) => {
  await page.evaluate((countryName) => {
    const target = typeof currentCountryAggregate === "function" ? currentCountryAggregate(countryName) : null;
    if (!target) throw new Error(`No country aggregate for ${countryName}`);
    openGeoCountry(target);
  }, country);
  await page.waitForSelector(".country-detail-shell", {timeout: 12000});
};

await ensureDir(recordingPath);
await fs.rm(recordingPath, {force: true});

const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless: true});
const context = await browser.newContext({
  viewport: {width: WIDTH, height: HEIGHT},
  deviceScaleFactor: 1,
  recordVideo: {
    dir: path.dirname(recordingPath),
    size: {width: WIDTH, height: HEIGHT},
  },
});
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") pageErrors.push(message.text());
});

try {
  await page.goto(`${dashboardUrl}?video-record=${Date.now()}`, {waitUntil: "domcontentloaded", timeout: 45000});
  await page.waitForLoadState("networkidle", {timeout: 18000}).catch(() => {});
  await page.waitForFunction(() => document.querySelectorAll(".leaflet-company-dot, .geo-point").length > 20, {timeout: 20000});
  await injectPresenterLayer(page);

  const clock = timed();
  await moveCursor(page, 1510, 198, 480, 0.86);
  await clock.waitUntil(3.2);
  await moveCursor(page, 815, 385, 1000, 0.9);
  await clock.waitUntil(6.0);
  await smoothScrollToMap(page);

  await clock.waitUntil(9.2);
  await moveCursor(page, 1045, 800, 1200, 0.88);
  await clock.waitUntil(14.4);
  await moveCursor(page, 1510, 763, 900, 0.9);

  await clock.waitUntil(18.0);
  await moveCursor(page, 865, 592, 520, 1);
  await pulse(page, 865, 592);
  await page.locator('[data-geo-metric="companies"]').click();
  await page.waitForTimeout(1800);

  await clock.waitUntil(23.0);
  await moveCursor(page, 781, 592, 520, 1);
  await pulse(page, 781, 592);
  await page.locator('[data-geo-metric="products"]').click();
  await page.waitForTimeout(900);

  await clock.waitUntil(28.0);
  await selectValue(page, "#geoTrackFilter", "Injectables", 770, 724);
  await selectValue(page, "#geoRegionFilter", "Asia-Pacific", 1075, 724);
  await flyTo(page, 35.5, 127.8, 4.1, 2.2);

  await clock.waitUntil(36.5);
  await moveCursor(page, 1522, 805, 900, 0.92);
  await pulse(page, 1522, 805);

  await clock.waitUntil(40.0);
  await openCountry(page, "South Korea");
  await moveCursor(page, 1020, 905, 900, 0.9);

  await clock.waitUntil(45.0);
  const seoul = page.locator(".country-city-row", {hasText: "Seoul"}).first();
  if (await seoul.count()) {
    await moveCursor(page, 160, 882, 520, 1);
    await pulse(page, 160, 882);
    await seoul.click();
  }

  await clock.waitUntil(49.2);
  const seongnam = page.locator(".country-city-row", {hasText: "Seongnam"}).first();
  if (await seongnam.count()) {
    await moveCursor(page, 475, 882, 520, 1);
    await pulse(page, 475, 882);
    await seongnam.click();
  }

  await clock.waitUntil(53.0);
  await moveCursor(page, 1856, 50, 520, 1);
  await pulse(page, 1856, 50);
  await page.locator(".result-close").click();
  await page.waitForTimeout(700);
  await page.selectOption("#geoTrackFilter", "all");
  await page.selectOption("#geoRegionFilter", "all");
  await flyTo(page, 22, 12, 2.0, 2.0);

  await clock.waitUntil(61.5);
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  const temporaryPath = await video?.path();
  if (temporaryPath) {
    await fs.copyFile(temporaryPath, recordingPath);
  }
}

const stat = await fs.stat(recordingPath);
console.log(JSON.stringify({
  ok: true,
  recordingPath,
  bytes: stat.size,
  warnings: pageErrors.slice(0, 8),
}, null, 2));

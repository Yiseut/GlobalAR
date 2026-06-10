import fs from "node:fs/promises";
import path from "node:path";
import {loadPlaywright} from "./load-playwright.mjs";
import {
  dashboardUrl,
  ensureParent,
  mainRecordingPath,
  rawRecordingPath,
  recordingMetaPath,
  run,
  runCapture,
} from "./utils.mjs";
import {installPresenterLayer, installTextureRoutes, installV3VideoHooks, scrollToGlobe, waitForGlobeReady} from "./browser-helpers.mjs";

const WIDTH = 1920;
const HEIGHT = 1080;
const MAIN_DURATION = 100;

const clock = () => {
  const started = Date.now();
  return {
    elapsed: () => (Date.now() - started) / 1000,
    waitUntil: async (seconds) => {
      const ms = Math.max(0, seconds * 1000 - (Date.now() - started));
      if (ms > 0) await new Promise((resolve) => setTimeout(resolve, ms));
    },
  };
};

const moveCursor = async (page, x, y, duration = 640, scale = 1, visible = true) => {
  await page.evaluate((payload) => window.__videoMoveCursor?.(payload), {x, y, duration, scale, visible});
  await page.mouse.move(x, y, {steps: Math.max(4, Math.round(duration / 45))});
  await page.waitForTimeout(duration + 40);
};

const pulse = async (page, x, y) => {
  await page.evaluate((payload) => window.__videoPulse?.(payload), {x, y});
};

const focusRect = async (page, selector, visible = true) => {
  const rect = await page.locator(selector).first().boundingBox().catch(() => null);
  if (!rect) return;
  await page.evaluate((payload) => window.__videoFocusRect?.(payload), {
    x: rect.x - 8,
    y: rect.y - 8,
    width: rect.width + 16,
    height: rect.height + 16,
    visible,
  });
};

const pointOfView = async (page, lat, lng, altitude, duration = 1600) => {
  await page.evaluate(
    ({lat, lng, altitude, duration}) => window.__videoGlobe.pointOfView({lat, lng, altitude}, duration),
    {lat, lng, altitude, duration},
  );
};

const setAutoRotate = async (page, value) => {
  await page.evaluate((enabled) => {
    const controls = window.__videoGlobe?.controls?.();
    if (controls) controls.autoRotate = enabled;
  }, value);
};

const stageBox = async (page) => {
  const box = await page.locator(".globe-stage-wrap").boundingBox();
  if (!box) throw new Error("Globe stage box is unavailable.");
  return {
    ...box,
    cx: box.x + box.width * 0.54,
    cy: box.y + box.height * 0.54,
  };
};

const clickTrack = async (page, track) => {
  const pill = page.locator(`.globe-controls .filter-pill[data-track="${track}"]`).first();
  const box = await pill.boundingBox();
  if (!box) throw new Error(`Track pill not visible: ${track}`);
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await moveCursor(page, x, y, 420, 0.92);
  await pulse(page, x, y);
  await pill.click();
  await page.waitForTimeout(900);
};

const openUsa = async (page, box) => {
  const x = box.x + box.width * 0.39;
  const y = box.y + box.height * 0.49;
  await moveCursor(page, x, y, 520, 0.94);
  await pulse(page, x, y);
  await page.evaluate(() => window.__videoShowCountryDrawer("United States of America"));
  await page.waitForSelector("#countryDrawer.show", {timeout: 12000});
};

const clickAllergan = async (page) => {
  const row = page.locator("#countryDrawer .drawer-list .row", {hasText: "Allergan"}).first();
  await row.scrollIntoViewIfNeeded();
  const box = await row.boundingBox();
  if (!box) throw new Error("Allergan row is not visible.");
  const x = Math.min(box.x + box.width * 0.32, 1810);
  const y = box.y + box.height / 2;
  await moveCursor(page, x, y, 440, 0.92);
  await pulse(page, x, y);
  await row.click();
  await page.waitForSelector("#globeDetailCard.show", {timeout: 12000});
};

const scrollProducts = async (page) => {
  await page.evaluate(() => {
    const list = document.querySelector("#globeDetailCard .card-products");
    if (list) list.scrollTo({top: 170, behavior: "smooth"});
  });
};

await ensureParent(fs, rawRecordingPath);
await fs.rm(rawRecordingPath, {force: true});
await fs.rm(mainRecordingPath, {force: true});

const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless: true});
const context = await browser.newContext({
  viewport: {width: WIDTH, height: HEIGHT},
  deviceScaleFactor: 1,
  recordVideo: {
    dir: path.dirname(rawRecordingPath),
    size: {width: WIDTH, height: HEIGHT},
  },
});
const page = await context.newPage();
const warnings = [];
page.on("pageerror", (error) => warnings.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") warnings.push(message.text());
});

try {
  await installTextureRoutes(page);
  await installV3VideoHooks(page);
  await page.goto(`${dashboardUrl}?video-record=${Date.now()}`, {waitUntil: "domcontentloaded", timeout: 70000});
  await waitForGlobeReady(page);
  await scrollToGlobe(page);
  await installPresenterLayer(page);
  await page.waitForTimeout(1000);

  const box = await stageBox(page);
  await page.evaluate(() => {
    document.querySelector("#globe-loading")?.remove();
    document.querySelector("#globeDetailCard")?.classList.remove("show");
    document.querySelector("#countryDrawer")?.classList.remove("show");
  });
  await pointOfView(page, 28, 22, 1.58, 0);
  await setAutoRotate(page, true);
  await moveCursor(page, box.x + box.width * 0.84, box.y + box.height * 0.18, 0, 0.7, false);
  await page.waitForTimeout(600);

  const demo = clock();

  await demo.waitUntil(3.4);
  await pointOfView(page, 43, -118, 1.34, 1800);

  await demo.waitUntil(7.2);
  await moveCursor(page, box.cx + 300, box.cy - 26, 360, 0.92);
  await page.mouse.down();
  await page.evaluate(() => window.__videoMoveCursor?.({x: window.innerWidth * 0.38, y: window.innerHeight * 0.57, duration: 980, scale: 0.9}));
  await page.mouse.move(box.cx - 250, box.cy + 28, {steps: 32});
  await page.waitForTimeout(180);
  await page.mouse.move(box.cx - 410, box.cy - 10, {steps: 18});
  await page.mouse.up();
  await pulse(page, box.cx - 410, box.cy - 10);
  await setAutoRotate(page, false);

  await demo.waitUntil(11.0);
  await moveCursor(page, box.cx + 122, box.cy + 42, 480, 0.9);
  await page.mouse.wheel(0, -1250);
  await pulse(page, box.cx + 122, box.cy + 42);
  await pointOfView(page, 58, -100, 0.98, 1450);

  await demo.waitUntil(15.2);
  await moveCursor(page, box.cx - 30, box.cy + 210, 300, 0.88);
  await page.mouse.down();
  await page.evaluate(() => window.__videoMoveCursor?.({x: window.innerWidth * 0.50, y: window.innerHeight * 0.32, duration: 900, scale: 0.88}));
  await page.mouse.move(box.cx - 12, box.cy - 180, {steps: 30});
  await page.mouse.up();
  await pulse(page, box.cx - 12, box.cy - 180);

  await demo.waitUntil(18.0);
  await setAutoRotate(page, true);
  await pointOfView(page, 44, 10, 1.28, 2200);

  await demo.waitUntil(25.0);
  await pointOfView(page, 36, 127.8, 1.18, 2300);

  await demo.waitUntil(31.5);
  await pointOfView(page, 42, -92, 1.24, 2100);

  await demo.waitUntil(36.0);
  await pointOfView(page, 30, 30, 1.72, 1700);
  await setAutoRotate(page, true);

  await demo.waitUntil(43.4);
  await clickTrack(page, "EBD");
  await demo.waitUntil(47.0);
  await clickTrack(page, "Injectables");
  await demo.waitUntil(49.4);
  await clickTrack(page, "all");

  await demo.waitUntil(57.0);
  await setAutoRotate(page, false);
  await pointOfView(page, 39, -98, 1.08, 1200);
  await demo.waitUntil(60.0);
  await openUsa(page, box);
  await focusRect(page, "#countryDrawer .country-minimap-wrap", true);

  await demo.waitUntil(72.0);
  await focusRect(page, "#countryDrawer .drawer-list", true);
  await demo.waitUntil(75.0);
  await page.evaluate(() => {
    const list = document.querySelector("#countryDrawer .drawer-list");
    if (list) list.scrollTo({top: 150, behavior: "smooth"});
  });
  await demo.waitUntil(78.2);
  await page.evaluate(() => {
    const list = document.querySelector("#countryDrawer .drawer-list");
    if (list) list.scrollTo({top: 0, behavior: "smooth"});
  });

  await demo.waitUntil(82.0);
  await clickAllergan(page);
  await focusRect(page, "#globeDetailCard", true);

  await demo.waitUntil(92.0);
  await scrollProducts(page);

  await demo.waitUntil(MAIN_DURATION + 0.6);
} finally {
  const video = page.video();
  await context.close();
  await browser.close();
  const temporaryPath = await video?.path();
  if (temporaryPath) {
    await fs.copyFile(temporaryPath, rawRecordingPath);
  }
}

const probe = await runCapture("ffprobe", [
  "-v",
  "error",
  "-show_entries",
  "format=duration",
  "-of",
  "default=noprint_wrappers=1:nokey=1",
  rawRecordingPath,
]);
const rawDurationSec = Number(probe.stdout.toString("utf8").trim());
const trimStartSec = Math.max(0, rawDurationSec - (MAIN_DURATION + 0.75));

await run("ffmpeg", [
  "-y",
  "-i",
  rawRecordingPath,
  "-ss",
  trimStartSec.toFixed(3),
  "-t",
  MAIN_DURATION.toFixed(3),
  "-vf",
  "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p",
  "-an",
  "-c:v",
  "libx264",
  "-preset",
  "medium",
  "-crf",
  "18",
  mainRecordingPath,
]);

await ensureParent(fs, recordingMetaPath);
await fs.writeFile(
  recordingMetaPath,
  JSON.stringify(
    {
      ok: true,
      rawRecordingPath,
      mainRecordingPath,
      trimStartSec,
      rawDurationSec,
      durationSec: MAIN_DURATION,
      warnings: warnings.slice(0, 10),
      notes: [
        "Opening starts directly on the globe.",
        "Includes auto-rotation, drag pause, wheel zoom, USA country panel, and Allergan product card.",
      ],
    },
    null,
    2,
  ),
  "utf8",
);

const stat = await fs.stat(mainRecordingPath);
console.log(JSON.stringify({ok: true, mainRecordingPath, bytes: stat.size, trimStartSec, rawDurationSec, warnings: warnings.slice(0, 8)}, null, 2));

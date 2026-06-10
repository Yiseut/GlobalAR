import fs from "node:fs/promises";
import {loadPlaywright} from "./load-playwright.mjs";
import {dashboardUrl, ensureParent, stills} from "./utils.mjs";

const {chromium} = await loadPlaywright();
const browser = await chromium.launch({headless: true});
const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});

try {
  await page.goto(`${dashboardUrl}?video-stills=${Date.now()}`, {waitUntil: "domcontentloaded", timeout: 70000});
  await page.waitForFunction(() => window.GLOBAL_AESTHETICS_DATA && document.querySelector(".page-hero [data-bind='companies']")?.textContent?.trim() === "366", {timeout: 40000});
  await page.waitForTimeout(1000);

  await ensureParent(fs, stills.hero);

  await page.evaluate(() => window.scrollTo({top: 0, behavior: "instant"}));
  await page.waitForTimeout(450);
  await page.screenshot({path: stills.hero, fullPage: false, timeout: 0});

  await page.locator(".kpi-grid").scrollIntoViewIfNeeded();
  await page.waitForTimeout(450);
  await page.screenshot({path: stills.metrics, fullPage: false, timeout: 0});

  await page.evaluate(() => window.scrollTo({top: 0, behavior: "instant"}));
  await page.waitForTimeout(450);
  await page.screenshot({path: stills.rail, fullPage: false, timeout: 0});

  const tracksBlock = page.locator("h2", {hasText: "赛道分布"}).locator("xpath=ancestor::section[1]");
  await tracksBlock.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await page.screenshot({path: stills.tracks, fullPage: false, timeout: 0});

  const sizes = {};
  for (const [key, file] of Object.entries(stills)) {
    const stat = await fs.stat(file);
    sizes[key] = stat.size;
  }
  console.log(JSON.stringify({ok: true, stills, sizes}, null, 2));
} finally {
  await browser.close();
}

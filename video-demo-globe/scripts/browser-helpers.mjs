import fs from "node:fs/promises";
import path from "node:path";
import {projectRoot} from "./utils.mjs";

const textureRoot = path.join(projectRoot, "public", "assets", "textures");

export const installTextureRoutes = async (page) => {
  await page.route("**/earth-blue-marble.jpg", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/jpeg",
      body: await fs.readFile(path.join(textureRoot, "earth-blue-marble.jpg")),
    });
  });
  await page.route("**/earth-topology.png", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "image/png",
      body: await fs.readFile(path.join(textureRoot, "earth-topology.png")),
    });
  });
};

export const installV3VideoHooks = async (page) => {
  await page.route("**/v3/index.html**", async (route) => {
    const response = await route.fetch();
    let html = await response.text();
    const needle = "globe.pointOfView({ lat: 30, lng: 30, altitude: 2.0 }, 0);";
    if (!html.includes(needle)) {
      throw new Error("Could not inject v3 globe video hooks: pointOfView anchor not found.");
    }
    html = html
      .replace("opacity: 0.85,", "opacity: 0.48,")
      .replace("opacity: 0.40,", "opacity: 0.20,");
    html = html.replace(
      needle,
      [
        "try {",
        "  const mat = globe.globeMaterial && globe.globeMaterial();",
        "  if (mat) {",
        "    mat.color && mat.color.set && mat.color.set('#ffffff');",
        "    if (mat.emissive && mat.emissive.set) mat.emissive.set('#202024');",
        "    if ('emissiveIntensity' in mat) mat.emissiveIntensity = 0.34;",
        "    if ('shininess' in mat) mat.shininess = 9;",
        "    mat.needsUpdate = true;",
        "  }",
        "  if (typeof THREE !== 'undefined' && globe.scene) globe.scene().add(new THREE.AmbientLight(0xffffff, 0.45));",
        "} catch (err) { console.warn('[video] globe material lift skipped', err); }",
        "window.__videoGlobe = globe;",
        "window.__videoShowCountryDrawer = showCountryDrawer;",
        "window.__videoShowDetailCard = showDetailCard;",
        "window.__videoAllCompanies = allCompanies;",
        needle,
      ].join("\n    "),
    );
    await route.fulfill({
      response,
      body: html,
      headers: {...response.headers(), "content-type": "text/html; charset=utf-8"},
    });
  });
};

export const installPresenterLayer = async (page) => {
  await page.evaluate(() => {
    if (document.getElementById("globeVideoPresenterStyle")) return;
    const style = document.createElement("style");
    style.id = "globeVideoPresenterStyle";
    style.textContent = `
      html, body { scroll-behavior: auto !important; }
      body::-webkit-scrollbar { width: 0; height: 0; }
      #globeVideoCursor {
        position: fixed;
        z-index: 2147483000;
        left: 0;
        top: 0;
        width: 26px;
        height: 26px;
        margin-left: -13px;
        margin-top: -13px;
        border-radius: 999px;
        border: 1px solid rgba(255, 235, 205, 0.92);
        background: rgba(217, 160, 91, 0.84);
        box-shadow: 0 0 0 8px rgba(217, 160, 91, 0.12), 0 16px 34px rgba(0, 0, 0, 0.28);
        pointer-events: none;
        opacity: 0;
        transform: translate(1600px, 700px) scale(0.8);
        transition: transform 640ms cubic-bezier(.16, 1, .3, 1), opacity 220ms ease;
      }
      #globeVideoCursor.visible { opacity: 1; }
      .globeVideoPulse {
        position: fixed;
        z-index: 2147482999;
        left: 0;
        top: 0;
        width: 30px;
        height: 30px;
        margin-left: -15px;
        margin-top: -15px;
        border-radius: 999px;
        border: 1px solid rgba(217, 160, 91, 0.8);
        pointer-events: none;
        animation: globeVideoPulse 820ms cubic-bezier(.16, 1, .3, 1) forwards;
      }
      .globeVideoFocus {
        position: fixed;
        z-index: 2147482998;
        border-radius: 20px;
        border: 1px solid rgba(217, 160, 91, 0.58);
        box-shadow: 0 0 0 9999px rgba(9, 7, 13, 0.18), 0 0 34px rgba(217, 160, 91, 0.18);
        pointer-events: none;
        opacity: 0;
        transition: opacity 260ms ease, transform 680ms cubic-bezier(.16, 1, .3, 1);
      }
      .globeVideoFocus.visible { opacity: 1; }
      @keyframes globeVideoPulse {
        from { opacity: 0.9; transform: scale(.8); }
        to { opacity: 0; transform: scale(4.6); }
      }
    `;
    document.head.appendChild(style);

    const cursor = document.createElement("div");
    cursor.id = "globeVideoCursor";
    document.body.appendChild(cursor);

    const focus = document.createElement("div");
    focus.className = "globeVideoFocus";
    document.body.appendChild(focus);

    window.__videoMoveCursor = ({x, y, duration = 640, scale = 1, visible = true}) => {
      cursor.style.transitionDuration = `${duration}ms, 220ms`;
      cursor.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
      cursor.classList.toggle("visible", visible);
    };
    window.__videoPulse = ({x, y}) => {
      const pulse = document.createElement("div");
      pulse.className = "globeVideoPulse";
      pulse.style.left = `${x}px`;
      pulse.style.top = `${y}px`;
      document.body.appendChild(pulse);
      window.setTimeout(() => pulse.remove(), 900);
    };
    window.__videoFocusRect = ({x, y, width, height, scale = 1, visible = true}) => {
      focus.style.left = `${x}px`;
      focus.style.top = `${y}px`;
      focus.style.width = `${width}px`;
      focus.style.height = `${height}px`;
      focus.style.transform = `scale(${scale})`;
      focus.classList.toggle("visible", visible);
    };
  });
};

export const scrollToGlobe = async (page) => {
  await page.evaluate(() => {
    const wrap = document.querySelector(".globe-stage-wrap");
    const section = document.querySelector(".globe-section");
    const target = wrap || section;
    if (!target) return;
    const y = target.getBoundingClientRect().top + window.scrollY - 150;
    window.scrollTo(0, Math.max(0, y));
  });
};

export const waitForGlobeReady = async (page) => {
  await page.waitForFunction(
    () =>
      window.__videoGlobe &&
      document.querySelector("#globe-stage canvas") &&
      window.__videoAllCompanies?.some((c) => c.company === "Allergan"),
    {timeout: 70000},
  );
  await page.waitForTimeout(1800);
};

import path from "node:path";
import fs from "node:fs/promises";
import {pathToFileURL} from "node:url";
import {runCapture} from "./utils.mjs";

const fileExists = async (filePath) => {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
};

export const loadPlaywright = async () => {
  try {
    return await import("playwright");
  } catch {
    const pathEntries = (process.env.Path || process.env.PATH || "")
      .split(path.delimiter)
      .filter(Boolean);
    const prefixes = [
      process.env.PLAYWRIGHT_GLOBAL_ROOT,
      process.env.npm_config_prefix && path.join(process.env.npm_config_prefix, "node_modules"),
      ...pathEntries.map((entry) => path.join(entry, "node_modules")),
    ].filter(Boolean);

    for (const root of prefixes) {
      const entry = path.join(root, "playwright", "index.mjs");
      if (await fileExists(entry)) return await import(pathToFileURL(entry).href);
    }

    const {stdout} = await runCapture("cmd", ["/d", "/s", "/c", "npm root -g"]);
    const globalRoot = stdout.toString("utf8").trim();
    const entry = path.join(globalRoot, "playwright", "index.mjs");
    return await import(pathToFileURL(entry).href);
  }
};

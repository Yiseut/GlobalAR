import path from "node:path";
import fs from "node:fs/promises";
import {pathToFileURL} from "node:url";
import {runCapture} from "./utils.mjs";

const exists = async (filePath) => {
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
    const candidates = [
      process.env.PLAYWRIGHT_GLOBAL_ROOT,
      "E:\\shared\\tools\\npm-global\\node_modules",
      process.env.npm_config_prefix && path.join(process.env.npm_config_prefix, "node_modules"),
      ...pathEntries.map((entry) => path.join(entry, "node_modules")),
    ].filter(Boolean);

    for (const root of candidates) {
      const entry = path.join(root, "playwright", "index.mjs");
      if (await exists(entry)) return await import(pathToFileURL(entry).href);
    }

    const {stdout} = await runCapture("npm", ["root", "-g"]);
    const entry = path.join(stdout.toString("utf8").trim(), "playwright", "index.mjs");
    return await import(pathToFileURL(entry).href);
  }
};

import fs from "node:fs/promises";
import path from "node:path";
import {captionAssetPath, ensureParent, outputCaptionPath, outputScriptPath, voiceoverTextPath} from "./utils.mjs";
import {captions, voiceoverText} from "./story-data.mjs";

const pad = (number, width = 2) => String(number).padStart(width, "0");
const timestamp = (seconds) => {
  const totalMs = Math.round(seconds * 1000);
  const ms = totalMs % 1000;
  const totalSeconds = Math.floor(totalMs / 1000);
  const s = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const m = totalMinutes % 60;
  const h = Math.floor(totalMinutes / 60);
  return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
};

const srt = captions
  .map((caption, index) => `${index + 1}\n${timestamp(caption.start)} --> ${timestamp(caption.end)}\n${caption.zh}\n${caption.en}\n`)
  .join("\n");

await ensureParent(fs, captionAssetPath);
await ensureParent(fs, outputCaptionPath);
await fs.writeFile(captionAssetPath, srt, "utf8");
await fs.writeFile(outputCaptionPath, srt, "utf8");

const table = captions
  .map((caption) => `| ${caption.start}-${caption.end}s | ${caption.zh} | ${caption.en} |`)
  .join("\n");
const markdown = `# 全球医美地球仪演示片脚本\n\n## Voiceover\n\n${voiceoverText}\n\n## Bilingual Subtitles\n\n| Time | 中文 | English |\n|---|---|---|\n${table}\n\n## Notes\n\n- Opening starts directly on the rotating globe.\n- The pacing is natural, approximately 113 seconds, so the globe rotation, country view, company view, closing overview, and brand outro are readable.\n- Closing montage uses 16:9 overview frames and a 3-second brand outro.\n- The rendered video burns one bilingual subtitle layer; this SRT is exported separately to avoid accidental duplicate loading.\n`;

await fs.writeFile(outputScriptPath, markdown, "utf8");
await fs.writeFile(voiceoverTextPath, voiceoverText, "utf8");

console.log(JSON.stringify({ok: true, captionAssetPath, outputCaptionPath, outputScriptPath, voiceoverTextPath}, null, 2));

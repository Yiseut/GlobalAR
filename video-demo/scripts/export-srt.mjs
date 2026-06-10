import fs from "node:fs/promises";
import path from "node:path";
import {captionPath, outputCaptionPath} from "./utils.mjs";

const storyboard = JSON.parse(await fs.readFile(new URL("../data/storyboard.json", import.meta.url), "utf8"));

const formatSrtTime = (seconds) => {
  const safe = Math.max(0, Number(seconds || 0));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const wholeSeconds = Math.floor(safe % 60);
  const millis = Math.round((safe - Math.floor(safe)) * 1000);
  return [hours, minutes, wholeSeconds].map((part) => String(part).padStart(2, "0")).join(":") + `,${String(millis).padStart(3, "0")}`;
};

const body = storyboard.storyboard
  .map((cue, index) => [
    String(index + 1),
    `${formatSrtTime(cue.start)} --> ${formatSrtTime(cue.end)}`,
    cue.caption,
  ].join("\n"))
  .join("\n\n") + "\n";

await fs.mkdir(path.dirname(captionPath), {recursive: true});
await fs.writeFile(captionPath, body, "utf8");
await fs.mkdir(path.dirname(outputCaptionPath), {recursive: true});
await fs.writeFile(outputCaptionPath, body, "utf8");

console.log(JSON.stringify({ok: true, captionPath, outputCaptionPath}, null, 2));

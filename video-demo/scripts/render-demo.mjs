import {run} from "./utils.mjs";

const steps = [
  ["preflight", ["run", "preflight"]],
  ["record", ["run", "record"]],
  ["audio", ["run", "audio"]],
  ["captions", ["run", "captions"]],
  ["render", ["run", "render:ffmpeg"]],
  ["validate", ["run", "validate"]],
];

for (const [label, args] of steps) {
  console.log(`\n[video-demo] ${label}`);
  await run("npm", args);
}

console.log("\n[video-demo] done");

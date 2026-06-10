import fs from "node:fs/promises";
import path from "node:path";
import {outputRoot, run, runCapture, videoPath} from "./utils.mjs";

const probe = await runCapture("ffprobe", [
  "-v", "error",
  "-print_format", "json",
  "-show_streams",
  "-show_format",
  videoPath,
]);

const metadata = JSON.parse(probe.stdout.toString("utf8"));
const video = metadata.streams.find((stream) => stream.codec_type === "video");
const audio = metadata.streams.find((stream) => stream.codec_type === "audio");
const duration = Number(metadata.format?.duration || video?.duration || 0);

const problems = [];
if (!video) problems.push("No video stream found");
if (!audio) problems.push("No audio stream found");
if (video && (Number(video.width) !== 1920 || Number(video.height) !== 1080)) {
  problems.push(`Expected 1920x1080, got ${video.width}x${video.height}`);
}
if (!(duration >= 58 && duration <= 64)) problems.push(`Expected about 60 seconds, got ${duration.toFixed(2)} seconds`);

const frameDir = path.join(outputRoot, "video-demo-frame-checks");
await fs.mkdir(frameDir, {recursive: true});

const sampledFrames = [];
for (const second of [5, 20, 35, 50]) {
  const jpg = path.join(frameDir, `frame-${String(second).padStart(2, "0")}.jpg`);
  await run("ffmpeg", [
    "-y",
    "-ss", String(second),
    "-i", videoPath,
    "-frames:v", "1",
    "-q:v", "3",
    jpg,
  ], {stdio: "ignore"});
  const raw = await runCapture("ffmpeg", [
    "-v", "error",
    "-ss", String(second),
    "-i", videoPath,
    "-frames:v", "1",
    "-vf", "scale=16:9,format=gray",
    "-f", "rawvideo",
    "pipe:1",
  ]);
  const pixels = [...raw.stdout];
  const average = pixels.reduce((sum, value) => sum + value, 0) / Math.max(1, pixels.length);
  sampledFrames.push({second, jpg, averageLuma: Number(average.toFixed(2))});
  if (average < 12) problems.push(`Frame at ${second}s looks too dark`);
}

const summary = {
  ok: problems.length === 0,
  videoPath,
  width: video?.width,
  height: video?.height,
  duration: Number(duration.toFixed(3)),
  hasAudio: Boolean(audio),
  sampledFrames,
  problems,
};

await fs.writeFile(path.join(frameDir, "validation-summary.json"), JSON.stringify(summary, null, 2), "utf8");
console.log(JSON.stringify(summary, null, 2));

if (problems.length) process.exit(1);

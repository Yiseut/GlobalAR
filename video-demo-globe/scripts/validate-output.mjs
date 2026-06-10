import fs from "node:fs/promises";
import path from "node:path";
import {outputRoot, run, runCapture, videoPath} from "./utils.mjs";

const fail = (message, details = {}) => {
  console.error(JSON.stringify({ok: false, message, ...details}, null, 2));
  process.exit(1);
};

await fs.access(videoPath).catch(() => fail("Rendered video is missing.", {videoPath}));

const probe = await runCapture("ffprobe", [
  "-v",
  "error",
  "-print_format",
  "json",
  "-show_format",
  "-show_streams",
  videoPath,
]);
const info = JSON.parse(probe.stdout.toString("utf8"));
const video = info.streams.find((stream) => stream.codec_type === "video");
const audio = info.streams.find((stream) => stream.codec_type === "audio");
const duration = Number(info.format.duration || 0);

if (!video || Number(video.width) !== 1920 || Number(video.height) !== 1080) {
  fail("Video stream is not 1920x1080.", {video});
}
if (!audio) fail("Audio stream is missing.", {streams: info.streams});
if (duration < 112.2 || duration > 113.8) fail("Video duration is outside the expected natural-paced 113s window.", {duration});

const frameDir = path.join(outputRoot, "video-check", "globe-demo");
await fs.mkdir(frameDir, {recursive: true});
await run("ffmpeg", [
  "-y",
  "-i",
  videoPath,
  "-vf",
  "select='eq(n,0)+eq(n,600)+eq(n,1200)+eq(n,1900)+eq(n,2700)+eq(n,3180)+eq(n,3330)'",
  "-vsync",
  "vfr",
  path.join(frameDir, "frame-%02d.jpg"),
]);

const frames = await fs.readdir(frameDir);
const frameStats = [];
for (const file of frames.filter((name) => name.endsWith(".jpg"))) {
  const stat = await fs.stat(path.join(frameDir, file));
  frameStats.push({file, bytes: stat.size});
  if (stat.size < 25000) fail("Extracted frame is suspiciously small.", {file, bytes: stat.size});
}

const blackDetect = await runCapture(
  "ffmpeg",
  ["-i", videoPath, "-vf", "blackdetect=d=0.35:pix_th=0.10", "-an", "-f", "null", "-"],
  {stdio: ["ignore", "pipe", "pipe"]},
).catch((error) => ({stderr: error.message}));
const blackLog = blackDetect.stderr || "";
if (blackLog.includes("black_start:")) fail("Black-frame detector found a black segment.", {blackLog});

console.log(JSON.stringify({ok: true, videoPath, duration, video: {width: video.width, height: video.height}, audio: audio.codec_name, frameStats}, null, 2));

import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";
import path from "node:path";

export const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const publicRoot = path.join(projectRoot, "public");
export const outputRoot = path.resolve(projectRoot, "..", "output");
export const dashboardUrl = process.env.DASHBOARD_URL || "http://127.0.0.1:8790/v3/index.html";

export const rawRecordingPath = path.join(publicRoot, "assets", "recordings", "globe-interaction-raw.webm");
export const mainRecordingPath = path.join(publicRoot, "assets", "recordings", "globe-interaction-main.mp4");
export const recordingMetaPath = path.join(publicRoot, "assets", "metadata", "recording-meta.json");
export const voiceoverTextPath = path.join(outputRoot, "global-aesthetics-globe-demo-voiceover-en.txt");
export const voiceoverPath = path.join(publicRoot, "assets", "audio", "voiceover-en.mp3");
export const voiceoverWavPath = path.join(publicRoot, "assets", "audio", "voiceover-en.wav");
export const brandVoiceoverPath = path.join(publicRoot, "assets", "audio", "brand-voiceover-en.mp3");
export const brandVoiceoverWavPath = path.join(publicRoot, "assets", "audio", "brand-voiceover-en.wav");
export const musicPath = path.join(publicRoot, "assets", "audio", "tech-pulse-bed.wav");
export const captionAssetPath = path.join(publicRoot, "assets", "captions", "globe-demo-bilingual.srt");
export const outputCaptionPath = path.join(outputRoot, "subtitles", "global-aesthetics-globe-demo-bilingual.srt");
export const outputScriptPath = path.join(outputRoot, "global-aesthetics-globe-demo-script.md");
export const videoPath = path.join(outputRoot, "global-aesthetics-globe-demo-16x9.mp4");

export const stills = {
  hero: path.join(publicRoot, "assets", "stills", "overview-hero.png"),
  metrics: path.join(publicRoot, "assets", "stills", "overview-metrics.png"),
  tracks: path.join(publicRoot, "assets", "stills", "overview-tracks.png"),
  rail: path.join(publicRoot, "assets", "stills", "overview-rail.png"),
};

const platformCommand = (command) => {
  if (process.platform !== "win32") return command;
  if (command === "npm" || command === "npx") return `${command}.cmd`;
  if (command === "python") return "python.exe";
  if (command === "powershell") return "powershell.exe";
  return command;
};

export const run = (command, args, options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(platformCommand(command), args, {
      cwd: options.cwd || projectRoot,
      shell: false,
      stdio: options.stdio || "inherit",
      ...options,
    });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${command} ${args.join(" ")} exited with ${code}`));
    });
  });

export const runCapture = (command, args, options = {}) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    const errors = [];
    const child = spawn(platformCommand(command), args, {
      cwd: options.cwd || projectRoot,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
      ...options,
    });
    child.stdout.on("data", (chunk) => chunks.push(chunk));
    child.stderr.on("data", (chunk) => errors.push(chunk));
    child.on("error", reject);
    child.on("exit", (code) => {
      const stdout = Buffer.concat(chunks);
      const stderr = Buffer.concat(errors).toString("utf8");
      if (code === 0) resolve({stdout, stderr});
      else reject(new Error(`${command} ${args.join(" ")} exited with ${code}\n${stderr}`));
    });
  });

export const ensureParent = async (fs, filePath) => {
  await fs.mkdir(path.dirname(filePath), {recursive: true});
};

import {spawn} from "node:child_process";
import {fileURLToPath} from "node:url";
import path from "node:path";

export const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const publicRoot = path.join(projectRoot, "public");
export const outputRoot = path.resolve(projectRoot, "..", "output");
export const dashboardUrl = process.env.DASHBOARD_URL || "http://127.0.0.1:8790/index.html";
export const videoPath = path.join(outputRoot, "global-aesthetics-map-demo-16x9.mp4");
export const recordingPath = path.join(publicRoot, "assets", "recordings", "dashboard-interaction.webm");
export const audioPath = path.join(publicRoot, "assets", "audio", "generated-ambient-bed.wav");
export const captionPath = path.join(publicRoot, "assets", "captions", "global-aesthetics-map-demo.srt");
export const outputCaptionPath = path.join(outputRoot, "global-aesthetics-map-demo-16x9.srt");

const platformCommand = (command) => {
  if (process.platform !== "win32") return command;
  if (command === "npm" || command === "npx") return `${command}.cmd`;
  return command;
};

export const run = (command, args, options = {}) =>
  new Promise((resolve, reject) => {
    const child = spawn(platformCommand(command), args, {
      cwd: options.cwd || projectRoot,
      stdio: options.stdio || "inherit",
      shell: false,
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

import fs from "node:fs/promises";
import {audioPath, outputRoot, recordingPath, run, videoPath} from "./utils.mjs";

const firstActEnd = 52.8;
const sourceStart = 4.8;
const outroSourceStart = 60.2;
const outroSourceEnd = 66.36;
const outroDuration = 60 - firstActEnd;
const outroStretch = outroDuration / (outroSourceEnd - outroSourceStart);
const pi = "3.141592653589793";
const ease = (start, end) => `(1-cos(${pi}*(t-${start})/${end - start}))/2`;
const zoomExpr = `if(lt(t,7),1+0.075*${ease(0, 7)},if(lt(t,18),1.075+0.055*${ease(7, 18)},if(lt(t,28),1.13-0.04*${ease(18, 28)},if(lt(t,40),1.09+0.07*${ease(28, 40)},if(lt(t,52.8),1.16-0.04*${ease(40, 52.8)},1.12-0.12*${ease(52.8, 60)})))))`;
const panXExpr = `if(lt(t,18),0.50,if(lt(t,28),0.50+0.04*${ease(18, 28)},if(lt(t,40),0.54+0.08*${ease(28, 40)},if(lt(t,52.8),0.62-0.12*${ease(40, 52.8)},0.50))))`;
const panYExpr = `if(lt(t,18),0.47,if(lt(t,28),0.47-0.05*${ease(18, 28)},if(lt(t,40),0.42+0.03*${ease(28, 40)},if(lt(t,52.8),0.45+0.03*${ease(40, 52.8)},0.47))))`;

await fs.mkdir(outputRoot, {recursive: true});

for (const required of [recordingPath, audioPath]) {
  await fs.access(required);
}

const videoFilters = [
  `[0:v]trim=start=${sourceStart}:end=${sourceStart + firstActEnd},setpts=PTS-STARTPTS[v0];[0:v]trim=start=${outroSourceStart}:end=${outroSourceEnd},setpts=(PTS-STARTPTS)*${outroStretch.toFixed(6)}[v1];[v0][v1]concat=n=2:v=1:a=0,fps=30`,
  `scale=w='1920*(${zoomExpr})':h='1080*(${zoomExpr})':eval=frame`,
  `crop=1920:1080:x='(in_w-1920)*(${panXExpr})':y='(in_h-1080)*(${panYExpr})'`,
  "unsharp=3:3:0.22",
  "format=yuv420p",
  "drawbox=x=0:y=1074:w=iw:h=6:color=0x1F1B1726:t=fill",
  "drawbox=x=0:y=1074:w='if(lte(t,60),iw*t/60,iw)':h=6:color=0xD97757FF:t=fill",
].join(",") + "[v]";

const filters = `${videoFilters};[1:a]atrim=duration=60,asetpts=PTS-STARTPTS[a]`;

await run("ffmpeg", [
  "-y",
  "-i", recordingPath,
  "-i", audioPath,
  "-filter_complex", filters,
  "-map", "[v]",
  "-map", "[a]",
  "-t", "60",
  "-c:v", "libx264",
  "-preset", "medium",
  "-crf", "18",
  "-pix_fmt", "yuv420p",
  "-c:a", "aac",
  "-b:a", "192k",
  "-movflags", "+faststart",
  videoPath,
]);

const stat = await fs.stat(videoPath);
console.log(JSON.stringify({ok: true, videoPath, bytes: stat.size}, null, 2));

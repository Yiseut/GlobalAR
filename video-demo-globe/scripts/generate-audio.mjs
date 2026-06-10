import fs from "node:fs/promises";
import {
  brandVoiceoverPath,
  brandVoiceoverWavPath,
  ensureParent,
  musicPath,
  run,
  voiceoverPath,
  voiceoverTextPath,
  voiceoverWavPath,
} from "./utils.mjs";
import {brandVoiceoverText, mainVoiceoverText, voiceoverText} from "./story-data.mjs";

const sampleRate = 48000;
const durationSec = 113;
const mainVoiceDurationSec = 110;
const brandVoiceDurationSec = 3;
const channels = 2;
const beatSec = 60 / 108;
const notes = [220, 277.18, 329.63, 440, 329.63, 277.18, 246.94, 196];

const writeUInt32LE = (buffer, value, offset) => buffer.writeUInt32LE(value, offset);
const writeUInt16LE = (buffer, value, offset) => buffer.writeUInt16LE(value, offset);

const frac = (x) => x - Math.floor(x);
const noise = (i) => frac(Math.sin(i * 12.9898 + 78.233) * 43758.5453) * 2 - 1;

const synthMusic = async () => {
  const frames = sampleRate * durationSec;
  const dataBytes = frames * channels * 2;
  const buffer = Buffer.alloc(44 + dataBytes);
  buffer.write("RIFF", 0);
  writeUInt32LE(buffer, 36 + dataBytes, 4);
  buffer.write("WAVE", 8);
  buffer.write("fmt ", 12);
  writeUInt32LE(buffer, 16, 16);
  writeUInt16LE(buffer, 1, 20);
  writeUInt16LE(buffer, channels, 22);
  writeUInt32LE(buffer, sampleRate, 24);
  writeUInt32LE(buffer, sampleRate * channels * 2, 28);
  writeUInt16LE(buffer, channels * 2, 32);
  writeUInt16LE(buffer, 16, 34);
  buffer.write("data", 36);
  writeUInt32LE(buffer, dataBytes, 40);

  for (let i = 0; i < frames; i++) {
    const t = i / sampleRate;
    const beat = t % beatSec;
    const beatIndex = Math.floor(t / beatSec);
    const barBeat = beatIndex % 4;
    const fadeIn = Math.min(1, t / 2.8);
    const fadeOut = Math.min(1, (durationSec - t) / 3.4);
    const fade = Math.max(0, Math.min(fadeIn, fadeOut));
    const side = 0.75 + 0.25 * Math.min(1, beat / 0.18);

    const kickEnv = Math.exp(-beat * 24) * (beat < 0.17 ? 1 : 0);
    const kickFreq = 48 + 42 * Math.exp(-beat * 18);
    const kick = Math.sin(2 * Math.PI * kickFreq * t) * kickEnv * 0.42;

    const bassNote = [55, 55, 73.42, 82.41][Math.floor(beatIndex / 2) % 4];
    const bassGate = beat < beatSec * 0.72 ? 1 : 0;
    const bass = Math.sin(2 * Math.PI * bassNote * t) * bassGate * 0.075 * side;

    const stepSec = beatSec / 2;
    const step = Math.floor(t / stepSec);
    const phase = t % stepSec;
    const arpEnv = Math.exp(-phase * 15) * (phase < 0.16 ? 1 : 0);
    const arp = Math.sin(2 * Math.PI * notes[step % notes.length] * t) * arpEnv * 0.095;

    const hatPhase = (t + beatSec / 2) % beatSec;
    const hatEnv = Math.exp(-hatPhase * 55) * (hatPhase < 0.065 ? 1 : 0);
    const hat = noise(i) * hatEnv * 0.034;

    const pad =
      Math.sin(2 * Math.PI * 110 * t) * 0.024 +
      Math.sin(2 * Math.PI * 165 * t + 0.7) * 0.018 +
      Math.sin(2 * Math.PI * 220 * t + 1.4) * 0.012;

    const accent = barBeat === 0 ? 1.08 : 0.92;
    const mono = (kick + bass + arp + hat + pad) * fade * accent;
    const pan = Math.sin(2 * Math.PI * 0.04 * t) * 0.18;
    const left = Math.max(-1, Math.min(1, mono * (1 - pan)));
    const right = Math.max(-1, Math.min(1, mono * (1 + pan)));
    const offset = 44 + i * channels * 2;
    buffer.writeInt16LE(Math.round(left * 32767), offset);
    buffer.writeInt16LE(Math.round(right * 32767), offset + 2);
  }

  await ensureParent(fs, musicPath);
  await fs.writeFile(musicPath, buffer);
};

await ensureParent(fs, voiceoverTextPath);
await fs.writeFile(voiceoverTextPath, voiceoverText, "utf8");

const synthVoice = async ({text, mediaPath, wavPath, seconds, rate = "-5%"}) => {
  await ensureParent(fs, mediaPath);
  let usedEdge = true;
  try {
    await run("python", [
      "-m",
      "edge_tts",
      "--voice",
      "en-US-GuyNeural",
      `--rate=${rate}`,
      "--text",
      text,
      "--write-media",
      mediaPath,
    ]);
  } catch (error) {
    usedEdge = false;
    console.warn(`Edge TTS failed, falling back to local SAPI voice: ${error.message}`);
    const ps = [
      "Add-Type -AssemblyName System.Speech",
      "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
      "$s.Rate = 0",
      `$s.SetOutputToWaveFile('${wavPath.replace(/\\/g, "\\\\")}')`,
      `$s.Speak('${text.replace(/'/g, "''")}')`,
      "$s.Dispose()",
    ].join("; ");
    await run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps]);
  }

  if (usedEdge) {
    await run("ffmpeg", [
      "-y",
      "-i",
      mediaPath,
      "-af",
      `apad=pad_dur=${seconds},atrim=0:${seconds},loudnorm=I=-18:LRA=11:TP=-1.5`,
      "-ar",
      "48000",
      "-ac",
      "2",
      wavPath,
    ]);
  }
};

await synthVoice({
  text: mainVoiceoverText,
  mediaPath: voiceoverPath,
  wavPath: voiceoverWavPath,
  seconds: mainVoiceDurationSec,
});
await synthVoice({
  text: brandVoiceoverText,
  mediaPath: brandVoiceoverPath,
  wavPath: brandVoiceoverWavPath,
  seconds: brandVoiceDurationSec,
  rate: "+12%",
});

await synthMusic();

const voiceStat = await fs.stat(voiceoverWavPath);
const brandVoiceStat = await fs.stat(brandVoiceoverWavPath);
const musicStat = await fs.stat(musicPath);
console.log(
  JSON.stringify(
    {
      ok: true,
      voiceoverWavPath,
      brandVoiceoverWavPath,
      musicPath,
      voiceBytes: voiceStat.size,
      brandVoiceBytes: brandVoiceStat.size,
      musicBytes: musicStat.size,
    },
    null,
    2,
  ),
);

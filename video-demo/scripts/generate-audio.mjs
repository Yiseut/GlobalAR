import fs from "node:fs/promises";
import path from "node:path";
import {audioPath} from "./utils.mjs";

const sampleRate = 48000;
const duration = 60;
const channels = 2;
const totalFrames = sampleRate * duration;
const pcm = new Int16Array(totalFrames * channels);

const notes = {
  C2: 65.41,
  D2: 73.42,
  E2: 82.41,
  F2: 87.31,
  G2: 98.0,
  A2: 110.0,
  B2: 123.47,
  C3: 130.81,
  D3: 146.83,
  E3: 164.81,
  F3: 174.61,
  G3: 196.0,
  A3: 220.0,
  B3: 246.94,
  C4: 261.63,
  D4: 293.66,
  E4: 329.63,
  F4: 349.23,
  G4: 392.0,
  A4: 440.0,
  B4: 493.88,
  C5: 523.25,
  D5: 587.33,
  E5: 659.25,
  F5: 698.46,
  G5: 783.99,
  A5: 880.0,
};

const progression = [
  {root: notes.D2, pad: [notes.D3, notes.A3, notes.C4, notes.F4], arp: [notes.A4, notes.C5, notes.F5, notes.C5]},
  {root: notes.F2, pad: [notes.F3, notes.C4, notes.E4, notes.A4], arp: [notes.C5, notes.E5, notes.A5, notes.E5]},
  {root: notes.C2, pad: [notes.C3, notes.G3, notes.B3, notes.E4], arp: [notes.G4, notes.B4, notes.E5, notes.B4]},
  {root: notes.G2, pad: [notes.G3, notes.D4, notes.F4, notes.A4], arp: [notes.D5, notes.F5, notes.A5, notes.F5]},
];

const tau = Math.PI * 2;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const smooth = (value) => {
  const x = clamp(value, 0, 1);
  return x * x * (3 - 2 * x);
};
const fade = (t) => Math.min(smooth(t / 5), smooth((duration - t) / 5));
const chordAt = (t) => progression[Math.floor(t / 7.5) % progression.length];
const sine = (frequency, t, phase = 0) => Math.sin(tau * frequency * t + phase);
const softTriangle = (frequency, t, phase = 0) => Math.asin(sine(frequency, t, phase)) * (2 / Math.PI);
const pulseEnv = (local, length, attack = 0.03, release = 7) => {
  if (local < 0 || local > length) return 0;
  return smooth(local / attack) * Math.exp(-local * release);
};

for (let i = 0; i < totalFrames; i += 1) {
  const t = i / sampleRate;
  const chord = chordAt(t);
  const master = fade(t);
  const chordLocal = t % 7.5;
  const chordEnvelope = smooth(chordLocal / 1.2) * smooth((7.5 - chordLocal) / 1.2);

  let padLeft = 0;
  let padRight = 0;
  chord.pad.forEach((frequency, index) => {
    const weight = 0.055 / (index + 1);
    padLeft += sine(frequency * 0.997, t, index * 0.73) * weight;
    padRight += sine(frequency * 1.003, t, index * 0.91) * weight;
    padLeft += softTriangle(frequency / 2, t, index * 0.37) * weight * 0.38;
    padRight += softTriangle(frequency / 2, t, index * 0.41) * weight * 0.38;
  });

  const bassBeat = t % 2;
  const bassEnv = pulseEnv(bassBeat, 1.35, 0.05, 2.8);
  const bass = sine(chord.root, t) * 0.12 * bassEnv + sine(chord.root * 2, t) * 0.035 * bassEnv;

  const arpStep = Math.floor(t * 2) % chord.arp.length;
  const arpLocal = (t * 2) % 1;
  const arpEnv = pulseEnv(arpLocal, 0.88, 0.02, 5.8);
  const arpFreq = chord.arp[arpStep];
  const pan = arpStep % 2 === 0 ? -0.34 : 0.34;
  const arp = (sine(arpFreq, t) + sine(arpFreq * 2.01, t) * 0.28) * 0.05 * arpEnv;

  const bellLocal = t % 7.5;
  const bellEnv = pulseEnv(bellLocal, 3.8, 0.02, 1.55);
  const bell = (sine(chord.arp[1] * 1.5, t) + sine(chord.arp[2] * 2, t) * 0.22) * 0.035 * bellEnv;

  const shimmer = sine(0.07, t) * 0.004 + sine(0.11, t, 1.2) * 0.003;
  const left = (padLeft * chordEnvelope + bass + arp * (1 - pan) + bell + shimmer) * master;
  const right = (padRight * chordEnvelope + bass + arp * (1 + pan) + bell - shimmer) * master;

  pcm[i * 2] = Math.round(clamp(Math.tanh(left * 1.65), -1, 1) * 32767);
  pcm[i * 2 + 1] = Math.round(clamp(Math.tanh(right * 1.65), -1, 1) * 32767);
}

const byteRate = sampleRate * channels * 2;
const dataSize = pcm.length * 2;
const buffer = Buffer.alloc(44 + dataSize);
buffer.write("RIFF", 0);
buffer.writeUInt32LE(36 + dataSize, 4);
buffer.write("WAVE", 8);
buffer.write("fmt ", 12);
buffer.writeUInt32LE(16, 16);
buffer.writeUInt16LE(1, 20);
buffer.writeUInt16LE(channels, 22);
buffer.writeUInt32LE(sampleRate, 24);
buffer.writeUInt32LE(byteRate, 28);
buffer.writeUInt16LE(channels * 2, 32);
buffer.writeUInt16LE(16, 34);
buffer.write("data", 36);
buffer.writeUInt32LE(dataSize, 40);

for (let i = 0; i < pcm.length; i += 1) {
  buffer.writeInt16LE(pcm[i], 44 + i * 2);
}

await fs.mkdir(path.dirname(audioPath), {recursive: true});
await fs.writeFile(audioPath, buffer);

const stat = await fs.stat(audioPath);
console.log(JSON.stringify({ok: true, audioPath, bytes: stat.size, style: "locally synthesized stereo instrumental bed"}, null, 2));

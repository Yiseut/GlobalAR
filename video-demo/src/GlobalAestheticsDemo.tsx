import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  OffthreadVideo,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const SECOND = 30;

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const mix = (frame: number, input: number[], output: number[]) =>
  interpolate(frame, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

const cameraForFrame = (frame: number, fps: number) => {
  const points = [
    {time: 0, scale: 1.0, x: 0, y: 0},
    {time: 7 * SECOND, scale: 1.075, x: -34, y: -18},
    {time: 18 * SECOND, scale: 1.13, x: -72, y: -24},
    {time: 28 * SECOND, scale: 1.09, x: -48, y: -12},
    {time: 40 * SECOND, scale: 1.16, x: -96, y: -22},
    {time: 53 * SECOND, scale: 1.07, x: -34, y: -14},
    {time: 60 * SECOND, scale: 1.0, x: 0, y: 0},
  ];
  const nextIndex = points.findIndex((point) => frame <= point.time);
  const right = nextIndex <= 0 ? points[1] : points[nextIndex];
  const left = points[Math.max(0, (nextIndex <= 0 ? 1 : nextIndex) - 1)];
  const accent =
    spring({
      frame: frame - 18 * fps,
      fps,
      config: {damping: 18, mass: 0.7, stiffness: 92},
    }) *
      mix(frame, [18 * fps, 24 * fps, 28 * fps], [1, 1, 0]) +
    spring({
      frame: frame - 40 * fps,
      fps,
      config: {damping: 20, mass: 0.8, stiffness: 86},
    }) *
      mix(frame, [40 * fps, 47 * fps, 53 * fps], [1, 1, 0]);
  if (!right) return points[points.length - 1];
  return {
    scale: mix(frame, [left.time, right.time], [left.scale, right.scale]) + accent * 0.018,
    x: mix(frame, [left.time, right.time], [left.x, right.x]),
    y: mix(frame, [left.time, right.time], [left.y, right.y]),
  };
};

const ProgressLine = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const width = interpolate(frame, [0, durationInFrames - 1], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 6,
        background: "rgba(31, 27, 23, 0.08)",
      }}
    >
      <div
        style={{
          width: `${width}%`,
          height: "100%",
          background: "linear-gradient(90deg, #d97757, #5b7b9a, #8aa57d)",
        }}
      />
    </div>
  );
};

const AudioBed = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const fadeIn = interpolate(frame, [0, 90], [0, 0.34], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [durationInFrames - 110, durationInFrames - 1], [0.34, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return <Audio src={staticFile("assets/audio/generated-ambient-bed.wav")} volume={Math.min(fadeIn, fadeOut)} />;
};

export const GlobalAestheticsDemo = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const camera = cameraForFrame(frame, fps);
  const vignette = interpolate(frame, [0, 120, 1740, 1800], [0.12, 0.08, 0.08, 0.16], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{backgroundColor: "#f8f6f0", overflow: "hidden"}}>
      <AbsoluteFill
        style={{
          transform: `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`,
          transformOrigin: "50% 50%",
        }}
      >
        <OffthreadVideo
          src={staticFile("assets/recordings/dashboard-interaction.webm")}
          style={{width: "100%", height: "100%", objectFit: "cover"}}
        />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background: `
            linear-gradient(180deg, rgba(13, 18, 28, 0.20) 0%, transparent 18%, transparent 68%, rgba(13, 18, 28, 0.34) 100%),
            radial-gradient(circle at 50% 50%, transparent 58%, rgba(34, 28, 22, ${vignette}) 100%)
          `,
        }}
      />
      <ProgressLine />
      <AudioBed />
    </AbsoluteFill>
  );
};

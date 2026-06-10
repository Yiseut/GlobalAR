import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {captions} from "./captions";

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const clampInterpolate = (frame: number, input: number[], output: number[]) =>
  interpolate(frame, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: ease,
  });

const formatNumber = (value: number) => value.toLocaleString("en-US");

const localSpring = (frame: number, fps: number, from: number, config = {damping: 21, stiffness: 125, mass: 0.72}) =>
  spring({
    frame: frame - from,
    fps,
    config,
  });

const CaptionLayer = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const time = frame / fps;
  const active = captions.find((caption) => time >= caption.start && time < caption.end);
  if (!active) return null;

  const local = frame - active.start * fps;
  const duration = (active.end - active.start) * fps;
  const enter = spring({
    frame: local,
    fps,
    config: {damping: 22, stiffness: 120, mass: 0.72},
  });
  const exit = clampInterpolate(local, [duration - 14, duration], [1, 0]);
  const opacity = Math.min(enter, exit);
  const y = interpolate(enter, [0, 1], [18, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const zhFontSize = active.zh.length > 82 ? 22 : active.zh.length > 58 ? 24 : 26;
  const enFontSize = active.en.length > 170 ? 14 : active.en.length > 120 ? 15 : 17;

  return (
    <div
      style={{
        position: "absolute",
        left: 250,
        right: 250,
        bottom: 50,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        opacity,
        transform: `translateY(${y}px)`,
      }}
    >
      <div
        style={{
          maxWidth: 1430,
          padding: "12px 22px 14px",
          borderRadius: 10,
          background: "linear-gradient(180deg, rgba(17, 13, 22, 0.72), rgba(17, 13, 22, 0.56))",
          border: "1px solid rgba(239, 232, 218, 0.15)",
          boxShadow: "0 18px 60px rgba(0,0,0,0.28)",
          backdropFilter: "blur(10px)",
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: '"Microsoft YaHei", "Noto Sans SC", sans-serif',
            fontSize: zhFontSize,
            lineHeight: 1.25,
            color: "#fff6ea",
            fontWeight: 650,
            textShadow: "0 2px 12px rgba(0,0,0,0.46)",
            letterSpacing: 0,
          }}
        >
          {active.zh}
        </div>
        <div
          style={{
            marginTop: 8,
            fontFamily: '"Inter", "DM Sans", Arial, sans-serif',
            fontSize: enFontSize,
            lineHeight: 1.28,
            color: "rgba(244, 230, 214, 0.84)",
            fontWeight: 520,
            textShadow: "0 2px 10px rgba(0,0,0,0.36)",
            letterSpacing: 0,
          }}
        >
          {active.en}
        </div>
      </div>
    </div>
  );
};

const ProgressLine = () => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  const width = interpolate(frame, [0, durationInFrames - 1], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = clampInterpolate(frame, [109.5 * fps, 110.5 * fps], [1, 0]);
  return (
    <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 5, background: "rgba(255,255,255,0.08)", opacity}}>
      <div
        style={{
          width: `${width}%`,
          height: "100%",
          background: "linear-gradient(90deg, #d9a05b, #b85957, #6b5a75)",
        }}
      />
    </div>
  );
};

const GlobeFootage = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale =
    1.1 +
    clampInterpolate(frame, [0, 8 * fps, 14 * fps, 20 * fps, 35 * fps], [0.015, 0.045, 0.095, 0.055, 0.035]) +
    clampInterpolate(frame, [60 * fps, 72 * fps, 82 * fps, 94 * fps, 100 * fps], [0.04, 0.075, 0.13, 0.115, 0.08]);
  const x = clampInterpolate(frame, [0, 14 * fps, 26 * fps, 43 * fps, 60 * fps, 72 * fps, 82 * fps, 100 * fps], [-92, -124, -96, -76, -82, -116, -152, -112]);
  const y = clampInterpolate(frame, [0, 16 * fps, 42 * fps, 60 * fps, 82 * fps, 100 * fps], [-38, -60, -42, -46, -64, -56]);
  const exit = clampInterpolate(frame, [100 * fps, 100.65 * fps], [1, 0]);

  return (
    <AbsoluteFill
      style={{
        opacity: exit,
        transform: `translate(${x}px, ${y}px) scale(${scale})`,
        transformOrigin: "50% 52%",
        backgroundColor: "#100b17",
      }}
    >
      <OffthreadVideo
        src={staticFile("assets/recordings/globe-interaction-main.mp4")}
        style={{width: "100%", height: "100%", objectFit: "cover"}}
      />
    </AbsoluteFill>
  );
};

const DataGlint = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const visible = frame < 99 * fps ? 1 : clampInterpolate(frame, [99 * fps, 100 * fps], [1, 0]);
  const pulse = 0.55 + Math.sin(frame * 0.23) * 0.25 + Math.sin(frame * 0.071) * 0.18;
  return (
    <div
      style={{
        position: "absolute",
        top: 38,
        right: 42,
        width: 210,
        height: 38,
        opacity: visible * Math.max(0.25, pulse),
        pointerEvents: "none",
        background: "linear-gradient(90deg, transparent, rgba(217,160,91,0.34), transparent)",
        filter: "blur(8px)",
        transform: `translateX(${Math.sin(frame * 0.036) * 18}px)`,
      }}
    />
  );
};

const CounterPanel = ({
  from,
  to,
  title,
  items,
}: {
  from: number;
  to: number;
  title: string;
  items: Array<{label: string; value: number; sub: string}>;
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const fromFrame = from * fps;
  const toFrame = to * fps;
  if (frame < fromFrame || frame > toFrame) return null;

  const enter = spring({
    frame: frame - fromFrame,
    fps,
    config: {damping: 23, stiffness: 126, mass: 0.72},
  });
  const exit = clampInterpolate(frame, [toFrame - 18, toFrame], [1, 0]);
  const opacity = Math.min(enter, exit);
  const y = interpolate(enter, [0, 1], [-22, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
  const shimmer = 0.5 + Math.sin(frame * 0.21) * 0.32;

  return (
    <div
      style={{
        position: "absolute",
        left: 86,
        top: 82,
        width: 526,
        padding: "24px 26px 22px",
        borderRadius: 18,
        border: "1px solid rgba(232, 202, 172, 0.14)",
        background: "linear-gradient(180deg, rgba(21, 14, 28, 0.86), rgba(17, 10, 22, 0.72))",
        boxShadow: `0 24px 70px rgba(0,0,0,0.38), 0 0 ${18 + shimmer * 24}px rgba(217,160,91,0.12)`,
        backdropFilter: "blur(10px)",
        opacity,
        transform: `translateY(${y}px)`,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          color: "#e9ae68",
          fontFamily: '"Inter", Arial, sans-serif',
          fontSize: 12,
          fontWeight: 760,
          letterSpacing: 4,
          textTransform: "uppercase",
        }}
      >
        <span style={{width: 7, height: 7, borderRadius: 99, background: "#e1a65d", boxShadow: "0 0 18px #e1a65d"}} />
        {title}
      </div>
      <div style={{display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 18, marginTop: 25}}>
        {items.map((item, index) => {
          const itemStart = fromFrame + index * 6;
          const progress = Math.min(
            1,
            spring({
              frame: Math.max(0, frame - itemStart),
              fps,
              config: {damping: 17, stiffness: 118, mass: 0.78},
            }),
          );
          const value = Math.round(item.value * progress);
          const pulse = frame - itemStart < 34 ? Math.max(0, Math.sin((frame - itemStart) * 0.55)) : 0;
          return (
            <div key={item.label} style={{minWidth: 0}}>
              <div
                style={{
                  color: "rgba(238, 223, 210, 0.62)",
                  fontFamily: '"Inter", Arial, sans-serif',
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: 2.8,
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {item.label}
              </div>
              <div
                style={{
                  marginTop: 8,
                  fontFamily: '"Inter", Arial, sans-serif',
                  fontSize: 40,
                  lineHeight: 1,
                  color: "#fff8ef",
                  fontWeight: 820,
                  textShadow: `0 0 ${10 + pulse * 22}px rgba(244,201,142,${0.24 + pulse * 0.28})`,
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {formatNumber(value)}
              </div>
              <div
                style={{
                  marginTop: 9,
                  color: "#d79b58",
                  fontFamily: '"Inter", Arial, sans-serif',
                  fontSize: 12,
                  fontWeight: 760,
                  letterSpacing: 2.2,
                  textTransform: "uppercase",
                }}
              >
                {item.sub}
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          position: "absolute",
          left: 26,
          right: 26,
          top: 0,
          height: 1,
          opacity: Math.max(0, shimmer),
          background: "linear-gradient(90deg, transparent, rgba(244,203,147,0.7), transparent)",
          transform: `translateY(${18 + Math.sin(frame * 0.075) * 12}px)`,
        }}
      />
    </div>
  );
};

const KpiOverlays = () => (
  <>
    <CounterPanel
      from={0.25}
      to={17.2}
      title="Global"
      items={[
        {label: "Companies", value: 366, sub: "Active"},
        {label: "Countries", value: 37, sub: "Total"},
        {label: "Products", value: 971, sub: "L1 x 10"},
        {label: "Cities", value: 196, sub: "Mapped"},
      ]}
    />
    <CounterPanel
      from={60.05}
      to={83.4}
      title="USA · North America"
      items={[
        {label: "Companies", value: 58, sub: "In country"},
        {label: "Cities", value: 48, sub: "In country"},
        {label: "Products", value: 187, sub: "In country"},
        {label: "Listed", value: 9, sub: "Public"},
      ]}
    />
  </>
);

const CloseupFrame = ({
  src,
  from,
  duration,
  scaleFrom,
  scaleTo,
  xFrom,
  xTo,
  yFrom,
  yTo,
  background = "#f1ede4",
}: {
  src: string;
  from: number;
  duration: number;
  scaleFrom: number;
  scaleTo: number;
  xFrom: number;
  xTo: number;
  yFrom: number;
  yTo: number;
  background?: string;
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const local = frame - from;
  const entrance = spring({
    frame: local,
    fps,
    config: {damping: 24, stiffness: 125, mass: 0.75},
  });
  const opacity = entrance;
  const scale = clampInterpolate(local, [0, duration], [scaleFrom, scaleTo]);
  const x = clampInterpolate(local, [0, duration], [xFrom, xTo]);
  const y = clampInterpolate(local, [0, duration], [yFrom, yTo]);

  return (
    <AbsoluteFill style={{backgroundColor: background, opacity}}>
      <Img
        src={staticFile(src)}
        style={{
          position: "absolute",
          left: "50%",
          top: "50%",
          maxWidth: "none",
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translate(-50%, -50%) translate(${x}px, ${y}px) scale(${scale})`,
          transformOrigin: "50% 50%",
          filter: "saturate(1.03) contrast(1.02)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(180deg, rgba(21, 16, 28, 0.04), transparent 45%, rgba(21, 16, 28, 0.08)), radial-gradient(circle at 70% 30%, rgba(184,89,87,0.08), transparent 38%)",
        }}
      />
    </AbsoluteFill>
  );
};

const MetricCardsStage = ({from, duration}: {from: number; duration: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from || frame > from + duration) return null;

  const fadeIn = clampInterpolate(frame, [from, from + 18], [0, 1]);
  const fadeOut = clampInterpolate(frame, [from + duration - 18, from + duration], [1, 0]);
  const opacity = Math.min(fadeIn, fadeOut);
  const cards = [
    {kicker: "Product Lines", zh: "产品线", value: 971, note: "38 countries · 10 L1 categories", tint: "#a24740"},
    {kicker: "Upstream Co.", zh: "上游企业", value: 366, note: "manufacturers · brand owners", tint: "#2e455f"},
    {kicker: "Reg. Evidence", zh: "监管注册证据", value: 413, note: "FDA 321 · CE/EU 49", tint: "#a85854"},
    {kicker: "Official Sources", zh: "官方源", value: 19983, note: "deduped to 372 domains", tint: "#58456a"},
  ];

  return (
    <AbsoluteFill style={{opacity, background: "#f1ede4"}}>
      <Img
        src={staticFile("assets/stills/overview-metrics.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          filter: "blur(2px) saturate(0.9) contrast(0.98)",
          opacity: 0.24,
          transform: `scale(${clampInterpolate(frame, [from, from + duration], [1.06, 1.12])})`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(241,237,228,0.94), rgba(241,237,228,0.70) 50%, rgba(241,237,228,0.92)), radial-gradient(circle at 70% 35%, rgba(184,89,87,0.16), transparent 42%)",
        }}
      />
      <div style={{position: "absolute", left: 150, top: 126, right: 150}}>
        <div
          style={{
            color: "#3c3646",
            fontFamily: '"Noto Serif SC", "Microsoft YaHei", serif',
            fontSize: 48,
            lineHeight: 1.1,
            letterSpacing: 0,
          }}
        >
          核心指标
        </div>
        <div
          style={{
            marginTop: 9,
            color: "rgba(60,54,70,0.56)",
            fontFamily: '"Inter", Arial, sans-serif',
            fontSize: 14,
            letterSpacing: 5,
            textTransform: "uppercase",
          }}
        >
          normalized evidence map
        </div>
      </div>
      <div style={{position: "absolute", left: 150, right: 150, top: 286, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 22}}>
        {cards.map((card, index) => {
          const start = from + index * 13;
          const enter = spring({
            frame: Math.max(0, frame - start),
            fps,
            config: {damping: 22, stiffness: 132, mass: 0.78},
          });
          const value = Math.round(card.value * Math.min(1, enter));
          const y = interpolate(enter, [0, 1], [48, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});
          return (
            <div
              key={card.kicker}
              style={{
                minHeight: 250,
                borderRadius: 18,
                border: "1px solid rgba(82,75,89,0.12)",
                background: "rgba(255,252,245,0.78)",
                boxShadow: "0 26px 80px rgba(45,38,31,0.10)",
                padding: "34px 34px 30px",
                opacity: Math.min(1, enter),
                transform: `translateY(${y}px)`,
                overflow: "hidden",
                position: "relative",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  right: -20,
                  top: -24,
                  width: 160,
                  height: 160,
                  borderRadius: 999,
                  background: card.tint,
                  opacity: 0.08 + Math.sin(frame * 0.06 + index) * 0.015,
                  filter: "blur(8px)",
                }}
              />
              <div
                style={{
                  color: "rgba(60,54,70,0.64)",
                  fontFamily: '"Inter", Arial, sans-serif',
                  fontSize: 12,
                  fontWeight: 760,
                  letterSpacing: 5,
                  textTransform: "uppercase",
                }}
              >
                {card.kicker}
              </div>
              <div
                style={{
                  marginTop: 9,
                  color: "#68606e",
                  fontFamily: '"Microsoft YaHei", sans-serif',
                  fontSize: 16,
                  fontWeight: 520,
                }}
              >
                {card.zh}
              </div>
              <div
                style={{
                  marginTop: 28,
                  color: card.tint,
                  fontFamily: '"Georgia", "Times New Roman", serif',
                  fontSize: card.value > 9999 ? 62 : 78,
                  lineHeight: 0.95,
                  fontStyle: "italic",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {formatNumber(value)}
              </div>
              <div
                style={{
                  marginTop: 28,
                  color: "rgba(60,54,70,0.58)",
                  fontFamily: '"Inter", Arial, sans-serif',
                  fontSize: 14,
                }}
              >
                {card.note}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const RegionSwitchStage = ({from, duration}: {from: number; duration: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from || frame > from + duration) return null;

  const fadeIn = clampInterpolate(frame, [from, from + 12], [0, 1]);
  const fadeOut = clampInterpolate(frame, [from + duration - 12, from + duration], [1, 0]);
  const opacity = Math.min(fadeIn, fadeOut);
  const rows = [
    ["EBD · 光电", "480", "largest L1 category"],
    ["Injectables · 注射", "328", "second-largest supply lane"],
    ["Skincare · 护肤", "79", "brand-heavy segment"],
    ["Regenerative · 再生", "28", "specialized long tail"],
  ];

  return (
    <AbsoluteFill style={{opacity, background: "#f1ede4"}}>
      <Img
        src={staticFile("assets/stills/overview-tracks.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translate(${clampInterpolate(frame, [from, from + duration], [0, -52])}px, ${clampInterpolate(frame, [from, from + duration], [-20, -42])}px) scale(${clampInterpolate(frame, [from, from + duration], [1.04, 1.12])})`,
          filter: "saturate(1.03) contrast(1.02)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(90deg, rgba(241,237,228,0.04), rgba(241,237,228,0.55) 58%, rgba(241,237,228,0.86))",
        }}
      />
      <div
        style={{
          position: "absolute",
          right: 112,
          top: 142,
          width: 560,
          padding: "34px 38px",
          borderRadius: 18,
          border: "1px solid rgba(82,75,89,0.12)",
          background: "rgba(255,252,245,0.82)",
          boxShadow: "0 30px 90px rgba(45,38,31,0.13)",
        }}
      >
        <div style={{fontFamily: '"Noto Serif SC", "Microsoft YaHei", serif', fontSize: 38, color: "#3d3546"}}>赛道结构</div>
        <div style={{marginTop: 8, fontFamily: '"Inter", Arial, sans-serif', fontSize: 12, letterSpacing: 5, color: "#9d5560", textTransform: "uppercase"}}>
          product-line distribution
        </div>
        <div style={{marginTop: 28}}>
          {rows.map((row, index) => {
            const start = from + 10 + index * 9;
            const reveal = spring({
              frame: Math.max(0, frame - start),
              fps,
              config: {damping: 21, stiffness: 125, mass: 0.8},
            });
            return (
              <div
                key={row[0]}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 86px",
                  gap: 20,
                  alignItems: "baseline",
                  padding: "16px 0",
                  borderBottom: "1px solid rgba(82,75,89,0.12)",
                  opacity: Math.min(1, reveal),
                  transform: `translateX(${interpolate(reveal, [0, 1], [34, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}px)`,
                }}
              >
                <div>
                  <div style={{fontFamily: '"Microsoft YaHei", sans-serif', fontSize: 20, fontWeight: 680, color: "#403846"}}>{row[0]}</div>
                  <div style={{marginTop: 5, fontFamily: '"Inter", Arial, sans-serif', fontSize: 12, color: "rgba(64,56,70,0.55)"}}>{row[2]}</div>
                </div>
                <div style={{fontFamily: '"Georgia", serif', fontSize: 34, fontStyle: "italic", color: "#a24740", textAlign: "right"}}>{row[1]}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const BrandEndCard = ({from, duration}: {from: number; duration: number}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  if (frame < from || frame > from + duration) return null;
  const fadeIn = clampInterpolate(frame, [from, from + 20], [0, 1]);
  const fadeOut = clampInterpolate(frame, [from + duration - 22, from + duration], [1, 0]);
  const opacity = Math.min(fadeIn, fadeOut);
  const enter = spring({
    frame: Math.max(0, frame - from),
    fps,
    config: {damping: 25, stiffness: 112, mass: 0.86},
  });
  const scale = interpolate(enter, [0, 1], [0.94, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"});

  return (
    <AbsoluteFill
      style={{
        opacity,
        background:
          "radial-gradient(circle at 30% 20%, rgba(184,89,87,0.18), transparent 32%), radial-gradient(circle at 76% 38%, rgba(46,69,95,0.16), transparent 30%), #f1ede4",
        color: "#26395a",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div style={{transform: `translateY(${interpolate(enter, [0, 1], [18, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}px) scale(${scale})`, textAlign: "center"}}>
        <Img
          src={staticFile("assets/brand/aesthetic-reflections.png")}
          style={{
            width: 720,
            maxWidth: "72vw",
            height: "auto",
            objectFit: "contain",
            filter: "drop-shadow(0 22px 34px rgba(38,57,90,0.10))",
          }}
        />
        <div
          style={{
            marginTop: 34,
            width: 480,
            height: 1,
            marginLeft: "auto",
            marginRight: "auto",
            background: "linear-gradient(90deg, transparent, rgba(42,61,96,0.22), transparent)",
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

const CloseupMontage = () => {
  const {fps} = useVideoConfig();
  const fStart = 100 * fps;
  return (
    <>
      <CloseupFrame
        src="assets/stills/overview-hero.png"
        from={Math.round(fStart)}
        duration={Math.round(2.7 * fps)}
        scaleFrom={1.2}
        scaleTo={1.29}
        xFrom={230}
        xTo={180}
        yFrom={88}
        yTo={64}
      />
      <MetricCardsStage from={Math.round(102.5 * fps)} duration={Math.round(4.3 * fps)} />
      <CloseupFrame
        src="assets/stills/overview-rail.png"
        from={Math.round(106.5 * fps)}
        duration={Math.round(1.8 * fps)}
        scaleFrom={1.12}
        scaleTo={1.24}
        xFrom={470}
        xTo={410}
        yFrom={0}
        yTo={-20}
        background="#100b17"
      />
      <RegionSwitchStage from={Math.round(107.35 * fps)} duration={Math.round(2.65 * fps)} />
      <BrandEndCard from={Math.round(110 * fps)} duration={Math.round(3 * fps)} />
      <AbsoluteFill
        style={{
          background: "linear-gradient(90deg, rgba(16, 11, 23, 0.18), transparent 25%, transparent 75%, rgba(16, 11, 23, 0.12))",
          pointerEvents: "none",
        }}
      />
    </>
  );
};

const GlobeMatte = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const visible = clampInterpolate(frame, [100 * fps, 100.65 * fps], [1, 0]);
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 78,
        opacity: visible,
        background: "#100b17",
        pointerEvents: "none",
      }}
    />
  );
};

const AudioMix = () => {
  const frame = useCurrentFrame();
  const {durationInFrames, fps} = useVideoConfig();
  const musicFadeIn = clampInterpolate(frame, [0, 80], [0, 0.18]);
  const musicFadeOut = clampInterpolate(frame, [durationInFrames - 120, durationInFrames - 1], [0.18, 0]);
  const voiceFadeIn = clampInterpolate(frame, [0, 20], [0, 1]);
  const voiceFadeOut = clampInterpolate(frame, [durationInFrames - 36, durationInFrames - 1], [1, 0]);
  const brandVolume = Math.min(
    clampInterpolate(frame, [110 * fps, 110 * fps + 12], [0, 0.98]),
    clampInterpolate(frame, [durationInFrames - 16, durationInFrames - 1], [0.98, 0]),
  );
  return (
    <>
      <Audio src={staticFile("assets/audio/tech-pulse-bed.wav")} volume={Math.min(musicFadeIn, musicFadeOut)} />
      <Audio src={staticFile("assets/audio/voiceover-en.wav")} volume={Math.min(voiceFadeIn, voiceFadeOut)} />
      <Sequence from={110 * fps} durationInFrames={3 * fps}>
        <Audio src={staticFile("assets/audio/brand-voiceover-en.wav")} volume={brandVolume} />
      </Sequence>
    </>
  );
};

export const GlobalAestheticsGlobeDemo = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const closeupOpacity = clampInterpolate(frame, [100 * fps, 100.65 * fps], [0, 1]);
  return (
    <AbsoluteFill style={{backgroundColor: "#100b17", overflow: "hidden"}}>
      <GlobeFootage />
      <GlobeMatte />
      <AbsoluteFill style={{opacity: closeupOpacity}}>
        <CloseupMontage />
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background:
            "linear-gradient(180deg, rgba(10, 7, 15, 0.10) 0%, transparent 28%, transparent 65%, rgba(10, 7, 15, 0.38) 100%)",
        }}
      />
      <DataGlint />
      <KpiOverlays />
      <CaptionLayer />
      <ProgressLine />
      <AudioMix />
    </AbsoluteFill>
  );
};

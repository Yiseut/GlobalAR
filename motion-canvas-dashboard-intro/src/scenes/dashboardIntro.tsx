import {Circle, Line, Rect, Txt, makeScene2D} from '@motion-canvas/2d';
import {createRef, waitFor} from '@motion-canvas/core';

const c = {
  bg: '#efeae0',
  surface: '#f7f1e6',
  card: '#fdfaf2',
  ink: '#3a3340',
  muted: '#6a5d68',
  subtle: '#998f9b',
  hairline: 'rgba(80, 60, 70, 0.18)',
  accent: '#b85957',
  accentDeep: '#8e3a3a',
  plum: '#4a3d52',
  sidebar: '#140f1f',
  sidebarPanel: '#4a2029',
  gold: '#e4b867',
  washRose: '#eac1bf',
  washPlum: '#dcd2df',
  washPeach: '#f4d8c0',
  washSage: '#dbe3d2',
  washSlate: '#cfd8e0',
  washSand: '#e8dbc4',
};

const serif = 'Noto Serif SC, Songti SC, SimSun, Georgia, serif';
const display = 'Marcellus, Noto Serif SC, Georgia, serif';
const sans = 'DM Sans, Microsoft YaHei, Segoe UI, sans-serif';
const mono = 'DM Mono, Space Mono, Consolas, monospace';

function Topbar() {
  const nav = ['总览', '监管脉搏', '地域深掘', '资本地图', '赛道', '公司', '证据'];
  return (
    <Rect x={0} y={-516} width={1920} height={48} fill={c.surface} stroke={c.hairline} lineWidth={1}>
      <Rect x={-918} width={22} height={22} radius={5} fill={c.accentDeep}>
        <Txt text={'研'} fontFamily={serif} fontSize={14} fill={'#fff8ef'} />
      </Rect>
      <Txt text={'全球医美情报'} x={-850} fontFamily={serif} fontSize={15} fill={c.ink} />
      <Txt text={'AESTHETIC REFLECTIONS'} x={-735} fontFamily={mono} fontSize={7} letterSpacing={7} fill={c.subtle} />
      {nav.map((item, index) => (
        <Txt
          text={item}
          x={615 + index * 52}
          y={0}
          fontFamily={sans}
          fontSize={10}
          fill={index === 0 ? c.accentDeep : c.ink}
        />
      ))}
    </Rect>
  );
}

function Sidebar() {
  const rows = [
    ['总览', ''],
    ['监管脉搏', '411'],
    ['地域深掘', '38 国'],
    ['资本地图', '61'],
    ['赛道结构', '10 L1'],
    [''],
    ['公司列表', '372'],
    ['适应症星图', '958'],
    ['技术树', '-'],
    ['证据库 · INT', '1,182'],
    [''],
    ['光电 EBD', '480'],
    ['注射 Injectables', '328'],
    ['再生 Regen', '28'],
    ['护肤 Skincare', '79'],
  ];

  return (
    <Rect x={-876} y={24} width={168} height={1032} fill={c.sidebar}>
      <Txt text={'• 情报视角'} x={-47} y={-440} fontFamily={sans} fontSize={10} fill={c.subtle} />
      {rows.map((row, index) => {
        const y = -410 + index * 36;
        if (!row[0]) {
          return <Txt text={'•'} x={-70} y={y + 8} fontFamily={sans} fontSize={18} fill={c.gold} />;
        }
        const active = index === 0;
        return (
          <Rect x={0} y={y} width={146} height={31} radius={5} fill={active ? c.sidebarPanel : 'rgba(0,0,0,0)'}>
            {active ? <Line points={[[-73, 0], [-73, 0]]} stroke={c.gold} lineWidth={4} /> : null}
            <Txt text={row[0]} x={-46} fontFamily={sans} fontSize={11} fontWeight={active ? 700 : 400} fill={active ? '#fff7ec' : '#d9d0d7'} />
            <Txt text={row[1]} x={53} fontFamily={mono} fontSize={9} fill={c.subtle} />
          </Rect>
        );
      })}
    </Rect>
  );
}

function MetricCard({
  x,
  y,
  label,
  title,
  value,
  note,
  wash,
  accent = c.ink,
}: {
  x: number;
  y: number;
  label: string;
  title: string;
  value: string;
  note: string;
  wash: string;
  accent?: string;
}) {
  return (
    <Rect x={x} y={y} width={360} height={145} radius={10} fill={c.card} stroke={c.hairline} lineWidth={1}>
      <Circle x={126} y={-42} size={120} fill={wash} opacity={0.35} />
      <Txt text={label} x={-118} y={-50} fontFamily={mono} fontSize={9} letterSpacing={6} fill={c.subtle} />
      <Txt text={title} x={-121} y={-27} fontFamily={serif} fontSize={12} fill={c.ink} />
      <Txt text={value} x={-118} y={19} fontFamily={display} fontSize={43} fill={accent} />
      <Txt text={note} x={-117} y={58} fontFamily={sans} fontSize={9} fill={c.muted} />
    </Rect>
  );
}

function Chip({x, text, active = false}: {x: number; text: string; active?: boolean}) {
  return (
    <Rect x={x} y={-137} width={active ? 82 : 116} height={28} radius={14} fill={active ? c.plum : 'rgba(255,255,255,0.28)'} stroke={c.hairline} lineWidth={1}>
      <Txt text={text} fontFamily={sans} fontSize={10} fill={active ? '#fffaf1' : c.muted} />
    </Rect>
  );
}

function OverviewPage({dim = false}: {dim?: boolean}) {
  return (
    <Rect width={1920} height={1080} fill={c.bg} opacity={dim ? 0.42 : 1}>
      <Topbar />
      <Sidebar />

      <Rect x={86} y={20} width={1664} height={940} fill={'rgba(0,0,0,0)'}>
        <Txt text={'• 全球情报 · 2026 VOL. 02'} x={-642} y={-405} fontFamily={mono} fontSize={10} letterSpacing={5} fill={c.accent} />
        <Txt text={'全球医美产业图谱'} x={-505} y={-350} fontFamily={serif} fontSize={58} fill={c.ink} />
        <Txt text={'Global Medical Aesthetics Landscape'} x={-500} y={-292} fontFamily={display} fontStyle={'italic'} fontSize={28} fill={c.muted} />
        <Txt text={'注射 · 光电 · 再生 · 护肤 · 植入物 · 耗材 — 上游品牌、监管、规格与官方源的一体化情报。'} x={-400} y={-248} fontFamily={serif} fontSize={15} fill={c.ink} />
        <Txt text={'全球 366 家上游企业 · 971 款产品线      覆盖 37 个国家 / 地区      监管证据 413 条 · FDA 主导'} x={-392} y={-203} fontFamily={serif} fontSize={14} fill={c.ink} />
        <Chip x={-594} text={'全部 977'} active />
        <Chip x={-488} text={'光电 EBD 480'} />
        <Chip x={-360} text={'注射 Injectables 328'} />
        <Chip x={-214} text={'护肤 Skincare 79'} />
        <Chip x={-82} text={'再生 Regen 28'} />
        <Chip x={48} text={'植入物 Implants 19'} />
        <Line points={[[-650, -78], [845, -78]]} stroke={c.hairline} lineWidth={1} />

        <Txt text={'核心指标'} x={-606} y={-26} fontFamily={serif} fontSize={26} fill={c.ink} />
        <Txt text={'· 规范化数据'} x={-523} y={-25} fontFamily={serif} fontSize={11} fill={c.subtle} />
        <Txt text={'▪ CORE METRICS · NORMALIZED'} x={720} y={-26} fontFamily={mono} fontSize={8} letterSpacing={5} fill={c.subtle} />

        <MetricCard x={-472} y={92} label={'PRODUCT LINES'} title={'产品线 · 全球覆盖'} value={'971'} note={'38 countries · 10 L1 categories'} wash={c.washRose} accent={c.accentDeep} />
        <MetricCard x={-80} y={92} label={'UPSTREAM CO.'} title={'上游企业'} value={'366'} note={'manufacturers · brand owners'} wash={c.washSlate} />
        <MetricCard x={312} y={92} label={'LISTED ENTITIES'} title={'上市主体'} value={'61'} note={'15 exchanges · KRX leads'} wash={c.washPeach} />
        <MetricCard x={704} y={92} label={'BRANDS'} title={'品牌'} value={'939'} note={'881 product · 96 corporate'} wash={c.washSand} />

        <MetricCard x={-472} y={257} label={'INDICATION SIGNALS'} title={'适应症信号'} value={'958'} note={'cross-ref product master'} wash={c.washPlum} />
        <MetricCard x={-80} y={257} label={'REG. EVIDENCE'} title={'监管注册证据'} value={'413'} note={'FDA 321 · CE/EU 49'} wash={c.washRose} />
        <MetricCard x={312} y={257} label={'PRODUCT SPECS'} title={'产品规格证据'} value={'52,254'} note={'362 companies covered'} wash={c.washSage} />
        <MetricCard x={704} y={257} label={'OFFICIAL SOURCES'} title={'官方源'} value={'19,983'} note={'deduped to 372 domains'} wash={c.washPlum} />

        <Txt text={'编辑视角'} x={-606} y={410} fontFamily={serif} fontSize={26} fill={c.ink} />
        <Txt text={'· 三组新发现'} x={-523} y={411} fontFamily={serif} fontSize={11} fill={c.subtle} />
        <Txt text={'▪ EDITORIAL · NEW LENSES FROM RE-SCAN'} x={676} y={411} fontFamily={mono} fontSize={8} letterSpacing={5} fill={c.subtle} />
      </Rect>
    </Rect>
  );
}

function Callout({x, y, title, body}: {x: number; y: number; title: string; body: string}) {
  return (
    <Rect x={x} y={y} width={440} height={132} radius={10} fill={'rgba(253,250,242,0.96)'} stroke={c.accentDeep} lineWidth={1.5}>
      <Txt text={title} x={-185} y={-34} fontFamily={serif} fontSize={24} fill={c.accentDeep} />
      <Txt text={body} x={-1} y={24} width={370} textAlign={'left'} fontFamily={sans} fontSize={16} lineHeight={24} fill={c.ink} />
    </Rect>
  );
}

function RouteMap() {
  const items = ['总览', '监管', '地域', '资本', '赛道', '公司', '证据'];
  return (
    <Rect width={1920} height={1080} fill={c.bg}>
      <Topbar />
      <Sidebar />
      <Txt text={'把介绍视频做成一条阅读路线'} x={-202} y={-245} fontFamily={serif} fontSize={54} fill={c.ink} />
      <Txt text={'不要只快闪局部，而是让观众知道这个仪表盘如何被使用。'} x={-200} y={-184} fontFamily={serif} fontSize={20} fill={c.muted} />
      <Rect x={90} y={78} width={1180} height={360} radius={14} fill={c.card} stroke={c.hairline} lineWidth={1}>
        {items.map((item, index) => {
          const x = -485 + index * 162;
          return (
            <>
              <Circle x={x} y={-30} size={70} fill={index === 0 ? c.accentDeep : '#f5eadf'} stroke={c.hairline} lineWidth={1} />
              <Txt text={`${index + 1}`} x={x} y={-30} fontFamily={display} fontSize={28} fill={index === 0 ? '#fffaf1' : c.accentDeep} />
              <Txt text={item} x={x} y={66} fontFamily={serif} fontSize={22} fill={c.ink} />
              {index < items.length - 1 ? <Line points={[[x + 42, -30], [x + 118, -30]]} stroke={c.hairline} lineWidth={2} /> : null}
            </>
          );
        })}
      </Rect>
    </Rect>
  );
}

function EvidencePage() {
  return (
    <Rect width={1920} height={1080} fill={c.bg}>
      <Topbar />
      <Sidebar />
      <Txt text={'最后落在证据链：为什么这些数可信'} x={-192} y={-260} fontFamily={serif} fontSize={50} fill={c.ink} />
      <Txt text={'Motion Canvas 可以把网页里的“证据库”改写成更适合视频理解的流程。'} x={-190} y={-202} fontFamily={serif} fontSize={19} fill={c.muted} />
      <Rect x={90} y={72} width={1160} height={430} radius={14} fill={c.card} stroke={c.hairline} lineWidth={1}>
        <Rect x={-355} y={-10} width={240} height={150} radius={10} fill={'#fbefe7'}>
          <Txt text={'来源'} y={-30} fontFamily={serif} fontSize={32} fill={c.accentDeep} />
          <Txt text={'官网 / FDA / CE'} y={25} fontFamily={sans} fontSize={16} fill={c.muted} />
        </Rect>
        <Line points={[[-214, -10], [-92, -10]]} stroke={c.accentDeep} lineWidth={3} endArrow />
        <Rect x={55} y={-10} width={240} height={150} radius={10} fill={'#f8f0d9'}>
          <Txt text={'清洗'} y={-30} fontFamily={serif} fontSize={32} fill={c.accentDeep} />
          <Txt text={'去重 / 归类 / 摘要'} y={25} fontFamily={sans} fontSize={16} fill={c.muted} />
        </Rect>
        <Line points={[[196, -10], [318, -10]]} stroke={c.accentDeep} lineWidth={3} endArrow />
        <Rect x={465} y={-10} width={240} height={150} radius={10} fill={'#edf3ea'}>
          <Txt text={'下钻'} y={-30} fontFamily={serif} fontSize={32} fill={c.accentDeep} />
          <Txt text={'企业 / 产品 / 地域'} y={25} fontFamily={sans} fontSize={16} fill={c.muted} />
        </Rect>
        <Txt text={'一句介绍视频里的判断，最后都能回到网页中的来源、证据和可复核记录。'} y={160} fontFamily={serif} fontSize={25} fill={c.ink} />
      </Rect>
    </Rect>
  );
}

export default makeScene2D(function* (view) {
  view.fill(c.bg);

  const overview = createRef<Rect>();
  const metricOverlay = createRef<Rect>();
  const route = createRef<Rect>();
  const evidence = createRef<Rect>();
  const end = createRef<Rect>();

  view.add(
    <>
      <Rect ref={overview} width={1920} height={1080}>
        <OverviewPage />
      </Rect>

      <Rect ref={metricOverlay} width={1920} height={1080} opacity={0}>
        <OverviewPage dim />
        <Rect x={36} y={175} width={1536} height={340} radius={14} stroke={c.accentDeep} lineWidth={4} fill={'rgba(0,0,0,0)'} />
        <Callout x={442} y={-210} title={'核心指标先建立尺度'} body={'开场 15 秒内抓住产品线、企业、国家和证据四组数字，让观众知道这是产业图谱。'} />
      </Rect>

      <Rect ref={route} width={1920} height={1080} opacity={0}>
        <RouteMap />
      </Rect>

      <Rect ref={evidence} width={1920} height={1080} opacity={0}>
        <EvidencePage />
      </Rect>

      <Rect ref={end} width={1920} height={1080} fill={c.bg} opacity={0}>
        <Topbar />
        <Sidebar />
        <Txt text={'整支介绍视频的方向'} x={-150} y={-180} fontFamily={serif} fontSize={56} fill={c.ink} />
        <Txt
          text={'保留真实仪表盘风格，用 Motion Canvas 做镜头推进、重点圈选、数字转场和旁白节奏。'}
          x={-150}
          y={-100}
          width={980}
          textAlign={'center'}
          fontFamily={serif}
          fontSize={27}
          lineHeight={42}
          fill={c.muted}
        />
        <Rect x={-150} y={105} width={820} height={185} radius={12} fill={c.card} stroke={c.hairline} lineWidth={1}>
          <Txt text={'下一步：把每个页面截成真实素材'} y={-40} fontFamily={serif} fontSize={33} fill={c.accentDeep} />
          <Txt text={'总览 / 监管脉搏 / 地域深掘 / 赛道 / 公司 / 证据，各自做 8-12 秒。'} y={35} fontFamily={sans} fontSize={20} fill={c.ink} />
        </Rect>
      </Rect>
    </>,
  );

  yield* waitFor(7);
  yield* metricOverlay().opacity(1, 0.55);
  yield* waitFor(8);
  yield* metricOverlay().opacity(0, 0.45);
  yield* overview().opacity(0, 0.45);
  yield* route().opacity(1, 0.6);
  yield* waitFor(8);
  yield* route().opacity(0, 0.45);
  yield* evidence().opacity(1, 0.6);
  yield* waitFor(8);
  yield* evidence().opacity(0, 0.45);
  yield* end().opacity(1, 0.6);
  yield* waitFor(6);
});

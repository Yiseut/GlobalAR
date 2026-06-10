export type SubtitleCue = {
  start: number;
  end: number;
  text: string;
};

export const subtitles: SubtitleCue[] = [
  {
    start: 0.6,
    end: 6.7,
    text: "971 条产品线、366 家企业，勾勒全球医美供给网络。",
  },
  {
    start: 7.2,
    end: 17.4,
    text: "欧洲、北美与东亚，形成三处高密度企业带。",
  },
  {
    start: 18.2,
    end: 27.5,
    text: "从产品线到企业数，规模重心在地图上重新排布。",
  },
  {
    start: 28.5,
    end: 39.5,
    text: "注射材料是跨区域竞争最密集的赛道之一。",
  },
  {
    start: 40.4,
    end: 52.5,
    text: "韩国样本显示：50 家企业集中在 9 个城市。",
  },
  {
    start: 53.2,
    end: 59.4,
    text: "一张图看清区域集中度、赛道结构与企业版图。",
  },
];

export const formatSrtTime = (seconds: number) => {
  const safe = Math.max(0, seconds);
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const wholeSeconds = Math.floor(safe % 60);
  const millis = Math.round((safe - Math.floor(safe)) * 1000);
  return [hours, minutes, wholeSeconds]
    .map((part) => String(part).padStart(2, "0"))
    .join(":") + `,${String(millis).padStart(3, "0")}`;
};

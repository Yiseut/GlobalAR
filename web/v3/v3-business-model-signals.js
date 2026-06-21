window.V3_BUSINESS_MODEL_SIGNALS = {
  updatedAt: "2026-06-21",
  sources: [
    {
      sourceId: "asiae_korea_medical_tourism_exports_20260621",
      title: "Foreign Big Spenders Flock to Korean Dermatology Clinics and Pharmacies",
      publisher: "Asia Business Daily",
      date: "2026-06-21",
      url: "https://www.asiae.co.kr/en/article/stock-etc/2026061819415596313",
      status: "news_secondary_needs_official_verification",
      note: "The article cites DB Financial Investment. Treat as business-model signal until official Korea MOHW/KHIDI/KHISS or customs data is verified."
    }
  ],
  countries: [
    {
      country: "South Korea",
      countryZh: "韩国",
      period: "2026-05",
      modelLabel: "入境消费 + 出口双轮驱动",
      modelTags: ["export-led", "inbound-medical-tourism-led"],
      verificationStatus: "待官方核验",
      sourceId: "asiae_korea_medical_tourism_exports_20260621",
      inboundSpendKrwBn: [
        { name: "皮肤科/医美服务", value: 145.2, share: 57.8, yoy: 46.4 },
        { name: "药房/功效护肤", value: 32.5, share: 12.9, yoy: 172.1 },
        { name: "其他医疗旅游", value: 73.5, share: 29.3, derived: true }
      ],
      inboundDemand: [
        { name: "医疗旅游消费", value: 251.2, unit: "KRW bn", yoy: 44.0 },
        { name: "医疗旅游病例", value: 597000, unit: "cases", yoy: 63.0 },
        { name: "皮肤科消费", value: 145.2, unit: "KRW bn", yoy: 46.4 },
        { name: "药房消费", value: 32.5, unit: "KRW bn", yoy: 172.1 }
      ],
      exportCategoriesUsdM: [
        { name: "填充剂", value: 336.4, yoy: 40.2 },
        { name: "EBD", value: 95.4, yoy: 14.0 },
        { name: "毒素", value: 50.2, yoy: 14.1 }
      ],
      exportTotal: { name: "医疗及医美产品出口", value: 480.0, unit: "USD mn", yoy: 31.1 },
      ebdDestinationsUsdM: [
        { name: "美国", value: 20.6, yoy: 13.9, mom: 43.5 },
        { name: "巴西", value: 6.3, yoy: 140.8, mom: 66.1 }
      ],
      interpretation: "韩国的可见样本显示，医美商业增长不只来自本土治疗需求，也来自外国人在韩消费和产品出口同步拉动。后续可用同一框架对比中国内销驱动、美国全球品牌平台和欧洲区域出口/本土服务结构。"
    }
  ],
  comparisonPlaceholders: [
    {
      country: "China",
      countryZh: "中国",
      modelLabel: "内销需求驱动",
      status: "待补可比出口与入境消费口径",
      note: "先作为假设对照，不在图表中给数值。"
    },
    {
      country: "USA",
      countryZh: "美国",
      modelLabel: "高价值本土消费 + 全球品牌平台",
      status: "待补可比出口/海外收入口径",
      note: "可用上市公司地区收入、ASPS/Aesthetic Society 和 IR 报告交叉验证。"
    },
    {
      country: "Europe",
      countryZh: "欧洲",
      modelLabel: "区域多中心 + 品牌出口",
      status: "待补国家级来源",
      note: "可从法国、瑞士、意大利、德国和西班牙逐步补齐。"
    }
  ]
};

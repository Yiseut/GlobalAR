"""Build a readable next user-confirmation package from current review queues."""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "data" / "audits"
PRODUCT_GAP_QUEUE = AUDIT_DIR / "product_gap_queue_latest.csv"
KOREA_QUEUE = AUDIT_DIR / "korea_mfds_confirmation_queue_latest.csv"
OUT_CSV_LATEST = AUDIT_DIR / "next_user_confirmation_batch_latest.csv"
OUT_HTML_LATEST = AUDIT_DIR / "next_user_confirmation_batch_latest.html"
OUT_JSON_LATEST = AUDIT_DIR / "next_user_confirmation_batch_latest.json"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def url_host(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def group_for(row: dict[str, str]) -> tuple[str, str]:
    company = clean(row.get("company"))
    form = clean(row.get("form")).lower()
    track = clean(row.get("track")).lower()
    technology = clean(row.get("technology")).lower()
    brand = clean(row.get("brand")).lower()

    if clean(row.get("korea_p1")) == "yes":
        if "biostimulator" in form or any(token in technology for token in ["plla", "pdlla", "pla"]):
            return ("韩国再生材料/MFDS P1", "先确认产品身份，再补韩国 MFDS/KFDA；若只是分销/弱线索就排除。")
        if track == "ebd":
            return ("韩国光电设备/MFDS P1", "确认是否真实韩国上游设备产品线，再补 MFDS/KFDA 或标记无公开证号。")
        if track in {"surgical", "consumables"}:
            return ("韩国手术耗材/MFDS P1", "确认是否属于医美上游核心耗材；非核心通用耗材可排除或并入。")
        return ("韩国注射/耗材/MFDS P1", "确认产品身份与是否纳入，再补 MFDS/KFDA 或标记无公开证号。")

    if "hyaluronic" in technology or "dermal filler" in form or any(token in brand for token in ["juv", "restylane", "perfectha"]):
        return ("主流 HA 填充剂", "通常是核心产品线；请确认是否补入官方适应证/监管，还是并入既有大品牌家族。")
    if "biostimulator" in form or any(token in technology for token in ["plla", "pdlla", "collagen"]):
        return ("再生材料/生物刺激剂", "确认是否作为独立产品线保留，并给官方适应证与 CE/KFDA/FDA 状态。")
    if track == "ebd":
        return ("光电/能量源设备", "确认设备是否真实医美上游产品线，并补官方适应证/监管；弱代理或院端服务可排除。")
    if track in {"surgical", "consumables"}:
        return ("手术/脂肪移植/耗材", "确认是否属于医美上游核心器械耗材；通用外科或弱线索可排除。")
    if track == "skincare":
        return ("专业护肤/术后修护", "确认是否院线/医美机构使用的专业产品线；普通护肤或下游项目可排除。")
    return ("其他高优先级待核", "请按是否医美上游、是否独立产品线、是否有官方适应证/监管来判断。")


def suggested_options(row: dict[str, str]) -> str:
    company = clean(row.get("company"))
    brand = clean(row.get("brand"))
    form = clean(row.get("form")).lower()
    track = clean(row.get("track")).lower()
    needs_mfds = clean(row.get("korea_p1")) == "yes"
    options = ["确认保留并补官方适应证/监管"]
    if needs_mfds:
        options.append("确认保留；韩国 MFDS/KFDA 无公开证号")
    if track in {"surgical", "consumables"} or "needle" in brand.lower() or "implant" in form:
        options.append("并入现有产品/作为 SKU 或配件")
    options.append("排除-非医美/非上游/弱线索")
    options.append("先查证")
    return "；".join(options)


def issue_cn(row: dict[str, str]) -> str:
    issue_map = {
        "master_unverified_seed": "主表仍是 seed/未核身份",
        "no_direct_official_product_or_family_url": "缺直接官网产品页",
        "no_direct_spec_candidate": "缺直接规格/IFU候选",
        "no_registration_evidence": "缺注册证据",
        "no_official_indication": "缺官方适应证",
        "no_reviewed_differentiator": "缺已核差异化/规格点",
        "priority_company": "重点公司/重点产品",
        "has_review_leads": "已有线索但未能直接落库",
    }
    parts = [clean(part) for part in clean(row.get("issues")).split("|") if clean(part)]
    labels = [issue_map.get(part, part) for part in parts]
    if clean(row.get("korea_p1")) == "yes":
        labels.append("韩国 MFDS/KFDA P1：需先核产品身份")
    return "；".join(labels)


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    product_rows = [
        row for row in read_csv(PRODUCT_GAP_QUEUE)
        if clean(row.get("priority")) in {"P0", "P1"}
    ]
    korea_p1 = {
        clean(row.get("seed_record_id")): row
        for row in read_csv(KOREA_QUEUE)
        if clean(row.get("priority")) == "P1"
    }

    by_seed: dict[str, dict[str, str]] = {}
    for row in product_rows:
        seed = clean(row.get("seed_record_id"))
        if not seed:
            continue
        merged = dict(row)
        if seed in korea_p1:
            merged["korea_p1"] = "yes"
            merged["korea_status"] = clean(korea_p1[seed].get("status"))
        by_seed[seed] = merged
    for seed, row in korea_p1.items():
        if seed in by_seed:
            continue
        by_seed[seed] = {
            "priority": "K-P1",
            "gap_score": "0",
            "company": clean(row.get("company")),
            "brand": clean(row.get("brand")),
            "standard_product_name": clean(row.get("standard_product_name")),
            "product_id": clean(row.get("product_id")),
            "seed_record_id": seed,
            "track": clean(row.get("track")),
            "form": clean(row.get("form")),
            "technology": "",
            "verification_status": clean(row.get("verification_status")),
            "lead_official_url": "",
            "lead_spec_url": "",
            "issues": "korea_mfds_p1",
            "recommended_next_action": clean(row.get("recommended_action")),
            "korea_p1": "yes",
            "korea_status": clean(row.get("status")),
        }

    rows: list[dict[str, str]] = []
    for index, row in enumerate(
        sorted(
            by_seed.values(),
            key=lambda item: (
                0 if clean(item.get("priority")) == "P0" else 1 if clean(item.get("priority")) == "P1" else 2,
                -int(clean(item.get("gap_score")) or "0"),
                clean(item.get("company")).lower(),
                clean(item.get("brand")).lower(),
            ),
        ),
        start=1,
    ):
        group, group_instruction = group_for(row)
        lead_url = clean(row.get("lead_official_url")) or clean(row.get("lead_spec_url")) or clean(row.get("lead_registration_url"))
        rows.append(
            {
                "confirm_id": f"NEXT-{index:03d}",
                "group": group,
                "group_instruction": group_instruction,
                "priority": clean(row.get("priority")),
                "gap_score": clean(row.get("gap_score")),
                "seed_record_id": clean(row.get("seed_record_id")),
                "company": clean(row.get("company")),
                "brand": clean(row.get("brand")),
                "original_product_name": clean(row.get("standard_product_name")),
                "track": clean(row.get("track")),
                "form": clean(row.get("form")),
                "technology": clean(row.get("technology")),
                "current_problem": issue_cn(row),
                "lead_url": lead_url,
                "lead_domain": url_host(lead_url),
                "recommended_action": clean(row.get("recommended_next_action")),
                "suggested_user_reply_options": suggested_options(row),
                "korea_p1": clean(row.get("korea_p1")),
                "korea_status": clean(row.get("korea_status")),
            }
        )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = AUDIT_DIR / f"next_user_confirmation_batch_{stamp}.csv"
    out_html = AUDIT_DIR / f"next_user_confirmation_batch_{stamp}.html"
    out_json = AUDIT_DIR / f"next_user_confirmation_batch_{stamp}.json"
    fields = [
        "confirm_id",
        "group",
        "group_instruction",
        "priority",
        "gap_score",
        "seed_record_id",
        "company",
        "brand",
        "original_product_name",
        "track",
        "form",
        "technology",
        "current_problem",
        "lead_url",
        "lead_domain",
        "recommended_action",
        "suggested_user_reply_options",
        "korea_p1",
        "korea_status",
    ]
    for path in [out_csv, OUT_CSV_LATEST]:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fields})

    group_counts = Counter(row["group"] for row in rows)
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "rows": len(rows),
        "group_counts": dict(group_counts),
        "product_gap_p0_p1_rows": len(product_rows),
        "korea_p1_rows": len(korea_p1),
        "csv": str(OUT_CSV_LATEST),
        "html": str(OUT_HTML_LATEST),
    }
    for path in [out_json, OUT_JSON_LATEST]:
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)

    def esc(value: object) -> str:
        return html.escape(clean(value))

    sections: list[str] = []
    for group, group_rows in sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        instruction = group_rows[0]["group_instruction"]
        cards = []
        for row in group_rows:
            lead = row["lead_url"]
            lead_html = f'<a href="{esc(lead)}" target="_blank">{esc(row["lead_domain"] or lead)}</a>' if lead else '<span class="muted">无直接线索链接</span>'
            cards.append(
                f"""
      <article class="card">
        <div class="card-head">
          <span class="id">{esc(row['confirm_id'])}</span>
          <span class="badge">{esc(row['priority'])}</span>
          <span class="score">score {esc(row['gap_score'])}</span>
        </div>
        <h3>{esc(row['company'])} / {esc(row['brand'])}</h3>
        <p class="product">{esc(row['original_product_name'])}</p>
        <dl>
          <dt>原始分类</dt><dd>{esc(row['track'])} / {esc(row['form'])} / {esc(row['technology'])}</dd>
          <dt>当前缺口</dt><dd>{esc(row['current_problem'])}</dd>
          <dt>线索链接</dt><dd>{lead_html}</dd>
          <dt>建议回复</dt><dd>{esc(row['suggested_user_reply_options'])}</dd>
        </dl>
      </article>"""
            )
        sections.append(
            f"""
    <section>
      <h2>{esc(group)} <span>{len(group_rows)}</span></h2>
      <p class="instruction">{esc(instruction)}</p>
      <div class="cards">{''.join(cards)}</div>
    </section>"""
        )

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>下一批用户确认清单</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #28231f;
      --muted: #776d64;
      --line: #e6ded6;
      --bg: #fbfaf8;
      --panel: #ffffff;
      --accent: #c75f42;
      --soft: #f6eee9;
      --green: #2d7567;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.55;
    }}
    header {{
      padding: 28px 32px 18px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      position: sticky;
      top: 0;
      z-index: 5;
    }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    .meta {{ color: var(--muted); display: flex; flex-wrap: wrap; gap: 14px; }}
    main {{ padding: 24px 32px 40px; max-width: 1320px; margin: 0 auto; }}
    .how {{
      background: var(--soft);
      border: 1px solid var(--line);
      padding: 14px 16px;
      margin-bottom: 22px;
    }}
    section {{ margin: 0 0 28px; }}
    h2 {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 0 0 6px;
      font-size: 21px;
    }}
    h2 span {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 30px;
      height: 24px;
      padding: 0 8px;
      color: #fff;
      background: var(--accent);
      border-radius: 999px;
      font-size: 13px;
    }}
    .instruction {{ margin: 0 0 12px; color: var(--muted); }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .card-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }}
    .id {{ font-weight: 700; color: var(--accent); }}
    .badge {{ color: #fff; background: var(--green); padding: 2px 7px; border-radius: 999px; font-size: 12px; }}
    .score {{ color: var(--muted); font-size: 12px; }}
    h3 {{ margin: 0; font-size: 17px; }}
    .product {{ margin: 4px 0 10px; color: var(--muted); }}
    dl {{ display: grid; grid-template-columns: 72px 1fr; gap: 7px 10px; margin: 0; }}
    dt {{ color: var(--muted); }}
    dd {{ margin: 0; min-width: 0; overflow-wrap: anywhere; }}
    a {{ color: #9c412d; }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 640px) {{
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .cards {{ grid-template-columns: 1fr; }}
      dl {{ grid-template-columns: 1fr; }}
      dt {{ font-weight: 700; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>下一批用户确认清单</h1>
    <div class="meta">
      <span>生成时间：{esc(summary['generated_at'])}</span>
      <span>合并去重后：{len(rows)} 条</span>
      <span>P0/P1：{len(product_rows)} 条</span>
      <span>韩国 P1：{len(korea_p1)} 条</span>
    </div>
  </header>
  <main>
    <div class="how">
      回复时直接写编号即可，例如：<strong>NEXT-001 确认保留，补 FDA/CE；NEXT-002 排除；NEXT-003 先查证。</strong>
      每条都保留了原始公司、品牌、产品名和系统当前缺口，方便你判断“看的是什么”。
    </div>
    {''.join(sections)}
  </main>
</body>
</html>"""
    for path in [out_html, OUT_HTML_LATEST]:
        path.write_text(html_doc, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

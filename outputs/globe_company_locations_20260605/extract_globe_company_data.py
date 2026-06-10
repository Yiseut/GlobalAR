import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = Path("E:/shared/Documents/data/global_aesthetics_dashboard/data/global_aesthetics.db")
OUTPUT_PATH = Path("E:/shared/Documents/data/global_aesthetics_dashboard/outputs/globe_company_locations_20260605/globe_company_locations_data.json")

TRACK_ORDER = [
    "EBD",
    "Injectables",
    "Skincare",
    "Regenerative",
    "Implants",
    "Consumables",
    "Diagnostics",
    "Surgical",
    "Pharma",
]

TRACK_DISPLAY = {
    "EBD": "EBD / 光电",
    "Injectables": "Injectables / 注射",
    "Skincare": "Cosmeceutical / 功能性护肤品",
    "Regenerative": "Regenerative / 再生",
    "Implants": "Implants / 植入物",
    "Consumables": "Consumables / 耗材",
    "Diagnostics": "Diagnostics / 诊断",
    "Surgical": "Surgical / 外科",
    "Pharma": "Pharma / 药物",
}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    company_rows = [
        dict(row)
        for row in cur.execute(
            """
            select
              cm.company_id,
              cm.canonical_name,
              cm.hq_country,
              cm.region as master_region,
              cm.location_full as master_location_full,
              cm.ownership,
              cm.status,
              cm.stock_code,
              cm.exchange,
              cm.ticker_symbol,
              cm.product_count as master_product_count,
              cm.brand_count as master_brand_count,
              cm.primary_track as master_primary_track,
              cm.priority_rank,
              cm.verification_status,
              cm.review_status,
              cm.source_status,
              cg.city,
              cg.country,
              cg.region as geo_region,
              cg.location_full as geo_location_full,
              cg.lat,
              cg.lon,
              cg.precision,
              cg.products as globe_product_count,
              cg.brands as globe_brand_count,
              cg.primary_track as globe_primary_track,
              cg.regulatory_channels
            from company_master cm
            left join company_geo cg on cg.company_id = cm.company_id
            order by coalesce(cg.products, cm.product_count, 0) desc, cm.canonical_name
            """
        )
    ]

    product_rows = [
        dict(row)
        for row in cur.execute(
            """
            select company_id, product_id, commercial_path_l1, inclusion_status
            from product_master
            where coalesce(inclusion_status, '') not in ('excluded', 'delete', 'deleted')
            """
        )
    ]

    tracks_by_company: dict[str, Counter[str]] = defaultdict(Counter)
    products_by_company: Counter[str] = Counter()
    for product in product_rows:
        company_id = product.get("company_id") or ""
        if not company_id:
            continue
        products_by_company[company_id] += 1
        track = product.get("commercial_path_l1") or ""
        if track:
            tracks_by_company[company_id][track] += 1

    export_rows = []
    for company in company_rows:
        company_id = company.get("company_id") or ""
        track_counter = tracks_by_company.get(company_id, Counter())
        ordered_tracks = [track for track in TRACK_ORDER if track_counter.get(track, 0)]
        ordered_tracks.extend(sorted(track for track in track_counter if track not in TRACK_ORDER))
        track_list_display = " | ".join(TRACK_DISPLAY.get(track, track) for track in ordered_tracks)
        track_list_raw = " | ".join(ordered_tracks)

        product_count = int(products_by_company.get(company_id, 0))
        globe_product_count = company.get("globe_product_count")
        if product_count == 0 and globe_product_count not in (None, ""):
            product_count = int(globe_product_count or 0)

        city = company.get("city") or ""
        country = company.get("country") or company.get("hq_country") or ""
        pin_label = f"{city}, {country}".strip(", ") if city else country
        primary_raw = company.get("globe_primary_track") or company.get("master_primary_track") or ""

        export_rows.append(
            {
                "company_id": company_id,
                "company": company.get("canonical_name") or "",
                "pin_label": pin_label,
                "city": city,
                "country": country,
                "region": company.get("geo_region") or company.get("master_region") or "",
                "latitude": company.get("lat"),
                "longitude": company.get("lon"),
                "geo_precision": company.get("precision") or "",
                "location_full": company.get("geo_location_full") or company.get("master_location_full") or "",
                "primary_track": TRACK_DISPLAY.get(primary_raw, primary_raw),
                "primary_track_raw": primary_raw,
                "track_count": len(ordered_tracks),
                "track_list": track_list_display,
                "track_list_raw": track_list_raw,
                "product_count": product_count,
                "globe_product_count": int(globe_product_count or 0),
                "brand_count": int(company.get("globe_brand_count") or company.get("master_brand_count") or 0),
                "ownership": company.get("ownership") or "",
                "stock_code": company.get("stock_code") or "",
                "exchange": company.get("exchange") or "",
                "ticker_symbol": company.get("ticker_symbol") or "",
                "regulatory_channels": company.get("regulatory_channels") or "",
                "priority_rank": company.get("priority_rank") or "",
                "verification_status": company.get("verification_status") or "",
                "review_status": company.get("review_status") or "",
                "source_status": company.get("source_status") or "",
                **{f"track_{track}": int(track_counter.get(track, 0)) for track in TRACK_ORDER},
            }
        )

    track_stats = []
    for track in TRACK_ORDER:
        companies = {row["company_id"] for row in export_rows if row.get(f"track_{track}", 0) > 0}
        track_stats.append(
            {
                "track_raw": track,
                "track_display": TRACK_DISPLAY.get(track, track),
                "product_count": sum(row.get(f"track_{track}", 0) for row in export_rows),
                "company_count": len(companies),
            }
        )

    conn.close()

    summary = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db_path": str(DB_PATH),
        "company_count": len(export_rows),
        "mapped_geo_count": sum(1 for row in export_rows if row.get("latitude") is not None and row.get("longitude") is not None),
        "city_precision_count": sum(1 for row in export_rows if row.get("geo_precision") == "city"),
        "country_precision_count": sum(1 for row in export_rows if row.get("geo_precision") == "country"),
        "product_count": sum(row["product_count"] for row in export_rows),
        "globe_product_count": sum(row["globe_product_count"] for row in export_rows),
        "multi_track_companies": sum(1 for row in export_rows if row["track_count"] >= 2),
    }

    OUTPUT_PATH.write_text(
        json.dumps({"summary": summary, "rows": export_rows, "track_stats": track_stats}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

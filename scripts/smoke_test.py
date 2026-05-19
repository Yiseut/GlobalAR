#!/usr/bin/env python3
"""Smoke checks for the local dashboard build."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "data" / "global_aesthetics.db"
MANIFEST_PATH = PROJECT_DIR / "data" / "import_manifest.json"
SNAPSHOT_PATH = PROJECT_DIR / "web" / "app-data.js"
TOPIC_JS_PATH = PROJECT_DIR / "web" / "topic.js"
APP_JS_PATH = PROJECT_DIR / "web" / "app.js"


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest["summary"]
    snapshot_text = SNAPSHOT_PATH.read_text(encoding="utf-8")
    snapshot = json.loads(snapshot_text.removeprefix("window.GLOBAL_AESTHETICS_DATA = ").rstrip(";\n"))
    ha_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "ha"), {})
    pcl_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "pcl"), {})
    caha_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "caha"), {})
    pn_pdrn_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "pn_pdrn"), {})
    exosome_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "exosome"), {})
    mesotherapy_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "mesotherapy"), {})
    ebd_segment = next((item for item in snapshot.get("segments", []) if item.get("code") == "ebd"), {})
    ha_slice_names = {item.get("name") for item in ha_segment.get("subtrack_slices", [])}
    caha_slice_names = {item.get("name") for item in caha_segment.get("subtrack_slices", [])}
    ebd_slice_names = {item.get("name") for item in ebd_segment.get("subtrack_slices", [])}
    all_subtrack_slices = [
        item
        for segment in snapshot.get("segments", [])
        for item in segment.get("subtrack_slices", [])
    ]
    runtime_subtrack_names = {
        item.get("name")
        for segment in snapshot.get("segments", [])
        for item in segment.get("subtrack_slices", []) + segment.get("top_subtracks", [])
    }
    runtime_subtrack_names |= {
        name
        for segment in snapshot.get("segments", [])
        for row in segment.get("sample_products", [])
        for name in row.get("subtracks", [])
    }
    leaky_subtrack_labels = {
        "眼周 / 细纹",
        "眼周细纹",
        "头皮 / 毛发",
        "头皮毛发",
        "肤质活化",
        "局部减脂",
        "脂肪溶解",
        "皮肤修复",
        "身体 / 私密",
        "身体用 PLLA 制剂",
        "身体胶原刺激",
        "线材 / 提拉",
        "PCL 线材",
        "稀释/超稀释 CaHA 用法",
        "治疗性适应症",
    }
    topic_js = TOPIC_JS_PATH.read_text(encoding="utf-8")
    app_js = APP_JS_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    registration_columns = {row[1] for row in conn.execute("PRAGMA table_info(registration_evidence)").fetchall()}
    official_indication_columns = {row[1] for row in conn.execute("PRAGMA table_info(official_indication_evidence)").fetchall()}
    checks = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "brands": conn.execute("SELECT COUNT(*) FROM brands").fetchone()[0],
        "company_master": conn.execute("SELECT COUNT(*) FROM company_master").fetchone()[0],
        "company_geo": conn.execute("SELECT COUNT(*) FROM company_geo").fetchone()[0],
        "product_master": conn.execute("SELECT COUNT(*) FROM product_master").fetchone()[0],
        "product_families": conn.execute("SELECT COUNT(*) FROM product_family_master").fetchone()[0],
        "product_sku_candidates": conn.execute("SELECT COUNT(*) FROM product_sku_master").fetchone()[0],
        "sku_split_candidates": conn.execute(
            "SELECT COUNT(*) FROM product_sku_master WHERE split_status != 'family_level'"
        ).fetchone()[0],
        "registration_evidence": conn.execute("SELECT COUNT(*) FROM registration_evidence").fetchone()[0],
        "registration_precise_description_columns": {"official_description_exact", "official_description_source_field", "field_note"}.issubset(registration_columns),
        "official_sources": conn.execute("SELECT COUNT(*) FROM official_source_registry WHERE scope_status != 'external_project'").fetchone()[0],
        "source_authority_policy": conn.execute("SELECT COUNT(*) FROM source_authority_policy").fetchone()[0],
        "verification_queue": conn.execute("SELECT COUNT(*) FROM verification_queue").fetchone()[0],
        "evidence_staging": conn.execute("SELECT COUNT(*) FROM evidence_staging").fetchone()[0],
        "market_snapshot": conn.execute("SELECT COUNT(*) FROM market_snapshot").fetchone()[0],
        "company_background_evidence": conn.execute("SELECT COUNT(*) FROM company_background_evidence").fetchone()[0],
        "company_capital_structure": conn.execute("SELECT COUNT(*) FROM company_capital_structure").fetchone()[0],
        "listed_company_batch": conn.execute("SELECT COUNT(*) FROM listed_company_batch").fetchone()[0],
        "company_official_source_plan": conn.execute("SELECT COUNT(*) FROM company_official_source_plan").fetchone()[0],
        "company_official_source_product_plan": conn.execute(
            "SELECT COUNT(*) FROM company_official_source_plan WHERE COALESCE(product_family_id, '') != ''"
        ).fetchone()[0],
        "company_official_source_evidence": conn.execute("SELECT COUNT(*) FROM company_official_source_evidence").fetchone()[0],
        "official_website_master": conn.execute("SELECT COUNT(*) FROM official_website_master").fetchone()[0],
        "company_official_website": conn.execute("SELECT COUNT(*) FROM company_official_website").fetchone()[0],
        "company_media_asset_index": conn.execute("SELECT COUNT(*) FROM company_media_asset_index").fetchone()[0],
        "product_specification_evidence": conn.execute("SELECT COUNT(*) FROM product_specification_evidence").fetchone()[0],
        "official_product_line_websites": conn.execute("SELECT COUNT(*) FROM official_website_master WHERE entity_scope = 'product_line'").fetchone()[0],
        "policy_regulatory_source_plan": conn.execute("SELECT COUNT(*) FROM policy_regulatory_source_plan").fetchone()[0],
        "mdr_ce_search_plan": conn.execute("SELECT COUNT(*) FROM mdr_ce_search_plan").fetchone()[0],
        "evidence_promotion_log": conn.execute("SELECT COUNT(*) FROM evidence_promotion_log").fetchone()[0],
        "official_indication_evidence": conn.execute("SELECT COUNT(*) FROM official_indication_evidence").fetchone()[0],
        "official_indication_precise_description_columns": {
            "official_description_exact",
            "official_description_source_field",
            "field_note",
            "analysis_bucket_note",
        }.issubset(official_indication_columns),
        "official_indication_snapshot": snapshot.get("official_indication_analysis", {}).get("rows", 0),
        "official_indication_heatmap_rows": len(snapshot.get("official_indication_analysis", {}).get("by_regulator_heatmap", {}).get("rows", [])),
        "official_indication_heatmap_has_exact_examples": any(
            row.get("examples")
            for row in snapshot.get("official_indication_analysis", {}).get("by_regulator_heatmap", {}).get("rows", [])
        ),
        "official_indication_top_buckets": len(snapshot.get("official_indication_analysis", {}).get("top_buckets", [])),
        "official_indication_exact_rows": conn.execute(
            "SELECT COUNT(*) FROM official_indication_evidence WHERE COALESCE(official_description_exact, '') != ''"
        ).fetchone()[0],
        "official_indication_noise_rows": conn.execute(
            """
            SELECT COUNT(*)
            FROM official_indication_evidence
            WHERE lower(COALESCE(official_description_exact, '')) LIKE '%adverse experiences%'
               OR lower(COALESCE(official_description_exact, '')) LIKE '%adverse events%'
               OR lower(COALESCE(official_description_exact, '')) LIKE '%clinical trials%'
               OR lower(COALESCE(official_description_exact, '')) LIKE '%date summary prepared%'
            """
        ).fetchone()[0],
        "official_indication_field_note_rows": conn.execute(
            "SELECT COUNT(*) FROM official_indication_evidence WHERE COALESCE(official_description_exact, '') != '' AND COALESCE(field_note, '') != ''"
        ).fetchone()[0],
        "field_dictionary": conn.execute("SELECT COUNT(*) FROM field_dictionary").fetchone()[0],
        "field_dictionary_has_precise_description": bool(
            conn.execute(
                "SELECT 1 FROM field_dictionary WHERE table_name = 'Registration_Evidence' AND field_name = 'official_description_exact'"
            ).fetchone()
        ),
        "radiesse_s162_has_exact_indication": bool(
            conn.execute(
                "SELECT 1 FROM registration_evidence WHERE registration_no = 'P050052/S162' AND official_description_source_field = 'approved_indication' AND official_description_exact LIKE '%décolleté%'"
            ).fetchone()
        ),
        "radiesse_s162_has_decollete_bucket": bool(
            conn.execute(
                "SELECT 1 FROM official_indication_evidence WHERE registration_no = 'P050052/S162' AND buckets LIKE '%颈胸部/胸前区%'"
            ).fetchone()
        ),
        "radiesse_s049_has_hand_bucket": bool(
            conn.execute(
                "SELECT 1 FROM official_indication_evidence WHERE registration_no = 'P050052/S049' AND buckets LIKE '%手背/手部增容%'"
            ).fetchone()
        ),
        "seed_integrity_issues": conn.execute("SELECT COUNT(*) FROM seed_integrity_issues").fetchone()[0],
        "seed_integrity_high": conn.execute("SELECT COUNT(*) FROM seed_integrity_issues WHERE severity IN ('critical','high')").fetchone()[0],
        "conference_rows": conn.execute("SELECT COUNT(*) FROM conferences").fetchone()[0],
        "market_metrics": conn.execute("SELECT COUNT(*) FROM market_metrics").fetchone()[0],
        "reports": conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0],
        "pcl_evidence": conn.execute("SELECT COUNT(*) FROM evidence WHERE LOWER(body || title) LIKE '%pcl%'").fetchone()[0],
        "gouri_hits": conn.execute("SELECT COUNT(*) FROM evidence WHERE LOWER(body || title) LIKE '%gouri%'").fetchone()[0],
        "ha_indication_rows": len(ha_segment.get("indication_heatmap", {}).get("rows", [])),
        "ha_subtrack_rows": len(ha_segment.get("subtrack_heatmap", {}).get("rows", [])),
        "pcl_products": pcl_segment.get("products", 0),
        "pcl_indication_rows": len(pcl_segment.get("indication_heatmap", {}).get("rows", [])),
        "caha_products": caha_segment.get("products", 0),
        "caha_indication_rows": len(caha_segment.get("indication_heatmap", {}).get("rows", [])),
        "caha_subtrack_rows": len(caha_segment.get("subtrack_heatmap", {}).get("rows", [])),
        "harmonyca_in_caha_only": bool(
            conn.execute(
                """
                SELECT 1
                FROM products
                WHERE LOWER(COALESCE(brand, '') || ' ' || COALESCE(core_product, '')) LIKE '%harmonyca%'
                  AND segments = 'caha'
                """
            ).fetchone()
        ),
        "harmonyca_not_exosome": not bool(
            conn.execute(
                """
                SELECT 1
                FROM products
                WHERE LOWER(COALESCE(brand, '') || ' ' || COALESCE(core_product, '')) LIKE '%harmonyca%'
                  AND (',' || segments || ',') LIKE '%,exosome,%'
                """
            ).fetchone()
        ),
        "caha_subtracks_no_dilution_use": "稀释/超稀释 CaHA 用法"
        not in (
            set(caha_segment.get("configured_subtracks", []))
            | caha_slice_names
            | {item.get("name") for item in caha_segment.get("top_subtracks", [])}
            | {
                name
                for row in caha_segment.get("sample_products", [])
                for name in row.get("subtracks", [])
            }
        ),
        "caha_dilution_is_indication": "稀释/超稀释应用" in set(caha_segment.get("configured_indications", [])),
        "ha_subtrack_slices": len(ha_segment.get("subtrack_slices", [])),
        "ebd_subtrack_slices": len(ebd_segment.get("subtrack_slices", [])),
        "subtrack_slices": len(all_subtrack_slices),
        "subtrack_slices_with_evidence_scope": sum(1 for item in all_subtrack_slices if isinstance(item.get("evidence_scope"), dict)),
        "topic_js_has_parent_scope_fallback": "segment.evidence_scope" in topic_js or "findSegment().evidence_scope" in topic_js,
        "app_js_has_missing_per_call": "per(" in app_js,
        "global_analysis_blueprint": len(snapshot.get("analysis_blueprint", [])),
        "ha_analysis_lenses": len(ha_segment.get("analysis_lenses", [])),
        "ha_evidence_funnel": len(ha_segment.get("evidence_funnel", [])),
        "pcl_company_subtrack_rows": len(pcl_segment.get("company_subtrack_matrix", {}).get("rows", [])),
        "ebd_country_subtrack_rows": len(ebd_segment.get("country_subtrack_matrix", {}).get("rows", [])),
        "ebd_sample_has_merz": any((row.get("company") or "").lower() == "merz" for row in ebd_segment.get("sample_products", [])),
        "regulatory_atlas_size": len(snapshot.get("regulatory_atlas", [])),
        "regulatory_atlas_has_mdsap_note": any(
            item.get("code") == "mdsap" and item.get("license_effect") == "quality_system_audit_not_sales_authorization"
            for item in snapshot.get("regulatory_atlas", [])
        ),
        "ha_has_filler_booster_meso": {"Filler / 交联填充剂", "Skin Booster / 无交联水光", "中胚层 HA 复配液"}.issubset(ha_slice_names),
        "subtracks_no_application_leakage": not (leaky_subtrack_labels & {name for name in runtime_subtrack_names if name}),
        "pn_pdrn_subtracks_material_only": not {
            "PN 注射",
            "PN 注射剂",
            "眼周 / 细纹",
            "眼周细纹",
            "头皮 / 毛发",
            "头皮毛发",
            "PDRN / 修复",
            "PN/PDRN 复合配方",
        }.intersection(set(pn_pdrn_segment.get("configured_subtracks", []))),
        "pn_pdrn_subtracks_no_repair_word": not any(
            "修复" in name for name in pn_pdrn_segment.get("configured_subtracks", [])
        ),
        "pn_pdrn_subtracks_are_exclusive": all(
            len(row.get("subtracks", [])) <= 1 for row in pn_pdrn_segment.get("sample_products", [])
        ),
        "pn_pdrn_indications_keep_applications": {"眼周细纹", "头皮毛发"}.issubset(
            set(pn_pdrn_segment.get("configured_indications", []))
        ),
        "exosome_subtracks_material_only": not {
            "头皮 / 毛发再生",
            "毛发 / 头皮",
            "皮肤再生 / 抗炎",
            "术后修复",
        }.intersection(set(exosome_segment.get("configured_subtracks", []))),
        "exosome_indications_keep_applications": {"毛发 / 头皮", "皮肤再生 / 抗炎"}.issubset(
            set(exosome_segment.get("configured_indications", []))
        ),
        "mesotherapy_subtracks_product_form_only": not {
            "肤质活化",
            "头皮 / 毛发",
            "头皮毛发",
            "脂肪溶解",
            "局部减脂",
            "HA 复配溶液",
        }.intersection(
            set(mesotherapy_segment.get("configured_subtracks", []))
            | {item.get("name") for item in mesotherapy_segment.get("top_subtracks", [])}
            | {
                name
                for row in mesotherapy_segment.get("sample_products", [])
                for name in row.get("subtracks", [])
            }
        ),
        "mesotherapy_subtracks_are_exclusive": all(
            len(row.get("subtracks", [])) <= 1 for row in mesotherapy_segment.get("sample_products", [])
        ),
        "mesotherapy_indications_keep_applications": {"肤质活化", "局部减脂", "头皮毛发"}.issubset(
            set(mesotherapy_segment.get("configured_indications", []))
        ),
        "mesotherapy_has_ha_base_cocktail": "HA 基底复配液 / HA-based cocktail" in set(
            mesotherapy_segment.get("configured_subtracks", [])
        ),
        "injectable_materials_no_thread_subtracks": not {
            "线材 / 提拉",
            "PCL 线材",
        }.intersection(
            set(pcl_segment.get("configured_subtracks", []))
            | set(pcl_segment.get("configured_indications", []))
            | set(next((item for item in snapshot.get("segments", []) if item.get("code") == "plla"), {}).get("configured_subtracks", []))
            | {
                name
                for row in pcl_segment.get("sample_products", [])
                for name in row.get("subtracks", [])
            }
        ),
        "regenerative_featured_material_only": all(
            old_label not in app_js
            for old_label in ["PDRN / 修复", "PN 注射剂", "PN/PDRN 复合配方", "头皮 / 毛发再生", "外泌体护肤 / 医美"]
        ),
        "mesotherapy_featured_product_form_only": all(
            old_label not in app_js for old_label in ["肤质活化", "头皮 / 毛发", "脂肪溶解"]
        ),
        "ebd_subtracks_energy_only": not {"身体塑形 / 溶脂", "皮肤管理"}.intersection(
            set(ebd_segment.get("configured_subtracks", []))
            | ebd_slice_names
            | {item.get("name") for item in ebd_segment.get("top_subtracks", [])}
            | {
                name
                for row in ebd_segment.get("sample_products", [])
                for name in row.get("subtracks", [])
            }
        ),
        "ebd_has_rf_laser_ultrasound": {"射频 / RF", "激光 / Laser / IPL", "超声 / Ultrasound / HIFU"}.issubset(ebd_slice_names),
        "app_js_no_old_caha_ebd_featured": all(
            old_label not in app_js
            for old_label in ["身体塑形 / 溶脂", "皮肤管理"]
        ),
        "workbench_top_companies": len(snapshot.get("verification_workbench", {}).get("top_companies", [])),
        "workbench_sources": len(snapshot.get("verification_workbench", {}).get("source_registry", [])),
        "source_registry_has_mdsap_qms": any(
            item.get("key") == "mdsap_program" and item.get("kind") == "qms_audit"
            for item in snapshot.get("verification_workbench", {}).get("source_registry", [])
        ),
        "source_authority_rules": len(snapshot.get("source_authority_policy", [])),
        "source_registry_excludes_nmpa": not any(
            item.get("channel_code") == "nmpa"
            for item in snapshot.get("verification_workbench", {}).get("source_registry", [])
        ),
        "current_phase_note": snapshot.get("verification_workbench", {}).get("current_phase", {}).get("note", ""),
        "market_snapshot_cards": len(snapshot.get("market_snapshot", {}).get("cards", [])),
        "background_snapshot_evidence": snapshot.get("summary", {}).get("company_background_evidence", 0),
        "capital_snapshot_rows": snapshot.get("summary", {}).get("company_capital_structure", 0),
        "workbench_background_evidence": snapshot.get("verification_workbench", {}).get("company_background", {}).get("evidence_rows", 0),
        "workbench_capital_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("capital_rows", 0),
        "workbench_listed_company_batch_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("listed_company_batch_rows", 0),
        "workbench_official_source_plan_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("official_source_plan_rows", 0),
        "workbench_official_source_evidence_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("official_source_evidence_rows", 0),
        "workbench_official_website_master_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("official_website_master_rows", 0),
        "workbench_company_official_website_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("company_official_website_rows", 0),
        "workbench_media_asset_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("media_asset_rows", 0),
        "workbench_product_specification_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("product_specification_rows", 0),
        "workbench_policy_plan_rows": snapshot.get("verification_workbench", {}).get("company_background", {}).get("policy_plan_rows", 0),
        "mdr_ce_snapshot_rows": snapshot.get("summary", {}).get("mdr_ce_search_plan", 0),
        "workbench_mdr_ce_rows": snapshot.get("verification_workbench", {}).get("mdr_ce_plan", {}).get("rows", 0),
        "hierarchy_snapshot_families": snapshot.get("product_hierarchy", {}).get("summary", {}).get("families", 0),
        "hierarchy_snapshot_skus": snapshot.get("product_hierarchy", {}).get("summary", {}).get("sku_candidates", 0),
        "hierarchy_top_families": len(snapshot.get("product_hierarchy", {}).get("top_families", [])),
        "hierarchy_split_candidates": len(snapshot.get("product_hierarchy", {}).get("split_candidates", [])),
        "data_quality_snapshot": snapshot.get("summary", {}).get("data_quality_issues", 0),
        "data_quality_reported": bool(snapshot.get("data_quality", {}).get("summary", {}).get("issues_path")),
        "geo_snapshot": len(snapshot.get("geo_companies", [])),
        "geo_points": len(snapshot.get("geo_points", [])),
        "geo_city_clusters": len(snapshot.get("geo_city_clusters", [])),
        "geo_mapped_summary": snapshot.get("geo_summary", {}).get("mapped_companies", 0),
        "geo_city_precision": snapshot.get("geo_summary", {}).get("city_precision", 0),
    }
    conn.close()
    mismatches = {key: (checks[key], expected[key]) for key in expected if key in checks and checks[key] != expected[key]}
    api = {}
    for label, query, expected_segment in [
        ("pcl", "GOURI%20PCL", "pcl"),
        ("caha", "Radiesse%20CaHA", "caha"),
    ]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:8790/api/ask?q={query}", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
                api[label] = {
                    "status": "ok",
                    "segment": payload.get("segment"),
                    "products": payload.get("counts", {}).get("products"),
                    "expected_segment": expected_segment,
                }
        except (urllib.error.URLError, TimeoutError) as exc:
            api[label] = {"status": "offline", "detail": str(exc), "expected_segment": expected_segment}
    # The local ask API is a frontend convenience server. It is useful to report
    # when available, but offline API status should not stop background evidence
    # collection or workbook/database promotion.
    api_failed = any(
        item.get("status") == "ok" and item.get("segment") != item.get("expected_segment")
        for item in api.values()
    )
    result = {"checks": checks, "mismatches": mismatches, "api": api}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (
        mismatches
        or checks["pcl_evidence"] == 0
        or checks["gouri_hits"] == 0
        or checks["ha_indication_rows"] == 0
        or checks["ha_subtrack_rows"] == 0
        or checks["pcl_products"] == 0
        or checks["pcl_indication_rows"] == 0
        or checks["caha_products"] == 0
        or checks["caha_indication_rows"] == 0
        or checks["caha_subtrack_rows"] == 0
        or not checks["harmonyca_in_caha_only"]
        or not checks["harmonyca_not_exosome"]
        or not checks["caha_subtracks_no_dilution_use"]
        or not checks["caha_dilution_is_indication"]
        or checks["ha_subtrack_slices"] < 3
        or checks["ebd_subtrack_slices"] < 5
        or checks["subtrack_slices_with_evidence_scope"] != checks["subtrack_slices"]
        or checks["topic_js_has_parent_scope_fallback"]
        or checks["app_js_has_missing_per_call"]
        or checks["global_analysis_blueprint"] < 6
        or checks["ha_analysis_lenses"] < 5
        or checks["ha_evidence_funnel"] < 5
        or checks["pcl_company_subtrack_rows"] == 0
        or checks["ebd_country_subtrack_rows"] == 0
        or not checks["ebd_sample_has_merz"]
        or checks["regulatory_atlas_size"] != 19
        or not checks["regulatory_atlas_has_mdsap_note"]
        or not checks["ha_has_filler_booster_meso"]
        or not checks["subtracks_no_application_leakage"]
        or not checks["pn_pdrn_subtracks_material_only"]
        or not checks["pn_pdrn_subtracks_no_repair_word"]
        or not checks["pn_pdrn_subtracks_are_exclusive"]
        or not checks["pn_pdrn_indications_keep_applications"]
        or not checks["exosome_subtracks_material_only"]
        or not checks["exosome_indications_keep_applications"]
        or not checks["mesotherapy_subtracks_product_form_only"]
        or not checks["mesotherapy_subtracks_are_exclusive"]
        or not checks["mesotherapy_indications_keep_applications"]
        or not checks["mesotherapy_has_ha_base_cocktail"]
        or not checks["injectable_materials_no_thread_subtracks"]
        or not checks["regenerative_featured_material_only"]
        or not checks["mesotherapy_featured_product_form_only"]
        or not checks["ebd_subtracks_energy_only"]
        or not checks["ebd_has_rf_laser_ultrasound"]
        or not checks["app_js_no_old_caha_ebd_featured"]
        or checks["company_master"] < checks["companies"] - 2
        or checks["company_geo"] != checks["company_master"]
        or checks["product_master"] != checks["products"]
        or checks["product_families"] == 0
        or checks["product_sku_candidates"] != checks["products"]
        or checks["hierarchy_snapshot_families"] != checks["product_families"]
        or checks["hierarchy_snapshot_skus"] != checks["product_sku_candidates"]
        or checks["hierarchy_top_families"] == 0
        or min(checks["sku_split_candidates"], 40) != checks["hierarchy_split_candidates"]
        or checks["registration_evidence"] == 0
        or not checks["registration_precise_description_columns"]
        or checks["official_sources"] < 19
        or checks["source_authority_policy"] < 4
        or checks["source_authority_rules"] < 4
        or checks["verification_queue"] < checks["workbench_top_companies"] * 4
        or checks["market_snapshot"] == 0
        or checks["background_snapshot_evidence"] != checks["company_background_evidence"]
        or checks["capital_snapshot_rows"] != checks["company_capital_structure"]
        or checks["workbench_background_evidence"] != checks["company_background_evidence"]
        or checks["workbench_capital_rows"] != checks["company_capital_structure"]
        or checks["workbench_listed_company_batch_rows"] != checks["listed_company_batch"]
        or checks["workbench_official_source_plan_rows"] != checks["company_official_source_plan"]
        or checks["workbench_official_source_evidence_rows"] != checks["company_official_source_evidence"]
        or checks["workbench_official_website_master_rows"] != checks["official_website_master"]
        or checks["workbench_company_official_website_rows"] != checks["company_official_website"]
        or checks["workbench_media_asset_rows"] != checks["company_media_asset_index"]
        or checks["workbench_product_specification_rows"] != checks["product_specification_evidence"]
        or checks["workbench_policy_plan_rows"] != checks["policy_regulatory_source_plan"]
        or checks["company_official_source_plan"] == 0
        or checks["company_official_source_product_plan"] == 0
        or checks["official_website_master"] == 0
        or checks["company_official_website"] == 0
        or checks["official_product_line_websites"] == 0
        or checks["product_specification_evidence"] == 0
        or checks["policy_regulatory_source_plan"] < 19
        or checks["mdr_ce_snapshot_rows"] != checks["mdr_ce_search_plan"]
        or checks["workbench_mdr_ce_rows"] != checks["mdr_ce_search_plan"]
        or checks["evidence_promotion_log"] == 0
        or checks["official_indication_evidence"] != checks["official_indication_snapshot"]
        or checks["official_indication_evidence"] == 0
        or not checks["official_indication_precise_description_columns"]
        or checks["official_indication_exact_rows"] == 0
        or checks["official_indication_noise_rows"] != 0
        or checks["official_indication_field_note_rows"] != checks["official_indication_exact_rows"]
        or checks["official_indication_heatmap_rows"] == 0
        or not checks["official_indication_heatmap_has_exact_examples"]
        or checks["official_indication_top_buckets"] == 0
        or checks["field_dictionary"] < 8
        or not checks["field_dictionary_has_precise_description"]
        or not checks["radiesse_s162_has_exact_indication"]
        or not checks["radiesse_s162_has_decollete_bucket"]
        or not checks["radiesse_s049_has_hand_bucket"]
        or checks["data_quality_snapshot"] != checks["seed_integrity_issues"]
        or not checks["data_quality_reported"]
        or checks["geo_snapshot"] != checks["company_geo"]
        or checks["geo_mapped_summary"] != checks["company_geo"]
        or checks["geo_points"] < 100
        or checks["geo_city_clusters"] == 0
        or checks["geo_city_precision"] < checks["company_geo"] // 2
        or checks["workbench_top_companies"] < 30
        or checks["workbench_sources"] < 19
        or not checks["source_registry_has_mdsap_qms"]
        or not checks["source_registry_excludes_nmpa"]
        or "NMPA" not in checks["current_phase_note"]
        or checks["market_snapshot_cards"] == 0
        or api_failed
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

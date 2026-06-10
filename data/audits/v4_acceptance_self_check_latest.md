# v4 Acceptance Self-Check

- Generated: 2026-06-01T10:28:35.579222+00:00
- Database: `E:\shared\Documents\data\global_aesthetics_dashboard\data\global_aesthetics.db`
- Overall passed: `True`

| Section | Metric | Current | Threshold | Passed | Next action |
|---|---|---:|---:|---:|---|
| A | `A1_duplicate_active_product_groups` No duplicate active products across companies by normalized brand + standard_product_name | 0 | = 0 duplicate groups | True | Merge or soft-delete duplicate Product_Master rows and retarget references. |
| A | `A2_active_product_ownership_completeness` Active products have company, legal_manufacturer, and marketing_holder | 100.0% (979/979) | 100% | True | Backfill legal manufacturer and marketing holder from registration/official sources. |
| A | `A3_evidence_product_id_integrity` Evidence/reference tables have no orphan product_id and no active references to deleted products | 0 issues (0 orphan, 0 deleted refs) | = 0 issues | True | Retarget evidence rows to active product_id values or mark the evidence inactive/noise. |
| B | `B1_inclusion_and_material_path_coverage` inclusion_status is filled for all Product_Master rows and material_taxonomy_path_cn is filled for active products | inclusion 100.0% (979/979); material path 100.0% (979/979) | 100% / 100% | True | Preserve existing classification fields when rebuilding Product_Master. |
| B | `B2_material_taxonomy_review_backlog` material_taxonomy_review_status has no needs_review, pending_review, or pending_subclass rows | 0 | = 0 backlog rows | True | Resolve taxonomy backlog; pause only for explicit hold taxonomy decisions. |
| B | `B3_material_family_coverage` material_family coverage among active products | 100.0% (979/979) | >= 95% | True | Backfill material_family from confirmed taxonomy/SKU family assignments. |
| B | `B4_registered_name_regulated_subset` registered_name coverage among products with regulatory evidence | 99.7% (903/906) | >= 90% | True | Promote registered names from Registration_Evidence into Product_Master. |
| B | `B5_sku_split_candidate_backlog` Product_SKU_Master split candidates have all been resolved | 0 | = 0 candidate rows | True | Execute SKU/family split candidates and mark terminal split_status values. |
| B | `B6a_spec_evidence_product_id_mapping` Product_Spec_Evidence product_id-level mapping has expanded beyond the initial 11-product baseline | 755 | > 11 products | True | Map family-level spec evidence to product_id before judging technical_specs_json coverage. |
| B | `B6b_technical_specs_json_spec_subset` technical_specs_json coverage among products with product_id-level specification evidence | 98.5% (744/755) | >= 85% | True | Promote verified specification evidence into Product_Master.technical_specs_json. |
| B | `B6c_spec_candidate_conversion` Product_Spec_Evidence candidate conversion rate (promoted or cross_checked) | 66.7% (35821/53676) | >= 60% | True | Convert raw candidate rows into promoted or cross_checked terminal states. |
| C | `C1_registration_followup_backlog` Registration_Evidence has no needs_source_followup or pdf_indication_not_found rows | 0 | = 0 rows | True | 补源；若确实无公开适应症，显式标记为 unavailable_verified/no_public_indication. |
| C | `C2_registration_indication_coverage` approved_indication and intended_use coverage in Registration_Evidence | approved_indication 100.0% (1605/1605); intended_use 100.0% (1605/1605) | >= 60% / >= 60% | True | Promote official indications from regulator/IFU evidence or mark unavailable after source follow-up. |
| C | `C3_nmpa_link_and_supplement_closure` NMPA pending links/supplements are landed with no prod_NEW placeholders | pending links 0; supplement rows 19; prod_NEW placeholders 0 | pending links = 0; supplement rows >= 18; prod_NEW = 0 | True | Apply remaining NMPA manual link decisions and replace all prod_NEW placeholders. |
| D | `D1_public_market_cap_coverage` Market_Cap_USD_M coverage among public companies | 100.0% (45/45) | 100% | True | Refresh public-company market-cap snapshots for blank rows. |
| D | `D2_public_revenue_coverage` Revenue_USD_M + Revenue_Year coverage among public companies | 100.0% (45/45) | >= 90% | True | Collect annual report/XBRL revenue and fiscal year for public companies. |
| D | `D3_public_stock_code_coverage` Stock_Code coverage among public companies | 100.0% (45/45) | 100% | True | Backfill exchange/ticker identifiers from listed-company batch evidence. |
| D | `D4_public_aesthetics_revenue_pct_coverage` Aesthetics_Revenue_Pct coverage among public companies | 51.1% (23/45) | >= 50% | True | Extract aesthetics segment revenue share from annual report segment notes. |
| D | `D5_parent_company_known_group_subset` Parent_Company coverage among known group/subsidiary relationships | 95.1% (58/61) | >= 90% | True | Promote parent/ultimate parent from Listed_Company_Batch evidence into company tables. |
| E | `E1_promoted_field_traceability` Every promoted product fact has a matching Evidence_Promotion_Log source record | 0 | = 0 missing log rows | True | Write or repair Evidence_Promotion_Log rows for promoted facts before field promotion is accepted. |
| E | `E2_seed_integrity_high_open` Seed_Integrity_Issues high severity unresolved rows | 0 | = 0 high open rows | True | Resolve high-severity seed integrity issues before final acceptance. |

## Failing Metrics

- None.

# Database Guardrail Validation

- Generated at: 2026-06-16T05:12:13.386349+00:00
- Database: `E:\shared\Documents\data\global_aesthetics_dashboard\data\global_aesthetics.db`
- Overall assessment: **Ready to share**
- Failures: 0
- Warnings/caveats: 6

## Failures
- None

## Warnings And Caveats
- [Medium] listed_company_batch_blank_company_id: This is not an integrity failure, but it is a stakeholder caveat for interpretation. Details: `{"count": 6}`
- [Medium] company_financial_metrics_blank_company_id: This is not an integrity failure, but it is a stakeholder caveat for interpretation. Details: `{"count": 4}`
- [Medium] registration_needs_review: This is not an integrity failure, but it is a stakeholder caveat for interpretation. Details: `{"count": 120}`
- [Medium] duplicate_or_affiliate_sku_family_cross_company: This is not an integrity failure, but it is a stakeholder caveat for interpretation. Details: `{"count": 6}`
- [Medium] public_companies_without_aesthetics_revenue_pct: This is not an integrity failure, but it is a stakeholder caveat for interpretation. Details: `{"count": 21}`
- [Low] sqlite_declared_foreign_keys: SQLite tables do not declare foreign keys; referential integrity is enforced by guardrail scripts instead.

## Key Check Results
- `row_counts`: `{"company_master": 329, "product_master": 943, "product_family_master": 927, "product_sku_master": 1047, "registration_evidence": 1599, "product_specification_evidence": 53676, "company_official_source_evidence": 26891, "official_website_master": 19824}`
- `foreign_key_orphans`: `[]`
- `owner_consistency`: `{"sku_family_company_mismatch": 0, "duplicate_or_affiliate_sku_family_cross_company": 6, "product_sku_company_mismatch": 0, "products_without_sku_row": 0, "evidence_mismatches": {"product_specification_evidence.product_family_vs_product": 0, "product_specification_evidence.company_vs_product": 0, "manual_product_fact_evidence.product_family_vs_product": 0, "manual_product_fact_evidence.company_vs_product": 0, "evidence_promotion_log.product_family_vs_product": 0, "evidence_promotion_log.company_vs_product": 0, "registration_evidence.company_vs_product": 0}}`
- `data_usability`: `{"missing_owner_rows": 0, "ledger_tables_with_missing_owner_or_status": 0}`
- `traceability`: `{"promoted_fact_missing_logs": 0}`
- `nul_bytes`: `[]`
- `database_nul_text`: `[]`
- `source_parse_errors`: `[]`

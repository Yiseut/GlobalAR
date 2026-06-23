# ISAPS Full Survey Extraction 2020-2024

This folder contains a full extraction pass over the local ISAPS Global Survey PDFs for 2020-2024.

## Source PDFs

- `E:\shared\行业报告\2020isaps-global-survey.pdf`
- `E:\shared\行业报告\2021isaps-global-survey.pdf`
- `E:\shared\行业报告\2022isaps-global-survey.pdf`
- `E:\shared\行业报告\2023isaps-global-survey.pdf`
- `E:\shared\行业报告\2024 isaps-global-survey.pdf`

## Files

- `isaps_raw_page_text_2020_2024.jsonl` / `.csv`
  - One row per PDF page.
  - Use this for source audit, text search, and checking pages that are not yet fully normalized.

- `isaps_raw_table_cells_2020_2024.csv`
  - One row per extracted PDF table cell.
  - This is the broadest "all data" safety layer. It keeps page, table, row, column, cell text, and row text.

- `isaps_normalized_long_2020_2024.csv`
  - One row per normalized data point.
  - Key fields: `source_year`, `data_year`, `metric_family`, `record_role`, `procedure_type`, `procedure_group`, `procedure`, `geo`, `dimension_type`, `dimension`, `value`, `unit`, `percent`, `percent_of_total`, `page`.
  - Use `record_role = current` for report-year trend analysis.
  - Use `record_role = comparator` or `percent_change` when reading the comparison columns printed inside each report.

- `isaps_series_comparability_2020_2024.csv`
  - One row per normalized series key.
  - `trend_5yr`: comparable in all five report years.
  - `trend_partial`: comparable in at least three report years but with gaps.
  - `stage_2yr`: only two report-year observations.
  - `stage_single_year`: one-year/new/retired/one-off metric.

- `isaps_extraction_manifest_2020_2024.json`
  - Run metadata, row counts, metric family counts, and comparability counts.

## Important Notes

- PCL / polycaprolactone does not appear as a normalized ISAPS procedure item in the 2020-2024 PDFs.
- ISAPS does include PLLA, CaHA, HA, botulinum toxin, and in some pages PMMA adoption-rate rows.
- Face/body injectable application is available mainly as plastic-surgeon adoption rate, not as treatment-volume distribution by body part.
- New 2024 procedure items such as buccal fat removal, dimple creation, scar revision, inverted nipple correction, hand rejuvenation with fat grafting, and other outer genital surgery should be treated as stage/new-scope items unless earlier-year continuity is verified.

## Re-run

From `global_aesthetics_dashboard`:

```powershell
$env:PYTHONIOENCODING='utf-8'
& "C:\Users\gisel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "scripts\extract_isaps_full_survey.py"
```

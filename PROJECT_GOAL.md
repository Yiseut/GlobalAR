# Global Aesthetics Verification Goal

This project runs in continuous verification mode. The source workbook is an
editable seed database, not a final fact source.

## Operating Rule

- Do not pause for routine confirmation between batches.
- Continue collecting, comparing, verifying, rebuilding, and syncing until the
  backlog is exhausted or a hard blocker is recorded in the run log.
- Regulator facts use regulator/certificate/label evidence as authority.
- Product and specification facts use official company, brand, product, IFU,
  catalog, or official PDF evidence as authority.
- Parent/listed-company websites, operating-company websites, brand websites,
  and product-line websites remain separate evidence surfaces.
- Secondary media and databases are cross-check leads only.
- China NMPA is excluded from this global project because the China dashboard
  handles it separately.

## Completion Criteria

- Current 8-hour priority: promote FDA/openFDA, EUDAMED/CE, IFU, and
  certificate evidence into `Product_Master` and `Registration_Evidence` before
  continuing broad media/spec enrichment.
- Official product specifications stay blank or candidate-only until the
  official-source search has enough evidence; do not fill specification fields
  from weak snippets.
- Each promoted registration or indication fact must retain source URL, capture
  timestamp, source class, confidence, and a clear regulator/IFU/certificate
  authority label.
- Official approved indications must be recorded as long-form facts:
  product, country/region, regulator, pathway, registration or certificate
  number, official indication, approval date, expiry date when available, and
  source URL. FDA is the first deep source, but the same structure applies to
  CE/MDR, TGA/ARTG, ANVISA, Health Canada, PMDA/MHLW, MHRA/UKCA, HSA/SMDR,
  Malaysia MDA, Thai FDA, Indonesia MoH/AKL, Philippines CMDN/CMDR, Vietnam
  MoH/DMEC, COFEPRIS, Saudi SFDA, Taiwan TFDA and other official regulators.
- Inaccurate seed workbook registration fields must be treated as
  `unverified_seed` or superseded by promoted long-form evidence, not displayed
  as final facts.
- Dashboard pages must distinguish promoted facts from candidate evidence; topic
  pages must show only the selected product segment's scoped evidence.
- Every company in `Company_Master` has an official-source query result or a
  recorded blocker.
- Every listed company / related listed parent has ticker, exchange, listed
  entity, valuation snapshot, and source timestamp.
- Every product family has a commercial official-source trail where available.
- FDA and MDR/CE evidence collection has been attempted for every relevant
  company/product-family priority queue item.
- Product specifications have been extracted into
  `Product_Spec_Evidence` with source URL, timestamp, confidence, and notes.
- Logo and product-image candidates are indexed in `Media_Asset_Index` with
  local paths when downloads succeed.
- `global_aesthetics.db`, `web/app-data.js`, progress reports, and the source
  Excel sheets are rebuilt after each successful batch.
- `scripts/smoke_test.py` passes after rebuild.

## Batch Entry Point

Use:

```powershell
python scripts\run_continuous_verification_batch.py
```

The batch runner appends logs to:

- `data/continuous_run_log.jsonl`
- `data/continuous_run_state.json`

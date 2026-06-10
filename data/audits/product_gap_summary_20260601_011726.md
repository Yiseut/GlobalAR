# Product Gap Verification Queue

Generated: 2026-06-01T01:17:26

## Executive Read

- Products in current master: 1008 across 368 companies.
- Company coverage source: product_master.csv derived.
- Queue rows generated: 1008; P0/P1 review-first rows: 100.
- Unverified seed rows in queue: 70 (6.9%).
- Products without direct official product/family URL: 114 (11.3%).
- Products without direct A/B spec candidate: 120 (11.9%).
- Regulated products without registration evidence: 643.
- Possible product/family additions from existing website/spec signals: 0.

## Operating Decision

- Replace broad webpage/image continuation with this gap queue as the default worklist.
- Promote nothing automatically: official product pages, IFU/catalogs, certificates, FDA/EUDAMED/regulator records remain review evidence until checked.
- Use secondary/search-excerpt rows only as leads; do not merge them into product master without official-source confirmation.
- Direct official URL/spec counts mean linked candidate evidence is present; they are not treated as reviewed facts.
- Missing-product candidates are mined only from already stored website/spec signals; zero candidates is not proof that no product lines are missing.

## Priority Meaning

- P0: high-priority company/product with multiple blocking gaps.
- P1: important product with missing direct evidence or regulated-market proof.
- P2: useful review item, often with some fuzzy leads already present.
- P3: lower-priority monitoring or mostly covered product.

## Top Review Rows

| Priority | Score | Company | Product | Track | Gaps | Next Action |
|---|---:|---|---|---|---|---|
| P0 | 104 | BTL | EMTONE / RF + Mechanical Cellulite Treatment | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company | Cross-check product existence and core positioning against official product page. |
| P0 | 98 | Allergan | Juvéderm Ultra Plus XC / HA Filler for Facial Wrinkles and Folds | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Allergan | Juvéderm Ultra XC / HA Filler for Lip Augmentation | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Allergan | Juvéderm Volbella XC / HA Filler for Lips and Undereye | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Allergan | Juvéderm Vollure XC / HA Filler for Smile Lines | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Allergan | REVOLVE / REVOLVE Advanced Adipose System | Surgical | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Galderma | Restylane Defyne / HA Filler for Deep Facial Folds | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Galderma | Restylane Kysse / HA Filler for Lips | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 98 | Galderma | Restylane Lyft / HA Filler for Cheeks and Hands | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 98 | Galderma | Restylane Refyne / HA Filler for Dynamic Facial Folds | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 98 | Galderma | Restylane Skinboosters Vital Light / HA Skin Quality Booster for Delicate Areas | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 98 | Medytox | NEWLUX / Botulinum Toxin Type A 100U | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Sinclair Pharma | Lanluma / PLLA Collagen Stimulating Injectable Filler | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 98 | Sinclair Pharma | Perfectha / HA Dermal Filler Line | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator <br> priority_company <br> has_review_leads | Review A/B spec candidates and map useful rows to product/family; discard weak C rows. |
| P0 | 94 | Taumedika SRL | Karisma FACE Rh Collagen / Karisma FACE Rh Collagen | Injectables | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> no_reviewed_differentiator | Cross-check product existence and core positioning against official product page. |
| P0 | 90 | Advance Esthetic | Adonyss / CarbonFrax CO2 | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 90 | Advance Esthetic | Adonyss / DioPulse 808 | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 90 | Advance Esthetic | Adonyss / T-Novation | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 90 | Advance Esthetic | Adonyss / OxiPulse | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |
| P0 | 90 | Advance Esthetic | Zemits / CoolRestore Elegance | EBD | master_unverified_seed <br> no_direct_official_product_or_family_url <br> no_direct_spec_candidate <br> no_registration_evidence <br> no_official_indication <br> priority_company <br> has_review_leads | Review fuzzy official product/catalog/IFU URL and attach it to product/family. |

## Files

- Product gap queue: `data\audits\product_gap_queue_20260601_011726.csv`
- Candidate missing product/family rows: `data\audits\candidate_missing_product_lines_20260601_011726.csv`

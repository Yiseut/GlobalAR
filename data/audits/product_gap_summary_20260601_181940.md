# Product Gap Verification Queue

Generated: 2026-06-01T18:19:40

## Executive Read

- Products in current master: 979 across 362 companies.
- Company coverage source: product_master.csv derived.
- Queue rows generated: 875; P0/P1 review-first rows: 0.
- Unverified seed rows in queue: 0 (0.0%).
- Products without direct official product/family URL: 15 (1.7%).
- Products without direct A/B spec candidate: 10 (1.1%).
- Regulated products without registration evidence: 224.
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
| P3 | 18 | Allergan | Juvéderm Ultra XC / HA Filler for Lip Augmentation | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Allergan | Juvéderm Volbella XC / HA Filler for Lips and Undereye | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Allergan | Juvéderm Vollure XC / HA Filler for Smile Lines | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Allergan | LATISSE / Bimatoprost Eyelash Growth | Skincare | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Allergan | REVOLVE / REVOLVE Advanced Adipose System | Surgical | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Galderma | ALASTIN Skincare / TriHex Technology Skincare | Skincare | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Galderma | Restylane Kysse / HA Filler for Lips | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Galderma | Restylane Lyft / HA Filler for Cheeks and Hands | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Galderma | Restylane Refyne / HA Filler for Dynamic Facial Folds | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Galderma | Restylane Skinboosters Vital Light / HA Skin Quality Booster for Delicate Areas | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Sinclair Pharma | Lanluma / PLLA Collagen Stimulating Injectable Filler | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 18 | Sinclair Pharma | Perfectha / HA Dermal Filler Line | Injectables | no_reviewed_differentiator <br> priority_company | Keep as lower-priority monitoring item. |
| P3 | 12 | A.A.M.S. | Concerto / Mesogun | EBD | no_official_indication | Keep as lower-priority monitoring item. |
| P3 | 12 | A.A.M.S. | Ultim / Mesogun | EBD | no_official_indication | Keep as lower-priority monitoring item. |
| P3 | 12 | Allergan | AlloDerm / Regenerative Tissue Matrix | Implants | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |
| P3 | 12 | Allergan | CoolTone / Magnetic Muscle Stimulation | EBD | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |
| P3 | 12 | Allergan | DiamondGlow / Dermal Infusion System | EBD | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |
| P3 | 12 | Allergan | Juvéderm Voluma XC / HA Filler for Midface | Injectables | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |
| P3 | 12 | Allergan | Juvéderm Volux XC / HA Filler for Jawline | Injectables | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |
| P3 | 12 | Alma Lasers | Alma Duo / Focused Shockwave Therapy | EBD | no_reviewed_differentiator <br> priority_company <br> has_review_leads | Keep as lower-priority monitoring item. |

## Files

- Product gap queue: `data\audits\product_gap_queue_20260601_181940.csv`
- Candidate missing product/family rows: `data\audits\candidate_missing_product_lines_20260601_181940.csv`

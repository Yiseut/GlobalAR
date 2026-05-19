# Collection Effectiveness Audit

Generated: 2026-05-19T13:48:06

## Executive Read

- Current run status: `completed`; last batch `batch_20260519_133944`.
- Website queue: 3830 / 19992 website IDs have media/spec scan rows; pending 16167.
- At `--media-websites 8` and recent average batch duration 5.1 min, rough remaining media/spec ETA is 172.7 hours.
- Logo usefulness: 64 / 372 companies currently have at least one downloaded logo candidate.
- Spec usefulness: A=1512 review-first rows, B=22617 candidate rows, C=7317 likely noisy/weak rows.
- Recommendation: 建议把当前网页扫描从“广泛继续跑”改成“缺口驱动”：logo 使用本地已下载资产先接入；产品规格只保留 A/B 级线索进入人工审核，C 级作为噪声样本，不继续为产品图片扩大下载。

## What The Current Pipeline Is Capturing

- `official_website_master.csv`: candidate official/company/product-line URLs.
- `company_media_asset_index.csv`: parsed image/logo candidates and page scan markers from those URLs.
- `product_specification_evidence.csv`: regex-extracted specification candidates from official pages and search excerpts.
- These are staging/review signals. They are not reviewed master facts yet.

## Coverage

- Official website rows: 19992 across 372 companies and 19992 website IDs.
- Website scope mix: product_line=13956, operating_company=5832, listed_parent=204.
- Website candidate flags: likely=9966, possible=7756, unknown=2270.
- Media/spec rows: 6665; status mix: downloaded=5169, error=794, download_failed=349, processed_no_asset=210, processed_no_logo=136, processed_specs_only=7.
- Logo candidates: 4418 downloaded / 4688 total rows.
- Product image candidates: 588 downloaded / 645 total rows.

## Specification Quality

- Total spec rows: 31446.
- Product-context rows: 28712 (91.3%).
- Tier mix: B_candidate_pool=22617, C_review_noise=7317, A_review_first=1512.
- Main noise reasons: search_excerpt_with_product_context=22617, weak_short_value=4829, missing_product_identity=1906, official_site_with_product_context=1512, garbled_or_binary_excerpt=582.
- Category mix: material_or_ingredient=9049, packaging=7634, device_energy=6873, dose_strength=3565, volume_packaging=3068, commercial_certification=1257.
- Confidence mix: official_search_excerpt_spec_candidate=26981, official_site_spec_candidate=4465.
- Top source domains: fda.innolitics.com=834, accessdata.fda.gov=629, pdf.medicalexpo.com=384, tradekorea.com=302, france-health.com=272, lumenis.com=265, cynosure.com=237, medicalexpo.com=231, candelamedical.com=202, tga.gov.au=196.

## Cost / Value Judgment

- The pipeline is currently doing page fetch + HTML/spec parsing; after `--download-logos-only`, it is no longer intentionally downloading product images, but it still scans pages for logos and specs.
- Logo extraction is useful as an asset-finding pass, but current coverage is incomplete and should now be normalized from existing local files rather than expanded blindly.
- Spec extraction has a real candidate pool, but it mixes useful official-page rows with weak regex matches and binary/PDF noise. It needs review-tier filtering before any table promotion.
- The broad media/spec queue is large enough that continuing it unchanged is a poor default unless a specific gap list justifies it.

## Review Files

- Spec quality sample: `data\audits\spec_quality_sample_20260519_134806.csv`
- Logo coverage table: `data\audits\logo_candidate_coverage_20260519_134806.csv`

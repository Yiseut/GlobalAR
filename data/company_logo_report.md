# Company Logo Normalization Report

Generated: 2026-05-23T01:25:45

- Companies: 371
- Normalized logos: 62
- Missing or skipped: 309
- Status mix: missing_downloaded_logo=308, no_usable_raster_logo=1, ok=62
- Display mix: candidate_hidden=7, not_available=309, trusted_display=55
- Output size: 256x256 PNG, transparent canvas, artwork scaled proportionally.
- Manifest: `data\company_logo_manifest.csv`
- Logo directory: `web\assets\company_logos`

Notes:
- SVG-only candidates are skipped in this pass because the current environment has no stable SVG rasterizer.
- Light/white source backgrounds are removed conservatively; non-uniform opaque backgrounds are preserved to avoid damaging marks.

"""Normalize downloaded company logo candidates for the dashboard.

The output image size is fixed at 256x256 for stable frontend layout, but the
logo artwork is never stretched. It is scaled proportionally and centered on a
transparent canvas.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
MEDIA_INDEX_PATH = DATA_DIR / "company_media_asset_index.csv"
PROFILE_PATH = DATA_DIR / "company_profiles_bridge.json"
MANIFEST_PATH = DATA_DIR / "company_logo_manifest.csv"
REPORT_PATH = DATA_DIR / "company_logo_report.md"
LOGO_OUT_DIR = WEB_DIR / "assets" / "company_logos"

CANVAS_SIZE = 256
ARTWORK_MAX = 224
SUPPORTED_RASTER = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".avif"}

ROLE_PRIORITY = {
    "operating_company_logo_img": 0,
    "listed_parent_logo_img": 1,
    "favicon_or_touch_icon": 2,
    "product_line_logo_img": 3,
}
SCOPE_PRIORITY = {"operating_company": 0, "listed_parent": 1, "product_line": 2}
EXT_PRIORITY = {".png": 0, ".webp": 1, ".jpg": 2, ".jpeg": 2, ".ico": 3, ".gif": 4, ".avif": 4}
DISPLAY_ALLOWED_SCOPES = {"operating_company", "listed_parent"}
DISPLAY_ALLOWED_ROLES = {"operating_company_logo_img", "listed_parent_logo_img", "favicon_or_touch_icon"}
TRUSTED_DISPLAY_STATUSES = {"trusted_display", "approved_display"}
GENERIC_COMPANY_TOKENS = {
    "aesthetic",
    "aesthetics",
    "beauty",
    "bio",
    "biotech",
    "company",
    "corp",
    "corporation",
    "derma",
    "dermatology",
    "group",
    "holding",
    "holdings",
    "inc",
    "international",
    "lab",
    "laboratoire",
    "laboratories",
    "ltd",
    "medical",
    "medicine",
    "pharma",
    "pharmaceutical",
    "pharmaceuticals",
    "srl",
    "technology",
    "technologies",
}
BLOCKED_TEXT_HINTS = {
    "amazon",
    "bazaar",
    "bloomberg",
    "cbinsights",
    "daltonmedical",
    "fda_search_drug",
    "fliphtml5",
    "harper",
    "harpers",
    "linkedin",
    "marketplace",
    "marketscreener",
    "medicalexpo",
    "moph.go.th",
    "pharmaboardroom",
    "pitchbook",
    "repository.usmf",
    "wikipedia",
}
NON_COMPANY_HOST_HINTS = (
    "amazon.",
    "bloomberg.",
    "cbinsights.",
    "facebook.",
    "fda.moph.go.th",
    "fliphtml5.",
    "instagram.",
    "linkedin.",
    "marketscreener.",
    "medicalexpo.",
    "pharmaboardroom.",
    "pitchbook.",
    "repository.usmf.",
    "wikipedia.",
    "youtube.",
)


@dataclass
class ImageInfo:
    path: Path
    width: int
    height: int
    has_alpha: bool
    error: str = ""


def clean(value: Any) -> str:
    return str(value or "").strip()


def url_slug(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "company"


def compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def text_tokens(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", clean(value).lower()) if len(token) >= 3]


def host_from_url(value: str) -> str:
    parsed = urllib.parse.urlparse(clean(value))
    host = (parsed.netloc or "").lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def unique_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def company_identity_tokens(company: str) -> list[str]:
    compact = compact_text(company)
    tokens = [token for token in text_tokens(company) if token not in GENERIC_COMPANY_TOKENS]
    values = []
    if len(compact) >= 4:
        values.append(compact)
    values.extend(token for token in tokens if len(token) >= 3)
    return unique_list(values)


def candidate_public_text(row: dict[str, str]) -> str:
    # Do not include local_path here: it contains the company folder and would
    # make every downloaded candidate appear to match the company.
    fields = [
        clean(row.get("source_page_url")),
        clean(row.get("image_url")),
        clean(row.get("notes")),
        clean(row.get("file_name")),
    ]
    return " ".join(field for field in fields if field)


def blocked_logo_candidate(row: dict[str, str]) -> bool:
    text = candidate_public_text(row).lower()
    return any(hint in text for hint in BLOCKED_TEXT_HINTS)


def source_matches_company(row: dict[str, str], company: str) -> bool:
    tokens = company_identity_tokens(company)
    if not tokens:
        return False
    host_text = compact_text(
        " ".join(
            [
                host_from_url(clean(row.get("source_page_url"))),
                host_from_url(clean(row.get("image_url"))),
            ]
        )
    )
    public_text = compact_text(candidate_public_text(row))
    return any(token in host_text or token in public_text for token in tokens)


def non_company_host(row: dict[str, str]) -> bool:
    hosts = [
        host_from_url(clean(row.get("source_page_url"))),
        host_from_url(clean(row.get("image_url"))),
    ]
    text = " ".join(host for host in hosts if host)
    return any(hint in text for hint in NON_COMPANY_HOST_HINTS)


def classify_logo_display(company: str, row: dict[str, str]) -> tuple[str, str]:
    scope = clean(row.get("entity_scope"))
    role = clean(row.get("asset_role"))
    if scope not in DISPLAY_ALLOWED_SCOPES:
        return "candidate_hidden", "not_company_level_logo"
    if role not in DISPLAY_ALLOWED_ROLES:
        return "candidate_hidden", "not_company_display_role"
    if blocked_logo_candidate(row):
        return "candidate_hidden", "blocked_third_party_or_media_logo_hint"
    if not source_matches_company(row, company):
        return "candidate_hidden", "source_does_not_match_company_identity"
    if non_company_host(row) and not source_matches_company(row, company):
        return "candidate_hidden", "non_company_source_host"
    return "trusted_display", "company_identity_match"


def rel_web_path(path: Path) -> str:
    return "./" + path.relative_to(WEB_DIR).as_posix()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def resolve_asset_path(local_path: str) -> Path:
    path = Path(local_path)
    if path.is_absolute():
        return path
    return ROOT / path


def inspect_image(path: Path) -> ImageInfo:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_RASTER:
        return ImageInfo(path=path, width=0, height=0, has_alpha=False, error=f"unsupported_extension:{suffix}")
    try:
        with Image.open(path) as image:
            if getattr(image, "is_animated", False):
                image.seek(0)
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            extrema = alpha.getextrema()
            return ImageInfo(
                path=path,
                width=rgba.width,
                height=rgba.height,
                has_alpha=bool(extrema and extrema[0] < 250),
            )
    except Exception as exc:  # noqa: BLE001 - report and skip bad downloaded files.
        return ImageInfo(path=path, width=0, height=0, has_alpha=False, error=exc.__class__.__name__)


def image_key(row: dict[str, str], info: ImageInfo) -> tuple[int, int, int, int, int, str]:
    role_rank = ROLE_PRIORITY.get(clean(row.get("asset_role")), 9)
    scope_rank = SCOPE_PRIORITY.get(clean(row.get("entity_scope")), 9)
    suffix = info.path.suffix.lower()
    ext_rank = EXT_PRIORITY.get(suffix, 9)
    max_side = max(info.width, info.height)
    tiny_rank = 2 if max_side < 64 else 1 if max_side < 128 else 0
    area_rank = -(info.width * info.height)
    return (role_rank, scope_rank, tiny_rank, ext_rank, area_rank, clean(row.get("asset_id")))


def load_companies() -> list[str]:
    payload = read_json(PROFILE_PATH, {})
    companies = []
    if isinstance(payload, dict):
        for item in payload.get("companies", []):
            if isinstance(item, dict) and clean(item.get("company")):
                companies.append(clean(item.get("company")))
    return sorted(set(companies), key=str.casefold)


def logo_candidates_by_company(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        if clean(row.get("asset_type")) != "logo_candidate":
            continue
        if clean(row.get("review_status")) != "downloaded":
            continue
        if not clean(row.get("local_path")):
            continue
        company = clean(row.get("company"))
        if not company:
            continue
        grouped.setdefault(company, []).append(row)
    return grouped


def load_rgba(path: Path) -> Image.Image:
    with Image.open(path) as image:
        if getattr(image, "is_animated", False):
            image.seek(0)
        return image.convert("RGBA")


def close_rgb(a: tuple[int, int, int], b: tuple[int, int, int], tolerance: int) -> bool:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) <= tolerance


def remove_uniform_light_background(image: Image.Image) -> tuple[Image.Image, str]:
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    if extrema and extrema[0] < 250:
        return image, "alpha_preserved"

    width, height = image.size
    corners = [
        image.getpixel((0, 0))[:3],
        image.getpixel((width - 1, 0))[:3],
        image.getpixel((0, height - 1))[:3],
        image.getpixel((width - 1, height - 1))[:3],
    ]
    avg = tuple(round(sum(color[i] for color in corners) / len(corners)) for i in range(3))
    if min(avg) < 225:
        return image, "opaque_source"
    if any(not close_rgb(color, avg, 18) for color in corners):
        return image, "opaque_source"

    pixels = image.load()
    transparent = 0
    total = width * height
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a and min(r, g, b) >= 218 and close_rgb((r, g, b), avg, 30):
                pixels[x, y] = (r, g, b, 0)
                transparent += 1

    if transparent / max(total, 1) < 0.03:
        return image, "opaque_source"
    return image, "light_background_removed"


def normalize_image(src: Path, dest: Path) -> tuple[str, int, int]:
    image = load_rgba(src)
    image, background_status = remove_uniform_light_background(image)
    src_width, src_height = image.size
    scale = min(ARTWORK_MAX / max(src_width, 1), ARTWORK_MAX / max(src_height, 1), 1.0)
    new_size = (max(1, round(src_width * scale)), max(1, round(src_height * scale)))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    resized = image.resize(new_size, resample=resample)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
    offset = ((CANVAS_SIZE - new_size[0]) // 2, (CANVAS_SIZE - new_size[1]) // 2)
    canvas.alpha_composite(resized, dest=offset)
    dest.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest, format="PNG", optimize=True)
    return background_status, src_width, src_height


def select_logo(
    company: str, candidates: list[dict[str, str]]
) -> tuple[dict[str, str] | None, ImageInfo | None, list[str], str, str]:
    inspected: list[tuple[dict[str, str], ImageInfo, str, str]] = []
    errors: list[str] = []
    for row in candidates:
        path = resolve_asset_path(clean(row.get("local_path")))
        if not path.exists():
            errors.append(f"{clean(row.get('asset_id'))}:missing_file")
            continue
        info = inspect_image(path)
        if info.error:
            errors.append(f"{clean(row.get('asset_id'))}:{info.error}")
            continue
        display_status, display_reason = classify_logo_display(company, row)
        inspected.append((row, info, display_status, display_reason))
    if not inspected:
        return None, None, errors, "", ""
    trusted = [item for item in inspected if item[2] in TRUSTED_DISPLAY_STATUSES]
    pool = trusted or inspected
    row, info, display_status, display_reason = sorted(pool, key=lambda item: image_key(item[0], item[1]))[0]
    return row, info, errors, display_status, display_reason


def build_report(rows: list[dict[str, Any]], generated_at: str) -> str:
    total = len(rows)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[clean(row.get("status"))] = status_counts.get(clean(row.get("status")), 0) + 1
    success = status_counts.get("ok", 0)
    skipped = total - success
    display_counts: dict[str, int] = {}
    for row in rows:
        display_counts[clean(row.get("display_status"))] = display_counts.get(clean(row.get("display_status")), 0) + 1
    status_text = ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items()))
    display_text = ", ".join(f"{key}={value}" for key, value in sorted(display_counts.items()))
    return "\n".join(
        [
            "# Company Logo Normalization Report",
            "",
            f"Generated: {generated_at}",
            "",
            f"- Companies: {total}",
            f"- Normalized logos: {success}",
            f"- Missing or skipped: {skipped}",
            f"- Status mix: {status_text}",
            f"- Display mix: {display_text}",
            f"- Output size: {CANVAS_SIZE}x{CANVAS_SIZE} PNG, transparent canvas, artwork scaled proportionally.",
            f"- Manifest: `{MANIFEST_PATH.relative_to(ROOT)}`",
            f"- Logo directory: `{LOGO_OUT_DIR.relative_to(ROOT)}`",
            "",
            "Notes:",
            "- SVG-only candidates are skipped in this pass because the current environment has no stable SVG rasterizer.",
            "- Light/white source backgrounds are removed conservatively; non-uniform opaque backgrounds are preserved to avoid damaging marks.",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    companies = load_companies()
    media_rows = read_csv_rows(MEDIA_INDEX_PATH)
    candidates = logo_candidates_by_company(media_rows)
    generated_at = datetime.now().isoformat(timespec="seconds")
    manifest_rows: list[dict[str, Any]] = []

    for company in companies:
        company_candidates = candidates.get(company, [])
        selected, info, errors, display_status, display_reason = select_logo(company, company_candidates)
        slug = url_slug(company)
        output_path = LOGO_OUT_DIR / f"{slug}.png"
        row: dict[str, Any] = {
            "company": company,
            "company_slug": slug,
            "status": "missing_downloaded_logo",
            "web_path": "",
            "output_path": "",
            "source_asset_id": "",
            "source_role": "",
            "source_scope": "",
            "source_page_url": "",
            "source_url": "",
            "source_local_path": "",
            "source_ext": "",
            "source_width": "",
            "source_height": "",
            "background_status": "",
            "display_status": "not_available",
            "display_reason": "",
            "notes": "; ".join(errors[:5]),
            "generated_at": generated_at,
        }
        if selected and info:
            try:
                background_status, src_width, src_height = ("dry_run", info.width, info.height)
                if not args.dry_run:
                    background_status, src_width, src_height = normalize_image(info.path, output_path)
                row.update(
                    {
                        "status": "ok",
                        "web_path": rel_web_path(output_path),
                        "output_path": str(output_path.relative_to(ROOT)),
                        "source_asset_id": clean(selected.get("asset_id")),
                        "source_role": clean(selected.get("asset_role")),
                        "source_scope": clean(selected.get("entity_scope")),
                        "source_page_url": clean(selected.get("source_page_url")),
                        "source_url": clean(selected.get("image_url")),
                        "source_local_path": clean(selected.get("local_path")),
                        "source_ext": info.path.suffix.lower(),
                        "source_width": src_width,
                        "source_height": src_height,
                        "background_status": background_status,
                        "display_status": display_status or "candidate_hidden",
                        "display_reason": display_reason,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - keep processing other companies.
                row.update({"status": "normalize_failed", "notes": f"{exc.__class__.__name__}: {exc}"})
        elif company_candidates:
            row.update({"status": "no_usable_raster_logo"})
        manifest_rows.append(row)

    fieldnames = [
        "company",
        "company_slug",
        "status",
        "web_path",
        "output_path",
        "source_asset_id",
        "source_role",
        "source_scope",
        "source_page_url",
        "source_url",
        "source_local_path",
        "source_ext",
        "source_width",
        "source_height",
        "background_status",
        "display_status",
        "display_reason",
        "notes",
        "generated_at",
    ]

    if not args.dry_run:
        write_csv(MANIFEST_PATH, manifest_rows, fieldnames)
        REPORT_PATH.write_text(build_report(manifest_rows, generated_at), encoding="utf-8")

    summary = {
        "companies": len(manifest_rows),
        "normalized": sum(1 for row in manifest_rows if row["status"] == "ok"),
        "missing_or_skipped": sum(1 for row in manifest_rows if row["status"] != "ok"),
        "manifest": str(MANIFEST_PATH),
        "report": str(REPORT_PATH),
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

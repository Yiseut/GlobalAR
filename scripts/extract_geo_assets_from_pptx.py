from __future__ import annotations

import json
import math
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SOURCE_DIR = Path(r"E:\shared\设计\素材\地图")
PROJECT_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = PROJECT_DIR / "web" / "v3" / "assets" / "geo"
FLAG_DIR = OUT_DIR / "flags"
MAP_DIR = OUT_DIR / "maps"
MANIFEST_JSON = OUT_DIR / "manifest.json"
MANIFEST_JS = PROJECT_DIR / "web" / "v3" / "v3-geo-assets.js"

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"


COUNTRY_ALIASES = {
    "Bulgary": "Bulgaria",
    "Czech": "Czech Republic",
    "New Zeland": "New Zealand",
    "USA": "United States",
    "UAE": "United Arab Emirates",
    "Dem. Rep. Congo": "Democratic Republic of the Congo",
    "Ivory Coast": "Cote d'Ivoire",
    "England": "United Kingdom",
    "Scotland": "United Kingdom",
    "Wales": "United Kingdom",
    "Northern Ireland": "United Kingdom",
}

JS_ALIASES = {
    "US": "United States",
    "USA": "United States",
    "United States of America": "United States",
    "UK": "United Kingdom",
    "Britain": "United Kingdom",
    "Great Britain": "United Kingdom",
    "Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "Korea, Republic of": "South Korea",
    "Chinese Taipei": "Taiwan",
    "Czechia": "Czech Republic",
    "Turkiye": "Turkey",
    "UAE": "United Arab Emirates",
    "Cote d’Ivoire": "Cote d'Ivoire",
    "Côte d'Ivoire": "Cote d'Ivoire",
    "Democratic Republic Congo": "Democratic Republic of the Congo",
}

MAP_SOURCES = {
    "world": ("World_maps.pptx", 1, "World map"),
    "asia": ("Asia.pptx", 1, "Asia"),
    "europe": ("Europe.pptx", 1, "Europe"),
    "africa": ("Africa.pptx", 1, "Africa"),
    "north-america": ("North America.pptx", 1, "North America"),
    "south-america": ("South_America.pptx", 1, "South America"),
    "oceania": ("Oceania.pptx", 1, "Oceania"),
    "continents": ("Continents.pptx", 1, "Continents"),
}


def clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def slugify(value: str) -> str:
    text = clean_label(value).lower()
    text = text.replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unknown"


def canonical_country(label: str) -> str:
    label = clean_label(label)
    return COUNTRY_ALIASES.get(label, label)


def read_rels(zf: zipfile.ZipFile, slide_no: int) -> dict[str, str]:
    rel_path = f"ppt/slides/_rels/slide{slide_no}.xml.rels"
    if rel_path not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read(rel_path))
    return {rel.attrib.get("Id", ""): rel.attrib.get("Target", "") for rel in root}


def xfrm_box(node: ET.Element | None) -> tuple[float, float, float, float]:
    if node is None:
        return 0, 0, 0, 0
    off = node.find("a:off", NS)
    ext = node.find("a:ext", NS)
    x = float(off.attrib.get("x", 0)) if off is not None else 0
    y = float(off.attrib.get("y", 0)) if off is not None else 0
    cx = float(ext.attrib.get("cx", 0)) if ext is not None else 0
    cy = float(ext.attrib.get("cy", 0)) if ext is not None else 0
    return x, y, cx, cy


def extract_flags() -> list[dict[str, object]]:
    pptx = SOURCE_DIR / "Flags.pptx"
    if not pptx.exists():
        raise FileNotFoundError(pptx)

    FLAG_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    seen_slug: set[str] = set()

    with zipfile.ZipFile(pptx) as zf:
        slide_names = sorted(
            [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=lambda name: int(re.search(r"(\d+)", name).group(1)),
        )
        for slide_name in slide_names:
            slide_no = int(re.search(r"(\d+)", slide_name).group(1))
            root = ET.fromstring(zf.read(slide_name))
            rels = read_rels(zf, slide_no)

            labels = []
            for sp in root.findall(".//p:sp", NS):
                text = clean_label(" ".join(t.text or "" for t in sp.findall(".//a:t", NS)))
                if not text or text.isupper():
                    continue
                x, y, cx, cy = xfrm_box(sp.find(".//a:xfrm", NS))
                labels.append({"label": text, "x": x, "y": y, "cx": cx, "cy": cy, "center": x + cx / 2})

            pics = []
            for pic in root.findall(".//p:pic", NS):
                blip = pic.find(".//a:blip", NS)
                rid = blip.attrib.get(R_EMBED) if blip is not None else ""
                target = rels.get(rid, "")
                if not target.lower().endswith(".png"):
                    continue
                x, y, cx, cy = xfrm_box(pic.find(".//a:xfrm", NS))
                pics.append({"target": target, "x": x, "y": y, "cx": cx, "cy": cy, "center": x + cx / 2})

            for pic in pics:
                candidates = [
                    label
                    for label in labels
                    if label["y"] >= pic["y"] + pic["cy"] * 0.65
                    and abs(label["center"] - pic["center"]) < max(pic["cx"], label["cx"]) * 0.65
                ]
                if not candidates:
                    continue
                label = min(candidates, key=lambda item: (item["y"] - pic["y"], abs(item["center"] - pic["center"])))
                original = str(label["label"])
                country = canonical_country(original)
                slug = slugify(country)
                if slug in seen_slug:
                    continue
                seen_slug.add(slug)
                src = ("ppt/" + pic["target"].lstrip("../")).replace("\\", "/")
                dest_name = f"{slug}.png"
                with zf.open(src) as fh, (FLAG_DIR / dest_name).open("wb") as out:
                    shutil.copyfileobj(fh, out)
                entries.append(
                    {
                        "country": country,
                        "originalLabel": original,
                        "slug": slug,
                        "file": f"assets/geo/flags/{dest_name}",
                        "source": "Flags.pptx",
                        "slide": slide_no,
                    }
                )
        if "united-states" not in seen_slug:
            src = "ppt/media/image85.png"
            dest_name = "united-states.png"
            with zf.open(src) as fh, (FLAG_DIR / dest_name).open("wb") as out:
                shutil.copyfileobj(fh, out)
            entries.append(
                {
                    "country": "United States",
                    "originalLabel": "USA",
                    "slug": "united-states",
                    "file": f"assets/geo/flags/{dest_name}",
                    "source": "Flags.pptx",
                    "slide": 10,
                    "note": "Fallback for a non-standard text container in the source deck.",
                }
            )
    return sorted(entries, key=lambda row: str(row["country"]))


def get_text(sp: ET.Element) -> str:
    return clean_label(" ".join(t.text or "" for t in sp.findall(".//a:t", NS)))


def point_from_pt(pt: ET.Element) -> tuple[float, float]:
    return float(pt.attrib.get("x", 0)), float(pt.attrib.get("y", 0))


def path_to_commands(path: ET.Element, shape_box: tuple[float, float, float, float], transform) -> tuple[str, list[tuple[float, float]]]:
    pw = float(path.attrib.get("w", 1) or 1)
    ph = float(path.attrib.get("h", 1) or 1)
    sx, sy, scx, scy = shape_box
    commands: list[str] = []
    points: list[tuple[float, float]] = []

    def convert(x: float, y: float) -> tuple[float, float]:
        px = sx + x / pw * scx
        py = sy + y / ph * scy
        ox, oy = transform(px, py)
        ox /= 10000.0
        oy /= 10000.0
        points.append((ox, oy))
        return ox, oy

    for child in path:
        tag = child.tag.split("}", 1)[-1]
        pts = [point_from_pt(pt) for pt in child.findall("a:pt", NS)]
        if tag == "moveTo" and pts:
            x, y = convert(*pts[0])
            commands.append(f"M{x:.3f},{y:.3f}")
        elif tag == "lnTo" and pts:
            x, y = convert(*pts[0])
            commands.append(f"L{x:.3f},{y:.3f}")
        elif tag == "cubicBezTo" and len(pts) == 3:
            coords = [convert(*pt) for pt in pts]
            commands.append("C" + " ".join(f"{x:.3f},{y:.3f}" for x, y in coords))
        elif tag == "quadBezTo" and len(pts) == 2:
            coords = [convert(*pt) for pt in pts]
            commands.append("Q" + " ".join(f"{x:.3f},{y:.3f}" for x, y in coords))
        elif tag == "close":
            commands.append("Z")
    return " ".join(commands), points


def compose_group_transform(parent_transform, xfrm: ET.Element | None):
    if xfrm is None:
        return parent_transform
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    ch_off = xfrm.find("a:chOff", NS)
    ch_ext = xfrm.find("a:chExt", NS)
    ox = float(off.attrib.get("x", 0)) if off is not None else 0
    oy = float(off.attrib.get("y", 0)) if off is not None else 0
    ex = float(ext.attrib.get("cx", 1)) if ext is not None else 1
    ey = float(ext.attrib.get("cy", 1)) if ext is not None else 1
    cox = float(ch_off.attrib.get("x", 0)) if ch_off is not None else 0
    coy = float(ch_off.attrib.get("y", 0)) if ch_off is not None else 0
    cex = float(ch_ext.attrib.get("cx", ex)) if ch_ext is not None else ex
    cey = float(ch_ext.attrib.get("cy", ey)) if ch_ext is not None else ey
    cex = cex or 1
    cey = cey or 1

    def transform(x: float, y: float) -> tuple[float, float]:
        gx = ox + (x - cox) * ex / cex
        gy = oy + (y - coy) * ey / cey
        return parent_transform(gx, gy)

    return transform


def shape_paths(sp: ET.Element, transform) -> list[tuple[str, str, list[tuple[float, float]]]]:
    if get_text(sp):
        return []
    name_node = sp.find(".//p:cNvPr", NS)
    name = name_node.attrib.get("name", "") if name_node is not None else ""
    shape_box = xfrm_box(sp.find(".//a:xfrm", NS))
    out = []
    for path in sp.findall(".//a:path", NS):
        d, pts = path_to_commands(path, shape_box, transform)
        if d and pts:
            out.append((name, d, pts))
    return out


def iter_shape_paths(node: ET.Element, transform) -> list[tuple[str, str, list[tuple[float, float]]]]:
    rows: list[tuple[str, str, list[tuple[float, float]]]] = []
    for child in list(node):
        local = child.tag.split("}", 1)[-1]
        if local == "sp":
            rows.extend(shape_paths(child, transform))
        elif local == "grpSp":
            group_transform = compose_group_transform(transform, child.find("p:grpSpPr/a:xfrm", NS))
            rows.extend(iter_shape_paths(child, group_transform))
    return rows


def extract_map_svg(key: str, pptx_name: str, slide_no: int, label: str) -> dict[str, object]:
    pptx = SOURCE_DIR / pptx_name
    if not pptx.exists():
        raise FileNotFoundError(pptx)
    with zipfile.ZipFile(pptx) as zf:
        root = ET.fromstring(zf.read(f"ppt/slides/slide{slide_no}.xml"))
    identity = lambda x, y: (x, y)
    paths = iter_shape_paths(root.find("p:cSld/p:spTree", NS) or root, identity)
    if not paths:
        raise RuntimeError(f"No vector paths found in {pptx_name} slide {slide_no}")

    all_points = [pt for _, _, pts in paths for pt in pts if math.isfinite(pt[0]) and math.isfinite(pt[1])]
    min_x = min(x for x, _ in all_points)
    min_y = min(y for _, y in all_points)
    max_x = max(x for x, _ in all_points)
    max_y = max(y for _, y in all_points)
    pad = max(max_x - min_x, max_y - min_y) * 0.035
    view = (min_x - pad, min_y - pad, (max_x - min_x) + pad * 2, (max_y - min_y) + pad * 2)

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    dest = MAP_DIR / f"{key}.svg"
    path_markup = "\n".join(
        f'  <path class="geo-map-land" data-name="{escape_xml(name)}" d="{d}" />' for name, d, _ in paths
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view[0]:.3f} {view[1]:.3f} {view[2]:.3f} {view[3]:.3f}" role="img" aria-label="{escape_xml(label)}">
  <style>
    .geo-map-land {{ fill: #d7cdc0; stroke: rgba(83, 74, 82, 0.38); stroke-width: 0.08; vector-effect: non-scaling-stroke; }}
  </style>
{path_markup}
</svg>
'''
    dest.write_text(svg, encoding="utf-8")
    return {
        "key": key,
        "label": label,
        "file": f"assets/geo/maps/{key}.svg",
        "source": pptx_name,
        "slide": slide_no,
        "paths": len(paths),
    }


def escape_xml(value: str) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_manifest(flags: list[dict[str, object]], maps: list[dict[str, object]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generatedFrom": str(SOURCE_DIR),
        "flags": flags,
        "maps": maps,
        "aliases": JS_ALIASES,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    country_map = {row["country"]: row["file"] for row in flags}
    map_files = {row["key"]: row["file"] for row in maps}
    js = f'''(function () {{
  const FLAGS = {json.dumps(country_map, ensure_ascii=False, indent=2)};
  const MAPS = {json.dumps(map_files, ensure_ascii=False, indent=2)};
  const ALIASES = {json.dumps(JS_ALIASES, ensure_ascii=False, indent=2)};

  function esc(value) {{
    return String(value || "").replace(/[&<>"']/g, ch => ({{
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }})[ch]);
  }}

  function canonicalCountry(value) {{
    const text = String(value || "").trim();
    return ALIASES[text] || text;
  }}

  function flagUrl(country) {{
    const key = canonicalCountry(country);
    return FLAGS[key] || null;
  }}

  function flagHTML(country, className) {{
    const url = flagUrl(country);
    if (!url) return "";
    const label = canonicalCountry(country);
    const cls = className || "geo-flag";
    return `<img class="${{esc(cls)}}" src="${{esc(url)}}" alt="${{esc(label)}} flag" loading="lazy" decoding="async">`;
  }}

  function mapUrl(key) {{
    return MAPS[key] || null;
  }}

  window.V3_GEO_ASSETS = {{ flags: FLAGS, maps: MAPS, aliases: ALIASES, canonicalCountry, flagUrl, flagHTML, mapUrl }};
}})();
'''
    MANIFEST_JS.write_text(js, encoding="utf-8")


def main() -> None:
    flags = extract_flags()
    maps = [extract_map_svg(key, pptx, slide, label) for key, (pptx, slide, label) in MAP_SOURCES.items()]
    write_manifest(flags, maps)
    print(json.dumps({"flags": len(flags), "maps": len(maps), "out": str(OUT_DIR)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

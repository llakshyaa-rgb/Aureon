"""Local vector creative studio: original SVG artwork, mockup previews and print QA.

This is deterministic artwork generation, not a hosted image model. It creates
editable vector assets locally and records provenance and validation results.
"""
import html
import math
import re
import xml.etree.ElementTree as ET
from .workflows import create_record, list_records

PALETTES = {
    "midnight": ("#10172A", "#F4E9D8", "#7BDFF2", "#F7A8B8"),
    "sunset": ("#24152F", "#FFF0D8", "#FF8A5B", "#F6C85F"),
    "forest": ("#102820", "#F1E9D2", "#A8D5BA", "#E9AFA3"),
    "mono": ("#111111", "#FFFFFF", "#A8A8A8", "#E5E5E5"),
    "ocean": ("#092B3B", "#EAF7F7", "#5BC0BE", "#F4D35E"),
}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _text(value, label, limit):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(label + " must be 1-" + str(limit) + " characters")
    return re.sub(r"\s+", " ", value.strip())


def _wrap(text, max_chars):
    words = text.split()
    lines, current = [], ""
    for word in words:
        if len(word) > max_chars:
            word = word[:max_chars]
        candidate = (current + " " + word).strip()
        if len(candidate) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines[:4]


def validate_svg_artwork(svg, width=4500, height=5400, safe_margin=250):
    if not isinstance(svg, str) or not svg.startswith("<svg ") or len(svg) > 200000:
        raise ValueError("artwork must be an SVG document under 200 KB")
    lowered = svg.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise ValueError("SVG declarations and entities are not allowed")
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        raise ValueError("artwork must be well-formed SVG XML") from None
    allowed_tags = {"svg", "g", "circle", "ellipse", "text", "path"}
    allowed_attrs = {"xmlns", "width", "height", "viewBox", "role", "aria-label",
                     "fill", "stroke", "stroke-width", "transform", "cx", "cy", "r",
                     "rx", "ry", "x", "y", "text-anchor", "font-family", "font-size",
                     "font-weight", "letter-spacing", "d"}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in allowed_tags:
            raise ValueError("unsupported SVG element: " + tag)
        for attr, value in element.attrib.items():
            name = attr.rsplit("}", 1)[-1]
            if name not in allowed_attrs or "url(" in value.lower() or "javascript:" in value.lower():
                raise ValueError("unsupported or active SVG attribute: " + name)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("artwork root must be SVG")
    checks = {
        "svg_document": True,
        "print_dimensions": width >= 3000 and height >= 3000,
        "transparent_background": 'background="' not in svg and "<rect" not in svg,
        "safe_area": isinstance(safe_margin, int) and safe_margin >= 150,
        "file_size": len(svg.encode("utf-8")) <= 200000,
        "vector_format": True,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "dimensions_px": {"width": width, "height": height},
            "safe_margin_px": safe_margin,
            "warnings": ["Review trademark/copyright and print-provider templates manually.",
                         "SVG preview is vector artwork; raster export is not included."]}


def generate_vector_artwork(title, concept, style="orbit", palette="midnight",
                            accent=None, width=4500, height=5400):
    title = _text(title, "title", 80)
    concept = _text(concept, "concept", 240)
    style = _text(style, "style", 30).lower()
    if style not in {"orbit", "badge", "type", "botanical", "geometric"}:
        raise ValueError("style must be orbit, badge, type, botanical or geometric")
    if palette not in PALETTES:
        raise ValueError("unknown palette")
    if isinstance(width, bool) or not isinstance(width, int) or not 3000 <= width <= 9000:
        raise ValueError("width must be 3000..9000 pixels")
    if isinstance(height, bool) or not isinstance(height, int) or not 3000 <= height <= 12000:
        raise ValueError("height must be 3000..12000 pixels")
    bg, fg, a, b = PALETTES[palette]
    if accent is not None:
        if not isinstance(accent, str) or not HEX.fullmatch(accent):
            raise ValueError("accent must be a six-digit hex color")
        a = accent
    cx, cy = width // 2, height // 2
    lines = _wrap(title.upper(), 18)
    title_svg = "".join(
        '<text x="{}" y="{}" text-anchor="middle" font-family="sans-serif" '
        'font-size="{}" font-weight="800" letter-spacing="18" fill="{}">{}</text>'.format(
            cx, cy + (i - (len(lines)-1)/2) * 230, 250 if len(lines) < 3 else 205,
            fg, html.escape(line))
        for i, line in enumerate(lines)
    )
    concept_lines = _wrap(concept, 34)
    sub_svg = "".join(
        '<text x="{}" y="{}" text-anchor="middle" font-family="sans-serif" '
        'font-size="105" letter-spacing="5" fill="{}">{}</text>'.format(
            cx, cy + 650 + i * 145, b, html.escape(line))
        for i, line in enumerate(concept_lines)
    )
    if style == "orbit":
        motif = (f'<circle cx="{cx}" cy="{cy-650}" r="520" fill="none" stroke="{a}" stroke-width="34"/>'
                 f'<ellipse cx="{cx}" cy="{cy-650}" rx="850" ry="260" fill="none" stroke="{b}" stroke-width="28" transform="rotate(-28 {cx} {cy-650})"/>'
                 f'<circle cx="{cx+610}" cy="{cy-1010}" r="75" fill="{a}"/>'
                 f'<circle cx="{cx-690}" cy="{cy-330}" r="42" fill="{b}"/>')
    elif style == "badge":
        motif = (f'<circle cx="{cx}" cy="{cy-650}" r="700" fill="none" stroke="{a}" stroke-width="38"/>'
                 f'<circle cx="{cx}" cy="{cy-650}" r="590" fill="none" stroke="{b}" stroke-width="14"/>')
    elif style == "type":
        motif = (f'<path d="M {cx-1100} {cy-1250} H {cx+1100} M {cx-1100} {cy+1150} H {cx+1100}" stroke="{a}" stroke-width="32"/>')
    elif style == "botanical":
        motif = "".join(
            f'<path d="M {cx} {cy-1000} Q {cx+v} {cy-700} {cx} {cy-350}" fill="none" stroke="{a if i%2==0 else b}" stroke-width="32"/>'
            f'<ellipse cx="{cx+v//2}" cy="{cy-820}" rx="170" ry="65" transform="rotate({i*28-50} {cx+v//2} {cy-820})" fill="{a if i%2==0 else b}"/>'
            for i, v in enumerate((-500, -250, 250, 500)))
    else:
        motif = (f'<path d="M {cx} {cy-1350} L {cx+650} {cy-650} L {cx} {cy+50} L {cx-650} {cy-650} Z" fill="none" stroke="{a}" stroke-width="34"/>'
                 f'<circle cx="{cx}" cy="{cy-650}" r="220" fill="none" stroke="{b}" stroke-width="24"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">'
           f'<g fill="none">{motif}</g>{title_svg}{sub_svg}'
           f'<text x="{cx}" y="{height-500}" text-anchor="middle" font-family="sans-serif" '
           f'font-size="65" letter-spacing="18" fill="{a}">AUREON ORIGINAL SERIES</text></svg>')
    qa = validate_svg_artwork(svg, width, height)
    return {"title": title, "concept": concept, "style": style, "palette": palette,
            "format": "image/svg+xml", "width": width, "height": height,
            "svg": svg, "qa": qa, "editable": True,
            "provenance": "Generated locally by Aureon vector studio; no third-party artwork."}


def generate_mockup_preview(artwork):
    if not isinstance(artwork, dict) or not isinstance(artwork.get("svg"), str):
        raise ValueError("artwork with SVG content is required")
    source = artwork["svg"]
    if not validate_svg_artwork(source, artwork.get("width", 4500), artwork.get("height", 5400))["passed"]:
        raise ValueError("artwork failed print validation")
    # This is an illustrative flat product mockup, not a photograph.
    escaped = html.escape(source)
    return {
        "format": "image/svg+xml",
        "kind": "illustrative_flat_mockup",
        "svg": (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1050" viewBox="0 0 900 1050">'
                '<rect width="900" height="1050" rx="48" fill="#e8e1d7"/>'
                '<path d="M210 100 L690 100 L740 930 L160 930 Z" fill="#ffffff" stroke="#c5bdb2" stroke-width="12"/>'
                '<svg x="250" y="190" width="400" height="600" viewBox="0 0 4500 5400">'
                + source.split(">", 1)[1].rsplit("</svg>", 1)[0] + '</svg></svg>'),
        "warning": "Illustrative flat mockup only; not a product photograph or supplier mockup."
    }


def create_asset(db_path, **kwargs):
    artwork = generate_vector_artwork(**kwargs)
    record = create_record(db_path, "design", artwork["title"],
                           {k: v for k, v in artwork.items() if k != "svg"} |
                           {"svg": artwork["svg"], "asset_type": "vector_artwork"},
                           "generated")
    return {"record": record, "artwork": artwork}


def list_assets(db_path, limit=50):
    return [r for r in list_records(db_path, "design", limit)
            if r["data"].get("asset_type") == "vector_artwork"]


def create_collection(db_path, title, concept, styles, palette="midnight"):
    title = _text(title, "collection title", 100)
    concept = _text(concept, "collection concept", 240)
    if not isinstance(styles, list) or not 1 <= len(styles) <= 5:
        raise ValueError("collection must contain 1-5 styles")
    if any(not isinstance(style, str) for style in styles) or len(set(styles)) != len(styles):
        raise ValueError("collection styles must be unique text values")
    if any(style.lower() not in {"orbit", "badge", "type", "botanical", "geometric"} for style in styles):
        raise ValueError("collection contains an unsupported style")
    if palette not in PALETTES:
        raise ValueError("unknown palette")
    variants = []
    for index, style in enumerate(styles, 1):
        asset = create_asset(db_path, title=title + " · " + str(index), concept=concept,
                             style=style, palette=palette)
        variants.append({"record_id": asset["record"]["id"], "title": asset["artwork"]["title"],
                         "style": style, "qa_passed": asset["artwork"]["qa"]["passed"]})
    collection = create_record(db_path, "design", title,
        {"asset_type": "creative_collection", "concept": concept, "palette": palette,
         "variants": variants, "variant_count": len(variants)}, "review")
    return {"collection": collection, "variants": variants,
            "warning": "Generated vector variations require rights, brand and provider-template review."}

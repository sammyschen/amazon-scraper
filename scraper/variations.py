"""
Amazon's variation ("twister") data, embedded as JSON in every product page that
has variations. Verified on amazon.co.uk (Sept 2026), e.g.:

    "currentAsin" : "B0CG19QXWD",
    "parentAsin" : "B0HC6NY128",
    "dimensionToAsinMap" : {"0":"B0CG19FGQ5","1":"B0CG19QXWD", ...},
    "dimensions" : ["style_name"],
    "dimensionValuesDisplayData" : {"B0CG19FGQ5":["Osmo Pocket 3 Creator Combo"], ...},
    "variationDisplayLabels" : {"style_name":"Style Name"},
"""

import json
import re

from .utils import ASIN_PATTERN


def _json_value(src, key):
    """Parse the JSON object / array / string that follows "key": in src."""
    m = re.search(r'"%s"\s*:\s*' % re.escape(key), src)
    if not m or m.end() >= len(src):
        return None
    start = m.end()
    if src[start] == '"':
        s = re.match(r'"(?:[^"\\]|\\.)*"', src[start:])
        return json.loads(s.group()) if s else None
    if src[start] not in "{[":
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(src)):
        c = src[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(src[start:i + 1])
                except ValueError:
                    return None
    return None


def _twister_script(html):
    """The <script> that holds the variation data, or None if the product has none."""
    anchor = html.find('"dimensionToAsinMap"')
    if anchor == -1:
        return None
    start, end = html.rfind("<script", 0, anchor), html.find("</script>", anchor)
    return html[start:end] if start != -1 and end != -1 else html


def page_asin(html, default=None):
    """The ASIN the page actually shows (Amazon may redirect, e.g. parent -> default child)."""
    tag = re.search(r'<input[^>]*\bid="ASIN"[^>]*>', html)
    m = tag and re.search(r'value="(%s)"' % ASIN_PATTERN, tag.group())
    m = m or re.search(r'"currentAsin"\s*:\s*"(%s)"' % ASIN_PATTERN, html)
    return m.group(1) if m else default


def get_parent_asin(html):
    """Parent ASIN of the product on this page, or None (no variations / not detectable).
    Only the variation data counts: other widgets (e.g. the video player) also carry a
    "parentAsin", which is just the product itself."""
    script = _twister_script(html)
    m = script and re.search(r'"parentAsin"\s*:\s*"(%s)"' % ASIN_PATTERN, script)
    return m.group(1) if m else None


def get_dimensions(html):
    """Display names of the variation dimensions, e.g. ['Colour', 'Size']."""
    script = _twister_script(html)
    if not script:
        return []
    dims = _json_value(script, "dimensions") or []
    labels = _json_value(script, "variationDisplayLabels") or {}
    return [labels.get(d) or d.replace("_name", "").replace("_", " ").title()
            for d in dims if isinstance(d, str)]


def get_child_asins(html):
    """Every child ASIN in the family, in Amazon's option order:
    [{"asin": "B0...", "variation": "Colour: Black; Size: M"}, ...]. [] if no variations."""
    script = _twister_script(html)
    if not script:
        return []
    combos = _json_value(script, "dimensionToAsinMap") or {}
    values = _json_value(script, "dimensionValuesDisplayData") or {}
    names = get_dimensions(html)

    def option_order(key):  # "1_8_3" -> (1, 8, 3)
        return tuple(int(x) if x.isdigit() else 0 for x in str(key).split("_"))

    asins = [a for _, a in sorted(combos.items(), key=lambda kv: option_order(kv[0]))]
    asins += list(values)
    return [{"asin": a, "variation": describe(values.get(a), names)}
            for a in dict.fromkeys(asins) if re.fullmatch(ASIN_PATTERN, a or "")]


def describe(vals, names):
    """(['Black', 'M'], ['Colour', 'Size']) -> 'Colour: Black; Size: M'"""
    vals = [v for v in (vals or []) if isinstance(v, str)]
    if names and len(names) == len(vals):
        return "; ".join(f"{n}: {v}" for n, v in zip(names, vals) if v)
    return "; ".join(v for v in vals if v)


def variation_of(html, asin):
    """Variation description of one ASIN on this page ('' if it has none)."""
    script = _twister_script(html)
    if not script:
        return ""
    values = _json_value(script, "dimensionValuesDisplayData") or {}
    return describe(values.get(asin), get_dimensions(html))

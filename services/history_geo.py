"""Format Histoire : cartes à partir de vraie géographie (Natural Earth, domaine public).

build_map(places) cadre la région qui contient les lieux, projette les côtes et les fleuves dans le
repère vidéo 1920x1080 et renvoie des tracés SVG prêts pour le template Remotion « map ».
Données (~17 Mo) téléchargées une fois dans data/geo/.
"""
import json
import math
import os
import urllib.request

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(APP_DIR, "data", "geo")
SRC = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
FILES = {"land": "ne_10m_land.geojson", "rivers": "ne_10m_rivers_lake_centerlines.geojson"}
W, H = 1920, 1080
_cache = {}


def _load(kind):
    if kind in _cache:
        return _cache[kind]
    path = os.path.join(os.getenv("HISTORY_GEO_DIR") or GEO_DIR, FILES[kind])
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(SRC + FILES[kind], path + ".part")
        os.replace(path + ".part", path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lines = []  # (bbox, [(lon, lat), ...]) ; anneaux de polygones ou lignes
    for feat in data.get("features") or []:
        g = feat.get("geometry") or {}
        t, coords = g.get("type"), g.get("coordinates") or []
        if t == "Polygon":
            parts = coords
        elif t == "MultiPolygon":
            parts = [ring for poly in coords for ring in poly]
        elif t == "LineString":
            parts = [coords]
        elif t == "MultiLineString":
            parts = coords
        else:
            continue
        for ring in parts:
            if len(ring) < 2:
                continue
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            lines.append(((min(xs), min(ys), max(xs), max(ys)), ring))
    _cache[kind] = lines
    return lines


def _view(places, pad=0.38, min_span=1.2):
    """Cadre 16:9 autour des lieux : (lon0, lat0, k) avec x = (lon-lon0)*cos(lat0)*k + W/2."""
    lons = [p["lon"] for p in places]
    lats = [p["lat"] for p in places]
    lon0, lat0 = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
    cos0 = max(0.2, math.cos(math.radians(lat0)))
    span_x = max((max(lons) - min(lons)) * cos0, min_span) * (1 + 2 * pad)
    span_y = max(max(lats) - min(lats), min_span * 0.6) * (1 + 2 * pad)
    k = min(W / span_x, (H * 0.86) / span_y)
    return lon0, lat0, cos0, k


def _proj(v, lon, lat):
    lon0, lat0, cos0, k = v
    return ((lon - lon0) * cos0 * k + W / 2, -(lat - lat0) * k + H * 0.54)


def _clip(poly, xmin, ymin, xmax, ymax):
    """Sutherland–Hodgman : polygone découpé au rectangle (garde des tracés légers)."""
    def cut(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i - 1], pts[i]
            ia, ib = inside(a), inside(b)
            if ib:
                if not ia:
                    out.append(inter(a, b))
                out.append(b)
            elif ia:
                out.append(inter(a, b))
        return out

    def ix(x0):
        return lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / ((b[0] - a[0]) or 1e-9))

    def iy(y0):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / ((b[1] - a[1]) or 1e-9), y0)

    pts = poly
    for inside, inter in ((lambda p: p[0] >= xmin, ix(xmin)), (lambda p: p[0] <= xmax, ix(xmax)),
                          (lambda p: p[1] >= ymin, iy(ymin)), (lambda p: p[1] <= ymax, iy(ymax))):
        if not pts:
            break
        pts = cut(pts, inside, inter)
    return pts


def _rdp(pts, eps):
    """Douglas–Peucker itératif (simplification des côtes, en pixels)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy)
        best, idx = 0.0, -1
        for i in range(a + 1, b):
            # anneau fermé (a == b) : distance au point lui-même, sinon distance à la corde
            d = (abs(dy * (pts[i][0] - ax) - dx * (pts[i][1] - ay)) / n) if n > 1e-6 else math.hypot(pts[i][0] - ax, pts[i][1] - ay)
            if d > best:
                best, idx = d, i
        if best > eps and idx > 0:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]


def _path(pts, close):
    return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts) + (" Z" if close else "")


def build_map(places):
    """places = [{name, lat, lon}] → {land, rivers, xy: {name: [x, y]}}."""
    v = _view(places)
    lon0, lat0, cos0, k = v
    margin = 60
    # cadre géographique (avec marge) pour filtrer vite les anneaux
    half_w = (W / 2 + margin) / (cos0 * k)
    half_h = (H / 2 + margin) / k
    gx0, gx1 = lon0 - half_w, lon0 + half_w
    gy0, gy1 = lat0 - half_h * 1.1, lat0 + half_h * 1.1
    land = []
    for (bx0, by0, bx1, by1), ring in _load("land"):
        if bx1 < gx0 or bx0 > gx1 or by1 < gy0 or by0 > gy1:
            continue
        pts = [_proj(v, lon, lat) for lon, lat in ring]
        pts = _clip(pts, -margin, -margin, W + margin, H + margin)
        pts = _rdp(pts, 0.9)
        if len(pts) >= 3:
            land.append(_path(pts, True))
    rivers = []
    for (bx0, by0, bx1, by1), line in _load("rivers"):
        if bx1 < gx0 or bx0 > gx1 or by1 < gy0 or by0 > gy1:
            continue
        run = []
        for lon, lat in line + [(None, None)]:
            p = _proj(v, lon, lat) if lon is not None else None
            if p and -margin <= p[0] <= W + margin and -margin <= p[1] <= H + margin:
                run.append(p)
                continue
            if len(run) >= 2:
                rivers.append(_path(_rdp(run, 0.9), False))
            run = []
    xy = {p["name"]: [round(c, 1) for c in _proj(v, p["lon"], p["lat"])] for p in places}
    return {"land": land, "rivers": rivers[:120], "xy": xy}

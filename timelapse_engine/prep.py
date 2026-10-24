"""Prépare la scène 3D d'une ville : bâtiments (avec année d'apparition), routes, parcs, eau, arbres.

    python timelapse_engine/prep.py timelapse_engine/cities/tel_aviv.json work/timelapse/tel_aviv

Lit les .parquet de fetch.py, écrit scene.json (mètres : x vers l'est, z vers le sud).
Années : vraie année pour les tours de la liste `towers`, sinon date approximative du quartier
(`zones`, fondation documentée) ou de la distance au noyau d'origine (`fallback`).
"""
import json
import math
import os
import random
import sys

import duckdb
from shapely import wkt as swkt
from shapely.geometry import MultiPolygon, Polygon, LineString, MultiLineString, Point

R_EARTH = 6371000.0
ROAD_W = {"motorway": 16, "trunk": 13, "primary": 11, "secondary": 9, "tertiary": 7,
          "residential": 5, "living_street": 4.5, "unclassified": 5, "pedestrian": 4}
PARK = {"park", "grass", "garden", "meadow", "village_green", "recreation_ground", "pitch",
        "golf_course", "cemetery", "dog_park", "playground"}


def main(cfg_path, folder):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    lon0, lat0 = cfg["center"]
    kx = math.cos(math.radians(lat0)) * math.pi / 180 * R_EARTH
    ky = math.pi / 180 * R_EARTH
    rnd = random.Random(7)

    def xy(lon, lat):
        return (round((lon - lon0) * kx, 1), round(-(lat - lat0) * ky, 1))

    zones = [dict(z, x=xy(z["lon"], z["lat"])[0], z=xy(z["lon"], z["lat"])[1]) for z in cfg["zones"]]
    fb = cfg["fallback"]
    core = xy(fb["core_lon"], fb["core_lat"])

    def zone_year(x, z):
        for zn in zones:
            d = math.hypot(x - zn["x"], z - zn["z"])
            if d < zn["r"]:
                f = d / zn["r"]  # le centre du quartier d'abord, les bords ensuite
                return zn["from"] + (zn["to"] - zn["from"]) * min(1, f * 0.8 + rnd.random() * 0.35)
        d = math.hypot(x - core[0], z - core[1]) / 1000
        return min(fb["max"], fb["base"] + d * fb["per_km"] + rnd.uniform(-4, 6))

    # satellite (GHSL, surface bâtie par case de 90 m, 1975-2020) : date réelle d'urbanisation après 1975
    ghsl = None
    if cfg.get("ghsl"):
        import numpy as np
        z_ = np.load(cfg["ghsl"])
        glon, glat, gpx = z_["meta"]
        epochs = sorted(int(k) for k in z_.files if k.isdigit())
        stack = np.stack([z_[str(e)] for e in epochs])
        first = np.where((stack > 900).any(0), (stack > 900).argmax(0), -1)
        ghsl = (first, glon, glat, gpx, epochs)

    def sat_year(lon, lat):
        if ghsl is None:
            return None
        first, glon, glat, gpx, epochs = ghsl
        r, c = int((glat - lat) / gpx), int((lon - glon) / gpx)
        if not (0 <= r < first.shape[0] and 0 <= c < first.shape[1]):
            return None
        k = int(first[r, c])
        if k < 0:
            return 2022 + rnd.uniform(0, 3)
        return None if k == 0 else rnd.uniform(epochs[k - 1], epochs[k])  # k == 0 : déjà bâti en 1975

    con = duckdb.connect()
    q = lambda name, sql: con.execute(sql.replace("T", f"'{os.path.join(folder, name)}.parquet'")).fetchall()

    towers = cfg.get("towers", [])
    bld, tall = [], []
    for bid, h, nf, cls, name, g in q("buildings", "select id,height,num_floors,class,name,wkt from T"):
        if name and any(x in name for x in cfg.get("exclude_names", [])):
            continue
        geom = swkt.loads(g)
        polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for p in polys:
            ring = [xy(lon, lat) for lon, lat in p.exterior.coords[:-1]]
            ring = _simplify(ring, 0.7)
            if len(ring) < 3 or Polygon(ring).area < 12:
                continue
            cx = sum(a for a, _ in ring) / len(ring)
            cz = sum(b for _, b in ring) / len(ring)
            height = h or (nf * 3.3 + 1.5 if nf else None)
            label, year = None, None
            for t in towers:
                if (name and t.get("match") and t["match"] in name) or (t.get("match_h") and h and abs(h - t["match_h"]) < 0.5):
                    label, year = t["label"], t["year"]
                    break
            if height is None:
                area = Polygon(ring).area
                height = rnd.choice([7, 10, 10, 13, 13, 16]) if area > 60 else rnd.choice([4, 7])
            if year is None:
                c = p.centroid
                sy = sat_year(c.x, c.y)
                year = sy if sy is not None else min(zone_year(cx, cz), 1975)
                if height >= 45:  # tours sans date connue : la plupart après 1990, plus haut = plus récent
                    year = max(year, min(2024, 1968 + (height - 45) * 0.45 + rnd.uniform(0, 22)))
                elif height >= 22:  # immeubles de 7 à 13 étages : reconstruits après 1955
                    year = max(year, rnd.uniform(1956, 2018))
            kind = 2 if height >= 60 else (1 if height >= 22 else 0)
            bld.append([round(year, 2), round(height, 1), kind, rnd.randrange(6), ring])
            if label:
                tall.append({"label": label, "year": year, "x": cx, "z": cz, "h": height})

    # grille des années des bâtiments pour dater routes, parcs et arbres
    G = 60
    grid = {}
    for b in bld:
        r = b[4]
        k = (int(r[0][0] // G), int(r[0][1] // G))
        grid[k] = min(grid.get(k, 9999), b[0])

    def near_year(x, z):
        best = 9999
        kx0, kz0 = int(x // G), int(z // G)
        for i in range(-1, 2):
            for j in range(-1, 2):
                best = min(best, grid.get((kx0 + i, kz0 + j), 9999))
        return best if best < 9999 else zone_year(x, z)

    roads = []
    for cls, g in q("roads", "select class,wkt from T"):
        if cls not in ROAD_W or not g:
            continue
        geom = swkt.loads(g)
        lines = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        for ln in lines:
            if not isinstance(ln, LineString) or ln.length == 0:
                continue
            pts = _simplify([xy(lon, lat) for lon, lat in ln.coords], 0.8)
            if len(pts) < 2:
                continue
            mx, mz = pts[len(pts) // 2]
            roads.append([round(near_year(mx, mz) - 0.5, 2), ROAD_W[cls], pts])

    def polys_of(g):
        geom = swkt.loads(g)
        if isinstance(geom, Polygon):
            return [geom]
        if hasattr(geom, "geoms"):
            return [p for p in geom.geoms if isinstance(p, Polygon)]
        return []

    parks, water, beach, trees = [], [], [], []
    for sub, cls, g in q("landuse", "select subtype,class,wkt from T"):
        if cls in PARK and g:
            for p in polys_of(g):
                ring = _simplify([xy(a, b) for a, b in p.exterior.coords[:-1]], 1.0)
                if len(ring) >= 3 and Polygon(ring).area > 0:
                    c = Polygon(ring).centroid
                    yr = round(near_year(c.x, c.y), 2)
                    parks.append([yr, ring])
                    area = Polygon(ring).area
                    pol = Polygon(ring)
                    minx, miny, maxx, maxy = pol.bounds
                    for _ in range(min(400, int(area / 220))):
                        tx, tz = rnd.uniform(minx, maxx), rnd.uniform(miny, maxy)
                        if pol.contains(Point(tx, tz)):
                            trees.append([round(yr + rnd.uniform(0, 3), 2), round(tx, 1), round(tz, 1), round(rnd.uniform(0.8, 1.4), 2)])
    sea_tris = []
    for sub, cls, g in q("water", "select subtype,class,wkt from T"):
        if cls in ("swimming_pool", "drain", "ditch") or not g:
            continue
        if cls in ("sea", "ocean"):
            if cls == "sea":
                import shapely
                from shapely.ops import transform
                for p in polys_of(g):
                    pp = transform(lambda a, b, z=None: xy(a, b), p).simplify(2.0).buffer(0)
                    for t in shapely.constrained_delaunay_triangles(pp).geoms:
                        sea_tris.append([list(c) for c in t.exterior.coords[:3]])
            continue
        for p in polys_of(g):
            ring = _simplify([xy(a, b) for a, b in p.exterior.coords[:-1]], 1.5)
            # petites surfaces « water » = piscines, bassins : elles apparaîtraient en 1909
            if len(ring) >= 3 and (cls in ("river", "stream", "canal") or Polygon(ring).area > 5000):
                water.append([cls, ring])
    for sub, cls, g in q("land", "select subtype,class,wkt from T"):
        if not g:
            continue
        geom = swkt.loads(g)
        if cls in ("beach", "sand"):
            for p in polys_of(g):
                ring = _simplify([xy(a, b) for a, b in p.exterior.coords[:-1]], 1.5)
                if len(ring) >= 3:
                    beach.append(ring)
        elif cls == "tree" and isinstance(geom, Point):
            x, z = xy(geom.x, geom.y)
            trees.append([round(near_year(x, z) + rnd.uniform(0, 4), 2), x, z, round(rnd.uniform(0.8, 1.3), 2)])
    # arbres d'alignement le long des boulevards (Rothschild, etc.)
    for r in roads:
        if r[1] >= 9:
            pts = r[2]
            for (x1, z1), (x2, z2) in zip(pts, pts[1:]):
                L = math.hypot(x2 - x1, z2 - z1)
                for k in range(int(L // 14)):
                    f = (k + 0.5) * 14 / L
                    nx, nz = -(z2 - z1) / L, (x2 - x1) / L
                    side = r[1] / 2 + 2.5
                    for sgn in (-1, 1):
                        trees.append([round(r[0] + 1 + rnd.uniform(0, 3), 2), round(x1 + (x2 - x1) * f + nx * side * sgn, 1),
                                      round(z1 + (z2 - z1) * f + nz * side * sgn, 1), round(rnd.uniform(0.7, 1.0), 2)])

    w, s, e, n = cfg["bbox"]
    out = {"bounds": [xy(w, n), xy(e, s)], "buildings": bld, "roads": roads, "parks": parks,
           "water": water, "sea_tris": sea_tris, "beach": beach, "trees": trees, "towers": tall,
           "labels": [dict(l, x=xy(l["lon"], l["lat"])[0], z=xy(l["lon"], l["lat"])[1]) for l in cfg.get("labels", [])]}
    json.dump(out, open(os.path.join(folder, "scene.json"), "w"), separators=(",", ":"))
    print(f"bâtiments {len(bld)}  routes {len(roads)}  parcs {len(parks)}  eau {len(water)}  arbres {len(trees)}  tours {len(tall)}")


def _simplify(pts, tol):
    """Retire les points presque alignés (Douglas-Peucker léger via shapely)."""
    if len(pts) < 3:
        return pts
    ls = LineString(pts).simplify(tol)
    return [(round(a, 1), round(b, 1)) for a, b in ls.coords]


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

"""Monaco's data.js: like osm_data.py, plus the real relief and the land won from the sea.

    python citylapse/tools/osm_data_monaco.py timelapse_engine/cities/monaco.json work/timelapse/monaco citylapse/cities/monaco

Differences from osm_data.py (Tel Aviv):
  - the coast comes from Overture's `land` polygons (the sea is everything else in the box, plus the open sea south
    and east of it), not from water polygons;
  - E  terrain height grid (decimetres, int16, GRID metres per cell) from the Copernicus GLO-30 surface model
       (dem_crop.npz), with the buildings eroded away (a 5x5 minimum filter) and smoothed;
  - RC the reclaimed areas: [{name, from, to, ring}] in world metres (Fontvieille, Larvotto, Mareterra), clipped to
       today's land. Before `from` they are sea; the scene raises them out of the water between `from` and `to`.
"""
import base64
import json
import math
import os
import sys

import duckdb
import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
GRID = 10.0


def main(cfg_path, src, dst):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    lon0, lat0 = cfg["center"]
    kx = math.cos(math.radians(lat0)) * math.pi / 180 * 6371000.0
    ky = math.pi / 180 * 6371000.0
    to_xy = lambda a: np.column_stack([(a[:, 0] - lon0) * kx, -(a[:, 1] - lat0) * ky])
    sc = json.load(open(os.path.join(src, "scene.json")))
    (bx0, bz0), (bx1, bz1) = sc["bounds"]
    EXT = (bx0, bz0, bx1, bz1)

    # buildings, footprints, roads, trees: exactly as osm_data.py
    B, BR = [], []
    for year, h, kind, ci, ring in sc["buildings"]:
        p = Polygon(ring)
        if not p.is_valid:
            p = p.buffer(0)
        r = p.minimum_rotated_rectangle
        c = list(r.exterior.coords)[:4]
        e1 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e2 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
        w, d = math.hypot(*e1), math.hypot(*e2)
        if w < 2 or d < 2:
            continue
        k = math.sqrt(min(1.0, p.area / (w * d)))
        ang = -math.atan2(e1[1], e1[0])
        cx, cz = r.centroid.x, r.centroid.y
        B += [round(cx * 10), round(cz * 10), round(w * k * 10), round(d * k * 10), round(ang * 1000), round(h * 10), round(year * 100), kind, ci]
        q = shapely.geometry.polygon.orient(p if p.geom_type == "Polygon" else max(p.geoms, key=lambda g: g.area), 1.0)
        ring = list(q.exterior.coords)[:-1]
        BR.append(len(ring))
        for px, pz in ring:
            BR += [round((px - cx) * 10), round((pz - cz) * 10)]
    R = []
    for year, w, pts in sc["roads"]:
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            R += [round(ax, 1), round(az, 1), round(bx, 1), round(bz, 1), w, round(year, 1)]
    T = []
    for year, x, z, s in sc["trees"]:
        T += [round(year, 1), x, z, s]

    # land = Overture's `land` polygons; the sea = the rest of the box
    con = duckdb.connect()
    lands = []
    for cls, g in con.execute(f"select class, wkt from '{os.path.join(src, 'land.parquet')}'").fetchall():
        if g and cls == "land":
            lands.append(shapely.transform(shapely.from_wkt(g), to_xy).buffer(0))
    land = unary_union(lands).simplify(1.0)
    box = shapely.box(EXT[0] - 50, EXT[1] - 50, EXT[2] + 50, EXT[3] + 50)
    water = box.difference(land)
    nx, nz = int((EXT[2] - EXT[0]) / GRID), int((EXT[3] - EXT[1]) / GRID)
    xs = EXT[0] + (np.arange(nx) + 0.5) * GRID
    zs = EXT[1] + (np.arange(nz) + 0.5) * GRID
    X, Z = np.meshgrid(xs, zs)
    pts = shapely.points(X.ravel(), Z.ravel())
    shapely.prepare(water)
    inside = shapely.contains(water, pts)
    dist = shapely.distance(water.boundary, pts)
    sd = np.where(inside, -dist, dist).reshape(nz, nx)
    sd = np.clip(np.round(sd / 1.0), -120, 120).astype(np.int8)
    S = base64.b64encode(sd.tobytes()).decode()

    # relief: Copernicus DSM, buildings eroded, sampled on the same grid
    dm = np.load(os.path.join(src, "dem_crop.npz"))
    D = dm["z"].astype(np.float32)
    pad = np.pad(D, 2, mode="edge")
    ero = np.min(np.stack([pad[i:i + D.shape[0], j:j + D.shape[1]] for i in range(5) for j in range(5)]), axis=0)
    pad = np.pad(ero, 1, mode="edge")
    sm = np.mean(np.stack([pad[i:i + D.shape[0], j:j + D.shape[1]] for i in range(3) for j in range(3)]), axis=0)
    LON = lon0 + X / kx
    LAT = lat0 - Z / ky
    r = (float(dm["lat0"]) - LAT) / float(dm["dlat"]) - 0.5
    c = (LON - float(dm["lon0"])) / float(dm["dlon"]) - 0.5
    r0 = np.clip(np.floor(r).astype(int), 0, D.shape[0] - 2); c0 = np.clip(np.floor(c).astype(int), 0, D.shape[1] - 2)
    fr = np.clip(r - r0, 0, 1); fc = np.clip(c - c0, 0, 1)
    Hg = (sm[r0, c0] * (1 - fr) * (1 - fc) + sm[r0 + 1, c0] * fr * (1 - fc) + sm[r0, c0 + 1] * (1 - fr) * fc + sm[r0 + 1, c0 + 1] * fr * fc)
    Hg = np.where(sd.reshape(nz, nx) > 0, np.maximum(Hg, 1.0), 0.0)
    E = base64.b64encode(np.round(Hg * 10).astype(np.int16).tobytes()).decode()

    # reclaimed land, clipped to today's land
    RC = []
    for rc in cfg.get("reclaim", []):
        poly = Polygon([((lon - lon0) * kx, -(lat - lat0) * ky) for lat, lon in rc["poly"]])
        part = poly.intersection(land)
        geoms = [g for g in getattr(part, "geoms", [part]) if g.geom_type == "Polygon" and g.area > 400]
        for g in geoms:
            g = g.simplify(1.5)
            RC.append({"name": rc["name"], "from": rc["from"], "to": rc["to"], "ring": [[round(x, 1), round(z, 1)] for x, z in list(g.exterior.coords)[:-1]]})

    from PIL import Image, ImageDraw
    PX0, PZ0, PEXT, PN = EXT[0], EXT[1], max(EXT[2] - EXT[0], EXT[3] - EXT[1]), 1024
    img = Image.new("I", (PN, PN), 0); dr = ImageDraw.Draw(img)
    for year, ring in sorted(sc["parks"], key=lambda r: -r[0]):
        pp = [((x - PX0) / PEXT * PN, (z - PZ0) / PEXT * PN) for x, z in ring]
        if len(pp) >= 3:
            dr.polygon(pp, fill=int(max(1, min(65535, round((year - 1800) * 100)))))
    pk = np.array(img, dtype=np.uint32).astype(np.uint16)
    P = base64.b64encode(pk.tobytes()).decode()
    out = {"B": B, "BR": BR, "R": R, "T": T, "towers": sc.get("towers", []), "labels": sc.get("labels", []), "RC": RC,
           "center": [lon0, lat0], "k": [kx, ky],
           "P": {"x0": PX0, "z0": PZ0, "ext": PEXT, "n": PN, "b64": P},
           "S": {"x0": EXT[0], "z0": EXT[1], "nx": nx, "nz": nz, "g": GRID, "b64": S, "e64": E}}
    os.makedirs(dst, exist_ok=True)
    with open(os.path.join(dst, "data.js"), "w") as f:
        f.write("// generated by tools/osm_data_monaco.py from OpenStreetMap / Overture Maps data (ODbL) and Copernicus GLO-30; do not edit\n")
        f.write("export const DATA = " + json.dumps(out, separators=(",", ":")) + ";\n")
    print(f"buildings {len(B) // 9}  road segments {len(R) // 6}  trees {len(T) // 4}  grid {nx}x{nz}  reclaimed {len(RC)}  "
          f"relief max {Hg.max():.0f} m  {os.path.getsize(os.path.join(dst, 'data.js')) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])

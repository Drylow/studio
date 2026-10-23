"""Télécharge les données réelles d'une ville (Overture Maps, dérivé d'OpenStreetMap) dans un dossier.

    python timelapse_engine/fetch.py timelapse_engine/cities/tel_aviv.json work/timelapse/tel_aviv

Sorties : buildings.parquet, water.parquet, landuse.parquet, land.parquet, roads.parquet.
Accès S3 public anonyme ; passe par le proxy de la session cloud s'il existe.
"""
import json
import os
import sys
import urllib.parse

import duckdb

RELEASE = "2026-10-21.0"
ROOT = f"s3://overturemaps-us-west-2/release/{RELEASE}"


def main(cfg_path, out):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    w, s, e, n = cfg["bbox"]
    os.makedirs(out, exist_ok=True)
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        os.environ.pop(k, None)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    if os.environ.get("HTTPS_PROXY"):
        p = urllib.parse.urlparse(os.environ["HTTPS_PROXY"])
        con.execute(f"SET http_proxy='{p.hostname}:{p.port}'")
    con.execute("CREATE SECRET ov (TYPE s3, KEY_ID '', SECRET '', REGION 'us-west-2')")
    env = f"ST_MakeEnvelope({w},{s},{e},{n})"
    inside = f"bbox.xmin > {w} AND bbox.xmax < {e} AND bbox.ymin > {s} AND bbox.ymax < {n}"
    touch = f"bbox.xmin < {e} AND bbox.xmax > {w} AND bbox.ymin < {n} AND bbox.ymax > {s}"
    jobs = [
        ("buildings", "theme=buildings/type=building",
         "id, height, num_floors, class, names.primary AS name, ST_AsText(geometry) AS wkt", inside),
        ("water", "theme=base/type=water", f"subtype, class, ST_AsText(ST_Intersection(geometry, {env})) wkt", touch),
        ("landuse", "theme=base/type=land_use", f"subtype, class, ST_AsText(ST_Intersection(geometry, {env})) wkt", touch),
        ("land", "theme=base/type=land", f"subtype, class, ST_AsText(ST_Intersection(geometry, {env})) wkt", touch),
        ("roads", "theme=transportation/type=segment",
         f"class, ST_AsText(ST_Intersection(geometry, {env})) wkt", touch + " AND subtype='road'"),
    ]
    for name, path, cols, where in jobs:
        dest = os.path.join(out, name + ".parquet")
        if os.path.exists(dest):
            continue
        con.execute(f"COPY (SELECT {cols} FROM read_parquet('{ROOT}/{path}/*', hive_partitioning=1) "
                    f"WHERE {where}) TO '{dest}' (FORMAT parquet)")
        print(name, con.execute(f"select count(*) from '{dest}'").fetchone()[0])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

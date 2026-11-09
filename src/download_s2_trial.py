"""Download only AOI windows of two public Sentinel-2 L2A COG products.

Run with QGIS's python-qgis-ltr.bat; no credentials or new packages required.
Outputs are unscaled source DN and numeric SCL, not analytical indices.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from osgeo import gdal, osr


def main():
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    gdal.SetConfigOption("GDAL_HTTP_TIMEOUT", "60")
    gdal.SetConfigOption("GDAL_HTTP_MAX_RETRY", "2")
    root = Path(__file__).resolve().parents[1]
    aoi = root / "data/reference/venkatapur_initial_study_area_5km.geojson"
    ring = json.loads(aoi.read_text())["features"][0]["geometry"]["coordinates"][0]
    source, target = osr.SpatialReference(), osr.SpatialReference()
    source.ImportFromEPSG(4326)
    target.ImportFromEPSG(32644)
    for crs in (source, target):
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    points = [transform.TransformPoint(*point) for point in ring]
    bounds = [math.floor(min(p[0] for p in points)/20)*20,
              math.floor(min(p[1] for p in points)/20)*20,
              math.ceil(max(p[0] for p in points)/20)*20,
              math.ceil(max(p[1] for p in points)/20)*20]
    output = root / "data/raw/sentinel/s2/trial_2025"
    output.mkdir(parents=True, exist_ok=True)
    report = {"downloaded_utc": datetime.now(timezone.utc).isoformat(),
              "aoi_sha256": hashlib.sha256(aoi.read_bytes()).hexdigest(),
              "crs": "EPSG:32644", "resolution_m": 20, "bounds": bounds,
              "note": "Rectangular subset covering the full planning circle; not a village boundary. Source DN retained; apply asset scale/offset before indices. Two dates are not seasonal composites.",
              "products": []}
    for date, item_id in [
        ("2025-05-12", "S2C_T44QKF_20250512T051730_L2A"),
        ("2025-12-28", "S2C_T44QKF_20251228T051231_L2A"),
    ]:
        url = "https://earth-search.aws.element84.com/v1/collections/sentinel-2-c1-l2a/items/" + item_id
        with urlopen(url, timeout=45) as response:
            item = json.load(response)
        folder = output / date
        folder.mkdir(exist_ok=True)
        (folder / "source_stac.json").write_text(json.dumps(item, indent=2), encoding="utf-8")
        product = {"item_id": item_id, "item_url": url,
                   "source_product": item["properties"].get("s2:product_uri"), "files": []}
        for band, key in [("B03", "green"), ("B04", "red"), ("B08", "nir"), ("B11", "swir16"), ("SCL", "scl")]:
            asset = item["assets"][key]
            path = folder / (band + ".tif")
            if path.exists():
                raise FileExistsError(f"Refusing to overwrite {path}")
            print(f"Downloading AOI window: {date} {band}", flush=True)
            ds = gdal.Warp(str(path), "/vsicurl/" + asset["href"],
                           format="GTiff", dstSRS="EPSG:32644", outputBounds=bounds,
                           xRes=20, yRes=20, targetAlignedPixels=True,
                           resampleAlg="near" if band == "SCL" else "average",
                           dstNodata=0, creationOptions=["COMPRESS=DEFLATE", "TILED=YES"])
            ds = None
            ds = gdal.Open(str(path))
            array = ds.ReadAsArray()
            assert ds.RasterCount == 1 and ds.GetGeoTransform()[1] == 20
            valid = array != 0
            record = {"band": band, "path": str(path.relative_to(root)),
                      "source_url": asset["href"], "raster_bands": asset.get("raster:bands"),
                      "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "shape": list(array.shape), "nonzero_fraction_rectangle": float(valid.mean())}
            if band == "SCL":
                classes, counts = np.unique(array, return_counts=True)
                record["class_counts_rectangle"] = {str(int(c)): int(n) for c, n in zip(classes, counts)}
                assert set(classes.tolist()).issubset(set(range(12)))
            ds = None
            product["files"].append(record)
            print(f"Verified {path.name}: {record['shape']}, {record['bytes']} bytes", flush=True)
        report["products"].append(product)
        (output / "download_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Completed. Manifest: " + str(output / "download_manifest.json"), flush=True)


if __name__ == "__main__":
    main()

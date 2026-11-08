# Venkatapur Groundwater Potential Pilot

**Pilot area:** Venkatapur, Korutla Mandal, Jagtial District, Telangana 505330, India  
**Goal:** produce a transparent groundwater-potential and borewell-risk map for screening candidate locations. It is a decision-support tool, not a guarantee that a borewell will yield water.

## Scientific scope

The model will combine:

- local borewell outcomes (depth, water level, yield, success/failure);
- Sentinel-1 and Sentinel-2 surface indicators;
- terrain, drainage, rainfall, geology, and lineament information; and
- field verification, including a hydrogeologist / electrical-resistivity survey before drilling.

Satellite data cannot directly observe groundwater at one borewell point. The pilot must therefore be trained and checked against local field data.

## Project workflow

1. Collect at least 100 local borewell records with the template in `data/raw/`.
2. Draw the study boundary and inspect source layers in QGIS.
3. Create terrain, drainage, Sentinel, rainfall, geology, and nearby-well features.
4. Train a transparent baseline model (Random Forest).
5. Validate with held-out spatial locations and field checks.
6. Publish a simple map/dashboard only after validation.

## Coordinate standard

- Field collection: WGS 84 latitude/longitude (EPSG:4326)
- Analysis grid for Venkatapur: UTM zone 44N (EPSG:32644)

## Folder guide

- `data/raw/` — original survey and source data; do not overwrite
- `data/interim/` — cleaned intermediate data
- `data/processed/` — analysis-ready features and model outputs
- `qgis/` — QGIS project and layer styles
- `src/` — Python processing and modelling code
- `docs/` — field instructions and project notes

## First milestone

Create a verified dataset of 100+ borewells. Each row needs a coordinate and a meaningful outcome (yield, water level, or clear success/failure). Without this ground truth, a machine-learning model cannot make a reliable local prediction.

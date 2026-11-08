# Satellite Groundwater-Potential Screening — Venkatapur Pilot

**Pilot area:** Venkatapur, Korutla Mandal, Jagtial District, Telangana 505330, India.

**Goal:** build a satellite-only relative groundwater-potential screening workflow using transparent weighted overlay / multi-criteria decision analysis (MCDA).

Satellites cannot directly detect groundwater, guarantee water, predict borewell yield or predict drilling depth. Scores describe relative screening potential within the study area, not probabilities of drilling success.

## Current workflow

Follow [the public satellite data plan](docs/04_public_satellite_data_plan.md) for sources, periods, indicators, processing, weights and quality checks.

1. Confirm the village boundary and buffered processing area.
2. Inventory Sentinel-1, Sentinel-2, DEM-derived terrain/drainage and satellite rainfall.
3. Create seasonal surface indicators on a common 30 m grid.
4. Combine documented scores and weights using MCDA; report coverage and sensitivity.
5. Prioritize further investigation. Consult a hydrogeologist and undertake appropriate field/geophysical checks before drilling decisions.

No verified borewell labels are available. Do not use supervised machine learning or report predictive accuracy. The older field-survey document and script list in `src/README.md` describe earlier planning, not instructions or prerequisites for this phase. Future verified observations may support independent assessment; they are not current model inputs.

## Coordinate standard

- Boundary exchange: WGS 84 longitude/latitude (EPSG:4326).
- Analysis: UTM zone 44N (EPSG:32644), aligned 30 m cells.

## Folder guide

- `data/raw/`: original inputs, stored outside Git as specified in the plan.
- `data/interim/`: local source copies and intermediate processing, ignored by Git.
- `data/processed/`: screening rasters and quality outputs, ignored by Git.
- `qgis/`: QGIS project and styles.
- `src/`: future reproducible processing and MCDA code.
- `docs/`: methodology and provenance.

The current milestone is a reviewable data and processing plan. Do not download large datasets or configure API credentials yet. Keep raw satellite data, generated rasters, secrets and credentials out of Git.

# Satellite Groundwater-Potential Screening — Venkatapur Pilot

**Pilot area:** Venkatapur, Korutla Mandal, Jagtial District, Telangana 505330, India.

**Goal:** build a satellite-only relative groundwater-potential screening workflow using transparent weighted overlay / multi-criteria decision analysis (MCDA).

Satellites cannot directly detect groundwater, guarantee water, predict borewell yield or predict drilling depth. Scores describe relative screening potential within the study area, not probabilities of drilling success.

## Current workflow

The current milestone is a reproducible **exploratory evidence-review pilot**, using a user-confirmed centre and a 5 km planning buffer, not a verified village boundary. See the [scenario review](docs/06_scenario_review.md) for findings, assumptions and remaining gaps.

Completed locally:

- Sampled Sentinel-2 optical and Sentinel-1 radar seasonal indicators for **2023–2025**, a subset of the planned 2021–2025 baseline.
- Copernicus GLO-30 terrain, TWI and drainage diagnostics, with upstream uncertainty exclusions.
- Complete **May 2025** IMERG uncalibrated rainfall for two native grid cells; regional context only, not a seasonal baseline or village average.
- Correlation, vegetation-confounding, temporal-consistency and water-mask reviews, plus drainage and hypothetical terrain-weight/normalization sensitivity checks.
- A QGIS evidence project with **49 map/table layers**, a three-page report and a verified eleven-step offline review rebuild.

The ten terrain-only scenarios are hypothetical setting scores. No final terrain-plus-surface weights, validated groundwater classes or borewell predictions have been selected. Village-boundary verification, wider rainfall coverage and independent crop/irrigation and hydrogeological assessment remain outstanding.

Follow [the public satellite data plan](docs/04_public_satellite_data_plan.md) for sources, periods, indicators, processing, weights and quality checks.

1. Confirm the village boundary and buffered processing area.
2. Inventory Sentinel-1, Sentinel-2, DEM-derived terrain/drainage and satellite rainfall.
3. Create seasonal surface indicators on a common 30 m grid.
4. Compare separate terrain and surface-evidence scenarios; document directions, redundancy and sensitivity before selecting any final combined MCDA weights.
5. Prioritize further investigation. Consult a hydrogeologist and undertake appropriate field/geophysical checks before drilling decisions.

No verified borewell labels are available. Do not use supervised machine learning or report predictive accuracy. The field-survey document and any older supervised-ML planning are optional future validation, not prerequisites for this phase. Future verified observations may support independent assessment; they are not current model inputs. See [src/README.md](src/README.md) for implemented scripts and their environments.

## Open the local review

- QGIS: `data/processed/integrated_evidence_review/venkatapur_evidence_review.qgz`.
- Report: `data/processed/integrated_evidence_review/venkatapur_analysis_review.pdf`.
- Run record: `data/processed/integrated_evidence_review/offline_review_run.json`.

These generated outputs are Git-ignored and are not included in a GitHub clone. The QGIS project requires the sibling processed-data folders; it is not a standalone portable file.

For sharing a local demonstration, `data/processed/share/venkatapur_evidence_demo.zip` packages the required derived layers, a portable QGIS project, report, limitations and attribution. Extract the entire ZIP, read `START_HERE.txt`, then open `OPEN_IN_QGIS.qgz`. QGIS is required; this is not a hosted website. The bundle was relocation-tested with all 49 layers and file hashes verified. Rebuild it with QGIS Python using `src/package_evidence_demo.py` after the offline review. The ZIP remains outside Git.

With the completed cached inputs available, close QGIS and run in PowerShell:

```powershell
& 'C:\Program Files\QGIS 3.40.11\bin\python-qgis-ltr.bat' src/run_offline_review.py
```

This rebuilds review outputs only, without downloads or login. It does not obtain missing source data or independently validate the science. QGIS installation paths may differ on another computer. Source extraction and rainfall environment instructions are in [src/README.md](src/README.md).

## Coordinate standard

- Boundary exchange: WGS 84 longitude/latitude (EPSG:4326).
- Analysis: UTM zone 44N (EPSG:32644), aligned 30 m cells.

## Folder guide

- `data/raw/`: original inputs, stored outside Git as specified in the plan.
- `data/interim/`: local source copies and intermediate processing, ignored by Git.
- `data/processed/`: screening rasters and quality outputs, ignored by Git.
- `qgis/`: QGIS project and styles.
- `src/`: implemented extraction, processing, exploratory scenarios and review code.
- `docs/`: methodology and provenance.

Keep raw satellite data, generated rasters, secrets and credentials out of Git. Any extension requiring additional downloads or private authentication should document its scope and retain native data support and missing-data checks.

# Public satellite data plan: Venkatapur

## 1. Scope and boundary

Build a **relative groundwater-potential screening index** for Venkatapur, Korutla, Jagtial, Telangana, India, using public satellite observations and DEM-derived proxies with transparent weighted overlay / MCDA. No verified borewell labels exist: do not use supervised machine learning, nearby-well features, calibrated probabilities or predictive accuracy claims.

Satellites do not directly detect groundwater. Surface moisture, vegetation, terrain and rainfall cannot establish aquifer storage, borewell yield, water availability or drilling depth. Irrigation, soils, crops and infrastructure can dominate the signals. Results prioritize investigation; drilling requires local hydrogeological assessment and appropriate field/geophysical checks.

This plan supersedes the older training instructions in `docs/01_field_data_collection.md` and `src/README.md` for this phase. Optional geology is non-satellite context and must be identified as such. CHIRPS is satellite-plus-gauge, not strictly satellite-only.

Confirm the intended village with a documented public boundary or a reviewed manually digitized polygon. Record source, license, date, CRS and uncertainty. Do not infer the boundary from a name or single coordinate. Label provisional boundaries and outputs explicitly. Keep the reporting polygon separate from a **5 km processing buffer**. Expand the DEM extent further where necessary to include upstream contributing catchments; derive hydrology before clipping.

## 2. Time periods and common grid

- Primary baseline: **2021–2025**, five complete calendar years. Do not mix incomplete 2026 seasons into it.
- Pre-monsoon: March–May; monsoon: June–September; post-monsoon: October–December, separately for each year.
- Make seasonal composites per year, then a median across years so scene-rich years do not dominate. Compare matched pre/post seasons within each year. Record actual Sentinel-1 availability and orbit coverage changes.
- Rainfall climatology: 2001–2025 if consistently available for the selected product; otherwise document a shorter complete period. Never treat missing months as zero.
- Analysis grid: EPSG:32644, 30 m square cells, fixed origin, extent and alignment saved in configuration. Retain EPSG:4326 for boundary exchange. A 30 m output does not imply borewell-scale accuracy; rainfall retains its coarse native support.

## 3. Public data inventory

Public availability does not guarantee anonymous downloads. This task is documentation only: no large downloads, API setup or credentials are required now. Later, inventory the AOI and estimate sizes before obtaining scenes. Scientific processing requires numeric bands and metadata, not browser screenshots or rendered RGB exports.

| Input | Public source / product | Selection and native scale | Role and caveats |
| --- | --- | --- | --- |
| Sentinel-2 | [Copernicus Sentinel-2](https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2), L2A through [Copernicus Browser](https://documentation.dataspace.copernicus.eu/Applications/Browser.html) | 2021–2025; B3/B4/B8 at 10 m, B11 and SCL at 20 m. Start inventory at scene cloud cover <=40%, then mask pixels. | Surface reflectance, vegetation, moisture and water screening. Downloads may require a free account. |
| Sentinel-1 | Copernicus Browser, IW GRD VV+VH | One relative orbit and pass direction with the best repeated coverage; preserve incidence angles. Approximately 10 m pixel spacing is not 10 m independent resolution. | Seasonal surface backscatter response; confounded by crops, roughness and geometry. |
| DEM | [SRTM 1 Arc-Second Global](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm), void-filled, via EarthExplorer | Approximately 30 m; February 2000 acquisition. Account access may be needed later. | Slope, flow accumulation, wetness and drainage. Old surface elevations and artifacts limit local detail. |
| Satellite rainfall | [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Approximately 0.1 degrees. Select a documented satellite-only/uncalibrated precipitation variable where offered; freeze release, run, variable, units and period. | Verify gauge-adjustment status before use. Final calibrated precipitation is gauge-adjusted and does not satisfy strict satellite-only scope. Regional temporal context, not local recharge. |
| Optional rainfall alternative | [CHIRPS v2](https://chc.ucsb.edu/data/chirps/), public CHC monthly files | 0.05 degrees, 2001–2025 climatology and 2021–2025 seasonal totals | Satellite-plus-gauge alternative only if that scope change is explicitly accepted. Do not silently mix product versions. |
| Optional geology / lineaments | Public GSI maps via [Bhukosh](https://bhukosh.gsi.gov.in/), subject to access/reuse terms; DEM hillshades and optical interpretation | Record geological map scale/edition and interpretation evidence | Geology is non-satellite context. Image lineaments are unverified surface structures, not confirmed fractures or water-bearing zones. Omit if evidence/access is inadequate. |

For every input record product ID, provider URL, attribution/license, acquisition date, processing baseline/version, tile/orbit, bands/variables, native CRS/resolution, units, NoData, extent, size and local checksum. Exclude tokens and signed URLs from manifests. Record failed searches and missing seasons rather than filling gaps invisibly.

## 4. Local folders and Git hygiene

Proposed layout; these directories and scripts are not created by this plan:

```text
data/raw/sentinel/s1/                  # original GRD products
data/raw/sentinel/s2/                  # original L2A products
data/interim/public_inputs/dem/        # unchanged local source DEM
data/interim/public_inputs/rainfall/   # original rainfall files
data/interim/public_inputs/context/    # boundary and optional geology
data/interim/s1/                       # corrected backscatter/composites
data/interim/s2/                       # masks and seasonal indices
data/interim/terrain/                  # hydrology and drainage
data/interim/aligned/                  # common-grid inputs
data/processed/mcda/                   # score and relative classes
data/processed/quality/                # coverage and sensitivity
docs/data_manifest.csv                 # small sanitized provenance table
qgis/                                 # project, styles, processing models
src/                                  # future scripts and configuration
```

Existing `.gitignore` rules cover `data/raw/sentinel/`, all `data/interim/` and `data/processed/`, and common raster extensions. Put **all other downloaded inputs**, including archives, NetCDF/HDF and vectors, under `data/interim/public_inputs/`, not directly under `data/raw/`. Preserve these source copies unchanged despite the folder name. Store secrets outside the repository, for example in an OS credential store. The current ignore rules do not protect every secret filename or raster format everywhere: never add `.env`, tokens, service-account files or credential-bearing configuration.

Before future acquisition, extend ignore rules if a different layout is needed. Before staging, inspect `git status --short`, `git diff --cached --stat` and `git check-ignore <representative-path>` for each input format. Ignore rules do not untrack committed files. Commit only documentation, code, small sanitized configuration/metadata and suitable QGIS project/style files; inspect QGIS files for private paths and embedded credentials.

## 5. QGIS / SNAP processing

### A. Preparation and alignment

Set QGIS project CRS to EPSG:32644. Repair the AOI geometry, visually confirm location and create the buffer. Use GDAL Warp/Align Rasters with explicit grid extent/origin: average for aggregation of finer continuous data, bilinear for continuous reprojection where appropriate, nearest-neighbor for categorical masks/classes. Preserve NoData separately from zero. Do not interpolate rainfall into apparent village-scale information.

### B. Sentinel-2

1. Read product metadata and convert DN to reflectance using declared quantification and band offsets. Respect provider harmonization; do not apply offsets twice across baselines. See the [ESA L2A quality report](https://sentiwiki.copernicus.eu/__attachments/1673423/OMPC.CS.DQR.002.12-2024%20-%20MSI%20L2A%20DQR%20January%202025%20-%2081.0.pdf).
2. Mask SCL classes 0, 1, 2, 3, 7, 8, 9, 10 and 11 by default. These cover NoData, defective pixels, dark/shadow pixels, cloud shadows, cloud-low-probability/unclassified pixels, medium/high-probability clouds, cirrus and snow. Class 7 is cloud-low-probability/unclassified; class 2 is treated cautiously as a dark/shadow class. Start cloud/shadow dilation at 60 m and review edges. Save valid observation counts.
3. Align reflectance bands and use Raster Calculator for `NDVI=(B8-B4)/(B8+B4)`, `NDMI=(B8-B11)/(B8+B11)` and `MNDWI=(B3-B11)/(B3+B11)`. Mask zero denominators. B11 imposes at least 20 m source support on moisture/water indices.
4. Create pixelwise seasonal medians per year. Require at least three valid observations per season and three matched years for seasonal differences; otherwise mark insufficient coverage. Derive median pre-monsoon NDMI and median post-minus-pre NDMI. Keep NDVI as vegetation/irrigation context rather than another independent moisture weight.
5. Review persistent open water using MNDWI >0 as an initial flag, SCL water and multi-date imagery. Exclude it from terrestrial scoring. Flag visible built-up areas and irrigated crops for caution using documented interpretation rules, without a trained classifier. Persistent greenness in irrigated fields does not establish natural recharge.

### C. Sentinel-1

Preprocess raw GRD with ESA SNAP before QGIS; QGIS raster calculators do not calibrate GRD. Use an explicit graph based on the [ESA time-series tutorial](https://step.esa.int/docs/tutorials/S1TBX%20Time-series%20analysis%20with%20Sentinel-1.pdf): orbit correction, border/thermal noise removal as applicable, calibration, consistent speckle treatment and DEM-based terrain correction. Use one backscatter convention (initially sigma0) throughout. Terrain correction provides geolocation and is not automatically radiometric terrain flattening; if using gamma0 terrain-flattened products, process every scene consistently and document the alternative.

Use buffered subsets and a local DEM; record orbit availability and prevent unexpected automatic downloads until acquisition is authorized. Mask invalid edges, water and layover/shadow where available; inspect incidence-angle artifacts. Form temporal medians in **linear power**, then convert positive values with `10*log10(power)` for dB diagnostics. Compare matched seasonal VV changes in dB; retain VH and VV/VH as crop/roughness diagnostics. Require three acquisitions per season and three matched years, or flag coverage failure. Higher return is not uniquely wetter ground.

### D. DEM, wetness and drainage

1. Reproject with elevation units in metres. Preserve the original DEM and inspect voids/artifacts. Fill/breach spurious depressions on the larger catchment extent; do not indiscriminately remove real tanks. Record elevation datum, algorithm and parameters.
2. Derive slope in degrees with QGIS/GDAL. Use one documented GRASS or equivalent hydrology provider for D8 flow direction and contributing area. Convert contributing cell counts to square metres using 900 square metres per cell, checking the tool's convention for including the current cell.
3. Calculate `TWI=ln(a/tan(beta))`, with specific contributing area `a` in metres (contributing area divided by 30 m contour width) and slope `beta` in radians. Use a recorded 0.1-degree slope floor. Inspect flats/channel artifacts and mask open water.
4. Extract drainage initially at 0.5 square kilometres contributing area (about 556 cells). Test 0.25 and 1.0 square kilometre thresholds against imagery. Compute drainage distance in metres and density as stream kilometres per square kilometre within a 1 km radius on buffered data, then clip.
5. Keep distance/density as diagnostics initially. Streams may convey runoff, indicate discharge or support infiltration; proximity/density is not universally favorable. Do not double-count these with TWI in the baseline.

### E. Rainfall and optional structural context

Aggregate satellite rainfall to complete monthly, monsoon and annual totals with unit-aware integration: multiply rates by elapsed duration, but do not multiply existing accumulations again. Area-weight native cells intersecting the AOI. Report 2021–2025 variability and anomalies against the fixed climatology. Retain native spatial support; give rainfall zero baseline spatial weight where no meaningful gradient is resolved. A regional rainfall anomaly is not measured recharge.

For optional lineaments, compare multiple hillshade azimuths and optical dates. Record interpreter, confidence, evidence and a starting minimum length of 300 m. Exclude roads, canals, field boundaries and illumination artifacts. Keep geology and lineaments outside the baseline until provenance and interpretation are reviewed; introduce any later weights only in a separately documented scenario.

## 6. Candidate evidence and exploratory MCDA scenarios

**Final combined weights must not be set before the first small-AOI data inventory, correlation review, and irrigation/crop-confounding review.** No default combined weights or GPI equation are prescribed at this stage. Review observation coverage, informative spatial variation, redundancy and plausible alternative explanations before choosing any combination.

| Candidate evidence | Role | Interpretation to review |
| --- | --- | --- |
| Slope | Terrain-setting candidate | Lower slope may favor infiltration opportunity, but does not establish permeability. |
| TWI | Terrain-setting candidate | Higher convergence may indicate accumulation, discharge or waterlogging; inspect terrain artifacts and correlation with slope. |
| Pre-monsoon NDMI and seasonal NDMI change | Separate optical surface-evidence candidates | Moisture patterns may reflect irrigation, vegetation or crop cycles rather than natural recharge. |
| Sentinel-1 VV seasonal change, with VH and VV/VH diagnostics | Separate radar surface-evidence candidates | Response direction is unresolved until crop, roughness and acquisition-geometry confounding are reviewed. |

Keep drainage, rainfall, NDVI and optional geology/lineaments as contextual diagnostics during the first review. Do not assign them combined weights in advance. Rainfall must retain its native spatial support; optional geology remains explicitly non-satellite context.

Require separate named scenarios before any combined exploratory score: `terrain-setting` for slope/TWI candidates, `optical-surface-evidence` for NDMI candidates, and `radar-surface-evidence` for Sentinel-1 candidates. Initially present their individual layers separately. Record each scenario's selected indicators, any within-scenario transformations or weights, rationale, exclusions and coverage; names do not imply that a weighted score must be produced.

Compare these scenarios and their sensitivities, including correlated-indicator omission, alternative radar-response directions, year-to-year variation, and exclusion of irrigated/crop-confounded areas. Only after this comparison and the required reviews may a separately named `combined-exploratory` scenario be considered. Document its proposed weights and rationale explicitly and compare alternative combinations; do not treat any one combination as an established baseline.

If normalization is used, record its numeric breakpoints, reporting extent and suitability assumptions, and keep them fixed for comparisons. Do not force a suitability direction for unresolved surface evidence. Keep water exclusions and insufficient coverage separate; never replace NoData with low suitability or renormalize weights differently at each pixel. Omit uninformative indicators only in explicitly named scenarios. Do not produce a score if the remaining evidence is inadequate.

Any later score or classes describe only the named exploratory scenario and its assumptions. Record class boundaries and handle tied/constant values without forcing distinct classes. **Do not call any scenario a validated groundwater-potential map.** No scenario establishes aquifer properties, drilling success probabilities, yield, depth or guaranteed water.

## 7. Python reproduction and quality checks

Future implementation can use rasterio/GDAL for aligned masked rasters, numpy for composites/overlay, geopandas for boundaries, and xarray with a suitable rainfall reader. Use SNAP `gpt` for radar and one pinned GRASS/QGIS hydrology method. These are planned dependencies, not installation steps now.

Implement separate stages for input validation, Sentinel preprocessing, terrain/drainage, rainfall summaries, alignment/scoring and quality/sensitivity exports. Configuration must save AOI checksum, dates, product versions, CRS/grid transform, masks, count minima, hydrology parameters, percentile breakpoints and weights. Save software versions and logs. Match QGIS/SNAP algorithms rather than silently substituting Python approximations.

Before releasing a map:

- Verify CRS, transforms, dimensions, units, denominators, NoData, count thresholds, mask behavior, score range and weight sum. Inspect alignment, cloud edges, radar seams and drainage artifacts visually.
- Compare years and outputs with irrigated/built-up flags excluded. For any weights proposed after the required reviews, test +/-20% relative variations and renormalize globally within each named scenario. Run leave-one-indicator-out scenarios and test alternative masks, drainage thresholds and radar-response direction/omission. These assess robustness, not predictive accuracy.
- Export score spread and class agreement across scenarios, preserving the declared reference scenario's class boundaries for comparisons. Label unstable areas uncertain. Coverage and sensitivity are not confidence probabilities.
- Deliver score/classes, masks/counts, sensitivity layers, manifest/configuration and a QGIS layout with scale, CRS, date and source attribution. Include: **Relative groundwater-potential screening; not borewell yield, drilling depth or a guarantee of water.**

The current deliverable is documentation only. Boundary confirmation and a reviewed source inventory precede later small AOI trials and full acquisition.

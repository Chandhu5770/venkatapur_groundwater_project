# Python modules

`build_drainage_diagnostics.py` runs locally after the terrain pilot to create directed D8 stream segments and approximate drainage density within a 1 km radius, at 0.25/0.5/1 km2 contributing-area thresholds. Run with QGIS Python. It uses SciPy (included in this QGIS installation). Outputs are in ignored `data/processed/terrain_pilot/drainage_diagnostics/`. Density uses half of each segment's length at each endpoint cell and a discrete circular neighbourhood; it is not an exact vector intersection calculation. Neighbourhoods containing uncertain upstream flow are excluded. Stream vectors are clipped to the planning circle; neighbourhood density uses the larger processing extent. Existing vector output is protected against overwrite: review or rename it before rerunning. These remain provisional drainage diagnostics with no assumed suitability direction.

## Available processing scripts

- `download_s2_trial.py`: downloads the original two-date small-area trial.
- `process_s2_trial.py`: scales and masks those inputs and creates trial indices.
- `audit_s2_water_masks.py`: compares alternative water exclusions.
- `build_s2_seasons_2025.py`: downloads up to two distinct low-cloud dates per month for March-May and October-December 2025, then builds sampled seasonal medians, observation counts, separate water-frequency layers and a QGIS review project.
- `build_terrain_pilot.py`: creates a separate 30 m Copernicus GLO-30 DSM terrain pilot using GDAL and installed GRASS 8.4 D8 routing. Run with the same QGIS Python environment. It tries 30 km and 50 km processing extents and retains edge-underestimate flags. Outputs and the review project are under `data/processed/terrain_pilot/`; source subsets and GRASS working files remain under ignored `data/interim/` paths.

The terrain pilot uses Copernicus GLO-30 Public (AWS 2021 release), an explicit public-access alternative to the SRTM source proposed in the data plan. This is a surface model including buildings and vegetation. GRASS handles depressions with least-cost routing; no blanket depression filling or surveyed tank/depression mask is applied. Stream thresholds are 0.25, 0.5 and 1 square kilometre. TWI uses specific contributing area and a 0.1-degree slope floor. Pixels flagged as likely flow underestimates are excluded from hydrology outputs. Streams, depressions, open-water areas and boundary effects still require review. Stream vectors and drainage density remain pending. The manifest records the assumptions and affected-pixel counts. Seasonal optical layers retain their separate 20 m grid in the review project; no combined score is generated.

Run these with the QGIS Python environment, which supplies GDAL, NumPy and QGIS libraries. For the installed Windows version:

```powershell
& 'C:\Program Files\QGIS 3.40.11\bin\python-qgis-ltr.bat' src/build_s2_seasons_2025.py
```

The seasonal script uses anonymous public Earth Search COG access and downloads only study-area windows. Source data/metadata are under the ignored `data/raw/sentinel/s2/seasons_2025/`; outputs are under the ignored `data/processed/s2_seasons_2025/`. Existing downloaded windows are reused; derived seasonal outputs are regenerated on rerun. Keep input metadata paired with each window.

The 2025 seasonal pilot retains the trial's 20 m grid spacing, with a 100 m apron for shadow masking; it is not the planned final 30 m MCDA grid. Medians require at least three valid observations per pixel per index. Counts include zero inside the circle; outside is NoData. Reflectance offsets come from source metadata. Pixels with negative index-input reflectance or a near-zero denominator are excluded rather than clipped. SCL and MNDWI water frequencies are separate uncertain diagnostics; no automatic persistent-water exclusion is applied to the seasonal medians. Differences include surface water and must be interpreted accordingly.

The date selection is a small, month-balanced sample ranked by whole-tile cloud cover, not a complete seasonal archive or a guarantee of cloud-free AOI pixels. The manifest records dates, hashes, scales, thresholds and coverage. One sampled year does not meet the multi-year requirement in the data plan and must not be described as a validated groundwater-potential result.

The current workflow is satellite-only screening using transparent MCDA, following [the public satellite data plan](../docs/04_public_satellite_data_plan.md). No verified borewell labels are available. Do not train supervised models or generate success-probability rasters.

Planned processing stages cover input inventory, Sentinel preprocessing, terrain/drainage, rainfall summaries, grid alignment, separate named evidence scenarios and sensitivity comparison. Combined weights remain unset until the small-AOI inventory, correlation review and irrigation/crop-confounding review are complete.

Borewell-survey validation and supervised-ML material from earlier planning are optional future work, not the current workflow or a prerequisite for it. Verified survey observations may later support independent assessment. Any supervised-ML study would require a separately reviewed scope, suitable verified labels and spatial validation; no training scripts are planned for the current phase.

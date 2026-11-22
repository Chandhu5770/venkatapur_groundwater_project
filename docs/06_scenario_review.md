# Scenario review: Venkatapur pilot

Review date: 22 November 2026. This records exploratory evidence, not a validated groundwater-potential map. The 5 km planning buffer is not a verified village boundary. No borewell labels, supervised learning, yield estimates or drilling-depth predictions are used.

## Evidence available

- Optical and radar seasonal outputs cover 2023–2025, a subset of the planned 2021–2025 baseline. Pre-monsoon is March–May; post-monsoon is October–December. Changes are calculated within each year before multi-year summarization.
- Terrain uses Copernicus GLO-30 DSM as a documented alternative to the originally planned SRTM. Slope and drainage are setting indicators, not observations of aquifer storage. Hydrological outputs exclude flagged underestimated upstream contributing areas. DSM vegetation/building effects and drainage threshold choice remain limitations.
- May 2025 IMERG precipitationUncal has 31 complete UTC days and 1,488 valid half-hour intervals in each of two native cells. Totals are 123.32 and 123.98 mm. This is regional context, not a village average, recharge estimate, seasonal baseline or a 30 m spatial indicator. Monthly gauge adjustment is omitted; ancillary calibration/models remain.

## Named scenarios to retain separately

| Scenario | Evidence and interpretation | Restrictions |
|---|---|---|
| Terrain setting | Slope, TWI, drainage-distance and drainage-density diagnostics | Lower slope and higher TWI are hypotheses about runoff/convergence, not universally monotonic groundwater suitability. Compare drainage extraction thresholds before any ranking. TWI and drainage derive from the same DEM and can duplicate information. |
| Optical surface evidence | NDMI seasonal changes, with NDVI as vegetation context | Moist vegetation, irrigation and crop phenology can dominate NDMI. NDVI must not automatically become a second independently weighted moisture indicator. |
| Radar surface evidence | Same-orbit VV/VH seasonal changes and consistency | Increased brightness has no default groundwater-suitability direction. Moisture, roughness, vegetation and surface water can change the response. VV and VH are not independent evidence by assumption. |
| Recurrent SCL-water exclusion | Repeat optical/radar summaries after excluding recurrent SCL water | Classification uncertainty remains; this is a sensitivity mask. |
| Broad-water exclusion | Repeat using recurrent SCL water or MNDWI > 0 | Broad MNDWI can flag land. Compare retained area and distributions rather than treating this mask as confirmed water. |
| Vegetation-confounding stress test | Exclude recurrent NDVI > 0.3 as well as SCL water | This is not an irrigation/crop classifier. It removes most optical support and cannot serve as the default analysis population. |

Final combined terrain-plus-surface weights remain unset. A combined exploratory score requires documented indicator directions and normalization, within-group redundancy decisions, matched spatial support, separate named weight scenarios and sensitivity comparison. No scenario is validated by agreement with another proxy map. The terrain-only hypothetical weights tested below are not final groundwater weights.

## Findings from existing sensitivity outputs

Automated NDMI/NDVI comparison removes the need for manual screenshot comparison. On 81,423 common pixels after recurrent SCL-water exclusion, 45.72% have positive changes in both indices and 44.61% negative changes in both: 90.33% share a strict sign. Descriptive Spearman correlation is 0.9091. With arbitrary ±0.02 near-zero bands for each index, 81.15% of all common pixels still change together beyond those bands, 4.16% change in opposite directions and 14.69% have at least one near-zero change. The denominator remains all common pixels. Both indices share NIR, so this is not independent confirmation. Results support keeping vegetation confounding explicit; they do not identify irrigation, establish causation or validate groundwater. Reproduce using `review_optical_confounding.py`; results and notes are in `multiyear_2023_2025/surface_patterns/optical_confounding_statistics.csv` and `optical_confounding_notes.txt`.

The all-complete optical scenario retains 81,590 pixels (73.431 km²). Its median within-year NDMI change across three paired years is +0.01470. Recurrent SCL-water exclusion gives +0.01438; broad-water exclusion gives approximately +0.01423. The aggregate median is similar across these water masks; this does not establish pixel-level rank stability or groundwater validity.

The vegetation stress test leaves only about 6.54% of the complete optical population. A changed summary under that mask describes a substantially different population, not a causal irrigation effect. Radar's unrestricted support covers 87,315 pixels; compare sensor relationships on common valid pixels rather than comparing unrestricted sensor medians as though they cover the same population.

## May rainfall and individual-image review

The 2–12 May optical comparison retains 97.82% of the planning circle on common valid pixels. Median pixel NDMI change is −0.0278; water exclusions give similar aggregate changes. Estimated rainfall in the seven complete UTC days before 12 May is 16.80–17.44 mm, but the previous three days have zero estimated rainfall. These observations do not establish a causal response or a rain-independent moisture signal.

The 16–28 May radar comparison has median pixel changes of +2.41 dB VV and +3.08 dB VH. About 90–92% of common pixels brighten. Rainfall before 28 May is 71.28–81.66 mm over seven complete UTC days. Rain and brightness changes coincide; rainfall influence is a plausible confounder, not an established explanation. Only three radar dates are available in this monthly comparison.

Rainfall windows exclude the acquisition day to avoid including rain after acquisition; they are calendar-day windows, not exact trailing-hour totals. Windows needing unavailable April data stay blank. May cannot explain the entire March–May seasonal composite or the multi-year seasonal changes.

## Next analysis gate

### Exploratory terrain-only weight scenarios

After the inventory, correlation and crop/irrigation-confounding reviews, three hypothetical terrain-setting scenarios were tested on 81,270 identical valid pixels: `slope_emphasis` (0.75 inverse slope rank, 0.25 TWI rank), `balanced_terrain` (0.50/0.50), and `convergence_emphasis` (0.25/0.75). These symmetric contrasts test sensitivity; they are not calibrated, selected final weights or validated groundwater-potential maps. They do not combine terrain with optical/radar evidence.

Average-tied percentile ranks normalize both indicators on the common analysis domain. Lower slope and higher TWI are conditional runoff/convergence hypotheses. Their shared DEM provenance and TWI's slope dependence mean that combining them can duplicate terrain information. Source layers remain available for single-indicator review; formal omission and alternative-normalization comparisons remain necessary before selecting a final combined model.

Comparing slope emphasis with convergence emphasis gives rank correlation 0.8718. Membership in the locally defined upper score fifth changes for 13.46% of common pixels; upper-fifth intersection/union is 0.4965. This sensitivity is material even though overall ranks are correlated. No scenario is selected. The optical-derived recurrent-water/coverage mask limits the domain, and upstream-edge estimates remain excluded. Upper-fifth membership is not a favorable groundwater class or success probability.

Reproduce with `explore_terrain_mcda.py`; outputs are in `data/processed/terrain_scenarios/`, including `terrain_scenarios_review.qgz`, named score rasters, coverage, weights and pairwise sensitivity tables. Read `README.txt` before interpretation. Drainage, rainfall and surface indicators have no weight in these terrain-only experiments.

The experiment now includes slope-only and TWI-only omission checks and a second normalization: values scaled linearly between their local 2nd/98th percentiles, clipped to 0–1, with slope inverted. Ten scenarios yield 45 pairwise comparisons on the same 81,270 pixels. Clipping limits are arbitrary sensitivity assumptions, not hydrogeological thresholds. All three original weight scenarios remain unchanged.

Relative to balanced percentile-rank terrain, upper-fifth membership changes for 11.94% of common pixels with slope alone and 12.93% with TWI alone. Changing only balanced normalization to clipped-linear changes membership for 8.68%, despite rank correlation of 0.9751. Slope-only versus TWI-only gives 23.37% membership change. Both indicator omission and normalization therefore matter; no unique preferred map follows from these tests. Original source layers and all scenarios remain separate. Score ranges, identical masks and reconstruction of balanced scores from single-indicator components were checked for both normalizations. The scenario-count raster retains its original meaning across only the three rank-weight scenarios.

### Temporal consistency

On 81,423 common pixels after recurrent SCL-water exclusion, NDMI seasonal changes are positive in all three years for 37.21% of pixels and negative in all three for 25.30%; 37.49% have mixed signs or an exact zero. Corresponding positive/negative/mixed-or-zero shares are 25.42%/10.89%/63.68% for VV and 26.03%/14.15%/59.82% for VH. These use strict nonzero signs, so tiny changes count. A three-year median alone hides substantial annual sign variability, particularly for radar. Consistency does not establish groundwater persistence, statistical confidence or independence from recurring land management.

Reproduce with `review_temporal_consistency.py` using QGIS Python. Maps and the QGIS project `temporal_consistency_review.qgz` are in `multiyear_2023_2025/surface_patterns/`; category totals are checked against identical common support.

### Drainage-density threshold sensitivity

The 0.25, 0.5 and 1.0 km² contributing-area thresholds were compared on 65,696 common valid density pixels (59.1264 km²). Median 1 km-neighbourhood density changes from 1.5438 to 1.1639 to 0.8405 km/km². Between the extreme thresholds, descriptive Spearman rank correlation is 0.8602, but 15.36% of common pixels change membership of the locally defined upper density third; upper-third intersection/union is 0.6256. Ties are included at the quantile cutoff.

Threshold choice therefore affects both magnitude and spatial grouping. An upper density third is not a groundwater-suitability class, and overlap is not validation accuracy. Preserve all three threshold scenarios rather than selecting a threshold for a preferred result. This comparison covers density, not a recomputation of distance-to-drainage at all thresholds. Uncertain upstream neighbourhoods remain NoData; coverage loss must accompany any density-based scenario. Results: `terrain_pilot/drainage_diagnostics/threshold_sensitivity.csv`.

### Common-support terrain and baseline review

The surface-pattern maps compare NDMI with VV and VH separately, under unrestricted, recurrent SCL-water and broad-water masks. Strict sign and arbitrary near-zero bands (NDMI ±0.02; radar ±0.5 dB) are separate scenarios. These bands are sensitivity assumptions, not calibrated uncertainty limits. Agreement is not independent validation.

Terrain-stratum summaries retain 81,270 common pixels after recurrent SCL-water exclusion and valid-data checks for slope, TWI, NDMI, NDVI, VV and VH. Local thirds are descriptive groups, not suitability thresholds. The lower slope third has pre-monsoon NDMI 0.0820 and post-monsoon NDMI 0.0150; the upper third has 0.0158 and 0.0491 respectively. Median within-year NDMI changes are −0.0357 and +0.0571, accompanied by NDVI changes of −0.0789 and +0.0480.

Thus greater NDMI change does not imply a higher initial moisture index. Vegetation changes follow the same broad group pattern, leaving crop/irrigation confounding unresolved. The upper slope third has a median slope of only about 2.09 degrees: “upper” is relative to this local sample, not an absolute steep-terrain class. Higher-TWI groups also start with higher NDMI and show declining NDVI. These associations are descriptive; no causal mechanism is established.

Pre/post level summaries and within-year change summaries use different orders of median aggregation. Subtracting the displayed level medians need not reproduce the displayed median change. The figure `surface_patterns/terrain_surface_review.pdf` displays both quantities separately.

1. Inspect mapped differences and distributions on common support, including water-mask and vegetation strata, rather than relying on whole-area medians.
2. Quantify terrain-threshold and surface-mask sensitivity separately. Retain NoData and upstream-edge exclusions in every comparison.
3. Document what rainfall coverage is sufficient for the declared demonstration scope. Keep May as limited context unless additional periods are obtained; do not imply the full rainfall baseline is complete.
4. Only then consider separate exploratory weight scenarios, reporting changes in retained area and rankings. Keep terrain setting and surface evidence visible alongside any combined result.

## Reproducible local evidence

For a single review workspace, open `data/processed/integrated_evidence_review/venkatapur_evidence_review.qgz`. The generated project groups terrain, optical levels/changes, radar changes, surface-pattern scenarios, temporal consistency, ten hypothetical terrain-only scenarios and CSV review tables, including automated optical-confounding statistics. All 49 layers were validated after reopening the saved project. Keep sibling processed folders in place because paths are relative. The project has no online basemap and no final combined groundwater score. Toggle one raster at a time and consult the accompanying `START_HERE.txt`. A compact findings and limitations report, `venkatapur_analysis_review.pdf`, is generated in the same folder by `build_analysis_review_report.py`.

`run_offline_review.py` provides a cached eleven-step rebuild with per-step logs and a completion manifest. After QGIS was closed, all eleven steps completed successfully; final product hashes, 49 reopened valid layers and the three-page PDF were verified. This verifies cached review reproducibility, not a fresh source-data extraction or scientific validation. Close QGIS before rerunning because open layers can lock output files on Windows. The runner checks for common QGIS executable names before beginning. Pattern maps use `pattern_` filenames and temporary-file replacement to protect existing maps on replacement failure. Source data is not modified by the review runner.

Generated outputs remain Git-ignored under `data/processed/`:

- `multiyear_2023_2025/sensitivity/scenario_statistics.csv` and `scenario_correlations.csv`.
- `indicator_review/correlations.csv` and `review_report.txt`.
- `rainfall_context/imerg_uncal_2025_05.csv`, `daily_rainfall_2025_05.csv`, and `may_acquisition_rainfall_context.csv`.
- `rainfall_context/may_paired_optical_statistics.csv` and `may_paired_radar_statistics.csv`.

Rainfall context is reproduced with `review_rainfall_context.py` in the Earthdata environment. Paired optical/radar diagnostics run with QGIS Python using `review_may_optical_rainfall.py` and `review_may_radar_rainfall.py`. These review scripts use cached data without credentials or downloads.

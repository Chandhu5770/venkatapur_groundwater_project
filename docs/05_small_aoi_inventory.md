# Small-AOI inventory: 2025 trial

## Scope

Metadata-only trial queried on 2026-11-08. The user confirmed the intended location in QGIS; this is not independent verification of an administrative boundary. Centre: latitude 18.83066925215722, longitude 78.75026556626672. The existing 5 km geodesic planning buffer has longitude/latitude bounds [78.70282636232028, 18.78549796615316, 78.79770477021316, 18.875840319515586]. Analysis CRS remains EPSG:32644.

This trial does not replace the planned 2021-2025 inventory. No imagery, DEM or rainfall rasters were downloaded. No weights, scores or groundwater maps were produced.

## Observed public catalogue results

Source: [Copernicus Data Space STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), GET `https://stac.dataspace.copernicus.eu/v1/search`. Parameters: `collections` as below, `bbox` as above, `datetime` covering each complete season in UTC, and `limit=100`. All four responses contained fewer than 100 results and no next-page link. The companion CSV contains all 151 returned product metadata records, without asset URLs or credentials.

| Collection | Season | Candidate products | Unique acquisition dates | Additional metadata |
| --- | --- | ---: | ---: | --- |
| sentinel-2-l2a | March-May 2025 | 66 | 22 | 52 products have whole-tile cloud cover <=40% |
| sentinel-2-l2a | October-December 2025 | 69 | 23 | 49 products have whole-tile cloud cover <=40% |
| sentinel-1-grd | March-May 2025 | 8 | 8 | IW GRDH, VV+VH, relative orbit 165, descending |
| sentinel-1-grd | October-December 2025 | 8 | 8 | IW GRDH, VV+VH, relative orbit 165, descending |

Sentinel-2 results include overlapping MGRS tiles 44QKF, 43QHB and 43QHA, all relative orbit 19. Multiple tile products from the same date are not independent observations. Do not interpret 66 products as 66 usable dates. Bounding-box candidates still require footprint and valid-pixel coverage checks over the actual buffer. Tile cloud percentages do not establish AOI cloud-free coverage. Three valid observations per pixel per season have not been demonstrated.

Orbit 165 descending is a Sentinel-1 candidate for a matched-season trial, not a final multi-year orbit selection. Confirm footprint coverage, valid edges, incidence angles and 2021-2025 continuity before choosing it. This single-year trial cannot establish the required three paired years.

## DEM, drainage and rainfall: pending

- SRTM 1 Arc-Second remains the planned DEM. The buffer lies within the nominal N18E078 one-degree tile based on its bounds; actual product availability, size, voids and required upstream processing extent remain unchecked. Do not assume a single tile suffices for catchment analysis.
- Drainage will be derived from a reviewed DEM; no independent drainage dataset or derived streams have been acquired.
- IMERG release, run, uncalibrated variable, temporal coverage, access route and download size still need confirmation. NASA's [V07 release notes](https://gpm.nasa.gov/sites/default/files/2024-12/IMERG_V07_ReleaseNotes_241126.pdf) document changes to variable organization. Do not substitute gauge-calibrated rainfall or presume a convenient monthly product provides the desired satellite-only variable.
- Geology and interpreted lineaments remain optional and unacquired.

## Next QGIS review

1. Retain the confirmed reference point and provisional buffer in `map1.qgz`.
2. Open [Copernicus Browser](https://browser.dataspace.copernicus.eu/), locate the centre and inspect Sentinel-2 L2A candidates for March-May and October-December 2025.
3. Compare footprints of overlapping tiles and inspect cloud/shadow coverage over the actual circle. Record candidate IDs from the CSV; do not download all overlapping tile products.
4. Record visible crops, irrigation, tanks and built-up areas as interpretation flags, not aquifer evidence. Browser imagery supports visual review, not quantitative reflectance analysis.
5. Review a small numeric-data acquisition and its estimated size before downloading. Then apply the documented SCL mask and observation-count checks. Correlation and irrigation/crop-confounding reviews require processed data and remain pending.

Keep terrain-setting, optical surface evidence and radar surface evidence separate. Any combined exploratory scenario remains deferred until the reviews and sensitivity comparisons in the public data plan are complete. These catalogue results do not validate groundwater potential.

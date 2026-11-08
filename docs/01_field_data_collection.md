# Venkatapur borewell survey: optional future validation

This survey is optional future validation, not the current workflow or a prerequisite for satellite-only screening. Follow [the public satellite data plan](04_public_satellite_data_plan.md) for the current MCDA workflow. No verified borewell labels are currently available; do not train supervised models. Any supervised-ML material belongs to a separately reviewed future phase, not this pilot workflow.

## What to collect

For every existing borewell, record the GPS location, present status, total depth, approximate drilling year, water level, yield, and whether it remains usable in the pre-monsoon period. Photograph the borewell only with the farmer's permission.

## Quality order

Prefer evidence in this order:

1. water-level meter or pumping-test measurement;
2. drilling log / pump invoice / written local record;
3. farmer's well-maintained records; and
4. farmer recall.

Mark recall-only values as `medium` or `low` data quality. Do not invent missing depths or yields.

## Minimum first survey target

If a future validation survey is undertaken, collect 25 records first to test the form, then plan broader spatial and outcome coverage. Include failed and abandoned borewells as well as productive ones to reduce selection bias. A record-count target alone does not establish label quality or justify supervised learning; any later predictive study requires a separate methodology and validation review.

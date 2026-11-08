# Python modules

The current workflow is satellite-only screening using transparent MCDA, following [the public satellite data plan](../docs/04_public_satellite_data_plan.md). No verified borewell labels are available. Do not train supervised models or generate success-probability rasters.

Planned processing stages cover input inventory, Sentinel preprocessing, terrain/drainage, rainfall summaries, grid alignment, separate named evidence scenarios and sensitivity comparison. Combined weights remain unset until the small-AOI inventory, correlation review and irrigation/crop-confounding review are complete.

Borewell-survey validation and supervised-ML material from earlier planning are optional future work, not the current workflow or a prerequisite for it. Verified survey observations may later support independent assessment. Any supervised-ML study would require a separately reviewed scope, suitable verified labels and spatial validation; no training scripts are planned for the current phase.

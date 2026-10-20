# Illustrated final revision

Three figures supplement the independently accepted manuscript without changing
its original words, formulas, numbers, candidate selection or conclusions.
They use exact accepted HY3-010 saved results at
`4b8ac5d6822ac39ff1189c13d34ed3f84f699319`; no original observations are opened
and no investment simulation is rerun. The old eight-page PDF is preserved.

- Figure1: all eight generic modes, final60 scenarios, H30, fee0.25%; separate
  marginal median real growth and p90 real drawdown, zero-based bar axes.
- Figure2: four executed B/C own-horizon/fee cases against their fixed loss
  tolerances. A/D/E are referrals, not zero-valued simulated observations.
- Figure3: predeclared severe scenario172 for fixed Balanced, with annual thirds
  on the same path. Initial, post-fee and year-end observations are connected;
  no intra-year path, smoothing or new scenario selection is inferred.

The exact original final receipt authenticates each source blob. PNGs are300DPI
at full manuscript width; all chart fonts are11.2pt at that width. Vector PDF
versions and full plotted data are included in figure-provenance.json.

## Reproduction

Python3.12; Matplotlib3.11.2, Pillow12.3.0, pypdf6.21.1 and ReportLab as recorded
in the existing report requirements. Restore the offline Git bundle following
REPRODUCTION.txt before reading exact source objects.

The delivered figure assets can be used directly. To regenerate into a new
directory without replacing them:

    python -B report/build_final_figures.py --output-dir .runtime/reproduced-figures

To render the illustrated manuscript from saved assets without private names:

    python -B report/build_illustrated_submission.py --public --output-dir .runtime/reproduced-illustrated

For a local named submission, replace --public with --team-file pointing to a
local ignored JSON file containing report_display. Private member identities
and the named PDF are excluded from the source ZIP and GitHub.

## Software and procedural attribution

Matplotlib creates all quantitative plots. Procedural figure-design and review
guidance used Scientific Agent Skills' MIT-licensed scientific-visualization
skill (installed version1.4). This is a workflow resource, not a source of
competition observations or numerical results:

Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026).
Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents.
arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065

The author/title/year and current record were checked against
https://arxiv.org/abs/2609.00065 on2026-10-20. No claim that an automated style
check certifies scientific validity or general accessibility is made.

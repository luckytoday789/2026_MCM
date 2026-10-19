# Baseline figure captions and accessible descriptions

These are chief-prepared report assets from independently accepted development
results. The transformations and wording await the targeted independent figure
review. They do not represent new experiments, selected-policy results or final
outcomes. Use the original 180 mm export width to retain at least 11 pt text;
check actual size again in the assembled A4 report. A final comparison may need
a different panel containing accepted candidate results.

## Figure B1: Three fixed references over 30 years

**Caption.** Development scenarios 1--120, horizon 30 years, one-way transfer fee
0.25%, including initial allocation. Dots denote the scenario median; ticks denote
p10 real CAGR in panel A and p90 maximum real drawdown in panel B. Connecting
segments show the distance between these two descriptive statistics, not confidence
intervals. Large loss includes initial and post-fee observations. Annual thirds
restores equal weights at each annual review; initial thirds held makes only the
initial allocation; bills held makes no transfers. These are separate scenario
quantiles. They neither quantify statistical significance nor select a customer
portfolio. Full source values and all five horizons appear in
[baseline-development.md](baseline-development.md).

**Alt text.** Two horizontal dot-and-tick plots compare three references. Bills
held has the lowest median real growth and p90 loss. Initial thirds held has the
highest median growth, but annual thirds has higher p10 growth and lower p90 loss.
All three have positive maximum real drawdowns. The figure shows development
scenario statistics rather than confidence bounds or guarantees.

Files: `figures/baseline-h30-summary.svg`, `.pdf` and `.png`.

## Figure B2: A severe path for the required annual equal-weight baseline

**Caption.** Development scenario 5 is the annual-thirds reference's largest-loss
case at the 30-year horizon, selected under the existing greatest-drawdown rule.
The circle marks its year-1 ending peak; the triangle marks the year-8 post-fee
trough, a 50.88% decline. Fees are plotted at the beginning of each year: year-8
post-fee therefore lies at elapsed time 7. The plot retains every initial,
post-fee and annual-end observation; straight segments only join observations and
do not assert an intra-year path. The other two references use this same scenario;
this is not their own worst case. Terminal recovery does not undo the earlier
peak-to-trough loss. Fee rate 0.25%; initial nominal and real wealth 100.

**Alt text.** Real-wealth paths in scenario 5 compare annual thirds, initially
held thirds and bills. Annual thirds falls from its year-1 peak to about half that
peak just after the year-8 fee, then recovers. Initially held thirds tracks it
closely early and ends higher, while bills follows a different lower-growth path.
The selected scenario belongs to the annual baseline, not to each comparator's
severe-case selection. The downloadable event table preserves the fee observations.

Files: `figures/baseline-h30-severe-path.svg`, `.pdf` and `.png`;
`figures/baseline-h30-severe-points.csv` contains all 183 plotted observations.

## Reproduction and attribution

Run `python -B report/build_baseline_figures.py --check` for a read-only source,
data and stored-output integrity check. New exports are created only at missing
paths; conflicting files are never overwritten. Sources are exact HY3-003 Git
blobs at `7652410d73425371110784ef5fa97c03470a074e`, independently reviewed by
SOL-008 at `818af5d65bd8a271962d848dd552bd39ca561f68`. The provenance JSON stores
full-precision summary rows, selected peak/trough, hashes, dimensions and versions.
No simulation or competition input CSV is opened by this renderer.

The original supplied competition material is recorded as CC BY-NC-SA 4.0 in
`data/manifest.json`; these derived figures retain that attribution. Figure design
used the existing MIT-licensed scientific-visualization skill from K-Dense,
pinned at `593377bb048752abb0152deab9fbb1083a6087df` in `ops/skills-lock.json`.
No skill code was copied and no package was installed. Its procedural reference is:
Kassis, T., Agarwal, V., He, Y., Patel, D., and Brueckner, A. M. (2026).
*Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*.
[arXiv:2609.00065](https://doi.org/10.48550/arXiv.2609.00065).
The arXiv author/title record was checked on 2026-10-20 (latest record: v2).

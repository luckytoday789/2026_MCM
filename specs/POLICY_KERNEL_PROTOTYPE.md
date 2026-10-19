# Provisional policy kernel, 2026-10-20

The current user and overnight plan authorize chief to prepare provisional code
while independent design review is pending. This note does not amend the immutable
SOL-009 task, approve its design, authorize production experiments, or freeze any
policy. The original pilot specification remains unchanged and awaiting SOL-009.

`src/safeinvest/policy_pilot.py` implements only the declared five cost-aware
modes' mathematical decision core. It is not exported by the package and exposes
no data-loading CLI. Its convenience wrapper labels all runs synthetic. The
accepted accounting, metrics, baseline driver and existing baseline results are
unchanged. The module reads no competition file or external data.

The explicit prior contains positive three-asset annual real gross factors with
equal empirical weights. Stable log-sum-exp computes the gamma=4 negative third
moment. Contextual modes mix that entire marginal distribution with up to five
completed same-scenario observations using exactly 15:n probability mass. The
current gross outcome is absent from the callback context. The actual fee is
charged once through the accepted accounting functions; the factor of two affects
only the estimated-benefit score. All five normative targets and parameters are
unchanged from the proposal. No parameter was selected using new outcomes.

The callback owns one sequential scenario. It checks incoming holdings against
its prior post-fee holdings advanced by the latest completed observation. It
tracks initial real wealth, every post-fee value and every completed year end.
A crossing observed in year t can first suspend automation at review t+1.
Suspension latches and keeps component dollars at each future review. Returns
still accrue, so this is no guarantee against further losses. Invalid data fail
the entire synthetic run, including invalid data in its last year.

## Explicit details for the independent reviewer

- Tie comparisons are to the maximum candidate score, within absolute 1e-12.
  Candidate order is active, defensive, central, growth-tilted with duplicates
  removed. Every selected candidate must independently pass the strict keep
  gate; a near-tied active candidate cannot inherit a competitor's passing gate.
  Please challenge this resolution of the proposal's tolerance boundary.
- `proposed_target` records the highest-scoring target before the keep gate;
  `selected_target` is null when no trade request wins. Initial-deferred is a
  run-level flag describing year 1, retained in later diagnostics even if a
  subsequent allocation succeeds.
- An engine request can be a nominal `target_change` with transfer <=1e-10;
  `is_trade` and `executed_target_change` remain false and active target stays
  unchanged. The proposal explicitly defines this transfer as a nontrade. This
  numerical corner needs independent review rather than an assumed acceptance.
- `recent_count` and `prior_mass` show the applicable information weights even
  during suspension, but scores are empty then; no fresh trade decision is made.
- The callback supports a caller-supplied review threshold for synthetic tests
  and the specified future personalized follow-up. No personalized competition
  run is authorized. Generic default remains 25 percent.
- `EmpiricalPrior` validates gross factors; it does not certify training-fold
  exclusion. The production loader, four-fold calibration IDs/hashes, output
  schemas, saved-evidence verifier, suitability screen, selection logic, and
  final protocol are still unimplemented. A complete independently reviewed
  driver is required before HY3 gets any policy computation command.

## Evidence and next gates

`tests/test_policy_pilot.py` contains chief-authored synthetic tests, including
rational arithmetic for one initial all-bills-to-thirds trade. Its expected
fee is 1/6 nominal unit, target CE is 26/25, buffered score is 3887/3750,
and actual one-year wealth is 7787/75 in the deterministic zero-inflation toy.
Those are fixture numbers, not competition performance. Timestamped logs and
source hashes are under `audit/chief/policy-kernel/`; failed attempts, if any,
are retained instead of overwritten. No independent acceptance is claimed.

The next separate Sol task must challenge this code with its own numerical oracle
and state/timing fixtures. Release only after SOL-009 is accepted without a
material design change and Sol's real availability probe has passed. If design
changes, preserve this prototype and publish a corrected task/attempt against
new pushed source. A review result cannot certify a future calibration/driver.

Backtesting discipline used the existing `backtesting-frameworks` skill from
wshobson/agents, commit 0874a27b17a22e2b7c2e2bcd725768e0803cad06, already pinned in
ops/skills-lock.json. No skill was installed and no example code was copied.
The original synthetic annual-return/fee/split problem overrides generic trading
suggestions about historical labels, daily annualization or extra trading costs.

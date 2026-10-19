# Final implementation notes after SOL-024

These notes carry requirements I1-I8 from the accepted SOL-024 review at
b1de55ec16f7b67884415637f562fcdf446034c7 into future implementation tasks.
Chief acceptance is audit/chief/SOL-024-review.json. The original final proposal
and its JSON remain unchanged as the exact reviewed sources. This note adds no
policy, threshold, execution permission, freeze record or holdout access.

## Source and output boundaries

New final-capable code must be assigned and independently accepted on generated
inputs. Preserve existing development/synthetic guards. Bind the fixed input
path/hash, all 121..180 scenario and 1..30 period keys, source/module bytes,
parameters and the independently accepted all-development refit. Freeze text
hash equality does not establish those facts. Refit uses all 120 development
scenarios/3600 annual rows before access; no final row fits a prior, enters a
fold or updates another path. The single prior is shared at both fees. Context
still uses only the same path's last min(5,t-1) completed observations.

The final comparison schema must preserve all 100 descriptive contrast rows
and 6000 paired rows, with the frozen primary choice. Final fold IDs, positive
fold support and promotion flags are null with an explicit not-applicable
status. Do not invoke the development selection routine on final statistics.

The personalized root retains ten profile/fee rows. Use these conventions:

| State | Scenario count / denominator | Personalized values and flags | Recommendation |
| --- | --- | --- | --- |
| Development referral; no final simulation | 0 / 0 | Null metrics, exceedance count/fraction, screens and case path | Null class; preserve upstream reason and source |
| Completed frozen rule; both final screens pass | 60 / 60 | All outcomes retained; actual finite metrics and screen flags | Frozen class; frozen_rule_supported_on_final_sample |
| Completed frozen rule; either screen fails | 60 / 60 | All outcomes and failed reasons retained | Null class; final_validation_failed_human_review |
| Invalid/incomplete execution | Not a completed summary | Preserve partial files and explicit failure | No invented referral or result |

Retain historical proposed class separately from the final recommendation. No
replacement class search, tolerance change or bills proxy follows a failure.
Risk is p90 loss <= own tolerance; power is p10 growth >= 0; exceedance counts
strict loss > tolerance. Own horizons remain 5,15,30,25,6. For executed pairs E,
metrics number 60*|E| and ledger/decision rows each number 60*sum(H for E).
All eligible gives 9720 ledger rows and 600 metrics; zero eligible still gives
ten no-run summary rows. These are schema counts, not actual assignments.
Fee-specific classes remain counterfactual suitability choices. Keep generic
same-primary-mode cost robustness separately visible.

## Freeze attestations and corrections

A complete freeze binds prerequisite acceptance commits. Its own audit must be
an external later attestation binding the exact freeze's canonical blob SHA256
and runner SHA256 of UTF-8 Git text with outer whitespace stripped. Do not put
an audit's future commit or the freeze's own hash inside the file it certifies.
Require valid UTF-8; replacement decoding by the existing runner is not a UTF-8
validation check. Internal formatting/order and BOM change the runner digest.

Push accepted source/refit/configurations first, complete freeze next, external
independent freeze review next, then gate opening and immutable final tasks.
A later task base can contain extra ops files while computational files still
match the frozen source. Predeclare disjoint shard membership/coverage, fixed
commands, unique output roots, counts and <=1800-second task limits before access.
Preserve failed staging and check actual file size <=10485760 bytes.

If a genuine software defect requires correction after attempted access, preserve
the original freeze, gate, receipt, partial results and exposure history. A new
reviewed correction record must bind original task/source/freeze hashes, exact
minimal patch/new source hashes, new immutable configuration/task/commands,
affected and unaffected behavior, and changed outcomes/claims. Explicitly
reconcile the new source with the original freeze through that record. Never
claim corrected bytes match old source or that the holdout remains untouched.
Policy parameters remain fixed; a poor policy outcome is not a retry reason.

Severe selection uses greatest exact float drawdown and smallest ID only on an
exact tie. Chronological initial/post_fee/end events and strict updates retain
earliest locations; zero loss retains the initial sentinel. Do not apply the
policy decision epsilon. Show the frozen primary's severe path with baseline
on that same path, separately identifying the baseline's own severe path.

The eventual immutable task must pin this note and actual accepted sources.
No final implementation or final experiment is accepted by this handoff.

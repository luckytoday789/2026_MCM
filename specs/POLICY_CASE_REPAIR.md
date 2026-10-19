# Bounded SOL-023 execution-entry repair

The failed exact delivery ea2569d4624dc86d68861446610ba08548de121f is
preserved, not accepted. Its parent command fails to import safeinvest because
tests/test_policy_cases.py omitted the repository src bootstrap used by other
test modules. The agent's PYTHONPATH setting did not reach the parent runner.

A new immutable task may copy the two exact quarantined blobs into their assigned
source/test paths. Keep policy_cases.py unchanged unless an actual defect is
reproduced and explicitly reported. Add a portable source bootstrap to the test
module before package imports. Do not change the runner, environment, installed
packages, policies, thresholds, prior computation, schemas, accepted core code,
or original failed evidence. Do not accept the old worker completion statement.

Run both prescribed commands in fresh Python 3.12 subprocesses with PYTHONPATH
absent; record command, return code and output. Confirm imported safeinvest
modules resolve to this task checkout, including direct unittest discovery.
Keep the inherited 14 meaningful tests and all generated fixture coverage.
Build a separate task-specific verifier and exclusively created evidence with
explicit base/task/source and delivered hashes, canonical key/type checks,
relative numeric comparisons with zero absolute floor for tiny fees, read-only
--check, and negative numeric/hash corruption rejection. No repairing saved
evidence during --check. Keep findings and limitations accurate. Bind explicit
Git objects without requiring current HEAD to remain a worker branch.

Use audit/chief/case_reference.py and its saved references as an additional
comparison target for 16 cases: five policy modes plus three reference modes at
two fees on four identical six-year generated paths. The chief independently
found all 3310 comparisons passed on the failed source. These tests must stay
synthetic and must not read raw/development/final outcome files. Exact severe
locations follow accepted binary64 comparisons, not epsilon ties or rational
plateau locations. Keep prior negative trials at their original commit.

Use small fresh numerical facts and a minimal scratch corruption per concern;
do not duplicate megabyte audit JSONs unnecessarily. This repair does not
authorize a result writer, production run, personalized policy or final access.

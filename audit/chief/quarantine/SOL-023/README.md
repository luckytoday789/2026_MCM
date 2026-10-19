# Unaccepted SOL-023 draft

Exact source/test blobs from ea2569d4624dc86d68861446610ba08548de121f.
The complete failed delivery, all negative trials and every artifact remain on
work/sol/SOL-023-a1 and in the preserved isolated chief review checkout.
The original parent validation failed: unittest discovery could not import
safeinvest without an unrecorded PYTHONPATH. These files are repair inputs, not
accepted runtime code. See audit/chief/SOL-023-failure-review.json.

Chief reproduced the failure, replayed 14 tests and 1172 scalar/rational checks
with their required import path, and independently checked 3310 comparisons in
16 generated cases. This does not waive the prescribed-command failure.
No competition outcomes were read. A fresh immutable task must fix the entry
point, bind its own evidence, and pass the exact parent commands before review.

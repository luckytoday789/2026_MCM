# K1 numerical correction for the v2 policy kernel

SOL-013 at 1908813ef2627ca6e15591278ec15ccf2f9e9cff approved the corrected v2
design but required a kernel correction. Chief independently reproduced K1 and
accepted the negative review evidence in audit/chief/SOL-013-review.json.
Historical review outputs and failed trials remain unchanged.

For positive finite asset gross factors, the old weighted dot product could
underflow before taking logarithms. In particular, with every gross factor equal
to the smallest positive binary64 value and weights (0.2,0.3,0.5), all three
products round to zero, although the portfolio gross and CE are positive.

Compute the portfolio log gross directly as
logsumexp(log(w_i)+log(g_i)) over strictly positive weights, then use the existing
inverse-cube prior/recent mixture. Zero weights contribute nothing. This changes
floating-point evaluation, not gamma, targets, fees, hurdle, ties, prior strength,
window, review threshold, action semantics or research selection rules. No
clipping, imputation, new support bounds or outcomes were introduced.

Chief synthetic checks cover constant minimum subnormal support for n=0..5,
zero-weight assets, heterogeneous subnormal rational dot products, ordinary
rational accounting, all existing policy tests and calibration tests. These
checks do not replace independent review. Both corrected kernel and calibration
reviews must approve before the corresponding production components run.

The next independent review should close K1 at the new exact source, challenge
minimum subnormal through maximum finite support and zero-weight handling, and
check the ordinary rational/mixture/decision behavior remains consistent. It may
reuse the preserved SOL-013 scalar oracle as independently authored evidence but
must bind new imported code bytes explicitly; never edit old saved verdicts or
claim that replay of old pinned code certifies the correction.

This is a synthetic numerical defect with no competition-outcome run or final
exposure. SOL-013 code_verdict remains changes_required historically; a new
immutable review determines whether the corrected source is approved.

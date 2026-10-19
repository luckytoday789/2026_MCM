# Local chief allowance stop

The user authorized this chief host to continue until its signed-in account's
weekly subscription allowance has 50% remaining, finish the current bounded task,
save/push its work, and stop locally. This is an account allowance, not a token
budget or an estimate from elapsed time. Other uses of that same account can
also change the observed balance.

The opt-in configuration is ignored `.runtime/chief-quota-config.json`; it is
not shared with the other machines. The supervisor calls Codex's documented
read-only `account/rateLimits/read` interface approximately every 60 seconds.
It selects the `codex` quota bucket and the 10,080-minute weekly window.
There are no inference requests, account changes, purchases or reset-credit
redemptions in this inspection. Source:
https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt

When remaining allowance is at or below the configured threshold, the supervisor
creates `.runtime/chief-budget-drain.json`. It asks the active chief turn to
finish its current work. The active process is not killed by the quota guard.
The runner checks the guard before each new chief turn, including recovery turns,
and stops after the current turn exits. It publishes a local-chief stopped status;
it does not change global control, remote task ownership, or other machines.
The separate supervisor honors the same drain and cannot restart the worker.

After all chief processes end, `.runtime/chief-budget-stop.json` records the
actual stop time, latest allowance reading, local changes, unpushed commits and
recovery work plan. Any failed or unfinished outputs remain intact. Check those
records before resuming; do not call unsent work uploaded or partial work finished.
The stop remains latched across process restarts and weekly quota resets. Only a
new explicit user instruction can authorize clearing it. An ordinary watchdog
restart must never clear it.

If allowance cannot be read or its snapshot is older than three minutes, hold
new model work until a verified reading returns. Never infer a balance from
tokens, heartbeat, elapsed time or an expired quota window. Keep the current
task monitored, and retry only the inexpensive read-only metadata request.

The 50% value triggers graceful draining, not a promise of an exact final
balance. Periodic readings, server accounting delay and finishing the current
task can leave the final balance somewhat below 50%. Existing completion,
manual STOP and competition-deadline rules still apply.

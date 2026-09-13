# Durable optimizer recovery

`sera` now writes `ledger.sqlite3` before updating `result.json` and `report.md`.
SQLite is the recovery authority. JSON remains the portable, readable report.
The other package, `sera_loop`, is not involved in this path.

The database contains the run specification, code/software fingerprint, full
checkpoint, unique trial configurations, measurements, quality gates, proposals,
decisions, frontier, and timestamped transitions. Parallel investigator calls
write their request intent before the provider call and their response after it.
An operating-system lock permits only one optimizer owner for a run directory.
SQLite transactions use WAL and `synchronous=FULL`.

## Resume

Inspect first. This is read-only and does not contact the GPU or provider:

```python
import sera

checkpoint = sera.inspect_recovery("sera-runs/my-run")
print(checkpoint["run_hash"])
print(checkpoint["checkpoint"])
```

Use the same installed code, dependencies, model revision, workload, objective,
provider certificate, and versioned evaluator. Supply the run hash you inspected:

```python
with sera.resume(
    output_dir="sera-runs/my-run",
    expected_run_hash=checkpoint["run_hash"],
    agent=agent,
    provider_check="provider-check/result.json",
    evaluation=evaluate_answer,
    evaluation_version="tasks-v1",
    confirm_interrupted=True,
    weave_project="team/project",
) as result:
    result.print_summary()
    print(result.models[0].generate("A fresh request"))
```

`agent` is the same validated provider/model configuration, with the normal
credentials configured outside the report. Quick-mode runs omit the evaluator
arguments. `weave_project` must match the agent's project. Without it, low-level
swarm callers must supply their own scoped `trace_reader` and tracing context.

## Safety contract

- A second owner is refused while the first optimizer or returned runner owns
  the run. SIGKILL releases the OS lock; it does **not** make GPU children safe.
- Resume verifies the saved GPU UUIDs, model, capacity, compute capability,
  driver, low idle memory, and absence of compute processes on those devices.
- Resume never adopts a saved PID, sends it a signal, or kills an unknown owner.
  If a child remains after the optimizer dies, resolve that process ownership
  explicitly before resuming. A busy device is a blocker, not permission to kill.
- `confirm_interrupted=True` is required for a run that was not closed. This
  acknowledgment does not bypass the lock, provenance, or hardware checks.
- Completed trials are reused from the ledger, not measured again. An interrupted
  trial without a complete committed measurement/gate becomes `interrupted` and
  consumes its existing attempt. Its configuration cannot run again in that run.
- An incomplete agent round is marked interrupted. Unexecuted proposals are not
  silently executed on restart. The next round receives the saved measured
  history and regenerates legal proposals.
- Plateau state is preserved. A committed measured round updates progress once;
  interruption before any GPU trial does not count as a no-progress round.
- Restoring the selected runner starts a new owned server in a new artifact
  directory. It is a deployment restore, not a duplicate measurement trial.
- The evaluator's version is checked. The caller is responsible for supplying
  the actual evaluator associated with that version; Python callables are not
  serialized into SQLite.
- Known credential patterns and configured API-key values are refused before
  persistence. Environment variables are never copied into the ledger.

## Weave after restart

The traced path creates a new `sera_resume` root. It records the source checkpoint,
prior trace URL when available, and recovery identity. `restore_saved_trial_evidence`
imports committed model outputs, request metrics, and diagnoses into this new
root. These are explicitly historical exports, not fresh inference. Each imported
trial carries its source-record hash in the recovery report. Investigators can
then query the same bounded Weave reader for both imported history and new trials.
New agent calls and model measurements are traced normally. A failed import
blocks resumed experimentation; it does not replace missing traces with invented data.

## Verified and excluded

Offline tests kill a separate Python process with SIGKILL at candidate intent,
completed measurement, and completed round checkpoints. Each restart skips the
baseline and attempted candidate, continues the search, and returns a fake but
usable runner. Other tests cover damaged JSON mirrors, SQLite checksum failures,
concurrent ownership, changed provenance, busy/changed GPUs, credentials, and
traced history import. These tests are **not** a live GPU outage-recovery claim.

Resume requires a committed measured baseline and initialized investigation state.
It covers the autonomous single-model path, including a promoted fit-first
reference and explicit portable hardware assignments. It does not restart a
partly downloaded initial baseline, the fixed-candidate first milestone, a
two-model placement job, or a legacy JSON-only run. Those cases fail closed.

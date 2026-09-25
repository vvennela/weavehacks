# Dataflow-informed specialist board

Status: prepared; no measurements yet.

Continue the approved classical/one-level Strassen search with unchanged full512 NN
baseline8bb0113e377808a841819354296fa0ef02ff49e4188d57a091afc6463fc0ca18.
Preparation source and correctness records are reused from the preceding Strassen
phase; they are not new measurements. This block collects fresh baseline scores and
paired controls. The copied numerical worker is unchanged and still requires48
standard plus four cancellation/scale cases for every submitted source.

The next15-Luna board receives the previous phase outcomes, reversible exact displays
of all three measured source changes, compiler output for both Strassen wrappers,
and Luna's inventory/dataflow/codegen reviews. These inputs correct known aliases and
unsupported vectorization claims; they do not mandate an experiment or restrict the
board to an exhaustive option list. Astra selects15roles, implements their ranked
queue, and reviews evidence. Only Codex agents through ChatGPT login are used.

Same limits: six implementation attempts,108 model calls,180seconds per call,
1800seconds per block, ten validations and ten alternating paired controls per
candidate, min(candidate)>1.05*max(control), then held-out confirmation. No change to
the hill, tolerance.002, power settings, FP32 rule, single thread or timed costs.
Both saved historical peaks and fresh same-mode peaks remain reported separately;
the legacy1800 flag does not define the current ten-run goal.

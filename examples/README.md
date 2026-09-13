# Save and run these examples

For Molab, **clone [FAST_START](../notebooks/FAST_START.py) into your
own workspace first**. Select the RTX PRO 6000 GPU, enter your keys and Weave
team/project, then Shift+Enter on either workflow cell. The notebook installs its
pinned dependencies and downloads missing model files. Each workflow saves its
own 8× and 16× HTML replays plus a task for an ARIA browser agent. The plain Python
scripts below still require a prepared Linux GPU runtime with vLLM 0.26.0.
Installing the Python library does not create a GPU or install its driver.

Weave is used by the live loop. ARIA is a separate review through your signed-in
W&B UI, either manually or with a browser-capable agent; it is not a callable
investigator in this package. Run in your own Molab account and use a W&B team
project where ARIA is enabled. Do not claim that generating the task runs ARIA.

```python
from sera.demo import aria_agent_task
print(aria_agent_task(y))  # Give this task to your browser-capable agent after the run.
```

## Download Sera

Source: <https://github.com/vvennela/weavehacks>.

```sh
git clone https://github.com/vvennela/weavehacks.git
cd weavehacks
python -m pip install ".[swarm,litellm]"
```

Or install just the library directly from GitHub:

```sh
python -m pip install "sera-inference[swarm,litellm] @ git+https://github.com/vvennela/weavehacks.git"
```

The distribution is `sera-inference`; the Python import is `import sera`.
Do not run `pip install sera`: that name does not identify this repository.
These commands install the current GitHub source, not a claimed PyPI release.
For reproducible environments, append `@<tested-commit>` to the Git URL.

## Three separate Python files

| File | What it does |
| --- | --- |
| [latency.py](latency.py) | Searches for faster responses, tests a returned runner, and saves its replay. |
| [latency_then_throughput.py](latency_then_throughput.py) | Optimizes latency, then throughput, keeping the earlier latency result within `k=3%`. |
| [replay_saved_run.py](replay_saved_run.py) | Builds an offline replay from your saved result. No GPU or API calls. |

Run one live example at a time on the prepared GPU:

```sh
python examples/latency.py
# Or:
python examples/latency_then_throughput.py
```

**Add your keys here:** the scripts ask for `OPENAI_API_KEY` and `WANDB_API_KEY`
using hidden prompts, unless already supplied by the runtime. They also ask for
your Weave `entity/project`. Keys are not saved in the example files. A supplied
`SERA_PROVIDER_CHECK` path reuses a certificate only after verifying it matches
the provider; otherwise setup performs a fresh provider check.

Each live run saves its own directory, checks quality, and closes its runner.
`demo.html` is saved inside that run directory. Keep application requests inside
the `with` block while the runner is open.

To visualize an existing saved run instead:

```sh
python examples/replay_saved_run.py /path/to/your/result.json --output my-demo.html
```

The supplied Qwen72B examples use a known-working FP8-weight/BF16-cache reference,
eight easy strict-JSON tasks, and concurrency 1/2/4/8. `prepare_demo()` exposes
these as ordinary keyword arguments; replace the prompts and versioned evaluator
for your own task. The library still supports only its declared models/hardware.

## The short API

After setup returns `config`:

```python
with sera.optimize(**config, stages=["latency", "throughput"], k=3.0,
                   min_improvement_pct=5.0) as y:
    y.print_summary()
    if y.models:
        print(y.models[0].generate(config["prompts"][0]).text)

sera.visualize(y)                  # Display in Molab or Jupyter.
sera.visualize(y).save("demo.html") # Or save the replay.
```

`k=3` limits how much a later stage can worsen an earlier result. It does not mean
a required 3% gain. `min_improvement_pct=5` is the separate progress target.
Quality remains a hard gate. Stages can preserve the baseline when no candidate
passes; there is no guarantee of a speedup or a globally optimal configuration.

The single-stage latency path has a recorded live pass. Ordered throughput
stages have automated pipeline tests; a live staged performance gain has not yet
been measured. Each stage starts and measures its baseline again, so a sequence
costs more time than a single run.

**Cost:** replaying saved results makes no GPU or model-provider calls. Live
optimization uses your GPU and investigator account; provider and hosting charges
can apply. Do not pitch those external resources as free inference.

# Interactive demo rehearsal: passed

The actual `python -m experiments.run_fit_demo --interactive` command ran from a clean repository clone at `0b1efab884932ed4ce7e1d3fc086e6243e17a477`, using the supplied Molab GPU and the existing environment key. No credentials are in the command or saved files.

- The model loaded, all eight unchanged strict-JSON tasks passed, and the automatic returned-runner probe passed.
- The corrected agent review passed during this real run. No separate review repair was needed.
- The process stayed alive at `Prompt:` after returning the runner.
- A new prompt asked: `What is 7 + 8? Return only a JSON object with one key named answer and an integer value.`
- Interactive output was `{"answer": 15}`. This was not part of the eight-task acceptance score.
- Blank input stopped the loop. Process exit was zero; GPU cleanup passed and memory returned to 0 MiB.

Startup with downloaded weights took 60.06 seconds. The 24 timed requests had p95 573.20 ms and output throughput 13.67 tokens/s. This rehearses the existing deployment; it does not establish a speedup or search advantage. The structured result contains raw acceptance requests, the automatic fresh probe, the agent responses, the trace link, and runtime provenance. The interactive transcript is saved separately as `console.log`.

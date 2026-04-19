# Architecture

`solr-metal` is a hybrid runner:

- Python core runtime
- YAML registry
- Optional Python helper checks

It deliberately keeps shallow trust checks ahead of deeper synthetic workload probes.

## Major Layers

- `cli.py`: Typer command tree and operator UX
- `registry.py`: builtin and YAML catalog loading
- `engine.py`: dispatch, retries, timeouts, artifact capture
- `builtins.py`: Kubernetes and OpenShift checks using official clients
- `reports.py`: terminal rendering and persisted report bundle generation

## Result Model

Every test ends as one of:

- `PASS`
- `FAIL`
- `ERROR`
- `SKIP`
- `TIMEOUT`

## Extension Model

- Builtin checks for reusable, API-first logic
- YAML command checks for simple probes
- Python helper checks for custom logic without bloating the core

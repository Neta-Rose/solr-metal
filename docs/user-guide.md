# User Guide

## Typical Commands

```text
sm version
sm version --check
sm doctor
sm list tests
sm list suites
sm config show
sm run smoke
sm run --test kubernetes.nodes.ready
sm report --run ./runs/<timestamp>
```

## Result Semantics

- `PASS`: the check completed and the cluster satisfied it
- `FAIL`: the check completed honestly and the cluster did not satisfy it
- `ERROR`: the check could not be evaluated honestly
- `SKIP`: the check was intentionally deferred or unsupported
- `TIMEOUT`: the check exceeded its configured execution window

## Reports

Each run writes a bundle under `runs/` with machine-readable and human-readable outputs.

## Configuration Precedence

`solr-metal` resolves configuration in this order:

1. CLI flags
2. Environment variables prefixed with `SM_`
3. Config files
4. Built-in defaults

Supported config files:

- site config: `<platform config dir>/solr-metal/config.toml`
- user config: `<user config dir>/solr-metal/config.toml`
- local config: `.solr-metal.toml`
- explicit config: `sm --config path/to/config.toml ...`

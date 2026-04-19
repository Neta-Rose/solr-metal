# User Guide

## Typical Commands

```text
sm doctor
sm list tests
sm list suites
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

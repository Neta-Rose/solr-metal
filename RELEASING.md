# Releasing solr-metal

## Mental Model

This repository is a release system with a CLI attached.

The release process is built around the wheel and sdist artifacts, not around running the code from the checkout.

## Versioning

- The authoritative version lives in `project.version` in `pyproject.toml`.
- The CLI reads the installed package version from package metadata.
- Release tags must match the package version exactly, for example `v0.1.0`.

## Release Flow

1. Update `project.version` in `pyproject.toml`.
2. Update changelog or release notes as needed.
3. Merge to `main`.
4. Create and push a matching git tag such as `v0.1.0`.
5. GitHub Actions:
   - installs the project with locked dependencies
   - runs linting and tests
   - builds wheel and sdist
   - installs the built wheel in a fresh virtual environment
   - verifies the wheel entrypoint and packaged resources
   - creates the GitHub release
   - publishes to PyPI using trusted publishing when `PUBLISH_TO_PYPI=true`
   - optionally uploads to an internal package index

## Publishing Security

- Prefer PyPI trusted publishing through GitHub OIDC.
- For internal registries, prefer short-lived registry-issued tokens over long-lived static secrets.
- Publishing credentials should be owned by CI, not local developer machines.

## Air-Gapped Release Pattern

1. Build the wheel and sdist in CI.
2. Export all required wheels into a wheelhouse.
3. Move the wheelhouse and `solr-metal` wheel into the target environment.
4. Install with `pip --no-index --find-links`.

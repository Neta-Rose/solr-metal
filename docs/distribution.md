# Distribution

`solr-metal` is designed for multiple delivery backends without changing the artifact itself.

## Public Distribution

- Upload the built wheel and sdist to PyPI.
- Upgrade checks can use the PyPI JSON API.

## Private Distribution

- Upload the same built wheel and sdist to an internal package index.
- Configure upgrade checks to use either:
  - a PEP 691 simple API endpoint
  - a custom static JSON endpoint

Relevant settings:

- `version_source_type`
- `version_source_url`
- `version_source_package`

## Air-Gapped Distribution

Build outside the isolated network:

```powershell
uv build
python -m pip wheel --wheel-dir wheelhouse .
```

Install inside the isolated network:

```powershell
python -m pip install --no-index --find-links wheelhouse solr-metal
```

The core runtime does not assume internet access. Network access is only needed if the operator explicitly requests a version check against a remote source.

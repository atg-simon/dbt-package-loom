# dbt-package-loom

A drop-in replacement for [dbt-loom](https://github.com/nicholasyager/dbt-loom) that works with dbt Core 2.0 (Fusion).

Reads your existing `dbt_loom.config.yml`, fetches each upstream project's `manifest.json`, and injects a package of ephemeral stub models directly into `dbt_packages/`. Cross-project `ref()` resolves exactly as it did under dbt-loom — no plugin hooks, no dbt Core dependency.

## Why

dbt-loom works by hooking into dbt Core's Python plugin API at parse time. dbt Core v2.0 (Fusion) is a ground-up Rust rewrite — the hook mechanism is gone and the dbt-loom maintainer has confirmed Fusion support is out of scope.

This tool sidesteps the problem: it runs _before_ `dbt run` and writes stub packages that dbt treats as regular installed packages.

## Migration from dbt-loom

```yaml
# Before
- run: pip install dbt-loom
- run: dbt run

# After
- run: pip install dbt-package-loom
- run: dbt-package-loom inject
- run: dbt run
```

- `dbt_loom.config.yml` is unchanged
- Remove `dbt-loom` from your dependencies
- Remove any `dependencies.yml` `projects:` entries for upstream projects — no `packages.yml` entry is needed either

## Installation

**Developer machine** (uv tool — isolated environment):
```bash
uv tool install "dbt-package-loom @ git+https://github.com/atg-simon/dbt-package-loom.git"
```

**CI / container where dbt is already installed** (install into the same environment as dbt):
```bash
pip install "dbt-package-loom @ git+https://github.com/atg-simon/dbt-package-loom.git"
```

> **Note:** If you use `uv tool install` in an environment where `PYTHONPATH` includes dbt's site-packages (common in dbt Docker images), the tool will pick up dbt's pydantic build and fail with a `pydantic_core` import error. Either install via `pip` into the dbt environment, or clear `PYTHONPATH` before invoking: `PYTHONPATH= dbt-package-loom inject`.

## Usage

```
dbt-package-loom inject [--config PATH]
```

`--config` defaults to `dbt_loom.config.yml` in the current directory. Output is always written to `dbt_packages/<project_name>/`.

## Config format

Unchanged from dbt-loom:

```yaml
manifests:
  - name: jaffle_finance
    type: file
    config:
      path: ./target/manifest.json

  - name: jaffle_marketing
    type: dbt_cloud
    config:
      account_id: 12345
      job_id: 67890
```

## Supported manifest sources

| Type | Notes |
|---|---|
| `file` | Local path or `http(s)://` URL; gzip-aware |
| `dbt_cloud` | Fetches latest successful run artifact via dbt Cloud Admin API v2. Requires `DBT_CLOUD_API_TOKEN`. |
| `paradime` | Fetches latest BOLT run manifest. Requires `paradime-io` extra and credentials. |
| `s3` / `gcs` / `azure` | Deferred — not yet implemented |

### dbt Cloud

```yaml
- name: jaffle_finance
  type: dbt_cloud
  config:
    account_id: 12345
    job_id: 67890
    api_endpoint: https://cloud.getdbt.com/api/v2  # optional
    step: 1                                         # optional
```

Token is read from `DBT_CLOUD_API_TOKEN` — not stored in config.

### Paradime

```yaml
- name: jaffle_finance
  type: paradime
  config:
    schedule_name: jaffle_finance_production
```

Install the extra: `pip install dbt-package-loom[paradime]`

Credentials fall back to `PARADIME_API_KEY`, `PARADIME_API_SECRET`, `PARADIME_API_ENDPOINT`.

## What gets generated

```
dbt_packages/
└── jaffle_finance/
    ├── dbt_project.yml          # materialized: ephemeral, tag: package-mesh-stub
    └── models/
        └── integrated/
            ├── sources.yml
            ├── schema.yml
            ├── fct_booking.sql      # unversioned alias → latest version
            ├── fct_booking_v1.sql
            └── fct_booking_v2.sql
```

Only `access: public` models from the upstream project are included. Folder structure mirrors the upstream project's `models/` layout.

## gitignore

Add `dbt_packages/` to `.gitignore`. Running `dbt deps` after inject will not overwrite the mesh stubs — no `packages.yml` entry exists for them, so `dbt deps` ignores them.

## Development

```bash
uv sync --dev
uv run pytest
uvx ty check .
```

## Attribution

Manifest loading adapted from [nicholasyager/dbt-loom](https://github.com/nicholasyager/dbt-loom) under Apache 2.0.

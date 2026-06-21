# dbt-package-loom — Specification v1

## Overview

`dbt-package-loom` is a CLI tool that reads an existing `dbt_loom.config.yml`, fetches each upstream project's compiled `manifest.json`, and injects a dbt package of ephemeral stub models directly into `dbt_packages/`. It is a drop-in replacement for dbt-loom that works with dbt Core 2.0 (Fusion).

### Problem

- dbt Mesh cross-project `ref()` is an Enterprise Cloud-only feature — unavailable in dbt Core
- dbt-loom replicates this via a Python plugin hook against dbt Core's manifest API
- dbt Core v2.0 (Fusion) is a ground-up Rust rewrite — the Python hook mechanism is broken and the dbt-loom maintainer has confirmed they will not support Fusion
- ATG uses cross-project refs in production today; a path forward is required that works with dbt Core 2.0

### Solution

Before each `dbt run`, execute `dbt-package-loom inject`. The tool:

1. Reads `dbt_loom.config.yml` (the existing dbt-loom config — no new file required)
2. For each entry in `manifests:`, fetches the upstream `manifest.json` via the configured source type
3. Filters to `access: public` models
4. Writes a dbt package of ephemeral stub models directly into `dbt_packages/<project_name>/`

From dbt's perspective the stub is an installed package. `{{ ref('jaffle_finance', 'fct_booking') }}` resolves exactly as it did under dbt-loom. No `packages.yml` entry is required for mesh projects.

---

## Migration from dbt-loom

```yaml
# Before
- run: pip install dbt-loom
- run: dbt run          # dbt-loom hooks in at parse time via Python plugin API

# After
- run: pip install dbt-package-loom
- run: dbt-package-loom inject   # populates dbt_packages/ pre-run
- run: dbt run
```

`dbt_loom.config.yml` is unchanged. Remove `dbt-loom` from your dependencies. Remove any `dependencies.yml` `projects:` entries for the upstream projects — no replacement entry in `packages.yml` is needed.

---

## CLI

```
dbt-package-loom inject [OPTIONS]

Options:
  --config PATH     Path to dbt-loom config file [default: dbt_loom.config.yml]
```

The tool reads `dbt_loom.config.yml` by convention. `--config` is available for non-standard paths (e.g. CI environments where the working directory differs from the project root).

No `--out` flag. Output is always `dbt_packages/<project_name>/` relative to the working directory, matching where `dbt deps` would install a package of the same name.

---

## Config File Format

`dbt-package-loom inject` reads the existing dbt-loom config format without modification:

```yaml
manifests:
  - name: jaffle_finance
    type: file
    config:
      path: ./target/manifest.json

  - name: jaffle_marketing
    type: s3
    config:
      bucket: atg-dbt-manifests
      key: jaffle_marketing/prod/manifest.json
      region: eu-west-1
```

Multiple upstream projects are handled in a single invocation — one `dbt_packages/<name>/` directory written per entry.



---

## Generated Package Structure

Written to `dbt_packages/<project_name>/`:

```
dbt_packages/
└── jaffle_finance/
    ├── dbt_project.yml
    └── models/
        ├── conformed/
        │   ├── sources.yml
        │   ├── schema.yml
        │   └── dim_customer.sql
        └── integrated/
            ├── sources.yml
            ├── schema.yml
            ├── fct_booking_v1.sql
            └── fct_booking_v2.sql
```

No unversioned alias stub is generated. `ref('jaffle_finance', 'fct_booking')` (without a version suffix) is handled by dbt natively via the `latest_version` field in `schema.yml`.

Folder structure mirrors the upstream project's `models/` layout exactly, derived from `node["path"]` in the manifest.

---

## Generated `dbt_project.yml`

```yaml
name: <upstream_project_name>
version: '1.0.0'
config-version: 2

models:
  <upstream_project_name>:
    +materialized: ephemeral
    +schema: <upstream_project_name>
    +tags:
      - package-mesh-stub
```

`+schema: <upstream_project_name>` gives each stub package a unique schema namespace (e.g. `dbt_sperry_atg_source`). Without this, two upstream packages that both expose a model with the same name would share a computed database representation and dbt would refuse to compile, even though both stubs are ephemeral and never materialise.

---

## Generated `sources.yml` (one per folder)

Source `name` is the upstream project name. Database and schema are resolved directly from the manifest.

Table naming rules:

| Model kind | Table `name` | Table `identifier` |
|---|---|---|
| Unversioned | `node.name` (model name) | `node.alias` if set, else `node.name` |
| Versioned | `node.file_stem` (path stem, e.g. `fct_booking_v2`) | `node.alias` if set, else `node.name` |

Using the path stem for versioned tables ensures uniqueness when two models share the same alias but live in different folders (e.g. two models both aliased to `ent_order_item_v3` but with different path stems). Descriptions are not copied.

```yaml
version: 2

sources:
  - name: jaffle_finance
    database: jaffle_finance_prod
    schema: integrated
    tables:
      - name: fct_booking_v1
        identifier: fct_booking_v1
      - name: fct_booking_v2
        identifier: fct_booking_v2
```

The package is environment-specific by design. To target a different environment, re-run `inject` against that environment's `manifest.json`.

---

## Generated Stub SQL

### Unversioned model

Source table name is `node.name`:

```sql
-- Generated by dbt-package-loom. Do not edit.
select * from {{ source('jaffle_finance', 'fct_booking') }}
```

### Versioned models

One stub per version. Source table name is `node.file_stem` (the path stem), matching the table name in `sources.yml`:

```sql
-- Generated by dbt-package-loom. Do not edit.
select * from {{ source('jaffle_finance', 'fct_booking_v1') }}
```

No unversioned alias stub is emitted. `ref('jaffle_finance', 'fct_booking')` (no version pin) is resolved by dbt using the `latest_version` declared in `schema.yml`.

---

## Generated `schema.yml` (one per folder)

Versioned models use dbt's native `versions:` block with `defined_in` and `latest_version`:

```yaml
version: 2

models:
  - name: fct_booking
    latest_version: 2
    versions:
      - v: 1
        defined_in: fct_booking_v1
      - v: 2
        defined_in: fct_booking_v2
```

`defined_in` uses `node.file_stem` (the path stem), matching the SQL filename. Descriptions are not copied. `latest_version` is taken from the manifest node's `latest_version` field, falling back to the highest version number present. This ensures both `ref('jaffle_finance', 'fct_booking', v=1)` and the unversioned `ref('jaffle_finance', 'fct_booking')` resolve correctly.

---

## Generator Behaviour

1. Parse `dbt_loom.config.yml`
2. For each entry in `manifests:`:
   a. Instantiate the configured source type and call `.load()` to get parsed manifest dict
   b. Filter nodes: `resource_type == "model"` AND `access == "public"` AND `package_name == <name>`
   c. Group nodes by output folder (derived from `node["path"]`, filename stripped)
   e. For each folder: emit `sources.yml`, `schema.yml`, and stub SQL files
   f. Emit `dbt_project.yml`
   g. Write all files to `dbt_packages/<name>/`, overwriting any existing contents

---

## Manifest Sources

Source loading is adapted directly from dbt-loom, copied with Apache 2.0 attribution. dbt-loom is not taken as a Python dependency — this avoids inheriting its transitive `dbt-core` dependency, which conflicts on dbt Core 2.0 environments.

### Upstream source reference

All adapted code originates from [`nicholasyager/dbt-loom @ main/dbt_loom`](https://github.com/nicholasyager/dbt-loom/tree/main/dbt_loom). The specific files:

| dbt-loom file | Adapted into | Notes |
|---|---|---|
| [`dbt_loom/config.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/config.py) | `dbt_package_loom/config.py` | `dbtLoomConfig`, `ManifestReference`, `ManifestReferenceType`, `FileReferenceConfig`, `_TYPE_TO_CONFIG` — stripped to `file`, `dbt_cloud`, `paradime` only |
| [`dbt_loom/manifests.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/manifests.py) | `dbt_package_loom/manifests.py` | `ManifestNode`, `ManifestLoader` — loader stripped to `file`, `dbt_cloud`, `paradime`; `NodeType` import removed (no dbt-core dependency) |
| [`dbt_loom/clients/__init__.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/clients/__init__.py) | `dbt_package_loom/clients/__init__.py` | `is_gzipped()` helper only |
| [`dbt_loom/clients/dbt_cloud.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/clients/dbt_cloud.py) | `dbt_package_loom/clients/dbt_cloud.py` | `DbtCloud`, `DbtCloudReferenceConfig` — `fire_event` replaced with stdlib `logging` |
| [`dbt_loom/clients/paradime.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/clients/paradime.py) | `dbt_package_loom/clients/paradime.py` | `ParadimeClient`, `ParadimeReferenceConfig` — `fire_event` replaced with stdlib `logging` |

Each adapted file must carry the original Apache 2.0 copyright header from dbt-loom.

### Supported Source Types (v1)

| Type | Status | Notes |
|---|---|---|
| `file` | Implemented | Local path or http(s) URL; gzip-aware |
| `dbt_cloud` | Implemented | Fetches latest successful run artifact via dbt Cloud Admin API v2 |
| `paradime` | Implemented | Fetches latest BOLT run manifest via `paradime-io` SDK |
| `s3` | Not implemented | Deferred — copy from dbt-loom when needed |
| `gcs` | Not implemented | Deferred — copy from dbt-loom when needed |
| `azure` | Not implemented | Deferred — copy from dbt-loom when needed |
| `snowflake` | Not implemented | Deferred — copy from dbt-loom when needed |
| `databricks` | Not implemented | Deferred — copy from dbt-loom when needed |

### Config shapes

#### `file`

```yaml
- name: jaffle_finance
  type: file
  config:
    path: ./target/manifest.json   # local path or http(s) URL; gzip supported
```

The `path` validator in dbt-loom normalises bare paths to `file://` URIs. Local and http(s) paths are both handled by `FileReferenceConfig`. Gzip detection uses magic bytes (`\x1f\x8b`).

#### `dbt_cloud`

```yaml
- name: jaffle_finance
  type: dbt_cloud
  config:
    account_id: 12345
    job_id: 67890
    api_endpoint: https://cloud.getdbt.com/api/v2   # optional, this is the default
    step: 1                                          # optional, defaults to last step
```

Token is read from `DBT_CLOUD_API_TOKEN` environment variable — not stored in config. The client calls `GET /accounts/{account_id}/runs/?job_definition_id={job_id}&status=10&order_by=-finished_at&limit=1` to find the latest successful run, then `GET /accounts/{account_id}/runs/{run_id}/artifacts/manifest.json`.

#### `paradime`

```yaml
- name: jaffle_finance
  type: paradime
  config:
    schedule_name: jaffle_finance_production
    api_endpoint: https://api.paradime.io   # optional, falls back to PARADIME_API_ENDPOINT
    api_key: ...                             # optional, falls back to PARADIME_API_KEY
    api_secret: ...                          # optional, falls back to PARADIME_API_SECRET
    command_index: 0                         # optional, index of dbt command in the schedule
```

Credentials fall back to `PARADIME_API_KEY`, `PARADIME_API_SECRET`, `PARADIME_API_ENDPOINT` environment variables. All three are required. Uses the `paradime-io` Python SDK: `Paradime.bolt.get_latest_manifest_json(schedule_name, command_index)`. The `paradime-io` SDK is an optional pip extra — not included in the base install.

### Config model (adapted from dbt-loom `config.py`)

`dbt_loom.config.yml` is parsed using the same Pydantic models as dbt-loom:

- `dbtLoomConfig` — top-level, `manifests: List[ManifestReference]`
- `ManifestReference` — `name`, `type`, `config`, optional `excluded_packages`, `included_packages`, `optional`. When `optional: true`, a load or generation failure logs a warning and continues; the exit code is still 0. Non-optional failures print an error and exit 1.
- `ManifestReferenceType` — enum: `file | dbt_cloud | paradime | s3 | gcs | azure | snowflake | databricks`
- Config type is resolved explicitly via `_TYPE_TO_CONFIG` dict keyed on `ManifestReferenceType` — avoids Pydantic Union ambiguity between types that share field names (e.g. `path`)

`enable_telemetry` from `dbtLoomConfig` is parsed but ignored.

### `ManifestNode` model (adapted from dbt-loom `manifests.py`)

Fields used by the generator:

| Field | Source in manifest | Notes |
|---|---|---|
| `name` | `node.name` | Model name |
| `package_name` | `node.package_name` | Used to filter to upstream project |
| `unique_id` | `node.unique_id` | |
| `resource_type` | `node.resource_type` | Filter to `model` |
| `schema_name` | `node.schema` | Physical schema |
| `database` | `node.database` | Physical database |
| `relation_name` | `node.relation_name` | Used to derive `identifier` — strips quotes via `[\"\`\[\]]` pattern |
| `version` | `node.version` | Version number for versioned models |
| `latest_version` | `node.latest_version` | Declared latest version |
| `access` | `node.access` | Filter to `public` |
| `path` | `node.path` | Relative path within the upstream project's `models/` dir; used to derive folder, filename stem (`file_stem`), and `defined_in` |
| `alias` | `node.alias` | Physical table/view name; used as `identifier` in `sources.yml` (falls back to `name` if absent) |

`file_stem` is a computed property: `PurePosixPath(node.path).stem`. For unversioned models this equals the model name; for versioned models it includes the version suffix (e.g. `fct_booking_v2`). It is always unique within a package, unlike `alias`.

The `identifier` property on `ManifestNode` strips SQL quote characters from the last segment of `relation_name`. If `relation_name` is absent, falls back to `name`.

### `pyproject.toml` extras

```toml
[project]
name = "dbt-package-loom"
dependencies = [
    "click>=8.0",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "requests>=2.28",
]

[project.optional-dependencies]
dbt-cloud  = []                          # no extra deps — uses requests only
paradime   = ["paradime-io"]
# s3/gcs/azure extras deferred — add when source types are implemented

[project.scripts]
dbt-package-loom = "dbt_package_loom.cli:cli"
```


---

## Python Package Structure

```
dbt_package_loom/
├── __init__.py
├── cli.py                  # Click entrypoint: `dbt-package-loom inject`
├── config.py               # dbtLoomConfig, ManifestReference, ManifestReferenceType
│                           #   — adapted from dbt_loom/config.py
├── clients/
│   ├── __init__.py         # is_gzipped() — adapted from dbt_loom/clients/__init__.py
│   ├── dbt_cloud.py        # DbtCloud, DbtCloudReferenceConfig — adapted from dbt-loom
│   └── paradime.py         # ParadimeClient, ParadimeReferenceConfig — adapted from dbt-loom
├── manifests.py            # ManifestNode, ManifestLoader — adapted from dbt_loom/manifests.py
│                           #   loader stripped to file/dbt_cloud/paradime only
├── generator.py            # Core generation logic
└── writers.py              # File emission (SQL, YAML) into dbt_packages/
```

No `dbt-core` dependency. No `dbt-loom` dependency.

---

## Contributing Back to dbt-loom

`dbt-package-loom` solves a distinct problem (package injection) rather than extending dbt-loom's plugin architecture, so it is a standalone tool rather than a PR to dbt-loom. However, parts of this work may be worth contributing back:

### What could go upstream

**Injection mode as a dbt-loom feature**
The core idea — injecting into `dbt_packages/` directly rather than hooking into dbt Core's plugin API — is a viable alternative execution mode for dbt-loom that would make it Fusion-compatible. This could be proposed as an issue or PR to dbt-loom once the approach is proven. The PR surface would be: a new `dbt-loom inject` subcommand that runs the same manifest loading pipeline but writes to `dbt_packages/` instead of registering nodes at parse time.

**`paradime` source type improvements**
If bugs or config gaps are found in `ParadimeClient` during the Paradime trial (e.g. `command_index` behaviour, API endpoint handling), fixes should be contributed back to [`dbt_loom/clients/paradime.py`](https://github.com/nicholasyager/dbt-loom/blob/main/dbt_loom/clients/paradime.py) directly.

**Additional source types**
If `s3`, `gcs`, or other source types are implemented in `dbt-package-loom`, the implementations will be near-identical to dbt-loom's. There is no value in maintaining a separate copy — contribute them to dbt-loom and copy back (or consider a shared utility library, but that reintroduces the dependency problem).

### How to contribute

dbt-loom is maintained by [@nicholasyager](https://github.com/nicholasyager). The repo is at [`nicholasyager/dbt-loom`](https://github.com/nicholasyager/dbt-loom). Contributions via standard GitHub fork + PR. The project has an active issue tracker — check for existing issues before opening new ones, particularly around Fusion compatibility ([issue #180](https://github.com/nicholasyager/dbt-loom/issues/180) is the relevant thread).

### What stays in dbt-package-loom

The stub generation logic (`generator.py`, `writers.py`) is specific to this tool and has no place in dbt-loom. The injection approach as a whole may eventually be proposed upstream, but the YAML/SQL generation for ephemeral stub packages is out of dbt-loom's scope.

---



- Exposure, snapshot, and seed stubs
- Incremental or table materializations (all stubs are ephemeral)
- `s3`, `gcs`, `azure`, `snowflake`, `databricks` manifest sources (deferred — copy from dbt-loom when needed)
- Column-level metadata / contracts propagation
- Manifest schema version validation (minimum supported: v10 / dbt Core 1.5+)
- `excluded_packages` / `included_packages` filtering from `ManifestReference` (fields parsed, behaviour deferred)

---

## Open Issues

1. **Manifest schema version:** Tool should validate schema version at load time and emit a clear error if unsupported. Deferred to v1.1.
2. **`dbt_packages/` gitignore:** Conventionally gitignored. Teams running bare `dbt deps` after inject will not overwrite the mesh stubs (no `packages.yml` entry exists for them). This should be explicitly documented in the README.
3. **Paradime `command_index`:** `get_latest_manifest_json` accepts an optional `command_index` to select which dbt command in a multi-command BOLT schedule produced the manifest. Default (None) returns the manifest from the last command. Confirm correct index with Paradime during trial.

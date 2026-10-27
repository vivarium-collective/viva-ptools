# pbg-ptools

A **vivarium-workbench analysis-viewer plugin** (distribution `pbg-ptools`, import
`pbg_ptools`; repo `viva-ptools`) that contributes the **Pathway Tools (EcoCyc)
Omics Viewer** launcher to a workbench workspace's Analyses page.

## What it does

The workbench discovers a `<pkg>.workbench_viewers.get_viewers(ws_root)` entry on
the workspace package and on **every installed `pbg-*` distribution**. `pbg-ptools`
is found via that `pbg-*` scan — so it activates purely by being installed in the
workbench's environment, independent of which workspace is served.

The viewer overlays a study's exported PTools TSVs onto the E. coli metabolic map
in a Pathway Tools "Cellular Overview" Omics Viewer. It is **dormant** unless the
served workspace (or a deployment config) sets `ui.ptools_server_url`.

## Producer / viewer split

This package is only the **viewer** (read-only: it globs `**/ptools/*.tsv` and
builds an Omics-Viewer URL). The **producers** that write those TSVs live with the
science repo (e.g. `v2ecoli/workflow/analyses/ptools_*.py`), because they are bound
to that model's simulation data. The two sides couple **only through the on-disk
`**/ptools/*.tsv` file contract** — never a Python import — so they version
independently.

## Dependency direction

```
pbg-ptools ──depends on──▶ vivarium-workbench      (leaf → host; correct)
```

The workbench never depends back on `pbg-ptools`; it discovers it at runtime. This
package imports the workbench's canonical path resolvers
(`lib.study_spec.study_dir`, `lib.workspace_paths.WorkspacePaths`) directly, and,
when available (vivarium-workbench >= 0.3.56), resolves `ui:` through the
workbench's deployment-config layer so a site can supply its own `ptools_server_url`
without rewriting the workspace's `workspace.yaml`.

## Configuration (`workspace.yaml`)

```yaml
ui:
  ptools_server_url: https://ptools.example.org   # REQUIRED — enables the viewer
  ptools_orgid: ECOLI                              # optional (default ECOLI)
  ptools_omics_url_template: "..."                 # optional URL template override
  ptools_data_dir: /srv/data                       # optional — serve TSVs from disk
  dashboard_public_base_url: https://dash.example  # optional — overrides request host
```

## Contents / public API

`pbg_ptools.workbench_viewers`:

- `get_viewers(ws_root) -> list` — the plugin entry point. Returns the single
  `pathway-tools` launcher card (id, title, `applies`/`launch`/`targets`
  callbacks) that the workbench renders on the Analyses page.
- `build_ptools_launch_url(study_dir, ws_root, ptools_server_url,
  ptools_omics_url_template, public_base, analysis=None, data_dir=None,
  orgid="ECOLI") -> dict` — discovers `**/ptools/*.tsv` under a study and builds
  the Omics-Viewer URL. Returns `{url, tsv_url, available}` or `{error, available}`.
  Supports HTTP delivery (`public_base`) or filesystem delivery (`data_dir`).
- `ptools_object_class(name) -> str` — infers the PTools object class
  (`gene` / `reaction` / `protein` / `compound`) from an analysis/TSV name.

## Install / develop

```bash
uv pip install -e ".[dev]"   # resolves vivarium-workbench via [tool.uv.sources]
pytest
```

In the combined workbench image, install `pbg-ptools` explicitly (the workbench is
installed with `--no-deps`, which would skip it).

## Links

- Repository: https://github.com/vivarium-collective/viva-ptools
- vivarium-workbench (host): https://github.com/vivarium-collective/vivarium-workbench
- Pathway Tools / EcoCyc: https://ecocyc.org · https://pathwaytools.com

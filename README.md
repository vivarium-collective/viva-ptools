# pbg-ptools

A **vivarium-workbench analysis-viewer plugin** that contributes the **Pathway
Tools (EcoCyc) Omics Viewer** launcher to a workbench workspace's Analyses page.

## What it does

The workbench discovers a `<pkg>.workbench_viewers.get_viewers(ws_root)` entry on
the workspace package and on **every installed `pbg-*` distribution**. `pbg-ptools`
is found via that `pbg-*` scan — so it activates purely by being installed in the
workbench's environment, independent of which workspace is served.

The viewer overlays a study's exported PTools TSVs onto the E. coli metabolic map
in a Pathway Tools "Cellular Overview" Omics Viewer. It is **dormant** unless the
served workspace sets `ui.ptools_server_url` in `workspace.yaml`.

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
(`lib.study_spec.study_dir`, `lib.workspace_paths.WorkspacePaths`) directly.

## Configuration (`workspace.yaml`)

```yaml
ui:
  ptools_server_url: https://ptools.example.org   # REQUIRED — enables the viewer
  ptools_orgid: ECOLI                              # optional (default ECOLI)
  ptools_omics_url_template: "..."                 # optional URL template override
  ptools_data_dir: /srv/data                       # optional — serve TSVs from disk
  dashboard_public_base_url: https://dash.example  # optional — overrides request host
```

## Install / develop

```bash
uv pip install -e ".[dev]"   # resolves vivarium-workbench via [tool.uv.sources]
pytest
```

In the combined workbench image, install `pbg-ptools` explicitly (the workbench is
installed with `--no-deps`, which would skip it).

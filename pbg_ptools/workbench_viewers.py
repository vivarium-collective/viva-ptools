"""Pathway Tools Omics-Viewer — a vivarium-workbench analysis-viewer plugin.

The workbench (vivarium-workbench) discovers a ``<pkg>.workbench_viewers`` module
on the workspace package and every installed ``pbg-*`` distribution, and calls its
``get_viewers(ws_root)`` to render extra cards on the Analyses page. This package
(``pbg-ptools``) is discovered via that ``pbg-*`` scan and contributes the
**Pathway Tools Omics Viewer** launcher.

The viewer overlays a study's exported PTools TSVs (written by a producer such as
``v2ecoli.workflow.analyses.ptools_*``) onto the E. coli metabolic map in a
Pathway Tools / EcoCyc "Cellular Overview" Omics Viewer. It only appears when the
workspace configures ``ui.ptools_server_url`` in ``workspace.yaml``.

This package depends on ``vivarium-workbench`` (leaf → host), so it imports the
workbench's canonical path resolvers directly. The viewer couples to the producer
only through the on-disk ``**/ptools/*.tsv`` contract — never a Python import.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from urllib.parse import quote

import yaml

# The workbench is a declared dependency of this package, so these resolvers are
# imported directly (they honour a ``layout:`` remap / ``workspace/`` subdir in
# workspace.yaml). This replaces the lazy try/except fallback that existed while
# this module lived inside v2ecoli and the workbench was only optionally present.
from vivarium_workbench.lib.study_spec import study_dir as _study_dir_resolver
from vivarium_workbench.lib.workspace_paths import WorkspacePaths

# Default targets the sms-ptools 0.8.2 Omics Viewer auto-load endpoint
# (omics=t&url=…&class=…&column1=…). Override via ui.ptools_omics_url_template.
# Placeholders: {server},{orgid},{tsv_url},{cls},{columns}.
_PTOOLS_DEFAULT_OMICS_URL_TEMPLATE = (
    "{server}/overviewsWeb/celOv.shtml"
    "?omics=t&url={tsv_url}&orgid={orgid}&class={cls}&column1={columns}"
)


def _ui_config(ws_root: Path) -> dict:
    """The ``ui:`` block from the workspace's ``workspace.yaml`` (or {})."""
    try:
        ws = yaml.safe_load(
            (Path(ws_root) / "workspace.yaml").read_text(encoding="utf-8")
        ) or {}
    except Exception:
        return {}
    return ws.get("ui") or {}


def _ptools_configured(ws_root: Path) -> bool:
    return bool((_ui_config(ws_root).get("ptools_server_url") or "").strip())


def _study_dir(ws_root: Path, slug: str) -> Path:
    """Resolve a study's directory via the workbench's canonical resolver
    (honours a ``layout:`` remap in workspace.yaml)."""
    return Path(_study_dir_resolver(ws_root, slug))


def ptools_object_class(name: str) -> str:
    """Infer the Pathway Tools object class from an analysis/TSV name.

    The Omics Viewer needs to know whether the row IDs are genes, reactions,
    proteins, or compounds. Producers name their ptools analyses accordingly
    (ptools_rna → genes, ptools_rxns → reactions, ptools_proteins → proteins).
    """
    n = name.lower()
    if "rxn" in n or "reaction" in n:
        return "reaction"
    if "protein" in n:
        return "protein"
    if "metabolite" in n or "compound" in n:
        return "compound"
    return "gene"  # rna / default


def build_ptools_launch_url(
    study_dir: "Path | str",
    ws_root: "Path | str",
    ptools_server_url: str,
    ptools_omics_url_template: str,
    public_base: str,
    analysis: Optional[str] = None,
    data_dir: Optional[str] = None,
    orgid: str = "ECOLI",
) -> dict:
    """Discover ptools TSVs under *study_dir* and build an Omics-Viewer URL.

    Returns ``{url, tsv_url, available}`` on success, or ``{error, available}``.
    Two data-delivery modes: HTTP (``tsv_url`` on the dashboard's reachable host)
    or filesystem (``data_dir`` set → server-local ``<data_dir>/<rel>``).
    """
    study_dir = Path(study_dir)
    ws_root = Path(ws_root)

    all_tsvs = sorted(study_dir.glob("**/ptools/*.tsv"))
    if analysis:
        prefix = f"{analysis}__"
        all_tsvs = [p for p in all_tsvs if p.name.startswith(prefix)]

    def _relpath(p: Path) -> str:
        try:
            return p.relative_to(ws_root).as_posix()
        except ValueError:
            return p.as_posix()

    available = [_relpath(p) for p in all_tsvs]
    if not available:
        return {"error": "no ptools TSVs found for this run", "available": []}

    chosen = all_tsvs[0]
    rel = available[0]
    if data_dir:
        tsv_url = f"{data_dir.rstrip('/')}/{rel}"
    else:
        tsv_url = f"{public_base.rstrip('/')}/{rel}"

    cls = ptools_object_class(analysis or chosen.name)

    # Animate across every data column.
    columns = "1"
    try:
        for line in chosen.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith(("#", ";")):
                continue
            ncol = len(line.split("\t")) - 1  # minus the name/ID column
            columns = f"1-{ncol}" if ncol > 1 else "1"
            break
    except Exception:
        pass

    # Percent-encode the nested TSV URL so strict URL parsers (WebKit/Safari
    # window.open) accept the Omics-Viewer query string. PTools decodes it.
    launch_url = ptools_omics_url_template.format(
        server=ptools_server_url.rstrip("/"),
        tsv_url=quote(tsv_url, safe=""),
        orgid=orgid,
        cls=cls,
        columns=columns,
    )
    return {"url": launch_url, "tsv_url": tsv_url, "available": available}


def _launch(ws_root, study, run, ctx) -> dict:
    """Workbench launcher callback: build the PTools Omics-Viewer URL for a study.

    Returns ``{"url": ...}`` on success, or ``{"error": ..., "status": ...}``.
    (``run`` is accepted for signature compatibility; TSV discovery globs the
    whole study directory.)
    """
    ws_root = Path(ws_root)
    ui = _ui_config(ws_root)

    ptools_server_url = (ui.get("ptools_server_url") or "").strip()
    if not ptools_server_url:
        return {"error": "ptools_server_url not configured", "status": 400}

    if not study:
        return {"error": "study is required", "status": 400}

    template = ui.get("ptools_omics_url_template", _PTOOLS_DEFAULT_OMICS_URL_TEMPLATE)
    orgid = (ui.get("ptools_orgid") or "ECOLI").strip() or "ECOLI"

    # workspace.yaml config wins over the request-derived public_base.
    public_base = (ctx or {}).get("public_base") or "http://localhost"
    cfg_base = (ui.get("dashboard_public_base_url") or "").strip()
    if cfg_base:
        public_base = cfg_base

    data_dir = (ui.get("ptools_data_dir") or "").strip() or None

    sd = _study_dir(ws_root, study)
    if not sd.is_dir():
        return {"error": f"study not found: {study}", "status": 404}

    result = build_ptools_launch_url(
        study_dir=sd,
        ws_root=ws_root,
        ptools_server_url=ptools_server_url,
        ptools_omics_url_template=template,
        public_base=public_base,
        analysis=None,
        data_dir=data_dir,
        orgid=orgid,
    )
    if "error" in result:
        result.setdefault("status", 404)
    return result


def _studies_root(ws_root: Path) -> Path:
    """The directory holding study subdirs, via the workbench's canonical
    ``WorkspacePaths.studies`` resolver (honours a ``layout:`` remap /
    ``workspace/`` subdir)."""
    return WorkspacePaths.load(ws_root).studies


def _ptools_targets(ws_root) -> list:
    """Studies that have exported ``ptools/*.tsv`` files — the launchable rows."""
    ws_root = Path(ws_root)
    root = _studies_root(ws_root)
    out = []
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if not p.is_dir():
                continue
            n = len(list(p.glob("**/ptools/*.tsv")))
            if n:
                out.append({
                    "study": p.name,
                    "label": p.name,
                    "detail": f"{n} TSV{'' if n == 1 else 's'}",
                })
    return out


def get_viewers(ws_root) -> list:
    """Contribute the Pathway Tools Omics Viewer launcher (when configured)."""
    return [
        {
            "id": "pathway-tools",
            "title": "Pathway Tools — Omics Viewer",
            "description": (
                "Overlay a study's PTools TSV exports (genes / reactions / "
                "proteins / compounds) on the E. coli metabolic map in the "
                "EcoCyc Cellular Overview Omics Viewer."
            ),
            "kind": "launcher",
            "applies": _ptools_configured,
            "launch": _launch,
            "targets": _ptools_targets,
        }
    ]

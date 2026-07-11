"""pbg-ptools — Pathway Tools (EcoCyc) Omics-Viewer plugin for vivarium-workbench.

The workbench discovers ``pbg_ptools.workbench_viewers.get_viewers`` at runtime
(via its ``pbg-*`` distribution scan) and renders the contributed viewer on the
Analyses page. Nothing here runs unless a workspace configures
``ui.ptools_server_url`` in ``workspace.yaml``.
"""

__version__ = "0.1.0"

"""Unit tests for the pure viewer helpers.

These exercise the URL/classification logic without a live workbench server —
only a temp directory with a couple of ``ptools/*.tsv`` files. Importing the
module requires ``vivarium-workbench`` to be installed (a declared dependency).
"""
from pathlib import Path

from pbg_ptools.workbench_viewers import (
    build_ptools_launch_url,
    get_viewers,
    ptools_object_class,
)


def test_object_class_inference():
    assert ptools_object_class("ptools_rxns") == "reaction"
    assert ptools_object_class("ptools_proteins") == "protein"
    assert ptools_object_class("ptools_compounds") == "compound"
    assert ptools_object_class("ptools_rna") == "gene"  # default
    assert ptools_object_class("anything_else") == "gene"


def test_launch_url_http_mode(tmp_path: Path):
    study = tmp_path / "studies" / "s1"
    ptools = study / "run-1" / "ptools"
    ptools.mkdir(parents=True)
    tsv = ptools / "ptools_rna__genes.tsv"
    tsv.write_text("id\tt0\tt1\tt2\ng1\t1\t2\t3\n", encoding="utf-8")

    out = build_ptools_launch_url(
        study_dir=study,
        ws_root=tmp_path,
        ptools_server_url="https://ptools.example/",
        ptools_omics_url_template=(
            "{server}/overviewsWeb/celOv.shtml"
            "?omics=t&url={tsv_url}&orgid={orgid}&class={cls}&column1={columns}"
        ),
        public_base="http://host",
        orgid="ECOLI",
    )
    assert "error" not in out
    assert out["available"] == ["studies/s1/run-1/ptools/ptools_rna__genes.tsv"]
    # gene class (rna default), 3 data columns → 1-3, nested URL percent-encoded.
    assert "class=gene" in out["url"]
    assert "column1=1-3" in out["url"]
    assert "orgid=ECOLI" in out["url"]
    assert "http%3A%2F%2Fhost" in out["url"]  # tsv_url encoded


def test_launch_url_no_tsvs(tmp_path: Path):
    study = tmp_path / "studies" / "empty"
    study.mkdir(parents=True)
    out = build_ptools_launch_url(
        study_dir=study,
        ws_root=tmp_path,
        ptools_server_url="https://ptools.example",
        ptools_omics_url_template="{server}?url={tsv_url}",
        public_base="http://host",
    )
    assert out.get("error")
    assert out["available"] == []


def test_get_viewers_shape():
    viewers = get_viewers(Path("/nonexistent-ws"))
    assert len(viewers) == 1
    v = viewers[0]
    assert v["id"] == "pathway-tools"
    assert v["kind"] == "launcher"
    assert callable(v["applies"]) and callable(v["launch"]) and callable(v["targets"])


# ---------------------------------------------------------------------------
# deployment-config layer (vivarium-workbench #471 phase 3)
# ---------------------------------------------------------------------------

class TestUiConfigResolution:
    """`_ui_config` resolves through the workbench's deployment-config layer.

    These matter because the viewer **self-gates** on `ptools_server_url` and
    fails *silently* -- an unconfigured launcher simply never renders. A
    regression here is invisible until someone asks why the button is gone.
    """

    def test_deployment_config_overrides_the_workspace(self, tmp_path, monkeypatch):
        """The whole point: a site supplies its own URL without the deployment
        rewriting workspace.yaml."""
        import yaml as _yaml
        (tmp_path / "workspace.yaml").write_text(
            _yaml.safe_dump({"ui": {"ptools_server_url": "http://localhost:1555"}}),
            encoding="utf-8",
        )
        cfg = tmp_path / "deploy.yaml"
        cfg.write_text(
            _yaml.safe_dump({"ui": {"ptools_server_url": "http://site:8080"}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("VIVARIUM_WORKBENCH_DEPLOY_CONFIG", str(cfg))

        from pbg_ptools.workbench_viewers import _ui_config
        assert _ui_config(tmp_path)["ptools_server_url"] == "http://site:8080"

    def test_no_deployment_config_uses_the_workspace(self, tmp_path, monkeypatch):
        """Local dev: unchanged behavior, no configuration required."""
        import yaml as _yaml
        (tmp_path / "workspace.yaml").write_text(
            _yaml.safe_dump({"ui": {"ptools_server_url": "http://localhost:1555"}}),
            encoding="utf-8",
        )
        monkeypatch.delenv("VIVARIUM_WORKBENCH_DEPLOY_CONFIG", raising=False)

        from pbg_ptools.workbench_viewers import _ui_config
        assert _ui_config(tmp_path)["ptools_server_url"] == "http://localhost:1555"

    def test_null_unsets_a_key(self, tmp_path, monkeypatch):
        """`ptools_data_dir: null` is what replaces the seed script's
        imperative `ui.pop("ptools_data_dir")`, so the launcher falls back to
        HTTP delivery where the ptools pod has no workspace mount."""
        import yaml as _yaml
        (tmp_path / "workspace.yaml").write_text(
            _yaml.safe_dump({"ui": {
                "ptools_server_url": "http://x:1555",
                "ptools_data_dir": "/ptools-data",
            }}),
            encoding="utf-8",
        )
        cfg = tmp_path / "deploy.yaml"
        cfg.write_text("ui:\n  ptools_data_dir: null\n", encoding="utf-8")
        monkeypatch.setenv("VIVARIUM_WORKBENCH_DEPLOY_CONFIG", str(cfg))

        from pbg_ptools.workbench_viewers import _ui_config
        resolved = _ui_config(tmp_path)
        assert "ptools_data_dir" not in resolved
        assert resolved["ptools_server_url"] == "http://x:1555"

    def test_viewer_still_gates_on_the_resolved_value(self, tmp_path, monkeypatch):
        """A site can ACTIVATE the viewer for a workspace that never declared a
        ptools server -- the launcher must appear."""
        import yaml as _yaml
        (tmp_path / "workspace.yaml").write_text(
            _yaml.safe_dump({"ui": {}}), encoding="utf-8")
        cfg = tmp_path / "deploy.yaml"
        cfg.write_text(
            _yaml.safe_dump({"ui": {"ptools_server_url": "http://site:8080"}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("VIVARIUM_WORKBENCH_DEPLOY_CONFIG", str(cfg))

        from pbg_ptools.workbench_viewers import _ptools_configured
        assert _ptools_configured(tmp_path) is True

    def test_older_workbench_without_the_resolver_still_works(self, tmp_path, monkeypatch):
        """The ImportError guard: this plugin is versioned independently of its
        host, so it must not require vivarium-workbench >= 0.3.56."""
        import builtins
        import yaml as _yaml
        (tmp_path / "workspace.yaml").write_text(
            _yaml.safe_dump({"ui": {"ptools_server_url": "http://localhost:1555"}}),
            encoding="utf-8",
        )
        real_import = builtins.__import__

        def _no_deploy_config(name, *a, **kw):
            if name == "vivarium_workbench.lib.deploy_config":
                raise ImportError("simulated older workbench")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", _no_deploy_config)
        from pbg_ptools.workbench_viewers import _ui_config
        assert _ui_config(tmp_path)["ptools_server_url"] == "http://localhost:1555"

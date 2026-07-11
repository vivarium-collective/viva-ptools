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

"""Read-only coverage, scoped joins and explicit uncertainty in research views.

Author: Brent Thompson <brent.thompson@ucf.edu>
"""
import hashlib
from pathlib import Path
import pytest
from dpv_dashboard import catalog, model, research


@pytest.fixture
def run(tmp_path):
    model.write(tmp_path / "run.json", {"stages": {"extract": {}, "normalize": {}, "ontology": {}},
        "corpus": {"items": 2, "selection": {"selected": [{"key": "P1"}, {"key": "P2"}]}}})
    model.write(tmp_path / "papers/P1.json", {"key": "P1", "title": "First paper", "doi": "10.1/first",
        "concepts": [{"id": "c1", "label": "solar cells", "type": "device"}, {"id": "c2", "label": "layer", "type": "material"}],
        "relations": [{"s": "c1", "p": "has_part", "o": "c2", "evidence": "the cell has a layer", "verified": True, "evidence_status": "verified"}],
        "causal": [{"cause": "c2", "effect": "c1", "polarity": "increases", "evidence": "layers increase efficiency", "evidence_status": "unverified"}],
        "measurements": [{"concept": "c1", "entity": "c2", "value": "23", "unit": "%", "evidence": "efficiency was 23 percent", "evidence_status": "unevidenced"}],
        "figures": [{"id": "F1", "caption": "A cell", "concepts": ["c1"]}]})
    model.write(tmp_path / "papers/P2.json", {"key": "P2", "title": "Second paper", "concepts": [{"id": "c1", "label": "silicon", "type": "material"}],
                                           "relations": [], "causal": [], "measurements": [], "figures": []})
    concepts = [{"id": "k1", "label": "solar cell", "alt_labels": ["solar cells"], "papers": ["P1"]},
                {"id": "k2", "label": "silicon", "alt_labels": [], "papers": ["P2"]},
                {"id": "k3", "label": "layer", "alt_labels": [], "papers": ["P1"]}]
    model.write(tmp_path / "normalized/concepts.json", concepts)
    model.write(tmp_path / "ontology/classes.json", [{**c, "iri": "https://example.org/" + c["id"],
                "parent": "k3", "parent_source": "type_default"} for c in concepts])
    model.write(tmp_path / "normalized/contradictions.json", [{"cause": "k1", "effect": "k3", "claims": [
        {"polarity": "increases", "papers": ["P1"], "conditions": ["heat"]}, {"polarity": "decreases", "papers": ["P2"]}]}])
    return tmp_path


def test_recorded_lineage_is_scoped_and_joins_original_claims(run):
    model.write(run / "normalized/concept_lineage.json", [
        {"paper": "P1", "original_id": "c1", "original_label": "solar cells", "canonical_id": "k1", "canonical_label": "solar cell"},
        {"paper": "P2", "original_id": "c1", "original_label": "silicon", "canonical_id": "k2", "canonical_label": "silicon"}])
    data = research.index(run)
    assert data.by_canonical["k1"][0]["paper"] == "P1"
    assert data.by_canonical["k2"][0]["paper"] == "P2"
    assert len(data.claims(canonical="k1")) == 3
    assert data.claims(canonical="k2") == []
    assert {r["verification"] for r in data.claims(paper="P1")} == {"verified", "unverified", "unevidenced"}
    assert any(r["original_id"] == "c2" and r["lineage_status"].startswith("unavailable") for r in data.lineage)


def test_older_runs_never_claim_recorded_merge_decisions(run):
    data = research.index(run)
    assert data.by_canonical["k1"][0]["lineage_status"].startswith("reconstructed")
    assert "no exact lineage artifact" in data.narrative("normalize")
    assert data.progress("normalize")[1]["recorded lineage rows"] == 0


def test_ambiguous_alias_does_not_create_a_claim_join(run):
    concepts = catalog.load(run / "normalized/concepts.json")
    model.write(run / "normalized/concepts.json", concepts + [{"id": "k4", "label": "ambiguous cell", "alt_labels": ["solar cells"], "papers": ["P1"]}])
    data = research.index(run)
    row = next(r for r in data.lineage if r["paper"] == "P1" and r["original_id"] == "c1")
    assert row["lineage_status"] == "ambiguous" and row["canonical_id"] == ""
    assert data.claims(canonical="k1") == []


def test_bad_saved_mapping_is_explicit_not_reconstructed(run):
    model.write(run / "normalized/concept_lineage.json", [{"paper": "P1", "original_id": "c1", "canonical_id": "missing"}])
    data = research.index(run)
    assert data.lineage[0]["lineage_status"] == "recorded; source or target unavailable"
    assert data.by_canonical.get("k1", []) == []


def test_unreadable_lineage_never_falls_back_to_an_inferred_map(run):
    (run / "normalized/concept_lineage.json").write_text('{"incomplete":')
    data = research.index(run)
    assert data.lineage_present and not data.lineage_readable
    assert all(r["lineage_status"] == "unavailable (lineage artifact unreadable)" for r in data.lineage)
    assert "no reconstructed map is substituted" in data.narrative("normalize")


def test_conflicting_or_changed_recorded_sources_are_not_used_as_evidence(run):
    model.write(run / "normalized/concept_lineage.json", [
        {"paper": "P1", "original_id": "c1", "canonical_id": "k1", "original_label": "different source label"}])
    assert research.index(run).claims(canonical="k1") == []
    model.write(run / "normalized/concept_lineage.json", [
        {"paper": "P1", "original_id": "c1", "canonical_id": "k1"},
        {"paper": "P1", "original_id": "c1", "canonical_id": "k3"}])
    data = research.index(run)
    assert data.claims(canonical="k1") == [] and data.claims(canonical="k3") == []
    assert data.lineage[0]["lineage_status"] == "ambiguous (duplicate saved identity)"


def test_inventory_keeps_unknown_partial_and_restricted_files(run):
    (run / "unknown.bin").write_bytes(b"artifact")
    (run / "active.partial.json").write_text('{"partial":')
    (run / ".env").write_text("contents must not be previewed")
    rows = {r["path"]: r for r in catalog.inventory(run, superseded=True)}
    assert rows["unknown.bin"]["stage"] == "other"
    assert rows["active.partial.json"]["availability"].startswith("unreadable")
    assert rows["active.partial.json"]["completion"].startswith("partial")
    assert rows["normalized/relations.json"]["availability"] == "missing"
    assert rows["normalized/concept_lineage.json"]["availability"].startswith("unavailable")
    assert rows["unknown.bin"]["attempt"].startswith("superseded")
    with pytest.raises(ValueError):
        catalog.accessible(run, ".env")
    with pytest.raises(ValueError):
        catalog.accessible(run, "../outside.json")


def test_reads_do_not_rewrite_source_artifacts(run):
    before = {p: hashlib.sha256(p.read_bytes()).digest() for p in run.rglob("*") if p.is_file()}
    data = research.index(run)
    catalog.inventory(run)
    data.stage_rows("normalize", "contradictions")
    data.stage_rows("ontology", "placements")
    assert before == {p: hashlib.sha256(p.read_bytes()).digest() for p in run.rglob("*") if p.is_file()}


def test_unreadable_non_json_artifact_is_visible_but_not_downloadable(run, monkeypatch):
    blocked = run / "blocked.bin"
    blocked.write_bytes(b"fixture")
    original_open = Path.open
    def open_file(path, *args, **kwargs):
        if path == blocked:
            raise PermissionError("fixture access denied")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", open_file)
    rows = {r["path"]: r for r in catalog.inventory(run)}
    assert rows["blocked.bin"]["availability"] == "unreadable"
    with pytest.raises(ValueError, match="not currently readable"):
        catalog.accessible(run, "blocked.bin")


def test_newer_recorded_upstream_completion_marks_existing_outputs_superseded(run):
    manifest = catalog.load(run / "run.json")
    manifest["stages"]["normalize"] = {"completed": "2026-10-15T14:00:00+00:00"}
    manifest["stages"]["ontology"] = {"completed": "2026-10-15T13:00:00+00:00"}
    model.write(run / "run.json", manifest)
    rows = {r["path"]: r for r in catalog.inventory(run)}
    assert rows["ontology/classes.json"]["attempt"] == "superseded (newer upstream completion)"
    assert rows["normalized/concepts.json"]["attempt"] == "selected attempt"


def test_new_files_refresh_index_but_unchanged_files_reuse_it(run):
    first = research.index(run)
    assert research.index(run) is first
    model.write(run / "papers/P3.json", {"key": "P3", "concepts": []})
    assert research.index(run) is not first
    assert len(research.index(run).papers) == 3


def test_enrichment_mapping_and_review_views_retain_provenance(run):
    model.write(run / "ontology/enriched.json", [{"id": "k1", "label": "solar cell", "definition": "A device", "definition_status": "imported",
        "definition_source": "https://ontology.example/Cell", "restrictions": [{"p": "has_part", "o": "k3", "evidence": [{"paper": "P1", "text": "cell has a layer"}]}],
        "candidates": [{"iri": "https://ontology.example/Cell", "label": "Cell", "ontology": "Example"}]}])
    model.write(run / "ontology/mappings.json", [{"id": "k1", "label": "Cell", "iri": "https://ontology.example/Cell", "relation": "close", "confidence": .8, "ontology": "Example"}])
    model.write(run / "ontology/uncertain.json", {"items": {"interop": [{"id": "k1", "kind": "candidate_screened_out", "reason": "different category"}]}})
    data = research.index(run)
    assert data.stage_rows("enrich", "definitions")[0]["definition_status"] == "imported"
    assert data.stage_rows("enrich", "restrictions")[0]["target_label"] == "layer"
    candidate = data.stage_rows("enrich", "candidates")[0]
    assert candidate["label"] == "solar cell" and candidate["candidate_label"] == "Cell"
    mapping = data.stage_rows("interop", "mappings")[0]
    assert mapping["local_label"] == "solar cell" and mapping["external_label"] == "Cell"
    assert data.review_rows("interop", "k1")[0]["kind"] == "candidate_screened_out"


def test_integration_source_navigation_uses_only_recorded_local_runs(run):
    integration = run / "integration"
    integration.mkdir()
    model.write(integration / "integration.json", {"inputs": [{"run_id": ".."}, {"run_id": "../outside"}, {"run_id": "source"}],
                                                "ontology": {"files": ["missing.ttl"]}})
    model.write(run / "source/run.json", {"run_id": "source"})
    model.write(integration / "mappings.json", [{"a_iri": "https://example.org/a", "b_iri": "https://example.org/b", "relation": "exact"}])
    model.write(integration / "bridge_concepts.json", [{"label": "Cell", "domains": ["a", "b"], "members": [{"domain": "a", "label": "A", "iri": "https://example.org/a"}]}])
    model.write(integration / "candidates.json", [{"id": "p1", "reviewed": False, "a": {"label": "A"}, "b": {"label": "B"}}])
    assert research.source_roots(integration) == [run / "source"]
    data = research.index(integration)
    assert data.stage_rows("integrate", "bridges")[0]["iri"] == "https://example.org/a"
    assert data.stage_rows("integrate", "candidates")[0]["reviewed"] is False
    assert any(r["path"] == "missing.ttl" and r["availability"] == "missing" for r in catalog.inventory(integration, "integration"))


def test_integration_federation_keeps_domains_and_paper_ids_separate(tmp_path):
    from dpv_dashboard import integration
    for name in ("one", "two"):
        model.write(tmp_path / name / "run.json", {})
        model.write(tmp_path / name / "papers/P1.json", {"key": "P1", "title": name, "concepts": [], "figures": [{"id": "F1", "page": 2, "caption": name}]})
        model.write(tmp_path / name / "normalized/concepts.json", [{"id": "k1", "label": name, "papers": ["P1"]}])
        model.write(tmp_path / name / "ontology/classes.json", [{"id": "k1", "label": name, "iri": "https://example.org/shared"}])
    root = tmp_path / "integration"
    model.write(root / "integration.json", {"inputs": [{"run_id": "one", "domain": "A"}, {"run_id": "two", "domain": "B"}, {"run_id": "missing", "domain": "C"}]})
    values = integration.rows(root, "source_papers")
    assert {(r["source_run"], r["paper"], r["title"]) for r in values} == {("one", "P1", "one"), ("two", "P1", "two")}
    assert len(integration.rows(root, "source_concepts", "one")) == 1
    assert {(r["source_run"], r["id"], r["caption"]) for r in integration.rows(root, "source_figures")} == {("one", "F1", "one"), ("two", "F1", "two")}
    assert integration.rows(root, "sources")[-1]["availability"] == "source run unavailable"
    assert integration.member(root, "https://example.org/shared") is None
    assert integration.member(root, "https://example.org/shared", run="two")[2] == "k1"


def test_media_references_escape_content_and_restrict_files(run, tmp_path):
    from dpv_dashboard import media
    data = research.index(run)
    pdf = run / "paper.pdf"
    pdf.write_bytes(b"%PDF-example")
    assert media.local_file(data, str(pdf), {".pdf"}) == pdf
    assert media.local_file(data, str(run / "../outside.pdf"), {".pdf"}) is None
    assert media.local_file(data, str(pdf), {".png"}) is None
    result = str(media.reference(data, "<script>bad</script>", canonical="k1"))
    assert "<script>bad</script>" not in result and "&lt;script&gt;" in result
    assert "First paper" in result and "reconstructed" in result
    frame = media.rich_table(data, [{"paper": "P1", "title": "First paper"}])
    assert "data-figure=\"F1\"" in str(frame.iloc[0]["figure_links"])


def test_pdf_page_preview_uses_recorded_page_and_rejects_outside_page(run):
    from dpv_dashboard import media
    import pymupdf
    path = run / "paper.pdf"
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40, 40), "Synthetic figure page")
        doc.save(path)
    image = media.page_image(path, catalog.fingerprint(path), 1)
    assert image.startswith(b"\x89PNG")
    with pytest.raises(ValueError):
        media.page_image(path, catalog.fingerprint(path), 2)


def test_artifact_relationship_names_preserve_original_scoped_ids(run):
    from dpv_dashboard import media, presentation
    data = research.index(run)
    rows = [{"paper": "P1", "s": "c1", "p": "has_part", "o": "c2"},
            {"paper": "P2", "s": "c1", "p": "related_to", "o": "missing"}]
    frame = media.rich_table(data, rows)
    assert "solar cells" in str(frame.iloc[0]["s"])
    assert "silicon" in str(frame.iloc[1]["s"])
    assert frame.iloc[1]["o"] == "missing"
    shown = presentation.grid(frame, compact=True).data
    class Renderer:
        def data(self): return shown
        def data_view(self, selected): return shown.iloc[[1]]
    restored = presentation.selected(Renderer()).iloc[0]
    assert restored["s"] == "c1" and restored["paper"] == "P2"
    assert rows[0]["s"] == "c1"

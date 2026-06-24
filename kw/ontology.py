# -*- coding: utf-8 -*-
"""
graphdb_connector.py
====================
Reads v5 schema + concepts CSV outputs, builds an OWL 2 / MDS-Onto-compliant
Turtle ontology for each collection, then emits JSON-LD documents for GraphDB.

Pipeline (per collection)
-------------------------
  1. Build OWL 2 TTL ontology from schema columns + canonical concept terms.
  2. Load that TTL for property IRI resolution.
  3. Emit one JSON-LD file per paper  (named by paper title).
  4. Emit combined  all.jsonld  for GraphDB bulk import.

Usage
-----
  python graphdb_connector.py                     # auto-discover all schema CSVs
  python graphdb_connector.py --schema PATH       # specific schema CSV
  python graphdb_connector.py --dry-run --limit 2 # preview first 2 rows
  python graphdb_connector.py --verbose           # print each file written
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import glob
import sys
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# NAMESPACE CONFIGURATION
# ---------------------------------------------------------------------------

MDS_BASE = "https://cwrusdle.bitbucket.io/mds/"

DOMAIN_NS_MAP: dict[str, str] = {
    "copper":     "https://cwrusdle.bitbucket.io/mds/manufacturing/coppermetallization/",
    "metalliz":   "https://cwrusdle.bitbucket.io/mds/manufacturing/coppermetallization/",
    "electron":   "https://cwrusdle.bitbucket.io/mds/characterization/electronmicroscopy/",
    "sem":        "https://cwrusdle.bitbucket.io/mds/characterization/electronmicroscopy/",
    "solar":      "https://cwrusdle.bitbucket.io/mds/energy/solarcell/",
    "perovskite": "https://cwrusdle.bitbucket.io/mds/energy/solarcell/",
    "gaas":       "https://cwrusdle.bitbucket.io/mds/semiconductors/gaas/",
}

DEFAULT_NS = "https://cwrusdle.bitbucket.io/mds/generic/"

# BFO grounding is opt-in (off by default) so the domain graph stays focused.
GROUND_BFO = os.getenv('GROUND_BFO', 'false').lower() == 'true'

# ---------------------------------------------------------------------------
# EXPLICIT PROPERTY MAP  (column label → full IRI)
# ---------------------------------------------------------------------------

PROPERTY_MAP: dict[str, str] = {
    # Measurements
    "power conversion efficiency":   MDS_BASE + "measurement/PowerConversionEfficiency",
    "fill factor":                    MDS_BASE + "measurement/FillFactor",
    "open circuit voltage":           MDS_BASE + "measurement/OpenCircuitVoltage",
    "short circuit current density":  MDS_BASE + "measurement/ShortCircuitCurrentDensity",
    "series resistance":              MDS_BASE + "measurement/SeriesResistance",
    "contact resistivity":            MDS_BASE + "measurement/ContactResistivity",
    "contact resistance":             MDS_BASE + "measurement/ContactResistance",
    "line resistance":                MDS_BASE + "measurement/LineResistance",
    "electrical conductivity":        MDS_BASE + "measurement/ElectricalConductivity",
    "light absorption loss":          MDS_BASE + "measurement/LightAbsorptionLoss",
    # Materials
    "absorber material":              MDS_BASE + "material/AbsorberMaterial",
    "front contact metallization":    MDS_BASE + "material/FrontContactMetallization",
    "rear contact metallization":     MDS_BASE + "material/RearContactMetallization",
    "contact material":               MDS_BASE + "material/ContactMaterial",
    "seed layer":                     MDS_BASE + "material/SeedLayer",
    "barrier layer":                  MDS_BASE + "material/BarrierLayer",
    "passivation layer":              MDS_BASE + "material/PassivationLayer",
    "buffer layer":                   MDS_BASE + "material/BufferLayer",
    "transparent conductive oxide":   MDS_BASE + "material/TransparentConductiveOxide",
    "anti-reflection coating":        MDS_BASE + "material/AntiReflectionCoating",
    "paste formulation":              MDS_BASE + "material/PasteFormulation",
    "ink formulation":                MDS_BASE + "material/InkFormulation",
    "masking layer":                  MDS_BASE + "material/MaskingLayer",
    "particle size":                  MDS_BASE + "material/ParticleSize",
    "particle morphology":            MDS_BASE + "material/ParticleMorphology",
    "optical properties":             MDS_BASE + "material/OpticalProperties",
    "perovskite composition":         MDS_BASE + "material/PerovskiteComposition",
    # Processes
    "metallization method":           MDS_BASE + "process/MetallizationMethod",
    "deposition method":              MDS_BASE + "process/DepositionMethod",
    "plating process":                MDS_BASE + "process/PlatingProcess",
    "screen printing":                MDS_BASE + "process/ScreenPrinting",
    "laser processing":               MDS_BASE + "process/LaserProcessing",
    "sintering temperature":          MDS_BASE + "process/SinteringTemperature",
    "sintering method":               MDS_BASE + "process/SinteringMethod",
    "curing temperature":             MDS_BASE + "process/CuringTemperature",
    "curing atmosphere":              MDS_BASE + "process/CuringAtmosphere",
    "contact formation":              MDS_BASE + "process/ContactFormation",
    "nanoparticle sintering":         MDS_BASE + "process/NanoparticleSintering",
    "pulsed light processing":        MDS_BASE + "process/PulsedLightProcessing",
    "selective metallization":        MDS_BASE + "process/SelectiveMetallization",
    "process temperature":            MDS_BASE + "process/ProcessTemperature",
    "process scalability":            MDS_BASE + "process/ProcessScalability",
    "printing resolution":            MDS_BASE + "process/PrintingResolution",
    "printing speed":                 MDS_BASE + "process/PrintingSpeed",
    "encapsulation method":           MDS_BASE + "process/EncapsulationMethod",
    "industrial scalability":         MDS_BASE + "process/IndustrialScalability",
    # Device
    "cell architecture":              MDS_BASE + "device/CellArchitecture",
    "grid design":                    MDS_BASE + "device/GridDesign",
    "finger width":                   MDS_BASE + "device/FingerWidth",
    "finger geometry":                MDS_BASE + "device/FingerGeometry",
    "busbar configuration":           MDS_BASE + "device/BusbarConfiguration",
    "photovoltaic technology":        MDS_BASE + "device/PhotovoltaicTechnology",
    "tandem cell architecture":       MDS_BASE + "device/TandemCellArchitecture",
    "cell bifaciality":               MDS_BASE + "device/CellBifaciality",
    "device stability":               MDS_BASE + "device/DeviceStability",
    # Sample
    "substrate material":             MDS_BASE + "sample/SubstrateMaterial",
    "wafer size":                     MDS_BASE + "sample/WaferSize",
    "wafer thickness":                MDS_BASE + "sample/WaferThickness",
    "substrate thermal sensitivity":  MDS_BASE + "sample/SubstrateThermalSensitivity",
    # Reliability
    "degradation mechanism":          MDS_BASE + "characterization/DegradationMechanism",
    "reliability testing":            MDS_BASE + "characterization/ReliabilityTesting",
    "damp heat test":                 MDS_BASE + "characterization/DampHeatTest",
    "thermal cycling test":           MDS_BASE + "characterization/ThermalCyclingTest",
    "adhesion strength":              MDS_BASE + "characterization/AdhesionStrength",
    "contact adhesion strength":      MDS_BASE + "characterization/ContactAdhesionStrength",
    # Economics
    "material cost":                  MDS_BASE + "economics/MaterialCost",
    "production cost":                MDS_BASE + "economics/ProductionCost",
    "silver consumption":             MDS_BASE + "economics/SilverConsumption",
    "carbon footprint":               MDS_BASE + "economics/CarbonFootprint",
    "manufacturing throughput":       MDS_BASE + "economics/ManufacturingThroughput",
}

# ---------------------------------------------------------------------------
# JSON-LD @context base
# ---------------------------------------------------------------------------

BASE_CONTEXT: dict[str, Any] = {
    "rdf":    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs":   "http://www.w3.org/2000/01/rdf-schema#",
    "owl":    "http://www.w3.org/2002/07/owl#",
    "xsd":    "http://www.w3.org/2001/XMLSchema#",
    "skos":   "http://www.w3.org/2004/02/skos/core#",
    "schema": "https://schema.org/",
    "prov":   "http://www.w3.org/ns/prov#",
    "qudt":   "http://qudt.org/schema/qudt/",
    "mds":    MDS_BASE,
}

# ---------------------------------------------------------------------------
# OWL 2 CLASS HIERARCHY CONFIG
# ---------------------------------------------------------------------------

_CLASS_RULES: list[tuple[tuple[str, ...], str]] = [
    (("efficiency", "voltage", "current density", "resistance", "resistivity",
      "conductivity", "fill factor", "power", "loss", "absorption"),
     "mds:Measurement"),
    (("material", "layer", "paste", "ink", "formulation", "coating",
      "oxide", "seed", "barrier", "buffer", "encapsul", "frit",
      "composition", "species", "conductor"),
     "mds:Material"),
    (("method", "process", "printing", "sintering", "curing", "plating",
      "deposition", "laser", "firing", "anneal", "treatment",
      "formation", "patterning", "masking", "selectiv",
      "speed", "temperature", "atmosphere", "duration"),
     "mds:Process"),
    (("architecture", "design", "geometry", "configuration", "structure",
      "busbar", "finger", "grid", "cell", "module", "tandem", "bifacial",
      "polarity", "technology", "device"),
     "mds:Device"),
    (("characterization", "characterisation", "imaging", "microscopy",
      "elemental", "cross section", "surface", "multiscale", "spatial"),
     "mds:Characterization"),
    (("degradation", "reliability", "corrosion", "adhesion", "test",
      "stress", "exposure", "failure", "aging", "cycling", "outdoor", "field"),
     "mds:Reliability"),
    (("substrate", "wafer", "sample", "specimen"),
     "mds:Sample"),
    (("cost", "consumption", "carbon", "silver", "scalability",
      "throughput", "market", "supply", "sustainability"),
     "mds:Economics"),
]

_MDS_CLASSES: dict[str, str] = {
    "mds:Concept":             MDS_BASE + "Concept",
    "mds:Measurement":         MDS_BASE + "Measurement",
    "mds:Material":            MDS_BASE + "Material",
    "mds:Process":             MDS_BASE + "Process",
    "mds:Device":              MDS_BASE + "Device",
    "mds:Characterization":    MDS_BASE + "Characterization",
    "mds:Reliability":         MDS_BASE + "Reliability",
    "mds:Sample":              MDS_BASE + "Sample",
    "mds:Economics":           MDS_BASE + "Economics",
    "mds:ResearchPublication": MDS_BASE + "ResearchPublication",
}

_CLASS_PARENTS: dict[str, str] = {
    "mds:Measurement":      "mds:Concept",
    "mds:Material":         "mds:Concept",
    "mds:Process":          "mds:Concept",
    "mds:Device":           "mds:Concept",
    "mds:Characterization": "mds:Concept",
    "mds:Reliability":      "mds:Characterization",
    "mds:Sample":           "mds:Concept",
    "mds:Economics":        "mds:Concept",
}

# BFO grounding for the MDS branches (impl-plan T1.4). Full BFO IRIs are emitted
# directly (as a second rdfs:subClassOf) so the generated ontology links to an
# upper-level standard, not just MDS. These are conservative, reviewable defaults:
# a material/device/sample is a BFO material entity; a process/characterization is
# a BFO process; a measured property is a BFO quality; everything is a BFO entity.
_BFO_BASE = "http://purl.obolibrary.org/obo/"
_CLASS_UPPER_PARENTS: dict[str, str] = {
    "mds:Concept":          _BFO_BASE + "BFO_0000001",  # entity
    "mds:Material":         _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Device":           _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Sample":           _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Process":          _BFO_BASE + "BFO_0000015",  # process
    "mds:Characterization": _BFO_BASE + "BFO_0000015",  # process
    "mds:Measurement":      _BFO_BASE + "BFO_0000019",  # quality
}

# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def to_camel(label: str) -> str:
    return "".join(w.capitalize() for w in re.sub(r"[^a-z0-9 ]", " ", label.lower()).split())


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", text).strip("_")[:120]


def resolve_ns(domain_value: str) -> tuple[str, str]:
    slug = domain_value.lower()
    for key, ns in DOMAIN_NS_MAP.items():
        if key in slug:
            label = ns.rstrip("/").split("/")[-1][:8].lower()
            return label, ns
    return "mds", DEFAULT_NS


def prop_iri(column: str, ns: str, ttl_map: dict[str, str]) -> str:
    col = column.strip().lower()
    if col in PROPERTY_MAP:
        return PROPERTY_MAP[col]
    if col in ttl_map:
        return ttl_map[col]
    return ns + "has" + to_camel(col)


def split_value_quote(cell: str) -> tuple[str, str]:
    if " | " in cell:
        parts = cell.split(" | ", 1)
        return parts[0].strip(), parts[1].strip()
    return cell.strip(), ""


def build_context(prefix_label: str, ns: str) -> dict[str, Any]:
    ctx = dict(BASE_CONTEXT)
    ctx[prefix_label] = ns
    return ctx


# ---------------------------------------------------------------------------
# TTL PARSER  (loads existing TTL for extra property IRIs)
# ---------------------------------------------------------------------------

def load_ttl_property_map(ttl_path: str) -> dict[str, str]:
    """Return {lowercase_label: iri} from a Turtle file."""
    mapping: dict[str, str] = {}
    if not ttl_path or not os.path.isfile(ttl_path):
        return mapping

    try:
        import rdflib
        g = rdflib.Graph()
        g.parse(ttl_path, format="turtle")
        RDFS = rdflib.namespace.RDFS
        for s, _, o in g.triples((None, RDFS.label, None)):
            mapping[str(o).lower()] = str(s)
        return mapping
    except ImportError:
        pass

    text = Path(ttl_path).read_text(encoding="utf-8", errors="replace")
    iri_pat   = re.compile(r"<([^>]+)>")
    label_pat = re.compile(r'rdfs:label\s+"([^"]+)"')
    current_iri = None
    for line in text.splitlines():
        m = iri_pat.search(line)
        if m:
            current_iri = m.group(1)
        lm = label_pat.search(line)
        if lm and current_iri:
            mapping[lm.group(1).lower()] = current_iri
    return mapping


# ---------------------------------------------------------------------------
# OWL 2 ONTOLOGY BUILDER
# ---------------------------------------------------------------------------

def _classify_concept(label: str) -> str:
    """Return the mds: class curie best matching the concept label."""
    lower = label.lower()
    for keywords, cls in _CLASS_RULES:
        if any(kw in lower for kw in keywords):
            return cls
    return "mds:Concept"


def build_collection_ontology(
    schema_path: str,
    outdir: str,
    domain_val: str | None = None,
) -> str:
    """
    Build an OWL 2 / MDS-Onto-compliant Turtle ontology from v5 pipeline
    outputs (schema CSV + companion concepts CSV) and write it to
      <outdir>/<collection_slug>/<collection_slug>_onto.ttl

    Returns the written file path.
    """
    schema_dir = Path(schema_path).parent
    col_slug   = safe_slug(schema_dir.name or "default")
    col_outdir = Path(outdir) / col_slug
    col_outdir.mkdir(parents=True, exist_ok=True)

    # Schema columns
    df_schema    = pd.read_csv(schema_path, dtype=str).fillna("")
    concept_cols = [c for c in df_schema.columns if c not in ("domain", "doi")]

    # Domain namespace
    if domain_val is None:
        domain_val = str(df_schema.iloc[0].get("domain", "")).strip() if len(df_schema) else ""
    prefix_label, domain_ns = resolve_ns(domain_val or "")

    # Canonical terms + paper-term examples from concepts CSV
    canonical_terms: dict[str, list[str]] = {}
    for cf in schema_dir.glob("concepts_*.csv"):
        try:
            df_c = pd.read_csv(cf, dtype=str).fillna("")
            for _, row in df_c.iterrows():
                can = str(row.get("canonical", "")).strip()
                pt  = str(row.get("paper_term", "")).strip()
                if can:
                    canonical_terms.setdefault(can, [])
                    if pt and pt not in canonical_terms[can]:
                        canonical_terms[can].append(pt)
        except Exception:
            pass

    # Union of schema columns + canonical concept terms
    all_concepts: list[str] = list(dict.fromkeys(
        concept_cols + [c for c in canonical_terms if c not in concept_cols]
    ))

    onto_iri = domain_ns.rstrip("/") + "/ontology"
    today    = datetime.date.today().isoformat()

    lines: list[str] = []

    # --- Prefixes ---
    lines += [
        "@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix owl:     <http://www.w3.org/2002/07/owl#> .",
        "@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix schema:  <https://schema.org/> .",
        "@prefix prov:    <http://www.w3.org/ns/prov#> .",
        f"@prefix mds:     <{MDS_BASE}> .",
        f"@prefix {prefix_label}:     <{domain_ns}> .",
        "",
    ]

    # --- Ontology header ---
    readable = col_slug.replace("_", " ").strip()
    lines += [
        f"<{onto_iri}>",
        "    a owl:Ontology ;",
        f'    rdfs:label "{readable} Ontology"@en ;',
        f'    dcterms:description "OWL 2 ontology generated from MDS-Onto v5 NLP pipeline outputs for the {domain_val or readable} domain."@en ;',
        f'    dcterms:created "{today}"^^xsd:date ;',
        '    dcterms:creator "MDS-Onto v5 NLP Pipeline" ;',
        f'    owl:imports <{MDS_BASE}> ;',
        "    .",
        "",
    ]

    # --- Top-level MDS-Onto classes ---
    lines.append("# ── MDS-Onto top-level classes ───────────────────────────")
    lines.append("")
    for curie, iri in _MDS_CLASSES.items():
        parent = _CLASS_PARENTS.get(curie)
        upper  = _CLASS_UPPER_PARENTS.get(curie)
        lines.append(f"<{iri}>")
        lines.append("    a owl:Class ;")
        lines.append(f'    rdfs:label "{curie.split(":")[-1]}"@en ;')
        if parent:
            lines.append(f"    rdfs:subClassOf <{_MDS_CLASSES[parent]}> ;")
        if upper and GROUND_BFO:
            lines.append(f"    rdfs:subClassOf <{upper}> ;")
        lines.append("    .")
        lines.append("")

    # --- Domain-specific SchemaRecord class ---
    domain_class_iri = domain_ns + "SchemaRecord"
    domain_label     = to_camel(domain_val or domain_ns.rstrip("/").split("/")[-1])
    lines += [
        "# ── Domain record class ──────────────────────────────────────",
        "",
        f"<{domain_class_iri}>",
        "    a owl:Class ;",
        f'    rdfs:label "{domain_label} Schema Record"@en ;',
        f"    rdfs:subClassOf <{_MDS_CLASSES['mds:ResearchPublication']}> ;",
        f'    skos:definition "Structured record extracted from a research publication in the {domain_val or domain_label} domain."@en ;',
        "    .",
        "",
    ]

    # --- One OWL DatatypeProperty per concept ---
    lines.append("# ── Extracted concept properties ─────────────────────────")
    lines.append("")
    seen: set[str] = set()
    for concept in all_concepts:
        mds_class    = _classify_concept(concept)
        col_lower    = concept.strip().lower()
        if col_lower in PROPERTY_MAP:
            p_iri = PROPERTY_MAP[col_lower]
        else:
            p_iri = domain_ns + "has" + to_camel(concept)

        if p_iri in seen:
            continue
        seen.add(p_iri)

        range_iri = _MDS_CLASSES.get(mds_class, MDS_BASE + "Concept")
        examples  = canonical_terms.get(concept, [])[:5]

        lines.append(f"<{p_iri}>")
        lines.append("    a owl:DatatypeProperty ;")
        lines.append(f'    rdfs:label "{concept}"@en ;')
        lines.append(f"    rdfs:domain <{domain_class_iri}> ;")
        lines.append("    rdfs:range xsd:string ;")
        lines.append(f"    skos:broader <{range_iri}> ;")
        if examples:
            ex_str = " ,\n        ".join(f'"{e}"@en' for e in examples)
            lines.append(f"    skos:example {ex_str} ;")
        lines.append("    .")
        lines.append("")

    ttl_content  = "\n".join(lines)
    ttl_filename = col_slug + "_onto.ttl"
    ttl_out      = col_outdir / ttl_filename
    ttl_out.write_text(ttl_content, encoding="utf-8")
    return str(ttl_out)


# ---------------------------------------------------------------------------
# ROW → JSON-LD
# ---------------------------------------------------------------------------

def row_to_jsonld(
    row: pd.Series,
    columns: list[str],
    ttl_map: dict[str, str],
    source_file: str,
    title_map: dict[str, str] | None = None,
    concepts_map: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    """Convert one schema CSV row to a JSON-LD document.

    concepts_map: {doi -> [{"canonical": ..., "paper_term": ..., "relevance": ...}]}
    Each concept is embedded as a mds:hasConcept blank node so GraphDB shows
    all extracted terms when you click on the paper.
    """
    domain_val  = str(row.get("domain", "")).strip()
    doi_val     = str(row.get("doi",    "")).strip()
    prefix_label, ns = resolve_ns(domain_val)
    ctx         = build_context(prefix_label, ns)
    paper_title = (title_map or {}).get(doi_val, "")

    if paper_title:
        doc_id = ns + safe_slug(paper_title)
    elif doi_val:
        doc_id = ns + safe_slug(doi_val)
    else:
        doc_id = ns + "unknown_" + safe_slug(domain_val)

    doc: dict[str, Any] = {
        "@context":          ctx,
        "@id":               doc_id,
        "@type":             ["mds:ResearchPublication", prefix_label + ":SchemaRecord"],
        "schema:identifier": doi_val,
        "mds:hasDomain":     domain_val,
        "mds:derivedFrom":   os.path.basename(source_file),
    }

    if paper_title:
        doc["schema:name"] = paper_title

    if doi_val:
        clean_doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi_val)
        doc["owl:sameAs"] = {"@id": f"https://doi.org/{clean_doi}"}

    # Schema column values (structured property assertions)
    for col in [c for c in columns if c not in ("domain", "doi")]:
        cell = str(row.get(col, "")).strip()
        if not cell:
            continue
        iri           = prop_iri(col, ns, ttl_map)
        value, quote  = split_value_quote(cell)
        entry: dict[str, Any] = {}
        if value:
            entry["mds:value"] = value
        if quote:
            entry["mds:quote"] = quote
        if entry:
            doc[iri] = entry

    # Embed all concepts from the concepts CSV as mds:hasConcept nodes.
    # Each node carries: canonical term, the exact paper term, relevance,
    # and a skos:broader link to the MDS-Onto class branch.
    concept_rows = (concepts_map or {}).get(doi_val, [])
    if concept_rows:
        concept_nodes: list[dict[str, Any]] = []
        for cr in concept_rows:
            canonical  = cr.get("canonical", "").strip()
            paper_term = cr.get("paper_term", "").strip()
            relevance  = cr.get("relevance",  "").strip()
            if not canonical:
                continue
            mds_class  = _classify_concept(canonical)
            class_iri  = _MDS_CLASSES.get(mds_class, MDS_BASE + "Concept")
            node: dict[str, Any] = {
                "mds:canonicalTerm": canonical,
                "skos:broader":      {"@id": class_iri},
            }
            if paper_term:
                node["mds:paperTerm"] = paper_term
            if relevance:
                try:
                    node["mds:relevance"] = {"@value": float(relevance),
                                             "@type": "xsd:decimal"}
                except ValueError:
                    node["mds:relevance"] = relevance
            concept_nodes.append(node)
        if concept_nodes:
            doc["mds:hasConcept"] = concept_nodes

    return doc


# ---------------------------------------------------------------------------
# DISCOVERY
# ---------------------------------------------------------------------------

def discover_schema_files(roots: list[str] | None = None) -> list[str]:
    """Auto-discover schema_*.csv files under outputs/ and schemas/."""
    search_roots = roots or ["outputs", "schemas"]
    found: list[str] = []
    for root in search_roots:
        found.extend(glob.glob(os.path.join(root, "**", "schema_*.csv"), recursive=True))
    return sorted(set(found))


# ---------------------------------------------------------------------------
# MAIN PROCESSOR
# ---------------------------------------------------------------------------

def process_schema_file(
    schema_path: str,
    outdir: str,
    ttl_map: dict[str, str],
    dry_run: bool = False,
    limit: int | None = None,
    verbose: bool = False,
    ttl_path: str | None = None,  # legacy arg; ignored — ontology built fresh
) -> int:
    """
    For one collection:
      1. Build OWL 2 TTL ontology from v5 CSV outputs → write to outdir.
      2. Load that TTL for property IRI resolution.
      3. Write per-paper JSON-LD files.
      4. Write combined all.jsonld last.
    Returns number of rows processed.
    """
    df = pd.read_csv(schema_path, dtype=str).fillna("")
    if limit:
        df = df.head(limit)
    columns = list(df.columns)

    col_slug      = safe_slug(Path(schema_path).parent.name or "default")
    col_outdir    = os.path.join(outdir, col_slug)
    if not dry_run:
        os.makedirs(col_outdir, exist_ok=True)

    # doi → paper title  +  doi → [{canonical, paper_term, relevance}]
    title_map: dict[str, str] = {}
    concepts_map: dict[str, list[dict[str, str]]] = {}
    for cf in Path(schema_path).parent.glob("concepts_*.csv"):
        try:
            cdf = pd.read_csv(cf, dtype=str).fillna("")
            if "doi" in cdf.columns and "paper" in cdf.columns:
                title_map = dict(zip(cdf["doi"], cdf["paper"]))
            if "doi" in cdf.columns and "canonical" in cdf.columns:
                for _, cr in cdf.iterrows():
                    doi_key = str(cr.get("doi", "")).strip()
                    if doi_key:
                        concepts_map.setdefault(doi_key, []).append({
                            "canonical":  str(cr.get("canonical",  "")).strip(),
                            "paper_term": str(cr.get("paper_term", "")).strip(),
                            "relevance":  str(cr.get("relevance",  "")).strip(),
                        })
        except Exception:
            pass

    # 1. Build ontology TTL first
    active_ttl_map = dict(ttl_map)
    if not dry_run:
        domain_val_for_onto = ""
        if len(df):
            domain_val_for_onto = str(df.iloc[0].get("domain", "")).strip()
        try:
            onto_path = build_collection_ontology(
                schema_path=schema_path,
                outdir=outdir,
                domain_val=domain_val_for_onto or None,
            )
            print(f"  Ontology → {onto_path}")
            active_ttl_map = load_ttl_property_map(onto_path)
        except Exception as exc:
            print(f"  [warn] Ontology build failed: {exc}")

    # 2. Per-paper JSON-LD
    all_docs: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(df.iterrows()):
        doc         = row_to_jsonld(row, columns, active_ttl_map, schema_path, title_map, concepts_map)
        doi_val     = str(row.get("doi", "")).strip()
        paper_title = title_map.get(doi_val, "")
        fname       = (
            safe_slug(paper_title) if paper_title
            else (safe_slug(doi_val) if doi_val else f"row_{i:04d}")
        )
        all_docs.append(doc)

        if dry_run:
            print(f"\n--- {fname}.jsonld ---")
            print(json.dumps(doc, indent=2, ensure_ascii=False))
        else:
            out_path = os.path.join(col_outdir, f"{fname}.jsonld")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
            if verbose:
                print(f"  Wrote: {out_path}")

    # 3. Combined all.jsonld - written last
    combined = {
        "@context": all_docs[0]["@context"] if all_docs else BASE_CONTEXT,
        "@graph":   all_docs,
    }
    if dry_run:
        print("\n--- all.jsonld (combined) ---")
        print(json.dumps(combined, indent=2, ensure_ascii=False))
    else:
        combined_path = os.path.join(col_outdir, "all.jsonld")
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)
        print(f"  Combined -> {combined_path}")

    return len(all_docs)


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build OWL 2 TTL ontology + JSON-LD from v5 schema CSVs."
    )
    parser.add_argument("--schema",   metavar="PATH", action="append", dest="schemas")
    parser.add_argument("--ontology", metavar="PATH", default=None)
    parser.add_argument("--outdir",   metavar="DIR",  default="graphdb")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--limit",    type=int, default=None)
    parser.add_argument("--verbose",  action="store_true")
    args = parser.parse_args()

    ttl_map: dict[str, str] = {}
    if args.ontology:
        print(f"Loading external ontology: {args.ontology}")
        ttl_map = load_ttl_property_map(args.ontology)
        print(f"  {len(ttl_map)} mappings loaded.")

    schema_paths = args.schemas or discover_schema_files()
    if not schema_paths:
        print("No schema CSV files found. Use --schema PATH or run from project root.")
        sys.exit(1)

    print(f"\nProcessing {len(schema_paths)} schema file(s):")
    total = 0
    for path in schema_paths:
        print(f"\n  {path}")
        n = process_schema_file(
            schema_path=path,
            outdir=args.outdir,
            ttl_map=ttl_map,
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose,
        )
        total += n
        print(f"  {n} rows -> {args.outdir}/{safe_slug(Path(path).parent.name)}/")

    print(f"\nDone. {total} JSON-LD document(s) -> {args.outdir}/")


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    main()

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

from kw.taxonomy import normalize_stages
from kw import mds_props

# Provenance / property-selection (read via env to keep this module import-light).
CREATOR_ORCID = os.getenv('CREATOR_ORCID', '')
PROPERTY_SELECTION = os.getenv('PROPERTY_SELECTION', 'hybrid').lower()


def _atomic_write_json(obj: Any, path: str) -> None:
    """Write JSON to *path* atomically.

    Serialises to a sibling ``*.tmp`` file, fsyncs, then os.replace()s it into
    place. A crash mid-write leaves only the throwaway temp file, never a
    half-written / truncated target — the cause of the corrupt all.jsonld files.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

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
# Promote each concept to an owl:Class under its branch/subdomain (domain taxonomy).
CONCEPT_CLASSES = os.getenv('CONCEPT_CLASSES', 'true').lower() != 'false'

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
    "mds:Measurement":         MDS_BASE + "Measurement",
    "mds:Material":            MDS_BASE + "Material",
    "mds:Process":             MDS_BASE + "Process",
    "mds:Device":              MDS_BASE + "Device",
    "mds:Characterization":    MDS_BASE + "Characterization",
    "mds:Reliability":         MDS_BASE + "Reliability",
    "mds:Sample":              MDS_BASE + "Sample",
    "mds:Economics":           MDS_BASE + "Economics",
    "mds:ResearchPublication": MDS_BASE + "ResearchPublication",
    "mds:Concept":             MDS_BASE + "Concept",

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
    "mds:Sample":           _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Material":         _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Device":           _BFO_BASE + "BFO_0000040",  # material entity
    "mds:Process":          _BFO_BASE + "BFO_0000015",  # process
    "mds:Characterization": _BFO_BASE + "BFO_0000015",  # process
    "mds:Measurement":      _BFO_BASE + "BFO_0000019",  # quality
    "mds:Concept":          _BFO_BASE + "BFO_0000001",  # entity

}

# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------

def to_camel(label: str) -> str:
    return "".join(w.capitalize() for w in re.sub(r"[^a-z0-9 ]", " ", label.lower()).split())


def _ttl_lit(value) -> str:
    """Escape a value for safe use inside a Turtle "..." string literal.

    Turtle literals must escape backslash and double-quote, plus the control
    characters newline/CR/tab. Without this, data-derived values that contain
    quotes (e.g. leaked JSON fragments in extracted examples) produce invalid
    Turtle and break the ontology parse.
    """
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return s


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", text).strip("_")[:120]


# Prefix labels that map to fixed namespaces and must NEVER be reused by a
# domain namespace — otherwise `@prefix mds:` gets redefined to the generic ns
# in both the TTL and the JSON-LD @context, corrupting every mds: term and
# leaving OntoPortal with no usable ontology.
_RESERVED_PREFIXES = frozenset({
    "rdf", "rdfs", "owl", "xsd", "skos", "schema", "prov", "qudt", "dcterms", "mds",
})


def resolve_ns(domain_value: str) -> tuple[str, str]:
    slug = domain_value.lower()
    for key, ns in DOMAIN_NS_MAP.items():
        if key in slug:
            label = ns.rstrip("/").split("/")[-1][:8].lower()
            if label in _RESERVED_PREFIXES:        # don't clobber a fixed prefix
                label = "dom"
            return label, ns
    # Generic fallback keeps its OWN prefix so mds: stays bound to MDS_BASE.
    return "generic", DEFAULT_NS


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


def _load_mds_matches(schema_dir) -> dict:
    """Per-concept MDS-Onto portal matches from mdsonto_*.csv: {concept_lower: {iri,...}}.

    This is the persisted result of querying the live MDS-Onto via the portal/MCP
    tool (kw.mdsonto.resolve_concepts). Empty when grounding was off / unreachable.
    """
    out: dict = {}
    for mf in Path(schema_dir).glob("mdsonto_*.csv"):
        try:
            df_m = pd.read_csv(mf, dtype=str).fillna("")
            for _, row in df_m.iterrows():
                key = str(row.get("concept", "")).strip().lower()
                if key:
                    out[key] = {k: str(row.get(k, "")).strip()
                                for k in ("iri", "definition", "domain", "subdomain", "study_stage")}
        except Exception:
            pass
    return out


def _class_iri_for(concept: str, mds_matches: dict | None = None) -> str:
    """MDS class IRI for a concept, inferred from the ontology itself.

    Prefers the live portal match (the real MDS-Onto/CCO class resolved for THIS
    concept by querying the domains); falls back to the local keyword heuristic
    only when grounding is off or the concept has no confident match.
    """
    if mds_matches:
        m = mds_matches.get(concept.strip().lower())
        if m and m.get("iri"):
            return m["iri"]
    return _MDS_CLASSES.get(_classify_concept(concept), MDS_BASE + "Concept")


# ---------------------------------------------------------------------------
# MDS design metadata (hasDomain / hasSubDomain / hasStudyStage) + definitions
# ---------------------------------------------------------------------------
# Emit one skos:definition per concept (OntoCheck definitionCoverage). One batched
# LLM pass; falls back to a template when disabled/unavailable.
DEFINE_CONCEPTS = os.getenv('DEFINE_CONCEPTS', 'true').lower() != 'false'

# --- MDS-Onto canonical vocabulary (Getting Started §2, §3, §7.2) -----------
# Six canonical domains. hasDomain points to one of these mds: classes (defined
# in the imported MDS-Onto, owl:imports MDS_BASE).
_MDS_DOMAINS = ("Expo", "Manufact", "Charact", "BuildEnv", "Geo", "Chem")
# Default domain for an unrecognised collection (this corpus is PV-centric -> BuildEnv).
DEFAULT_MDS_DOMAIN = os.getenv("DEFAULT_MDS_DOMAIN", "BuildEnv")
if DEFAULT_MDS_DOMAIN not in _MDS_DOMAINS:
    DEFAULT_MDS_DOMAIN = "BuildEnv"

# Collection-keyword -> canonical domain (first match wins; order = specificity).
_DOMAIN_KEYWORDS: tuple = (
    ("Manufact", ("manufactur", "metalliz", "copper", "plating", "screen print",
                  "fabricat", "printing")),
    ("Charact",  ("charact", "microscop", "electron", "sem", "tem", "spectroscop",
                  "imaging", "metrology", "ftir", "optical")),
    ("Geo",      ("geo", "outage", "grid", "satellite", "spatial", "weather map")),
    ("Chem",     ("chem", "polymer", "pmma", "molecul", "reaction", "acrylic")),
    ("Expo",     ("exposure", "weather", "degrad", "damp heat", "aging", "uv ",
                  "corrosion", "reliability")),
    ("BuildEnv", ("solar", "photovolt", "pv", "perovskite", "gaas", "semiconductor",
                  "energy", "module", "cell", "building", "built env")),
)

# 12 canonical study stages (Getting Started §3) as IRI local names.
# Keyword -> stage (first match wins; specific instrument/processing before result).
_STAGE_KEYWORDS: tuple = (
    ("DataProcessing", ("data processing", "normalization", "calibration",
                        "segmentation", "filtering", "preprocessing", "peak fitting")),
    ("Tool", ("microscop", "spectroscop", "tem", "sem", "xrd", "afm", "instrument",
              "detector", "colorimeter", "indenter", "metrology", "tool")),
    ("Recipe", ("recipe", "setting", "temperature", "atmosphere", "duration", "dosage",
                "scan rate", "parameter")),
    ("MaterialsProcessing", ("deposition", "anneal", "etch", "sputter", "cvd", "ald",
                             "sinter", "fabricat", "lamination", "texturing", "passivation",
                             "coating", "processing", "growth", "curing", "plating",
                             "printing", "metallization", "method")),
    ("Synthesis", ("synthesis", "epitax", "crystal grow", "polymeriz")),
    ("Formulation", ("formulation", "precursor", "ink", "paste", "slurry", "mixing",
                     "composition")),
    ("Modeling", ("model", "simulation", "dft", "netsem", "drift-diffusion")),
    ("Analysis", ("analysis", "correlation", "statistic", "evaluation", "comparison")),
    ("Sample", ("sample", "wafer", "substrate", "film", "specimen", "layer", "absorber",
                "cell", "electrode", "junction", "material", "device", "module")),
    ("Result", ("result", "efficiency", "voltage", "current", "performance", "yield",
                "fill factor", "resistance", "mobility", "lifetime", "bandgap",
                "band gap", "output", "measurement", "loss", "index", "modulus",
                "hardness", "cost")),
    ("Data", ("data", "dataset", "signal", "spectrum", "image")),
)

# Representative study stage per MDS branch (top-level / branch classes).
_BRANCH_STAGE: dict[str, str] = {
    "mds:Measurement": "Result", "mds:Material": "Sample",
    "mds:Process": "MaterialsProcessing", "mds:Device": "Sample",
    "mds:Characterization": "Tool", "mds:Reliability": "Result",
    "mds:Sample": "Sample", "mds:Economics": "Result",
    "mds:Concept": "Result", "mds:ResearchPublication": "ResultsAndMetadata",
}


def _canon_domain(text: str) -> str:
    """Map a collection name/domain string to one of the six canonical MDS domains."""
    t = (text or "").lower()
    for dom, kws in _DOMAIN_KEYWORDS:
        if any(k in t for k in kws):
            return dom
    return DEFAULT_MDS_DOMAIN


def _stage_for(text: str) -> str:
    """Local keyword-based study-stage fallback -> one of the 12 canonical stages.
    Defaults to 'Result' (most extracted concepts are reported results)."""
    t = (text or "").lower()
    for stage, kws in _STAGE_KEYWORDS:
        if any(k in t for k in kws):
            return stage
    return "Result"


def _ns_domain_subdomain(domain_ns: str) -> tuple[str, str]:
    """(domain, subdomain) from a namespace path:
    .../mds/energy/solarcell/ -> ('energy', 'solarcell')."""
    parts = [p for p in domain_ns.split("/mds/", 1)[-1].split("/") if p]
    dom = parts[0] if parts else "generic"
    sub = parts[1] if len(parts) > 1 else ""
    return dom, sub


def _design_lines(domain_local: str, sub: str, stage_local: str) -> list[str]:
    """Mandatory MDS triples (Getting Started §7.2): mds:hasDomain + mds:hasStudyStage
    as mds: IRIs (canonical domain/stage classes from the imported MDS-Onto), plus an
    optional mds:hasSubDomain literal for the domain-specific subdomain."""
    out = [f"    mds:hasDomain mds:{domain_local} ;"]
    if sub:
        out.append(f'    mds:hasSubDomain "{_ttl_lit(sub)}"@en ;')
    out.append(f"    mds:hasStudyStage mds:{stage_local} ;")
    return out


def _altlabel_lines(label: str, examples: list[str] | None = None) -> list[str]:
    """Mandatory MDS triple (Getting Started §7.2): at least one skos:altLabel.
    Uses paper-specific terms as alternatives; falls back to a Title/lower variant
    so every term carries an altLabel (also satisfies OntoCheck altLabelCheck)."""
    lab = (label or "").strip()
    alts = [e.strip() for e in (examples or [])
            if e and e.strip() and e.strip().lower() != lab.lower()]
    if not alts:
        cand = lab.title() if lab.title() != lab else lab.lower()
        if cand == lab:
            cand = f"{lab} term"
        alts = [cand]
    seen, lines = set(), []
    for a in alts[:5]:
        if a.lower() in seen:
            continue
        seen.add(a.lower())
        lines.append(f'    skos:altLabel "{_ttl_lit(a)}"@en ;')
    return lines


def _template_definition(label: str, domain: str) -> str:
    d = (domain or "materials science").strip()
    return f"{label}: a concept in the {d} domain, identified from the source literature."


def _generate_definitions(concepts: list[str], domain_hint: str = "") -> dict[str, str]:
    """One batched LLM pass returning {concept_lower: definition}. Gated by
    DEFINE_CONCEPTS; returns {} (callers fall back to templates) on any failure so
    the build never depends on the LLM being reachable."""
    if not DEFINE_CONCEPTS or not concepts:
        return {}
    try:
        from pydantic import BaseModel, Field
        from pydantic_ai import Agent
        from kw import llm
        from kw.config import pydantic_model, output_spec

        class _Def(BaseModel):
            concept: str
            definition: str = Field(description="one concise factual sentence (<=25 words)")

        class _Defs(BaseModel):
            items: list[_Def]

        agent = Agent(
            pydantic_model, output_type=output_spec(_Defs), retries=2,
            system_prompt=("You write concise, factual one-sentence ontology definitions "
                           "for scientific concepts in the domain: "
                           f"{domain_hint or 'materials science'}. Do not restate the term."),
        )
        prompt = ("Define each concept in one concise sentence (<=25 words). Return every "
                  "concept exactly once.\nConcepts:\n- " + "\n- ".join(concepts))
        res = llm.run_sync(agent, prompt)
        out: dict[str, str] = {}
        for it in res.output.items:
            c = (it.concept or "").strip().lower()
            d = (it.definition or "").strip()
            if c and d:
                out[c] = d
        return out
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [ontology] definition LLM pass skipped ({type(exc).__name__}); using templates")
        return {}


_CANON_CACHE: dict = {}


def _canonical_property(name: str, domain_hint: str = "") -> str | None:
    """Resolve a concept attribute to a canonical MDS-Onto property IRI.
    Pass 1 deterministic; Pass 2 shortlisted-LLM fallback when PROPERTY_SELECTION
    is 'hybrid'. Cached so the property and class loops don't pay twice (and the
    Pass-2 LLM call fires at most once per concept). Returns IRI or None (mint)."""
    key = ((name or "").strip().lower(), domain_hint)
    if key in _CANON_CACHE:
        return _CANON_CACHE[key]
    r = mds_props.resolve_attribute_property(name)
    if not r and PROPERTY_SELECTION == "hybrid":
        r = mds_props.llm_choose(name, "attr", domain_hint=domain_hint)
    _CANON_CACHE[key] = r["iri"] if r else None
    return _CANON_CACHE[key]


def _provenance_lines(creator: str = "") -> list[str]:
    """dcterms:creator (ORCID) annotation when configured. Empty -> nothing."""
    return [f'    dcterms:creator "{_ttl_lit(creator)}" ;'] if creator else []


_QUDT_HAS_UNIT = "http://qudt.org/schema/qudt/hasUnit"
_UNIT_RE = re.compile(
    r'(?<![A-Za-z])(%|wt%|at%|mV|kV|V|mA/cm2|mA/cm\^2|mA|µA|uA|A|kΩ|Ω|ohm|meV|eV|nm|µm|um|mm|cm|'
    r'°C|K|kWh|kW|mW|W|ppm|ppb|min|hrs|hr|h|s)(?![A-Za-z])')


def _detect_unit(values) -> str:
    """Best-effort unit token from example values (e.g. '22.1 %' -> '%'). '' if none."""
    for v in values or []:
        m = _UNIT_RE.search(str(v))
        if m:
            return m.group(1)
    return ""


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

    # MDS-Onto matches (real IRI + definition + domain/subdomain) from mdsonto_*.csv
    mds_matches: dict[str, dict] = {}
    for mf in schema_dir.glob("mdsonto_*.csv"):
        try:
            df_m = pd.read_csv(mf, dtype=str).fillna("")
            for _, row in df_m.iterrows():
                key = str(row.get("concept", "")).strip().lower()
                if key:
                    mds_matches[key] = {k: str(row.get(k, "")).strip()
                                        for k in ("iri", "definition", "domain",
                                                  "subdomain", "study_stage")}
        except Exception:
            pass

    # Union of schema columns + canonical concept terms
    all_concepts: list[str] = list(dict.fromkeys(
        concept_cols + [c for c in canonical_terms if c not in concept_cols]
    ))

    # Canonical MDS domain for this collection (Getting Started §2) + namespace-derived
    # subdomain fallback, plus a batched LLM definition pass (template fallback).
    fb_dom, fb_sub = _ns_domain_subdomain(domain_ns)
    domain_local = _canon_domain(domain_val or fb_dom or col_slug)
    definitions = _generate_definitions(all_concepts, domain_val)

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
        f'    dcterms:description "OWL 2 ontology generated from MDS-Onto v5 NLP pipeline outputs for the {_ttl_lit(domain_val or readable)} domain."@en ;',
        f'    dcterms:created "{today}"^^xsd:date ;',
        '    dcterms:creator "MDS-Onto v5 NLP Pipeline" ;',
        '    dcterms:license "Creative Commons Attribution 4.0 International (CC BY 4.0)"@en ;',
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
        cname  = curie.split(":")[-1]
        lines.append(f"<{iri}>")
        lines.append("    a owl:Class ;")
        lines.append(f'    rdfs:label "{cname}"@en ;')
        lines += _altlabel_lines(cname)
        lines.append(f'    skos:definition "{_ttl_lit(cname)}: an MDS-Onto top-level category '
                     f'for {_ttl_lit(domain_local)} concepts."@en ;')
        lines += _design_lines(domain_local, cname, _BRANCH_STAGE.get(curie, "Result"))
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
        f'    skos:altLabel "{_ttl_lit(domain_label)} Record"@en ;',
        f"    rdfs:subClassOf <{_MDS_CLASSES['mds:ResearchPublication']}> ;",
        f'    skos:definition "Structured record extracted from a research publication in the {_ttl_lit(domain_val or domain_label)} domain."@en ;',
        *_design_lines(domain_local, fb_sub, "ResultsAndMetadata"),
        "    .",
        "",
    ]

    # --- One OWL DatatypeProperty per concept ---
    lines.append("# ── Extracted concept properties ─────────────────────────")
    lines.append("")
    seen: set[str] = set()
    for concept in all_concepts:
        col_lower    = concept.strip().lower()
        if col_lower in PROPERTY_MAP:
            p_iri = PROPERTY_MAP[col_lower]
        else:
            p_iri = domain_ns + "has" + to_camel(concept)

        if p_iri in seen:
            continue
        seen.add(p_iri)

        range_iri = _class_iri_for(concept, mds_matches)
        examples  = canonical_terms.get(concept, [])[:5]

        lines.append(f"<{p_iri}>")
        lines.append("    a owl:DatatypeProperty ;")
        # Distinct from the concept CLASS label (IO8 duplicateLabels compares
        # rdfs:label case-insensitively across classes + properties).
        lines.append(f'    rdfs:label "has {_ttl_lit(concept)}"@en ;')
        lines.append(f"    rdfs:domain <{domain_class_iri}> ;")
        lines.append("    rdfs:range xsd:string ;")
        lines.append(f"    skos:broader <{range_iri}> ;")
        _m = mds_matches.get(concept.strip().lower())
        if _m and _m.get("definition"):
            lines.append(f'    skos:definition "{_ttl_lit(_m["definition"])}"@en ;')
        # Map this attribute to the canonical MDS-Onto property (object or data).
        # Every relationship/attribute thus resolves to a defined MDS property.
        _canon = _canonical_property(concept, domain_val)
        if _canon:
            lines.append(f"    skos:exactMatch <{_canon}> ;")
        if examples:
            ex_str = " ,\n        ".join(f'"{_ttl_lit(e)}"@en' for e in examples)
            lines.append(f"    skos:example {ex_str} ;")
        lines.append("    .")
        lines.append("")

    # --- Concept classes + domain/subdomain hierarchy (grounded in MDS-Onto) ---
    if CONCEPT_CLASSES:
        lines.append("# -- Concept classes (domain taxonomy) --------------------")
        lines.append("")

        def _cls_iri(c):
            return domain_ns + to_camel(c)

        domain_roots = {}
        subdomain_roots = {}
        for c in all_concepts:
            m = mds_matches.get(c.strip().lower())
            if not m:
                continue
            dom = m.get("domain", "").strip()
            sub = m.get("subdomain", "").strip()
            if dom:
                domain_roots.setdefault(dom, domain_ns + to_camel(dom))
            if sub:
                subdomain_roots.setdefault(sub, (domain_ns + to_camel(sub),
                                                 domain_ns + to_camel(dom) if dom else MDS_BASE + "Concept"))

        for dom, iri in domain_roots.items():
            lines += [f"<{iri}>", "    a owl:Class ;", f'    rdfs:label "{_ttl_lit(dom)}"@en ;',
                      *_altlabel_lines(dom),
                      f'    skos:definition "{_ttl_lit(dom)}: an MDS-Onto domain grouping related concepts."@en ;',
                      *_design_lines(_canon_domain(dom), "", _stage_for(dom)),
                      f"    rdfs:subClassOf <{MDS_BASE}Concept> ;", "    .", ""]
        for sub, (iri, parent) in subdomain_roots.items():
            lines += [f"<{iri}>", "    a owl:Class ;", f'    rdfs:label "{_ttl_lit(sub)}"@en ;',
                      *_altlabel_lines(sub),
                      f'    skos:definition "{_ttl_lit(sub)}: an MDS-Onto subdomain within the {_ttl_lit(domain_local)} domain."@en ;',
                      *_design_lines(domain_local, sub, _stage_for(sub)),
                      f"    rdfs:subClassOf <{parent}> ;", "    .", ""]

        seen_cls = set()
        for concept in all_concepts:
            ci = _cls_iri(concept)
            if ci in seen_cls:
                continue
            seen_cls.add(ci)
            c_lower = concept.strip().lower()
            m = mds_matches.get(c_lower)
            if m and m.get("subdomain"):
                parent_iri = domain_ns + to_camel(m["subdomain"])
            elif m and m.get("domain"):
                parent_iri = domain_ns + to_camel(m["domain"])
            else:
                parent_iri = _class_iri_for(concept, mds_matches)
            branch_iri = _MDS_CLASSES[_classify_concept(concept)]
            lines.append(f"<{ci}>")
            lines.append("    a owl:Class ;")
            lines.append(f'    rdfs:label "{_ttl_lit(concept)}"@en ;')
            lines.append(f'    skos:prefLabel "{_ttl_lit(concept)}"@en ;')
            # Mandatory skos:altLabel (§7.2): paper-specific terms as alternatives.
            lines += _altlabel_lines(concept, canonical_terms.get(concept, []))
            lines.append(f"    rdfs:subClassOf <{parent_iri}> ;")
            # Guarantee a link to an in-file MDS branch class. OntoCheck's
            # isolatedElements treats a class as connected only when its subClassOf
            # target is another class declared in this file (a portal IRI is not).
            if branch_iri != parent_iri:
                lines.append(f"    rdfs:subClassOf <{branch_iri}> ;")
            # skos:definition: portal match -> LLM batch -> template (always present,
            # so definitionCoverage clears its threshold).
            definition = ((m or {}).get("definition") or definitions.get(c_lower)
                          or _template_definition(concept, domain_local))
            lines.append(f'    skos:definition "{_ttl_lit(definition)}"@en ;')
            # Mandatory MDS triples (§7.2): hasDomain + hasStudyStage as mds: IRIs,
            # plus subdomain (portal value or namespace fallback).
            lines += _design_lines(domain_local, (m or {}).get("subdomain") or fb_sub,
                                   _stage_for(concept))
            # Extra annotations (Getting Started §7.2: as many as the data supports).
            lines.append(f"    skos:broader <{branch_iri}> ;")
            lines += _provenance_lines(CREATOR_ORCID)
            lines.append(f'    skos:scopeNote "Extracted from the {_ttl_lit(domain_local)} '
                         f'corpus ({_ttl_lit(readable)})."@en ;')
            _u = _detect_unit(canonical_terms.get(concept, []))
            if _u:
                lines.append(f'    <{_QUDT_HAS_UNIT}> "{_ttl_lit(_u)}"@en ;')
            if m and m.get("iri"):
                lines.append(f"    skos:exactMatch <{m['iri']}> ;")
            ex = canonical_terms.get(concept, [])[:5]
            if ex:
                ex_str = " ,\n        ".join(f'"{_ttl_lit(e)}"@en' for e in ex)
                lines.append(f"    skos:example {ex_str} ;")
            lines.append("    .")
            lines.append("")

        # Concept-to-concept relations from REBEL triples (owl:Restriction axioms)
        label_lookup = {c.strip().lower(): _cls_iri(c) for c in all_concepts}

        def _match(text):
            # Confident concept link only: EXACT label match (no loose substring),
            # so noisy REBEL endpoints are not force-joined to concepts.
            return label_lookup.get((text or "").strip().lower(), "")

        # Only weave a REBEL triple into the concept graph when BOTH the triple is
        # confident AND both endpoints map exactly to a concept. Everything else
        # stays standalone in triples_*.csv / rebel_triples.jsonld (not joined).
        min_conf = float(os.getenv("REBEL_LINK_MIN_CONFIDENCE", "0.9"))
        used_props = {}
        axioms = []
        kept = dropped = 0
        for tf in schema_dir.glob("triples_*.csv"):
            try:
                dft = pd.read_csv(tf, dtype=str).fillna("")
                for _, r in dft.iterrows():
                    pn = str(r.get("predicate_norm", "")).strip()
                    if not pn:
                        continue
                    try:
                        conf = float(r.get("confidence", "") or 0)
                    except ValueError:
                        conf = 0.0
                    if conf < min_conf:                 # low-confidence triple -> standalone
                        dropped += 1
                        continue
                    s_iri = _match(r.get("subject", ""))
                    o_iri = _match(r.get("object", ""))
                    if not (s_iri and o_iri) or s_iri == o_iri:
                        dropped += 1
                        continue
                    # pn is now a canonical MDS-Onto object-property IRI
                    # (relations.normalize_predicate resolves the controlled vocab).
                    p_iri = pn if pn.startswith("http") else MDS_BASE + pn.split(":", 1)[-1]
                    p_local = re.split(r"[#/]", p_iri.rstrip("#/"))[-1]
                    used_props[p_iri] = p_local
                    axioms.append((s_iri, p_iri, o_iri))
                    kept += 1
            except Exception:
                pass
        if kept or dropped:
            print(f"  [ontology] REBEL links: {kept} added (conf>={min_conf}, exact match), "
                  f"{dropped} left standalone")

        if axioms:
            lines.append("# -- Object properties + concept relations (from REBEL) ---")
            lines.append("")
            for p_iri, p_local in sorted(used_props.items()):
                lines += [f"<{p_iri}>", "    a owl:ObjectProperty ;",
                          f'    rdfs:label "{p_local}"@en ;', "    .", ""]
            for s_iri, p_iri, o_iri in dict.fromkeys(axioms):
                lines.append(f"<{s_iri}> rdfs:subClassOf "
                             f"[ a owl:Restriction ; owl:onProperty <{p_iri}> ; "
                             f"owl:someValuesFrom <{o_iri}> ] .")
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
    mds_matches: dict | None = None,
    stage_map: dict[str, list[str]] | None = None,
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
        stages = (stage_map or {}).get(col.strip().lower(), [])
        if stages:
            entry["mds:studyStage"] = stages
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
            class_iri  = _class_iri_for(canonical, mds_matches)
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

    # concept (schema column name) → [canonical study stages]
    # Sourced from enriched_*.csv so the JSON-LD triples carry the study-stage
    # grounding that previously only lived in the diagram CSV.
    stage_map: dict[str, list[str]] = {}
    for ef in Path(schema_path).parent.glob("enriched_*.csv"):
        try:
            edf = pd.read_csv(ef, dtype=str).fillna("")
            if "concept" in edf.columns and "mds:studyStage" in edf.columns:
                for _, er in edf.iterrows():
                    key = str(er.get("concept", "")).strip().lower()
                    if key:
                        stage_map[key] = normalize_stages(er.get("mds:studyStage", ""))
        except Exception:
            pass

    # Per-concept MDS-Onto portal matches (drives concept->class assignment).
    mds_matches = _load_mds_matches(Path(schema_path).parent)

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
            print(f"  Ontology -> {onto_path}")
            active_ttl_map = load_ttl_property_map(onto_path)
        except Exception as exc:
            print(f"  [warn] Ontology build failed: {exc}")

    # 2. Per-paper JSON-LD
    all_docs: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(df.iterrows()):
        doc         = row_to_jsonld(row, columns, active_ttl_map, schema_path, title_map,
                                    concepts_map, mds_matches, stage_map)
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
            _atomic_write_json(doc, out_path)
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
        _atomic_write_json(combined, combined_path)
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

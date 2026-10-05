"""Local ontology store: every external term the pipeline may use (BFO, CCO, RO, QUDT, PMDCO, IOF, MDS-Onto).

- Oxigraph (pyoxigraph) holds one named graph per ontology; the term index is extracted from it with SPARQL.
- terms.sqlite: one row per term (labels, definition, parents, domain and range, mappings), the mapping links in
  both directions, and an FTS5 trigram index over every label for fuzzy search.
- vectors.npy: one EMBED vector per term (label, alternative labels, start of the definition).
- manifest.json: location, version and SHA-256 of each ontology file; embedding model and text recipe.

Oxigraph has no full-text or vector search (https://github.com/oxigraph/oxigraph/issues/48), hence the two sidecars.

  python -m src.run ontologies build | status | search <text>
"""
import hashlib
import json
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np
import requests

from src.config import CACHE, EMBED, ONTOLOGY_SEARCH, ONTOLOGY_SOURCES, ONTOLOGY_STORE, secret
from src.tools.progress import log

FILES = CACHE / "ontologies"
DB, VECTORS, MANIFEST = ONTOLOGY_STORE / "terms.sqlite", ONTOLOGY_STORE / "vectors.npy", ONTOLOGY_STORE / "manifest.json"
GRAPH = "urn:kw:ontology:"
PORTAL = "https://www.mdsonto-portal.com:8443"
RECIPE = "v1: label; up to 4 other labels: first 200 characters of the definition"

OWL, RDFS = "http://www.w3.org/2002/07/owl#", "http://www.w3.org/2000/01/rdf-schema#"
SKOS, OBO = "http://www.w3.org/2004/02/skos/core#", "http://purl.obolibrary.org/obo/"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
KINDS = {OWL + "Class": "class", OWL + "ObjectProperty": "object property",
         OWL + "DatatypeProperty": "datatype property", OWL + "AnnotationProperty": "annotation property",
         OWL + "NamedIndividual": "individual", "http://qudt.org/schema/qudt/QuantityKind": "individual",
         "http://qudt.org/schema/qudt/Unit": "individual"}
KIND_ORDER = ["class", "object property", "datatype property", "annotation property", "individual"]
LABELS = {RDFS + "label": "label", SKOS + "prefLabel": "prefLabel", SKOS + "altLabel": "altLabel",
          SKOS + "hiddenLabel": "hiddenLabel",
          "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym": "exactSynonym",
          "http://www.geneontology.org/formats/oboInOwl#hasRelatedSynonym": "relatedSynonym",
          OBO + "IAO_0000118": "alternativeTerm", "http://qudt.org/schema/qudt/symbol": "symbol"}
DEFINITIONS = [SKOS + "definition", OBO + "IAO_0000115",
               "https://spec.industrialontologies.org/ontology/annotation/naturalLanguageDefinition",
               "http://qudt.org/schema/qudt/plainTextDescription", "http://purl.org/dc/terms/description",
               RDFS + "comment"]
MAPPINGS = {OWL + "equivalentClass": "equivalent", OWL + "equivalentProperty": "equivalent", OWL + "sameAs": "same",
            SKOS + "exactMatch": "exact", SKOS + "closeMatch": "close", SKOS + "broadMatch": "broader",
            SKOS + "narrowMatch": "narrower", SKOS + "relatedMatch": "related",
            "http://qudt.org/schema/qudt/exactMatch": "exact", "http://qudt.org/schema/qudt/siExactMatch": "exact"}
INVERSE = {"broader": "narrower", "narrower": "broader"}
PARENTS = [RDFS + "subClassOf", RDFS + "subPropertyOf"]
SINGLE = {RDFS + "domain": "domain", RDFS + "range": "range", OWL + "inverseOf": "inverse"}


# ---------------------------------------------------------------- sources

def _portal(path: str, **params):
    key = secret("MDS_API_KEY")
    if not key:
        raise RuntimeError("MDS_API_KEY is blank in .env")
    r = requests.get(PORTAL + path, headers={"Authorization": f"apikey token={key}"}, params=params or None,
                     timeout=180)
    r.raise_for_status()
    return r


def latest_submission(acronym: str) -> dict:
    """Version, release date and id of an ontology's latest submission on the MDS-Onto portal."""
    sub = _portal(f"/ontologies/{acronym}/latest_submission", display="version,released,submissionId",
                  display_links="false", display_context="false").json()
    return {"version": str(sub.get("version") or ""), "released": sub.get("released"), "id": sub.get("submissionId")}


def _rdf_format(data: bytes) -> str:
    head = data[:4000].lstrip()
    return "xml" if head.startswith(b"<?xml") or b"<rdf:RDF" in head else "ttl"


def _version_key(path) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", path.stem)) or (0,)


def _fetch(name: str, spec: dict) -> dict:
    """Path of an ontology file, downloaded into outputs/cache/ontologies when missing."""
    FILES.mkdir(parents=True, exist_ok=True)
    if "portal" in spec:
        pattern = spec["file"].format(version="*").rsplit(".", 1)[0] + ".*"
        try:
            sub = latest_submission(spec["portal"])
        except Exception as e:  # portal unreachable: newest cached release
            cached = sorted(FILES.glob(pattern), key=_version_key)
            if not cached:
                raise RuntimeError(f"{name}: portal unreachable ({type(e).__name__}) and no cached file") from None
            log(f"{name}: MDS-Onto portal unreachable ({type(e).__name__}); using cached {cached[-1].name}")
            return {"path": cached[-1], "location": "cache (portal unreachable)"}
        stem = spec["file"].format(version=sub["version"]).rsplit(".", 1)[0]
        cached = [p for p in FILES.glob(stem + ".*")]
        if cached:
            return {"path": cached[0], "location": f"MDS-Onto portal {spec['portal']}", **sub}
        log(f"{name}: downloading {spec['portal']} {sub['version']} (released {sub['released']}) from the MDS-Onto portal")
        try:
            data = _portal(f"/ontologies/{spec['portal']}/submissions/{sub['id']}/download").content
        except requests.RequestException:
            data = _portal(f"/ontologies/{spec['portal']}/download").content
        path = FILES / f"{stem}.{'owl' if _rdf_format(data) == 'xml' else 'ttl'}"
        path.write_bytes(data)
        return {"path": path, "location": f"MDS-Onto portal {spec['portal']}", **sub}
    path = FILES / spec["file"]
    if not path.exists():
        log(f"{name}: downloading {spec['url']}")
        r = requests.get(spec["url"], timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    return {"path": path, "location": spec["url"]}


# ---------------------------------------------------------------- build

def build():
    """Download missing files, load every ontology into Oxigraph, extract the term index, embed every term."""
    import pyoxigraph as ox
    sources = {}
    for name, spec in ONTOLOGY_SOURCES.items():
        src = _fetch(name, spec)
        data = src["path"].read_bytes()
        sources[name] = {**src, "path": src["path"], "file": src["path"].name,
                         "sha256": hashlib.sha256(data).hexdigest(), "format": _rdf_format(data)}
    if ONTOLOGY_STORE.exists():
        shutil.rmtree(ONTOLOGY_STORE)
    ONTOLOGY_STORE.mkdir(parents=True)
    store = ox.Store(str(ONTOLOGY_STORE / "oxigraph"))
    for name, s in sources.items():
        fmt = ox.RdfFormat.RDF_XML if s["format"] == "xml" else ox.RdfFormat.TURTLE
        store.bulk_load(path=str(s["path"]), format=fmt, to_graph=ox.NamedNode(GRAPH + name), lenient=True)
    for g, (iri, version) in _versions(store).items():
        sources[g]["version"] = sources[g].get("version") or version
        sources[g]["ontology_iri"] = iri
    for name, s in sources.items():
        log(f"{name}: {s['file']} version {s.get('version') or '?'}")
    terms = _extract(store, list(sources))
    del store
    _write_index(terms)
    model = _write_vectors(terms)
    manifest = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sources": {n: {k: v for k, v in s.items() if k != "path"} for n, s in sources.items()},
                "terms": len(terms), "by_ontology": _count(terms, "ontology"), "by_kind": _count(terms, "kind"),
                "embed_model": model, "embed_recipe": RECIPE}
    MANIFEST.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    _reset()
    log(f"ontology store built: {len(terms):,} terms {manifest['by_ontology']}; "
        f"embeddings {'by ' + model if model else 'off'}")
    return manifest


def _count(terms: dict, field: str) -> dict:
    out = defaultdict(int)
    for t in terms.values():
        out[t[field]] += 1
    return dict(out)


def _query(store, preds) -> list[tuple]:
    values = " ".join(f"<{p}>" for p in preds)
    q = f"SELECT ?g ?s ?p ?o WHERE {{ GRAPH ?g {{ VALUES ?p {{ {values} }} ?s ?p ?o }} FILTER(isIRI(?s)) }}"
    return [(sol["g"].value[len(GRAPH):], sol["s"].value, sol["p"].value, sol["o"]) for sol in store.query(q)]


def _versions(store) -> dict:
    """graph name -> (ontology IRI, version) from each file's owl:Ontology header."""
    q = (f"SELECT ?g ?o ?info ?iri WHERE {{ GRAPH ?g {{ ?o a <{OWL}Ontology> "
         f"OPTIONAL {{ ?o <{OWL}versionInfo> ?info }} OPTIONAL {{ ?o <{OWL}versionIRI> ?iri }} }} }}")
    out = {}
    for sol in store.query(q):
        v = sol["info"] or sol["iri"]
        version = v.value if v is not None and "$$" not in v.value else ""
        g = sol["g"].value[len(GRAPH):]
        if g not in out or (version and not out[g][1]):
            out[g] = (sol["o"].value if sol["o"].__class__.__name__ == "NamedNode" else "", version)
    return out


def _english(lit) -> str | None:
    lang = (getattr(lit, "language", None) or "").lower()
    text = re.sub(r"\s+", " ", getattr(lit, "value", "")).strip()
    return text if text and (not lang or lang.startswith("en")) else None


def _extract(store, order: list[str]) -> dict:
    """One record per typed IRI, merged across graphs. A term belongs to the ontology whose IRI prefix it carries
    (its home) when that graph declares it, else to the first graph that declares it."""
    named = lambda o: o.__class__.__name__ == "NamedNode"
    per = defaultdict(lambda: {"kinds": set(), "types": set(), "labels": [], "defs": {}, "parents": set(),
                               "mappings": set(), "deprecated": False})
    for g, s, p, o in _query(store, [RDF_TYPE]):
        if o.value in KINDS:
            per[(g, s)]["kinds"].add(KINDS[o.value])
        if named(o) and not o.value.startswith((OWL, RDFS)):
            per[(g, s)]["types"].add(o.value)
    for g, s, p, o in _query(store, list(LABELS)):
        if (text := _english(o)):
            per[(g, s)]["labels"].append((text, LABELS[p]))
    for g, s, p, o in _query(store, DEFINITIONS):
        if (text := _english(o)):
            per[(g, s)]["defs"].setdefault(p, text)
    for g, s, p, o in _query(store, PARENTS):
        if named(o) and o.value not in (s, OWL + "Thing", OWL + "topObjectProperty"):
            per[(g, s)]["parents"].add(o.value)
    for g, s, p, o in _query(store, list(MAPPINGS)):
        if named(o) and o.value != s:
            per[(g, s)]["mappings"].add((MAPPINGS[p], o.value))
    for g, s, p, o in _query(store, list(SINGLE)):
        if named(o):
            per[(g, s)].setdefault(SINGLE[p], o.value)
    for g, s, p, o in _query(store, [OWL + "deprecated"]):
        per[(g, s)]["deprecated"] |= getattr(o, "value", "").lower() == "true"

    by_iri = defaultdict(dict)
    for (g, s), rec in per.items():
        by_iri[s][g] = rec
    homes = {name: ONTOLOGY_SOURCES[name]["home"] for name in order}
    terms = {}
    for iri, graphs in by_iri.items():
        typed = [g for g in order if g in graphs and graphs[g]["kinds"]]
        if not typed:
            continue
        home = next((g for g in typed if iri.startswith(tuple(homes[g]))), typed[0])
        rest = [graphs[g] for g in typed if g != home]
        main = graphs[home]
        labels, seen = [], set()
        for text, prop in sorted([x for r in [main, *rest] for x in r["labels"]],
                                 key=lambda x: (x[1] not in ("label", "prefLabel"),)):
            if text.lower() not in seen:
                seen.add(text.lower())
                labels.append({"text": text, "prop": prop})
        label = labels[0]["text"] if labels else re.sub(r"([a-z])([A-Z])", r"\1 \2", re.split(r"[#/]", iri)[-1])
        definition = next((r["defs"][p] for r in [main, *rest] for p in DEFINITIONS if p in r["defs"]), "")
        kinds = main["kinds"]  # the home ontology decides (MDS-Onto types some CCO properties as classes)
        terms[iri] = {
            "iri": iri, "ontology": home, "kind": next(k for k in KIND_ORDER if k in kinds), "label": label,
            "definition": definition, "labels": labels, "deprecated": any(graphs[g]["deprecated"] for g in typed),
            "parents": sorted(main["parents"] or set().union(*(r["parents"] for r in rest))),
            "domain": main.get("domain") or next((r["domain"] for r in rest if r.get("domain")), None),
            "range": main.get("range") or next((r["range"] for r in rest if r.get("range")), None),
            "inverse": main.get("inverse") or next((r["inverse"] for r in rest if r.get("inverse")), None),
            "mappings": sorted(set().union(*(graphs[g]["mappings"] for g in graphs))),
            "types": sorted(set().union(*(graphs[g]["types"] for g in typed))), "graphs": typed}
    return terms


def _norm(text: str) -> str:
    from src.tools.lexical import match_key
    return match_key(text.replace("_", " "))


def _write_index(terms: dict):
    con = sqlite3.connect(DB)
    con.executescript("""
        CREATE TABLE terms(iri TEXT PRIMARY KEY, ontology TEXT, kind TEXT, label TEXT, definition TEXT,
                           deprecated INTEGER, data TEXT);
        CREATE TABLE labels(iri TEXT, text TEXT, prop TEXT, norm TEXT);
        CREATE TABLE links(source TEXT, rel TEXT, target TEXT);
        CREATE VIRTUAL TABLE fts USING fts5(text, iri UNINDEXED, tokenize='trigram');""")
    keep = ("labels", "parents", "domain", "range", "inverse", "mappings", "types", "graphs")
    con.executemany("INSERT INTO terms VALUES (?,?,?,?,?,?,?)",
                    [(t["iri"], t["ontology"], t["kind"], t["label"], t["definition"], int(t["deprecated"]),
                      json.dumps({k: t[k] for k in keep})) for t in terms.values()])
    rows = [(t["iri"], x["text"], x["prop"], _norm(x["text"])) for t in terms.values() for x in t["labels"]]
    con.executemany("INSERT INTO labels VALUES (?,?,?,?)", rows)
    con.executemany("INSERT INTO fts(text, iri) VALUES (?,?)", [(text, iri) for iri, text, _, _ in rows])
    con.executemany("INSERT INTO links VALUES (?,?,?)",
                    [(t["iri"], rel, target) for t in terms.values() for rel, target in t["mappings"]])
    con.executescript("""
        CREATE INDEX labels_norm ON labels(norm); CREATE INDEX links_source ON links(source);
        CREATE INDEX links_target ON links(target);""")
    con.commit()
    con.close()


def _text(t: dict) -> str:
    others = [x["text"] for x in t["labels"][1:5]]
    return f"{t['label']}" + (f"; {'; '.join(others)}" if others else "") + f": {t['definition'][:200]}"


def _write_vectors(terms: dict) -> str | None:
    if not EMBED["model"]:
        return None
    from src.tools import llm
    ids = list(terms)
    log(f"embedding {len(ids):,} terms with {EMBED['model']} (once per store build)")
    try:
        vecs, _ = llm.embed([_text(terms[i]) for i in ids])
    except Exception as e:
        log(f"embeddings skipped ({type(e).__name__}: {str(e)[:120]}); search falls back to labels only")
        return None
    m = np.asarray(vecs, dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-12
    np.save(VECTORS, m)
    (ONTOLOGY_STORE / "vectors.json").write_text(json.dumps({"model": EMBED["model"], "recipe": RECIPE, "ids": ids}),
                                                 encoding="utf-8")
    return EMBED["model"]


# ---------------------------------------------------------------- lookups

def available() -> bool:
    return DB.exists() and MANIFEST.exists()


def require():
    if not available():
        raise RuntimeError("The ontology store is not built. Run: python -m src.run ontologies build")


@lru_cache(maxsize=1)
def _db() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def _reset():
    for f in (_db, manifest, term, ancestors, _vectors, _search_vectors):
        f.cache_clear()


@lru_cache(maxsize=None)
def term(iri: str) -> dict | None:
    """The store record of an IRI: ontology, kind, label, definition, labels, parents, domain, range, inverse,
    mappings, types, deprecated, defined_by (the ontology's IRI)."""
    if not iri or not available():
        return None
    row = _db().execute("SELECT iri, ontology, kind, label, definition, deprecated, data FROM terms WHERE iri=?",
                        (iri,)).fetchone()
    if not row:
        return None
    src = manifest().get("sources", {}).get(row[1], {})
    return {"iri": row[0], "ontology": row[1], "kind": row[2], "label": row[3], "definition": row[4],
            "deprecated": bool(row[5]), "source": row[1].lower(), "defined_by": src.get("ontology_iri") or "",
            **json.loads(row[6])}


@lru_cache(maxsize=None)
def ancestors(iri: str) -> tuple:
    """Named ancestors through every ontology in the store, nearest first."""
    seen, queue = [], list((term(iri) or {}).get("parents", []))
    while queue:
        p = queue.pop(0)
        if p not in seen and p != iri:
            seen.append(p)
            queue += (term(p) or {}).get("parents", [])
    return tuple(seen)


def reaches_bfo(iri: str) -> bool:
    return any(a.startswith(OBO + "BFO_") for a in (iri, *ancestors(iri)))


def links(iri: str) -> list[tuple[str, str]]:
    """(relation, IRI) for the term's own mappings and every mapping pointing at it (broader/narrower inverted)."""
    if not available():
        return []
    out = _db().execute("SELECT rel, target FROM links WHERE source=?", (iri,)).fetchall()
    out += [(INVERSE.get(rel, rel), s) for rel, s in
            _db().execute("SELECT rel, source FROM links WHERE target=?", (iri,)).fetchall()]
    return list(dict.fromkeys((r, t) for r, t in out if t != iri))


def propagate(iri: str, max_hops: int | None = None) -> list[dict]:
    """Terms reached through mappings from iri: one hop (its mappings) and two hops (theirs), each with the path
    of IRIs and relations it came through. Only terms that are in the store."""
    max_hops = ONTOLOGY_SEARCH["max_hops"] if max_hops is None else max_hops
    out, seen, frontier = [], {iri}, [(iri, [iri], [])]
    for hop in range(1, max_hops + 1):
        nxt = []
        for node, path, rels in frontier:
            for rel, target in links(node):
                if target in seen or not term(target):
                    continue
                seen.add(target)
                item = {"iri": target, "hop": hop, "path": [*path, target], "relations": [*rels, rel]}
                out.append(item)
                nxt.append((target, item["path"], item["relations"]))
        frontier = nxt
    return out


@lru_cache(maxsize=1)
def _vectors():
    """(matrix, ids, row of iri, ontology per row, kind per row, deprecated per row) or None when the store has
    no vectors for the current EMBED model."""
    meta_path = ONTOLOGY_STORE / "vectors.json"
    if not (VECTORS.exists() and meta_path.exists()):
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("model") != EMBED["model"] or meta.get("recipe") != RECIPE:
        return None
    info = {r[0]: r[1:] for r in _db().execute("SELECT iri, ontology, kind, deprecated FROM terms")}
    ids = meta["ids"]
    return (np.load(VECTORS), ids, {i: n for n, i in enumerate(ids)}, np.array([info[i][0] for i in ids]),
            np.array([info[i][1] for i in ids]), np.array([bool(info[i][2]) for i in ids]))


def has_vectors() -> bool:
    return available() and _vectors() is not None


@lru_cache(maxsize=32)
def _search_vectors(kinds: tuple, ontologies: tuple):
    """Reuse eligible vector subsets instead of scoring unrelated ontologies and term kinds."""
    vec = _vectors()
    if vec is None:
        return None
    m, _, _, onts, knds, dep = vec
    mask = ~dep
    if kinds:
        mask &= np.isin(knds, kinds)
    if ontologies:
        mask &= np.isin(onts, ontologies)
    indices = np.flatnonzero(mask)
    return indices, m[indices]


def exact(text: str, kinds=None, ontologies=None) -> list[dict]:
    """Terms (not deprecated) with any label that normalises to the same form as text."""
    require()
    if len(_norm(text)) < 3:  # "-", "x", "Si": too short to name a term safely
        return []
    rows = _db().execute("SELECT DISTINCT iri FROM labels WHERE norm=?", (_norm(text),)).fetchall()
    found = [t for (iri,) in rows if (t := term(iri)) and not t["deprecated"]]
    return [t for t in found if (not kinds or t["kind"] in kinds) and (not ontologies or t["ontology"] in ontologies)]


def similarity(a: str, b: str) -> float:
    """Trigram Dice similarity of two labels after the store's normalisation (0-1)."""
    return _dice(_norm(a), _norm(b))


def _grams(text: str) -> set:
    t = f" {text} "
    return {t[i:i + 3] for i in range(len(t) - 2)}


def _dice(a: str, b: str) -> float:
    ga, gb = _grams(a), _grams(b)
    return 2 * len(ga & gb) / (len(ga) + len(gb)) if ga and gb else 0.0


def search(texts: list[str], vector=None, kinds=None, ontologies=None, k: int = 10, pool: int = 60,
           nearest: int = 0) -> list[dict]:
    """Candidates for one concept, ranked exact label matches first, then by a fused score of three signals:
    exact (a normalised label equals one of texts), fuzzy (trigram similarity, FTS5 trigram index) and cosine
    (vector against the term vectors; pass the concept's EMBED vector, or None for labels only). A candidate needs
    one signal on its own (exact, fuzzy >= min_fuzzy or cosine >= min_cosine) and a fused score >= min_score;
    the `nearest` closest terms by cosine are kept regardless (placement always sees the nearest classes).
    kinds / ontologies restrict the result (e.g. kinds=("class",), ontologies=("CCO", "BFO"))."""
    if k < 1 or pool < 1 or nearest < 0:
        raise ValueError("Search k and pool must be positive and nearest must be nonnegative")
    require()
    con, s = _db(), ONTOLOGY_SEARCH
    hits = defaultdict(lambda: {"exact": 0.0, "fuzzy": 0.0, "cosine": None, "methods": set()})
    for text in [t for t in dict.fromkeys(texts) if t and t.strip()]:
        norm = _norm(text)
        for (iri,) in con.execute("SELECT DISTINCT iri FROM labels WHERE norm=?", (norm,)) if len(norm) >= 3 else []:
            hits[iri]["exact"] = 1.0
            hits[iri]["methods"].add("exact")
        grams = sorted({g for g in _grams(text.lower()) if g.strip() and '"' not in g and len(g.strip()) == 3})
        if not grams:
            continue
        expr = " OR ".join(f'"{g}"' for g in grams)
        for iri, label in con.execute("SELECT iri, text FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT 400", (expr,)):
            score = _dice(norm, _norm(label))
            if score > hits[iri]["fuzzy"]:
                hits[iri]["fuzzy"] = score
            if score >= s["min_fuzzy"]:
                hits[iri]["methods"].add("fuzzy")
    vec = _vectors() if vector is not None else None
    if vec is not None:
        m, ids, row, onts, knds, dep = vec
        query = np.asarray(vector, dtype=np.float32)
        if query.shape != (m.shape[1],) or not np.isfinite(query).all():
            raise ValueError("Search vector must be finite and match the ontology store's embedding dimension")
        indices, matrix = _search_vectors(tuple(kinds or ()), tuple(ontologies or ()))
        masked = np.full(len(ids), -1.0, dtype=np.float32)
        masked[indices] = matrix @ query / (np.linalg.norm(vector) + 1e-12)
        count = min(pool, len(ids))
        if count < len(ids):
            best = np.argpartition(-masked, count - 1)[:count]
            boundary = masked[best].min()
            # Retain the old sort's tie behavior, including ties spanning the pool boundary.
            if np.count_nonzero(masked == boundary) > 1 or len(np.unique(masked[best])) != count:
                best = np.argsort(-masked)[:count]
            else:
                best = best[np.argsort(-masked[best])]
        else:
            best = np.argsort(-masked)[:count]
        for rank, j in enumerate(best):
            if masked[j] >= s["min_cosine"] or rank < nearest:
                hits[ids[j]]["methods"].add("embedding" if masked[j] >= s["min_cosine"] else "nearest")
                hits[ids[j]]["cosine"] = float(masked[j])
        for iri, h in hits.items():
            if h["cosine"] is None and iri in row:
                h["cosine"] = float(masked[row[iri]])
    out = []
    for iri, h in hits.items():
        t = term(iri)
        if not t or t["deprecated"] or (kinds and t["kind"] not in kinds) or (ontologies and t["ontology"] not in ontologies):
            continue
        fused = _fuse(h["exact"], h["fuzzy"], h["cosine"])
        if "nearest" not in h["methods"] and not h["exact"] and (fused < s["min_score"] or not (
                h["fuzzy"] >= s["min_fuzzy"] or (h["cosine"] or 0) >= s["min_cosine"])):
            continue
        out.append({"iri": iri, "label": t["label"], "ontology": t["ontology"], "kind": t["kind"],
                    "definition": t["definition"], "labels": [x["text"] for x in t["labels"]],
                    "score": round(fused, 3), "exact": h["exact"] > 0, "fuzzy": round(h["fuzzy"], 3),
                    "cosine": None if h["cosine"] is None else round(h["cosine"], 3), "methods": sorted(h["methods"])})
    out.sort(key=lambda x: (-x["exact"], -x["score"]))
    return out[:k]


def _fuse(exact: float, fuzzy: float, cosine: float | None) -> float:
    """Weighted mean of the lexical signal (1 for an exact label, else the trigram similarity) and the embedding
    cosine; without embeddings the lexical signal alone."""
    w, lexical = ONTOLOGY_SEARCH["weights"], max(exact, fuzzy)
    if cosine is None:
        return lexical
    return (w["lexical"] * lexical + w["cosine"] * max(cosine, 0.0)) / (w["lexical"] + w["cosine"])


def score(iri: str, texts: list[str], vector=None) -> dict:
    """The search signals and fused score of one known term against a concept (for terms found elsewhere, such
    as MDS-Onto portal hits)."""
    t = term(iri)
    if not t:
        return {}
    norms = [_norm(x) for x in texts if x and len(_norm(x)) >= 3]
    names = [_norm(x["text"]) for x in t["labels"]]
    exact = float(any(n in names for n in norms))
    fuzzy = max((_dice(n, m) for n in norms for m in names), default=0.0)
    vec = _vectors() if vector is not None else None
    cosine = None
    if vec is not None and iri in vec[2]:
        cosine = float(vec[0][vec[2][iri]] @ np.asarray(vector, dtype=np.float32) / (np.linalg.norm(vector) + 1e-12))
    return {"score": round(_fuse(exact, fuzzy, cosine), 3), "exact": bool(exact), "fuzzy": round(fuzzy, 3),
            "cosine": None if cosine is None else round(cosine, 3)}


def score_external(label: str, definition: str, texts: list[str], vector=None, term_vector=None) -> dict:
    """The same signals and fused score for a term outside the store (a portal hit): term_vector is the term's
    embedding of label: definition, made with the store's recipe."""
    norms = [_norm(x) for x in texts if x and len(_norm(x)) >= 3]
    name = _norm(label)
    exact = float(name in norms)
    fuzzy = max((_dice(n, name) for n in norms), default=0.0)
    cosine = None
    if vector is not None and term_vector is not None:
        cosine = float(np.asarray(term_vector) @ np.asarray(vector) / (np.linalg.norm(vector) + 1e-12))
    return {"score": round(_fuse(exact, fuzzy, cosine), 3), "exact": bool(exact), "fuzzy": round(fuzzy, 3),
            "cosine": None if cosine is None else round(cosine, 3)}


def external_text(label: str, definition: str) -> str:
    return _text({"label": label, "labels": [{"text": label}], "definition": definition or ""})


# ---------------------------------------------------------------- reporting

def summary() -> dict:
    """What a run records in run.json: ontology versions and hashes, embedding model, build time."""
    m = manifest()
    return {"built": m.get("built"), "embed_model": m.get("embed_model"), "terms": m.get("terms"),
            "sources": {n: {k: s.get(k) for k in ("version", "file", "sha256", "location")}
                        for n, s in m.get("sources", {}).items()}} if m else {}


def status(check_portal: bool = True) -> dict:
    """Is the store built, built from the files and settings in use now, and is a newer MDS-Onto out?"""
    if not available():
        return {"built": False, "problems": ["not built: python -m src.run ontologies build"]}
    m, problems, notes = manifest(), [], []
    for name, spec in ONTOLOGY_SOURCES.items():
        src = m["sources"].get(name)
        if not src:
            problems.append(f"{name} is configured but not in the store")
            continue
        path = FILES / src["file"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != src["sha256"]:
            problems.append(f"{name}: {src['file']} changed or missing since the build")
        if check_portal and "portal" in spec:
            try:
                latest = latest_submission(spec["portal"])["version"]
                if latest and latest != src.get("version"):
                    problems.append(f"{name}: newer submission {latest} on the portal (store has {src.get('version')})")
            except Exception as e:
                notes.append(f"{name}: could not check the portal for a newer submission ({type(e).__name__})")
    problems += [f"{name} is in the store but no longer configured" for name in m["sources"] if name not in ONTOLOGY_SOURCES]
    if EMBED["model"] and m.get("embed_model") != EMBED["model"]:
        problems.append(f"embeddings were built with {m.get('embed_model')}, EMBED model is {EMBED['model']}: rebuild")
    return {"built": m["built"], "terms": m["terms"], "by_ontology": m["by_ontology"],
            "versions": {n: s.get("version") for n, s in m["sources"].items()},
            "embed_model": m.get("embed_model"), "problems": problems, "notes": notes}

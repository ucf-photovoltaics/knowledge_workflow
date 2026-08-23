# MDS-Onto branch mapping — for approval

Drafted 2026-08-22. Purpose: replace the ten self-minted branch classes in
`kw/ontology.py:_MDS_CLASSES` with real MDS-Onto terms, so "grounded in MDS-Onto" becomes
true. **Approve, correct, or reject each row.** Implementation is mechanical once this table
is settled.

---

## First: a correction to what I told you earlier

I said only `Characterization` was a real MDS-Onto term. That was based on the rendered
documentation page, and it was wrong in both directions. The authoritative local evidence is
`.mdsonto_cache.json` — 1,192 cached OntoPortal responses, and `kw/mdsonto.py:157` takes the
IRI **verbatim** from the portal's `@id` with no local construction. So every IRI in that
cache is a real term the portal actually served, with the portal's own definition attached.

What that evidence changes:

- **`mds:Material` and `mds:Measurement` are real.** Both came back from the portal with
  authored definitions. They stay.
- **`Characterization` is real but in a namespace the code doesn't know.** The portal returned
  it as `https://cwrusdle.bitbucket.io/mdsdom/Charact` — note `mdsdom/`, not `mds/`.
- **The slash namespace is correct.** `MDS_BASE = "https://cwrusdle.bitbucket.io/mds/"` matches
  what the portal serves (147 slash-form IRIs cached, zero hash-form). The `#`-separated form
  in the bitbucket TTL bundle is a different serialisation; the portal is what you ground
  against and submit to, so the portal form is the operative one. **No namespace change needed.**

Confidence grades below: **Confirmed** = portal returned it with a definition.
**Likely** = strong indirect evidence, needs one lookup. **No home** = nothing found.

---

## The structural problem underneath the table

The ten branches conflate two different axes, and that is the root cause of the misclassification
you've been seeing:

| Axis | Question it answers | Members currently in `_MDS_CLASSES` | Where it belongs |
|---|---|---|---|
| **Domain** | which subfield is this? | Characterization, Reliability, Economics | `mds:hasDomain` — already emitted, already using the six canonical domains |
| **Entity kind** | what sort of thing is this? | Material, Measurement, Process, Device, Sample | `rdfs:subClassOf` — the class hierarchy |

`ontology.py:433` already declares the six canonical MDS domains
(`Expo`, `Manufact`, `Charact`, `BuildEnv`, `Geo`, `Chem`) and uses them for `hasDomain`. They
live under `mdsdom/` and they are real. The class hierarchy should carry **entity kind only**.

This is why `surface passivation layer` classifies as Characterization (via the substring
"surface") when it is plainly a Material, and why `contact resistance` lands on Measurement via
"resistance". A concept can be a Material *in* the Characterization domain — those are not
competing answers, and forcing them into one axis guarantees wrong ones.

**Recommendation: drop Characterization, Reliability and Economics from the class hierarchy
entirely.** They are domain facets, already expressible on `hasDomain`. That takes the branch
set from ten to a coherent six.

---

## The mapping table

| # | Kweave branch | Verdict | Proposed target | Evidence / note |
|---|---|---|---|---|
| 1 | `mds:Material` | **Confirmed** | **keep `mds/Material`** | Portal: *"A Material Artifact that is a solid substance, and is used as a precursor or input to a manufacturing process in order to produce a finished product."* Exactly the sense Kweave uses. No change. |
| 2 | `mds:Measurement` | **Confirmed**, but see note | **split** — see §Measurement below | Portal: *"A measurement is an analytical result from a study about a sample and some of its properties."* That is a **result**, not a **quantity**. Kweave files efficiency, voltage, fill factor here — those are properties, not results. |
| 3 | `mds:Characterization` | **Confirmed, wrong namespace** | **`mdsdom/Charact`**, and move it off the class hierarchy onto `hasDomain` | Portal returned `https://cwrusdle.bitbucket.io/mdsdom/Charact` for label "Characterization". Matches `_MDS_DOMAINS` at `ontology.py:433`. |
| 4 | `mds:Process` | **No home under that name** | **`mds/ManufacturingMethod`** | Confirmed real. Portal: *"The process that produced the sample (e.g., LPBF, DIW, Casting etc)"*. Real sibling process classes also cached: `Coating`, `Etching`, `Annealing`, `ChemicalSynthesis`, `ThermalAtomicLayerDeposition`, `Illumination`. Alternative: use domain `mdsdom/Manufact` instead if you'd rather processes be a domain facet. |
| 5 | `mds:Device` | **No home** | **needs your call** — see §Device below | `mds/Equipment` is confirmed but means *instruments* (*"solar simulators, inverters, imaging…"*), not the artefact under study. `mds/PhotovoltaicModule` is confirmed but too narrow to be a branch. |
| 6 | `mds:Sample` | **Likely** | **`mds/Sample`** — confirm with one lookup | Listed as a top-level branch in the published docs and declared in the TTL bundle. Not in the cache because nothing searched for it. Confirmed sample-kind siblings cached: `Substrate`, `Wafer`, `Part`, `Crystal`. |
| 7 | `mds:Reliability` | **No home** | **retire from the hierarchy**; express as domain `mdsdom:Expo` | Nothing named Reliability. Nearest confirmed terms are `ThermalStability` and `HighlyAcceleratedLifetimeTestingSystem` — both leaves, not branches. Degradation/stress/exposure concepts belong to the **Exposure** domain. |
| 8 | `mds:Economics` | **No home** | **retire from the hierarchy**; mint under `kw:` if you still need the grouping | Nothing found. Cache has `Supplier` and `Manufacturer` (organisations), not an economics branch. MDS-Onto has no economics region — this is a legitimate gap, and per your policy that means CCO fallback or a `kw:` mint, **not** a mint inside `mds:`. |
| 9 | `mds:ResearchPublication` | **No home** | **CCO `InformationContentEntity`, or `kw:ResearchPublication`** | Nothing found in MDS-Onto. This is the clearest case for the CCO rung of the fallback ladder. |
| 10 | `mds:Concept` | **Not real — never was** | **delete** | The catch-all absorbing 41% of concepts. Replace with an explicit unplaced report (Phase 1.3). |

### Resulting branch set, if you take the recommendation

Five real MDS-Onto classes carrying entity kind:

```
mds/Material              solid substances, layers, pastes, coatings
mds/Property              measured quantities  (efficiency, Voc, fill factor…)
mds/Measurement           analytical results of a study
mds/ManufacturingMethod   processes, treatments, depositions
mds/Sample                wafers, substrates, specimens          [confirm]
```

Plus one open decision (Device), and everything else expressed on `hasDomain` against the six
real domains — `mdsdom:{Expo, Manufact, Charact, BuildEnv, Geo, Chem}`.

---

## §Measurement — the split worth making

`mds/Measurement` is defined as an analytical *result*. `mds/Property` is also confirmed real,
defined as *"The specific property being measured from a given study type"*. Kweave's
`_CLASS_RULES` currently sends both senses to Measurement:

| Concept | Currently | Should be |
|---|---|---|
| cell efficiency, open-circuit voltage, fill factor, resistivity | `mds:Measurement` | `mds/Property` |
| "the measured PCE of 22.4% reported in Table 2" | `mds:Measurement` | `mds/Measurement` |

Most of what Kweave extracts is the first kind. Sending it to `mds/Property` is both more
accurate and better aligned with the confirmed sibling terms already cached (`Absorbance`,
`Resistance`, `YoungModulus`, `Irradiance`, `CellEfficiency` — all properties).

## §Device — needs your domain judgement

This is the one row I can't resolve from evidence. Kweave's Device keywords are architecture,
geometry, busbar, finger, grid, cell, module, tandem, bifacial — the artefact being studied.
Three options:

1. **`mds/PhotovoltaicModule`** — confirmed real, but wrong granularity: a busbar is not a module.
2. **`mds/Part`** — confirmed real (*"a connected material that forms a functional element"*).
   Generic enough to cover fingers, busbars, grids; arguably right, arguably a stretch since its
   definition is written for additive manufacturing.
3. **`mds/Equipment`** — confirmed, but means instruments. Wrong sense; do not use.
4. **Fold into `mds/Material`** and let `hasDomain = BuildEnv` carry the device-ness.

My weak preference is (2) `mds/Part`, with (4) as the honest fallback if `Part`'s definition
reads as too additive-manufacturing-specific to you. You know the vocabulary better than the
definition strings do.

---

## Three lookups that close the remaining gaps

Everything above is settled except three terms the local cache never happened to query. One
portal search each:

```
mds/Sample          expected: confirms row 6
mds/Part            expected: confirms the Device recommendation
mdsdom/Expo         expected: confirms the Exposure domain IRI for row 7
```

Note `MDSONTO_API_KEY` now defaults to empty (the hardcoded key was removed on 2026-08-09), so
this needs a rotated key in `.env` first — which is outstanding anyway.

---

## What implementation looks like once approved

1. Add `mdsdom` to the namespace registry in `config.py:276` — it is a real MDS namespace the
   code currently doesn't know exists.
2. Rewrite `_MDS_CLASSES` to the five (or six) approved targets.
3. Delete `_CLASS_PARENTS` — the MDS-Onto classes bring their own parents; Kweave should not be
   re-parenting terms it doesn't own.
4. Attach with `rdfs:subClassOf`, not `skos:exactMatch`. Keep `exactMatch` as an *additional*
   annotation where a portal match exists, but the subsumption is what makes the claim true.
5. `_CLASS_UPPER_PARENTS` (the BFO block at `ontology.py:255`) can be **deleted** — real
   MDS-Onto terms carry BFO grounding transitively through PMDco. Per your policy, Kweave then
   emits no BFO IRIs of its own.
6. Concepts that match nothing go to an unplaced report, not to a catch-all.

Item 5 is the part that makes the earlier BFO objection moot: you get the grounding without the
complexity, because you're reusing terms that already have it.

---

## Footnote: two MDS-Onto quirks worth knowing

- The portal serves both `mds/Measurement` and `mds/measurement` (lowercase). Case-collision in
  the source ontology, not in your code — but worth normalising on lookup so you don't
  round-trip the wrong one.
- Several cached definitions are visibly copy-pasted from the wrong domain — `ThermalStability`
  is defined as *"Stability of a water body and its resistance to mixing"*. Reuse the IRI;
  don't trust every definition string you pull down.

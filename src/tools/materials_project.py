"""Materials Project (materialsproject.org) lookups for enrichment: computed properties of the crystalline
material a class names, attached to the class as annotations (never as mapping candidates).

A name is looked up when it is a Materials Project id (mp-149), a chemical formula (TiO2, CdTe, Si3N4), an element
name (silicon), or either of the last two followed by a material-form word (TiO2 layer, silicon wafer). All-capital
names without digits (PV, BSF, PERC, UV) are acronyms here, not formulas, and molecular gases and liquids are
skipped. Entries come from the summary endpoint, most stable first. Needs MATERIALS_PROJECT_API_KEY in .env.
"""
import re
from functools import lru_cache

import requests

from src.config import MATERIALS_PROJECT, secret

ELEMENTS = ("H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb "
            "Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf "
            "Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu").split()
NAMES = dict(zip(
    ("hydrogen helium lithium beryllium boron carbon nitrogen oxygen fluorine neon sodium magnesium aluminium silicon "
     "phosphorus sulfur chlorine argon potassium calcium scandium titanium vanadium chromium manganese iron cobalt "
     "nickel copper zinc gallium germanium arsenic selenium bromine krypton rubidium strontium yttrium zirconium "
     "niobium molybdenum technetium ruthenium rhodium palladium silver cadmium indium tin antimony tellurium iodine "
     "xenon caesium barium lanthanum cerium praseodymium neodymium promethium samarium europium gadolinium terbium "
     "dysprosium holmium erbium thulium ytterbium lutetium hafnium tantalum tungsten rhenium osmium iridium platinum "
     "gold mercury thallium lead bismuth polonium astatine radon francium radium actinium thorium protactinium "
     "uranium neptunium plutonium").split(), ELEMENTS), aluminum="Al", sulphur="S", cesium="Cs")
VOLATILE = {"H", "He", "N", "O", "F", "Ne", "Cl", "Ar", "Kr", "Xe", "Rn"}  # a formula of only these is a gas or water
MOLECULAR = {"CO2", "CH4", "SiH4", "Si2H6", "PH3", "B2H6", "SF6", "CF4", "NF3", "NH3", "N2O", "HCl", "HNO3",
             "H2SO4", "H3PO4", "C2H6", "C2H4"}  # process gases and liquids: Materials Project has only their solids
FORMS = ("thin film", "film", "layer", "wafer", "substrate", "coating", "single crystal", "crystal", "powder",
         "nanoparticles", "nanoparticle", "particles", "foil")  # "thin film" before "film"
FIELDS = ("material_id,formula_pretty,symmetry,energy_above_hull,is_stable,theoretical,formation_energy_per_atom,"
          "band_gap,is_gap_direct,is_metal,density,volume,nsites,bulk_modulus,shear_modulus")
_TOKEN = re.compile(r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?")


def formula(text: str) -> str | None:
    """`text` as a chemical formula the Materials Project can search, or None."""
    t = text.strip()
    if not re.fullmatch(r"(?:[A-Z][a-z]?(?:\d+(?:\.\d+)?)?)+", t) or not re.search(r"[a-z\d]", t):
        return None  # not element symbols and counts, or all capitals without digits (an acronym)
    symbols = [m.group(1) for m in _TOKEN.finditer(t)]
    if any(s not in ELEMENTS for s in symbols) or len(symbols) != len(set(symbols)):
        return None
    return None if set(symbols) <= VOLATILE or t in MOLECULAR else t


def lookup_key(name: str) -> tuple[str, str] | None:
    """('material_ids', 'mp-149') or ('formula', 'Si') for a class name, or None when it names no crystalline
    material."""
    t = " ".join(name.split())
    if re.fullmatch(r"mp-\d+", t.lower()):
        return "material_ids", t.lower()
    form = next((f for f in FORMS if t.lower().endswith(" " + f)), None)
    if form:
        t = t[:-len(form) - 1]
    symbol = NAMES.get(t.lower())
    if symbol:
        return None if symbol in VOLATILE else ("formula", symbol)
    f = formula(t)
    return ("formula", f) if f else None


def _get(path: str, params: dict) -> dict:
    r = requests.get(MATERIALS_PROJECT["base_url"].rstrip("/") + path, params=params, timeout=60,
                     headers={"X-API-KEY": secret("MATERIALS_PROJECT_API_KEY") or ""})
    r.raise_for_status()
    return r.json()


@lru_cache
def database_version() -> str | None:
    try:
        return _get("/heartbeat", {}).get("db_version")
    except requests.RequestException:
        return None


def _num(x, digits: int = 4):
    return round(x, digits) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _record(d: dict) -> dict:
    sym, n, mid = d.get("symmetry") or {}, d.get("nsites"), str(d["material_id"])
    return {"material_id": mid, "url": f"https://materialsproject.org/materials/{mid}",
            "formula": d.get("formula_pretty"), "crystal_system": sym.get("crystal_system"),
            "space_group": sym.get("symbol"), "energy_above_hull": _num(d.get("energy_above_hull")),
            "is_stable": d.get("is_stable"), "theoretical": d.get("theoretical"),
            "formation_energy_per_atom": _num(d.get("formation_energy_per_atom")), "band_gap": _num(d.get("band_gap")),
            "is_gap_direct": d.get("is_gap_direct"), "is_metal": d.get("is_metal"), "density": _num(d.get("density")),
            "volume_per_atom": _num(d["volume"] / n) if d.get("volume") and n else None,
            "bulk_modulus": _num((d.get("bulk_modulus") or {}).get("vrh"), 2),
            "shear_modulus": _num((d.get("shear_modulus") or {}).get("vrh"), 2)}


def search(kind: str, value: str, limit: int) -> list[dict]:
    """Entries for a formula (most stable first, within max_energy_above_hull) or a material id."""
    docs = _get("/materials/summary/", {kind: value, "deprecated": "false", "_fields": FIELDS,
                                        "_limit": 100}).get("data", [])
    if kind == "formula":
        cap = MATERIALS_PROJECT["max_energy_above_hull"]
        docs = sorted((d for d in docs if d.get("energy_above_hull") is not None and d["energy_above_hull"] <= cap),
                      key=lambda d: (d["energy_above_hull"], str(d["material_id"])))
    return [_record(d) for d in docs[:limit]]

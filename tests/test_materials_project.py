"""Only names of crystalline materials are looked up in the Materials Project; acronyms and gases are not."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.tools.materials_project import ELEMENTS, NAMES, lookup_key


def test_formulas_element_names_and_material_forms():
    assert lookup_key("TiO2") == ("formula", "TiO2")
    assert lookup_key("CdTe") == ("formula", "CdTe")
    assert lookup_key("Si3N4") == ("formula", "Si3N4")
    assert lookup_key("Al2O3 thin film") == ("formula", "Al2O3")
    assert lookup_key("Silicon wafer") == ("formula", "Si")
    assert lookup_key("aluminum") == ("formula", "Al")
    assert lookup_key("mp-149") == ("material_ids", "mp-149")


def test_acronyms_gases_and_non_stoichiometric_names_are_skipped():
    for name in ("PV", "UV", "BSF", "PERC", "LCOE", "IR", "Voc", "Isc", "SiNx", "a-Si:H", "ITO",
                 "hydrogen", "H2O", "SiH4", "CO2", "solar cell", "silicon solar cell", "TiO2 layer stack"):
        assert lookup_key(name) is None, name


def test_every_element_has_a_name():
    assert len(ELEMENTS) == 94 and set(NAMES.values()) == set(ELEMENTS)

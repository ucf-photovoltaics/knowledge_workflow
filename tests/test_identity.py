"""Concepts that end up with the same name are folded into one at normalization."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.agents.normalization import NormalizationAgent


def test_groups_with_the_same_final_label_are_one_concept():
    groups = [{"members": [("P1", {"id": "c1", "label": "boron-diffused emitter", "type": "material"}),
                           ("P1", {"id": "c2", "label": "p+ emitter", "type": "material"})],
               "label": "boron-doped emitter"},  # name the model gave a merged cluster
              {"members": [("P2", {"id": "c7", "label": "boron-doped emitters", "type": "material"})], "label": None}]
    concepts, cmap = NormalizationAgent._canonical(groups)
    assert [c["label"] for c in concepts] == ["boron-doped emitter"]
    assert set(cmap.values()) == {"k1"} and concepts[0]["papers"] == ["P1", "P2"]

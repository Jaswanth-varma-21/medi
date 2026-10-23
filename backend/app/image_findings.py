"""Maps image-model finding names to knowledge-base entries so flagged image findings can be explained and verified.

A name with no safe match returns None: the finding is then shown with 'no evidence found' instead of a guess.
"""
from .agents.analysis_agent import find_matches

# Model label -> phrase the knowledge base understands. Labels missing here are tried as-is.
ALIASES = {
    "effusion": "pleural effusion",
    "edema": "pulmonary edema",
    "infiltration": "infiltrate",
    "mass": "pulmonary mass",
    "nodule": "pulmonary nodule",
    "pleural_thickening": "pleural thickening",
    "lung opacity": "opacity",
    "emphysema": "emphysema",
}


def kb_entry(label: str, kb):
    key = label.strip().lower().replace("_", " ")
    phrase = ALIASES.get(key.replace(" ", "_"), ALIASES.get(key, key))
    hits = find_matches(phrase, kb)
    return hits[0][2] if hits else None

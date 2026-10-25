"""Optional spaCy enrichment: adds ORG / PERSON / DATE entities when a model is installed.

The pipeline works without spaCy; this module degrades gracefully.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from .models import Entity, ExtractedDocument

LOGGER = logging.getLogger(__name__)

MODELS = {"en": "en_core_web_sm", "fr": "fr_core_news_sm"}
KEPT_LABELS = {"ORG", "PERSON", "PER", "GPE", "LOC"}


@lru_cache(maxsize=4)
def _load_model(language: str) -> Any:
    try:
        import spacy
    except ImportError:
        LOGGER.info("spaCy not installed; skipping NER enrichment")
        return None
    name = MODELS.get(language, MODELS["en"])
    try:
        return spacy.load(name, disable=["lemmatizer"])
    except OSError:
        LOGGER.info("spaCy model '%s' missing (python -m spacy download %s)", name, name)
        return None


def enrich_with_spacy(doc: ExtractedDocument, text: str) -> ExtractedDocument:
    """Return ``doc`` with extra named entities found by spaCy (no-op if unavailable)."""
    nlp = _load_model(doc.language)
    if nlp is None:
        return doc
    known = {(e.text.lower(), e.label) for e in doc.entities}
    added: list[Entity] = []
    for ent in nlp(text).ents:
        label = "PERSON" if ent.label_ == "PER" else ent.label_
        if ent.label_ not in KEPT_LABELS:
            continue
        key = (ent.text.lower(), label)
        if key not in known:
            known.add(key)
            added.append(Entity(text=ent.text, label=label))
    return doc.model_copy(update={"entities": [*doc.entities, *added]})

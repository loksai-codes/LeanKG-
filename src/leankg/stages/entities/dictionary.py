"""Dictionary entity stage.

Two matching strategies, chosen by the language profile (``profile.dict_strategy``):

* ``"phrase"`` — spaCy ``PhraseMatcher`` on ``LOWER`` over tokens (good for languages
  with spaces).
* ``"chars"`` — character-level Aho-Corasick on normalized text with a map back to the
  original offsets (robust to tokenizers that split compounds differently from the
  dictionary, e.g. Sudachi on 油圧ポンプ).

Longest match wins; overlaps are resolved deterministically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar

from leankg.domain.pack import DomainPack
from leankg.models import Document, Mention, Sentence
from leankg.stages.base import BaseStage
from leankg.stages.entities.common import add_mentions, longest_non_overlapping, make_mention
from leankg.stages.preprocess import ensure_spacy_doc, nlp_for

log = logging.getLogger(__name__)


@dataclass
class ConceptRef:
    ontology_id: str
    type: str


@dataclass
class _Lexicon:
    """Normalized surface → concepts, for one language."""

    surfaces: list[str] = field(default_factory=list)
    refs: list[list[ConceptRef]] = field(default_factory=list)
    index: dict[str, int] = field(default_factory=dict)

    def add(self, key: str, ref: ConceptRef) -> None:
        if key not in self.index:
            self.index[key] = len(self.surfaces)
            self.surfaces.append(key)
            self.refs.append([])
        refs = self.refs[self.index[key]]
        if all(r.ontology_id != ref.ontology_id for r in refs):
            refs.append(ref)


def build_lexicon(pack: DomainPack, lang: str, profile: Any) -> tuple[_Lexicon, list[str]]:
    """Normalized lexicon plus the raw surface variants (for phrase matching)."""
    lex = _Lexicon()
    raw: list[str] = []
    for term in pack.terms_for(lang):
        for surface in term.surfaces():
            for variant in profile.term_variants(surface):
                key = profile.normalize(variant)
                if not key:
                    continue
                lex.add(key, ConceptRef(term.id, term.type))
                raw.append(variant)
    return lex, raw


class _CharMatcher:
    def __init__(self, lex: _Lexicon, profile: Any) -> None:
        import ahocorasick

        self.lex = lex
        self.profile = profile
        self.automaton = ahocorasick.Automaton()
        for idx, key in enumerate(lex.surfaces):
            if not profile.accept_dict_key(key):
                log.debug("skipping 1-char dictionary key %r", key)
                continue
            self.automaton.add_word(key, idx)
        self.empty = len(self.automaton) == 0
        if not self.empty:
            self.automaton.make_automaton()

    def find(self, sent: Sentence) -> list[tuple[int, int, int]]:
        if self.empty:
            return []
        nt = self.profile.normalize_map(sent.text)
        hits = []
        for end_idx, idx in self.automaton.iter(nt.text):
            key = self.lex.surfaces[idx]
            start = end_idx - len(key) + 1
            hits.append((start, end_idx + 1, idx))
        out = []
        for s, e, idx in longest_non_overlapping(hits):
            os_, oe = nt.to_original(s, e)
            out.append((os_, oe, idx))
        return out


class _PhraseMatcher:
    def __init__(self, lex: _Lexicon, raw: list[str], profile: Any, nlp: Any) -> None:
        from spacy.matcher import PhraseMatcher

        self.lex = lex
        self.profile = profile
        self.matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        patterns: dict[int, list[Any]] = {}
        for variant in raw:
            idx = lex.index.get(profile.normalize(variant))
            if idx is not None:
                patterns.setdefault(idx, []).append(nlp.make_doc(variant))
        for idx, docs in patterns.items():
            self.matcher.add(f"T{idx}", docs)
        self.vocab = nlp.vocab

    def find(self, sdoc: Any) -> list[tuple[int, int, int]]:
        hits = []
        for match_id, start, end in self.matcher(sdoc):
            idx = int(self.vocab.strings[match_id][1:])
            span = sdoc[start:end]
            hits.append((span.start_char, span.end_char, idx))
        return longest_non_overlapping(hits)


class DictionaryStage(BaseStage):
    """Cheapest entity stage: exact dictionary terms from the pack."""

    name: ClassVar[str] = "dictionary"

    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        self._matchers: dict[str, Any] = {}

    def _matcher(self, lang: str) -> Any:
        if lang not in self._matchers:
            pack = self.ctx.require_pack()
            profile = self.ctx.get_profiles().get(lang)
            lex, raw = build_lexicon(pack, lang, profile)
            if getattr(profile, "dict_strategy", "phrase") == "chars":
                self._matchers[lang] = _CharMatcher(lex, profile)
            else:
                self._matchers[lang] = _PhraseMatcher(lex, raw, profile, nlp_for(self.ctx, lang))
        return self._matchers[lang]

    def find(self, doc: Document, sent: Sentence) -> list[Mention]:
        matcher = self._matcher(sent.lang)
        profile = self.ctx.get_profiles().get(sent.lang)
        if isinstance(matcher, _CharMatcher):
            hits = matcher.find(sent)
        else:
            hits = matcher.find(ensure_spacy_doc(self.ctx, sent))
        prior = self.config.scoring.prior("dict")
        mentions = []
        for start, end, idx in hits:
            refs = matcher.lex.refs[idx]
            m = make_mention(
                doc,
                sent,
                start,
                end,
                refs[0].type,
                "dict",
                prior,
                normalized=profile.normalize(sent.text[start:end]),
                ontology_id=refs[0].ontology_id,
            )
            if len(refs) > 1:
                from leankg.models import LinkCandidate

                m.candidates = [
                    LinkCandidate(entity_id="", ontology_id=r.ontology_id, score=1.0, method="dict")
                    for r in refs
                ]
            mentions.append(m)
        return mentions

    def process(self, doc: Document) -> Document:
        new: list[Mention] = []
        for sent in doc.sentences():
            new.extend(self.find(doc, sent))
        add_mentions(doc, new)
        return doc

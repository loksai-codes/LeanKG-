"""Statistical NER stage: spaCy/GiNZA NER + extra spaCy pipelines (e.g. scispaCy).

Model labels are mapped to ontology types with ``models.yaml``'s ``ner_label_map``;
unmapped labels are ignored. Extra pipelines (``extra_spacy``) that aren't installed are
skipped with a warning in the RunReport.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, ClassVar

from leankg.models import Document, Mention, Sentence
from leankg.stages.base import BaseStage, StageContext
from leankg.stages.entities.common import add_mentions, make_mention

log = logging.getLogger(__name__)


class NerStage(BaseStage):
    name: ClassVar[str] = "ner"
    _extra_cache: ClassVar[dict[str, Any]] = {}

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._warned: set[str] = set()

    def _warn(self, msg: str) -> None:
        if msg not in self._warned:
            self._warned.add(msg)
            log.warning(msg)
            self.ctx.report.warnings.append(msg)

    def _extra_nlps(self, lang: str) -> list[Any]:
        names = self.ctx.require_pack().models.extra_spacy.get(lang, [])
        out = []
        for name in names:
            if name not in self._extra_cache:
                try:
                    import spacy

                    self._extra_cache[name] = spacy.load(name)
                except (OSError, ImportError) as exc:
                    self._extra_cache[name] = None
                    log.debug("could not load %s: %s", name, exc)
            if self._extra_cache[name] is None:
                self._warn(f"ner: spaCy model {name!r} not installed; skipped")
            else:
                out.append(self._extra_cache[name])
        return out

    def _from_ents(
        self, doc: Document, sent: Sentence, ents: Any, label_map: dict[str, str]
    ) -> list[Mention]:
        prior = self.config.scoring.prior("ner")
        profile = self.ctx.get_profiles().get(sent.lang)
        out = []
        for ent in ents:
            type_ = label_map.get(ent.label_)
            if type_ is None:
                continue
            out.append(
                make_mention(
                    doc,
                    sent,
                    ent.start_char,
                    ent.end_char,
                    type_,
                    "ner",
                    prior,
                    normalized=profile.normalize(ent.text),
                    pattern_id=f"ner:{ent.label_}",
                )
            )
        return out

    def process(self, doc: Document) -> Document:
        pack = self.ctx.require_pack()
        by_lang: dict[str, list[Sentence]] = defaultdict(list)
        for sent in doc.sentences():
            by_lang[sent.lang].append(sent)
        new: list[Mention] = []
        for lang, sents in by_lang.items():
            label_map = pack.models.ner_label_map.get(lang, {})
            if not label_map:
                continue
            for sent in sents:
                sdoc = sent.spacy_doc
                if sdoc is not None and sdoc.has_annotation("ENT_IOB"):
                    new.extend(self._from_ents(doc, sent, sdoc.ents, label_map))
            for nlp in self._extra_nlps(lang):
                for sent, edoc in zip(sents, nlp.pipe(s.text for s in sents), strict=True):
                    new.extend(self._from_ents(doc, sent, edoc.ents, label_map))
        add_mentions(doc, new)
        return doc

"""GLiNER stage (``[gliner]`` extra): zero-shot NER with a multilingual checkpoint.

Runs only on sentences where cheaper stages found fewer than
``[gliner].min_entities_before`` entities, to save CPU. Labels come from the pack
(``models.yaml`` → ``gliner.labels.<lang>``); ``label_lang: auto`` uses each sentence's
language, otherwise the given language's labels are used for every sentence.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from leankg.models import Document, Mention, Sentence
from leankg.stages.base import BaseStage, StageContext
from leankg.stages.entities.common import add_mentions, make_mention

log = logging.getLogger(__name__)


class GlinerStage(BaseStage):
    name: ClassVar[str] = "gliner"
    _models: ClassVar[dict[str, Any]] = {}

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._unavailable: str | None = None

    def model(self) -> Any:
        if self._unavailable is not None:
            return None
        name = self.ctx.require_pack().models.gliner.model
        if not name:
            self._unavailable = "gliner: no model configured in models.yaml"
        elif name not in self._models:
            try:
                from gliner import GLiNER

                self._models[name] = GLiNER.from_pretrained(name)
            except ImportError:
                self._unavailable = "gliner: [gliner] extra not installed; stage skipped"
            except Exception as exc:  # network / model download problems
                self._unavailable = f"gliner: could not load {name!r}: {exc}"
        if self._unavailable is not None:
            log.warning(self._unavailable)
            self.ctx.report.warnings.append(self._unavailable)
            return None
        return self._models[name]

    def _labels(self, lang: str) -> dict[str, str]:
        settings = self.ctx.require_pack().models.gliner
        label_lang = lang if settings.label_lang == "auto" else settings.label_lang
        return settings.labels.get(label_lang) or settings.labels.get("en", {})

    def _predict(self, model: Any, text: str, labels: list[str], threshold: float) -> list[Any]:
        result: list[Any] = model.predict_entities(text, labels, threshold=threshold)
        return result

    def process(self, doc: Document) -> Document:
        cfg = self.config.gliner
        counts: dict[str, int] = {}
        for m in doc.mentions:
            counts[m.sent_id] = counts.get(m.sent_id, 0) + 1
        todo: list[Sentence] = [
            s for s in doc.sentences() if counts.get(s.id, 0) < cfg.min_entities_before
        ]
        if not todo:
            return doc
        model = self.model()
        if model is None:
            return doc
        settings = self.ctx.require_pack().models.gliner
        threshold = settings.threshold if settings.threshold is not None else cfg.threshold
        new: list[Mention] = []
        for sent in todo:
            label_to_type = {v: k for k, v in self._labels(sent.lang).items()}
            if not label_to_type:
                continue
            profile = self.ctx.get_profiles().get(sent.lang)
            for ent in self._predict(model, sent.text, list(label_to_type), threshold):
                type_ = label_to_type.get(ent["label"])
                if type_ is None or ent["end"] <= ent["start"]:
                    continue
                new.append(
                    make_mention(
                        doc,
                        sent,
                        int(ent["start"]),
                        int(ent["end"]),
                        type_,
                        "gliner",
                        float(ent.get("score", threshold)),
                        normalized=profile.normalize(ent["text"]),
                        pattern_id="gliner",
                    )
                )
        add_mentions(doc, new)
        return doc

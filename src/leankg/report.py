"""Rendering of :class:`~leankg.models.RunReport`."""

from __future__ import annotations

from leankg.models import LangStats, RunReport

_COLUMNS: tuple[tuple[str, str], ...] = (
    ("docs", "docs"),
    ("sentences", "sents"),
    ("mentions", "mentions"),
    ("entities", "entities"),
    ("triples", "triples"),
    ("triples_negative", "neg"),
    ("hard_case_rate", "hard%"),
    ("llm_call_rate", "llm%"),
    ("cache_hit_rate", "cache%"),
    ("tokens_in", "tok_in"),
    ("tokens_out", "tok_out"),
    ("est_cost_usd", "cost$"),
)


def _fmt(stats: LangStats, attr: str) -> str:
    value = getattr(stats, attr)
    if attr.endswith("_rate"):
        return f"{value * 100:.1f}"
    if attr == "est_cost_usd":
        return f"{value:.4f}"
    return str(value)


def render_report(report: RunReport) -> str:
    """Plain-text table: one row per language plus the total."""
    header = ["lang", *(label for _, label in _COLUMNS)]
    rows = [
        [code, *(_fmt(s, a) for a, _ in _COLUMNS)] for code, s in sorted(report.by_lang.items())
    ]
    rows.append(["all", *(_fmt(report, a) for a, _ in _COLUMNS)])
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]
    lines = [
        f"leankg run — domain={report.domain or '-'} llm={report.provider}"
        + (f" ({report.model})" if report.model else ""),
        "  ".join(h.rjust(w) for h, w in zip(header, widths, strict=True)),
    ]
    lines += ["  ".join(c.rjust(w) for c, w in zip(r, widths, strict=True)) for r in rows]
    lines.append(
        f"duration {report.duration_s:.2f}s · {report.docs_per_min:.1f} docs/min · "
        f"llm requests {report.llm_requests} · cost/1k docs ${report.cost_per_1k_docs_usd:.4f}"
    )
    if report.budget_exhausted:
        lines.append("LLM budget exhausted: remaining hard cases kept as unverified.")
    lines += [f"warning: {w}" for w in report.warnings]
    return "\n".join(lines)

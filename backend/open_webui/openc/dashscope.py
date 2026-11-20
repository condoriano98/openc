"""Alibaba Cloud Model Studio (DashScope) request/response helpers.

DashScope's OpenAI-compatible endpoint accepts extra top-level fields:

* ``enable_thinking`` / ``thinking_budget``: hybrid-thinking Qwen models
  (qwen-plus, qwen-flash, qwen3-*) stream ``reasoning_content``. Open WebUI
  already renders that as a collapsible thinking block.
* ``enable_search`` / ``search_options``: Qwen's built-in web search.
"""

from __future__ import annotations

from typing import Any

MAX_THINKING_BUDGET = 81920

SEARCH_OPTIONS = {
    'forced_search': True,
    'enable_source': True,
    'enable_citation': True,
    'citation_format': '[<number>]',
}


def apply_dashscope_params(payload: dict, features: dict | None) -> dict:
    """Return ``payload`` with DashScope-specific fields set from chat features."""
    features = features or {}
    payload = dict(payload)

    thinking = features.get('thinking')
    if thinking is True:
        payload['enable_thinking'] = True
        budget = features.get('thinking_budget')
        if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
            payload['thinking_budget'] = int(min(budget, MAX_THINKING_BUDGET))
    elif thinking is False:
        payload['enable_thinking'] = False

    if features.get('qwen_search'):
        payload['enable_search'] = True
        payload['search_options'] = dict(SEARCH_OPTIONS)

    return payload


def search_info_to_sources(search_info: Any, seen: list | None = None) -> list[dict]:
    """Convert DashScope ``search_info`` into Open WebUI ``source`` event payloads.

    ``seen`` is a list of URLs that have already been emitted; it is updated in
    place so repeated chunks don't produce duplicate sources.
    """
    if not isinstance(search_info, dict):
        return []
    results = search_info.get('search_results') or []
    seen = seen if seen is not None else []

    sources = []
    for result in sorted(
        (r for r in results if isinstance(r, dict)),
        key=lambda r: r.get('index') if isinstance(r.get('index'), int) else 1 << 30,
    ):
        url = result.get('url') or ''
        if not url or url in seen:
            continue
        seen.append(url)
        title = result.get('title') or result.get('site_name') or url
        sources.append(
            {
                'source': {'name': title, 'url': url},
                'document': [title],
                'metadata': [{'source': url, 'name': title}],
            }
        )
    return sources

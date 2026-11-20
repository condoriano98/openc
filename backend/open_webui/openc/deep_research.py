"""Deep Research mode (inspired by ChatGPT Deep Research, Kimi Researcher and
Claude Research).

When the composer's "Research" toggle is on, OpenC runs a multi-round research
loop before the chat model answers:

1. plan search queries for the question (and for gaps found so far),
2. run them on the admin-configured web search engine,
3. load the new pages and extract cited learnings,
4. repeat until the model says it has enough, or the round limit is hit.

The collected sources are then numbered, emitted as citation sources, and given
to the chat model with instructions to write a structured, cited report. The
final report streams through Open WebUI's normal pipeline.

The loop itself (``run_deep_research``) only talks to injected callables, so it
can be tested without a model or the network.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

MAX_ROUNDS = int(os.getenv('OPENC_DEEP_RESEARCH_MAX_ROUNDS', '3'))
QUERIES_PER_ROUND = int(os.getenv('OPENC_DEEP_RESEARCH_QUERIES_PER_ROUND', '4'))
PAGES_PER_ROUND = int(os.getenv('OPENC_DEEP_RESEARCH_PAGES_PER_ROUND', '6'))
MAX_SOURCES = int(os.getenv('OPENC_DEEP_RESEARCH_MAX_SOURCES', '20'))
CHARS_PER_SOURCE = int(os.getenv('OPENC_DEEP_RESEARCH_CHARS_PER_SOURCE', '6000'))

LLM = Callable[[list[dict]], Awaitable[str]]
Search = Callable[[str], Awaitable[list[dict]]]  # -> [{url, title, snippet}]
Fetch = Callable[[list[str]], Awaitable[list[dict]]]  # -> [{url, title, content}]
Emit = Callable[[dict], Awaitable[None]]


@dataclass
class Source:
    index: int
    url: str
    title: str
    content: str


@dataclass
class ResearchResult:
    question: str
    sources: list[Source] = field(default_factory=list)
    learnings: list[str] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    rounds: int = 0


PLAN_PROMPT = """You are planning web research to answer the question below thoroughly.
{context}
Write up to {n} diverse, specific web search queries that would find the most useful
missing information. Vary angles (definitions, recent data, comparisons, criticism,
primary sources). Do not repeat earlier queries.

Question: {question}

Reply with JSON only: {{"queries": ["...", "..."]}}"""

LEARN_PROMPT = """You are a research analyst. Read the new sources and extract the key facts
that help answer the question. Cite each fact with the source number in square brackets,
for example "Revenue grew 12% in 2025 [3]". Only use the sources given.

Question: {question}

Learnings so far:
{learnings}

New sources:
{sources}

Reply with JSON only:
{{"learnings": ["fact [n]", ...],
  "gaps": ["what is still unknown or contested", ...],
  "done": true if the question can now be answered thoroughly, otherwise false}}"""

REPORT_INSTRUCTIONS = """<deep_research>
You are writing a Deep Research report. Answer the user's latest question with a
thorough, well-structured report in Markdown, based on the research below.

Requirements:
- Start with a short "Summary" section giving the direct answer.
- Then organise the findings into clear sections with headings.
- Cite every factual claim inline with the source number, e.g. [2] or [1][4].
  Only cite the numbered sources listed below, and never invent sources.
- Point out disagreements between sources and anything that remains uncertain.
- End with a "Sources" section listing each cited source as "[n] Title - URL".

Research question: {question}

Key learnings:
{learnings}

Sources:
{sources}
</deep_research>"""


def parse_json_object(text: str) -> dict:
    """Extract the last JSON object from a model reply (tolerates code fences and prose)."""
    if not text:
        return {}
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    candidates = re.findall(r'\{.*\}', text, flags=re.S)
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            continue
    return {}


def _status(description: str, done: bool = False, **extra) -> dict:
    return {
        'type': 'status',
        'data': {'action': 'deep_research', 'description': description, 'done': done, **extra},
    }


def _clean_list(values: Any, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    out = []
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip() not in out:
            out.append(value.strip())
        if len(out) >= limit:
            break
    return out


async def _plan(llm: LLM, question: str, result: ResearchResult, gaps: list[str]) -> list[str]:
    context = ''
    if result.queries:
        context += '\nEarlier queries:\n' + '\n'.join(f'- {q}' for q in result.queries) + '\n'
    if gaps:
        context += '\nOpen gaps to investigate:\n' + '\n'.join(f'- {g}' for g in gaps) + '\n'
    reply = await llm(
        [{'role': 'user', 'content': PLAN_PROMPT.format(context=context, n=QUERIES_PER_ROUND, question=question)}]
    )
    queries = _clean_list(parse_json_object(reply).get('queries'), QUERIES_PER_ROUND)
    return [q for q in queries if q not in result.queries]


async def run_deep_research(question: str, llm: LLM, search: Search, fetch: Fetch, emit: Emit) -> ResearchResult:
    result = ResearchResult(question=question)
    seen_urls: set[str] = set()
    gaps: list[str] = []

    for round_no in range(1, MAX_ROUNDS + 1):
        if len(result.sources) >= MAX_SOURCES:
            break

        await emit(_status(f'Planning research (round {round_no}/{MAX_ROUNDS})'))
        try:
            queries = await _plan(llm, question, result, gaps)
        except Exception as e:
            log.warning('deep research planning failed: %s', e)
            queries = []
        if not queries and round_no == 1:
            queries = [question]
        if not queries:
            break
        result.queries.extend(queries)
        result.rounds = round_no

        await emit(
            {
                'type': 'status',
                'data': {'action': 'web_search_queries_generated', 'queries': queries, 'done': False},
            }
        )

        search_results = await asyncio.gather(*(search(q) for q in queries), return_exceptions=True)
        candidates: list[dict] = []
        for items in search_results:
            if isinstance(items, Exception):
                log.warning('deep research search failed: %s', items)
                continue
            for item in items or []:
                url = (item or {}).get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append(item)

        budget = min(PAGES_PER_ROUND, MAX_SOURCES - len(result.sources))
        candidates = candidates[:budget]
        if not candidates:
            await emit(_status(f'No new sources found in round {round_no}'))
            if round_no == 1:
                break
            continue

        await emit(_status(f'Reading {len(candidates)} sources', urls=[c['url'] for c in candidates]))
        try:
            pages = await fetch([c['url'] for c in candidates])
        except Exception as e:
            log.warning('deep research fetch failed: %s', e)
            pages = []
        by_url = {p.get('url'): p for p in pages if p.get('url')}

        new_sources: list[Source] = []
        for candidate in candidates:
            page = by_url.get(candidate['url'], {})
            content = (page.get('content') or candidate.get('snippet') or '').strip()
            if not content:
                continue
            source = Source(
                index=len(result.sources) + 1,
                url=candidate['url'],
                title=(page.get('title') or candidate.get('title') or candidate['url']).strip(),
                content=content[:CHARS_PER_SOURCE],
            )
            result.sources.append(source)
            new_sources.append(source)

        if not new_sources:
            continue

        await emit(_status(f'Analysing sources ({len(result.sources)} total)'))
        try:
            reply = await llm(
                [
                    {
                        'role': 'user',
                        'content': LEARN_PROMPT.format(
                            question=question,
                            learnings='\n'.join(f'- {item}' for item in result.learnings) or '(none yet)',
                            sources=format_sources(new_sources),
                        ),
                    }
                ]
            )
        except Exception as e:
            log.warning('deep research analysis failed: %s', e)
            reply = ''
        analysis = parse_json_object(reply)
        result.learnings.extend(_clean_list(analysis.get('learnings'), 30))
        gaps = _clean_list(analysis.get('gaps'), 5)
        if analysis.get('done') is True:
            break

    await emit(
        _status(
            f'Research complete: {len(result.sources)} sources over {result.rounds} round(s)',
            done=True,
            urls=[s.url for s in result.sources],
        )
    )
    return result


def format_sources(sources: list[Source], max_chars: int | None = None) -> str:
    blocks = []
    for s in sources:
        content = s.content if max_chars is None else s.content[:max_chars]
        blocks.append(f'[{s.index}] {s.title}\nURL: {s.url}\n{content}')
    return '\n\n'.join(blocks)


def build_report_prompt(result: ResearchResult) -> str:
    return REPORT_INSTRUCTIONS.format(
        question=result.question,
        learnings='\n'.join(f'- {item}' for item in result.learnings) or '- (no structured learnings extracted)',
        sources=format_sources(result.sources) or '(no sources could be loaded)',
    )


def source_events(result: ResearchResult) -> list[dict]:
    return [
        {
            'type': 'source',
            'data': {
                'source': {'name': f'[{s.index}] {s.title}', 'url': s.url},
                'document': [s.content[:1500]],
                'metadata': [{'source': s.url, 'name': s.title}],
            },
        }
        for s in result.sources
    ]


# --- Open WebUI integration -------------------------------------------------


async def deep_research_handler(request, form_data: dict, extra_params: dict, user, add_system_message) -> dict:
    """Run the research loop and add the report brief to ``form_data``."""
    from open_webui.models.config import Config
    from open_webui.retrieval.web.utils import get_web_loader
    from open_webui.routers.retrieval import RETRIEVAL_CONFIG_KEYS, search_web
    from open_webui.utils.chat import generate_chat_completion
    from open_webui.utils.misc import get_last_user_message

    emit = extra_params['__event_emitter__']
    question = get_last_user_message(form_data.get('messages', [])) or ''
    if not question.strip():
        return form_data

    config = await Config.get_many(*RETRIEVAL_CONFIG_KEYS.values())
    if not config.get('web.search.enable'):
        await emit(_status('Deep Research needs web search; ask an admin to enable it', done=True, error=True))
        return form_data

    model_id = form_data['model']
    chat_id = extra_params.get('__chat_id__')

    async def llm(messages: list[dict]) -> str:
        res = await generate_chat_completion(
            request,
            form_data={
                'model': model_id,
                'messages': messages,
                'stream': False,
                'metadata': {
                    'task': 'openc_deep_research',
                    'chat_id': chat_id,
                    'features': {'thinking': False},
                },
            },
            user=user,
        )
        if hasattr(res, 'body'):
            raise RuntimeError(res.body.decode('utf-8', 'replace')[:300])
        return res['choices'][0]['message'].get('content') or ''

    async def search(query: str) -> list[dict]:
        items = await search_web(request, config['web.search.engine'], query, user, config=config)
        return [{'url': i.link, 'title': i.title or i.link, 'snippet': i.snippet or ''} for i in items or [] if i.link]

    async def fetch(urls: list[str]) -> list[dict]:
        if config.get('web.search.bypass_web_loader'):
            return []
        docs = await get_web_loader(urls, config).aload()
        pages: dict[str, dict] = {}
        for doc in docs:
            url = doc.metadata.get('source')
            if not url:
                continue
            page = pages.setdefault(url, {'url': url, 'title': doc.metadata.get('title') or url, 'content': ''})
            page['content'] += doc.page_content + '\n'
        return list(pages.values())

    result = await run_deep_research(question, llm, search, fetch, emit)

    for event in source_events(result):
        await emit(event)

    form_data['messages'] = add_system_message(build_report_prompt(result), form_data['messages'])
    return form_data

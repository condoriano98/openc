import asyncio
import json

from open_webui.openc import deep_research as DR


def run(coro):
    return asyncio.run(coro)


class FakeWorld:
    def __init__(self, done_after=2):
        self.events = []
        self.llm_calls = 0
        self.done_after = done_after
        self.analysis_rounds = 0

    async def llm(self, messages):
        self.llm_calls += 1
        prompt = messages[-1]['content']
        if 'search queries' in prompt:
            n = self.llm_calls
            return f'Sure!\n```json\n{json.dumps({"queries": [f"q{n}a", f"q{n}b"]})}\n```'
        self.analysis_rounds += 1
        return json.dumps(
            {
                'learnings': [f'fact {self.analysis_rounds} [1]'],
                'gaps': ['more data'],
                'done': self.analysis_rounds >= self.done_after,
            }
        )

    async def search(self, query):
        # Each query yields a unique page plus one page shared by every query.
        return [
            {'url': f'https://example.com/{query}', 'title': query, 'snippet': 'snip'},
            {'url': 'https://example.com/shared', 'title': 'shared', 'snippet': 'shared snip'},
        ]

    async def fetch(self, urls):
        return [{'url': u, 'title': f'Title {u}', 'content': f'content of {u}'} for u in urls if 'q' in u]

    async def emit(self, event):
        self.events.append(event)


def test_loop_stops_when_model_says_done_and_dedupes_urls():
    world = FakeWorld(done_after=2)
    result = run(DR.run_deep_research('What is X?', world.llm, world.search, world.fetch, world.emit))
    assert result.rounds == 2
    urls = [s.url for s in result.sources]
    assert len(urls) == len(set(urls))
    assert urls.count('https://example.com/shared') == 1
    # The shared page has no fetched content, so it falls back to the snippet.
    shared = next(s for s in result.sources if s.url.endswith('/shared'))
    assert shared.content == 'shared snip'
    assert [s.index for s in result.sources] == list(range(1, len(result.sources) + 1))
    assert result.learnings == ['fact 1 [1]', 'fact 2 [1]']
    assert world.events[-1]['data']['done'] is True


def test_round_limit(monkeypatch):
    monkeypatch.setattr(DR, 'MAX_ROUNDS', 2)
    world = FakeWorld(done_after=99)
    result = run(DR.run_deep_research('Q', world.llm, world.search, world.fetch, world.emit))
    assert result.rounds == 2


def test_falls_back_to_question_when_planning_fails():
    world = FakeWorld()

    async def bad_llm(messages):
        return 'no json here'

    result = run(DR.run_deep_research('Plain question', bad_llm, world.search, world.fetch, world.emit))
    assert result.queries == ['Plain question']
    assert result.sources


def test_report_prompt_and_source_events_are_numbered():
    result = DR.ResearchResult(
        question='Q',
        sources=[DR.Source(1, 'https://a', 'A', 'aaa'), DR.Source(2, 'https://b', 'B', 'bbb')],
        learnings=['x [1]'],
    )
    prompt = DR.build_report_prompt(result)
    assert '[1] A\nURL: https://a' in prompt and '[2] B' in prompt and '- x [1]' in prompt
    events = DR.source_events(result)
    assert [e['data']['source']['url'] for e in events] == ['https://a', 'https://b']


def test_parse_json_object_handles_think_tags_and_prose():
    assert DR.parse_json_object('<think>{"queries": ["bad"]}</think> ok {"queries": ["good"]}') == {
        'queries': ['good']
    }
    assert DR.parse_json_object('nothing') == {}

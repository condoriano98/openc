import asyncio

import pytest

from open_webui.openc import wanx


class FakeResponse:
    def __init__(self, status, body):
        self.status, self.body = status, body

    async def json(self, content_type=None):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, submit, polls):
        self.submit, self.polls, self.calls = submit, list(polls), []

    def post(self, url, json=None, headers=None, ssl=None):
        self.calls.append(('POST', url, json, headers))
        return FakeResponse(*self.submit)

    def get(self, url, headers=None, ssl=None):
        self.calls.append(('GET', url, None, headers))
        return FakeResponse(200, self.polls.pop(0))


@pytest.fixture(autouse=True)
def fast_poll(monkeypatch):
    monkeypatch.setattr(wanx, 'POLL_INTERVAL', 0)


def test_generate_polls_until_success():
    session = FakeSession(
        (200, {'output': {'task_id': 't1', 'task_status': 'PENDING'}}),
        [
            {'output': {'task_status': 'RUNNING'}},
            {'output': {'task_status': 'SUCCEEDED', 'results': [{'url': 'https://img/1.png'}]}},
        ],
    )
    urls = asyncio.run(wanx.generate(session, {'url': '', 'key': 'sk'}, 'a cat', None, 1024, 768, n=9))
    assert urls == ['https://img/1.png']
    method, url, body, headers = session.calls[0]
    assert url == 'https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis'
    assert headers['X-DashScope-Async'] == 'enable' and headers['Authorization'] == 'Bearer sk'
    assert body['model'] == wanx.DEFAULT_MODEL
    assert body['parameters'] == {'size': '1024*768', 'n': 4}
    assert session.calls[1][1].endswith('/tasks/t1')


def test_generate_raises_on_failure_and_http_error():
    failed = FakeSession(
        (200, {'output': {'task_id': 't'}}), [{'output': {'task_status': 'FAILED', 'message': 'bad prompt'}}]
    )
    with pytest.raises(wanx.WanxError, match='bad prompt'):
        asyncio.run(wanx.generate(failed, {'key': 'k'}, 'x', 'wan2.2-t2i-plus', 512, 512))

    http_error = FakeSession((401, {'message': 'Invalid API-key'}), [])
    with pytest.raises(wanx.WanxError, match='Invalid API-key'):
        asyncio.run(wanx.generate(http_error, {'key': 'k'}, 'x', None, 512, 512))


def test_fit_size():
    assert wanx.fit_size('qwen-image', 512, 512) == (1328, 1328)
    assert wanx.fit_size('qwen-image', 1920, 1080) == (1664, 928)
    assert wanx.fit_size('wan2.2-t2i-flash', 256, 4000) == (512, 1440)

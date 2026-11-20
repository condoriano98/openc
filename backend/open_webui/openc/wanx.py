"""Alibaba Cloud Model Studio image generation (Wanx / Qwen-Image).

DashScope's text-to-image API is asynchronous: submit a task, then poll it
until it succeeds and returns temporary image URLs.

    POST {base}/services/aigc/text2image/image-synthesis   (X-DashScope-Async: enable)
    GET  {base}/tasks/{task_id}
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://dashscope-intl.aliyuncs.com/api/v1'
DEFAULT_MODEL = 'wan2.2-t2i-flash'
KNOWN_MODELS = ['wan2.2-t2i-flash', 'wan2.2-t2i-plus', 'wanx2.1-t2i-turbo', 'wanx2.1-t2i-plus', 'qwen-image']
POLL_INTERVAL = 2.0
TIMEOUT_SECONDS = 180


class WanxError(RuntimeError):
    pass


def base_url(url: str | None) -> str:
    return (url or DEFAULT_BASE_URL).rstrip('/')


QWEN_IMAGE_SIZES = [(1664, 928), (1472, 1140), (1328, 1328), (1140, 1472), (928, 1664)]


def fit_size(model: str | None, width: int, height: int) -> tuple[int, int]:
    """Qwen-Image only accepts fixed sizes: pick the one with the closest aspect ratio.
    Wan models accept 512-1440 per side."""
    if (model or '').startswith('qwen-image'):
        ratio = width / max(height, 1)
        return min(QWEN_IMAGE_SIZES, key=lambda wh: abs(wh[0] / wh[1] - ratio))
    return max(512, min(width, 1440)), max(512, min(height, 1440))


def build_task_body(
    prompt: str, model: str | None, width: int, height: int, n: int = 1, negative_prompt: str | None = None
) -> dict:
    body: dict = {
        'model': model or DEFAULT_MODEL,
        'input': {'prompt': prompt},
        'parameters': {'size': '{}*{}'.format(*fit_size(model, width, height)), 'n': max(1, min(int(n or 1), 4))},
    }
    if negative_prompt:
        body['input']['negative_prompt'] = negative_prompt
    return body


def parse_task_status(res: dict) -> tuple[str, list[str], str]:
    """Return ``(status, image_urls, error_message)`` from a task response."""
    output = (res or {}).get('output') or {}
    status = str(output.get('task_status') or 'UNKNOWN').upper()
    urls = [r['url'] for r in output.get('results') or [] if isinstance(r, dict) and r.get('url')]
    error = output.get('message') or (res or {}).get('message') or output.get('code') or ''
    return status, urls, str(error)


async def generate(
    session,
    connection: dict,
    prompt: str,
    model: str | None,
    width: int,
    height: int,
    n: int = 1,
    negative_prompt: str | None = None,
    ssl=None,
) -> list[str]:
    """Submit a task and wait for it. Returns the generated image URLs."""
    url = base_url(connection.get('url'))
    headers = {'Authorization': f'Bearer {connection.get("key", "")}', 'Content-Type': 'application/json'}

    async with session.post(
        f'{url}/services/aigc/text2image/image-synthesis',
        json=build_task_body(prompt, model, width, height, n, negative_prompt),
        headers={**headers, 'X-DashScope-Async': 'enable'},
        ssl=ssl,
    ) as r:
        res = await r.json(content_type=None)
        if r.status >= 400:
            raise WanxError(res.get('message') or f'DashScope returned HTTP {r.status}')
    task_id = ((res or {}).get('output') or {}).get('task_id')
    if not task_id:
        raise WanxError('DashScope did not return a task id')

    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        async with session.get(f'{url}/tasks/{task_id}', headers=headers, ssl=ssl) as r:
            res = await r.json(content_type=None)
        status, urls, error = parse_task_status(res)
        if status == 'SUCCEEDED':
            if not urls:
                raise WanxError('DashScope task succeeded without images')
            return urls
        if status in ('FAILED', 'CANCELED', 'UNKNOWN'):
            raise WanxError(error or f'DashScope image task {status.lower()}')
        if time.monotonic() > deadline:
            raise WanxError('Timed out waiting for DashScope image generation')
        await asyncio.sleep(POLL_INTERVAL)

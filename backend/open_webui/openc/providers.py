"""Built-in provider presets for OpenC.

When ``DASHSCOPE_API_KEY`` or ``OPENCODE_API_KEY`` is set, the matching
OpenAI-compatible connection is added to the OpenAI connection list at
startup. This happens on first boot and on every later boot, so adding a
key to the environment of an existing install is enough. Connections an
admin has already configured are never modified or removed.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from dataclasses import dataclass

log = logging.getLogger(__name__)

OPENAI_DEFAULT_URL = 'https://api.openai.com/v1'


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    name: str
    env_key: str
    env_base_url: str
    default_base_url: str
    env_model_ids: str


PROVIDER_PRESETS: dict[str, ProviderPreset] = {
    'dashscope': ProviderPreset(
        id='dashscope',
        name='Alibaba Qwen',
        env_key='DASHSCOPE_API_KEY',
        env_base_url='DASHSCOPE_BASE_URL',
        # International endpoint. Mainland China accounts use
        # https://dashscope.aliyuncs.com/compatible-mode/v1
        default_base_url='https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
        env_model_ids='DASHSCOPE_MODEL_IDS',
    ),
    'opencode': ProviderPreset(
        id='opencode',
        name='OpenCode Zen',
        env_key='OPENCODE_API_KEY',
        env_base_url='OPENCODE_BASE_URL',
        default_base_url='https://opencode.ai/zen/v1',
        env_model_ids='OPENCODE_MODEL_IDS',
    ),
}


def _normalize(url: str) -> str:
    return url.strip().rstrip('/')


def preset_for_url(url: str, env: dict | None = None) -> ProviderPreset | None:
    """Return the preset whose base URL matches ``url``, if any."""
    env = os.environ if env is None else env
    url = _normalize(url)
    for preset in PROVIDER_PRESETS.values():
        candidates = {_normalize(preset.default_base_url)}
        if env.get(preset.env_base_url):
            candidates.add(_normalize(env[preset.env_base_url]))
        if url in candidates:
            return preset
    return None


def _preset_config(preset: ProviderPreset, env: dict) -> dict:
    config = {
        'enable': True,
        'connection_type': 'external',
        'provider': preset.id,
        'tags': [{'name': preset.name}],
    }
    model_ids = [m.strip() for m in env.get(preset.env_model_ids, '').split(',') if m.strip()]
    if model_ids:
        config['model_ids'] = model_ids
    return config


def merge_provider_connections(
    base_urls: list[str],
    api_keys: list[str],
    api_configs: dict,
    env: dict | None = None,
) -> tuple[list[str], list[str], dict, list[str]]:
    """Add preset connections for every provider whose API key is in ``env``.

    Returns ``(base_urls, api_keys, api_configs, added_provider_ids)``. The
    inputs are not mutated. A lone placeholder OpenAI connection with no key
    (upstream's default) is replaced instead of kept, so a fresh OpenC install
    with only a DashScope key doesn't show a broken OpenAI connection.
    """
    env = os.environ if env is None else env
    urls = list(base_urls or [])
    keys = list(api_keys or [])
    configs = deepcopy(api_configs or {})
    keys += [''] * (len(urls) - len(keys))

    added: list[str] = []
    for preset in PROVIDER_PRESETS.values():
        key = env.get(preset.env_key, '').strip()
        if not key:
            continue
        url = _normalize(env.get(preset.env_base_url) or preset.default_base_url)
        if any(_normalize(u) == url for u in urls):
            continue

        if urls == [OPENAI_DEFAULT_URL] and not keys[0] and not configs:
            urls, keys = [], []

        idx = len(urls)
        urls.append(url)
        keys.append(key)
        configs[str(idx)] = _preset_config(preset, env)
        added.append(preset.id)

    return urls, keys, configs, added


async def sync_env_provider_connections() -> list[str]:
    """Persist preset connections for providers configured via env vars."""
    from open_webui.models.config import Config

    current = await Config.get_many('openai.api_base_urls', 'openai.api_keys', 'openai.api_configs')
    urls, keys, configs, added = merge_provider_connections(
        current.get('openai.api_base_urls') or [],
        current.get('openai.api_keys') or [],
        current.get('openai.api_configs') or {},
    )
    if added:
        await Config.upsert(
            {
                'openai.api_base_urls': urls,
                'openai.api_keys': keys,
                'openai.api_configs': configs,
            }
        )
        log.info('OpenC: added provider connections from environment: %s', ', '.join(added))
    return added

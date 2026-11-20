from open_webui.openc.providers import (
    OPENAI_DEFAULT_URL,
    merge_provider_connections,
    preset_for_url,
)

DASH = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
ZEN = 'https://opencode.ai/zen/v1'


def test_no_keys_changes_nothing():
    urls, keys, configs, added = merge_provider_connections([OPENAI_DEFAULT_URL], [''], {}, env={})
    assert (urls, keys, configs, added) == ([OPENAI_DEFAULT_URL], [''], {}, [])


def test_fresh_install_replaces_empty_openai_placeholder():
    urls, keys, configs, added = merge_provider_connections(
        [OPENAI_DEFAULT_URL], [''], {}, env={'DASHSCOPE_API_KEY': 'sk-d', 'OPENCODE_API_KEY': 'sk-o'}
    )
    assert urls == [DASH, ZEN]
    assert keys == ['sk-d', 'sk-o']
    assert configs['0']['provider'] == 'dashscope'
    assert configs['1']['tags'] == [{'name': 'OpenCode Zen'}]
    assert added == ['dashscope', 'opencode']


def test_existing_connections_are_kept_and_appended_to():
    urls, keys, configs, added = merge_provider_connections(
        [OPENAI_DEFAULT_URL], ['sk-openai'], {'0': {'enable': True}}, env={'DASHSCOPE_API_KEY': 'sk-d'}
    )
    assert urls == [OPENAI_DEFAULT_URL, DASH]
    assert keys == ['sk-openai', 'sk-d']
    assert configs['0'] == {'enable': True}
    assert configs['1']['provider'] == 'dashscope'


def test_idempotent_when_url_already_present():
    first = merge_provider_connections([], [], {}, env={'DASHSCOPE_API_KEY': 'sk-d'})
    second = merge_provider_connections(first[0], first[1], first[2], env={'DASHSCOPE_API_KEY': 'sk-new'})
    assert second[3] == []
    assert second[1] == ['sk-d']  # an admin-managed key is never overwritten


def test_custom_base_url_and_model_ids():
    env = {
        'DASHSCOPE_API_KEY': 'k',
        'DASHSCOPE_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1/',
        'DASHSCOPE_MODEL_IDS': 'qwen-max, qwen-plus ,',
    }
    urls, _, configs, _ = merge_provider_connections([], [], {}, env=env)
    assert urls == ['https://dashscope.aliyuncs.com/compatible-mode/v1']
    assert configs['0']['model_ids'] == ['qwen-max', 'qwen-plus']
    assert preset_for_url(urls[0], env).id == 'dashscope'


def test_inputs_not_mutated():
    urls, keys, configs = [OPENAI_DEFAULT_URL], ['x'], {'0': {}}
    merge_provider_connections(urls, keys, configs, env={'OPENCODE_API_KEY': 'k'})
    assert urls == [OPENAI_DEFAULT_URL] and keys == ['x'] and configs == {'0': {}}

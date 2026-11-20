from open_webui.openc import features as F
from open_webui.openc.styles import MAX_CUSTOM_STYLE_CHARS, resolve_style_prompt


def add_system(content, messages):
    return [{'role': 'system', 'content': content}, *messages]


def test_style_presets_and_custom():
    assert resolve_style_prompt({}) == ''
    assert resolve_style_prompt({'style': 'normal'}) == ''
    assert 'concise' in resolve_style_prompt({'style': 'concise'}).lower()
    assert resolve_style_prompt({'style': 'unknown'}) == ''
    assert resolve_style_prompt({'style': 'custom', 'style_prompt': '  Pirate voice  '}) == 'Pirate voice'
    assert len(resolve_style_prompt({'style': 'custom', 'style_prompt': 'x' * 10000})) == MAX_CUSTOM_STYLE_CHARS


def test_apply_style_adds_system_message():
    form, feats = F.apply_openc_features(
        {'messages': [{'role': 'user', 'content': 'hi'}]}, {'style': 'formal'}, {}, {}, add_system
    )
    assert form['messages'][0]['role'] == 'system'
    assert '<response_style>' in form['messages'][0]['content']


def test_web_search_switches_to_qwen_search_for_dashscope_models():
    models = {'qwen-plus': {'id': 'qwen-plus', 'provider': 'dashscope'}}
    custom = {'id': 'my-assistant', 'info': {'base_model_id': 'qwen-plus'}}
    _, feats = F.apply_openc_features({'messages': []}, {'web_search': True}, custom, models, add_system)
    assert feats == {'web_search': False, 'qwen_search': True}


def test_web_search_untouched_for_other_providers():
    original = {'web_search': True}
    _, feats = F.apply_openc_features({'messages': []}, original, {'provider': 'opencode'}, {}, add_system)
    assert feats == {'web_search': True}
    assert original == {'web_search': True}

from open_webui.openc.dashscope import MAX_THINKING_BUDGET, apply_dashscope_params, search_info_to_sources


def test_no_features_leaves_payload_untouched():
    payload = {'model': 'qwen-plus', 'messages': []}
    assert apply_dashscope_params(payload, None) == payload
    assert apply_dashscope_params(payload, {}) == payload


def test_thinking_on_with_budget_is_clamped():
    out = apply_dashscope_params({'model': 'qwen-plus'}, {'thinking': True, 'thinking_budget': 10**9})
    assert out['enable_thinking'] is True
    assert out['thinking_budget'] == MAX_THINKING_BUDGET


def test_thinking_ignores_bad_budget_and_explicit_off():
    out = apply_dashscope_params({}, {'thinking': True, 'thinking_budget': True})
    assert out == {'enable_thinking': True}
    assert apply_dashscope_params({}, {'thinking': False}) == {'enable_thinking': False}


def test_qwen_search_sets_search_options():
    out = apply_dashscope_params({}, {'qwen_search': True})
    assert out['enable_search'] is True
    assert out['search_options']['enable_source'] is True


def test_search_info_to_sources_orders_and_dedupes():
    seen = []
    info = {
        'search_results': [
            {'index': 2, 'title': 'B', 'url': 'https://b.example'},
            {'index': 1, 'title': 'A', 'url': 'https://a.example'},
            {'index': 3, 'title': 'no url'},
        ]
    }
    first = search_info_to_sources(info, seen)
    assert [s['source']['url'] for s in first] == ['https://a.example', 'https://b.example']
    assert search_info_to_sources(info, seen) == []
    assert search_info_to_sources('garbage') == []

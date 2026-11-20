"""Hooks that apply OpenC chat features inside Open WebUI's chat pipeline."""

from __future__ import annotations

import os

from open_webui.openc.styles import style_system_block

QWEN_NATIVE_SEARCH = os.getenv('OPENC_QWEN_NATIVE_SEARCH', 'true').lower() == 'true'


def get_model_provider(model: dict | None, models: dict | None = None) -> str:
    """Return the connection provider id of ``model`` (following custom-model bases)."""
    if not model:
        return ''
    if model.get('provider'):
        return model['provider']
    base_id = (model.get('info') or {}).get('base_model_id')
    if base_id and models and base_id in models:
        return models[base_id].get('provider', '') or ''
    return ''


def apply_openc_features(
    form_data: dict,
    features: dict,
    model: dict | None,
    models: dict | None,
    add_system_message,
) -> tuple[dict, dict]:
    """Apply response style and Qwen-native search to the chat request.

    ``add_system_message(content, messages)`` is upstream's
    ``add_or_update_system_message`` (passed in to avoid an import cycle).
    """
    features = dict(features or {})

    block = style_system_block(features)
    if block and form_data.get('messages') is not None:
        form_data['messages'] = add_system_message(block, form_data['messages'])

    if (
        QWEN_NATIVE_SEARCH
        and features.get('web_search')
        and get_model_provider(model, models) == 'dashscope'
    ):
        # Let Qwen search the web itself instead of Open WebUI's search pipeline.
        features['web_search'] = False
        features['qwen_search'] = True

    return form_data, features

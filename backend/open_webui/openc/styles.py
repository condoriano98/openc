"""Response styles (inspired by Claude's Styles).

The composer sends ``features.style`` (a preset id or ``"custom"``) and, for
custom styles, ``features.style_prompt``. The style is added to the system
prompt.
"""

from __future__ import annotations

MAX_CUSTOM_STYLE_CHARS = 4000

STYLE_PRESETS: dict[str, dict[str, str]] = {
    'normal': {'name': 'Normal', 'prompt': ''},
    'concise': {
        'name': 'Concise',
        'prompt': (
            'Respond concisely. Lead with the answer, keep explanations short, avoid preamble and '
            'repetition, and use bullet points only when they make the reply shorter.'
        ),
    },
    'explanatory': {
        'name': 'Explanatory',
        'prompt': (
            'Respond like a patient teacher. Explain the reasoning step by step, define terms the '
            'reader may not know, give a concrete example, and finish with a short recap.'
        ),
    },
    'formal': {
        'name': 'Formal',
        'prompt': (
            'Respond in a clear, formal and professional register suitable for business or academic '
            'writing. Use complete sentences and well-organised paragraphs; avoid slang and emoji.'
        ),
    },
}


def resolve_style_prompt(features: dict | None) -> str:
    features = features or {}
    style = features.get('style')
    if not isinstance(style, str) or not style:
        return ''
    if style == 'custom':
        prompt = features.get('style_prompt')
        if not isinstance(prompt, str):
            return ''
        return prompt.strip()[:MAX_CUSTOM_STYLE_CHARS]
    return STYLE_PRESETS.get(style, {}).get('prompt', '')


def style_system_block(features: dict | None) -> str:
    prompt = resolve_style_prompt(features)
    if not prompt:
        return ''
    return f'<response_style>\n{prompt}\n</response_style>'

"""Slide deck generator (inspired by Kimi PPT).

The ``create_slides`` built-in tool takes a structured outline from the model,
renders a 16:9 PowerPoint file with python-pptx, saves it as a chat file and
returns a ``display_file``-style result, so Open WebUI shows its slide-by-slide
preview inline with a download option.
"""

from __future__ import annotations

import io
import logging
import re
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MAX_SLIDES = 40
MAX_BULLETS = 8

THEMES = {
    # name: (background, title, body, accent)
    'light': ('FFFFFF', '111827', '374151', '4F46E5'),
    'dark': ('0F172A', 'F8FAFC', 'CBD5E1', '38BDF8'),
    'ocean': ('0B3B5A', 'FFFFFF', 'D6EAF8', '5DADE2'),
    'warm': ('FFF7ED', '7C2D12', '431407', 'EA580C'),
}


class SlideItem(BaseModel):
    title: str = Field(..., description='Slide title')
    bullets: list[str] = Field(default_factory=list, description='Up to 8 short bullet points')
    notes: Optional[str] = Field(None, description='Optional speaker notes')


def _rgb(hex_color: str):
    from pptx.dml.color import RGBColor

    return RGBColor.from_string(hex_color)


def _fill_background(slide, color: str):
    background = slide.background.fill
    background.solid()
    background.fore_color.rgb = _rgb(color)


def _add_text(slide, left, top, width, height, text, size, color, bold=False):
    from pptx.util import Pt

    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)
    return box


def build_pptx(title: str, slides: list[SlideItem | dict], subtitle: str | None = None, theme: str = 'light') -> bytes:
    """Render the deck and return the .pptx bytes."""
    from pptx import Presentation
    from pptx.util import Emu, Inches, Pt

    bg, title_color, body_color, accent = THEMES.get(theme, THEMES['light'])
    items = [s if isinstance(s, SlideItem) else SlideItem(**s) for s in slides][:MAX_SLIDES]

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    width, height = prs.slide_width, prs.slide_height
    margin = Inches(0.8)

    # Title slide
    cover = prs.slides.add_slide(blank)
    _fill_background(cover, bg)
    bar = cover.shapes.add_shape(1, margin, Inches(3.0), Inches(1.2), Emu(Inches(0.08)))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(accent)
    bar.line.fill.background()
    _add_text(cover, margin, Inches(3.2), width - 2 * margin, Inches(1.6), title, 44, title_color, bold=True)
    if subtitle:
        _add_text(cover, margin, Inches(4.8), width - 2 * margin, Inches(1.0), subtitle, 22, body_color)

    for number, item in enumerate(items, start=2):
        slide = prs.slides.add_slide(blank)
        _fill_background(slide, bg)
        accent_bar = slide.shapes.add_shape(1, margin, Inches(0.55), Inches(0.9), Emu(Inches(0.06)))
        accent_bar.fill.solid()
        accent_bar.fill.fore_color.rgb = _rgb(accent)
        accent_bar.line.fill.background()
        _add_text(slide, margin, Inches(0.7), width - 2 * margin, Inches(1.1), item.title, 32, title_color, bold=True)

        bullets = [b.strip() for b in item.bullets if b and b.strip()][:MAX_BULLETS]
        if bullets:
            box = slide.shapes.add_textbox(margin, Inches(2.0), width - 2 * margin, height - Inches(2.8))
            frame = box.text_frame
            frame.word_wrap = True
            size = 24 if len(bullets) <= 4 else 20
            for i, bullet in enumerate(bullets):
                paragraph = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
                paragraph.space_after = Pt(10)
                marker = paragraph.add_run()
                marker.text = '•  '
                marker.font.size = Pt(size)
                marker.font.color.rgb = _rgb(accent)
                run = paragraph.add_run()
                run.text = bullet
                run.font.size = Pt(size)
                run.font.color.rgb = _rgb(body_color)

        _add_text(
            slide, width - Inches(1.6), height - Inches(0.6), Inches(1.0), Inches(0.4), str(number), 12, body_color
        )
        if item.notes:
            slide.notes_slide.notes_text_frame.text = item.notes

    buffer = io.BytesIO()
    prs.save(buffer)
    return buffer.getvalue()


def safe_filename(title: str) -> str:
    name = re.sub(r'[^\w\- ]+', '', title).strip().replace(' ', '-')[:60]
    return name or 'slides'


async def create_slides(
    title: str,
    slides: list[SlideItem],
    subtitle: Optional[str] = None,
    theme: Optional[str] = 'light',
    __request__=None,
    __user__: dict = None,
    __chat_id__: str = None,
    __message_id__: str = None,
) -> str:
    """
    Create a PowerPoint (.pptx) slide deck and show it to the user with a download option.
    Use this when the user asks for slides, a deck, a presentation or a PPT.
    Write concise slides: a clear title and 3-6 short bullets each, with speaker notes for detail.
    After it succeeds, briefly summarise the deck; do not repeat the slide content.

    :param title: Deck title shown on the cover slide
    :param slides: Content slides in order. Each item: title (string), bullets (list of short strings), notes (optional speaker notes)
    :param subtitle: Optional cover subtitle, such as the author, date or one-line summary
    :param theme: Colour theme: light, dark, ocean or warm
    :return: JSON describing the created file
    """
    from fastapi import UploadFile

    from open_webui.models.chats import Chats
    from open_webui.models.users import UserModel
    from open_webui.routers.files import upload_file_handler
    from open_webui.utils.json_codec import JSONCodec

    if __request__ is None or not __user__:
        return JSONCodec.dumps({'error': 'Request context not available'})
    if not slides:
        return JSONCodec.dumps({'error': 'Provide at least one slide'})

    try:
        data = build_pptx(title, slides, subtitle=subtitle, theme=theme or 'light')
        user = UserModel(**__user__)
        content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        file_item = await upload_file_handler(
            __request__,
            file=UploadFile(
                file=io.BytesIO(data),
                filename=f'{safe_filename(title)}.pptx',
                headers={'content-type': content_type},
            ),
            metadata={'chat_id': __chat_id__, 'message_id': __message_id__},
            process=False,
            user=user,
        )
        if __chat_id__ and __message_id__ and not str(__chat_id__).startswith('local:'):
            try:
                await Chats.insert_chat_files(
                    chat_id=__chat_id__, message_id=__message_id__, file_ids=[file_item.id], user_id=user.id
                )
            except Exception as e:  # linking is best-effort
                log.warning('create_slides: could not link file to chat: %s', e)

        path = f'/api/v1/files/{file_item.id}/content'
        return JSONCodec.dumps(
            {
                'type': 'file',
                'source': 'open_webui',
                'exists': True,
                'displayed': True,
                'path': path,
                'full_path': path,
                'name': (file_item.meta or {}).get('name') or file_item.filename,
                'content_type': content_type,
                'mime_type': content_type,
                'slides': len(slides) + 1,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        log.exception('create_slides error: %s', e)
        return JSONCodec.dumps({'error': str(e)})

import io

from pptx import Presentation

from open_webui.openc.slides import MAX_BULLETS, SlideItem, build_pptx, safe_filename


def test_build_pptx_has_cover_plus_content_slides_and_notes():
    data = build_pptx(
        'Quarterly Review',
        [
            SlideItem(title='Results', bullets=['Revenue up 12%', 'Churn down'], notes='Mention Q3'),
            {'title': 'Next steps', 'bullets': [f'b{i}' for i in range(20)]},
        ],
        subtitle='Team A',
        theme='dark',
    )
    prs = Presentation(io.BytesIO(data))
    assert len(prs.slides) == 3
    texts = [' '.join(sh.text_frame.text for sh in s.shapes if sh.has_text_frame) for s in prs.slides]
    assert 'Quarterly Review' in texts[0] and 'Team A' in texts[0]
    assert 'Revenue up 12%' in texts[1]
    assert prs.slides[1].notes_slide.notes_text_frame.text == 'Mention Q3'
    assert texts[2].count('•') == MAX_BULLETS


def test_unknown_theme_falls_back_and_filename_is_safe():
    assert build_pptx('x', [SlideItem(title='a')], theme='nope')
    assert safe_filename('Q3 / Plan: "Draft"') == 'Q3--Plan-Draft'
    assert safe_filename('???') == 'slides'

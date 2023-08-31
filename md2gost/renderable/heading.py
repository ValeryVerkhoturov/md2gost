from copy import copy
from typing import Generator

from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.shared import Parented, Length

from .page_break import PageBreak
from .paragraph_sizer import ParagraphSizer
from ..layout_tracker import LayoutState
from .paragraph import Paragraph
from ..rendered_info import RenderedInfo
from ..util import create_element


class Heading(Paragraph):
    def __init__(self, parent: Parented, level: int, numbered: bool):
        super().__init__(parent)

        self._parent = parent
        self._level = level

        if not 1 <= level <= 9:
            raise ValueError("Heading level must be in range from 1 to 9")

        self.style = f"Heading {level}"

        if not numbered:
            self._remove_numbering()
            self._docx_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        self._rendered_page = 0

        # todo: add bookmark here

    @property
    def rendered_page(self) -> int:
        return self._rendered_page

    @property
    def level(self) -> int:
        return self._level

    @property
    def text(self) -> str:
        return self._docx_paragraph.text

    def _remove_numbering(self):
        self._docx_paragraph._p.pPr.append(
            create_element("w:numPr", [
                create_element("w:ilvl", {
                    "w:val": "0"
                }),
                create_element("w:numId", {
                    "w:val": "0"
                })
            ])
        )

    def render(self, previous_rendered: RenderedInfo, layout_state: LayoutState) -> Generator[RenderedInfo, None, None]:
        if self._level == 1 and layout_state.page != 1 and\
                not (isinstance(previous_rendered.docx_element, DocxParagraph)
                     and previous_rendered.docx_element.text == "\n"):
            break_rendered_info = list(
                PageBreak(self._parent).render(previous_rendered, copy(layout_state)))
            break_height = sum([x.height for x in break_rendered_info])
            if break_height <= layout_state.remaining_page_height < layout_state.max_height:
                layout_state.add_height(break_height)
                yield from break_rendered_info

        height_data = ParagraphSizer(
            self._docx_paragraph,
            previous_rendered.docx_element
            if previous_rendered and isinstance(previous_rendered.docx_element, DocxParagraph) else None,
            layout_state.max_width).calculate_height()

        if layout_state.current_page_height == 0 and layout_state.page != 1:
            height_data.before = 0

        # if a heading + 2 lines don't fit to the page, they go to the next page
        if ((height_data.lines + 2 - 1) * height_data.line_spacing + 1) * height_data.line_height\
                > layout_state.remaining_page_height:
            self._docx_paragraph.paragraph_format.space_before = 0  # libreoffice fix
            height = height_data.full - height_data.before

            # force this behaviour as there could be a table or an image instead of text
            break_rendered_info = list(
                PageBreak(self._parent).render(previous_rendered, copy(layout_state)))
            if sum([x.height for x in break_rendered_info]) <= layout_state.remaining_page_height:
                yield from break_rendered_info
            else:
                height += layout_state.remaining_page_height

        else:
            height = height_data.full

        layout_state.add_height(height)
        self._rendered_page = layout_state.page

        yield RenderedInfo(self._docx_paragraph, Length(height))

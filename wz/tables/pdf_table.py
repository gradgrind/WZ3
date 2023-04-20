"""
tables/pdf_table.py

Last updated:  2023-04-19

Generate tabular reports as PDF files with multiple pages.

=+LICENCE=============================
Copyright 2023 Michael Towers

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
=-LICENCE========================================
"""

if __name__ == "__main__":
    # Enable package import if running as module
    import sys, os

    this = sys.path[0]
    appdir = os.path.dirname(this)
    sys.path[0] = appdir
    basedir = os.path.dirname(appdir)
    from core.base import start
    start.setup(os.path.join(basedir, "TESTDATA"))

T = TRANSLATIONS("tables.pdf_table")

### +++++

from io import BytesIO
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

PAGESIZE = A4
PAGESIZE_L = landscape(PAGESIZE)
BASE_MARGIN = 20 * mm

### -----


class MyDocTemplate(SimpleDocTemplate):
    """This is adapted to emit an "outline" for the pages."""

    def __init__(self, *args, **kargs):
        self.key = 0
        super().__init__(*args, **kargs)

    def handle_flowable(self, flowables):
        if flowables:
            flowable = flowables[0]
            try:
                flowable.toc(self.canv)
            except AttributeError:
                pass
        super().handle_flowable(flowables)

# Table coordinates are 0-based cells: (column, row).
# Positive coordinates are from (left, top),
# negative coordinates are from (right, bottom).
tablestyle0 = [
    # Simple table with grey line above bottom row, 12pt text
    ("FONT", (0, 0), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 12),
    ("LINEABOVE", (0, -1), (-1, -1), 1, colors.lightgrey),
]

tablestyle = [
    # A somewhat fancier table with black lines below the first and
    # last lines, bold titles, 11pt text.
    #         ('ALIGN', (0, 1), (-1, -1), 'RIGHT'),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
    ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
    #         ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
    ("FONT", (0, 1), (-1, -1), "Helvetica"),
    #         ('BACKGROUND', (1, 1), (-2, -2), colors.white),
    ("TEXTCOLOR", (0, 0), (1, -1), colors.black),
    ("FONTSIZE", (0, 0), (-1, -1), 11),
]

#?????
# Seems to work, but positioning is wrong (needs shifting right)
class RotatedParagraph(Paragraph):
    def draw(self):
        self.canv.rotate(90)
        super().draw()


class PdfCreator:
    def add_page_number(self, canvas, doc):
        canvas.saveState()
        font_name = "Helvetica"
        font_size = 11
        canvas.setFont(font_name, font_size)
        page_number_text = str(doc.page)
        w = stringWidth(page_number_text, font_name, font_size)
        x = (self.pagesize[0] - w) / 2
        canvas.drawCentredString(x, 10 * mm, page_number_text)
        canvas.restoreState()

    def build_pdf(
        self,
        pagelist,
        title,
        author,
        headers,
        colwidths=None,     # to specify column widths: list of sizes in mm
        do_landscape=False,
    ):
        all_refs = set()

        class PageHeader(Paragraph):
            # class PageHeader(Preformatted):
            def __init__(self, text, ref):
                if ref in all_refs:
                    REPORT("ERROR", T["Repeated_page_title"].format(ref=ref))
                    self.ref = None
                else:
                    self.ref = ref
                    all_refs.add(ref)
                super().__init__(text, heading_style)

            def toc(self, canvas):
                if self.ref:
                    canvas.bookmarkPage(self.ref)
                    canvas.addOutlineEntry(self.ref, self.ref, 0, 0)

        pdf_buffer = BytesIO()
        self.pagesize = PAGESIZE_L if do_landscape else PAGESIZE
        my_doc = MyDocTemplate(
            pdf_buffer,
            title=title,
            author=author,
            pagesize=self.pagesize,
            topMargin=BASE_MARGIN,
            leftMargin=BASE_MARGIN,
            rightMargin=BASE_MARGIN,
            bottomMargin=BASE_MARGIN,
        )
        sample_style_sheet = getSampleStyleSheet()

# body_style is not used at present!
        body_style = sample_style_sheet["BodyText"]
        # body_style = sample_style_sheet["Code"]
        body_style.fontSize = 11
        # body_style.leading = 14
        # body_style.leftIndent = 0

        # body_style_2 = copy.deepcopy(body_style)
        # body_style.spaceBefore = 10
        # body_style_2.alignment = TA_RIGHT

        # style for PageHeader
        heading_style = sample_style_sheet["Heading1"]
        # print("????????????", heading_style.fontName)
        # heading_style = copy.deepcopy(body_style)
        heading_style.fontName = "Helvetica-Bold"
        heading_style.fontSize = 14
        heading_style.spaceAfter = 24

        # sect_style = sample_style_sheet["Heading2"]
        # sect_style.fontSize = 13
        # sect_style.spaceBefore = 20
        # print("\n STYLES:", sample_style_sheet.list())

        flowables = []
        for pagehead, plist in pagelist:
            print("§§§", repr(pagehead), plist)
            # Need a copy of the style because it might be extended
            tstyle = tablestyle.copy()
            # h = Paragraph(pagehead, heading_style)
            # The second argument is the outline tag:
            h = PageHeader(pagehead, pagehead)  # .split("(", 1)[0].rstrip())
            flowables.append(h)
#            lines = [[RotatedParagraph(h, heading_style) for h in headers]]
            lines = [headers]
            nh = len(headers)
            for secthead, slist in plist:
                # With the special "section header" "#" add a table styled
                # by <tablestyle0>
                if secthead == "#":
                    table = Table(slist)
                    table_style = TableStyle(tablestyle0)
                    table.setStyle(table_style)
                    flowables.append(table)
                    continue
                lines.append("")
                for sline in slist:
                    r = len(lines)
                    if sline:
# This is rather specialized ... !
                        if sline[0].startswith("[["):
                            tstyle.append(("SPAN", (0, r), (2, r)))
                        elif sline[0] == "-----":
                            tstyle.append(
                                ("LINEABOVE", (0, r), (-1, r), 1, colors.black),
                            )
                            sline = sline[1:]
                        lines.append(
                            [Paragraph(l, body_style) for l in sline[:nh]]
                        )
                    else:
                        lines.append("")

            kargs = {"repeatRows": 1}
            if colwidths:
                kargs["colWidths"] = [w * mm for w in colwidths]
            table = Table(lines, **kargs)
            table_style = TableStyle(tstyle)
            table.setStyle(table_style)
            flowables.append(table)

            flowables.append(PageBreak())
        my_doc.build(
            flowables,
            onFirstPage=self.add_page_number,
            onLaterPages=self.add_page_number,
        )
        pdf_value = pdf_buffer.getvalue()
        pdf_buffer.close()
        return pdf_value


if __name__ == "__main__":

    pagelist = [
        ("Page 1",
            [
                ('#', 
                    [   
                        ("1", "2", "3"),
                        ("2.1", "2.2", "2.3"),
                        ("Longer item", "Very long item indeed", "3.3"),
                        "",
                    ]
                ),
                
                ('XXX',
                    [
                        ("First", "Second", "Third", "Last, but very long and most certainly not least"),
                        "",
                    ]
                ),
            ]
        ),
    ]
    pdf = PdfCreator()
    pdfbytes = pdf.build_pdf(
        pagelist,
        "TestPdfCreator",
        "Gradgrind",
        ["A", "B", "C", "D"],
        colwidths = [30, 30, 50, 50]
    )
    filepath = DATAPATH("testing/tmp/pdftable1.pdf")
    odir = os.path.dirname(filepath)
    os.makedirs(odir, exist_ok = True)
    with open(filepath, "wb") as fh:
        fh.write(pdfbytes)
    print("  --->", filepath)
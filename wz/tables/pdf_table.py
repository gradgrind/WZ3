"""
tables/pdf_table.py

Last updated:  2023-05-20

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
    Preformatted,
    Spacer,
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
TOP_MARGIN = 15 * mm
LR_MARGIN = 20 * mm
BOTTOM_MARGIN = 15 * mm
PAGEHEADGAP = 5 * mm

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

def ListTable(
    data,
    colwidths=None,     # to specify column widths: list of sizes in mm
    ncols=4,            # number of columns – only if no column widths given
    skip0=False,        # if true, column 0 will only be used in first line
    fontname="Helvetica",
    fontsize=11,
):
    tstyle = [
        # Simple table with grey line below bottom row
        ("FONT", (0, 0), (-1, -1), fontname),
        ("FONTSIZE", (0, 0), (-1, -1), fontsize),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.lightgrey),
    ]
    if colwidths:
        colwidths = [w * mm for w in colwidths]
        ncols = len(colwidths)
    lines = [line := []]
    for item in data:
        if len(line) == ncols:               
            lines.append(line := [])
            if skip0:
                line.append("")
        line.append(item)
    return Table(lines, colwidths, style = tstyle)


#?????
# Seems to work, but positioning is wrong (needs shifting right)
class RotatedParagraph(Paragraph):
    def draw(self):
        self.canv.rotate(90)
        super().draw()


class TablePages:
    def __init__(
        self,
        title,
        author,
        headers,
        colwidths=None,     # to specify column widths: list of sizes in mm
        # Horizontal alignment, default is "CENTRE"
        align=None,         # ((column-index, "l", "r" or "p"), ... )
        do_landscape=False,
        # Base font
        fontname="Helvetica",
        fontsize=11,
        # Font for table header
        headerfontname="Helvetica-Bold",
        # Font for <PageHeader>
        pageheaderfontname="Helvetica-Bold",
        pageheaderfontsize=14,
    ):
        self.headers = headers
        self.colwidths = colwidths
        self.align = {i: "CENTRE" for i in range(len(headers))}
        self.column_wrap = set()
        if align:
            for i, a in align:
                if a == "l":
                    self.align[i] = "LEFT"
                elif a == "r":
                    self.align[i] = "RIGHT"
                elif a == "p":
                    self.align[i] = "LEFT"
                    self.column_wrap.add(i) # wrap in <Paragraph>
        self.pdf_buffer = BytesIO()
        self.pagesize = PAGESIZE_L if do_landscape else PAGESIZE
        self.my_doc = MyDocTemplate(
            self.pdf_buffer,
            title=title,
            author=author,
            pagesize=self.pagesize,
            topMargin=TOP_MARGIN,
            leftMargin=LR_MARGIN,
            rightMargin=LR_MARGIN,
            bottomMargin=BOTTOM_MARGIN,
        )
        # style for <PageHeader>
        sample_style_sheet = getSampleStyleSheet()
        self.heading_style = sample_style_sheet["Heading1"]
        self.heading_style.fontName = pageheaderfontname
        self.heading_style.fontSize = pageheaderfontsize
        self.heading_style.spaceAfter = PAGEHEADGAP
        # style for the table
        tstyle = [
            # Black lines below the first and last rows
            ('ALIGN', (0, 0), (-1, 0), 'CENTRE'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
            ("FONT", (0, 0), (-1, 0), headerfontname),
            #         ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
            ("FONT", (0, 1), (-1, -1), fontname),
            #         ('BACKGROUND', (1, 1), (-2, -2), colors.white),
            ("TEXTCOLOR", (0, 0), (1, -1), colors.black),
            ("FONTSIZE", (0, 0), (-1, -1), fontsize),
            # Alternating row colours (ignoring first and last lines):
            ("ROWBACKGROUNDS", (0, 2), (-1, -2),
                (colors.white, (0.94, 0.94, 1.0))
            ),
        ]
        for i, a in self.align.items():
            tstyle.append(('ALIGN', (i, 1), (i, -1), a))
        self.TABLESTYLE = tuple(tstyle)

        # style for <Paragraph> items in table lines
        self.body_style = sample_style_sheet["BodyText"]
        self.body_style.fontName = fontname
        self.body_style.fontSize = fontsize
        self.pages = []

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

    def add_page(self, header):
        self.pages.append({
            "header": header,
            "tablestyle": self.TABLESTYLE,
#            lines = [
#                [   RotatedParagraph(h, self.heading_style)
#                    for h in self.headers
#                ]
#            ]
            "table": [self.headers],
            "PRE": [],
            "POST": [],
        })

    def add_line(self, values=None):
        if values is None:
            self.pages[-1]["table"].append([])
            return
        assert len(values) == len(self.headers)
        # Wrap field values in <Paragraph> to allow line breaking
        self.pages[-1]["table"].append(
            [Paragraph(l, self.body_style)
            if i in self.column_wrap
            else l
            for i, l in enumerate(values)]
        )

    def add_paragraph(self, text, indent=None, pre=True):
        if indent is None:
            self.pages[-1]["PRE" if pre else "POST"].append(
                Paragraph(text, self.body_style)
            )
        else:
            s = self.body_style.clone(
                "IndentedParagraph", leftIndent=indent*mm
            )
            self.pages[-1]["PRE" if pre else "POST"].append(
                Paragraph(text, s)
            )

    def add_text(self, text, pre=True):
        self.pages[-1]["PRE" if pre else "POST"].append(
            Preformatted(text, self.body_style)
        )

    def add_list_table(self, data, pre=True, **kargs):
        self.pages[-1]["PRE" if pre else "POST"].append(
            ListTable(data, **kargs)
        )

    def add_vspace(self, height, pre=True):
        self.pages[-1]["PRE" if pre else "POST"].append(
            Spacer(0, height * mm)
        )

    def build_pdf(self):
        """Build the pdf, returning the file as a byte array.
        """
        class PageHeader(Paragraph):
            def __init__(this, text, ref):
                if ref in all_refs:
                    REPORT("ERROR", T["Repeated_page_title"].format(ref=ref))
                    this.ref = None
                else:
                    this.ref = ref
                    all_refs.add(ref)
                super().__init__(text, self.heading_style)

            def toc(self, canvas):
                if self.ref:
                    canvas.bookmarkPage(self.ref)
                    canvas.addOutlineEntry(self.ref, self.ref, 0, 0)

        all_refs = set()
        flowables = []
        for pdata in self.pages:
            pagehead = pdata["header"]
            tstyle = pdata["tablestyle"]
            lines = pdata["table"]
            # The second argument is the outline tag:
            h = PageHeader(pagehead, pagehead)
            flowables.append(h)
            flowables += pdata["PRE"]
            kargs = {"repeatRows": 1}
            if self.colwidths:
                kargs["colWidths"] = [w * mm for w in self.colwidths]
            table = Table(lines, **kargs)
            table.setStyle(TableStyle(tstyle))
            flowables.append(table)
            flowables += pdata["POST"]
            flowables.append(PageBreak())
        self.my_doc.build(
            flowables,
            onFirstPage=self.add_page_number,
            onLaterPages=self.add_page_number,
        )
        pdf_value = self.pdf_buffer.getvalue()
        self.pdf_buffer.close()
        return pdf_value


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#

if __name__ == "__main__":

    pdf = TablePages(
        "TestPdfCreator",
        "Gradgrind",
        ["A", "B", "C", "D"],
        colwidths = [30, 30, 50, 50],
        align = ((3, "p"),),
    )

    pdf.add_page("Page 1")
    pdf.add_line()
    pdf.add_line((
        "First",
        "Second",
        "Third",
        "Last, but very long and most certainly not least",
    ))
    pdf.add_line(("2.1", "2.2", "2.3", "2.4"))
    pdf.add_line(("3.1", "3.2", "3.3", "3.4"))
    pdf.add_line()

    pdf.add_paragraph("An introductory line")
    pdf.add_paragraph("... which can be indented, too!", 10)
    pdf.add_vspace(5)   # mm

    pdf.add_vspace(5, pre=False)   # mm
    pdf.add_list_table(("Total hours for groups:", "A: 10", "B: 9",
        "C.G: 8", "D: 11"),
        skip0=True,
        colwidths=(60, 30, 30, 30),
        pre=False,
    )

    pdf.add_list_table(("Total hours for groups:", "A: 10", "B: 9",
        "C.G: 8", "D: 11"),
        skip0=True,
        ncols=8,
    )
    pdf.add_vspace(5)   # mm

    pdfbytes = pdf.build_pdf()
    filepath = DATAPATH("testing/tmp/pdftable0.pdf")
    odir = os.path.dirname(filepath)
    os.makedirs(odir, exist_ok = True)
    with open(filepath, "wb") as fh:
        fh.write(pdfbytes)
    print("  --->", filepath)

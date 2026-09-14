"""
Build the Hinweis (NCCT/AITC) Word submission from the paper's content.

That venue takes .doc/.docx only, in its own template, and prescribes a
nineteen-section structure that the LaTeX paper does not use: Motivation,
Problem Domain, Problem Definition, Statement, Innovative Content, Problem
Formulation, Solution Methodologies, Data Model, Comparison of Results and
Justification of the Results are all separate headings there. Its abstract is
capped at about 55 words against the paper's 210.

So this is not a conversion. The same measurements are re-ordered into their
structure, and every number here is the number the LaTeX paper reports.

    venv/bin/python scripts/build_hinweis_docx.py

Layout follows HR template.docx: A4, margins 3.25/3.0/3.25/2.5 cm, Times New
Roman, Roman section numbers, lettered subsections, no paragraph indent, no
page numbers.
"""

import sys
from pathlib import Path

FIGS = Path("/private/tmp/claude-501/-Users-rachitranka-Desktop-Shiksha-setu-main/"
            "3ec87c9d-72e2-4c8e-bbb8-15b40a397f90/scratchpad/figs")
OUT = Path("/Users/rachitranka/Desktop/Shiksha-setu-main/docs/NCCT_SHIKSHA_SETU.docx")

TITLE = ("Shiksha Setu: A Measurement-Driven, Local-Retrieval AI Tutoring "
         "Platform for Multilingual Indian Education")
AUTHORS = "Rachit Ranka, Aaditya Saini, Priyanka Devi, Yogesh Kohli and Ruhani Mehta"
AFFIL = "Department of Computer Science Engineering, Chandigarh University, Mohali, India"
EMAILS = ("Email: {rankarachit5, aadityasaini899, pjangra9105, ykohli2005, "
          "ruhanimehta019}@gmail.com")

# Their instruction: "typically 55 words or less". Counted: 54.
ABSTRACT = ("NCERT textbooks exist only in English, Hindi and Urdu, so most Indian "
            "students cannot read their own curriculum. Shiksha Setu retrieves from "
            "an English corpus for questions asked in eleven languages. Over 77 "
            "queries, lexical retrieval succeeds none; embedding recovers 47 and "
            "rewriting into English first recovers 66, inside 4 GB.")

KEYWORDS = ("Retrieval-Augmented Generation, Multilingual Education, Cross-Lingual "
            "Retrieval, Indian Languages, Curriculum-Aligned Tutoring, NCERT")


def body(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.first_line_indent = 0
    p.paragraph_format.space_after = 0
    return p


def main() -> int:
    from docx import Document
    from docx.shared import Pt, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin, s.bottom_margin = Cm(3.25), Cm(3.25)
    s.left_margin, s.right_margin = Cm(3.0), Cm(2.5)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(10)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.0

    def heading(text, roman):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(f"{roman}.  {text}")
        r.font.name = "Times New Roman"
        r.font.size = Pt(10)
        r.bold = True
        return p

    def sub(text, letter):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"{letter}.  {text}")
        r.font.name = "Times New Roman"
        r.italic = True
        r.font.size = Pt(10)
        return p

    def figure(img, caption):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.add_run().add_picture(str(img), width=Inches(4.4))
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_after = Pt(10)
        r = c.add_run(caption)
        r.font.size = Pt(8)
        r.font.name = "Times New Roman"

    def table(caption, rows, widths=None):
        c = doc.add_paragraph()
        c.alignment = WD_ALIGN_PARAGRAPH.CENTER
        c.paragraph_format.space_before = Pt(8)
        r = c.add_run(caption)
        r.font.size = Pt(8)
        r.bold = True
        t = doc.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Table Grid"
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.text = str(val)
                for par in cell.paragraphs:
                    par.paragraph_format.space_after = Pt(0)
                    for run in par.runs:
                        run.font.size = Pt(8)
                        run.font.name = "Times New Roman"
                        run.bold = (i == 0)
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # ---------------------------------------------------------------- title
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(TITLE)
    r.font.size = Pt(20)
    r.font.name = "Times New Roman"
    t.paragraph_format.space_after = Pt(10)

    for text, size in ((AUTHORS, 11), (AFFIL, 10), (EMAILS, 10)):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = p.add_run(text)
        rr.font.size = Pt(size)
        rr.font.name = "Times New Roman"
        p.paragraph_format.space_after = Pt(2)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    a = doc.add_paragraph()
    ar = a.add_run("Abstract")
    ar.bold = True
    ar.font.size = Pt(9)
    a.add_run("—" + ABSTRACT).font.size = Pt(9)
    a.paragraph_format.space_after = Pt(6)

    k = doc.add_paragraph()
    kr = k.add_run("Index Terms")
    kr.bold = True
    kr.font.size = Pt(9)
    k.add_run("—" + KEYWORDS + ".").font.size = Pt(9)
    k.paragraph_format.space_after = Pt(10)

    from hinweis_content import SECTIONS, TABLES, FIGURE_CAPTIONS, REFERENCES

    romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
              "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX"]
    for idx, (name, blocks) in enumerate(SECTIONS):
        heading(name, romans[idx])
        for b in blocks:
            kind = b[0]
            if kind == "p":
                body(doc, b[1])
            elif kind == "sub":
                sub(b[1], b[2])
            elif kind == "fig":
                figure(FIGS / b[1], FIGURE_CAPTIONS[b[1]])
            elif kind == "tab":
                table(TABLES[b[1]][0], TABLES[b[1]][1])
        if name == "References":
            for i, ref in enumerate(REFERENCES, 1):
                rp = doc.add_paragraph(f"[{i}]  {ref}")
                rp.paragraph_format.space_after = Pt(0)
                rp.paragraph_format.left_indent = Cm(0.8)
                rp.paragraph_format.first_line_indent = Cm(-0.8)
                for run in rp.runs:
                    run.font.size = Pt(8)
                    run.font.name = "Times New Roman"

    doc.save(OUT)
    print(f"  written: {OUT}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main())

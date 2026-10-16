"""Column-aware paper-text extraction (P6 re-read corpus builder).

The P5 full-text corpus was built with `pdftotext -layout`, which preserves the
*visual* layout: on two-column papers the left and right columns appear
side-by-side on the same lines, so a sequential reader interleaves them
(verified on Sentinel-VLA, where "Training Setup ..." and "Performance on
RLBench ..." share lines). A dual-mode scan (`logs/p6/DUAL_MODE_SCAN.tsv`)
showed plain `pdftotext` fixes some papers but worsens others, so neither
poppler mode is universally correct.

This builder uses PyMuPDF block coordinates to reconstruct reading order:

* blocks are classified full-width (spanning the page mid-line) vs column;
* the page is emitted top-to-bottom, and between two full-width blocks each
  column is emitted in its own top-to-bottom order (left, then right);
* every page starts with a `[page N]` marker so a reader can cite and
  re-extract a page directly.

Usage:
    python3 scripts/202_paper_text_extract.py --out Paper/fulltext_ca
    python3 scripts/202_paper_text_extract.py --check Sentinel-VLA

`--check` prints the first lines around a paper whose name matches, so the
column fix can be eyeballed against `Paper/fulltext/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore


def page_reading_order(page) -> str:
    """Reconstruct one page's reading order from block coordinates."""
    width = float(page.rect.width)
    mid = width / 2.0
    blocks = []
    for x0, y0, x1, y1, text, _no, btype in page.get_text("blocks"):
        if btype != 0 or not text.strip():
            continue
        blocks.append((float(x0), float(y0), float(x1), float(y1), text.strip()))
    blocks.sort(key=lambda b: (b[1], b[0]))

    def spanning(b) -> bool:
        return b[0] < mid - 20 and b[2] > mid + 20

    out: list[str] = []
    left: list[str] = []
    right: list[str] = []

    def flush() -> None:
        out.extend(left)
        out.extend(right)
        left.clear()
        right.clear()

    for b in blocks:
        if spanning(b):
            flush()
            out.append(b[4])
        elif (b[0] + b[2]) / 2 < mid:
            left.append(b[4])
        else:
            right.append(b[4])
    flush()
    return "\n".join(out)


def extract(pdf: Path, out: Path) -> tuple[int, int]:
    doc = pymupdf.open(pdf)
    parts: list[str] = []
    pages = 0
    for i, page in enumerate(doc, start=1):
        pages = i
        parts.append(f"[page {i}]")
        parts.append(page_reading_order(page))
    doc.close()
    text = "\n\n".join(parts) + "\n"
    # Strip control bytes (NUL / C0): 57/84 of the first CA build carried them
    # (font-encoding artifacts, up to 227 bytes per file) and they make generic
    # readers treat the file as binary. The visible text is unchanged.
    import re as _re
    text = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    out.write_text(text, encoding="utf-8")
    return pages, len(text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="Paper/fulltext_ca")
    ap.add_argument("--check", default=None,
                    help="print a sample of the first paper whose name matches")
    args = ap.parse_args()

    root = Path("Paper/论文")
    pdfs = sorted(p for p in root.rglob("*.pdf") if p.is_file())
    if not pdfs:
        print("no PDFs under Paper/论文")
        return 1

    if args.check:
        match = [p for p in pdfs if args.check.lower() in p.name.lower()]
        if not match:
            print(f"no paper matches {args.check!r}")
            return 1
        for p in match[:1]:
            rel = p.relative_to(root)
            out = Path(args.out) / (rel.parts[0] + "__" + p.stem + ".txt")
            if not out.exists():
                print("run without --check first to build the corpus")
                return 1
            text = out.read_text(encoding="utf-8")
            start = text.find("[page 4]")
            print(text[start:start + 1500] if start >= 0 else text[:1500])
        return 0

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    fails = []
    total_pages = total_chars = 0
    for p in pdfs:
        rel = p.relative_to(root)
        out = outdir / (rel.parts[0] + "__" + p.stem + ".txt")
        try:
            pages, chars = extract(p, out)
            total_pages += pages
            total_chars += chars
        except Exception as exc:  # noqa: BLE001 - report and continue
            fails.append((str(rel), repr(exc)[:120]))
    print(f"extracted {len(pdfs) - len(fails)}/{len(pdfs)} -> {outdir} "
          f"({total_pages} pages, {total_chars} chars)")
    for rel, err in fails:
        print("  FAIL", rel, err)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

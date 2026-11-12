"""Turn Claude's answer into plain text that fits the TI-84 Plus CE screen.

The calculator's large font shows 26 characters per line, and it can only
display plain ASCII, so this module strips Markdown and LaTeX, swaps math
symbols for ASCII spellings, and wraps the text to the screen width.
"""

import re
import textwrap

SCREEN_WIDTH = 26

# Unicode math symbols and their ASCII spellings.
SYMBOLS = {
    "\u00d7": "*",   # multiplication sign
    "\u00f7": "/",   # division sign
    "\u2212": "-",   # minus sign
    "\u2013": "-",   # en dash
    "\u2014": "-",   # em dash
    "\u00b7": "*",   # middle dot
    "\u22c5": "*",   # dot operator
    "\u00b2": "^2",
    "\u00b3": "^3",
    "\u221a": "sqrt",
    "\u03c0": "pi",
    "\u03b8": "theta",
    "\u221e": "inf",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2260": "!=",
    "\u2248": "~=",
    "\u00b1": "+/-",
    "\u00b0": " deg",
    "\u2192": "->",
    "\u21d2": "=>",
    "\u2026": "...",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
}

# LaTeX commands with simple ASCII replacements.
LATEX_WORDS = {
    r"\cdot": "*",
    r"\times": "*",
    r"\div": "/",
    r"\pm": "+/-",
    r"\pi": "pi",
    r"\theta": "theta",
    r"\infty": "inf",
    r"\leq": "<=",
    r"\le": "<=",
    r"\geq": ">=",
    r"\ge": ">=",
    r"\neq": "!=",
    r"\approx": "~=",
    r"\left": "",
    r"\right": "",
}


def _strip_latex(text: str) -> str:
    # Math delimiters: \( \) \[ \] and $...$
    text = re.sub(r"\\[\(\)\[\]]", "", text)
    text = text.replace("$", "")
    # \frac{a}{b} -> (a)/(b), repeated for nested fractions.
    frac = re.compile(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}")
    while frac.search(text):
        text = frac.sub(r"(\1)/(\2)", text)
    text = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", text)
    # \text{word} -> word
    text = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]*)\}", r"\1", text)
    # Longest command names first so \leq is not read as \le + q.
    for cmd in sorted(LATEX_WORDS, key=len, reverse=True):
        text = re.sub(re.escape(cmd) + r"(?![A-Za-z])", LATEX_WORDS[cmd], text)
    # ^{...} -> ^(...) when it is more than one character.
    text = re.sub(r"\^\{([^{}]{2,})\}", r"^(\1)", text)
    text = re.sub(r"\^\{([^{}])\}", r"^\1", text)
    # Any leftover braces or backslash commands.
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    return text.replace("{", "(").replace("}", ")")


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*[*+]\s+", "- ", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    return text


def to_ascii(text: str) -> str:
    """Replace symbols, strip Markdown and LaTeX, and drop non-ASCII."""
    for symbol, ascii_text in SYMBOLS.items():
        text = text.replace(symbol, ascii_text)
    text = _strip_latex(text)
    text = _strip_markdown(text)
    text = text.encode("ascii", "replace").decode("ascii")
    # Collapse runs of blank lines to one.
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def to_screen_lines(text: str, width: int = SCREEN_WIDTH) -> list[str]:
    """Return the answer as lines no wider than the calculator screen."""
    lines: list[str] = []
    for paragraph in to_ascii(text).split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(
            textwrap.wrap(
                paragraph,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
        )
    return lines

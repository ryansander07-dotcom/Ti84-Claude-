"""Check that the dongle's C++ text cleanup matches bridge/calc_text.py.

One known difference: the C++ version folds runs of spaces and tabs inside a
line into one space, where Python's textwrap keeps them. Samples avoid that.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

from calc_text import to_screen_lines  # noqa: E402

CXX = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")

SAMPLES = [
    "The answer is 42.",
    "**Step 1:** Subtract 3 from both sides.\n\n**Step 2:** Divide by 2.\nANSWER: x = 4",
    "# Heading\n## Smaller\n* bullet one\n+ bullet two\n> quoted line",
    "Use $\\frac{a+b}{c}$ and \\(\\sqrt{x^2+1}\\) here.",
    "Nested \\frac{\\frac{1}{2}}{3} and x^{10} and y^{2} and \\text{area} = \\pi r^2",
    "\\leq \\le \\geq \\neq \\approx \\cdot \\times \\div \\pm \\infty \\theta \\left( x \\right)",
    "Unicode: 3 × 4 ÷ 2 − 1, x² + y³, √9, πr², 45°, a ≤ b",
    "Unknown symbols: ∃ ∀ é \U0001F600 end",
    "```python\nprint('hi')\n```\nand `inline` code",
    "A supercalifragilisticexpialidociousword that is very long indeed",
    "Line one\n   \n\n  \nLine two after blanks",
    "   leading and trailing spaces   ",
    "word " * 40,
    "x" * 70,
    "short " + "y" * 30 + " tail",
    "",
    "__underlined__ and **bold** but ** not closed",
]


@pytest.fixture(scope="module")
def port(tmp_path_factory):
    if not CXX:
        pytest.skip("no C++ compiler")
    out = tmp_path_factory.mktemp("port") / "calc_text"
    subprocess.run(
        [
            CXX, "-std=c++17", "-O1", "-o", str(out),
            str(ROOT / "esp32" / "tests" / "calc_text_main.cpp"),
            str(ROOT / "esp32" / "ti84_dongle" / "calc_text.cpp"),
        ],
        check=True,
    )
    return out


@pytest.mark.parametrize("text", SAMPLES)
@pytest.mark.parametrize("width", [26, 12])
def test_port_matches_python(port, text, width):
    result = subprocess.run(
        [str(port), str(width)], input=text.encode("utf-8"), capture_output=True, check=True
    )
    got = result.stdout.decode("ascii").split("\n")[:-1]
    assert got == to_screen_lines(text, width)

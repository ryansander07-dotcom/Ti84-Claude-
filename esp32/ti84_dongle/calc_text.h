// Turn Claude's answer into plain ASCII lines that fit the calculator screen.
// A C++ port of bridge/calc_text.py; tests/test_calc_text_port.py checks that
// both give the same lines. One difference: runs of spaces or tabs inside a
// line become a single space here, which reads better on a 26-column screen.
#pragma once

#include <string>
#include <vector>

static const int SCREEN_WIDTH = 26;

std::string to_ascii(const std::string &text);
std::vector<std::string> to_screen_lines(const std::string &text, int width = SCREEN_WIDTH);

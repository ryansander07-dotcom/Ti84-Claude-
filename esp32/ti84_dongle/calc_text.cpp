// C++ port of bridge/calc_text.py, written without std::regex so it stays
// small and fast on the ESP32.
#include "calc_text.h"

#include <algorithm>
#include <cctype>
#include <cstring>

namespace {

struct Pair {
    const char *from;
    const char *to;
};

// Unicode math symbols (as UTF-8) and their ASCII spellings.
const Pair SYMBOLS[] = {
    {"×", "*"},     {"÷", "/"},   {"−", "-"},   {"–", "-"},
    {"—", "-"},     {"·", "*"},   {"⋅", "*"},   {"²", "^2"},
    {"³", "^3"},    {"√", "sqrt"}, {"π", "pi"}, {"θ", "theta"},
    {"∞", "inf"},   {"≤", "<="},  {"≥", ">="},  {"≠", "!="},
    {"≈", "~="},    {"±", "+/-"}, {"°", " deg"}, {"→", "->"},
    {"⇒", "=>"},    {"…", "..."}, {"‘", "'"},   {"’", "'"},
    {"“", "\""},    {"”", "\""},  {" ", " "},
};

// LaTeX commands with simple ASCII replacements.
const Pair LATEX_WORDS[] = {
    {"\\cdot", "*"},   {"\\times", "*"}, {"\\div", "/"},    {"\\pm", "+/-"},
    {"\\pi", "pi"},    {"\\theta", "theta"}, {"\\infty", "inf"}, {"\\leq", "<="},
    {"\\le", "<="},    {"\\geq", ">="},  {"\\ge", ">="},    {"\\neq", "!="},
    {"\\approx", "~="}, {"\\left", ""},  {"\\right", ""},
};

bool is_alpha(char c) { return std::isalpha(static_cast<unsigned char>(c)) != 0; }
bool is_space(char c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\f' || c == '\v'; }

void replace_all(std::string &s, const std::string &from, const std::string &to) {
    if (from.empty()) return;
    size_t pos = 0;
    while ((pos = s.find(from, pos)) != std::string::npos) {
        s.replace(pos, from.size(), to);
        pos += to.size();
    }
}

// Read "{...}" with no nested braces starting at s[pos] == '{'.
// On success sets end to the index after '}' and returns true.
bool brace_group(const std::string &s, size_t pos, std::string &inner, size_t &end) {
    if (pos >= s.size() || s[pos] != '{') return false;
    size_t close = pos + 1;
    while (close < s.size() && s[close] != '}' && s[close] != '{') close++;
    if (close >= s.size() || s[close] != '}') return false;
    inner = s.substr(pos + 1, close - pos - 1);
    end = close + 1;
    return true;
}

// \frac{a}{b}, \dfrac, \tfrac -> (a)/(b), innermost first, repeated.
void rewrite_fractions(std::string &s) {
    bool changed = true;
    while (changed) {
        changed = false;
        size_t pos = 0;
        while ((pos = s.find("frac{", pos)) != std::string::npos) {
            size_t start;
            if (pos >= 1 && s[pos - 1] == '\\') {
                start = pos - 1;
            } else if (pos >= 2 && (s[pos - 1] == 'd' || s[pos - 1] == 't') && s[pos - 2] == '\\') {
                start = pos - 2;
            } else {
                pos++;
                continue;
            }
            std::string a, b;
            size_t mid, end;
            if (brace_group(s, pos + 4, a, mid) && brace_group(s, mid, b, end)) {
                s.replace(start, end - start, "(" + a + ")/(" + b + ")");
                changed = true;
                pos = start;
            } else {
                pos++;
            }
        }
    }
}

// \name{x} -> before + x + after, for groups with no nested braces.
void rewrite_command(std::string &s, const std::string &name, const std::string &before,
                     const std::string &after) {
    std::string marker = "\\" + name + "{";
    size_t pos = 0;
    while ((pos = s.find(marker, pos)) != std::string::npos) {
        std::string inner;
        size_t end;
        if (brace_group(s, pos + marker.size() - 1, inner, end)) {
            std::string repl = before + inner + after;
            s.replace(pos, end - pos, repl);
            pos += repl.size();
        } else {
            pos++;
        }
    }
}

std::string strip_latex(std::string s) {
    // Math delimiters: \( \) \[ \] and $.
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); i++) {
        if (s[i] == '\\' && i + 1 < s.size() &&
            (s[i + 1] == '(' || s[i + 1] == ')' || s[i + 1] == '[' || s[i + 1] == ']')) {
            i++;
            continue;
        }
        if (s[i] == '$') continue;
        out += s[i];
    }
    s.swap(out);

    rewrite_fractions(s);
    rewrite_command(s, "sqrt", "sqrt(", ")");
    rewrite_command(s, "text", "", "");
    rewrite_command(s, "mathrm", "", "");
    rewrite_command(s, "mathbf", "", "");

    // Longest command names first so \leq is not read as \le + q.
    std::vector<Pair> words(std::begin(LATEX_WORDS), std::end(LATEX_WORDS));
    std::stable_sort(words.begin(), words.end(),
                     [](const Pair &a, const Pair &b) { return strlen(a.from) > strlen(b.from); });
    for (const Pair &w : words) {
        size_t len = strlen(w.from);
        size_t pos = 0;
        while ((pos = s.find(w.from, pos)) != std::string::npos) {
            if (pos + len < s.size() && is_alpha(s[pos + len])) {
                pos++;
                continue;
            }
            s.replace(pos, len, w.to);
            pos += strlen(w.to);
        }
    }

    // ^{...} -> ^(...) for two or more characters, ^{x} -> ^x.
    size_t pos = 0;
    while ((pos = s.find("^{", pos)) != std::string::npos) {
        std::string inner;
        size_t end;
        if (brace_group(s, pos + 1, inner, end) && !inner.empty()) {
            std::string repl = inner.size() == 1 ? "^" + inner : "^(" + inner + ")";
            s.replace(pos, end - pos, repl);
            pos += repl.size();
        } else {
            pos++;
        }
    }

    // Leftover backslash commands lose the backslash.
    out.clear();
    for (size_t i = 0; i < s.size(); i++) {
        if (s[i] == '\\' && i + 1 < s.size() && is_alpha(s[i + 1])) continue;
        out += s[i];
    }
    for (char &c : out) {
        if (c == '{') c = '(';
        else if (c == '}') c = ')';
    }
    return out;
}

// Remove paired markers like **x** or __x__ on a single line (non-greedy).
void strip_pairs(std::string &s, const std::string &mark) {
    size_t pos = 0;
    while ((pos = s.find(mark, pos)) != std::string::npos) {
        size_t start = pos + mark.size();
        size_t close = s.find(mark, start + 1);  // at least one character between
        size_t newline = s.find('\n', start);
        if (close == std::string::npos || (newline != std::string::npos && newline < close)) {
            pos = start;
            continue;
        }
        std::string inner = s.substr(start, close - start);
        s.replace(pos, close + mark.size() - pos, inner);
        pos += inner.size();
    }
}

std::string strip_markdown(std::string s) {
    // ``` fences with an optional language name and newline.
    size_t pos = 0;
    while ((pos = s.find("```", pos)) != std::string::npos) {
        size_t end = pos + 3;
        while (end < s.size() && is_alpha(s[end])) end++;
        if (end < s.size() && s[end] == '\n') end++;
        s.erase(pos, end - pos);
    }
    s.erase(std::remove(s.begin(), s.end(), '`'), s.end());
    strip_pairs(s, "**");
    strip_pairs(s, "__");

    // Line-by-line rules: headings, bullets, quotes.
    std::string out;
    size_t line_start = 0;
    while (line_start <= s.size()) {
        size_t nl = s.find('\n', line_start);
        std::string line = s.substr(line_start, nl == std::string::npos ? std::string::npos : nl - line_start);

        // Headings: up to 3 spaces, 1-6 #, then any spaces.
        size_t i = 0;
        while (i < line.size() && i < 3 && line[i] == ' ') i++;
        size_t hashes = 0;
        while (i + hashes < line.size() && line[i + hashes] == '#') hashes++;
        if (hashes >= 1 && hashes <= 6) {
            size_t j = i + hashes;
            while (j < line.size() && (line[j] == ' ' || line[j] == '\t')) j++;
            line = line.substr(j);
        }

        // Bullets "* x" or "+ x" -> "- x".
        size_t k = 0;
        while (k < line.size() && (line[k] == ' ' || line[k] == '\t')) k++;
        if (k < line.size() && (line[k] == '*' || line[k] == '+') && k + 1 < line.size() &&
            (line[k + 1] == ' ' || line[k + 1] == '\t')) {
            size_t j = k + 1;
            while (j < line.size() && (line[j] == ' ' || line[j] == '\t')) j++;
            line = "- " + line.substr(j);
        }

        // Block quotes "> x" -> "x".
        k = 0;
        while (k < line.size() && (line[k] == ' ' || line[k] == '\t')) k++;
        if (k < line.size() && line[k] == '>') {
            size_t j = k + 1;
            if (j < line.size() && line[j] == ' ') j++;
            line = line.substr(j);
        }

        out += line;
        if (nl == std::string::npos) break;
        out += '\n';
        line_start = nl + 1;
    }
    return out;
}

// Each non-ASCII UTF-8 character becomes one '?'.
std::string ascii_only(const std::string &s) {
    std::string out;
    out.reserve(s.size());
    for (size_t i = 0; i < s.size(); i++) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x80) {
            out += static_cast<char>(c);
            continue;
        }
        out += '?';
        size_t extra = (c >= 0xF0) ? 3 : (c >= 0xE0) ? 2 : (c >= 0xC0) ? 1 : 0;
        while (extra-- > 0 && i + 1 < s.size() && (static_cast<unsigned char>(s[i + 1]) & 0xC0) == 0x80) i++;
    }
    return out;
}

// "\n" + whitespace + "\n"... -> "\n\n".
std::string collapse_blank_lines(const std::string &s) {
    std::string out;
    size_t i = 0;
    while (i < s.size()) {
        if (s[i] == '\n') {
            size_t j = i + 1;
            size_t last_nl = std::string::npos;
            while (j < s.size() && is_space(s[j])) {
                if (s[j] == '\n') last_nl = j;
                j++;
            }
            if (last_nl != std::string::npos) {
                out += "\n\n";
                i = last_nl + 1;
                continue;
            }
        }
        out += s[i];
        i++;
    }
    return out;
}

std::string trim(const std::string &s) {
    size_t a = 0, b = s.size();
    while (a < b && is_space(s[a])) a++;
    while (b > a && is_space(s[b - 1])) b--;
    return s.substr(a, b - a);
}

// Greedy word wrap like Python's textwrap.wrap(break_long_words=True,
// break_on_hyphens=False).
void wrap_paragraph(const std::string &para, int width, std::vector<std::string> &lines) {
    std::vector<std::string> words;
    std::string word;
    for (char c : para) {
        if (is_space(c)) {
            if (!word.empty()) words.push_back(word);
            word.clear();
        } else {
            word += c;
        }
    }
    if (!word.empty()) words.push_back(word);

    std::string line;
    for (std::string w : words) {
        while (true) {
            size_t need = line.empty() ? w.size() : line.size() + 1 + w.size();
            if (need <= static_cast<size_t>(width)) {
                if (!line.empty()) line += ' ';
                line += w;
                break;
            }
            if (w.size() > static_cast<size_t>(width)) {
                // Fill the current line with the start of the long word.
                size_t room = line.empty() ? width : width - line.size() - 1;
                if (room > 0 && !line.empty()) line += ' ';
                if (room == 0) {
                    lines.push_back(line);
                    line.clear();
                    continue;
                }
                line += w.substr(0, room);
                w = w.substr(room);
                lines.push_back(line);
                line.clear();
                if (w.empty()) break;
                continue;
            }
            lines.push_back(line);
            line.clear();
        }
    }
    if (!line.empty()) lines.push_back(line);
}

}  // namespace

std::string to_ascii(const std::string &input) {
    std::string text = input;
    for (const Pair &p : SYMBOLS) replace_all(text, p.from, p.to);
    text = strip_latex(text);
    text = strip_markdown(text);
    text = ascii_only(text);
    text = collapse_blank_lines(text);
    return trim(text);
}

std::vector<std::string> to_screen_lines(const std::string &text, int width) {
    std::vector<std::string> lines;
    std::string ascii = to_ascii(text);
    size_t start = 0;
    while (true) {
        size_t nl = ascii.find('\n', start);
        std::string para = ascii.substr(start, nl == std::string::npos ? std::string::npos : nl - start);
        if (trim(para).empty()) {
            lines.push_back("");
        } else {
            wrap_paragraph(para, width, lines);
        }
        if (nl == std::string::npos) break;
        start = nl + 1;
    }
    return lines;
}

// Reads text on stdin and prints the screen lines, one per line, for tests.
#include <iostream>
#include <iterator>
#include <string>

#include "../ti84_dongle/calc_text.h"

int main(int argc, char **argv) {
    int width = argc > 1 ? std::stoi(argv[1]) : SCREEN_WIDTH;
    std::string text((std::istreambuf_iterator<char>(std::cin)), std::istreambuf_iterator<char>());
    for (const std::string &line : to_screen_lines(text, width)) std::cout << line << "\n";
    return 0;
}

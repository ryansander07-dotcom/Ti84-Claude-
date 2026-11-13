// Ask Claude a question, optionally with a JPEG photo, over HTTPS.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include <string>

struct ClaudeReply {
    bool ok;
    std::string text;  // the answer, or a short error to show on the calculator
};

// Called often while waiting on Claude; return true to give up (the calculator
// cancelled).
void claude_set_cancel_check(bool (*check)());

ClaudeReply ask_claude(const std::string &question, const uint8_t *jpeg = nullptr, size_t jpeg_len = 0);

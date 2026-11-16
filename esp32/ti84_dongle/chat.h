// Calculator-to-calculator chat over the internet.
//
// Two dongles with the same pair code talk through ntfy.sh, a free public
// message relay. The pair code picks a hidden topic name and the encryption key
// (AES-256-GCM), so ntfy.sh and anyone else only ever see scrambled bytes.
// ntfy.sh keeps messages for about 12 hours, so a dongle that was off catches
// up when it comes back.
#pragma once

#include <string>
#include <vector>

void chat_begin();

std::string chat_code();  // "" until one is set
std::string chat_name();  // this calculator's name in the chat

// Set the pair code (both calculators type the same one). Clears the
// messages shown so far. An empty code turns chat off. Returns an error to
// show, or "" when saved.
std::string chat_set_code(const std::string &code);
std::string chat_set_name(const std::string &name);

// Send a message. Returns an error to show, or "" when it was sent.
std::string chat_send(const std::string &text);

// How many messages from the other calculator haven't been looked at.
int chat_unread();

// The conversation as screen lines, newest message first. Marks all as read.
std::vector<std::string> chat_view();

// One line for STATUS, such as "Chat: connected" or "Chat: no pair code".
std::string chat_status();

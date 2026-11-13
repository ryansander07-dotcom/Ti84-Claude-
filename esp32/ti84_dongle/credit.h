// An estimate of how much API credit is left. The API doesn't tell an API key
// its balance, so the dongle keeps its own count: you enter your balance from
// the calculator (the number on platform.claude.com under Billing), and every
// answer subtracts its cost, worked out from the tokens it used.
#pragma once

#include <string>

void credit_begin();

// Record one reply's token usage, priced for the model that answered.
void credit_add_usage(const std::string &model, long input, long output, long cache_write, long cache_read);

// The API said the balance is too low: show it as empty until it's set again.
void credit_mark_empty();

// Start counting down from this balance, in dollars.
void credit_set_balance(double dollars);

bool credit_known();   // has a balance been entered?
double credit_left();  // dollars, estimated; 0 when empty
double credit_last();  // cost of the most recent answer, dollars

enum CreditState { CREDIT_UNKNOWN, CREDIT_OK, CREDIT_LOW, CREDIT_EMPTY };
CreditState credit_state();

// One short line for the calculator, such as "Credit left: ~$4.62".
std::string credit_line();

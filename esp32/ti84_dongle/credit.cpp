#include "credit.h"

#include <Arduino.h>
#include <Preferences.h>

#include <cstring>

#include "config.h"

namespace {

Preferences prefs;
bool known = false;
bool empty = false;
double balance = 0;  // what the user entered
double spent = 0;    // estimated spend since then
double last = 0;

struct Price {
    const char *model;  // matched as a prefix of the model that answered
    double input, output, cache_read;  // dollars per million tokens
};

// Claude API list prices. Cache writes cost 1.25x input (5-minute cache).
// Server-side fallbacks can answer with an older Opus, so those are listed too.
const Price PRICES[] = {
    {"claude-opus-5-5", 4.00, 20.00, 0.20},
    {"claude-opus-5", 5.00, 25.00, 0.50},
    {"claude-opus-4", 5.00, 25.00, 0.50},
    {"claude-sonnet-5", 2.00, 10.00, 0.10},
    {"claude-haiku-5-5", 0.10, 0.50, 0.01},
};
const Price FALLBACK_PRICE = {"", 5.00, 25.00, 0.50};  // unknown model: assume Opus pricing

const Price &price_for(const std::string &model) {
    for (const Price &p : PRICES)
        if (model.rfind(p.model, 0) == 0) return p;
    return FALLBACK_PRICE;
}

void save() {
    prefs.begin("credit", false);
    prefs.putBool("known", known);
    prefs.putBool("empty", empty);
    prefs.putDouble("balance", balance);
    prefs.putDouble("spent", spent);
    prefs.end();
}

}  // namespace

void credit_begin() {
    prefs.begin("credit", true);
    known = prefs.getBool("known", false);
    empty = prefs.getBool("empty", false);
    balance = prefs.getDouble("balance", 0);
    spent = prefs.getDouble("spent", 0);
    prefs.end();
}

void credit_add_usage(const std::string &model, long input, long output, long cache_write, long cache_read) {
    const Price &p = price_for(model);
    last = (input * p.input + output * p.output + cache_write * p.input * 1.25 + cache_read * p.cache_read) / 1e6;
    spent += last;
    if (known) save();
}

void credit_mark_empty() {
    empty = true;
    save();
}

void credit_set_balance(double dollars) {
    known = true;
    empty = dollars <= 0;
    balance = dollars;
    spent = 0;
    save();
}

bool credit_known() { return known; }

double credit_left() {
    if (empty) return 0;
    double left = balance - spent;
    return left > 0 ? left : 0;
}

double credit_last() { return last; }

CreditState credit_state() {
    if (empty) return CREDIT_EMPTY;
    if (!known) return CREDIT_UNKNOWN;
    double left = credit_left();
    if (left <= 0) return CREDIT_EMPTY;
    return left < CREDIT_LOW_USD ? CREDIT_LOW : CREDIT_OK;
}

std::string credit_line() {
    char buf[40];
    switch (credit_state()) {
        case CREDIT_EMPTY: return "Out of API credit.";
        case CREDIT_UNKNOWN: return "Credit: not set yet";
        default:
            snprintf(buf, sizeof buf, "Credit left: ~$%.2f", credit_left());
            return buf;
    }
}

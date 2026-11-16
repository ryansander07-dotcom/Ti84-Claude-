// Raw HTTPS call to the Claude Messages API. Mirrors bridge/claude_client.py:
// same system prompt, model, effort, and error messages.
#include "claude.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <mbedtls/base64.h>

#include <cctype>
#include <cstring>

#include "config.h"
#include "credit.h"
#include "secrets.h"
#include "tls_roots.h"

namespace {

const char *HOST = "api.anthropic.com";

bool (*cancel_check)() = nullptr;
void (*tick_fn)() = nullptr;
bool cancelled() {
    if (tick_fn) tick_fn();
    return cancel_check && cancel_check();
}

const char *SYSTEM_PROMPT =
    "You answer questions for a student using a TI-84 Plus CE graphing calculator.\n"
    "Your reply is shown on its small screen, 26 characters wide and 10 lines tall,\n"
    "so the student scrolls to read it.\n"
    "\n"
    "Rules for every reply:\n"
    "- Plain ASCII text only. No Markdown, no LaTeX, no emoji, no Unicode symbols.\n"
    "- Write math the way you would type it on the calculator: x^2, sqrt(x),\n"
    "  (a+b)/(c+d), pi, 3*x, <=, >=.\n"
    "- Keep it short. For a math problem, give the key steps on separate lines,\n"
    "  one step per line, then a last line that starts with \"ANSWER:\".\n"
    "- For anything else, answer in at most 6 short sentences.\n"
    "- If a photo is unreadable or cut off, say what you can read and ask for a\n"
    "  clearer photo instead of guessing.\n";

const char *PHOTO_PROMPT = "Solve the math problem in this photo.";

std::string json_string(const std::string &s) {
    std::string out = "\"";
    for (unsigned char c : s) {
        switch (c) {
            case '"': out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    snprintf(buf, sizeof buf, "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    return out + "\"";
}

std::string trim(const std::string &s) {
    size_t a = 0, b = s.size();
    while (a < b && isspace(static_cast<unsigned char>(s[a]))) a++;
    while (b > a && isspace(static_cast<unsigned char>(s[b - 1]))) b--;
    return s.substr(a, b - a);
}

bool uses_fallbacks() { return strcmp(CLAUDE_MODEL, "claude-opus-5-5") == 0; }

// Request body, with the photo base64-encoded straight into the string.
// Large strings land in PSRAM automatically.
bool build_body(const std::string &question, const uint8_t *jpeg, size_t jpeg_len, std::string &body) {
    std::string text = trim(question);
    if (text.empty()) text = PHOTO_PROMPT;

    std::string head = "{\"model\":" + json_string(CLAUDE_MODEL) +
                       ",\"max_tokens\":" + std::to_string(CLAUDE_MAX_TOKENS) +
                       ",\"system\":" + json_string(SYSTEM_PROMPT) +
                       ",\"output_config\":{\"effort\":" + json_string(CLAUDE_EFFORT) + "}";
    if (uses_fallbacks()) head += ",\"fallbacks\":\"default\"";
    head += ",\"messages\":[{\"role\":\"user\",\"content\":[";
    std::string tail = "{\"type\":\"text\",\"text\":" + json_string(text) + "}]}]}";

    size_t b64_len = 0;
    std::string image_head;
    const std::string image_tail = "\"}},";
    if (jpeg && jpeg_len) {
        image_head = "{\"type\":\"image\",\"source\":{\"type\":\"base64\",\"media_type\":\"image/jpeg\",\"data\":\"";
        b64_len = 4 * ((jpeg_len + 2) / 3);
    }

    body.clear();
    body.reserve(head.size() + image_head.size() + b64_len + image_tail.size() + tail.size() + 1);
    body += head;
    if (b64_len) {
        body += image_head;
        size_t start = body.size();
        body.resize(start + b64_len + 1);
        size_t written = 0;
        int rc = mbedtls_base64_encode(reinterpret_cast<unsigned char *>(&body[start]), b64_len + 1, &written,
                                       jpeg, jpeg_len);
        if (rc != 0) return false;
        body.resize(start + written);
        body += image_tail;
    }
    body += tail;
    return true;
}

bool write_all(WiFiClientSecure &client, const char *data, size_t len) {
    uint32_t deadline = millis() + 60000;
    while (len > 0) {
        size_t chunk = len < 4096 ? len : 4096;
        if (cancelled()) return false;
        size_t n = client.write(reinterpret_cast<const uint8_t *>(data), chunk);
        if (n == 0) {
            if (!client.connected() || millis() > deadline) return false;
            delay(5);
            continue;
        }
        data += n;
        len -= n;
    }
    return true;
}

std::string lower(std::string s) {
    for (char &c : s) c = static_cast<char>(tolower(static_cast<unsigned char>(c)));
    return s;
}

// Undo "Transfer-Encoding: chunked".
std::string dechunk(const std::string &raw) {
    std::string out;
    size_t pos = 0;
    while (pos < raw.size()) {
        size_t eol = raw.find("\r\n", pos);
        if (eol == std::string::npos) break;
        size_t size = strtoul(raw.substr(pos, eol - pos).c_str(), nullptr, 16);
        if (size == 0) break;
        pos = eol + 2;
        out.append(raw, pos, size);
        pos += size + 2;
    }
    return out;
}

ClaudeReply fail(const char *msg) { return {false, msg}; }

}  // namespace

void claude_set_cancel_check(bool (*check)()) { cancel_check = check; }
void claude_set_tick(void (*tick)()) { tick_fn = tick; }

ClaudeReply ask_claude(const std::string &question, const uint8_t *jpeg, size_t jpeg_len) {
    if (strlen(ANTHROPIC_API_KEY) == 0) return fail("No API key on the dongle. Add it to secrets.h and reflash.");
    // Wi-Fi sometimes drops for a moment; the background task rejoins within a
    // few seconds, so wait for it before giving up.
    for (uint32_t t = millis(); WiFi.status() != WL_CONNECTED && millis() - t < 10000;) {
        if (cancelled()) return fail("Cancelled.");
        delay(100);
    }
    if (WiFi.status() != WL_CONNECTED) return fail("No Wi-Fi. Pick a network in the Wi-Fi menu.");

    std::string body;
    if (!build_body(question, jpeg, jpeg_len, body)) return fail("Photo too big to send.");

    cancelled();  // first "still working" signal before the connection starts
    WiFiClientSecure client;
    client.setCACert(TLS_ROOTS);
    client.setTimeout(30);  // seconds, for connect and the TLS handshake
    // Another connection (chat) may be mid-handshake; on a small chip that can
    // make this one fail at first, so try a few times.
    bool connected = false;
    for (int i = 0; i < 4 && !(connected = client.connect(HOST, 443)); i++) {
        if (cancelled()) return fail("Cancelled.");
        delay(1500);
    }
    if (!connected) return fail("No internet connection.");

    std::string headers = "POST /v1/messages HTTP/1.1\r\n";
    headers += "Host: " + std::string(HOST) + "\r\n";
    headers += "x-api-key: " + std::string(ANTHROPIC_API_KEY) + "\r\n";
    headers += "anthropic-version: 2026-10-21\r\n";
    if (uses_fallbacks()) headers += "anthropic-beta: server-side-fallback-2026-07-01\r\n";
    headers += "content-type: application/json\r\n";
    headers += "content-length: " + std::to_string(body.size()) + "\r\n";
    headers += "connection: close\r\n\r\n";

    if (!write_all(client, headers.data(), headers.size()) || !write_all(client, body.data(), body.size())) {
        client.stop();
        if (cancelled()) return fail("Cancelled.");
        return fail("Lost the connection while sending. Try again.");
    }
    std::string().swap(body);  // free the photo copy before reading

    // Read the whole response; the server closes the connection when done.
    std::string raw;
    uint32_t deadline = millis() + CLAUDE_TIMEOUT_MS;
    uint8_t buf[1024];
    while (client.connected() || client.available()) {
        if (cancelled()) {
            client.stop();
            return fail("Cancelled.");
        }
        int n = client.available();
        if (n > 0) {
            int got = client.read(buf, n < (int)sizeof buf ? n : (int)sizeof buf);
            if (got > 0) raw.append(reinterpret_cast<char *>(buf), got);
            deadline = millis() + CLAUDE_TIMEOUT_MS;
        } else if (millis() > deadline) {
            client.stop();
            return fail("Claude took too long. Try again.");
        } else {
            delay(20);
        }
    }
    client.stop();

    size_t split = raw.find("\r\n\r\n");
    if (split == std::string::npos || raw.compare(0, 5, "HTTP/") != 0) return fail("No internet connection.");
    std::string head = lower(raw.substr(0, split));
    std::string payload = raw.substr(split + 4);
    std::string().swap(raw);
    if (head.find("transfer-encoding: chunked") != std::string::npos) payload = dechunk(payload);

    int status = atoi(head.c_str() + head.find(' ') + 1);
    if (status != 200) {
        // The API explains every error in {"error": {"message": ...}}.
        JsonDocument err;
        std::string reason;
        if (!deserializeJson(err, payload.data(), payload.size())) reason = err["error"]["message"] | "";
        if (reason.find("credit balance") != std::string::npos) {
            credit_mark_empty();
            return fail("No API credit left. Add credits at platform.claude.com under Billing, then enter the new balance in the Credit menu.");
        }
        if (status == 401) return fail("API key not accepted. Check secrets.h and reflash.");
        if (status == 403) return fail("API key can't use this model or has no credit.");
        if (status == 429) return fail("Too many requests. Wait a minute and try again.");
        std::string msg = "Claude API error " + std::to_string(status) + ".";
        if (!reason.empty()) msg += " " + reason.substr(0, 120);
        return {false, msg};
    }

    JsonDocument filter;
    filter["stop_reason"] = true;
    filter["content"][0]["type"] = true;
    filter["content"][0]["text"] = true;
    filter["model"] = true;
    filter["usage"] = true;
    JsonDocument doc;
    if (deserializeJson(doc, payload.data(), payload.size(), DeserializationOption::Filter(filter))) {
        return fail("Claude's reply got garbled. Try again.");
    }

    // Count what this answer cost, for the credit estimate. "model" is the model
    // that actually answered (a fallback model if the first one declined).
    JsonObject usage = doc["usage"];
    credit_add_usage(doc["model"] | CLAUDE_MODEL, usage["input_tokens"] | 0L, usage["output_tokens"] | 0L,
                     usage["cache_creation_input_tokens"] | 0L, usage["cache_read_input_tokens"] | 0L);

    const char *stop = doc["stop_reason"] | "";
    if (strcmp(stop, "refusal") == 0) return fail("Claude declined to answer that one.");

    std::string text;
    for (JsonObject block : doc["content"].as<JsonArray>()) {
        if (strcmp(block["type"] | "", "text") == 0) text += block["text"] | "";
    }
    text = trim(text);
    if (text.empty()) return fail("Claude sent back an empty answer. Try again.");
    if (strcmp(stop, "max_tokens") == 0) text += "\n(answer cut off)";
    return {true, text};
}

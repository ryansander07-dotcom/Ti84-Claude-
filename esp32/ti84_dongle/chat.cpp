#include "chat.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <esp_random.h>
#include <mbedtls/base64.h>
#include <mbedtls/gcm.h>
#include <mbedtls/sha256.h>

#include <algorithm>
#include <cctype>
#include <cstring>

#include "calc_text.h"
#include "tls_roots.h"

namespace {

const char *HOST = "ntfy.sh";
const size_t MAX_MESSAGES = 20;
const size_t MAX_TEXT = 200;
const size_t MAX_NAME = 12;
const uint32_t STREAM_IDLE_MS = 90000;  // ntfy.sh sends a keepalive every 45 s

struct Message {
    std::string id;
    uint32_t time;  // unix seconds, from ntfy.sh
    std::string name;
    std::string text;
    bool mine;
};

SemaphoreHandle_t lock;
Preferences prefs;
std::string code, name, me;  // me: this dongle's id (its MAC), to spot our own messages
std::string topic;
uint8_t key[32];
std::vector<Message> log_;  // oldest first
std::string last_id;        // newest message seen, to resume the stream after a drop
uint32_t seen = 0;          // newest message time the calculator has shown
volatile int generation = 0;  // bumped when the pair code changes
volatile bool streaming = false;
uint32_t server_time = 0, server_millis = 0;  // ntfy.sh's clock, from its events

struct Lock {
    Lock() { xSemaphoreTake(lock, portMAX_DELAY); }
    ~Lock() { xSemaphoreGive(lock); }
};

void sha256(const std::string &text, uint8_t out[32]) {
    mbedtls_sha256(reinterpret_cast<const uint8_t *>(text.data()), text.size(), out, 0);
}

// Topic and key both come from the pair code, each through its own hash.
void derive() {
    uint8_t h[32];
    sha256("ti84-chat topic|" + code, h);
    char hex[33];
    for (int i = 0; i < 16; i++) snprintf(hex + 2 * i, 3, "%02x", h[i]);
    topic = std::string("ti84c") + hex;
    sha256("ti84-chat key|" + code, key);
}

void note_time(uint32_t t) {
    if (!t) return;
    server_time = t;
    server_millis = millis();
}

uint32_t now() { return server_time ? server_time + (millis() - server_millis) / 1000 : 0; }

std::string b64(const uint8_t *data, size_t len) {
    size_t out_len = 0;
    std::string out(4 * ((len + 2) / 3) + 1, '\0');
    mbedtls_base64_encode(reinterpret_cast<uint8_t *>(&out[0]), out.size(), &out_len, data, len);
    out.resize(out_len);
    return out;
}

// Encrypted message: base64(nonce 12 | ciphertext | tag 16).
// Plaintext: "1\n<sender id>\n<name>\n<text>".
std::string seal(const std::string &plain) {
    uint8_t nonce[12];
    esp_fill_random(nonce, sizeof nonce);
    std::vector<uint8_t> out(12 + plain.size() + 16);
    memcpy(out.data(), nonce, 12);
    mbedtls_gcm_context gcm;
    mbedtls_gcm_init(&gcm);
    mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, key, 256);
    int err = mbedtls_gcm_crypt_and_tag(&gcm, MBEDTLS_GCM_ENCRYPT, plain.size(), nonce, 12, nullptr, 0,
                                        reinterpret_cast<const uint8_t *>(plain.data()), out.data() + 12, 16,
                                        out.data() + 12 + plain.size());
    mbedtls_gcm_free(&gcm);
    return err ? "" : b64(out.data(), out.size());
}

bool open_sealed(const std::string &text, std::string &plain) {
    std::vector<uint8_t> raw(text.size());
    size_t len = 0;
    if (mbedtls_base64_decode(raw.data(), raw.size(), &len, reinterpret_cast<const uint8_t *>(text.data()),
                              text.size()) ||
        len < 12 + 16)
        return false;
    size_t n = len - 12 - 16;
    plain.assign(n, '\0');
    mbedtls_gcm_context gcm;
    mbedtls_gcm_init(&gcm);
    mbedtls_gcm_setkey(&gcm, MBEDTLS_CIPHER_ID_AES, key, 256);
    int err = mbedtls_gcm_auth_decrypt(&gcm, n, raw.data(), 12, nullptr, 0, raw.data() + 12 + n, 16,
                                       raw.data() + 12, reinterpret_cast<uint8_t *>(&plain[0]));
    mbedtls_gcm_free(&gcm);
    return err == 0;
}

// Add a message from ntfy.sh to the log (ignoring repeats and anything that
// doesn't decrypt with our key).
void take(const std::string &id, uint32_t time, const std::string &sealed) {
    std::string plain;
    if (!open_sealed(sealed, plain)) return;
    size_t a = plain.find('\n'), b = plain.find('\n', a + 1), c = plain.find('\n', b + 1);
    if (a == std::string::npos || b == std::string::npos || c == std::string::npos || plain.substr(0, a) != "1")
        return;
    Message m{id, time, plain.substr(b + 1, c - b - 1), plain.substr(c + 1), plain.substr(a + 1, b - a - 1) == me};
    Lock l;
    last_id = id;
    if (std::any_of(log_.begin(), log_.end(), [&](const Message &x) { return x.id == id; })) return;
    log_.push_back(m);
    if (log_.size() > MAX_MESSAGES) log_.erase(log_.begin());
}

// Read one line from the connection; false if it closed or went quiet too long.
bool read_line(WiFiClientSecure &c, std::string &line, int gen) {
    line.clear();
    uint32_t last = millis();
    while (gen == generation) {
        while (c.available()) {
            int ch = c.read();
            if (ch < 0) break;
            last = millis();
            if (ch == '\n') return true;
            if (ch != '\r' && line.size() < 2048) line += static_cast<char>(ch);
        }
        if (!c.connected() || millis() - last > STREAM_IDLE_MS) return false;
        delay(20);
    }
    return false;
}

// Keep a streaming connection to ntfy.sh open and collect new messages.
void stream_task(void *) {
    for (;;) {
        std::string t, since;
        int gen;
        {
            Lock l;
            t = topic;
            since = last_id.empty() ? "all" : last_id;
            gen = generation;
        }
        if (code.empty() || WiFi.status() != WL_CONNECTED) {
            streaming = false;
            delay(1000);
            continue;
        }
        WiFiClientSecure c;
        c.setCACert(TLS_ROOTS);
        c.setTimeout(20);
        if (!c.connect(HOST, 443)) {
            streaming = false;
            delay(5000);
            continue;
        }
        // HTTP/1.0 so the reply isn't chunked: one JSON event per line.
        std::string req = "GET /" + t + "/json?since=" + since + " HTTP/1.0\r\nHost: ntfy.sh\r\n" +
                          "User-Agent: ti84-dongle\r\n\r\n";
        c.write(reinterpret_cast<const uint8_t *>(req.data()), req.size());
        std::string line;
        bool ok = read_line(c, line, gen) && line.find(" 200") != std::string::npos;
        while (ok && read_line(c, line, gen) && !line.empty()) {
        }  // headers
        streaming = ok;
        while (ok && read_line(c, line, gen)) {
            JsonDocument doc;
            if (deserializeJson(doc, line)) continue;
            note_time(doc["time"] | 0u);
            if (strcmp(doc["event"] | "", "message") == 0)
                take(doc["id"] | "", doc["time"] | 0u, doc["message"] | "");
        }
        c.stop();
        streaming = false;
        if (gen == generation) delay(2000);
    }
}

std::string clean(const std::string &s, size_t max_len) {
    std::string out;
    for (char ch : to_ascii(s)) {
        if (ch == '\n' || ch == '\r' || ch == '\t') ch = ' ';
        if (isprint(static_cast<unsigned char>(ch))) out += ch;
    }
    size_t a = out.find_first_not_of(' '), b = out.find_last_not_of(' ');
    out = a == std::string::npos ? "" : out.substr(a, b - a + 1);
    return out.substr(0, max_len);
}

std::string ago(uint32_t t) {
    uint32_t n = now();
    if (!n || !t || t > n) return "";
    uint32_t d = n - t;
    if (d < 60) return "now";
    if (d < 3600) return std::to_string(d / 60) + "m ago";
    if (d < 86400) return std::to_string(d / 3600) + "h ago";
    return std::to_string(d / 86400) + "d ago";
}

}  // namespace

void chat_begin() {
    lock = xSemaphoreCreateMutex();
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char buf[16];
    snprintf(buf, sizeof buf, "%02x%02x%02x%02x%02x%02x", mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    me = buf;
    snprintf(buf, sizeof buf, "Calc-%02X%02X", mac[4], mac[5]);
    prefs.begin("chat", true);
    code = prefs.getString("code", "").c_str();
    name = prefs.getString("name", buf).c_str();
    seen = prefs.getUInt("seen", 0);
    prefs.end();
    derive();
    xTaskCreate(stream_task, "chat", 12288, nullptr, 1, nullptr);
}

std::string chat_code() { return code; }
std::string chat_name() { return name; }

std::string chat_set_code(const std::string &raw) {
    std::string c = clean(raw, 40);
    for (char &ch : c) ch = static_cast<char>(tolower(static_cast<unsigned char>(ch)));
    if (!c.empty() && c.size() < 6) return "Use at least 6 letters or numbers, so nobody else picks the same code.";
    if (c.empty() && !raw.empty()) return "Type a pair code first.";
    Lock l;
    code = c;
    derive();
    log_.clear();
    last_id.clear();
    seen = 0;
    generation = generation + 1;
    prefs.begin("chat", false);
    prefs.putString("code", code.c_str());
    prefs.putUInt("seen", 0);
    prefs.end();
    return "";
}

std::string chat_set_name(const std::string &raw) {
    std::string n = clean(raw, MAX_NAME);
    if (n.empty()) return "Type a name first.";
    Lock l;
    name = n;
    prefs.begin("chat", false);
    prefs.putString("name", name.c_str());
    prefs.end();
    return "";
}

std::string chat_send(const std::string &raw) {
    if (code.empty()) return "Set a pair code first.";
    std::string text = clean(raw, MAX_TEXT);
    if (text.empty()) return "Type a message first.";
    if (WiFi.status() != WL_CONNECTED) return "No Wi-Fi. Pick a network in the Wi-Fi menu.";
    std::string t, body;
    {
        Lock l;
        t = topic;
        body = seal("1\n" + me + "\n" + name + "\n" + text);
    }
    if (body.empty()) return "Couldn't lock the message. Try again.";

    WiFiClientSecure c;
    c.setCACert(TLS_ROOTS);
    c.setTimeout(20);
    if (!c.connect(HOST, 443)) return "No internet connection.";
    std::string req = "POST /" + t + " HTTP/1.0\r\nHost: ntfy.sh\r\nUser-Agent: ti84-dongle\r\n" +
                      "Content-Length: " + std::to_string(body.size()) + "\r\n\r\n" + body;
    c.write(reinterpret_cast<const uint8_t *>(req.data()), req.size());
    std::string reply;
    uint32_t start = millis();
    while ((c.connected() || c.available()) && millis() - start < 20000) {
        while (c.available()) reply += static_cast<char>(c.read());
        delay(10);
    }
    c.stop();
    size_t split = reply.find("\r\n\r\n");
    if (reply.find(" 200") == std::string::npos || split == std::string::npos) {
        if (reply.find(" 429") != std::string::npos) return "Sending too fast. Wait a minute.";
        return "Couldn't send. Try again.";
    }
    JsonDocument doc;
    if (!deserializeJson(doc, reply.substr(split + 4))) {
        note_time(doc["time"] | 0u);
        Lock l;
        std::string id = doc["id"] | "";
        if (!std::any_of(log_.begin(), log_.end(), [&](const Message &x) { return x.id == id; })) {
            log_.push_back({id, doc["time"] | 0u, name, text, true});
            if (log_.size() > MAX_MESSAGES) log_.erase(log_.begin());
        }
    }
    return "";
}

int chat_unread() {
    Lock l;
    int n = 0;
    for (const Message &m : log_)
        if (!m.mine && m.time > seen) n++;
    return n;
}

std::vector<std::string> chat_view() {
    std::vector<std::string> out;
    Lock l;
    if (log_.empty()) {
        out.push_back("S:No messages yet.");
        out.push_back("S:");
        for (const std::string &s : to_screen_lines(
                 "Press [enter] to write one. The other calculator needs the same pair code."))
            out.push_back("S:" + s);
        return out;
    }
    uint32_t newest = seen;
    for (auto it = log_.rbegin(); it != log_.rend(); ++it) {
        std::string when = ago(it->time);
        std::string head = (it->mine ? std::string("You") : it->name) + (when.empty() ? "" : " (" + when + ")") + ":";
        if (!it->mine && it->time > seen) head = "* " + head;  // new since last look
        out.push_back("S:" + head.substr(0, SCREEN_WIDTH));
        for (const std::string &s : to_screen_lines(it->text)) out.push_back("A:" + s);
        out.push_back("S:");
        newest = std::max(newest, it->time);
    }
    out.pop_back();
    if (newest != seen) {
        seen = newest;
        prefs.begin("chat", false);
        prefs.putUInt("seen", seen);
        prefs.end();
    }
    return out;
}

std::string chat_status() {
    if (code.empty()) return "Chat: no pair code yet";
    return std::string("Chat: ") + (streaming ? "connected" : "connecting...") + " as " + name;
}

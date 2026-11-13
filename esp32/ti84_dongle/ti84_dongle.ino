// TI-84 Claude dongle for the Seeed XIAO ESP32S3 Sense.
//
// Plugs into the calculator's USB port with an OTG cable. The calculator is
// the USB host; this board shows up as a USB serial device and answers the
// protocol in the README: questions, camera previews, photos, Wi-Fi setup.
//
// Build settings (Arduino IDE Tools menu, or sketch.yaml for arduino-cli):
//   Board: XIAO_ESP32S3   USB Mode: USB-OTG (TinyUSB)   USB CDC On Boot: Disabled
//   PSRAM: OPI PSRAM      Partition Scheme: Huge APP

#include <Arduino.h>
#include <USB.h>
#include <USBCDC.h>

#include <string>

#include "calc_text.h"
#include "camera.h"
#include "claude.h"
#include "config.h"
#include "credit.h"
#include "wifi_store.h"

USBCDC Calc;

static std::string line_buf;
static uint8_t preview[PREVIEW_W * PREVIEW_H];

static void send_line(const std::string &line) {
    std::string out = line + "\n";
    Calc.write(reinterpret_cast<const uint8_t *>(out.data()), out.size());
}

static void send_bytes(const uint8_t *data, size_t len) {
    while (len > 0) {
        size_t n = Calc.write(data, len < 512 ? len : 512);
        if (n == 0) {
            delay(1);
            continue;
        }
        data += n;
        len -= n;
    }
}

static void send_wrapped(char kind, const std::string &text) {
    for (const std::string &line : to_screen_lines(text)) send_line(std::string(1, kind) + ":" + line);
}

static void send_error(const std::string &text) {
    send_wrapped('E', text);
    send_line("END");
}

// Machine-readable credit line for the calculator's menu: K:<cents left>,<state>
// with cents -1 when no balance has been entered, state 0 ok, 1 low, 2 empty, 3 not set.
static void send_credit_code() {
    CreditState st = credit_state();
    long cents = st == CREDIT_UNKNOWN ? -1 : (long)(credit_left() * 100 + 0.5);
    int code = st == CREDIT_OK ? 0 : st == CREDIT_LOW ? 1 : st == CREDIT_EMPTY ? 2 : 3;
    send_line("K:" + std::to_string(cents) + "," + std::to_string(code));
}

static void reply_with_claude(const ClaudeReply &reply) {
    send_wrapped(reply.ok ? 'A' : 'E', reply.text);
    CreditState st = credit_state();
    if (st == CREDIT_LOW || st == CREDIT_EMPTY) {
        send_line("S:");
        send_wrapped('S', st == CREDIT_LOW ? "! " + credit_line() + " Add credit soon." : "! " + credit_line());
    }
    send_credit_code();
    send_line("END");
}

static std::string after(const std::string &line, size_t prefix) {
    return line.size() > prefix ? line.substr(prefix) : "";
}

static void handle(const std::string &raw) {
    std::string line = raw;
    while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
    Serial.printf("calc> %.60s\n", line.c_str());

    if (line == "PING") {
        send_line("PONG");
        return;
    }

    if (line.rfind("Q:", 0) == 0) {
        std::string q = line.substr(2, MAX_QUESTION);
        if (q.find_first_not_of(' ') == std::string::npos) return send_error("Type a question first.");
        return reply_with_claude(ask_claude(q));
    }

    if (line == "VIEW") {
        if (!camera_ok()) return send_error("Camera not found.");
        if (!camera_preview(preview)) return send_error("Camera didn't send a picture.");
        char header[32];
        snprintf(header, sizeof header, "F:%d,%d,%d", PREVIEW_W, PREVIEW_H, PREVIEW_W * PREVIEW_H);
        send_line(header);
        send_bytes(preview, sizeof preview);
        send_line("END");
        return;
    }

    if (line == "SNAP") {
        if (!camera_ok()) return send_error("Camera not found.");
        if (!camera_snap()) return send_error("Couldn't take the picture. Try again.");
        send_line("S:Got it.");
        send_line("END");
        return;
    }

    if (line == "PHOTO" || line.rfind("PHOTO:", 0) == 0) {
        if (!camera_ok()) return send_error("Camera not found.");
        if (!camera_has_photo() && !camera_snap()) return send_error("Couldn't take the picture. Try again.");
        std::string note = line.size() > 6 ? line.substr(6, MAX_QUESTION) : "";
        size_t len = 0;
        const uint8_t *jpeg = camera_photo(&len);
        return reply_with_claude(ask_claude(note, jpeg, len));
    }

    if (line == "SCAN") {
        std::vector<std::string> names = wifi_scan();
        if (names.empty()) return send_error("No Wi-Fi networks found.");
        for (size_t i = 0; i < names.size() && i < 20; i++) send_line("N:" + names[i]);
        send_line("END");
        return;
    }

    if (line.rfind("WIFI:", 0) == 0) {
        std::string rest = line.substr(5);
        size_t tab = rest.find('\t');
        std::string ssid = rest.substr(0, tab);
        std::string pass = tab == std::string::npos ? "" : rest.substr(tab + 1);
        if (ssid.empty()) return send_error("Pick a network first.");
        if (!wifi_join(ssid, pass)) return send_error("Couldn't join " + ssid + ". Check the password.");
        send_wrapped('S', "Connected to " + ssid + ".");
        send_line("END");
        return;
    }

    if (line == "SAVED") {
        // C: the network it's on now (blank if none), then W: each remembered one.
        send_line("C:" + wifi_network());
        for (const std::string &name : wifi_saved()) send_line("W:" + name);
        send_line("END");
        return;
    }

    if (line.rfind("JOIN:", 0) == 0) {
        std::string ssid = after(line, 5);
        if (!wifi_join_saved(ssid)) return send_error("Couldn't join " + ssid + ". If its password changed, forget it and add it again.");
        send_wrapped('S', "Connected to " + ssid + ".");
        send_line("END");
        return;
    }

    if (line.rfind("FORGET:", 0) == 0) {
        std::string ssid = after(line, 7);
        if (!wifi_forget(ssid)) return send_error(ssid + " wasn't saved.");
        send_wrapped('S', "Forgot " + ssid + ".");
        send_line("END");
        return;
    }

    if (line == "CREDIT") {
        send_credit_code();
        send_wrapped('S', credit_line());
        if (credit_known() && credit_state() != CREDIT_EMPTY) send_line("S:(an estimate)");
        if (credit_last() > 0) {
            char buf[40];
            snprintf(buf, sizeof buf, "Last answer: ~$%.3f", credit_last());
            send_line(std::string("S:") + buf);
        }
        send_line("S:");
        if (!credit_known())
            send_wrapped('S', "Enter your balance from platform.claude.com (Billing) so the dongle can count down.");
        else
            send_wrapped('S', "After adding credit, enter the new balance.");
        send_line("END");
        return;
    }

    if (line.rfind("CREDIT:", 0) == 0) {
        std::string amount = after(line, 7);
        if (!amount.empty() && amount[0] == '$') amount = amount.substr(1);
        char *end = nullptr;
        double dollars = strtod(amount.c_str(), &end);
        if (amount.empty() || *end != '\0' || dollars < 0 || dollars > 100000)
            return send_error("Type the balance as a number, like 4.95.");
        credit_set_balance(dollars);
        send_credit_code();
        send_wrapped('S', "Saved. " + credit_line());
        send_line("END");
        return;
    }

    if (line == "STATUS") {
        if (wifi_connected()) {
            send_wrapped('S', "Wi-Fi: " + wifi_network());
            send_line("S:Signal: " + std::to_string(wifi_signal()) + " dBm");
        } else {
            send_line("S:Wi-Fi: not connected");
        }
        send_line("S:Saved networks: " + std::to_string(wifi_saved_count()));
        send_line(std::string("S:Camera: ") + (camera_ok() ? "ready" : "not found"));
        send_line("S:Model: " CLAUDE_MODEL);
        send_wrapped('S', credit_line());
        send_line("END");
        return;
    }

    send_error("Unknown message.");
}

void setup() {
    Serial.begin(115200);  // debug log on the UART pins, not the calculator
    USB.productName("TI-84 Claude Link");
    USB.manufacturerName("ti84-claude");
    Calc.begin();
    USB.begin();

    credit_begin();
    Serial.printf("camera: %s\n", camera_begin() ? "ok" : "not found");
    wifi_begin();
}

void loop() {
    while (Calc.available()) {
        int c = Calc.read();
        if (c < 0) break;
        if (c == '\n') {
            handle(line_buf);
            line_buf.clear();
        } else if (line_buf.size() < MAX_LINE) {
            line_buf += static_cast<char>(c);
        }
    }
    delay(2);
}

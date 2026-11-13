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

static void reply_with_claude(const ClaudeReply &reply) {
    send_wrapped(reply.ok ? 'A' : 'E', reply.text);
    send_line("END");
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

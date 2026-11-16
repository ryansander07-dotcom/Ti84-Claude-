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
#include <WiFi.h>

#include <functional>
#include <string>
#include <vector>

#include "calc_text.h"
#include "camera.h"
#include "chat.h"
#include "claude.h"
#include "config.h"
#include "credit.h"
#include "wifi_store.h"

#if defined(CONFIG_IDF_TARGET_ESP32S3)
// S3: the firmware runs the USB port itself (TinyUSB). Debug log goes to the UART pins.
#include <USB.h>
#include <USBCDC.h>
USBCDC Calc;
#define LOG(...) Serial.printf(__VA_ARGS__)
#else
// C3: the chip's built-in USB serial port is the calculator link (build with
// "USB CDC On Boot: Enabled"), so the debug log is switched off.
#define Calc Serial
#define LOG(...) \
    do {         \
    } while (0)
#endif

static std::string line_buf;
static void send_line(const std::string &line);

// The last answer, kept here so the calculator only holds one screenful.
// The calculator asks for more with PAGE:<first line>.
static std::vector<std::string> answer;
static const size_t PAGE_LINES = 9;

// The calculator sends this byte (CAN) when [clear] is pressed while it waits.
static const int CANCEL_BYTE = 0x18;
static bool cancel_requested() {
    while (Calc.available()) {
        int c = Calc.peek();
        if (c == CANCEL_BYTE) {
            Calc.read();
            return true;
        }
        if (c == '\n' || c == '\r') {
            Calc.read();
            continue;
        }
        return false;  // a new request: leave it for loop()
    }
    return false;
}

// While Claude works, send H:<seconds> every 2 s so the calculator can show a
// counter and knows the dongle is alive.
static uint32_t work_started = 0, last_tick = 0;
static void tick() {
    uint32_t now = millis();
    if (now - last_tick < 2000) return;
    last_tick = now;
    send_line("H:" + std::to_string((now - work_started) / 1000));
}
static void start_work() { work_started = last_tick = millis(); }

static void send_page(size_t first) {
    for (size_t i = first; i < answer.size() && i < first + PAGE_LINES; i++) send_line(answer[i]);
}
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
    answer.clear();
    char kind = reply.ok ? 'A' : 'E';
    for (const std::string &l : to_screen_lines(reply.text)) answer.push_back(std::string(1, kind) + ":" + l);
    CreditState st = credit_state();
    if (st == CREDIT_LOW || st == CREDIT_EMPTY) {
        answer.push_back("S:");
        for (const std::string &l : to_screen_lines(st == CREDIT_LOW ? "! " + credit_line() + " Add credit soon." : "! " + credit_line()))
            answer.push_back("S:" + l);
    }
    // P:<total lines>, then the first screenful; the rest on request.
    send_line("P:" + std::to_string(answer.size()));
    send_page(0);
    send_credit_code();
    send_line("END");
}

// Claude requests run in their own task so this loop stays free: it sends the
// heartbeat and notices [clear] right away, even while the slow TLS handshake
// is still going (several seconds on an ESP32-C3). After a cancel the task is
// told to stop and its answer is dropped.
struct ClaudeJob {
    std::function<ClaudeReply()> work;
    ClaudeReply reply;
};
static ClaudeJob *job = nullptr;
static volatile bool job_running = false;
static volatile bool job_abort = false;

static bool job_aborted() { return job_abort; }

static void claude_task(void *arg) {
    ClaudeJob *j = static_cast<ClaudeJob *>(arg);
    j->reply = j->work();
    job_running = false;
    vTaskDelete(nullptr);
}

// A cancelled request may still be finishing; wait before starting anything
// that uses the network, the camera or the photo it was sending.
static void wait_for_job() {
    while (job_running) delay(10);
}

// Run slow network work in the job task, with heartbeats and cancel. Returns
// false if the calculator cancelled (it has already left); otherwise the
// result is in job->reply.
static bool run_job(std::function<ClaudeReply()> work) {
    start_work();
    while (job_running) {  // the last cancelled request hasn't let go yet
        tick();
        if (cancel_requested()) return false;
        delay(10);
    }
    delete job;
    job = new ClaudeJob{work, {false, ""}};
    job_abort = false;
    job_running = true;
    if (xTaskCreate(claude_task, "claude", 16384, job, 1, nullptr) != pdPASS) {
        job_running = false;
        job->reply = {false, "The dongle is low on memory. Unplug it and plug it back in."};
        return true;
    }
    while (job_running) {
        tick();
        if (cancel_requested()) {
            job_abort = true;  // the calculator has already left this screen
            return false;
        }
        delay(10);
    }
    return true;
}

static void run_claude(const std::string &question, const uint8_t *jpeg = nullptr, size_t len = 0) {
    if (run_job([=] { return ask_claude(question, jpeg, len); })) reply_with_claude(job->reply);
}

// A paged list of lines kept here, like an answer, without the credit note.
static void send_paged(std::vector<std::string> lines) {
    answer = std::move(lines);
    send_line("P:" + std::to_string(answer.size()));
    send_page(0);
    send_line("END");
}

static void send_ok(const std::string &err, const std::string &ok_text) {
    if (!err.empty()) return send_error(err);
    send_wrapped('S', ok_text);
    send_line("END");
}

static std::string after(const std::string &line, size_t prefix) {
    return line.size() > prefix ? line.substr(prefix) : "";
}

static void handle(const std::string &raw) {
    std::string line = raw;
    while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) line.pop_back();
    LOG("calc> %.60s\n", line.c_str());

    if (line.empty()) return;  // a stray newline after a cancel

    if (line.rfind("PAGE:", 0) == 0) {
        send_page(strtoul(line.c_str() + 5, nullptr, 10));
        send_line("END");
        return;
    }

    if (line == "PING") {
        send_line("PONG");
        return;
    }

    if (line.rfind("Q:", 0) == 0) {
        std::string q = line.substr(2, MAX_QUESTION);
        if (q.find_first_not_of(' ') == std::string::npos) return send_error("Type a question first.");
        return run_claude(q);
    }

    if (line == "VIEW" || line == "SNAP" || line.rfind("PHOTO", 0) == 0 || line == "SCAN" ||
        line.rfind("WIFI:", 0) == 0 || line.rfind("JOIN:", 0) == 0 || line.rfind("FORGET:", 0) == 0)
        wait_for_job();

    if (line == "VIEW") {
        if (!camera_ok()) return send_error(HAS_CAMERA ? "Camera not found." : "This dongle has no camera.");
        if (!camera_preview(preview)) return send_error("Camera didn't send a picture.");
        char header[32];
        snprintf(header, sizeof header, "F:%d,%d,%d", PREVIEW_W, PREVIEW_H, PREVIEW_W * PREVIEW_H);
        send_line(header);
        send_bytes(preview, sizeof preview);
        send_line("END");
        return;
    }

    if (line == "SNAP") {
        if (!camera_ok()) return send_error(HAS_CAMERA ? "Camera not found." : "This dongle has no camera.");
        if (!camera_snap()) return send_error("Couldn't take the picture. Try again.");
        send_line("S:Got it.");
        send_line("END");
        return;
    }

    if (line == "PHOTO" || line.rfind("PHOTO:", 0) == 0) {
        if (!camera_ok()) return send_error(HAS_CAMERA ? "Camera not found." : "This dongle has no camera.");
        if (!camera_has_photo() && !camera_snap()) return send_error("Couldn't take the picture. Try again.");
        std::string note = line.size() > 6 ? line.substr(6, MAX_QUESTION) : "";
        size_t len = 0;
        const uint8_t *jpeg = camera_photo(&len);
        return run_claude(note, jpeg, len);
    }

    // Chat with another calculator (chat.h).
    if (line == "CHAT") return send_paged(chat_view());
    if (line == "CHATU") {
        send_line("U:" + std::to_string(chat_unread()));
        send_line("END");
        return;
    }
    if (line == "CHATINFO") {
        send_line("S:Pair code: " + (chat_code().empty() ? std::string("not set") : chat_code()));
        send_line("S:Your name: " + chat_name());
        send_wrapped('S', chat_status());
        send_line("END");
        return;
    }
    if (line.rfind("CHATCODE:", 0) == 0) return send_ok(chat_set_code(after(line, 9)), line.size() > 9 ? "Pair code saved." : "Chat turned off.");
    if (line.rfind("CHATNAME:", 0) == 0) return send_ok(chat_set_name(after(line, 9)), "Name saved.");
    if (line.rfind("CHATSEND:", 0) == 0) {
        std::string text = after(line, 9);
        if (!run_job([=] {
                std::string err = chat_send(text);
                return ClaudeReply{err.empty(), err};
            }))
            return;
        if (!job->reply.ok) return send_error(job->reply.text);
        return send_paged(chat_view());
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
            send_line("S:IP: " + std::string(WiFi.localIP().toString().c_str()));
        } else {
            send_line("S:Wi-Fi: not connected");
        }
        send_line("S:Saved networks: " + std::to_string(wifi_saved_count()));
#if HAS_CAMERA
        send_line(std::string("S:Camera: ") + (camera_ok() ? "ready" : "not found"));
#else
        send_line("S:Camera: none on this board");
#endif
        send_line("S:Model: " CLAUDE_MODEL);
        send_wrapped('S', credit_line());
        send_wrapped('S', chat_status());
        send_line("S:Free memory: " + std::to_string(ESP.getFreeHeap() / 1024) + " KB");
        send_line("END");
        return;
    }

    send_error("Unknown message.");
}

void setup() {
#if STATUS_LED_PIN >= 0
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, STATUS_LED_ON);  // on = the dongle has power
#endif

#if defined(CONFIG_IDF_TARGET_ESP32S3)
    Serial.begin(115200);  // debug log on the UART pins, not the calculator
    USB.productName("TI-84 Claude Link");
    USB.manufacturerName("ti84-claude");
    Calc.begin();
    USB.begin();
#else
    Calc.setTxTimeoutMs(50);  // don't stall long if the calculator stops reading
    Calc.begin(115200);
#endif

    credit_begin();
    claude_set_cancel_check(job_aborted);
#if HAS_CAMERA
    bool cam = false;
    for (int i = 0; i < 3 && !cam; i++) cam = camera_begin() || camera_ok();
    LOG("camera: %s\n", cam ? "ok" : "not found");
#endif
    wifi_begin();
    chat_begin();
}

void loop() {
    while (Calc.available()) {
        int c = Calc.read();
        if (c < 0) break;
        if (c == CANCEL_BYTE) continue;  // a cancel that arrived after the work was done
        if (c == '\n') {
            handle(line_buf);
            line_buf.clear();
        } else if (line_buf.size() < MAX_LINE) {
            line_buf += static_cast<char>(c);
        }
    }
    delay(2);
}

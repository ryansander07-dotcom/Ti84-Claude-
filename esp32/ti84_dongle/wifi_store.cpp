#include "wifi_store.h"

#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>

#include <algorithm>

#include "config.h"
#include "secrets.h"

namespace {

struct SavedNetwork {
    std::string ssid;
    std::string password;
};

std::vector<SavedNetwork> saved;  // most recently added first
SemaphoreHandle_t lock;
Preferences prefs;

void load() {
    saved.clear();
    prefs.begin("wifi", true);
    int n = prefs.getInt("count", 0);
    for (int i = 0; i < n && i < MAX_SAVED_NETWORKS; i++) {
        String s = prefs.getString(("s" + String(i)).c_str(), "");
        String p = prefs.getString(("p" + String(i)).c_str(), "");
        if (s.length()) saved.push_back({s.c_str(), p.c_str()});
    }
    prefs.end();
    if (strlen(WIFI_SSID) > 0) {
        bool known = std::any_of(saved.begin(), saved.end(), [](const SavedNetwork &n) { return n.ssid == WIFI_SSID; });
        if (!known) saved.push_back({WIFI_SSID, WIFI_PASSWORD});
    }
}

void store() {
    prefs.begin("wifi", false);
    prefs.clear();
    prefs.putInt("count", saved.size());
    for (size_t i = 0; i < saved.size(); i++) {
        prefs.putString(("s" + String(i)).c_str(), saved[i].ssid.c_str());
        prefs.putString(("p" + String(i)).c_str(), saved[i].password.c_str());
    }
    prefs.end();
}

bool connect_to(const std::string &ssid, const std::string &password, uint32_t timeout_ms) {
    WiFi.disconnect();
    WiFi.begin(ssid.c_str(), password.empty() ? nullptr : password.c_str());
    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        wl_status_t st = WiFi.status();
        if (st == WL_CONNECTED) return true;
        if (st == WL_CONNECT_FAILED || st == WL_NO_SSID_AVAIL) break;
        delay(100);
    }
    WiFi.disconnect();
    return false;
}

// Join the strongest remembered network in range. Call with the lock held.
void connect_best() {
    if (saved.empty()) return;
    int n = WiFi.scanNetworks();
    int best_rssi = -1000;
    const SavedNetwork *best = nullptr;
    for (int i = 0; i < n; i++) {
        std::string ssid = WiFi.SSID(i).c_str();
        for (const SavedNetwork &net : saved) {
            if (net.ssid == ssid && WiFi.RSSI(i) > best_rssi) {
                best_rssi = WiFi.RSSI(i);
                best = &net;
            }
        }
    }
    WiFi.scanDelete();
    if (best) connect_to(best->ssid, best->password, 12000);
}

void keep_connected(void *) {
    for (;;) {
        if (WiFi.status() != WL_CONNECTED && xSemaphoreTake(lock, 0) == pdTRUE) {
            connect_best();
            xSemaphoreGive(lock);
        }
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

}  // namespace

void wifi_begin() {
    lock = xSemaphoreCreateMutex();
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    load();
    xTaskCreatePinnedToCore(keep_connected, "wifi", 6144, nullptr, 1, nullptr, 0);
}

bool wifi_connected() { return WiFi.status() == WL_CONNECTED; }

std::string wifi_network() { return wifi_connected() ? WiFi.SSID().c_str() : ""; }

int wifi_signal() { return wifi_connected() ? WiFi.RSSI() : 0; }

int wifi_saved_count() { return saved.size(); }

std::vector<std::string> wifi_scan() {
    std::vector<std::pair<int, std::string>> found;
    if (xSemaphoreTake(lock, pdMS_TO_TICKS(30000)) != pdTRUE) return {};
    int n = WiFi.scanNetworks();
    for (int i = 0; i < n; i++) {
        std::string ssid = WiFi.SSID(i).c_str();
        if (ssid.empty()) continue;
        auto same = std::find_if(found.begin(), found.end(), [&](const auto &f) { return f.second == ssid; });
        if (same == found.end()) found.push_back({WiFi.RSSI(i), ssid});
        else same->first = std::max(same->first, (int)WiFi.RSSI(i));
    }
    WiFi.scanDelete();
    xSemaphoreGive(lock);
    std::sort(found.begin(), found.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
    std::vector<std::string> names;
    for (const auto &f : found) names.push_back(f.second);
    return names;
}

bool wifi_join(const std::string &ssid, const std::string &password) {
    if (xSemaphoreTake(lock, pdMS_TO_TICKS(30000)) != pdTRUE) return false;
    bool ok = connect_to(ssid, password, 15000);
    if (ok) {
        saved.erase(std::remove_if(saved.begin(), saved.end(), [&](const SavedNetwork &n) { return n.ssid == ssid; }),
                    saved.end());
        saved.insert(saved.begin(), {ssid, password});
        if (saved.size() > MAX_SAVED_NETWORKS) saved.resize(MAX_SAVED_NETWORKS);
        store();
    } else {
        connect_best();  // get back on a known network
    }
    xSemaphoreGive(lock);
    return ok;
}

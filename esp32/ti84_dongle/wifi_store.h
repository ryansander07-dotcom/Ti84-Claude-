// Remembered Wi-Fi networks, with a background task that keeps the dongle
// connected to the strongest one in range.
#pragma once

#include <string>
#include <vector>

void wifi_begin();
bool wifi_connected();
std::string wifi_network();
int wifi_signal();
int wifi_saved_count();

// Nearby network names, strongest first.
std::vector<std::string> wifi_scan();

// Join a network now. On success it is remembered for next time.
bool wifi_join(const std::string &ssid, const std::string &password);

// Remembered networks, most recently joined first.
std::vector<std::string> wifi_saved();

// Join a remembered network with its saved password.
bool wifi_join_saved(const std::string &ssid);

// Forget a network. Returns false if it wasn't saved.
bool wifi_forget(const std::string &ssid);

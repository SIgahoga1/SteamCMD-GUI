# ⚡ SteamCMD-GUI

> A modern Windows application for installing, configuring, and managing **Counter-Strike 2 Dedicated Servers** through an intuitive graphical interface.

🚧 **Current Version:** `v0.1.0` *(Initial Preview)*

SteamCMD-GUI is designed to simplify the deployment and administration of CS2 dedicated servers on Windows. It automates the installation process, integrates SteamCMD, and provides a powerful yet user-friendly interface for server management.

---

# ✨ Features

## 🚀 Easy Server Setup

* First-launch setup wizard
* Install a new CS2 dedicated server
* Connect to an existing server
* Restore from backups

## 📦 Automatic Installation

* SteamCMD
* Counter-Strike 2 Dedicated Server (`app_update 730`)
* Metamod:Source
* CounterStrikeSharp
* Ready-to-use server templates:

  * Public
  * Retake
  * Deathmatch
  * Bhop
  * Training
  * Custom

## 📊 Live Dashboard

* Online / Offline status
* Current map
* Server port
* Connected players
* Process ID (PID)
* CPU & RAM monitoring
* Component status
* Recent errors

## 🎮 Server Management

* Launch parameter editor
* Validate and update server files
* Execute RCON commands
* Change maps
* Run configuration files remotely

## 👥 Player Management

* Live player list via RCON
* Kick players
* Ban players
* Mute players
* Slay players
* Copy SteamID and IP addresses

## 💻 Built-in Console

* Real-time server output
* Colored log messages
* Command history
* Quick commands
* Search and filtering

## 🔌 Plugin Manager

* Metamod support
* CounterStrikeSharp support
* ZIP plugin installation
* Enable or disable plugins
* Automatic log error detection

## 🗺️ Map Management

* Automatic map scanning
* Custom map support
* Mapcycle editor
* Map list management
* Changelevel support

## ⚙️ Configuration Editor

* Syntax highlighting
* Built-in templates
* Automatic backup creation

## 👤 Server Profiles

* Multiple server profiles
* Clone profiles
* Export and import profiles

## 💾 Backup System

* Full backups
* Configuration backups
* Plugin backups
* Scheduled automatic backups
* Restore functionality

## 📜 Log Viewer

* Server logs
* Application logs
* Component logs
* Search and filtering
* Export support
* Diagnostic reports

## 🎨 Customizable Interface

* Multiple themes
* Custom accent colors
* Background customization
* Font settings
* Rounded UI elements
* Compact mode

Changes are applied instantly without restarting the application.

---

# 📁 Data Storage

Application settings and profiles are stored in:

```text
%APPDATA%\SteamCMDv2\
```

Including:

* `settings.json`
* `profiles.json`
* `logs/`
* `backups/`

---

# ▶️ Running from Source

```bash
py -3.12 -m pip install -r requirements.txt
py -3.12 main.py
```

---

# 📦 Building the Executable

Run:

```bash
BUILD_EXE.bat
```

or

```bash
py -3.12 build.py
```

The compiled executable will be available in:

```text
dist/SteamCMDv2.exe
```

---

# 📂 Project Structure

```text
main.py                  Application entry point
build.py                 PyInstaller build script

app/
 ├── gui/                User interface
 ├── core/               Core server logic
 ├── services/           Settings and utilities
 ├── models/             Data models
 └── assets/styles/      Themes and styles
```

---

# ⚠️ Version 0.1.0

This is the first public preview release of **SteamCMD-GUI**.

The project is currently under active development. New features, improvements, and bug fixes will be introduced in future releases.

Feedback and suggestions are always welcome.

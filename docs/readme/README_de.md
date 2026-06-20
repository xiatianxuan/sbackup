# Sbackup

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-green)](../../LICENSE)
[![PyPI](https://img.shields.io/pypi/v/sbackup-cli?color=blue)](https://pypi.org/project/sbackup-cli/)
[![Tests](https://img.shields.io/badge/tests-940%20passed-brightgreen)](../../.github/workflows/ci.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)]()

> Leichtgewichtiges, effizientes Ordner-Backup-Tool mit Kommandozeilenunterstuetzung zur einfachen Verwaltung Ihrer Backup-Strategien.

[English](../../README.md) | [Deutsch](README_de.md) | [Espanol](README_es.md) | [Francais](README_fr.md) | [Portugues](README_pt.md) | [Pycckuu](README_ru.md) | [日本語](README_ja.md) | [한국어](README_ko.md) | [中文](README_zh.md)

- [Ueberblick](#ueberblick)
- [Funktionen](#funktionen)
- [Schnellstart](#schnellstart)
  - [Installation](#installation)
  - [Verwendung](#verwendung)
- [Konfigurationsdatei](#konfigurationsdatei)
  - [Konfigurationsbeispiel](#konfigurationsbeispiel)
- [SFTP-Remote-Backup](#sftp-remote-backup)
- [WebDAV-Remote-Backup](#webdav-remote-backup)
- [Funktionsweise](#funktionsweise)
- [Entwicklerhandbuch](#entwicklerhandbuch)
  - [Tests ausfuehren](#tests-ausfuehren)
  - [Code-Struktur](#code-struktur)
- [Haeufig gestellte Fragen](#haeufig-gestellte-fragen)
- [Mitwirkungsrichtlinie](#mitwirkungsrichtlinie)
- [Lizenz](#lizenz)
- [Autor](#autor)

---

## Ueberblick

Sbackup ist ein leichtgewichtiges Ordner-Backup-Tool, mit dem Sie Backup-Strategien ueber die Kommandozeile hinzufuegen, loeschen und anzeigen koennen. Es basiert auf dem letzten Aenderungszeitpunkt eines Ordners, um zu entscheiden, ob ein Backup erforderlich ist, und stellt sicher, dass Ihre Daten stets aktuell bleiben.

## Funktionen

- **Inkrementelles Backup**: Nur geaenderte Ordner werden gesichert, was Zeit und Speicherplatz spart
- **Mehrere Formate**: Unterstuetzt ZIP, tar, tar.gz, tar.bz2, tar.xz, tar.zst und 7z -- sieben Packformate, global und pro Eintrag unabhaengig konfigurierbar
- **SFTP-Remote-Backup**: Basierend auf paramiko, unterstuetzt Passwort-/SSH-Schluessel-Authentifizierung mit automatischer Erkennung des Standardschluessels
- **WebDAV-Remote-Backup**: Basierend auf der Standardbibliothek urllib, ohne zusaetzliche Abhaengigkeiten, unterstuetzt Jianguoyun/NextCloud/Synology
- **S3-Cloud-Speicher**: Basierend auf minio, unterstuetzt alle S3-kompatiblen Speicher (AWS/MinIO/Alibaba Cloud OSS usw.)
- **Parallel-Backup auf mehrere Ziele**: Simultane Sicherung auf lokale und mehrere Remote-Ziele, unabhaengig voneinander
- **Backup-Wiederherstellung**: Entpacken und Wiederherstellen aus Backup-Dateien in ein angegebenes Verzeichnis, mit selektiver Wiederherstellung
- **Backup-Bereinigung**: Automatisches Loeschen alter Backups mit Strategien nach Anzahl/Zeit taeglicher Aufbewahrung
- **Verschluesselte Backups**: Passwortverschluesselung fuer 7z-Format und PBKDF2-Verschluesselung fuer alle Formate
- **Zeitgesteuerte Backups**: Intervallgesteuerte automatische Ausfuehrung, unterstuetzt Echtzeit-Dateiueberwachung (watchdog)
- **Backup-Verlauf**: Protokollierung von Zeitpunkt, Groesse und SHA256-Pruefsumme jedes Backups zur Nachverfolgung
- **Audit-Protokoll**: Protokollierung aller Backup-/Wiederherstellungsereignisse
- **Pre-/Post-Hooks**: Ausfuehren von benutzerdefinierten Befehlen vor und nach dem Backup
- **Konfigurationsprofile**: Speichern, Umschalten, Importieren und Exportieren mehrerer Konfigurationen
- **Suche ueber Archive hinweg**: Dateinamenssuche in mehreren Backup-Dateien
- **Datenintegritaet**: SHA256-Pruefsummen-Erzeugung und -Verifizierung, Reed-Solomon-Fehlerkorrektur
- **Konfigurationsvalidierung**: Automatische Pruefung der Konfigurationsparameter, Erkennung von Manipulationen
- **Aufgabenwarteschlange**: Verwaltung von Backup-Aufgaben mit Hinzufuegen, Ausfuehren und Abbrechen
- **Komprimierungs-Benchmark**: Vergleich der Komprimierungsleistung verschiedener Formate und Stufen
- **Speicherplatz-Schaetzung**: Backup-Groessenschaetzung nach Dateityp, Pruefung des Zielplatzes
- **Internationalisierung**: Unterstuetzt Chinesisch, Englisch, Franzoesisch, Spanisch, Russisch, Deutsch, Japanisch, Portugiesisch und Koreanisch
- **Shell-Autovervollstaendigung**: Unterstuetzt bash/zsh/fish/powershell
- **Leichtgewichtig und effizient**: Kleine Dateigroesse, schneller Start, geringer Ressourcenverbrauch
- **Plattformuebergreifend**: Unterstuetzt Windows, macOS und Linux

## Schnellstart

### Installation

#### Installation mit pip

```bash
pip install sbackup-cli
```

Nach der Installation verwenden Sie den Befehl `sbackup` (PyPI-Paketname: `sbackup-cli`, CLI-Befehl: `sbackup`).

#### Installation aus dem Quellcode

```bash
git clone https://github.com/xiatianxuan/sbackup.git
cd sbackup
uv sync
```

### Verwendung

#### Grundlegende Syntax

```bash
uv run python main.py <command> [options]
```

#### Verfuegbare Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `add` | Backup-Strategie hinzufuegen |
| `rm` / `remove` | Backup-Strategie loeschen |
| `edit` | Vorhandene Backup-Strategie bearbeiten |
| `all` | Alle Backup-Strategien anzeigen |
| `save` | Backup ausfuehren |
| `watch` | Backup zeitgesteuert ausfuehren |
| `restore` | Aus Backup-Datei wiederherstellen |
| `info` | Details einer Backup-Datei anzeigen |
| `diff` | Quellverzeichnis mit Backup vergleichen |
| `verify` | Integritaet der Backup-Datei pruefen |
| `search` | Dateien im Backup suchen |
| `xsearch` | Suche ueber mehrere Backup-Archive |
| `versions` | Backup-Versionsverlauf anzeigen |
| `sftp` | SFTP-Remote-Backup verwalten |
| `webdav` | WebDAV-Remote-Backup verwalten |
| `remote` | Remote-Dateiverwaltung (list/rm) |
| `task` | Backup-Aufgabenwarteschlange verwalten |
| `audit` | Audit-Protokoll abfragen |
| `hooks` | Pre-/Post-Hooks manuell ausfuehren |
| `profile` | Konfigurationsprofile verwalten |
| `rotate` | Backup-Rotation und Bereinigung |
| `clean` | Alte Backups bereinigen |
| `diskcheck` | Speicherplatz-Schaetzung |
| `benchmark` | Komprimierungsformat-Benchmark |
| `integrity` | Integritaetspruefung des Backup-Verzeichnisses |
| `dry-run` | Vorschau der Backup-Dateiauswahl |
| `export` / `import` | Backup-Strategien exportieren/importieren |
| `ignore` | .sbackupignore-Datei erstellen |
| `schedule` | Zeitgesteuerte Konfiguration exportieren |
| `webhook` | Webhook-Voreinstellungen konfigurieren |
| `config` | Konfiguration verschluesseln/pruefen |
| `report` | Backup-Bericht erstellen |
| `completion` | Shell-Autovervollstaendigungsskript erzeugen |
| `wizard` | Interaktiver Konfigurationsassistent |
| `status` | Backup-Status-Dashboard |
| `version` | Versionsinformationen anzeigen |
| `help` | Hilfe anzeigen |

#### Globale Parameter

| Parameter | Beschreibung |
|-----------|--------------|
| `--lang zh_CN` / `en_US` / `fr_FR` / `es_ES` / `ru_RU` / `de_DE` / `ja_JP` / `pt_BR` / `ko_KR` | Oberflaechensprache festlegen (wird in config.json gespeichert) |
| `--format zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z` | Packformat festlegen (wird in config.json gespeichert) |
| `--debug` | Debug-Protokollierung aktivieren |

#### Backup-Strategie hinzufuegen

```bash
uv run python main.py add <source> <dest> [-i ignore_patterns]
```

Parameter:
- **source**: Pfad des zu sichernden Quellordners
- **dest**: Pfad fuer die Ablage der Backup-Dateien
- **-i, --ignore**: Zu ignorierende Datei- oder Ordnernamen, kommagetrennt (Standard: `.git,__pycache__`)
- **--format**: Packformat pro Eintrag (gilt nur fuer diese Strategie, Standardwert wird verwendet, wenn nicht angegeben): `zip` / `tar` / `tar.gz` / `tar.bz2` / `tar.xz` / `tar.zst` / `7z`

Beispiele:
```bash
# Strategie mit globalem Standardformat hinzufuegen
uv run python main.py add F:/my_folder F:/backup -i node_modules,.git

# Tar.gz-Format fuer diese Strategie festlegen (jedes Backup dieses Ordners verwendet tar.gz)
uv run python main.py add F:/my_folder F:/backup --format tar.gz

# 7z-Format festlegen (nur fuer diesen Ordner)
uv run python main.py add F:/my_folder F:/backup --format 7z
```

#### Backup-Strategie loeschen

```bash
uv run python main.py rm <path>
```

Parameter:
- **path**: Pfad des Quellordners, dessen Backup-Strategie geloescht werden soll

Beispiel:
```bash
uv run python main.py rm F:/my_folder
```

#### Alle Backup-Strategien anzeigen

```bash
uv run python main.py all
```

Zeigt alle aktuell konfigurierten Backup-Strategien an.

#### Backup ausfuehren

```bash
# Mit Standardformat (ZIP)
uv run python main.py save

# Mit tar.gz-Format
uv run python main.py --format tar.gz save

# Die letzten 5 Backup-Dateien aufbewahren, alte automatisch bereinigen
uv run python main.py save --keep 5

# Mit 7z-Format und Verschluesselung
uv run python main.py --format 7z save --password mysecret

# Englische Oberflaeche + tar.xz-Format
uv run python main.py --lang en_US --format tar.xz save
```

**Parameter fuer den Befehl save:**

| Parameter | Standardwert | Beschreibung |
|-----------|-------------|--------------|
| `--keep N` | `0` | Die letzten N Backup-Dateien aufbewahren, 0 bedeutet keine Bereinigung |
| `--password PASSWORT` | `""` | Verschluesselungspasswort (nur fuer 7z-Format) |
| `--sftp` | `false` | Nach dem Backup auf SFTP-Server hochladen |
| `--webdav` | `false` | Nach dem Backup auf WebDAV-Server hochladen |

Gemaess der Backup-Strategie werden geaenderte Ordner automatisch gesichert.

#### Zeitgesteuertes Backup

```bash
# Alle 60 Minuten ein Backup ausfuehren
uv run python main.py watch --interval 60

# Alle 2 Stunden mit Aufbewahrung der letzten 10 Dateien
uv run python main.py watch --interval 120 --keep 10

# Zeitgesteuertes Backup + 7z-Verschluesselung
uv run python main.py --format 7z watch --interval 60 --password mysecret
```

**Parameter fuer den Befehl watch:**

| Parameter | Standardwert | Beschreibung |
|-----------|-------------|--------------|
| `--interval MINUTEN` | `60` | Backup-Intervall in Minuten |
| `--keep N` | `0` | Die letzten N Backup-Dateien aufbewahren |
| `--password PASSWORT` | `""` | Verschluesselungspasswort (nur fuer 7z-Format) |
| `--sftp` | `false` | Nach jedem Backup auf SFTP-Server hochladen |
| `--webdav` | `false` | Nach jedem Backup auf WebDAV-Server hochladen |

Mit `Ctrl+C` wird das zeitgesteuerte Backup gestoppt.

#### Backup wiederherstellen

```bash
uv run python main.py restore <backup_file> <target_dir>
```

Parameter:
- **backup_file**: Pfad zur Backup-Datei (unterstuetzt .zip / .tar / .tar.gz / .tar.bz2 / .tar.xz / .tar.zst / .7z)
- **target_dir**: Zielverzeichnis fuer die Wiederherstellung

Beispiele:
```bash
uv run python main.py restore F:/backup/my_folder.tar.gz F:/restored
uv run python main.py restore F:/backup/my_folder.7z F:/restored
uv run python main.py restore F:/backup/my_folder.tar.zst F:/restored
```

#### SFTP-Remote-Backup

```bash
# ============ Schnellstart (empfohlen) ============
# 1. SFTP konfigurieren (automatische SSH-Schluessel-Erkennung, keine manuelle Angabe noetig)
sbackup sftp config --host 192.168.1.100 --user admin --remote-path /backups

# 2. Verbindung testen
sbackup sftp test

# 3. Backup ausfuehren und hochladen
sbackup save --sftp

# ============ Authentifizierungsmethoden ============

# Methode 1: Automatische Schluessel-Erkennung (empfohlen)
# Das System versucht automatisch ~/.ssh/id_ed25519 -> id_rsa -> id_ecdsa
sbackup sftp config --host 192.168.1.100 --user admin

# Methode 2: Passwort-Authentifizierung
sbackup sftp config --host 192.168.1.100 --user admin --password secret

# Methode 3: Bestimmten Schluessel angeben
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Methode 4: Schluessel + Passphrase (interaktive Eingabe)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa

# Methode 5: Schluessel + Passphrase (Kommandozeile)
sbackup sftp config --host 192.168.1.100 --user admin --key-file ~/.ssh/id_rsa --key-passphrase mykeypass

# ============ Anwendungsszenarien ============

# Szenario 1: Einmaliges Backup mit Hochladen
sbackup save --sftp

# Szenario 2: Zeitgesteuertes Backup mit automatischem Hochladen (alle 60 Minuten)
sbackup watch --interval 60 --sftp

# Szenario 3: Bestimmtes Format + Hochladen
sbackup --format tar.gz save --sftp

# Szenario 4: Verschluesseltes Backup + Hochladen
sbackup --format 7z save --password mysecret --sftp

# Szenario 5: Aufbewahrung der letzten 5 Backups + Hochladen
sbackup save --keep 5 --sftp

# ============ Erweiterte Verwendung ============

# Interaktive Konfiguration (alle Parameter schrittweise eingeben)
sbackup sftp config

# Nicht-interaktive Konfiguration (alle Parameter in der Kommandozeile)
sbackup sftp config --host 192.168.1.100 --port 22 --user admin --password secret --remote-path /backups

# Verbindung testen mit detailliertem Protokoll
sbackup --debug sftp test
```

**sftp-Unterbefehle:**

| Unterbefehl | Beschreibung | Beispiel |
|-------------|--------------|----------|
| `sftp config` | SFTP-Verbindungsparameter konfigurieren (host/port/user/password/key_file/key_passphrase/remote_path) | `sbackup sftp config --host 192.168.1.100 --user admin` |
| `sftp test` | SFTP-Verbindung testen | `sbackup sftp test` |

**Authentifizierungsmethoden:**

| Methode | Parameter | Beschreibung | Beispiel |
|---------|-----------|--------------|----------|
| **Automatische Erkennung** | Keine Authentifizierungsparameter angeben | Versucht automatisch `~/.ssh/id_ed25519` -> `id_rsa` -> `id_ecdsa` (empfohlen) | `sbackup sftp config --host ... --user ...` |
| Passwort | `--password` | Direkt mit Passwort anmelden | `sbackup sftp config --host ... --user ... --password secret` |
| Schluessel | `--key-file` | Mit angegebenem SSH-Schluessel anmelden | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa` |
| Schluessel + Passphrase | `--key-file` + `--key-passphrase` | Wenn der Schluessel eine Passphrase hat | `sbackup sftp config --host ... --user ... --key-file ~/.ssh/id_rsa --key-passphrase mypass` |

Unterstuetzte Schluesselformate: RSA, Ed25519, ECDSA.

**Plattformuebergreifende Pfadunterstuetzung:**

| Plattform | Beispiel Schluesselpfad | Beschreibung |
|-----------|------------------------|--------------|
| Linux/macOS | `~/.ssh/id_rsa` | Wird automatisch zu `/home/user/.ssh/id_rsa` aufgeloest |
| Windows | `~/.ssh/id_rsa` | Wird automatisch zu `C:\Users\username\.ssh\id_rsa` aufgeloest |
| Alle Plattformen | Absoluter Pfad | Vollstaendiger Pfad wird direkt verwendet |

Die SFTP-Konfiguration wird im Feld `sftp` der Datei `config.json` gespeichert und unterstuetzt Kommandozeilenparameter oder interaktive Eingabe.

#### Versionsinformationen anzeigen

```bash
sbackup version
```

## Konfigurationsdatei

Sbackup unterstuetzt benutzerdefinierte Konfiguration ueber die Datei `config.json`. Die Konfigurationsdatei liegt im Projektstammverzeichnis.

### Konfigurationsparameter

```json
{
  "compression_format": "ZIP",
  "compression": {
    "algorithm": "ZIP_DEFLATED",
    "level": 6
  },
  "skip_patterns": [".git", "__pycache__"],
  "data_file": "sbackup.json",
  "lang": "zh_CN",
  "password": "",
  "sftp": {
    "host": "",
    "port": 22,
    "user": "",
    "password": "",
    "key_file": "",
    "key_passphrase": "",
    "remote_path": "/",
    "enabled": false
  }
}
```

| Parameter | Typ | Standardwert | Beschreibung |
|-----------|-----|-------------|--------------|
| `compression_format` | string | `"ZIP"` | Packformat, Auswahl: `ZIP`, `TAR`, `TAR_GZ`, `TAR_BZ2`, `TAR_XZ`, `TAR_ZST`, `7Z` |
| `compression.algorithm` | string | `"ZIP_DEFLATED"` | ZIP-Komprimierungsalgorithmus, Auswahl: `ZIP_DEFLATED`, `ZIP_STORED`, `ZIP_BZIP2`, `ZIP_LZMA` |
| `compression.level` | int | `6` | Komprimierungsstufe, Bereich 0-9 (0 = keine Komprimierung, 9 = hoechste Komprimierung) |
| `skip_patterns` | list | `[".git", "__pycache__"]` | Zu ignorierende Datei-/Ordnermuster (unterstuetzt fnmatch-Platzhalter und Pfadabgleich) |
| `data_file` | string | Plattform-Standardpfad | Pfad zur Datei mit den Backup-Strategien |
| `lang` | string | `"zh_CN"` | Oberflaechensprache, Auswahl: `zh_CN`, `en_US`, `fr_FR`, `es_ES`, `ru_RU`, `de_DE`, `ja_JP`, `pt_BR`, `ko_KR` |
| `password` | string | `""` | Verschluesselungspasswort fuer 7z |
| `sftp.host` | string | `""` | SFTP-Serveradresse |
| `sftp.port` | int | `22` | SFTP-Port |
| `sftp.user` | string | `""` | SFTP-Benutzername |
| `sftp.password` | string | `""` | SFTP-Passwort (fuer Passwort-Authentifizierung) |
| `sftp.key_file` | string | `""` | Pfad zur SSH-Schluesseldatei (fuer Schluessel-Authentifizierung, empfohlen) |
| `sftp.key_passphrase` | string | `""` | Schluessel-Passphrase (falls vorhanden) |
| `sftp.remote_path` | string | `"/"` | Remote-Zielpfad |
| `sftp.enabled` | bool | `false` | SFTP aktivieren oder nicht |

### Konfigurationsbeispiel

Backup mit dem tar.bz2-Format und hoher Komprimierung:

```json
{
  "compression_format": "TAR_BZ2",
  "compression_level": 9,
  "skip_patterns": [".git", "__pycache__", "node_modules", "*.log"],
  "data_file": "backup_strategies.json",
  "lang": "de_DE"
}
```

### Vergleich der Packformate

| Format | Dateiendung | Komprimierung | Geschwindigkeit | Abhaengigkeit | Anwendungsfall |
|--------|-------------|---------------|-----------------|---------------|----------------|
| ZIP | .zip | Mittel | Schnell | Standardbibliothek | Universell, beste Windows-Kompatibilitaet |
| tar | .tar | Keine | Sehr schnell | Standardbibliothek | Reines Archiv, fuer externe Komprimierung |
| tar.gz | .tar.gz | Mittel | Schnell | Standardbibliothek | Linux/macOS Standard |
| tar.bz2 | .tar.bz2 | Hoch | Mittel | Standardbibliothek | Hochkomprimierte Archive |
| tar.xz | .tar.xz | Am hoechsten | Langsam | Standardbibliothek | Langzeitarchivierung, platzsparend |
| tar.zst | .tar.zst | Mittel-hoch | Sehr schnell | zstandard | Modern, gute Balance zwischen Geschwindigkeit und Kompression |
| 7z | .7z | Sehr hoch | Langsam | py7zr | Hoechste Kompression, unterstuetzt Verschluesselung |

#### WebDAV-Remote-Backup

WebDAV ist ein HTTP-basiertes Dateiprotokoll, das Jianguoyun, NextCloud, Synology und andere gaengige Cloud-Speicher unterstuetzt. Verwendet die Python-Standardbibliothek `urllib` -- **keine zusaetzlichen Abhaengigkeiten**.

```bash
# ============ Schnellstart ============
# 1. WebDAV konfigurieren
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --password secret

# 2. Verbindung testen
sbackup webdav test

# 3. Backup ausfuehren und hochladen
sbackup save --webdav

# ============ Anwendungsszenarien ============

# Szenario 1: Einmaliges Backup mit Hochladen
sbackup save --webdav

# Szenario 2: Zeitgesteuertes Backup mit automatischem Hochladen (alle 60 Minuten)
sbackup watch --interval 60 --webdav

# Szenario 3: Remote-Unterverzeichnis angeben
sbackup webdav config --url https://dav.jianguoyun.com/dav/ --user user@example.com --remote-path /backups/sbackup

# Szenario 4: Simultanes Hochladen auf SFTP und WebDAV
sbackup save --sftp --webdav

# ============ Gaengige WebDAV-Adressen ============
# Jianguoyun: https://dav.jianguoyun.com/dav/
# NextCloud: https://your-server/remote.php/dav/files/username/
# Synology: https://your-synology:5006/webdav/
```

**webdav-Unterbefehle:**

| Unterbefehl | Beschreibung | Beispiel |
|-------------|--------------|----------|
| `webdav config` | WebDAV-Verbindungsparameter konfigurieren (url/user/password/remote_path) | `sbackup webdav config --url ... --user ...` |
| `webdav test` | WebDAV-Verbindung testen | `sbackup webdav test` |

| Parameter | Standardwert | Beschreibung |
|-----------|-------------|--------------|
| `--url URL` | `""` | WebDAV-Serveradresse (z.B. `https://dav.jianguoyun.com/dav/`) |
| `--user BENUTZER` | `""` | WebDAV-Benutzername (in der Regel E-Mail-Adresse) |
| `--password PASSWORT` | `""` | WebDAV-Passwort (fuer Jianguoyun muss in den Einstellungen ein App-Passwort generiert werden) |
| `--remote-path PFAD` | `/` | Remote-Zielpfad |

## Funktionsweise

Sbackup realisiert die Backup-Funktionalitaet auf folgende Weise:

1. **Backup-Strategie-Speicherung**: Backup-Strategien werden in einer JSON-Datei gespeichert, die Ordnerpfade, letzte Aenderungszeiten, Zielpfade, Ignoriermuster und packformat pro Eintrag enthaelt.
2. **Inkrementelles Backup**: Durch Vergleich des letzten Aenderungszeitpunkts eines Ordners werden nur geaenderte Ordner gesichert.
3. **Multiformat-Komprimierung**: Verwendet Pythons eingebaute `zipfile`- und `tarfile`-Module sowie die Drittanbieter-Bibliotheken `zstandard` und `py7zr` fuer sieben Packformate.
4. **Format pro Eintrag**: Jede Backup-Strategie kann ein eigenes Packformat angeben (`add --format`), das Vorrang vor dem globalen `--format` hat. Ohne Angabe wird der globale Standard verwendet.
5. **Backup-Bereinigung**: Nach erfolgreichem Backup wird das Zielverzeichnis automatisch gescannt, nach Aenderungszeitpunkt sortiert und alte Dateien werden ueber die Aufbewahrungsanzahl hinaus geloescht.
6. **Verschluesseltes Backup**: Das 7z-Format unterstuetzt LZMA2-Verschluesselung ueber den `--password`-Parameter oder die `config.json`-Konfiguration.
7. **Zeitgesteuertes Backup**: Der `watch`-Befehl fuehrt in einer Schleife in angegebenen Intervallen Backups aus. `Ctrl+C` beendet sicher.
8. **Backup-Verlauf**: Nach jedem Backup werden Zeitstempel, Dateigroesse und Dateianzahl protokolliert. Es werden die letzten 100 Eintraege aufbewahrt.
9. **SFTP-Remote-Backup**: Basierend auf der paramiko-Bibliothek als SFTP-Client, unterstuetzt Verbindungstests, automatische Erstellung von Remote-Verzeichnissen und Datei-Upload mit Fortschrittsanzeige.

### Datenformat der Datei

```json
{
  "/path/to/source/folder": [
    1719235200.0,
    "/path/to/target/folder",
    [".git", "__pycache__"],
    ""
  ],
  "/path/to/another/folder": [
    1719235200.0,
    "/path/to/another/target",
    [".git"],
    "TAR_GZ"
  ],
  "_history": [
    {
      "time": "2026-05-01T12:00:00",
      "source": "/path/to/source/folder",
      "size_mb": 12.5,
      "files_count": 150
    }
  ]
}
```

Jeder Backup-Strategie-Eintrag ist eine 4-Element-Liste: `[mtime, target, skip_patterns, compression_format]`

| Feld | Beschreibung |
|------|--------------|
| `mtime` | Letzter Aenderungszeitpunkt des Quellordners (fuer inkrementelle Backup-Entscheidung) |
| `target` | Zielpfad fuer die Backup-Dateien |
| `skip_patterns` | Liste der zu ignorierenden Datei-/Ordnermuster |
| `compression_format` | Packformat pro Eintrag (leerer String bedeutet globaler Standard) |

## Entwicklerhandbuch

### Tests ausfuehren

```bash
uv run coverage run -m unittest discover -s tests -t . && uv run coverage report -m
```

### Code-Struktur

```
sbackup/
├── main.py              # Programmeinstieg
├── sbackup/
│   ├── __init__.py      # Export der Kernfunktionen
│   ├── __main__.py      # python -m sbackup Einstieg
│   ├── cli.py           # CLI-Argument-Parser und Befehlsverteilung (30+ Befehle)
│   ├── config.py        # Konfigurationslade, Verschluesselung, Webhook-/SMTP-Konfiguration
│   ├── auto_save.py     # BackupManager Kern-Engine
│   ├── compression.py   # Komprimierung/Dekomprimierung fuer 7 Formate
│   ├── i18n.py          # Internationalisierung (9 Sprachen)
│   ├── sftp.py          # SFTP-Remote-Backup-Client (paramiko)
│   ├── webdav.py        # WebDAV-Remote-Backup-Client (ohne Abhaengigkeiten)
│   ├── cloud_storage.py # S3-Cloud-Speicher-Client (minio)
│   ├── multi_dest.py    # Parallel-Backup auf mehrere Ziele
│   ├── handlers.py      # SFTP-/WebDAV-/Remote-/Schedule-Befehlsverarbeitung
│   ├── hooks.py         # Pre-/Post-Hook-Ausfuehrung
│   ├── audit.py         # Audit-Protokollsystem
│   ├── profile.py       # Konfigurationsprofil-Verwaltung
│   ├── selective.py     # Selektive Wiederherstellung
│   ├── cross_search.py  | Suche ueber Archive hinweg
│   ├── integrity.py     # SHA256-Pruefsumme
│   ├── rotation.py      # Backup-Rotationsstrategie
│   ├── dryrun.py        # Dry-run-Vorschau
│   ├── diskcheck.py     # Speicherplatz-Schaetzung
│   ├── task_queue.py    # Aufgabenwarteschlangensystem
│   ├── schema.py        # Konfigurationsvalidierer
│   ├── benchmark.py     # Komprimierungs-Benchmark
│   ├── chunked_backup.py# Blockweise inkrementelle Sicherung
│   ├── dedup.py         # Dateiweise SHA256-Deduplizierung
│   ├── export.py        # Metadaten-Export (CSV/JSON)
│   ├── monitor.py       # watchdog Dateisystemueberwachung
│   ├── lock.py          # Plattformuebergreifende Prozesssperre
│   ├── retry.py         | Exponentielle Wiederholung mit Backoff
│   ├── ratelimiter.py   # Token-Bucket-Ratenbegrenzung
│   ├── keychain.py      # System-Keychain-Integration
│   ├── parity.py        # Reed-Solomon-Fehlerkorrektur
│   ├── completion.py    # Shell-Autovervollstaendigung
│   ├── wizard.py        # Interaktiver Konfigurationsassistent
│   └── locales/         # Uebersetzungsdateien fuer 9 Sprachen
└── tests/
    └── sbackup/
        └── test_*.py    # 30 Testdateien, alle Module abdeckend
```

### Neue Funktionen hinzufuegen

1. Erstellen Sie eine neue Moduldatei im `sbackup/`-Verzeichnis
2. Importieren Sie die neuen Funktionen in `sbackup/__init__.py`
3. Fuegen Sie die Verarbeitungslogik fuer den neuen Befehl in der `run()`-Funktion hinzu
4. Erstellen Sie die entsprechende Testdatei im `tests/`-Verzeichnis

## Haeufig gestellte Fragen

### Q: Was passiert, wenn die Backup-Strategie-Datei versehentlich geloescht wird?

A: Die Backup-Strategien werden in der Datendatei gespeichert. Bei versehentlicher Loeschung koennen die Strategien mit dem `add`-Befehl erneut hinzugefuegt werden.

### Q: Wie kann eine vorhandene Backup-Strategie geaendert werden?

A: Verwenden Sie den Befehl `sbackup edit`: `sbackup edit <source> --dest <new_dest> --ignore <patterns> --format <fmt>`.

### Q: Werden Remote-Backups unterstuetzt?

A: Ja! Es werden drei Remote-Backup-Methoden angeboten:
- **SFTP**: `sbackup sftp config` konfigurieren, `sbackup save --sftp` hochladen
- **WebDAV**: `sbackup webdav config` konfigurieren, `sbackup save --webdav` hochladen (unterstuetzt Jianguoyun/NextCloud/Synology)
- **S3-Cloud-Speicher**: Das Feld `cloud` in `config.json` konfigurieren, `sbackup save --cloud` hochladen
- Mehrere Methoden gleichzeitig: `sbackup save --sftp --webdav --cloud`

### Q: Was ist der Unterschied zwischen tar.gz und ZIP?

A: tar.gz wird auf Linux/macOS haeufiger verwendet und bietet eine etwas bessere Kompression. ZIP ist auf Windows gaengiger und hat die beste Kompatibilitaet. tar.bz2 und tar.xz bieten hoehere Kompression, sind aber langsamer. tar.zst ist ein moderner Algorithmus mit sehr hoher Geschwindigkeit und guter Kompression. 7z bietet die hoechste Kompression und unterstuetzt Verschluesselung.

### Q: Wie werden Backups verschluesselt?

A: Verwenden Sie das 7z-Format mit Passwort: `uv run python main.py --format 7z save --password yourpassword`. Das Passwort kann auch im Feld `password` der `config.json` hinterlegt werden.

### Q: Wie werden alte Backups automatisch bereinigt?

A: Verwenden Sie den Parameter `--keep`: `uv run python main.py save --keep 5` bewahrt nur die letzten 5 Backup-Dateien auf. Bei zeitgesteuerten Backups ebenfalls unterstuetzt: `uv run python main.py watch --interval 60 --keep 10`.

### Q: Wie richtet man zeitgesteuerte Backups ein?

A: Verwenden Sie den Befehl `watch`: `uv run python main.py watch --interval 60` fuehrt alle 60 Minuten ein Backup aus. Mit `Ctrl+C` wird gestoppt.

### Q: Ist die Passwortspeicherung sicher?

A: Die SFTP-Passwoerter und 7z-Verschluesselungspasswoerter in `config.json` werden im **Klartext** gespeichert. Stellen Sie sicher, dass der Zugriff auf die Datei `config.json` auf vertrauenswuerdige Benutzer beschraenkt ist (z.B. `chmod 600 config.json`). Fuegen Sie eine `config.json` mit Passwoertern nicht in ein Versionskontrollsystem ein.

## Mitwirkungsrichtlinie

Issues und Pull Requests sind willkommen!

1. Forken Sie dieses Repository
2. Erstellen Sie Ihren Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committen Sie Ihre Aenderungen (`git commit -m 'Add some AmazingFeature'`)
4. Pushen Sie auf den Branch (`git push origin feature/AmazingFeature`)
5. Erstellen Sie einen Pull Request

### Codestil

Dieses Projekt folgt PEP 8 und dem Google Python Style Guide. Bitte stellen Sie sicher, dass Ihr Code:
- Typannotationen verwendet
- Google-stile Docstrings einhaelt
- Alle Tests besteht

## Lizenz

Dieses Projekt steht unter der GNU GPL v3.0-Lizenz. Einzelheiten finden Sie in der Datei [LICENSE](../../LICENSE).

## Autor

**xiatianxuan** (CodeSeed)

- [Gitee](https://gitee.com/xiatianxuan)
- [Webseite](https://xnors-codeseed.pages.dev/)

## Besonderer Dank

- [Xnors Studio](https://xnors.github.io/)

## Kontakt

Bei Fragen oder Anregungen senden Sie bitte eine E-Mail an: xiatianxuan2025@163.com

---

*Letzte Aktualisierung: 19. Juni 2026*

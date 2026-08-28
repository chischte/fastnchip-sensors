# fastnchip-sensors

Messsystem fuer eine Klimakammer auf dem Arduino Portenta Machine Control:

- SCD41 fuer CO2 und relative Feuchte
- PT100 Kanal 1 fuer die Innentemperatur
- PT100 Kanal 0 fuer die Aussentemperatur
- lokale Webseite und QSPI-Rueckpuffer
- Python-Logger mit SQLite, CSV-Export, Viewer und Backup

## Installation

1. `include/wifi-credentials.example.h` nach
   `../wifi-credentials.h` kopieren und dort `WIFI_SSID` und
   `WIFI_PASSWORD` eintragen. Die echte Datei liegt damit ausserhalb des
   Repositorys.
2. Sensorparameter und Kanalbelegung in include/config.h kontrollieren.
3. Firmware bauen: pio run
4. Erstinstallation per USB/DFU: pio run -t upload
5. Python-Pakete: python -m pip install -r logger/requirements.txt

## Betrieb

Logger: python logger/logger.py

Andere IP: python logger/logger.py --url http://192.168.31.168

Eine vorhandene measurements.csv wird einmalig nach measurements.db importiert.
Danach wird der QSPI-Puffer nachgeholt und anhand von boot_id plus sequence
duplikatfrei gespeichert.

## Firmware-Struktur

Die Firmware ist entlang ihrer Verantwortlichkeiten unterteilt:

- `SensorManager`: SCD41- und RTD-Hardwarezugriff
- `MeasurementController`: Messtakt, Verlauf und Datenfluss
- `QspiStorage`: persistenter Messpuffer und Partitionen
- `FirmwareUpdater`: OTA-Datei, Pruefung und Aktivierung
- `WebServer`: WLAN, HTTP-API und UI-Auslieferung
- `Application`: explizite Verdrahtung und Ablaufsteuerung

Sensorinitialisierung, HTTP-Empfang, OTA-Upload und Backlog-Auslieferung werden
schrittweise im Hauptloop verarbeitet. Nur notwendige Start-/Reset-Wartezeiten
sind blockierend.

Viewer: python logger/viewer.py

CSV fuer Excel: python logger/logger.py --export-csv

## Datenqualitaet

Sensorfehler werden als SQL NULL plus Validitaetsflag und RTD-Fehlercode
gespeichert. Geraete-Uptime und Sequenznummer machen Neustarts und Luecken sichtbar.

Der SCD41-ASC ist standardmaessig deaktiviert, da eine geschlossene Kammer nicht
regelmaessig 400-ppm-Frischluft sieht. Hoehenwert und Temperaturoffset in config.h
muessen am Einbauort kalibriert werden. Betrieb nur ohne Kondensation.

## Persistenz und Backup

Der Portenta schreibt NDJSON auf QSPI und rotiert bei 4 MiB. SQLite ist die
fuehrende Langzeitspeicherung. backup.py sichert eine laufende Datenbank konsistent.

## OTA und Tests

pio run erzeugt firmware.ota. upload_firmware.ps1 akzeptiert kein rohes BIN.

Tests: python -m unittest discover -s test -p "test_*.py"

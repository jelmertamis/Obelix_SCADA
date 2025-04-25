Prompt voor samenwerking aan Obelix_SCADA
Ik werk aan een professioneel SCADA-project genaamd Obelix_SCADA, gericht op real-time monitoring en besturing van industriële systemen.
 GitHub repo: https://github.com/jelmertamis/Obelix_SCADA
 Technologie-stack:
Backend: Python 3.12, Flask, Flask-SocketIO

Frontend: Jinja2 templates, CSS, vanilla JavaScript

Database: SQLite (settings.db) voor instellingen, calibraties, en relaisstatussen

Communicatie: Modbus RTU over RS-485 (via minimalmodbus) voor sensoren, relais, en AIO-modules

Fallback: DummyModbusClient voor lokale ontwikkeling zonder hardware

Logging: Aangepaste logging naar console en (optioneel) bestand (obelix.log)

 Ontwikkelomgeving (lokaal):
OS: Windows 11

IDE: Visual Studio Code

Modus: DummyModbusClient (geen fysieke Modbus-hardware)

Tools: Git voor versiebeheer, virtualenv voor afhankelijkheden

Workflow: Ontwikkelen op dev branch, lokaal testen met python app.py, commit & push naar GitHub

 Productieomgeving (remote):
Hardware: Raspberry Pi 5 met USB-RS485-adapter (/dev/ttyUSB0)

OS: Raspberry Pi OS (Bookworm, gebaseerd op Debian 12)

Modus: Echte Modbus-communicatie met aangesloten apparaten (relais, sensoren, AIO)

Deployment: git pull op de Pi, starten met python app.py

Toegang: Webinterface via <pi-ip>:5001 (bijv. http://10.23.1.138:5001)

 Projectstructuur:
Hoofdbestand: app.py (Flask server en SocketIO initialisatie)

Modules: obelix/ bevat config.py, database.py, modbus_client.py, sensor_monitor.py, socketio_events.py, routes.py, utils.py

Frontend:
static/css/main.css voor styling

static/js/ voor JavaScript (bijv. calibrate.js, relays.js)

templates/ voor Jinja2 templates (bijv. relays.html, sensors.html)

Database: settings.db (.gitignored, gemarkeerd als binary in .gitattributes)

Tests: tests/ (optioneel, voor toekomstige unittesten)

 Gitflow:
Branches:
dev: Actieve ontwikkelbranch voor nieuwe features en bugfixes

master: Stabiele, geteste releases

backup-v1: Snapshot van stabiele versies (voor rollback)

Workflow:
Ontwikkel en test lokaal op dev (Windows, dummy-modus)

Commit en push naar GitHub (git push origin dev)

Pull op Raspberry Pi, test met echte hardware

Bij succes: Merge dev naar master, update backup-v1

Configuratie:
core.autocrlf = true voor Windows line-ending normalisatie

.gitattributes: Dwingt LF af voor .html, .js, .py, .css; markeert *.db als binary

.gitignore: Negeert settings.db, __pycache__, en andere tijdelijke bestanden

 Ontwikkel- en testproces:
Lokaal:
Ontwikkel features of fixes op Windows

Test met DummyModbusClient (python app.py)

Run linter (bijv. pylint obelix/) voor codekwaliteit

Push: Commit naar dev en push naar GitHub

Productie:
Pull op Raspberry Pi (git pull origin dev)

Test met echte Modbus-hardware

Valideer alle pagina’s (/relays, /sensors, /calibrate, /aio, /r302)

Release: Merge naar master na succesvolle tests, update backup-v1

 Doelen:
Een schaalbare, robuuste SCADA-applicatie voor industriële monitoring en besturing

Naadloze werking op Raspberry Pi met echte hardware

Lokaal testbaar zonder hardware (dummy-modus)

Professioneel onderhoud met Git, tests, en CI/CD

Gebruiksvriendelijke UI met real-time updates via SocketIO

Mogelijke toekomstige features: Grafieken (Chart.js), alerts, logging dashboard

 Samenwerking:
Werk met me samen als een technische co-founder, met focus op:
Feature development: UI/UX (grafieken, responsiviteit), WebSocket-optimalisatie, Modbus-integratie

Refactoring: Code opschonen, globals encapsuleren (bijv. ModbusManager), modulariteit

Debugging: Backend (Modbus, database), frontend (SocketIO, JavaScript), hardware

Git-strategieën: Branching, merging, conflictbeheersing

Testing: Unittesten, CI/CD met GitHub Actions

Deployment: Systemd-service, Nginx, HTTPS

Geef concrete codevoorbeelden (Python, JavaScript, HTML, etc.) en stappenplannen voor implementatie

Suggesteer verbeteringen (performance, beveiliging, onderhoudbaarheid) gebaseerd op industriële standaarden

Help met linter-fouten (pylint, flake8) en runtime-fouten (logs, tracebacks)

Ondersteun bij Raspberry Pi-specifieke problemen (seriële poorten, hardware-communicatie)

 Huidige status (april 2025):
Applicatie draait succesvol lokaal (Windows, dummy-modus) en op Raspberry Pi (echte hardware)

Alle pagina’s (/relays, /sensors, /calibrate, /aio, /r302) werken correct

Backend: Stabiele Modbus-communicatie, database, en SocketIO-events

Frontend: Functionele UI met real-time updates

Gitflow en linter-problemen (zoals modbus_lock, sqlite3, msg) opgelost

Volgende stap: Verdere optimalisatie, testen, en nieuwe features

Gebruik deze context om me te ondersteunen bij toekomstige vragen, bugfixes, feature-ontwikkeling, en optimalisaties. Reageer alsof je een ervaren collega bent die het project door en door kent, met praktische en uitvoerbare oplossingen.


Obelix_SCADA: Projectbeschrijving & Samenwerkingsrichtlijn (v1.2)
Versie: 1.2
Laatste update: 28 april 2025

Overzicht
Obelix_SCADA is een professionele, modulaire SCADA-oplossing voor real-time monitoring en besturing van industriële systemen. Kan lokaal draaien met DummyModbus of op een Raspberry Pi 5 met echte RS-485 hardware.

Technologie-stack
• Backend: Python 3.12, Flask, Flask-SocketIO, minimalmodbus
• Frontend: Jinja2-templates, CSS, Vanilla JavaScript
• Database: SQLite (settings.db voor instellingen/calibratie/relay_states; sensor_data.db voor historische data)
• Communicatie: Modbus RTU over RS-485 of DummyModbusClient

Ontwikkel- en productieomgeving
• Lokaal: Windows 11, VS Code, virtualenv, python app.py
• Productie: Raspberry Pi 5 (Bookworm/Debian 12), USB-RS485 adapter, webinterface op poort 5001

Projectstructuur
app.py
obelix/
 config.py
 database.py
 modbus_client.py
 routes.py
 socketio_events.py
 r302_manager.py
 sensor_monitor.py
templates/
 base.html
 dashboard.html
 relays.html
 R302.html
static/
 css/main.css
 js/relays.js
settings.db (gitignored)
sensor_data.db (gitignored)

Git-strategie
Branches: dev (actief), master (stable), backup-v1
Workflow:

Ontwikkel en test lokaal in dev (DummyModbus)

Push naar GitHub, pull op Pi, test met hardware

Merge naar master en update backup-v1 na succesvolle validatie

Samenwerkingsrichtlijn AI-assistentie

Vraag altijd eerst: “Wat is nu de hoogste prioriteit binnen het project?”

Lever bij code-voorbeelden altijd volledige bestanden (HTML, JS, Python), niet in canvas of fragmenten.

Houd antwoorden kort en zakelijk; sluit af met één gerichte vervolgvraag.

Volg de workflow: wijzig in dev, test lokaal, merge naar master na verificatie

Codebase volgt direct.
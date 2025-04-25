# Obelix_SCADA: Projectbeschrijving & Samenwerkingsrichtlijn

**Versie:** 1.0  
**Laatste update:** 25 april 2025

## Overzicht

**Obelix_SCADA** is een professioneel SCADA-project gericht op real-time monitoring en besturing van industriële systemen.

- **GitHub-repository:** https://github.com/jelmertamis/Obelix_SCADA  
- **Doel:** Een schaalbare, robuuste SCADA-oplossing voor Raspberry Pi, met volledige ondersteuning voor lokale ontwikkeling zonder fysieke hardware.

---

## Technologie-stack

### Backend
- Python 3.12
- Flask + Flask-SocketIO
- Logging (console + optioneel bestand)

### Frontend
- Jinja2 templates
- CSS
- Vanilla JavaScript

### Database
- SQLite (`settings.db`) voor instellingen, calibraties, relaisstatussen

### Communicatie
- Modbus RTU over RS-485 (via `minimalmodbus`)
- Fallback: `DummyModbusClient` voor lokale simulatie

---

## Ontwikkelomgeving (lokaal)

- **OS:** Windows 11  
- **IDE:** Visual Studio Code  
- **Modus:** DummyModbusClient  
- **Tools:** Git, `virtualenv`  
- **Workflow:** 
  - Lokaal testen via `python app.py`
  - Committen op `dev` branch
  - Push naar GitHub

---

## Productieomgeving (remote)

- **Hardware:** Raspberry Pi 5 + USB-RS485 adapter (`/dev/ttyUSB0`)  
- **OS:** Raspberry Pi OS (Bookworm/Debian 12)  
- **Modus:** Echte Modbus-communicatie met aangesloten apparaten  
- **Toegang:** Webinterface via `<pi-ip>:5001`

---

## Projectstructuur

- `app.py`: Main Flask-app met SocketIO
- `obelix/`: Bevat modules zoals `config.py`, `modbus_client.py`, `routes.py`, enz.
- `templates/`: Jinja2-pagina’s (zoals `relays.html`)
- `static/`: CSS en JavaScript
- `settings.db`: SQLite (uitgesloten via `.gitignore`)
- `tests/`: Voor toekomstige unit tests

---

## Gitstrategie

### Branches
- `dev`: Actieve ontwikkelbranch
- `master`: Stabiele, geteste releases
- `backup-v1`: Snapshot van werkende versie

### Workflow
1. Lokale ontwikkeling op Windows met DummyModbusClient
2. Push naar `dev`
3. Pull op Raspberry Pi
4. Test met fysieke hardware
5. Succesvol? Merge naar `master` + update `backup-v1`

---

## Configuratiebeheer

- `.gitignore`: Negeert `settings.db`, `__pycache__`, etc.
- `.gitattributes`: Forcing LF voor `.py`, `.html`, `.js`, `.css`; markeert `.db` als binary
- `core.autocrlf = true`: Voor correcte line endings op Windows

---

## Doelen

- Stabiele SCADA-applicatie voor Pi-hardware
- Lokale testbaarheid zonder fysieke hardware
- Onderhoudbare en modulaire code
- Realtime UI-updates via SocketIO
- Professionele workflow via Git, linter, CI/CD
- Toekomstige uitbreidingen zoals grafieken, alerts, en logging dashboards

---

## Samenwerking & Rollen

Deze repository is voorbereid voor samenwerking met een technische co-founder met focus op:

- Feature development (UI/UX, websockets, Modbus-integratie)
- Code refactoring en modularisatie
- Debugging (frontend/backend/hardware)
- Git-strategieën (branching, merging, conflicts)
- Testontwikkeling en CI/CD
- Deployment (systemd, Nginx, HTTPS)
- Raspberry Pi-specifieke problemen (serial, USB, hardwarecommunicatie)

---

## Richtlijn bij AI- of dev-assistentie

Bij gebruik van deze prompt door een AI-assistent of ontwikkelaar:

📝 **Graag op deze beginprompt alleen een korte reactie met een check wat momenteel de prioriteit is.**  
🎯 Vermijd uitgebreide antwoorden — stel liever een gerichte vraag over de volgende focus of benodigde actie binnen het project.

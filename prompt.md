# Obelix_SCADA

Obelix_SCADA is een professionele, modulaire SCADA-oplossing voor real-time monitoring en besturing van industriële systemen. Het systeem draait lokaal (DummyModbus) of in productie op een Raspberry Pi 5 met RS-485 hardware. De interface biedt veilige, eenvoudige toegang tot zowel het SCADA-dashboard als geïntegreerde live-trends via Grafana, allemaal achter één login.

---

## Overzicht

- **Professionele SCADA-omgeving** voor lokaal of remote gebruik
- **Geïntegreerde Grafana-dashboard** voor real-time trendanalyse
- **Toegang via één login** (nginx basic-auth, geen extra usermanagement)
- **Geschikt voor simulatie én echte hardware**

---

## Technologie-stack

- **Backend:** Python 3.12, Flask, Flask-SocketIO, minimalmodbus
- **Frontend:** Jinja2-templates, CSS, Vanilla JavaScript
- **Database:**
  - `settings.db` (SQLite): instellingen, calibratie, relay-states
  - **InfluxDB:** primaire tijdreeksdatabase voor sensordata (live en historisch, ontsloten via Grafana)
  - `sensor_data.db` (SQLite): (optioneel/historisch, niet meer in gebruik voor actieve opslag)
- **Communicatie:** Modbus RTU over RS-485 of DummyModbusClient
- **Visualisatie:** Grafana (via reverse proxy)
- **Webserver:** nginx (reverse proxy, basic-auth)
- **Remote Access:** Tailscale Funnel (optioneel)

---

## Ontwikkel- en productieomgeving

- **Lokaal (development):**
  - Windows 11, VS Code, virtualenv, `python app.py`
  - DummyModbus voor simulatie

- **Productie:**
  - Raspberry Pi 5 (Bookworm/Debian 12)
  - USB-RS485 adapter
  - SCADA-webinterface op poort 5001
  - Grafana op poort 3000 (datasource: InfluxDB)
  - nginx reverse proxy op poort 6000 (beveiligd met basic-auth)

---

## Architectuur & Beveiliging

- **Toegang:**
  - Via Tailscale Funnel ([https://raspi52.tail239abf.ts.net](https://raspi52.tail239abf.ts.net)) of lokaal LAN
  - nginx reverse proxy (poort 6000) met basic-auth op alle routes
  - Gebruikersbeheer uitsluitend via `.htpasswd` (geen extra usermanagement in Flask/Grafana)

- **SCADA-app:**
  - Proxy via `/` en `/socket.io/` naar Flask backend (5001)
  - Real-time bediening & live-status via Flask-SocketIO

- **Grafana dashboard:**
  - Ingebed of als aparte tab via `/grafana/`
  - Live-data & trends (InfluxDB als datasource) met correcte WebSocket-support voor realtime panels

---

## Git-strategie

- **Branches:**  
  - `dev` (actief), `master` (stable), `backup-v1`
- **Workflow:**
  1. Ontwikkel/test lokaal in `dev` (met DummyModbus)
  2. Push naar GitHub, pull op Pi, test met hardware
  3. Merge naar `master` en update `backup-v1` na succesvolle validatie

---

## Samenwerkingsrichtlijn AI-assistentie

- Vraag altijd eerst: “Wat is nu de hoogste prioriteit binnen het project?”
- Lever codevoorbeelden als **volledige bestanden** (HTML, JS, Python), niet als fragmenten of in canvas.
- Houd antwoorden kort en zakelijk; sluit af met één gerichte vervolgvraag.
- Volg de workflow: wijzig in `dev`, test lokaal, merge naar `master` na verificatie.

---

## Kernpunten

- Volledig modulaire SCADA met veilige remote toegang en moderne web-frontend
- Alle communicatie en data-beveiliging via één vertrouwde (basic-auth) login
- Real-time control, logging en trendanalyse via geïntegreerde Flask en Grafana (InfluxDB als sensordata-bron)
- Eenvoudige gebruikers- en codebasebeheer via Git, zonder overbodige complexiteit

---

**Vervolgvraag:**  
_Wat wil je als volgende optimaliseren of documenteren binnen Obelix_SCADA?_

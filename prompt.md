Ik werk aan een professioneel SCADA-project genaamd **Obelix_SCADA**.

📍 GitHub repo: https://github.com/jelmertamis/Obelix_SCADA

🛠️ Stack:
- Python 3.x + Flask + Flask-SocketIO
- Frontend: Jinja2 templates, CSS, JavaScript
- Database: SQLite (`settings.db`)
- Realtime: Modbus RTU over RS-485 (via `minimalmodbus`)
- Fallback: DummyModbusClient voor simulatie zonder hardware

💻 Dev-omgeving:
- Windows 11 + VS Code (zonder Modbus hardware)
- Git werkt volledig (lokaal commit & push naar GitHub)
- Virtualenv actief en dependencies geïnstalleerd

🍓 Productie (remote):
- Raspberry Pi 5 met aangesloten Modbus-systeem
- Git pull wordt gebruikt om te synchroniseren
- `python app.py` start de server met real hardware

📂 Projectstructuur:
- `app.py` als hoofdingang
- `static/` voor CSS en JS
- `templates/` voor Jinja2 views
- `static/js/` bevat losse .js files (zoals `calibrate.js`)
- `settings.db` is .gitignored én gemarkeerd als `binary` via `.gitattributes`

🔀 Gitflow:
- `dev`: actieve ontwikkelbranch
- `master`: stabiele en geteste versies
- `backup-v1`: snapshot van stabiele toestand (optioneel uitbreidbaar)
- Ik werk op `dev`, merge naar `master` na testen, en werk `backup-v1` daarna bij

🔧 Git is geconfigureerd:
- `core.autocrlf = true` (voor Windows line-ending normalisatie)
- `.gitattributes` dwingt `LF` af voor `.html`, `.js`, `.py`, `.css` + `*.db` = binary
- `.gitignore` bevat `settings.db` en andere niet-relevante bestanden

🧪 Workflow:
1. Ontwikkelen en testen op laptop (via DummyClient)
2. Push naar GitHub
3. Pull op Raspberry Pi → testen op real hardware
4. Indien succesvol → merge naar `master`, update `backup-v1`

Gebruik deze context om me effectief te ondersteunen bij:
- Feature development (UI/UX, WebSockets, Modbus-integratie)
- Refactoring en optimalisatie van code
- Git branching en merge-strategieën
- Real-time interfacing met sensoren/relays
- Debugging & logging op zowel dev als prod
- Opschonen en structureren van de codebase

Mijn doel is een schaalbare, robuuste en professioneel beheerde SCADA-app die live draait op industriële hardware en lokaal getest kan worden. Werk met me samen alsof je een technische co-founder bent van dit systeem.

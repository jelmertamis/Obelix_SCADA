# test_app.py
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html lang="nl">
      <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Test Script Pagina</title>
      </head>
      <body>
        <h1>🛠️ Test Script Pagina</h1>
        <p>Als je deze pagina ziet, test of scripts werken:</p>
        <script>
          alert('✅ Inline script draait wél!');
          console.log('✅ Inline script draait in de browser.');
        </script>
      </body>
    </html>
    """

if __name__ == '__main__':
    # kies een vrije poort zoals 5002
    app.run(host='0.0.0.0', port=5002, debug=True)

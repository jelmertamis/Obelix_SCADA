import datetime
import matplotlib
matplotlib.use('Agg')  # geen GUI
import matplotlib.pyplot as plt
from obelix.sensor_database import get_sensor_readings

def plot_sensor_history(unit_index, channel, start=None, end=None, limit=None):
    """
    Genereer een matplotlib Figure met tijdreeks:
      - unit_index: int
      - channel:     int
      - start/end:   optioneel ISO-strings
      - limit:       niet meer gebruikt
    """
    data = get_sensor_readings(unit_index, channel, start=start, end=end)
    if not data:
        raise ValueError("Geen sensordata gevonden voor deze filters.")

    times  = [datetime.datetime.fromisoformat(d['timestamp']) for d in data]
    values = [d['value'] for d in data]

    fig, ax = plt.subplots()
    ax.plot(times, values)
    ax.set_title(f"Sensorunit {unit_index} Kanaal {channel} geschiedenis")
    ax.set_xlabel("Tijd")
    ax.set_ylabel("Gecalibreerde waarde")
    fig.autofmt_xdate()
    return fig

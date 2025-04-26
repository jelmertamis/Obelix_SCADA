# obelix/sensor_plot.py (nieuw)
import sqlite3
import datetime
import matplotlib.pyplot as plt
from obelix.config import Config
from obelix.sensor_database import get_recent_sensor_readings


def plot_sensor_history(unit_index=None, channel=None, limit=100):
    """
    Haal recente sensorleeswaarden op en genereer een tijdreeksplot.
    - unit_index: filter op specifieke unit (int)
    - channel: filter op specifiek kanaal (int)
    - limit: maximaal aantal records om op te halen
    Returns: matplotlib.Figure
    """
    # Ophalen van data
    all_data = get_recent_sensor_readings(limit)
    # Filteren
    filtered = [d for d in all_data
                if (unit_index is None or d['unit_index'] == unit_index)
                and (channel is None or d['channel'] == channel)]
    if not filtered:
        raise ValueError("Geen sensordata gevonden voor de opgegeven filters")

    # Omzetten timestamps
    times = [datetime.datetime.fromisoformat(d['timestamp']) for d in filtered]
    values = [d['value'] for d in filtered]

    # Maak plot
    fig, ax = plt.subplots()
    ax.plot(times[::-1], values[::-1])  # omkeren zodat oudste links staat
    ax.set_title(f"Sensorunit {unit_index or 'all'} Kanaal {channel or 'all'} geschiedenis")
    ax.set_xlabel("Tijd")
    ax.set_ylabel("Gecalibreerde waarde")
    fig.autofmt_xdate()
    return fig


def save_plot(fig, path):
    """
    Sla een matplotlib-plot op naar bestand.
    """
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)

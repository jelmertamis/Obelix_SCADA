<!-- templates/sensor_plot.html -->
{% extends 'base.html' %}

{% block title %}Sensor Historie{% endblock %}

{% block content %}
<section class="sensor-plot">
  <h1>Sensor Historie</h1>
  <form id="plotForm" class="plot-form">
    <label>Unit:
      <select name="unit_index" id="unit_index">
        <option value="">Alle units</option>
        {% for unit in units %}
        <option value="{{ unit.idx }}">{{ unit.name }} (Slave {{ unit.slave_id }})</option>
        {% endfor %}
      </select>
    </label>
    <label>Kanaal:
      <select name="channel" id="channel">
        <option value="">Alle kanalen</option>
        {% for ch in range(4) %}
        <option value="{{ ch }}">Kanaal {{ ch }}</option>
        {% endfor %}
      </select>
    </label>
    <label>Vanaf:
      <input type="datetime-local" name="start" id="start">
    </label>
    <label>Tot:
      <input type="datetime-local" name="end" id="end">
    </label>
    <label>Limit:
      <input type="number" name="limit" id="limit" value="100" min="1">
    </label>
    <button type="submit" class="btn">Plot</button>
  </form>
  <div id="plotMeta" class="plot-meta"></div>
  <div id="plotArea" class="plot-area">
    <img id="sensorPlot" src="" alt="Sensor Plot">
  </div>
</section>
{% endblock %}

{% block scripts %}
<script>
  document.getElementById('plotForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const form = this;
    const params = new URLSearchParams(new FormData(form));
    // Voeg alleen start/end toe als ingevuld
    const start = form.querySelector('#start').value;
    const end = form.querySelector('#end').value;
    if (start) params.set('start', start);
    if (end)   params.set('end', end);

    document.getElementById('sensorPlot').src = '/plot/sensor?' + params.toString();

    // Toon metadata boven de plot
    const unitSelect = form.querySelector('#unit_index');
    const chanSelect = form.querySelector('#channel');
    const unitText = unitSelect.value
      ? unitSelect.options[unitSelect.selectedIndex].text
      : 'Alle units';
    const chanText = chanSelect.value !== ''
      ? 'Kanaal ' + chanSelect.value
      : 'Alle kanalen';
    const rangeText = (start ? ' vanaf ' + start : '') + (end ? ' tot ' + end : '');
    document.getElementById('plotMeta').textContent = unitText + ' - ' + chanText + rangeText;
  });
</script>
{% endblock %}

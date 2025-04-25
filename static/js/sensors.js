const socket = io('/sensors');
const tbody  = document.getElementById('sensorBody');

socket.on('connect', () => {
  console.log('✅ WebSocket verbonden op /sensors');
  tbody.innerHTML = '<tr><td colspan="5" class="no-data">Verbonden – wachten op sensor_update…</td></tr>';
});

socket.on('sensor_update', readings => {
  console.log('🔔 sensor_update ontvangen:', readings);
  if (!readings || readings.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="no-data">Geen sensoren gevonden.</td></tr>';
    return;
  }

  tbody.innerHTML = '';
  readings.forEach(r => {
    const tr = document.createElement('tr');
    ['name','slave_id','channel','raw','value'].forEach(key => {
      const td = document.createElement('td');
      let txt = r[key] !== null ? r[key] : '—';
      if (key === 'value') txt = r.value.toFixed(2);
      td.textContent = txt;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
});

socket.on('disconnect', () => {
  console.warn('❌ WebSocket verbinding verbroken');
  tbody.innerHTML = '<tr><td colspan="5" class="no-data">Verbinding verbroken.</td></tr>';
});

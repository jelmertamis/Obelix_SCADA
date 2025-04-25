// static/js/calibrate.js

const RAW1 = 819, RAW2 = 4095;
const socket = io('/cal');
const rows = document.querySelectorAll('tbody tr');

socket.on('init_cal', data => {
  rows.forEach(row => {
    const key = `${row.dataset.unit}-${row.dataset.channel}`;
    if (data[key]) {
      const { scale, offset, phys_min, phys_max, unit } = data[key];
      row.querySelector('.slope').textContent       = scale.toFixed(4);
      row.querySelector('.offset').textContent      = offset.toFixed(2);
      row.querySelector('.minVal').value            = phys_min.toFixed(2);
      row.querySelector('.maxVal').value            = phys_max.toFixed(2);
      row.querySelector('.unitVal').value           = unit;
      row.querySelector('.unitDisplay').textContent = unit || '—';
    }
  });
});

socket.on('cal_saved', info => {
  const sel = `tr[data-unit="${info.unit}"][data-channel="${info.channel}"]`;
  const row = document.querySelector(sel);
  row.querySelector('.slope').textContent        = info.scale.toFixed(4);
  row.querySelector('.offset').textContent       = info.offset.toFixed(2);
  row.querySelector('.minVal').value             = info.phys_min.toFixed(2);
  row.querySelector('.maxVal').value             = info.phys_max.toFixed(2);
  row.querySelector('.unitVal').value            = info.unitStr;
  row.querySelector('.unitDisplay').textContent  = info.unitStr || '—';
  const fb = row.querySelector('.feedback');
  fb.textContent = '✓ Opslaan gelukt';
  fb.className   = 'feedback status';
  setTimeout(() => fb.textContent = '', 3000);
});

socket.on('cal_error', err => {
  alert('Kalibratie fout: ' + err.error);
});

rows.forEach(row => {
  row.querySelector('.saveBtn').addEventListener('click', () => {
    const unit    = +row.dataset.unit;
    const channel = +row.dataset.channel;
    const phys1   = parseFloat(row.querySelector('.minVal').value);
    const phys2   = parseFloat(row.querySelector('.maxVal').value);
    const unitStr = row.querySelector('.unitVal').value.trim();
    const fb      = row.querySelector('.feedback');

    if (isNaN(phys1) || isNaN(phys2)) {
      fb.textContent = 'Vul beide waarden in';
      fb.className   = 'feedback error';
      return;
    }
    fb.textContent = '';

    socket.emit('set_cal_points', {
      unit:    unit,
      channel: channel,
      raw1:    RAW1,
      phys1:   phys1,
      raw2:    RAW2,
      phys2:   phys2,
      unitStr: unitStr
    });
  });
});

// Initialiseer de kalibratie-gegevens
socket.emit('connect');
socket.emit('init_cal');

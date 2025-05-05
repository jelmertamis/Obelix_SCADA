// sbr.js - Leesbaardere refactor voor SBR Control

// Definieer fases met hun type ('level' of 'time')
const PHASES = [
  { key: 'influent',      type: 'level' },
  { key: 'react',         type: 'time'  },
  { key: 'effluent',      type: 'level' },
  { key: 'wait',          type: 'time'  },
  { key: 'dose_nutrients',type: 'time'  },
  { key: 'wait_after_N',  type: 'time'  },
];

// Socket-verbindingen
const sbrSocket     = io('/sbr');
const sensorSocket  = io('/sensors');

// DOM-elementen
const elements = {
  timer:      document.getElementById('cycle-timer'),
  toggleBtn:  document.getElementById('btn-toggle'),
  resetBtn:   document.getElementById('btn-reset'),
  maxInput:   document.getElementById('cycle-max-input'),
  maxSetBtn:  document.getElementById('btn-set-cycle-max'),
  heatOnInput:  document.getElementById('heat-on-input'),
  heatOffInput: document.getElementById('heat-off-input'),
  heatSetBtn:   document.getElementById('btn-set-heat'),
  container: document.getElementById('sbr-config-section'),
  boxes:   {},
  actual:  {},
  target:  {},
  inputs:  {},
  setBtns: {},
};

// Initialiseer elementen per fase
PHASES.forEach(({ key }) => {
  elements.boxes[key]   = document.getElementById(`phase-${key}-box`);
  elements.actual[key]  = document.getElementById(`${key}-actual`);
  elements.target[key]  = document.getElementById(`${key}-target`);
  elements.inputs[key]  = document.getElementById(`${key}-input`);
  elements.setBtns[key] = document.getElementById(`btn-set-${key}`);
});

let lastPhase = PHASES[0].key;
let isActive  = false;

// ----------------------------------
// Helper functies
// ----------------------------------

function updateHighlight(current) {
  PHASES.forEach(({ key }) => {
    const active = isActive ? key === current : key === lastPhase;
    elements.boxes[key].classList.toggle('active', active);
  });
}

function validateNonNegative(value, label) {
  if (isNaN(value) || value < 0) {
    alert(`${label} moet ≥ 0 zijn`);
    return false;
  }
  return true;
}

// ----------------------------------
// Socket event handlers
// ----------------------------------

function handlePhaseTimes(data) {
  // Process thresholds en tijden op basis van type
  PHASES.forEach(({ key, type }) => {
    if (type === 'level') {
      const thr = data[`${key}_threshold`];
      elements.target[key].textContent = thr;
      elements.inputs[key].value       = thr;
    } else {
      const minutes = data[`${key}_minutes`];
      const seconds = data[`${key}_seconds`];
      elements.inputs[key].value        = minutes;
      elements.target[key].textContent = seconds;
    }
  });

  // Max cycle time
  const maxT = data.cycle_time_max_minutes;
  elements.maxInput.value = maxT;
  document.getElementById('cycle-max-text').textContent = maxT;

  // Heat setpoints
  const onT  = data.heating_on_temp;
  const offT = data.heating_off_temp;
  elements.heatOnInput.value  = onT;
  elements.heatOffInput.value = offT;
  document.getElementById('heat-on-text').textContent  = onT;
  document.getElementById('heat-off-text').textContent = offT;
}

function handleStatus(data) {
  isActive = data.active;
  elements.toggleBtn.textContent = isActive ? 'Stop Cycle' : 'Start Cycle';
  elements.container.classList.toggle('paused', !isActive);

  lastPhase = data.phase || lastPhase;
  updateHighlight(data.phase);

  // Toon fase-elapsed voor time-fases
  PHASES.filter(p => p.type === 'time').forEach(({ key }) => {
    elements.actual[key].textContent = key === data.phase ? data.phase_elapsed : '';
  });
}

function handleTimer(data) {
  const mins = String(Math.floor(data.timer / 60)).padStart(2, '0');
  const secs = String(data.timer % 60).padStart(2, '0');
  elements.timer.textContent = `Cyclus: ${mins}:${secs}`;

  lastPhase = data.phase;
  updateHighlight(data.phase);

  // Update actual/target
  PHASES.forEach(({ key, type }) => {
    if (type === 'time') {
      elements.actual[key].textContent = key === data.phase ? data.phase_elapsed : '';
    }
    if (key === data.phase && data.phase_target !== undefined) {
      elements.target[key].textContent = data.phase_target;
    }
  });
}

function handleSensorUpdate(readings) {
  const lvl = readings.find(r => r.slave_id === 5 && r.channel === 0);
  if (lvl) {
    const val = lvl.value.toFixed(1);
    elements.actual.influent.textContent = val;
    elements.actual.effluent.textContent = val;
  }
}

// ----------------------------------
// Event binding
// ----------------------------------

sbrSocket.on('connect',    () => sbrSocket.emit('sbr_get_phase_times'));
sbrSocket.on('sbr_phase_times', handlePhaseTimes);
sbrSocket.on('sbr_status',      handleStatus);
sbrSocket.on('sbr_timer',       handleTimer);
sensorSocket.on('sensor_update', handleSensorUpdate);

// Fase-instellingen
PHASES.forEach(({ key, type }) => {
  const btn   = elements.setBtns[key];
  const input = elements.inputs[key];
  const label = type === 'level' ? 'Level' : 'Time';

  btn.addEventListener('click', () => {
    const val = input.valueAsNumber;
    if (!validateNonNegative(val, label)) return;

    if (type === 'level') {
      const evt = key === 'influent'
        ? 'sbr_set_threshold'
        : 'sbr_set_effluent_threshold';
      sbrSocket.emit(evt, { threshold: val });
    } else {
      sbrSocket.emit('sbr_set_phase_times', { [key]: val });
    }
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { btn.click(); e.preventDefault(); }
  });
});

// Cycle control
elements.toggleBtn.addEventListener('click', () =>
  sbrSocket.emit('sbr_control', { action: 'toggle' })
);
elements.resetBtn.addEventListener('click', () =>
  sbrSocket.emit('sbr_control', { action: 'reset' })
);

// Max cycle time
elements.maxSetBtn.addEventListener('click', () => {
  const v = elements.maxInput.valueAsNumber;
  if (!validateNonNegative(v, 'Max Cycle Time')) return;
  sbrSocket.emit('sbr_set_cycle_time_max', { max_minutes: v });
});
elements.maxInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') { elements.maxSetBtn.click(); e.preventDefault(); }
});

// Heating setpoints
function applyHeatSetpoints() {
  const on  = elements.heatOnInput.valueAsNumber;
  const off = elements.heatOffInput.valueAsNumber;
  if (isNaN(on) || isNaN(off) || off < on) {
    return alert('Voer geldige Heat ON/Off waarden in (OFF ≥ ON)');
  }
  sbrSocket.emit('sbr_set_heating_setpoints', { on_temp: on, off_temp: off });
}

elements.heatSetBtn.addEventListener('click', applyHeatSetpoints);
[elements.heatOnInput, elements.heatOffInput].forEach(input => {
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { applyHeatSetpoints(); e.preventDefault(); }
  });
  input.addEventListener('change', applyHeatSetpoints);
});

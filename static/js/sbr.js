// sbr.js - Centraal configureren van alle magic strings met JSDoc

/**
 * Configuratie-object voor namespaces, events en DOM-selectors.
 * @constant {Object}
 */
const SBR_CONFIG = {
  /** Socket.io namespaces */
  namespaces: {
    sbr:    '/sbr',
    sensor: '/sensors',
  },
  /** Event-namen voor communicatie met de server */
  events: {
    getPhaseTimes:        'sbr_get_phase_times',
    phaseTimes:           'sbr_phase_times',
    status:               'sbr_status',
    timer:                'sbr_timer',
    sensorUpdate:         'sensor_update',
    control:              'sbr_control',
    setThreshold:         'sbr_set_threshold',
    setEffluentThreshold: 'sbr_set_effluent_threshold',
    setPhaseTimes:        'sbr_set_phase_times',
    setCycleTimeMax:      'sbr_set_cycle_time_max',
    setHeatingSetpoints:  'sbr_set_heating_setpoints',
  },
  /** DOM-element ID's en prefixes/suffixes */
  dom: {
    timer:            'cycle-timer',
    toggleBtn:        'btn-toggle',
    resetBtn:         'btn-reset',
    maxInput:         'cycle-max-input',
    maxSetBtn:        'btn-set-cycle-max',
    maxText:          'cycle-max-text',
    heatOnInput:      'heat-on-input',
    heatOffInput:     'heat-off-input',
    heatSetBtn:       'btn-set-heat',
    heatOnText:       'heat-on-text',
    heatOffText:      'heat-off-text',
    container:        'sbr-config-section',
    phaseBoxPrefix:   'phase-',
    phaseBoxSuffix:   '-box',
    phaseActualSuffix: '-actual',
    phaseTargetSuffix: '-target',
    phaseInputSuffix:  '-input',
    phaseBtnPrefix:    'btn-set-'
  }
};

/**
 * Beschrijving van een fase in de SBR-cyclus.
 * @typedef {Object} Phase
 * @property {string} key  - Unieke identificatie van de fase
 * @property {'level'|'time'} type - Type criterium voor overgang
 */

/**
 * Definities van alle fases met hun type ('level' of 'time').
 * @type {Phase[]}
 */
const PHASES = [
  { key: 'influent',       type: 'level' },
  { key: 'react',          type: 'time'  },
  { key: 'effluent',       type: 'level' },
  { key: 'wait',           type: 'time'  },
  { key: 'dose_nutrients', type: 'time'  },
  { key: 'wait_after_N',   type: 'time'  },
];

// Socket-verbindingen
const sbrSocket    = io(SBR_CONFIG.namespaces.sbr);
const sensorSocket = io(SBR_CONFIG.namespaces.sensor);

// DOM-elementen ophalen
const elements = {
  timer:       document.getElementById(SBR_CONFIG.dom.timer),
  toggleBtn:   document.getElementById(SBR_CONFIG.dom.toggleBtn),
  resetBtn:    document.getElementById(SBR_CONFIG.dom.resetBtn),
  maxInput:    document.getElementById(SBR_CONFIG.dom.maxInput),
  maxSetBtn:   document.getElementById(SBR_CONFIG.dom.maxSetBtn),
  maxText:     document.getElementById(SBR_CONFIG.dom.maxText),
  heatOnInput: document.getElementById(SBR_CONFIG.dom.heatOnInput),
  heatOffInput:document.getElementById(SBR_CONFIG.dom.heatOffInput),
  heatSetBtn:  document.getElementById(SBR_CONFIG.dom.heatSetBtn),
  heatOnText:  document.getElementById(SBR_CONFIG.dom.heatOnText),
  heatOffText: document.getElementById(SBR_CONFIG.dom.heatOffText),
  container:   document.getElementById(SBR_CONFIG.dom.container),
  boxes:   {},
  actual:  {},
  target:  {},
  inputs:  {},
  setBtns: {}
};

// Initialiseer fase-elementen dynamisch
PHASES.forEach(({ key }) => {
  const boxId     = SBR_CONFIG.dom.phaseBoxPrefix + key + SBR_CONFIG.dom.phaseBoxSuffix;
  const actualId  = key + SBR_CONFIG.dom.phaseActualSuffix;
  const targetId  = key + SBR_CONFIG.dom.phaseTargetSuffix;
  const inputId   = key + SBR_CONFIG.dom.phaseInputSuffix;
  const btnId     = SBR_CONFIG.dom.phaseBtnPrefix + key;

  elements.boxes[key]   = document.getElementById(boxId);
  elements.actual[key]  = document.getElementById(actualId);
  elements.target[key]  = document.getElementById(targetId);
  elements.inputs[key]  = document.getElementById(inputId);
  elements.setBtns[key] = document.getElementById(btnId);
});

/**
 * Houdt de laatst actieve fase bij voor pauzestatus.
 * @type {string}
 */
let lastPhase = PHASES[0].key;

/**
 * Status of de cyclus actief is.
 * @type {boolean}
 */
let isActive = false;

// ----------------------------------
// Helper functies
// ----------------------------------

/**
 * Highlight de huidige fase-box en dim de rest.
 * @param {string} current - Key van de huidige fase
 */
function updateHighlight(current) {
  PHASES.forEach(({ key }) => {
    const active = isActive ? (key === current) : (key === lastPhase);
    elements.boxes[key].classList.toggle('active', active);
  });
}

/**
 * Valideert of een waarde niet-negatief is en toont eventueel een alert.
 * @param {number} value - Ingevoerde waarde
 * @param {string} label - Label voor de alert
 * @returns {boolean} True als geldig
 */
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

/**
 * Initieert de weergave van setpoints en thresholds.
 * @param {Object} data - Gegevens van de server
 */
function handlePhaseTimes(data) {
  PHASES.forEach(({ key, type }) => {
    if (type === 'level') {
      const thr = data[`${key}_threshold`];
      elements.target[key].textContent = thr;
      elements.inputs[key].value = thr;
    } else {
      const mins = data[`${key}_minutes`];
      const secs = data[`${key}_seconds`];
      elements.inputs[key].value = mins;
      elements.target[key].textContent = secs;
    }
  });

  const maxT = data.cycle_time_max_minutes;
  elements.maxInput.value = maxT;
  elements.maxText.textContent = maxT;

  const onT = data.heating_on_temp;
  const offT = data.heating_off_temp;
  elements.heatOnInput.value = onT;
  elements.heatOffInput.value = offT;
  elements.heatOnText.textContent = onT;
  elements.heatOffText.textContent = offT;
}

/**
 * Werk de start/stop-status bij.
 * @param {Object} data - Statusinformatie van de server
 */
function handleStatus(data) {
  isActive = data.active;
  elements.toggleBtn.textContent = isActive ? 'Stop Cycle' : 'Start Cycle';
  elements.container.classList.toggle('paused', !isActive);

  lastPhase = data.phase || lastPhase;
  updateHighlight(data.phase);

  PHASES.filter(p => p.type === 'time').forEach(({ key }) => {
    elements.actual[key].textContent = (key === data.phase ? data.phase_elapsed : '');
  });
}

/**
 * Update de timer-indicator.
 * @param {Object} data - Timergegevens van de server
 */
function handleTimer(data) {
  const mins = String(Math.floor(data.timer / 60)).padStart(2, '0');
  const secs = String(data.timer % 60).padStart(2, '0');
  elements.timer.textContent = `Cyclus: ${mins}:${secs}`;

  lastPhase = data.phase;
  updateHighlight(data.phase);

  PHASES.forEach(({ key, type }) => {
    if (type === 'time') {
      elements.actual[key].textContent = (key === data.phase ? data.phase_elapsed : '');
    }
    if (key === data.phase && data.phase_target !== undefined) {
      elements.target[key].textContent = data.phase_target;
    }
  });
}

/**
 * Werk het niveau van de analoge sensor bij.
 * @param {Array<Object>} readings - Lijst van sensorlezingen
 */
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

sbrSocket.on('connect',        () => sbrSocket.emit(SBR_CONFIG.events.getPhaseTimes));
sbrSocket.on(SBR_CONFIG.events.phaseTimes,     handlePhaseTimes);
sbrSocket.on(SBR_CONFIG.events.status,         handleStatus);
sbrSocket.on(SBR_CONFIG.events.timer,          handleTimer);
sensorSocket.on(SBR_CONFIG.events.sensorUpdate, handleSensorUpdate);

// Fase-instellingen binden
PHASES.forEach(({ key, type }) => {
  const btn   = elements.setBtns[key];
  const input = elements.inputs[key];
  const label = type === 'level' ? 'Level' : 'Time';

  /**
   * Stuur de nieuwe instelling voor deze fase naar de server.
   */
  btn.addEventListener('click', () => {
    const val = input.valueAsNumber;
    if (!validateNonNegative(val, label)) return;

    if (type === 'level') {
      const evt = key === 'influent'
        ? SBR_CONFIG.events.setThreshold
        : SBR_CONFIG.events.setEffluentThreshold;
      sbrSocket.emit(evt, { threshold: val });
    } else {
      sbrSocket.emit(SBR_CONFIG.events.setPhaseTimes, { [key]: val });
    }
  });

  // Enter-toets naar click omzetten
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { btn.click(); e.preventDefault(); }
  });
});

// Teach cycle control to the buttons

/**
 * Wissel start/stop van de SBR-cyclus.
 */
elements.toggleBtn.addEventListener('click', () =>
  sbrSocket.emit(SBR_CONFIG.events.control, { action: 'toggle' })
);

/**
 * Reset de SBR-cyclus.
 */
elements.resetBtn.addEventListener('click', () =>
  sbrSocket.emit(SBR_CONFIG.events.control, { action: 'reset' })
);

// Max cycle time
elements.maxSetBtn.addEventListener('click', () => {
  const v = elements.maxInput.valueAsNumber;
  if (!validateNonNegative(v, 'Max Cycle Time')) return;
  sbrSocket.emit(SBR_CONFIG.events.setCycleTimeMax, { max_minutes: v });
});
elements.maxInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') { elements.maxSetBtn.click(); e.preventDefault(); }
});

// Heating setpoints

/**
 * Send heating ON/OFF setpoints to server.
 */
function applyHeatSetpoints() {
  const on  = elements.heatOnInput.valueAsNumber;
  const off = elements.heatOffInput.valueAsNumber;
  if (isNaN(on) || isNaN(off) || off < on) {
    return alert('Voer geldige Heat ON/Off waarden in (OFF ≥ ON)');
  }
  sbrSocket.emit(SBR_CONFIG.events.setHeatingSetpoints, { on_temp: on, off_temp: off });
}

elements.heatSetBtn.addEventListener('click', applyHeatSetpoints);
[elements.heatOnInput, elements.heatOffInput].forEach(input => {
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { applyHeatSetpoints(); e.preventDefault(); }
  });
  input.addEventListener('change', applyHeatSetpoints);
});

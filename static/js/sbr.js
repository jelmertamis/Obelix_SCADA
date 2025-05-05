// sbr.js - Leesbaardere refactor voor SBR Control

// Fase-namen en elementen
const PHASES = [
  "influent",
  "react",
  "effluent",
  "wait",
  "dose_nutrients",
  "wait_after_N",
];

// Socket-verbindingen
const sbrSocket = io("/sbr");
const sensorSocket = io("/sensors");

// DOM-elementen in één object
const elements = {
  timer: document.getElementById("cycle-timer"),
  toggleBtn: document.getElementById("btn-toggle"),
  resetBtn: document.getElementById("btn-reset"),
  maxInput: document.getElementById("cycle-max-input"),
  maxSetBtn: document.getElementById("btn-set-cycle-max"),
  heatOnInput: document.getElementById("heat-on-input"),
  heatOffInput: document.getElementById("heat-off-input"),
  heatSetBtn: document.getElementById("btn-set-heat"),
  container: document.getElementById("sbr-config-section"),
  boxes: {},         // fase-boxen
  actual: {},        // actuele waarden
  target: {},        // doelwaarden
  inputs: {},        // invoervelden
  setBtns: {},       // set-knoppen
};

// Dynamisch vullen voor iedere fase
PHASES.forEach(phase => {
  elements.boxes[phase]   = document.getElementById(`phase-${phase}-box`);
  elements.actual[phase]  = document.getElementById(`${phase}-actual`);
  elements.target[phase]  = document.getElementById(`${phase}-target`);
  elements.inputs[phase]  = document.getElementById(`${phase}-input`);
  elements.setBtns[phase] = document.getElementById(`btn-set-${phase}`);
});

let lastPhase = PHASES[0];
let isActive = false;

// ----------------------------------
// Helper functies
// ----------------------------------

/**
 * Markeer de actieve fase
 */
function updateHighlight(current) {
  PHASES.forEach(phase => {
    const active = isActive ? phase === current : phase === lastPhase;
    elements.boxes[phase].classList.toggle("active", active);
  });
}

/**
 * Toon waarschuwing bij invalide invoer
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
 * Initiële setpoints en thresholds tonen
 */
function handlePhaseTimes(data) {
  // Influent/Effluent thresholds
  elements.target.influent.textContent = data.influent_threshold;
  elements.inputs.influent.value       = data.influent_threshold;
  elements.target.effluent.textContent = data.effluent_threshold;
  elements.inputs.effluent.value       = data.effluent_threshold;

  // Tijds-fases
  ["react", "wait", "dose_nutrients", "wait_after_N"].forEach(phase => {
    elements.inputs[phase].value        = data[`${phase}_minutes`];
    elements.target[phase].textContent = data[`${phase}_seconds`];
  });

  // Max cycle time
  elements.maxInput.value = data.cycle_time_max_minutes;
  document.getElementById("cycle-max-text").textContent = data.cycle_time_max_minutes;

  // Heat setpoints
  elements.heatOnInput.value = data.heating_on_temp;
  elements.heatOffInput.value = data.heating_off_temp;
  document.getElementById("heat-on-text").textContent  = data.heating_on_temp;
  document.getElementById("heat-off-text").textContent = data.heating_off_temp;
}

/**
 * Start/stop-status bijwerken
 */
function handleStatus(data) {
  isActive = data.active;
  elements.toggleBtn.textContent = isActive ? "Stop Cycle" : "Start Cycle";
  elements.container.classList.toggle("paused", !isActive);

  if (data.phase) lastPhase = data.phase;
  updateHighlight(data.phase);

  // Toon elapsed tijd voor time-phases
  PHASES.filter(p => !["influent","effluent"].includes(p)).forEach(phase => {
    elements.actual[phase].textContent = phase === data.phase ? data.phase_elapsed : '';
  });
}

/**
 * Timer-display updaten
 */
function handleTimer(data) {
  const minutes = String(Math.floor(data.timer / 60)).padStart(2, '0');
  const seconds = String(data.timer % 60).padStart(2, '0');
  elements.timer.textContent = `Cyclus: ${minutes}:${seconds}`;

  lastPhase = data.phase;
  updateHighlight(data.phase);

  // Update actuele en target voor huidige fase
  PHASES.forEach(phase => {
    if (!["influent","effluent"].includes(phase)) {
      elements.actual[phase].textContent = phase === data.phase ? data.phase_elapsed : '';
    }
    if (phase === data.phase && data.phase_target !== undefined) {
      elements.target[phase].textContent = data.phase_target;
    }
  });
}

/**
 * Niveau-sensor (analoge input) bijwerken
 */
function handleSensorUpdate(readings) {
  const level = readings.find(r => r.slave_id === 5 && r.channel === 0);
  if (level) {
    const formatted = level.value.toFixed(1);
    elements.actual.influent.textContent = formatted;
    elements.actual.effluent.textContent = formatted;
  }
}

// ----------------------------------
// Gebeurtenisbindingen
// ----------------------------------

// Socket.IO
sbrSocket.on("connect", () => sbrSocket.emit("sbr_get_phase_times"));
sbrSocket.on("sbr_phase_times", handlePhaseTimes);
sbrSocket.on("sbr_status", handleStatus);
sbrSocket.on("sbr_timer", handleTimer);
sensorSocket.on("sensor_update", handleSensorUpdate);

// Fase-instellingen via set-knoppen
PHASES.forEach(phase => {
  const btn   = elements.setBtns[phase];
  const input = elements.inputs[phase];

  btn.addEventListener("click", () => {
    const value = input.valueAsNumber;
    const label = (phase === "influent" || phase === "effluent") ? 'Level' : 'Time';
    if (!validateNonNegative(value, label)) return;

    if (phase === "influent") {
      sbrSocket.emit("sbr_set_threshold", { threshold: value });
    } else if (phase === "effluent") {
      sbrSocket.emit("sbr_set_effluent_threshold", { threshold: value });
    } else {
      sbrSocket.emit("sbr_set_phase_times", { [phase]: value });
    }
  });

  // Enter-key stuurt click
  input.addEventListener("keydown", e => {
    if (e.key === 'Enter') {
      btn.click();
      e.preventDefault();
    }
  });
});

// Cycle control
elements.toggleBtn.addEventListener("click", () =>
  sbrSocket.emit("sbr_control", { action: "toggle" })
);
elements.resetBtn.addEventListener("click", () =>
  sbrSocket.emit("sbr_control", { action: "reset" })
);

// Max cycle time
elements.maxSetBtn.addEventListener("click", () => {
  const value = elements.maxInput.valueAsNumber;
  if (!validateNonNegative(value, 'Max Cycle Time')) return;
  sbrSocket.emit("sbr_set_cycle_time_max", { max_minutes: value });
});
elements.maxInput.addEventListener("keydown", e => {
  if (e.key === 'Enter') {
    elements.maxSetBtn.click();
    e.preventDefault();
  }
});

// Heating setpoints
function applyHeatSetpoints() {
  const on  = elements.heatOnInput.valueAsNumber;
  const off = elements.heatOffInput.valueAsNumber;
  if (isNaN(on) || isNaN(off) || off < on) {
    return alert("Voer geldige Heat ON/Off waarden in (OFF ≥ ON)");
  }
  sbrSocket.emit("sbr_set_heating_setpoints", { on_temp: on, off_temp: off });
}

elements.heatSetBtn.addEventListener("click", applyHeatSetpoints);
[ elements.heatOnInput, elements.heatOffInput ].forEach(input => {
  input.addEventListener("keydown", e => {
    if (e.key === 'Enter') {
      applyHeatSetpoints();
      e.preventDefault();
    }
  });
  input.addEventListener("change", applyHeatSetpoints);
});

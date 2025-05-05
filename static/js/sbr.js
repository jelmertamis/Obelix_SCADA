// Minimal refactor: verzamel alle DOM-elementen in één object en maak code iets overzichtelijker
const phases = [
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

// DOM-elementen groeperen voor overzicht
const elements = {
  cycleTimer:   document.getElementById("cycle-timer"),
  btnToggle:    document.getElementById("btn-toggle"),
  btnReset:     document.getElementById("btn-reset"),
  btnSetMax:    document.getElementById("btn-set-cycle-max"),
  maxInput:     document.getElementById("cycle-max-input"),
  btnSetHeat:   document.getElementById("btn-set-heat"),
  heatOnInput:  document.getElementById("heat-on-input"),
  heatOffInput: document.getElementById("heat-off-input"),
  section:      document.getElementById("sbr-config-section"),
  boxes: phases.reduce((acc, p) => { acc[p] = document.getElementById(`phase-${p}-box`); return acc; }, {}),
  actual: phases.reduce((acc, p) => { acc[p] = document.getElementById(`${p}-actual`); return acc; }, {}),
  target: phases.reduce((acc, p) => { acc[p] = document.getElementById(`${p}-target`); return acc; }, {}),
  inputs: phases.reduce((acc, p) => { acc[p] = document.getElementById(`${p}-input`); return acc; }, {}),
  setButtons: phases.reduce((acc, p) => { acc[p] = document.getElementById(`btn-set-${p}`); return acc; }, {}),
};

let lastPhase = "influent";
let isActive = false;

// Helper om highlight up-to-date te houden
function updateHighlight(currentPhase) {
  phases.forEach(p => {
    const shouldHighlight = isActive ? p === currentPhase : p === lastPhase;
    elements.boxes[p].classList.toggle("active", shouldHighlight);
  });
}

// Helper-functies voor socket-handlers
function handlePhaseTimes(data) {
  elements.target.influent.textContent = data.influent_threshold;
  elements.inputs.influent.value        = data.influent_threshold;
  elements.target.effluent.textContent = data.effluent_threshold;
  elements.inputs.effluent.value       = data.effluent_threshold;
  ["react","wait","dose_nutrients","wait_after_N"].forEach(p => {
    elements.inputs[p].value         = data[`${p}_minutes`];
    elements.target[p].textContent  = data[`${p}_seconds`];
  });
  elements.maxInput.value = data.cycle_time_max_minutes;
  document.getElementById("cycle-max-text").textContent = data.cycle_time_max_minutes;
  document.getElementById("heat-on-text").textContent  = data.heating_on_temp;
  document.getElementById("heat-off-text").textContent = data.heating_off_temp;
  elements.heatOnInput.value = data.heating_on_temp;
  elements.heatOffInput.value = data.heating_off_temp;
}

function handleStatus(data) {
  isActive = data.active;
  elements.btnToggle.textContent = isActive ? "Stop Cycle" : "Start Cycle";
  elements.section.classList.toggle("paused", !isActive);
  if (data.phase) lastPhase = data.phase;
  // Toon laatst bekende fase-elapsed bij pauze
  phases.forEach(p => {
    if (!["influent","effluent"].includes(p)) {
      elements.actual[p].textContent = p === data.phase ? String(data.phase_elapsed) : "";
    }
  });
  updateHighlight(data.phase);
}

function handleTimer(data) {
  const m = String(Math.floor(data.timer / 60)).padStart(2, "0");
  const s = String(data.timer % 60).padStart(2, "0");
  elements.cycleTimer.textContent = `Cyclus: ${m}:${s}`;
  lastPhase = data.phase;
  updateHighlight(data.phase);
  phases.forEach(p => {
    if (!["influent","effluent"].includes(p)) {
      elements.actual[p].textContent = p === data.phase ? String(data.phase_elapsed) : "";
    }
  });
  if (data.phase_target !== undefined) {
    elements.target[data.phase].textContent = data.phase_target;
  }
}

function handleSensorUpdate(readings) {
  const lvl = readings.find(r => r.slave_id === 5 && r.channel === 0);
  if (lvl) {
    elements.actual.influent.textContent = lvl.value.toFixed(1);
    elements.actual.effluent.textContent = lvl.value.toFixed(1);
  }
}

// Bind set-buttons voor elke fase
phases.forEach(p => {
  elements.setButtons[p].addEventListener("click", () => {
    const value = elements.inputs[p].valueAsNumber;
    if (isNaN(value) || value < 0) {
      return alert((p === "influent" || p === "effluent" ? "Level" : "Time") + " moet ≥ 0 zijn");
    }
    if (p === "influent") {
      sbrSocket.emit("sbr_set_threshold", { threshold: value });
    } else if (p === "effluent") {
      sbrSocket.emit("sbr_set_effluent_threshold", { threshold: value });
    } else {
      sbrSocket.emit("sbr_set_phase_times", { [p]: value });
    }
  });
  elements.inputs[p].addEventListener("keydown", e => {
    if (e.key === "Enter") {
      elements.setButtons[p].click();
      e.preventDefault();
    }
  });
});

// Control-buttons
elements.btnToggle.addEventListener("click", () => sbrSocket.emit("sbr_control", { action: "toggle" }));
elements.btnReset.addEventListener("click", () => sbrSocket.emit("sbr_control", { action: "reset" }));

elements.btnSetMax.addEventListener("click", () => {
  const v = elements.maxInput.valueAsNumber;
  if (isNaN(v) || v < 0) return alert("Max Cycle Time moet ≥ 0 zijn");
  sbrSocket.emit("sbr_set_cycle_time_max", { max_minutes: v });
});
elements.maxInput.addEventListener("keydown", e => {
  if (e.key === "Enter") { elements.btnSetMax.click(); e.preventDefault(); }
});

// Heating setpoints helper
function applyHeatSetpoints() {
  const on = elements.heatOnInput.valueAsNumber;
  const off = elements.heatOffInput.valueAsNumber;
  if (isNaN(on) || isNaN(off) || off < on) {
    return alert("Voer geldige Heat ON/Off waarden in (OFF ≥ ON)");
  }
  sbrSocket.emit("sbr_set_heating_setpoints", { on_temp: on, off_temp: off });
}

elements.btnSetHeat.addEventListener("click", applyHeatSetpoints);
elements.heatOnInput.addEventListener("keydown", e => {
  if (e.key === "Enter") { applyHeatSetpoints(); e.preventDefault(); }
});
elements.heatOffInput.addEventListener("keydown", e => {
  if (e.key === "Enter") { applyHeatSetpoints(); e.preventDefault(); }
});
elements.heatOnInput.addEventListener("change", applyHeatSetpoints);
elements.heatOffInput.addEventListener("change", applyHeatSetpoints);

// Socket.io event bindings met aparte handlers
sbrSocket.on("connect", () => sbrSocket.emit("sbr_get_phase_times"));
sbrSocket.on("sbr_phase_times", handlePhaseTimes);
sbrSocket.on("sbr_status", handleStatus);
sbrSocket.on("sbr_timer", handleTimer);
sensorSocket.on("sensor_update", handleSensorUpdate);

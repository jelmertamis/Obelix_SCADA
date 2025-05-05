const sbrSocket = io("/sbr");
const sensorSocket = io("/sensors");
const phases = [
  "influent",
  "react",
  "effluent",
  "wait",
  "dose_nutrients",
  "wait_after_N",
];

const cycleTimer = document.getElementById("cycle-timer");
const btnToggle = document.getElementById("btn-toggle");
const btnReset = document.getElementById("btn-reset");
const btnSetMax = document.getElementById("btn-set-cycle-max");
const maxInput = document.getElementById("cycle-max-input");
const btnSetHeat = document.getElementById("btn-set-heat");
const heatOnInput = document.getElementById("heat-on-input");
const heatOffInput = document.getElementById("heat-off-input");
const section = document.getElementById("sbr-config-section");

const boxes = {},
  actual = {},
  target = {},
  inputs = {},
  btns = {};

let lastPhase = "influent";
let isActive = false;

function updateHighlight(currentPhase) {
  console.log("[highlight] isActive:", isActive);
  console.log("[highlight] currentPhase:", currentPhase);
  console.log("[highlight] lastPhase:", lastPhase);

  phases.forEach((p) => {
    const shouldHighlight = isActive ? p === currentPhase : p === lastPhase;
    boxes[p].classList.toggle("active", shouldHighlight);
  });

  console.log(
    "[highlight] actieve boxen:",
    [...document.querySelectorAll(".phase-box.active")].map((e) => e.id)
  );
  console.log("[highlight] section class:", section.className);
}

phases.forEach((p) => {
  boxes[p] = document.getElementById(`phase-${p}-box`);
  actual[p] = document.getElementById(`${p}-actual`);
  target[p] = document.getElementById(`${p}-target`);
  inputs[p] = document.getElementById(`${p}-input`);
  btns[p] = document.getElementById(`btn-set-${p}`);
  btns[p].addEventListener("click", () => {
    const v = inputs[p].valueAsNumber;
    console.log(`DEBUG: button for phase "${p}" clicked, value =`, v);
    if (isNaN(v) || v < 0) {
      return alert((p === "influent" ? "Level" : "Time") + " moet ≥ 0 zijn");
    }
    if (p === "influent") {
      console.log("DEBUG: emitting sbr_set_threshold:", v);
      sbrSocket.emit("sbr_set_threshold", { threshold: v });
    } else if (p === "effluent") {
      sbrSocket.emit("sbr_set_effluent_threshold", { threshold: v });
    } else {
      sbrSocket.emit("sbr_set_phase_times", { [p]: v });
    }
  });
  // **ENTER-handler voor elk veld**
  inputs[p].addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      btns[p].click();
      e.preventDefault();
    }
  });
});

btnToggle.addEventListener("click", () =>
  sbrSocket.emit("sbr_control", { action: "toggle" })
);
btnReset.addEventListener("click", () =>
  sbrSocket.emit("sbr_control", { action: "reset" })
);

// Zet nieuwe max
btnSetMax.addEventListener("click", () => {
  const v = maxInput.valueAsNumber;
  if (isNaN(v) || v < 0) return alert("Max Cycle Time moet ≥ 0 zijn");
  sbrSocket.emit("sbr_set_cycle_time_max", { max_minutes: v });
});
maxInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    btnSetMax.click();
    e.preventDefault();
  }
});

// Set heating setpoints
btnSetHeat.addEventListener("click", () => {
  const on = heatOnInput.valueAsNumber;
  const off = heatOffInput.valueAsNumber;
  if (isNaN(on) || isNaN(off) || off < on)
    return alert("Voer geldige Heat ON/Off waarden in (OFF ≤ ON)");
  sbrSocket.emit("sbr_set_heating_setpoints", { on_temp: on, off_temp: off });
});
heatOnInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    btnSetHeat.click();
    e.preventDefault();
  }
});
heatOffInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    btnSetHeat.click();
    e.preventDefault();
  }
});

sbrSocket.on("connect", () => {
  sbrSocket.emit("sbr_get_phase_times");
});

sbrSocket.on("sbr_phase_times", (data) => {
  target["influent"].textContent = data.influent_threshold;
  inputs["influent"].value = data.influent_threshold;
  target["effluent"].textContent = data.effluent_threshold;
  inputs["effluent"].value = data.effluent_threshold;

  ["react", "wait", "dose_nutrients", "wait_after_N"].forEach((p) => {
    inputs[p].value = data[`${p}_minutes`];
    target[p].textContent = data[`${p}_seconds`];
  });
  maxInput.value = data.cycle_time_max_minutes;
  document.getElementById("cycle-max-text").textContent =
    data.cycle_time_max_minutes;

  document.getElementById("heat-on-text").textContent = data.heating_on_temp;
  document.getElementById("heat-off-text").textContent = data.heating_off_temp;
  heatOnInput.value = data.heating_on_temp;
  heatOffInput.value = data.heating_off_temp;
});

sbrSocket.on("sbr_status", (data) => {
  isActive = data.active;
  btnToggle.textContent = isActive ? "Stop Cycle" : "Start Cycle";
  section.classList.toggle("paused", !isActive);
  console.log("[status] section classes:", section.className);

  if (data.phase) {
    lastPhase = data.phase;
  }
  phases.forEach((p) => {
    if (p === "influent" || p === "effluent") {
      //actual[p].textContent =
      //data.actual_level != null
      //  ? data.actual_level.toFixed(2)
      //  : '';
    } else if (p === data.phase) {
      actual[p].textContent = String(data.phase_elapsed);
    } else {
      actual[p].textContent = "";
    }
  });
  updateHighlight(data.phase);
});

sbrSocket.on("sbr_timer", (data) => {
  const m = String(Math.floor(data.timer / 60)).padStart(2, "0"),
    s = String(data.timer % 60).padStart(2, "0");
  cycleTimer.textContent = `Cyclus: ${m}:${s}`;

  updateHighlight(data.phase);

  phases.forEach((p) => {
    if (p === "influent" || p === "effluent") {
      //actual[p].textContent =
      //data.actual_level != null
      //  ? data.actual_level.toFixed(2)
      //  : '';
    } else if (p === data.phase) {
      actual[p].textContent = String(data.phase_elapsed);
    } else {
      actual[p].textContent = "";
    }
  });

  if (data.phase_target !== undefined) {
    target[data.phase].textContent = data.phase_target;
  }
});

sensorSocket.on("sensor_update", (readings) => {
  const lvl = readings.find((r) => r.slave_id === 5 && r.channel === 0);
  if (lvl) {
    actual["influent"].textContent = lvl.value.toFixed(1);
    actual["effluent"].textContent = lvl.value.toFixed(1);
  }
});

// static/js/pulse-pause-modal.js
console.log('🛠️ Pulse-pause-modal script geladen');

const pulseModal = document.getElementById('pulse-pause-modal');
const pulseBtnOpen = document.getElementById('pulse-pause-open');
const pulseBtnClose = document.getElementById('pulse-pause-close');
const pulseForm = document.getElementById('pulse-pause-form');

if (!pulseModal || !pulseBtnOpen || !pulseBtnClose || !pulseForm) {
  console.error('❌ Pulse-pause-modal elementen niet gevonden.');
}

console.log({ pulseModal, pulseBtnOpen, pulseBtnClose, pulseForm });

// Dummy-gegevens (alleen voor influent)
const dummySettings = {
  influent: { pulse: 10.0, pause: 20.0 }
};

// Open modal en vul met dummy-gegevens
pulseBtnOpen.addEventListener('click', () => {
  console.log('🛠️ Open pulse-pause-modal');
  const tr = pulseForm.querySelector(`tr[data-phase="influent"]`);
  if (tr) {
    const cfg = dummySettings.influent;
    tr.querySelector(`#influent_pulse_current`).textContent = cfg.pulse.toFixed(1);
    tr.querySelector(`#influent_pause_current`).textContent = cfg.pause.toFixed(1);
    tr.querySelector(`[name="influent_pulse"]`).value = cfg.pulse.toFixed(1);
    tr.querySelector(`[name="influent_pause"]`).value = cfg.pause.toFixed(1);
  }
  pulseModal.style.display = 'flex';
});

// Sluit modal alleen via X of klik buiten
pulseBtnClose.addEventListener('click', () => pulseModal.style.display = 'none');
window.addEventListener('click', e => {
  if (e.target === pulseModal) pulseModal.style.display = 'none';
});

// Submit-handler: log gegevens, modal blijft open
pulseForm.addEventListener('submit', e => {
  e.preventDefault();
  const data = {};
  const tr = pulseForm.querySelector(`tr[data-phase="influent"]`);
  if (tr) {
    const phase = tr.dataset.phase;
    const pulseInput = tr.querySelector(`[name="${phase}_pulse"]`);
    const pauseInput = tr.querySelector(`[name="${phase}_pause"]`);
    const pulse = parseFloat(pulseInput.value);
    const pause = parseFloat(pauseInput.value);
    
    // Reset validatiestijl
    pulseInput.classList.remove('invalid');
    pauseInput.classList.remove('invalid');
    
    if (isNaN(pulse) || pulse < 0 || isNaN(pause) || pause < 0) {
      console.warn(`Ongeldige invoer voor ${phase}`);
      if (isNaN(pulse) || pulse < 0) pulseInput.classList.add('invalid');
      if (isNaN(pause) || pause < 0) pauseInput.classList.add('invalid');
      return;
    }
    data[phase] = { pulse, pause };
    // Update ingestelde waarden
    tr.querySelector(`#${phase}_pulse_current`).textContent = pulse.toFixed(1);
    tr.querySelector(`#${phase}_pause_current`).textContent = pause.toFixed(1);
  }
  if (Object.keys(data).length > 0) {
    console.log('🔄 Puls-pauze instellingen opgeslagen:', data);
    // Toekomstig: sbrSocket.emit('set_pulse_pause_settings', data);
  }
});
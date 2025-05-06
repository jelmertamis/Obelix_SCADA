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

// Open modal en vraag huidige instellingen
pulseBtnOpen.addEventListener('click', () => {
  console.log('🛠️ Open pulse-pause-modal, vraag settings op');
  sbrSocket.emit(SBR_CONFIG.events.getPulsePauseSettings);
  pulseModal.style.display = 'flex';
});

// Sluit modal alleen via X of klik buiten
pulseBtnClose.addEventListener('click', () => pulseModal.style.display = 'none');
window.addEventListener('click', e => {
  if (e.target === pulseModal) pulseModal.style.display = 'none';
});

// Vul inputs en "huidig" spans bij binnenkomst van settings
sbrSocket.on(SBR_CONFIG.events.pulsePauseSettings, settings => {
  console.log('🛠️ Ingeladen puls-pauze instellingen:', settings);
  const tr = pulseForm.querySelector(`tr[data-phase="influent"]`);
  if (tr) {
    const cfg = settings.influent;
    tr.querySelector(`#influent_pulse_current`).textContent = cfg.pulse.toFixed(1);
    tr.querySelector(`#influent_pause_current`).textContent = cfg.pause.toFixed(1);
    tr.querySelector(`[name="influent_pulse"]`).value = cfg.pulse.toFixed(1);
    tr.querySelector(`[name="influent_pause"]`).value = cfg.pause.toFixed(1);
  }
});

// Submit-handler: verzamel en emit zonder modal te sluiten
pulseForm.addEventListener('submit', e => {
  e.preventDefault();
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
      alert('Puls en pauze moeten ≥ 0 zijn');
      return;
    }
    const data = {
      influent: { pulse, pause }
    };
    console.log('🔄 Verstuur puls-pauze instellingen:', data);
    sbrSocket.emit(SBR_CONFIG.events.setPulsePauseSettings, data);
  }
});

// Server bevestiging: live bijwerken
sbrSocket.on(SBR_CONFIG.events.pulsePauseUpdated, settings => {
  console.log('✅ Puls-pauze instelling opgeslagen:', settings);
  const tr = pulseForm.querySelector(`tr[data-phase="influent"]`);
  if (tr) {
    const cfg = settings.influent;
    tr.querySelector(`#influent_pulse_current`).textContent = cfg.pulse.toFixed(1);
    tr.querySelector(`#influent_pause_current`).textContent = cfg.pause.toFixed(1);
  }
});

// Foutafhandeling
sbrSocket.on('sbr_error', error => {
  console.error('❌ SBR error:', error);
  alert(`Fout: ${error.error}`);
});
// static/js/compressor-modal.js

// Debug: controleer laden
console.log('🛠️ Compressor-modal script geladen');

const modal    = document.getElementById('compressor-modal');
const btnOpen  = document.getElementById('compressor-open');
const btnClose = document.getElementById('compressor-close');
const form     = document.getElementById('compressor-form');

console.log({ modal, btnOpen, btnClose, form });
if (!modal || !btnOpen || !btnClose || !form) {
  console.error('❌ Compressor-modal elementen niet gevonden.');
}

// 1) Open modal en vraag huidige instellingen:
btnOpen.addEventListener('click', () => {
  console.log('🛠️ Open compressor-modal, vraag settings op');
  sbrSocket.emit(SBR_CONFIG.events.getCompressorSettings);
  modal.style.display = 'flex';
});

// 2) Sluit modal:
btnClose.addEventListener('click', () => modal.style.display = 'none');
window.addEventListener('click', e => {
  if (e.target === modal) modal.style.display = 'none';
});

// 3) Vul inputs én “huidig” spans bij binnenkomst van settings:
sbrSocket.on(SBR_CONFIG.events.compressorSettings, settings => {
  console.log('🛠️ Ingeladen compressor-settings:', settings);
  Object.entries(settings).forEach(([phase, cfg]) => {
    const tr = form.querySelector(`tr[data-phase="${phase}"]`);
    if (!tr) return;

    // Huidig
    tr.querySelector(`#${phase}_k303_on_current`).textContent  = cfg.k303_on;
    tr.querySelector(`#${phase}_k303_pct_current`).textContent = cfg.k303_pct + '%';
    tr.querySelector(`#${phase}_k304_on_current`).textContent  = cfg.k304_on;
    tr.querySelector(`#${phase}_k304_pct_current`).textContent = cfg.k304_pct + '%';

    // Nieuw
    tr.querySelector(`[name="${phase}_k303_on"]`).value  = cfg.k303_on;
    tr.querySelector(`[name="${phase}_k303_pct"]`).value = cfg.k303_pct;
    tr.querySelector(`[name="${phase}_k304_on"]`).value  = cfg.k304_on;
    tr.querySelector(`[name="${phase}_k304_pct"]`).value = cfg.k304_pct;
  });
});

// 4) Submit-handler: verzamel en emit zonder modal te sluiten op Enter
form.addEventListener('submit', e => {
  e.preventDefault();  // modal blijft open
  const data = {};
  form.querySelectorAll('tbody tr[data-phase]').forEach(tr => {
    const phase = tr.dataset.phase;
    data[phase] = {
      k303_on: tr.querySelector(`[name="${phase}_k303_on"]`).value,
      k303_pct: +tr.querySelector(`[name="${phase}_k303_pct"]`).value,
      k304_on: tr.querySelector(`[name="${phase}_k304_on"]`).value,
      k304_pct: +tr.querySelector(`[name="${phase}_k304_pct"]`).value,
    };
  });
  console.log('🔄 Verstuur compressor-settings:', data);
  sbrSocket.emit(SBR_CONFIG.events.setCompressorSettings, data);
});

// 5) Server bevestiging: live bijwerken én modal open laten of sluiten:
sbrSocket.on(SBR_CONFIG.events.compressorUpdated, settings => {
  console.log('✅ Compressor instelling opgeslagen:', settings);
  // Update “huidig” kolommen direct:
  Object.entries(settings).forEach(([phase, cfg]) => {
    const tr = form.querySelector(`tr[data-phase="${phase}"]`);
    if (!tr) return;
    tr.querySelector(`#${phase}_k303_on_current`).textContent  = cfg.k303_on;
    tr.querySelector(`#${phase}_k303_pct_current`).textContent = cfg.k303_pct + '%';
    tr.querySelector(`#${phase}_k304_on_current`).textContent  = cfg.k304_on;
    tr.querySelector(`#${phase}_k304_pct_current`).textContent = cfg.k304_pct + '%';
  });
  // Optioneel: sluit modal als je dat wél wilt:
  // modal.style.display = 'none';
});

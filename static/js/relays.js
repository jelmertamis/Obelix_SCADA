// static/js/relays.js

document.addEventListener('DOMContentLoaded', () => {
    const relaySocket = io('/relays');
    const r302Socket  = io('/r302');
    const container   = document.getElementById('relaysContainer');
    const popup       = document.getElementById('mode-popup');
    const R302_UNIT   = 0;  // pas aan indien jouw R302-unit een andere index heeft
  
    // Houd per unit/coils de gekozen mode bij
    const modesMap = {};
  
    // Verberg de mode-popup
    function hidePopup() {
      popup.style.display = 'none';
    }
  
    // Laat de mode-popup onder de geklikte knop zien
    function showPopup(btn, unitIdx, coilIdx) {
      popup.dataset.unitIdx = unitIdx;
      popup.dataset.coilIdx = coilIdx;
      const rect = btn.getBoundingClientRect();
      popup.style.top  = `${rect.bottom + window.scrollY}px`;
      popup.style.left = `${rect.left + window.scrollX}px`;
      popup.style.display = 'block';
    }
  
    // Afhandelen keuze uit de popup
    function onPopupChoice(e) {
      const unitIdx = Number(popup.dataset.unitIdx);
      const coilIdx = Number(popup.dataset.coilIdx);
      let mode;
      if (e.target.classList.contains('manual-on'))      mode = 'MANUAL_ON';
      else if (e.target.classList.contains('manual-off')) mode = 'MANUAL_OFF';
      else                                               mode = 'AUTO';
  
      // Sla mode lokaal op
      modesMap[unitIdx] = modesMap[unitIdx] || [];
      modesMap[unitIdx][coilIdx] = mode;
  
      // Stuur naar server
      if (unitIdx === R302_UNIT) {
        r302Socket.emit('set_mode', { coil: coilIdx, mode });
        if (mode !== 'AUTO') {
          relaySocket.emit('toggle_relay', {
            unit_idx: unitIdx,
            coil_idx: coilIdx,
            state: mode === 'MANUAL_ON' ? 'ON' : 'OFF'
          });
        }
      } else {
        relaySocket.emit('toggle_relay', {
          unit_idx: unitIdx,
          coil_idx: coilIdx,
          state: mode === 'MANUAL_ON' ? 'ON' : 'OFF'
        });
      }
  
      // Direct UI bijwerken
      updateButton(unitIdx, coilIdx, mode === 'MANUAL_ON', mode);
      hidePopup();
      e.stopPropagation();
    }
  
    // Functie om één button te updaten (kleur + tekst)
    function updateButton(unitIdx, coilIdx, physicalOn, mode) {
      const btn = container.querySelector(
        `.relay-button-wrapper[data-unit-idx="${unitIdx}"][data-coil-idx="${coilIdx}"] .onoff-button`
      );
      if (!btn) return;
  
      // Reset alle klassen
      btn.className = 'onoff-button';
      btn.classList.remove('loading');
  
      // Zet juiste class en tekst (met <br> voor regelwisseling)
      if (mode === 'AUTO') {
        if (physicalOn) {
          btn.classList.add('auto-on');
          btn.innerHTML = 'Auto<br>ON';
        } else {
          btn.classList.add('auto-off');
          btn.innerHTML = 'Auto<br>OFF';
        }
      } else if (mode === 'MANUAL_ON') {
        btn.classList.add('on');
        btn.innerHTML = 'Manual<br>ON';
      } else if (mode === 'MANUAL_OFF') {
        btn.classList.add('off');
        btn.innerHTML = 'Manual<br>OFF';
      } else {
        // fallback: gewoon fysieke status
        if (physicalOn) {
          btn.classList.add('on');
          btn.innerHTML = 'ON';
        } else {
          btn.classList.add('off');
          btn.innerHTML = 'OFF';
        }
      }
    }
  
    // Init: alle relais ophalen en tonen
    relaySocket.on('init_relays', units => {
      units.forEach(u => {
        modesMap[u.idx] = Array.isArray(u.modes) ? u.modes.slice() : [];
        u.states.forEach((isOn, coilIdx) => {
          const mode = modesMap[u.idx][coilIdx];
          updateButton(u.idx, coilIdx, isOn, mode);
        });
      });
    });
  
    // Update bij enkel toggle-event
    relaySocket.on('relay_toggled', data => {
      const { unit_idx, coil_idx, state } = data;
      const isOn = (state === 'ON');
      const mode = modesMap[unit_idx]?.[coil_idx];
      updateButton(unit_idx, coil_idx, isOn, mode);
    });
  
    // Sync R302-modi en fysieke toestand
    r302Socket.on('r302_update', status => {
      Object.entries(status).forEach(([coil, info]) => {
        const c = Number(coil);
        modesMap[R302_UNIT][c] = info.mode;
        updateButton(R302_UNIT, c, info.physical, info.mode);
      });
    });
  
    // Klik op een status-knop opent de popup
    container.addEventListener('click', e => {
      const btn = e.target.closest('.onoff-button');
      if (!btn) return;
      e.stopPropagation();
      const wrap = btn.closest('.relay-button-wrapper');
      const ui   = Number(wrap.dataset.unitIdx);
      const ci   = Number(wrap.dataset.coilIdx);
      showPopup(btn, ui, ci);
    });
  
    // Klik buiten sluit de popup
    document.addEventListener('click', hidePopup);
  
    // Bind de keuze-buttons in de popup
    popup.querySelector('.manual-on').addEventListener('click', onPopupChoice);
    popup.querySelector('.manual-off').addEventListener('click', onPopupChoice);
    popup.querySelector('.auto').addEventListener('click', onPopupChoice);
  });
  
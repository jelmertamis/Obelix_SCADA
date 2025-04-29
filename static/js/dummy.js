// static/js/dummy.js
// Beheert de dummy sensor simulator: ophalen en instellen van dummy-waarden

document.addEventListener('DOMContentLoaded', () => {
    const tbody = document.getElementById('dummyBody');
    const units = window.DUMMY_UNITS || [];
  
    // Laden en weergeven van huidige dummy-waarden
    async function loadDummyValues() {
      try {
        const resp = await fetch('/api/dummy_values');
        const data = await resp.json();
        tbody.innerHTML = '';
        data.forEach(item => {
          const unit = units.find(u => u.idx === item.unit_index);
          const unitName = unit ? unit.name : `Unit ${item.unit_index}`;
          const slaveId = unit ? unit.slave_id : '';
          const value = item.value != null ? item.value : '';
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${unitName}</td>
            <td>${slaveId}</td>
            <td>${item.channel}</td>
            <td>
              <input type="number" step="0.1" id="val-${item.unit_index}-${item.channel}" value="${value}">
            </td>
            <td>
              <button data-unit="${item.unit_index}" data-channel="${item.channel}" class="save-btn">Save</button>
            </td>
          `;
          tbody.appendChild(tr);
        });
      } catch (err) {
        console.error('Fout bij laden dummy waarden:', err);
      }
    }
  
    // Opslaan van een enkele dummy-waarde
    async function saveDummyValue(unitIndex, channel, value) {
      try {
        const resp = await fetch('/api/dummy_value', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({unit_index: unitIndex, channel, value})
        });
        if (!resp.ok) throw new Error(`Status ${resp.status}`);
        console.log(`Dummy waarde ingesteld voor unit ${unitIndex} kanaal ${channel}: ${value}`);
      } catch (err) {
        console.error('Fout bij opslaan dummy waarde:', err);
      }
    }
  
    // Event delegatie voor Save-buttons
    tbody.addEventListener('click', e => {
      if (!e.target.classList.contains('save-btn')) return;
      const btn = e.target;
      const unitIndex = parseInt(btn.dataset.unit, 10);
      const channel = parseInt(btn.dataset.channel, 10);
      const input = document.getElementById(`val-${unitIndex}-${channel}`);
      const val = parseFloat(input.value);
      if (isNaN(val)) {
        alert('Voer een geldig getal in.');
        return;
      }
      saveDummyValue(unitIndex, channel, val);
    });
  
    loadDummyValues();
  });
  
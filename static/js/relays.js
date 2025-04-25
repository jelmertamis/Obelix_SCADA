// static/js/relays.js
document.addEventListener('DOMContentLoaded', () => {
    const socket = io('/relays');
    const container = document.getElementById('relaysContainer');

    socket.on('init_relays', units => {
        units.forEach(u => {
            u.states.forEach((state, coilIdx) => {
                const btn = container.querySelector(
                    `.onoff-button[data-unit-idx="${u.idx}"][data-coil-idx="${coilIdx}"]`
                );
                btn.classList.remove('loading');
                btn.classList.toggle('on', state);
                btn.classList.toggle('off', !state);
                btn.textContent = state ? 'ON' : 'OFF';
            });
        });
    });

    socket.on('relay_toggled', data => {
        const { unit_idx, coil_idx, state } = data;
        const btn = container.querySelector(
            `.onoff-button[data-unit-idx="${unit_idx}"][data-coil-idx="${coil_idx}"]`
        );
        btn.classList.toggle('on', state === 'ON');
        btn.classList.toggle('off', state === 'OFF');
        btn.textContent = state;
    });

    container.addEventListener('click', e => {
        if (!e.target.matches('.onoff-button')) return;
        const btn = e.target;
        const unitIdx = Number(btn.dataset.unitIdx);
        const coilIdx = Number(btn.dataset.coilIdx);
        const newState = btn.classList.contains('on') ? 'OFF' : 'ON';
        socket.emit('toggle_relay', {
            unit_idx: unitIdx,
            coil_idx: coilIdx,
            state: newState
        });
    });

    socket.on('relay_error', err => {
        console.error('Relay error:', err.error);
    });
});
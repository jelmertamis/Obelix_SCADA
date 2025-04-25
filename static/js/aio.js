// static/js/aio.js
const socket = io('/aio');
const body = document.getElementById('aioBody');

// Init: rijen tekenen
socket.on('aio_init', rows => {
    body.innerHTML = '';
    rows.forEach(r => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${r.channel}</td>
            <td>${r.raw_out}</td>
            <td>${r.phys_out}</td>
            <td>${r.percent_out ?? '—'}</td>
            <td>
                <input type="number" id="in${r.channel}" value="${r.percent_out ?? ''}" step="0.1">
                <button onclick="setPct(${r.channel})">Set</button>
            </td>
        `;
        body.appendChild(tr);
    });
});

// Update na set
socket.on('aio_updated', upd => {
    const tr = body.querySelectorAll('tr')[upd.channel];
    tr.children[1].textContent = upd.raw_out;
    tr.children[2].textContent = upd.phys_out;
    tr.children[3].textContent = upd.percent_out;
    document.getElementById(`in${upd.channel}`).value = upd.percent_out;
});

function setPct(ch) {
    const val = document.getElementById(`in${ch}`).value;
    socket.emit('aio_set', { channel: ch, percent: val });
}
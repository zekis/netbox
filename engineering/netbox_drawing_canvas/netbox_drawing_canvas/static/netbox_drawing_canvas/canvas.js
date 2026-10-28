(() => {
  'use strict';
  const app = document.getElementById('drawing-app');
  const canvas = document.getElementById('canvas');
  const world = document.getElementById('canvas-world');
  const saveButton = document.getElementById('save-scene');
  const status = document.getElementById('save-status');
  const state = document.getElementById('drawing-state');
  const error = document.getElementById('drawing-error');
  const editable = app.dataset.editable === 'true';
  const names = new Map();
  let scene, revision, dirty = false, busy = false, generation = 0, selected = null;
  let zoom = 1, pan = {x: 40, y: 40}, gesture = null;
  const key = item => `${item.kind}:${item.object_id ?? item.id}`;
  function appearanceId() {
    // randomUUID requires HTTPS/localhost; private HTTP previews still provide getRandomValues.
    if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  function report(message) { error.textContent = message; error.hidden = !message; }
  function refreshStatus() {
    status.textContent = busy ? 'Saving…' : dirty ? 'Unsaved changes' : `Saved · revision ${revision}${editable ? '' : ' · read only'}`;
    saveButton.disabled = !editable || !dirty || busy;
  }
  function changed() { dirty = true; generation++; refreshStatus(); }
  async function request(url, options = {}) {
    const response = await fetch(url, {credentials: 'same-origin', ...options});
    let data;
    try { data = await response.json(); } catch { throw new Error('Request failed. Check your login and reload.'); }
    if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
    return data;
  }
  function transform() { world.style.transform = `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`; }
  function point(event) {
    const box = canvas.getBoundingClientRect();
    return {x: event.clientX - box.left, y: event.clientY - box.top};
  }
  function draw() {
    world.replaceChildren();
    for (const item of scene.appearances) {
      const node = document.createElement('button');
      node.type = 'button'; node.className = `appearance ${item.kind}${selected === item.id ? ' selected' : ''}`;
      node.dataset.id = item.id; node.style.left = `${item.x}px`; node.style.top = `${item.y}px`;
      const kind = document.createElement('small'); kind.textContent = `${item.kind.toUpperCase()} · #${item.object_id}`;
      const title = document.createElement('strong'); title.textContent = names.get(key(item)) || `Loading ${item.kind}…`;
      node.append(kind, title);
      node.addEventListener('click', () => select(item));
      world.append(node);
    }
  }
  async function select(item) {
    selected = item.id;
    world.querySelectorAll('.appearance').forEach(node => node.classList.toggle('selected', node.dataset.id === selected));
    const panel = document.getElementById('properties');
    const heading = document.createElement('h2'); heading.textContent = 'Properties';
    const label = document.createElement('p'); label.textContent = `${item.kind} #${item.object_id}`;
    const identifier = document.createElement('p'); identifier.textContent = `Appearance ${item.id}`;
    panel.replaceChildren(heading, label, identifier);
    try {
      const data = await request(`${app.dataset.equipmentUrl}?kind=${item.kind}&object_id=${item.object_id}`);
      if (selected !== item.id) return;
      label.textContent = data.name;
      const link = document.createElement('a'); link.href = data.url; link.textContent = 'Open NetBox equipment details ↗';
      link.target = '_blank'; link.rel = 'noopener';
      const help = document.createElement('p');
      help.textContent = 'View the actual model, role, location, modules and ports in NetBox. Unknown information remains unknown.';
      panel.append(link, help);
      if (editable) {
        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove appearance';
        remove.onclick = () => {
          scene.appearances = scene.appearances.filter(row => row.id !== item.id);
          selected = null; panel.replaceChildren(heading); changed(); draw();
        };
        panel.append(remove);
      }
    } catch (exc) { report(exc.message); }
  }
  let searchSequence = 0;
  async function search() {
    const sequence = ++searchSequence;
    const kind = document.getElementById('equipment-kind').value;
    const q = document.getElementById('equipment-search').value;
    try {
      const data = await request(`${app.dataset.equipmentUrl}?${new URLSearchParams({kind, q})}`);
      if (sequence !== searchSequence) return;
      const list = document.getElementById('equipment-list'); list.replaceChildren();
      for (const row of data.results) {
        names.set(key(row), row.name);
        const button = document.createElement('button'); button.type = 'button'; button.textContent = `+ ${row.name}`;
        button.disabled = !editable || !scene;
        button.onclick = () => {
          const item = {id: appearanceId(), kind, object_id: row.id,
            x: Math.round((canvas.clientWidth / 2 - pan.x) / zoom - 84),
            y: Math.round((canvas.clientHeight / 2 - pan.y) / zoom - 38)};
          scene.appearances.push(item); changed(); draw(); select(item);
        };
        list.append(button);
      }
      if (!data.results.length) list.textContent = 'No matching equipment.';
      if (scene) draw();
    } catch (exc) { report(exc.message); }
  }
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !scene) return;
    const node = event.target.closest('.appearance');
    const item = node ? scene.appearances.find(row => row.id === node.dataset.id) : null;
    if (item) select(item);
    gesture = {start: point(event), pan: {...pan}, item: editable ? item : null,
      origin: item ? {x: item.x, y: item.y} : null};
    canvas.setPointerCapture(event.pointerId);
    event.preventDefault();
  });
  canvas.addEventListener('pointermove', event => {
    if (!gesture) return;
    const current = point(event), dx = current.x - gesture.start.x, dy = current.y - gesture.start.y;
    if (gesture.item) {
      const x = Math.max(-100000, Math.min(100000, Math.round(gesture.origin.x + dx / zoom)));
      const y = Math.max(-100000, Math.min(100000, Math.round(gesture.origin.y + dy / zoom)));
      if (x !== gesture.item.x || y !== gesture.item.y) {
        gesture.item.x = x; gesture.item.y = y; changed();
        const node = world.querySelector(`[data-id="${gesture.item.id}"]`);
        node.style.left = `${x}px`; node.style.top = `${y}px`;
      }
    } else { pan = {x: gesture.pan.x + dx, y: gesture.pan.y + dy}; transform(); }
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(name, () => { gesture = null; });
  canvas.addEventListener('wheel', event => {
    event.preventDefault();
    const mouse = point(event), next = Math.max(.2, Math.min(3, zoom * Math.exp(-event.deltaY * .001)));
    pan = {x: mouse.x - (mouse.x - pan.x) * next / zoom, y: mouse.y - (mouse.y - pan.y) * next / zoom};
    zoom = next; transform();
  }, {passive: false});
  document.getElementById('reset-view').onclick = () => { pan = {x: 40, y: 40}; zoom = 1; transform(); };
  document.getElementById('search-equipment').onclick = search;
  document.getElementById('equipment-kind').onchange = search;
  document.getElementById('equipment-search').onkeydown = event => { if (event.key === 'Enter') search(); };
  state.onchange = changed;
  saveButton.onclick = async () => {
    if (!dirty || busy) return;
    busy = true; const savingGeneration = generation; refreshStatus(); report('');
    try {
      const data = await request(app.dataset.sceneUrl, {
        method: 'POST', headers: {'Content-Type': 'application/json',
          'X-CSRFToken': app.querySelector('[name=csrfmiddlewaretoken]').value},
        body: JSON.stringify({scene, revision, state: state.value})
      });
      revision = data.revision;
      // Edits made while the request was in flight still need another explicit save.
      dirty = generation !== savingGeneration;
    } catch (exc) { report(exc.message); }
    finally { busy = false; refreshStatus(); }
  };
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (dirty && link && link.target !== '_blank' && !confirm('Leave this sheet and discard unsaved changes?')) event.preventDefault();
  });
  (async () => {
    try {
      const data = await request(app.dataset.sceneUrl);
      scene = data.scene; revision = data.revision; state.value = data.state;
      await Promise.all([...new Map(scene.appearances.map(item => [key(item), item])).values()].map(async item => {
        const row = await request(`${app.dataset.equipmentUrl}?kind=${item.kind}&object_id=${item.object_id}`);
        names.set(key(item), row.name);
      }));
      transform(); draw(); refreshStatus(); await search();
    } catch (exc) { report(exc.message); status.textContent = 'Unable to load'; }
  })();
})();

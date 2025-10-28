const map = L.map('map').setView([-23.5505, -46.6333], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap' }).addTo(map);
const markers = new Map();
if (navigator.geolocation) {
  navigator.geolocation.getCurrentPosition(pos => {
    const { latitude, longitude } = pos.coords;
    L.circleMarker([latitude, longitude], {radius: 6}).addTo(map).bindPopup("Você está aqui");
  });
}
map.on('click', e => {
  document.getElementById('lat').value = e.latlng.lat.toFixed(6);
  document.getElementById('lng').value = e.latlng.lng.toFixed(6);
});
async function loadMarkers() {
  const res = await fetch('/api/holes?status=ativo');
  const data = await res.json();
  markers.forEach(m => map.removeLayer(m));
  markers.clear();
  data.forEach(h => {
    const m = L.marker([h.lat, h.lng]).addTo(map);
    let html = `<b>${h.title}</b><br><small>${h.kind}</small>`;
    if (h.image_url) html += `<br><img src="${h.image_url}" alt="foto" style="max-width:160px; margin-top:6px; border-radius:6px;">`;
    if (h.description) html += `<br><small>${h.description}</small>`;
    html += `<div class="mt-2 d-flex gap-2">
              <button class="btn btn-sm btn-outline-success" onclick="concluir(${h.id})">Concluir</button>
              <button class="btn btn-sm btn-outline-danger" onclick="remover(${h.id})">Remover</button>
            </div>`;
    m.bindPopup(html);
    markers.set(h.id, m);
  });
}
async function concluir(id) {
  const res = await fetch(`/api/holes/${id}/concluir`, { method: 'POST' });
  if (res.ok) {
    const m = markers.get(id);
    if (m) { map.removeLayer(m); markers.delete(id); }
  } else { alert('Falha ao concluir.'); }
}
async function remover(id) {
  if (!confirm('Remover este registro?')) return;
  const res = await fetch(`/api/holes/${id}`, { method: 'DELETE' });
  if (res.ok) {
    const m = markers.get(id);
    if (m) { map.removeLayer(m); markers.delete(id); }
  } else { alert('Falha ao remover.'); }
}
loadMarkers();
const sidebar = document.getElementById('sidebar');
document.getElementById('togglePanel').addEventListener('click', () => {
  sidebar.classList.toggle('collapsed');
});
const form = document.getElementById('regForm');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  const img = document.getElementById('imageField').files[0];
  if (img && img.size > 2 * 1024 * 1024) { alert('Imagem maior que 2 MB.'); return; }
  const res = await fetch('/api/holes', { method: 'POST', body: fd });
  if (res.ok) {
    form.reset(); document.getElementById('preview').innerHTML = '';
    sidebar.classList.add('collapsed'); loadMarkers();
  } else { const err = await res.text(); alert('Erro ao registrar: ' + err); }
});
document.getElementById('imageField').addEventListener('change', (e) => {
  const out = document.getElementById('preview'); out.innerHTML = '';
  const file = e.target.files[0]; if (!file) return;
  if (file.size > 2 * 1024 * 1024) { out.innerHTML = '<small class="text-danger">Arquivo maior que 2 MB.</small>'; return; }
  const reader = new FileReader(); reader.onload = () => { const img = new Image(); img.src = reader.result; out.appendChild(img); }; reader.readAsDataURL(file);
});
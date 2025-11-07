const MAP_CONTAINER_ID = "map";
const API_URL = "/api/holes";
const START_LAT = -23.55052;
const START_LNG = -46.633308;
const START_ZOOM = 13;

let map;
let tempArrow = null;
let userMarker = null;
let lastClickTime = 0;
let lastTouchTime = 0;
let lastTouchLatLng = null;
let markers = {};

// === Ícone azul para indicar local do registro ===
function createArrowIcon(size = 56, color = "#1565c0") {
  const svg = encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}">
      <defs>
        <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
          <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="rgba(0,0,0,0.4)"/>
        </filter>
      </defs>
      <g filter="url(#shadow)">
        <path d="M32 4 L44 28 L36 28 L36 58 L28 58 L28 28 L20 28 Z"
              fill="${color}" stroke="#fff" stroke-width="2"/>
      </g>
    </svg>
  `);

  return L.divIcon({
    html: `<img src="data:image/svg+xml;charset=utf-8,${svg}" alt="seta azul" style="display:block;">`,
    className: "leaflet-arrow-icon",
    iconSize: [size, size],
    iconAnchor: [size / 2, size - 4], // ponta exata sobre o ponto
  });
}

// === Painel lateral ===
function openPanel(scrollTo) {
  const painel = document.querySelector("#painel-registro");
  if (window.innerWidth <= 992) painel.classList.add("open");

  if (scrollTo) {
    setTimeout(() => {
      scrollTo.scrollIntoView({ behavior: "smooth", block: "center" });
      scrollTo.classList.add("border-primary", "border-2");
      setTimeout(() => scrollTo.classList.remove("border-primary", "border-2"), 2000);
    }, 300);
  }
}

function closePanel() {
  const painel = document.querySelector("#painel-registro");
  if (window.innerWidth <= 992) painel.classList.remove("open");
}

// === Quando o usuário escolhe o ponto no mapa ===
function handleChoose(latlng) {
  if (tempArrow) map.removeLayer(tempArrow);

  tempArrow = L.marker(latlng, { icon: createArrowIcon(), interactive: false }).addTo(map);

  document.querySelector("#lat").value = latlng.lat.toFixed(6);
  document.querySelector("#lng").value = latlng.lng.toFixed(6);

  openPanel(document.querySelector("#title"));
  map.panTo(latlng, { animate: true });
}

// === Inicializa o mapa ===
function initMap() {
  map = L.map(MAP_CONTAINER_ID, {
    center: [START_LAT, START_LNG],
    zoom: START_ZOOM,
    doubleClickZoom: false,
  });

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
  }).addTo(map);

  locateUser();
  loadHoles();

  // Eventos de clique / toque
  map.on("dblclick", (e) => handleChoose(e.latlng));
  map.on("click", (e) => {
    const now = Date.now();
    if (now - lastClickTime < 300) handleChoose(e.latlng);
    lastClickTime = now;
  });
  map.on("touchstart", (e) => {
    const t = Date.now();
    const touch = e.originalEvent.touches[0];
    const latlng = map.mouseEventToLatLng(touch);
    const withinTime = t - lastTouchTime < 350;
    const withinDist =
      lastTouchLatLng &&
      map.latLngToLayerPoint(lastTouchLatLng).distanceTo(map.latLngToLayerPoint(latlng)) < 25;
    if (withinTime && withinDist) {
      handleChoose(latlng);
      lastTouchTime = 0;
    } else {
      lastTouchTime = t;
      lastTouchLatLng = latlng;
    }
  });
}

// === Localização do usuário (geolocalização real) ===
function locateUser() {
  if (!navigator.geolocation) return;

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      const userLatLng = L.latLng(lat, lng);

      const userIcon = L.divIcon({
        html: `<div style="width:18px;height:18px;background:#1976d2;border:2px solid #fff;border-radius:50%;box-shadow:0 0 8px rgba(0,0,0,0.3);"></div>`,
        className: "",
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });

      if (userMarker) map.removeLayer(userMarker);
      userMarker = L.marker(userLatLng, { icon: userIcon }).addTo(map)
        .bindPopup("📍 Você está aqui")
        .openPopup();

      map.setView(userLatLng, 15);
    },
    (err) => console.warn("Geolocalização negada:", err.message),
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 }
  );
}

// === Carrega buracos existentes da API ===
async function loadHoles() {
  try {
    const res = await fetch(`${API_URL}?status=ativo`);
    if (!res.ok) return;
    const data = await res.json();
    Object.values(markers).forEach((m) => map.removeLayer(m));
    markers = {};
    data.forEach(addMarker);
  } catch (err) {
    console.error("Erro ao carregar:", err);
  }
}

// === Adiciona marcador de ocorrência (buraco registrado) ===
function addMarker(h) {
  const lat = parseFloat(h.lat);
  const lng = parseFloat(h.lng);
  if (Number.isNaN(lat) || Number.isNaN(lng)) return;

  const icon = L.divIcon({
    html: `<div style="
      width:24px;height:24px;
      background:${h.status === 'concluido' ? '#4caf50' : '#c62828'};
      border:2px solid #fff;
      border-radius:50%;
      box-shadow:0 2px 5px rgba(0,0,0,0.3);
    "></div>`,
    className: "",
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });

  const marker = L.marker([lat, lng], { icon }).addTo(map);
  markers[h.id] = marker;

  const desc = h.description ? `<p>${h.description}</p>` : "";
  const img = h.image_url
    ? `<img src="${h.image_url}" style="max-width:180px;display:block;margin-top:6px;">`
    : "";

  marker.bindPopup(`
    <div>
      <strong>${h.title}</strong><br>
      ${desc}${img}
      <hr class="my-1">
      <button class="btn btn-sm btn-success me-2" onclick="concluirHole(${h.id})">✅ Concluir</button>
      <button class="btn btn-sm btn-danger" onclick="removerHole(${h.id})">🗑️ Remover</button>
    </div>
  `);
}

// === Remover ocorrência ===
async function removerHole(id) {
  if (!confirm("Deseja remover este registro permanentemente?")) return;
  try {
    const res = await fetch(`${API_URL}/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error();
    if (markers[id]) {
      map.removeLayer(markers[id]);
      delete markers[id];
    }
  } catch {
    alert("Erro ao remover o buraco.");
  }
}

// === Concluir ocorrência (compatível com o Flask atual) ===
async function concluirHole(id) {
  if (!confirm("Marcar este buraco como concluído?")) return;

  try {
    // Envia requisição POST para o endpoint /api/holes/<id>/concluir
    const res = await fetch(`${API_URL}/${id}/concluir`, {
      method: "POST",
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error("Erro ao concluir:", res.status, errText);
      throw new Error("Falha ao marcar como concluído.");
    }

    // Remove o marcador do mapa e do cache local
    if (markers[id]) {
      map.removeLayer(markers[id]);
      delete markers[id];
    }

    alert("✅ Buraco marcado como concluído!");
  } catch (err) {
    console.error("Erro ao concluir:", err);
    alert("❌ Erro ao marcar como concluído. Verifique o console para detalhes.");
  }
}


// === Inicialização e formulário ===
document.addEventListener("DOMContentLoaded", () => {
  initMap();

  const form = document.querySelector("#form-register");
  const msg = document.querySelector("#msg");
  const btn = document.querySelector("#btn-registrar");

  btn.addEventListener("click", () => openPanel(document.querySelector("#title")));

  // Pré-visualização de imagem
  const inputImage = document.querySelector("#image");
  const previewContainer = document.querySelector("#preview-container");
  const previewImage = document.querySelector("#image-preview");

  inputImage.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (evt) => {
        previewImage.src = evt.target.result;
        previewContainer.style.display = "block";
      };
      reader.readAsDataURL(file);
    } else {
      previewContainer.style.display = "none";
      previewImage.src = "#";
    }
  });

  // Envio AJAX com validação
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const lat = document.querySelector("#lat").value.trim();
    const lng = document.querySelector("#lng").value.trim();

    if (!lat || !lng) {
      alert("⚠️ Indique no mapa o local do buraco antes de salvar.");
      return;
    }

    const formData = new FormData(form);
    formData.set("lat", lat);
    formData.set("lng", lng);

    try {
      const res = await fetch(API_URL, { method: "POST", body: formData });
      if (!res.ok) throw new Error("Erro ao enviar dados");

      msg.innerHTML = `<div class="alert alert-success mt-2">✅ Buraco registrado com sucesso!</div>`;
      form.reset();
      previewContainer.style.display = "none";
      closePanel();
      if (tempArrow) {
        map.removeLayer(tempArrow);
        tempArrow = null;
      }
      loadHoles();
    } catch (err) {
      msg.innerHTML = `<div class="alert alert-danger mt-2">❌ Falha ao registrar o buraco.</div>`;
      console.error(err);
    }
  });
});

// docs/specs/09-web-viewer.md Checkpoint 6 — these two constants are the
// only things that change when publishing for real. During development
// they point at a locally-run API (docker compose up -d + uv run uvicorn
// app.main:app --port 8000) with a key from `manage_keys.py issue`.
const API_BASE = "http://127.0.0.1:8000/v1";
const API_KEY = "4xaMRIrY1ri5FgFqbD3CRE8CsT3OOM0BQK0P7NkntEA";

// docs/DATA_SOURCES.md — Fortaleza's data bounding box, [lat, lon] pairs.
const FORTALEZA_BOUNDS = [
  [-3.87, -38.63],
  [-3.69, -38.42],
];

const ROUTE_STYLE = { color: "#1d4ed8", weight: 3 };
const LEISURE_ROUTE_STYLE = { color: "#dc2626", weight: 3 };

const SUPPORT_POINT_STYLE = {
  parking: { radius: 6, color: "#d97706", fillColor: "#f59e0b", fillOpacity: 0.9 },
  station: { radius: 6, color: "#7c3aed", fillColor: "#a78bfa", fillOpacity: 0.9 },
  rest_point: { radius: 6, color: "#059669", fillColor: "#34d399", fillOpacity: 0.9 },
};

const map = L.map("map").fitBounds(FORTALEZA_BOUNDS);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  maxZoom: 19,
}).addTo(map);

// One layerGroup per resource type — cleared and repopulated on each
// search, added/removed from the map by their checkbox (docs/specs/09,
// decision 7). All start visible, matching the checkboxes' default
// `checked` state in index.html.
const layerGroups = {
  routes: L.layerGroup().addTo(map),
  leisure_routes: L.layerGroup().addTo(map),
  parking: L.layerGroup().addTo(map),
  station: L.layerGroup().addTo(map),
  rest_point: L.layerGroup().addTo(map),
};

const searchButton = document.getElementById("search-button");
const statusEl = document.getElementById("status");
const staleHintEl = document.getElementById("stale-hint");

let requestGeneration = 0;
let lastSearchedBounds = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("status-error", isError);
}

function clearLayers() {
  Object.values(layerGroups).forEach((group) => group.clearLayers());
}

function boundsToBbox(bounds) {
  const sw = bounds.getSouthWest();
  const ne = bounds.getNorthEast();
  return `${sw.lng},${sw.lat},${ne.lng},${ne.lat}`;
}

async function fetchResource(path, bbox) {
  const url = `${API_BASE}${path}?page=1&page_size=200&bbox=${bbox}`;
  const response = await fetch(url, { headers: { "X-API-Key": API_KEY } });

  let body;
  try {
    body = await response.json();
  } catch {
    const error = new Error("Resposta inválida da API.");
    error.status = response.status;
    throw error;
  }

  if (!response.ok) {
    const error = new Error(body?.error?.message || "Erro desconhecido.");
    error.hint = body?.error?.hint;
    error.status = response.status;
    throw error;
  }

  return body;
}

function renderLineCollection(collection, style, layerGroup) {
  if (!collection.features.length) return;
  L.geoJSON(collection, { style }).addTo(layerGroup);
}

function popupContent(resourceType, name) {
  const container = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = resourceType;
  container.append(title, document.createElement("br"), document.createTextNode(name ?? ""));
  return container;
}

function renderSupportPoints(collection) {
  if (!collection.features.length) return;
  L.geoJSON(collection, {
    pointToLayer: (feature, latlng) => {
      const style = SUPPORT_POINT_STYLE[feature.properties.resource_type] || {};
      return L.circleMarker(latlng, style);
    },
    onEachFeature: (feature, layer) => {
      const props = feature.properties;
      layer.bindPopup(popupContent(props.resource_type, props.name));
    },
    filter: (feature) => feature.properties.resource_type in layerGroups,
  }).eachLayer((marker) => {
    layerGroups[marker.feature.properties.resource_type].addLayer(marker);
  });
}

function overflowMessage(label, meta) {
  if (meta.total > meta.page_size) {
    return `${label}: mostrando ${meta.page_size} de ${meta.total} — aproxime o zoom para ver mais.`;
  }
  return null;
}

function updateStaleHint() {
  const moved = lastSearchedBounds !== null && !map.getBounds().equals(lastSearchedBounds);
  staleHintEl.classList.toggle("visible", moved);
}

async function searchCurrentArea() {
  const generation = ++requestGeneration;
  const bounds = map.getBounds();
  const bbox = boundsToBbox(bounds);

  searchButton.disabled = true;
  setStatus("Buscando...");

  try {
    const [routes, leisureRoutes, supportPoints] = await Promise.all([
      fetchResource("/routes", bbox),
      fetchResource("/leisure-routes", bbox),
      fetchResource("/support-points", bbox),
    ]);

    if (generation !== requestGeneration) return; // a newer search already started

    clearLayers();
    renderLineCollection(routes, ROUTE_STYLE, layerGroups.routes);
    renderLineCollection(leisureRoutes, LEISURE_ROUTE_STYLE, layerGroups.leisure_routes);
    renderSupportPoints(supportPoints);

    lastSearchedBounds = bounds;
    updateStaleHint();

    const overflowMessages = [
      overflowMessage("Rotas", routes.meta),
      overflowMessage("Rotas de lazer", leisureRoutes.meta),
      overflowMessage("Pontos de apoio", supportPoints.meta),
    ].filter(Boolean);

    setStatus(overflowMessages.length ? overflowMessages.join(" ") : "Busca concluída.");
  } catch (error) {
    if (generation !== requestGeneration) return;

    if (error.status === 429) {
      setStatus(`${error.message}${error.hint ? " " + error.hint : ""}`, true);
    } else if (error.status === 401) {
      setStatus("Chave de API indisponível.", true);
    } else {
      setStatus("Não foi possível carregar dados agora, tente novamente.", true);
    }
  } finally {
    if (generation === requestGeneration) {
      searchButton.disabled = false;
    }
  }
}

searchButton.addEventListener("click", searchCurrentArea);
map.on("moveend", updateStaleHint);

document.querySelectorAll("#layer-toggles input[type=checkbox]").forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const group = layerGroups[checkbox.dataset.layer];
    if (checkbox.checked) {
      map.addLayer(group);
    } else {
      map.removeLayer(group);
    }
  });
});

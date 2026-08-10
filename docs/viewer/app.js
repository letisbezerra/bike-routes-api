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

// docs/specs/09-web-viewer.md's line/marker styles — values read directly
// from the Map.dc.html mockup's buildLayerGroups(), not approximated.
const ROUTE_STYLE = { color: "#3f7fb0", weight: 4, opacity: 0.9, lineCap: "round", lineJoin: "round" };
const LEISURE_ROUTE_STYLE = {
  color: "#c05a3c", weight: 4, opacity: 0.9, lineCap: "round", lineJoin: "round", dashArray: "10,8",
};

const SUPPORT_POINT_STYLE = {
  station: { radius: 7, color: "#fff", weight: 2, fillColor: "#3f9b7a", fillOpacity: 1 },
  parking: { radius: 5, color: "#fff", weight: 1.5, fillColor: "#c78a2e", fillOpacity: 1 },
  rest_point: { radius: 6, color: "#fff", weight: 2, fillColor: "#a458a0", fillOpacity: 1 },
};

// docs/specs/09-web-viewer.md — CARTO Positron (light) / Dark Matter
// (dark), replacing the raw OSM tiles rounds 1-2 used. Free, no API key.
const TILE_URL = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
};
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
  '&copy; <a href="https://carto.com/attributions">CARTO</a>';

const map = L.map("map").fitBounds(FORTALEZA_BOUNDS);

let currentTileLayer = null;

function setTileLayer(theme) {
  if (currentTileLayer) map.removeLayer(currentTileLayer);
  currentTileLayer = L.tileLayer(TILE_URL[theme], {
    attribution: TILE_ATTRIBUTION,
    maxZoom: 19,
  }).addTo(map);
}

// docs/DESIGN-SYSTEM.md's icon rule: geometric SVG, square joints on
// straight strokes, one color via currentColor — no emoji.
const MOON_ICON =
  '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M13.5 2.5a7.5 7.5 0 1 0 4 13 8.5 8.5 0 0 1-4-13z" fill="currentColor"/></svg>';
const SUN_ICON =
  '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="4" fill="currentColor"/>' +
  '<g stroke="currentColor" stroke-width="1.6" stroke-linecap="square">' +
  '<line x1="10" y1="1" x2="10" y2="3.5"/><line x1="10" y1="16.5" x2="10" y2="19"/>' +
  '<line x1="1" y1="10" x2="3.5" y2="10"/><line x1="16.5" y1="10" x2="19" y2="10"/>' +
  '<line x1="3.5" y1="3.5" x2="5.3" y2="5.3"/><line x1="14.7" y1="14.7" x2="16.5" y2="16.5"/>' +
  '<line x1="3.5" y1="16.5" x2="5.3" y2="14.7"/><line x1="14.7" y1="5.3" x2="16.5" y2="3.5"/></g></svg>';

// docs/specs/09-web-viewer.md decision 9 — light/dark toggle, no
// persistence across reloads. `data-theme` on <html> is the only thing JS
// touches; style.css's CSS custom properties do the rest. Icon shown is
// the theme a click switches TO (moon while light, sun while dark).
const themeToggle = document.getElementById("theme-toggle");

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.innerHTML = theme === "dark" ? SUN_ICON : MOON_ICON;
  setTileLayer(theme);
}

applyTheme("light");
themeToggle.addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});

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
  statusEl.title = message; // full text on hover — CSS truncates long messages
  statusEl.classList.toggle("status-error", isError);
}

function clearLayers() {
  Object.values(layerGroups).forEach((group) => group.clearLayers());
}

// /v1/routes and /v1/leisure-routes each have their own real pagination
// meta; /v1/support-points is one combined endpoint covering parking +
// station + rest_point with a single shared total, so there's no true
// per-subtype total to show for those three — the legend format reflects
// that honestly instead of showing a precise-looking number it doesn't have.
const EXACT_TOTAL_TYPES = new Set(["routes", "leisure_routes"]);
let lastMeta = {};

// docs/specs/09-web-viewer.md's legend — one live count per layer,
// reflecting what's actually visible on the map right now. Refreshed
// after every render (including an empty one, so counts go back to 0)
// and on every checkbox toggle — a layer hidden via its checkbox shows 0,
// not the count of what's loaded but not displayed (confirmed with the
// developer after live testing showed a hidden layer still listing a
// nonzero count as confusing). When more data exists than was fetched:
// "N de M" where the real total is known, "N+" where only the rendered
// count is known (see EXACT_TOTAL_TYPES above) — only shown while the
// layer is actually visible. "N+" specifically only when N > 0: for a
// shared-meta type, "the combined response was capped" doesn't mean THIS
// subtype has more hiding (the cap may have been consumed entirely by a
// different subtype) — "0+" would claim knowledge of more zero-rendered
// items existing that we don't actually have.
function updateLegendCounts() {
  document.querySelectorAll("[data-count-for]").forEach((el) => {
    const type = el.dataset.countFor;
    const group = layerGroups[type];
    const visible = map.hasLayer(group);
    const rendered = visible ? group.getLayers().length : 0;
    const meta = lastMeta[type];

    if (!visible || !meta || meta.total <= meta.page_size) {
      el.textContent = rendered;
    } else if (EXACT_TOTAL_TYPES.has(type)) {
      el.textContent = `${rendered} de ${meta.total}`;
    } else if (rendered > 0) {
      el.textContent = `${rendered}+`;
    } else {
      el.textContent = rendered;
    }
  });
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

    lastMeta = {
      routes: routes.meta,
      leisure_routes: leisureRoutes.meta,
      parking: supportPoints.meta,
      station: supportPoints.meta,
      rest_point: supportPoints.meta,
    };
    updateLegendCounts();

    lastSearchedBounds = bounds;
    updateStaleHint();

    setStatus("Busca concluída");
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

document.querySelectorAll("#layer-legend input[type=checkbox]").forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const group = layerGroups[checkbox.dataset.layer];
    if (checkbox.checked) {
      map.addLayer(group);
    } else {
      map.removeLayer(group);
    }
    updateLegendCounts();
    setStatus("");
  });
});

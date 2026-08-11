// docs/specs/09-web-viewer.md Checkpoint 6 — these two constants are the
// only things that change when publishing for real. During development
// they point at a locally-run API (docker compose up -d + uv run uvicorn
// app.main:app --port 8000) with a key from `manage_keys.py issue`.
const API_BASE = "http://127.0.0.1:8000/v1";
const API_KEY = "4xaMRIrY1ri5FgFqbD3CRE8CsT3OOM0BQK0P7NkntEA";

// Initial view — tighter than docs/DATA_SOURCES.md's full data extent
// ([-3.87,-38.63] to [-3.69,-38.42]), centered on the same point but at
// ~60% of that box's size, so the map opens already zoomed into the urban
// core instead of the widest possible frame.
const FORTALEZA_BOUNDS = [
  [-3.834, -38.588],
  [-3.726, -38.462],
];

// docs/specs/09-web-viewer.md's line/marker styles — values read directly
// from the Map.dc.html mockup's buildLayerGroups(), not approximated.
const ROUTE_BASE_STYLE = { weight: 4, opacity: 0.9, lineCap: "round", lineJoin: "round" };

// docs/DESIGN-SYSTEM.md extension — one color per Tipologia, derived from
// the mockup's single Routes color (#3f7fb0 = oklch(0.576 0.100 244)) by
// varying only lightness within that same hue/chroma, not 4 unrelated
// hues (which would compete with the other map-data categories — parking
// is already amber, rest points already purple). Darker = more physically
// protected infrastructure, lighter = less — the gradient carries real
// meaning, not an arbitrary assignment.
const ROUTE_CATEGORY_COLORS = {
  ciclovia: "#02385b",
  ciclofaixa: "#096399",
  ciclorrota: "#4d99d3",
  passeio_compartilhado: "#9ed1fb",
};

function routeStyle(feature) {
  return { ...ROUTE_BASE_STYLE, color: ROUTE_CATEGORY_COLORS[feature.properties.category] };
}

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
const neighborhoodInput = document.getElementById("neighborhood-search");
const tipologiaCheckboxes = document.querySelectorAll("#tipologia-filter input[type=checkbox]");

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

let lastTotals = {};

function checkedCategories() {
  return new Set(
    Array.from(tipologiaCheckboxes)
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => checkbox.dataset.category)
  );
}

// docs/specs/09-web-viewer.md's legend — one live count per layer,
// reflecting what's actually visible on the map right now. Refreshed
// after every render (including an empty one, so counts go back to 0)
// and on every checkbox toggle — a layer hidden via its checkbox shows 0,
// not the count of what's loaded but not displayed (confirmed with the
// developer after live testing showed a hidden layer still listing a
// nonzero count as confusing). "N de M" appears whenever more items exist
// than were rendered — every type now has a real total (routes/
// leisure_routes from their own endpoint's meta.total, the 3 support-point
// types from /v1/support-points' meta.total_by_type, added by the
// fix/support-points-pagination branch), so there's no "N+" fallback for
// an unknown total anymore. docs/specs/09's decision 19 (revised) —
// Tipologia/Bairro's scope is stated once as a fixed hint next to each
// filter, not tracked per-layer here; a layer they don't touch just keeps
// showing its normal count, same as before either filter existed.
function updateLegendCounts() {
  document.querySelectorAll("[data-count-for]").forEach((el) => {
    const type = el.dataset.countFor;
    const group = layerGroups[type];
    const visible = map.hasLayer(group);
    const rendered = visible ? group.getLayers().length : 0;
    const total = lastTotals[type];

    el.textContent =
      visible && total !== undefined && rendered < total ? `${rendered} de ${total}` : rendered;
  });
}

// docs/specs/09-web-viewer.md decision 16 — Tipologia/Bairro filter
// client-side, on data already fetched for the current search area, same
// spirit as the layer-visibility checkboxes above (one fetch, then
// interact freely). `allLayers` is the master list of every rendered
// route/station layer, independent of which ones currently sit inside
// their layerGroup — re-snapshotted after every search so a new area's
// results go through the same filter state (decision 18: filters persist
// across searches).
let allLayers = { routes: [], station: [] };

// Diacritic-insensitive: Brazilian neighborhood names carry accents
// ("Rodolfo Teófilo") that most people don't bother typing — a plain
// substring match on the raw strings silently found nothing for a
// correctly-spelled-but-unaccented query, reading as "0 results" for a
// neighborhood that obviously has data. NFD-decomposes each string (e.g.
// "ó" → "o" + a separate combining-accent codepoint) then strips the
// combining marks before comparing, so both sides normalize the same way
// regardless of which one has accents typed.
function foldAccents(text) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function matchesNeighborhood(neighborhoods, text) {
  const needle = foldAccents(text.trim().toLowerCase());
  if (!needle) return true;
  return neighborhoods.some((n) => n && foldAccents(n.toLowerCase()).includes(needle));
}

function syncMembership(group, layer, shouldBeIn) {
  const isIn = group.hasLayer(layer);
  if (shouldBeIn && !isIn) group.addLayer(layer);
  if (!shouldBeIn && isIn) group.removeLayer(layer);
}

function applyFilters() {
  const categories = checkedCategories();
  const text = neighborhoodInput.value;

  allLayers.routes.forEach((layer) => {
    const matches =
      categories.has(layer.feature.properties.category) &&
      matchesNeighborhood(layer.feature.properties.neighborhoods, text);
    syncMembership(layerGroups.routes, layer, matches);
  });

  allLayers.station.forEach((layer) => {
    const neighborhood = layer.feature.properties.neighborhood;
    const matches = matchesNeighborhood(neighborhood ? [neighborhood] : [], text);
    syncMembership(layerGroups.station, layer, matches);
  });

  updateLegendCounts();
}

// Zooms to whatever the current Bairro text actually matched (routes +
// stations already filtered by applyFilters above) — not a real
// neighborhood-boundary lookup, since the API has no geographic bairro
// data, only the name as a text field on each route/station. Debounced
// (not tied to every keystroke) so the map doesn't jump mid-typing;
// resets on each new keystroke via clearTimeout. Only fires while Bairro
// has text — clearing it leaves the view where the user last put it.
let bairroZoomTimeout = null;

function scheduleBairroZoom() {
  clearTimeout(bairroZoomTimeout);
  if (!neighborhoodInput.value.trim()) return;
  bairroZoomTimeout = setTimeout(zoomToBairroMatches, 500);
}

function zoomToBairroMatches() {
  const matchedLayers = [...layerGroups.routes.getLayers(), ...layerGroups.station.getLayers()];
  if (matchedLayers.length === 0) return;
  map.flyToBounds(L.featureGroup(matchedLayers).getBounds(), { padding: [40, 40], maxZoom: 16 });
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
  // Flattened onto layerGroup directly (one addLayer per feature), not
  // .addTo(layerGroup) — that would nest the whole L.geoJSON FeatureGroup
  // as a single child, so layerGroup.getLayers() returned one group
  // lacking its own .feature instead of N individual feature layers,
  // breaking decision 16's per-feature filtering (layer.feature was
  // undefined). Same flattening renderSupportPoints already does below.
  L.geoJSON(collection, { style }).eachLayer((layer) => layerGroup.addLayer(layer));
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
    renderLineCollection(routes, routeStyle, layerGroups.routes);
    renderLineCollection(leisureRoutes, LEISURE_ROUTE_STYLE, layerGroups.leisure_routes);
    renderSupportPoints(supportPoints);

    lastTotals = {
      routes: routes.meta.total,
      leisure_routes: leisureRoutes.meta.total,
      parking: supportPoints.meta.total_by_type.parking,
      station: supportPoints.meta.total_by_type.station,
      rest_point: supportPoints.meta.total_by_type.rest_point,
    };
    allLayers = {
      routes: layerGroups.routes.getLayers(),
      station: layerGroups.station.getLayers(),
    };
    applyFilters();

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

tipologiaCheckboxes.forEach((checkbox) => checkbox.addEventListener("change", applyFilters));
neighborhoodInput.addEventListener("input", () => {
  applyFilters();
  scheduleBairroZoom();
});

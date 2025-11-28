const wallEl = document.getElementById("wall");
const locEl = document.getElementById("location");
const lastUpdateEl = document.getElementById("last-update");
const airportInput = document.getElementById("airport-input");
const airportBtn = document.getElementById("airport-set-btn");
const metaEl = document.querySelector(".meta");

// Map airline prefixes to logo image paths (under /static/logos)
const LOGO_BY_PREFIX = {
  DAL: "/static/logos/dal.png",
  AAL: "/static/logos/aal.png",
  UAL: "/static/logos/ual.png",
  SWA: "/static/logos/swa.png",
  JBU: "/static/logos/jbu.png",
  NKS: "/static/logos/nks.png",
  FFT: "/static/logos/fft.png",
  ASA: "/static/logos/asa.png",
  RPA: "/static/logos/rpa.png",
  SKW: "/static/logos/skw.png",
  ENY: "/static/logos/eny.png",
  GJS: "/static/logos/gjs.png",
  EJA: "/static/logos/eja.png",
  EJM: "/static/logos/ejm.png",
  UPS: "/static/logos/ups.png",
  FDX: "/static/logos/fdx.png",
  JIA: "/static/logos/jia.png",
  PDT: "/static/logos/pdt.png",
  CPZ: "/static/logos/cpz.png",
  EDV: "/static/logos/edv.png",
  CJT: "/static/logos/cjt.png",
  // Add GA logo here if desired
};

console.log("[FlightWall] app.js loaded");

// ---------------------------------------------------------------------
// Client-side state: center & radius (per user/tab), persisted in storage
// ---------------------------------------------------------------------

const STORAGE_KEY_CENTER = "flightwall_center_v1";
const STORAGE_KEY_RADIUS = "flightwall_radius_nm_v1";

let currentCenterLat = null;
let currentCenterLon = null;
let currentCenterLabel = "";

// null means "no explicit value yet" so we can tell if we should use config
let currentRadiusNm = null;

let radiusLabelEl = null;
let radiusSliderEl = null;

function loadStateFromStorage() {
  try {
    const centerRaw = localStorage.getItem(STORAGE_KEY_CENTER);
    if (centerRaw) {
      const c = JSON.parse(centerRaw);
      if (typeof c.lat === "number") currentCenterLat = c.lat;
      if (typeof c.lon === "number") currentCenterLon = c.lon;
      if (typeof c.label === "string") currentCenterLabel = c.label;
    }
  } catch (e) {
    console.warn("[FlightWall] Failed to load center from storage", e);
  }

  try {
    const radiusRaw = localStorage.getItem(STORAGE_KEY_RADIUS);
    if (radiusRaw != null) {
      const r = Number(radiusRaw);
      if (!Number.isNaN(r)) currentRadiusNm = r;
    }
  } catch (e) {
    console.warn("[FlightWall] Failed to load radius from storage", e);
  }
}

function saveCenterToStorage() {
  try {
    if (
      typeof currentCenterLat === "number" &&
      typeof currentCenterLon === "number"
    ) {
      const payload = {
        lat: currentCenterLat,
        lon: currentCenterLon,
        label: currentCenterLabel || "",
      };
      localStorage.setItem(STORAGE_KEY_CENTER, JSON.stringify(payload));
    }
  } catch (e) {
    console.warn("[FlightWall] Failed to save center to storage", e);
  }
}

function saveRadiusToStorage() {
  try {
    if (typeof currentRadiusNm === "number" && !Number.isNaN(currentRadiusNm)) {
      localStorage.setItem(STORAGE_KEY_RADIUS, String(currentRadiusNm));
    }
  } catch (e) {
    console.warn("[FlightWall] Failed to save radius to storage", e);
  }
}

function updateCenterDisplay() {
  let label = currentCenterLabel;
  if (!label) {
    if (
      typeof currentCenterLat === "number" &&
      typeof currentCenterLon === "number"
    ) {
      label = `${currentCenterLat.toFixed(3)}, ${currentCenterLon.toFixed(3)}`;
    } else {
      label = "(unknown)";
    }
  }
  locEl.textContent = `Center: ${label}`;
}

function updateRadiusDisplay() {
  if (radiusLabelEl) {
    const value =
      typeof currentRadiusNm === "number" && !Number.isNaN(currentRadiusNm)
        ? Math.round(currentRadiusNm)
        : 50;
    radiusLabelEl.textContent = `Range: ${value} NM`;
  }
}

function initRadiusControls() {
  if (!metaEl) {
    console.warn("[FlightWall] .meta element not found for radius controls");
    return;
  }

  // If we still don't have a radius, default it
  if (currentRadiusNm === null || Number.isNaN(currentRadiusNm)) {
    currentRadiusNm = 50;
  }

  // Clamp into [10, 250]
  currentRadiusNm = Math.min(250, Math.max(10, Math.round(currentRadiusNm)));

  // If controls already exist, just sync and bail
  if (radiusSliderEl && radiusLabelEl) {
    radiusSliderEl.value = currentRadiusNm;
    updateRadiusDisplay();
    return;
  }

  const radiusContainer = document.createElement("div");
  radiusContainer.className = "radius-control";
  radiusContainer.style.display = "flex";
  radiusContainer.style.alignItems = "center";
  radiusContainer.style.gap = "8px";
  radiusContainer.style.marginLeft = "12px";

  radiusLabelEl = document.createElement("span");
  radiusLabelEl.id = "radius-label";
  radiusLabelEl.style.fontSize = "0.85rem";
  radiusLabelEl.style.opacity = "0.9";

  radiusSliderEl = document.createElement("input");
  radiusSliderEl.type = "range";
  radiusSliderEl.min = "10";
  radiusSliderEl.max = "250";
  radiusSliderEl.step = "5";
  radiusSliderEl.value = currentRadiusNm;
  radiusSliderEl.id = "radius-slider";

  radiusSliderEl.addEventListener("input", () => {
    const val = Number(radiusSliderEl.value);
    if (!Number.isNaN(val)) {
      currentRadiusNm = val;
      updateRadiusDisplay();
    }
  });

  radiusSliderEl.addEventListener("change", () => {
    console.log("[FlightWall] Radius changed to", currentRadiusNm, "NM");
    saveRadiusToStorage();
    refreshFlights(); // re-fetch with new radius
  });

  radiusContainer.appendChild(radiusLabelEl);
  radiusContainer.appendChild(radiusSliderEl);

  // Insert near the end of the meta row (right side)
  metaEl.appendChild(radiusContainer);

  updateRadiusDisplay();
}

async function fetchConfig() {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) {
      throw new Error("Config fetch failed");
    }
    const cfg = await res.json();
    const radiusNmFromCfg =
      typeof cfg.radius_km === "number" ? cfg.radius_km / 1.852 : null;

    // Only seed center from config if we don't already have one from storage
    if (
      currentCenterLat === null ||
      currentCenterLon === null ||
      Number.isNaN(currentCenterLat) ||
      Number.isNaN(currentCenterLon)
    ) {
      if (typeof cfg.center_lat === "number") currentCenterLat = cfg.center_lat;
      if (typeof cfg.center_lon === "number") currentCenterLon = cfg.center_lon;

      if (cfg.center_label && typeof cfg.center_label === "string") {
        currentCenterLabel = cfg.center_label;
      } else {
        currentCenterLabel = "";
      }
    }

    // Only seed radius from config if we don't already have one from storage
    if (
      (currentRadiusNm === null || Number.isNaN(currentRadiusNm)) &&
      radiusNmFromCfg !== null
    ) {
      currentRadiusNm = radiusNmFromCfg;
    }

    updateCenterDisplay();
    initRadiusControls();
  } catch (err) {
    console.error("[FlightWall] Error fetching config", err);
    locEl.textContent = "Config unavailable";
  }
}

function getPrefixFromCallsign(callsign) {
  if (!callsign || typeof callsign !== "string") return null;
  const cs = callsign.trim().toUpperCase();
  const m = cs.match(/^([A-Z]{1,3})/);
  return m ? m[1] : null;
}

function buildDisplayTitleAndAirline(f) {
  const rawCallsign =
    f && typeof f.callsign === "string" ? f.callsign.trim() : "";
  const airlineText =
    f && typeof f.airline === "string" ? f.airline.trim() : "";

  let displayTitle = rawCallsign || "UNKNOWN";

  // GA aircraft: title = callsign
  if (airlineText === "GA Aircraft") {
    return {
      displayTitle: displayTitle,
      airlineText: "",
    };
  }

  // Airline flight with recognized airline + flight number
  if (rawCallsign && airlineText) {
    const m = rawCallsign.match(/^([A-Z]+)(\d+.*)$/i);
    if (m && m[2]) {
      const flightNum = m[2].trim();
      if (flightNum) {
        displayTitle = `${airlineText} ${flightNum}`;
      }
    }
  }

  return {
    displayTitle,
    airlineText: "",
  };
}

function renderFlights(flights) {
  wallEl.innerHTML = "";

  if (!flights.length) {
    wallEl.innerHTML = `<p>No flights currently in range.</p>`;
    return;
  }

  for (const f of flights) {
    const card = document.createElement("div");
    card.className = "flight-card";

    // Normalize callsign for FlightAware link
    let callsign = "";
    if (f.callsign && typeof f.callsign === "string") {
      callsign = f.callsign.trim();
    }
    const hasCallsign = callsign !== "";
    const linkHref = hasCallsign
      ? `https://flightaware.com/live/flight/${encodeURIComponent(callsign)}`
      : null;

    const { displayTitle } = buildDisplayTitleAndAirline(f);

    // Determine airline logo
    const prefix = getPrefixFromCallsign(callsign);
    const logoUrl =
      prefix && LOGO_BY_PREFIX[prefix] ? LOGO_BY_PREFIX[prefix] : null;

    // Convert km → nautical miles
    let distNM = null;
    if (typeof f.distance_km === "number") {
      distNM = f.distance_km / 1.852;
    }

    // Build meta row with DIST FIRST
    const metaParts = [];

    if (distNM !== null) {
      metaParts.push(
        `<span style="font-weight:bold; font-size:1.1em;">Dist: ${distNM.toFixed(
          1
        )} NM</span>`
      );
    }

    if (f.aircraft_type) {
      metaParts.push(`<span>Type: ${f.aircraft_type}</span>`);
    }

    if (f.altitude_ft) {
      metaParts.push(
        `<span>Alt: ${f.altitude_ft.toLocaleString()} ft</span>`
      );
    }

    if (typeof f.bearing_deg === "number") {
      metaParts.push(`<span>Brg: ${Math.round(f.bearing_deg)}°</span>`);
    }

    if (typeof f.gs === "number") {
      metaParts.push(`<span>GS: ${Math.round(f.gs)} kt</span>`);
    }

    if (typeof f.baro_rate === "number") {
      metaParts.push(`<span>V/S: ${Math.round(f.baro_rate)} fpm</span>`);
    }

    const metaHtml = metaParts.join("");

    const innerContent = `
      <div class="flight-title">
        ${
          logoUrl
            ? `<img class="airline-logo" src="${logoUrl}" alt="${prefix} logo" />`
            : ""
        }
        <div class="callsign">${displayTitle}</div>
      </div>
      <div class="flight-meta">
        ${metaHtml}
      </div>
    `;

    if (linkHref) {
      card.innerHTML = `
        <a href="${linkHref}"
           target="_blank"
           rel="noopener noreferrer"
           style="display:block;text-decoration:none;color:inherit;">
          ${innerContent}
        </a>
      `;
    } else {
      card.innerHTML = innerContent;
    }

    wallEl.appendChild(card);
  }

  const now = new Date();
  lastUpdateEl.textContent = `Last refresh: ${now.toLocaleTimeString()}`;
}

async function refreshFlights() {
  try {
    // Make sure we have a center; if not, pull defaults
    if (currentCenterLat === null || currentCenterLon === null) {
      await fetchConfig();
    }

    const params = new URLSearchParams();

    const radiusToSend =
      typeof currentRadiusNm === "number" && !Number.isNaN(currentRadiusNm)
        ? Math.round(currentRadiusNm)
        : 50;

    params.set("radius_nm", radiusToSend);

    if (currentCenterLat !== null && currentCenterLon !== null) {
      params.set("center_lat", currentCenterLat);
      params.set("center_lon", currentCenterLon);
    }

    const url = `/api/flights?${params.toString()}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Flights fetch failed");
    const flights = await res.json();
    renderFlights(flights);
  } catch (err) {
    console.error("[FlightWall] Failed to fetch flights", err);
    wallEl.innerHTML = "<p>Unable to load flights.</p>";
  }
}

async function setCenterFromAirport() {
  const code = airportInput ? airportInput.value.trim() : "";
  if (!code) {
    console.warn("[FlightWall] No airport code entered");
    return;
  }

  console.log("[FlightWall] Setting center from airport:", code);

  try {
    const res = await fetch("/api/center/airport", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ airport: code }),
    });

    if (!res.ok) {
      const text = await res.text();
      console.error("[FlightWall] Set center failed:", res.status, text);
      alert(`Set center failed (${res.status}): ${text}`);
      return;
    }

    const data = await res.json();
    console.log("[FlightWall] Center set response:", data);

    // Update local center state from response
    if (typeof data.center_lat === "number") {
      currentCenterLat = data.center_lat;
    }
    if (typeof data.center_lon === "number") {
      currentCenterLon = data.center_lon;
    }
    if (data.center_label && typeof data.center_label === "string") {
      currentCenterLabel = data.center_label;
    } else {
      currentCenterLabel = "";
    }

    // Persist center so a manual browser refresh keeps it
    saveCenterToStorage();

    // Clear the input back to blank (placeholder-only look)
    if (airportInput) {
      airportInput.value = "";
    }

    // Update header + flights after center change
    updateCenterDisplay();
    await refreshFlights();

    lastUpdateEl.textContent = `Center set to ${code.toUpperCase()} at ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    console.error("[FlightWall] Error setting center from airport", err);
    alert("Error setting center from airport. See console for details.");
  }
}

async function init() {
  console.log("[FlightWall] init() starting");

  // Load any saved center/radius first, so config only fills in gaps
  loadStateFromStorage();

  if (airportBtn) {
    airportBtn.addEventListener("click", () => {
      setCenterFromAirport();
    });
  } else {
    console.warn("[FlightWall] airportBtn not found");
  }

  if (airportInput) {
    airportInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        setCenterFromAirport();
      }
    });
  } else {
    console.warn("[FlightWall] airportInput not found");
  }

  // Grab defaults (center + radius) only where we don't already have them
  await fetchConfig();
  await refreshFlights();
  setInterval(refreshFlights, 15000); // refresh every 15 seconds

  console.log("[FlightWall] init() complete");
}

init();

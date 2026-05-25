// PatiRota Client-Side Logic (Google Maps)

const patirotaMapRegistry = {};

function patirotaEmit(hostId, event, args) {
    const el = getElement(hostId);
    if (el && typeof el.$emit === "function") {
        el.$emit(event, args);
    }
}

function loadGoogleMapsApi() {
    const key = window.PATIROTA_GMAPS_KEY;
    if (!key) {
        return Promise.reject(new Error("GOOGLE_MAPS_API_KEY tanimli degil."));
    }
    if (window.google && window.google.maps) {
        return Promise.resolve();
    }
    if (window.__patirotaGmapsLoading) {
        return window.__patirotaGmapsLoading;
    }
    window.__patirotaGmapsLoading = new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src =
            "https://maps.googleapis.com/maps/api/js?key=" +
            encodeURIComponent(key) +
            "&libraries=geometry&v=weekly";
        script.async = true;
        script.defer = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("Google Maps API yuklenemedi."));
        document.head.appendChild(script);
    });
    return window.__patirotaGmapsLoading;
}

function patirotaEscapeHtml(text) {
    if (text == null || text === "") {
        return "";
    }
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
}

function patirotaShelterMapsDirUrl(sh, payload) {
    const lat = Number(sh.lat);
    const lng = Number(sh.lng);
    if (!patirotaIsValidLatLng(lat, lng)) {
        const fallback = (sh.address || sh.name || "").trim();
        const query = encodeURIComponent(fallback || "Turkiye");
        return `https://www.google.com/maps/search/?api=1&query=${query}`;
    }
    const dest = `${lat},${lng}`;
    let url = `https://www.google.com/maps/dir/?api=1&destination=${dest}&travelmode=driving`;
    if (
        payload &&
        payload.locationReady &&
        patirotaIsValidLatLng(payload.userLat, payload.userLon)
    ) {
        url += `&origin=${Number(payload.userLat)},${Number(payload.userLon)}`;
    }
    return url;
}

function patirotaShelterPlaceUrl(sh, payload) {
    if (
        payload &&
        payload.locationReady &&
        patirotaIsValidLatLng(sh.lat, sh.lng) &&
        patirotaIsValidLatLng(payload.userLat, payload.userLon)
    ) {
        return patirotaShelterMapsDirUrl(sh, payload);
    }
    const lat = Number(sh.lat);
    const lng = Number(sh.lng);
    if (patirotaIsValidLatLng(lat, lng)) {
        return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
    }
    const query = encodeURIComponent((sh.address || sh.name || "").trim());
    return `https://www.google.com/maps/search/?api=1&query=${query}`;
}

function patirotaShelterNavigationUrl(sh, payload) {
    return patirotaShelterMapsDirUrl(sh, payload);
}

function patirotaBuildSheltersById(shelters) {
    const byId = {};
    (shelters || []).forEach((s) => {
        byId[s.id] = s;
        byId[String(s.id)] = s;
    });
    return byId;
}

function patirotaNormalizeShelter(raw, fallback) {
    const base = fallback || {};
    return {
        id: raw.id != null ? raw.id : base.id,
        lat: raw.lat != null ? raw.lat : raw.latitude != null ? raw.latitude : base.lat,
        lng: raw.lng != null ? raw.lng : raw.longitude != null ? raw.longitude : base.lng,
        n: raw.n != null ? raw.n : base.n,
        color: raw.color || base.color,
        name: raw.name || base.name || "",
        address: raw.address || base.address || "",
        phone: raw.phone || base.phone || "",
        distanceKm: raw.distanceKm || base.distanceKm || "",
    };
}

function patirotaResolveShelter(state, payload, shelterId, fallback) {
    const key = String(shelterId);
    if (
        window.PATIROTA_SHELTER_DETAILS &&
        window.PATIROTA_SHELTER_DETAILS[key]
    ) {
        return patirotaNormalizeShelter(
            window.PATIROTA_SHELTER_DETAILS[key],
            fallback
        );
    }
    if (payload.shelterDetails && payload.shelterDetails[key]) {
        return patirotaNormalizeShelter(payload.shelterDetails[key], fallback);
    }
    if (fallback && fallback.patirotaShelterData) {
        return patirotaNormalizeShelter(fallback.patirotaShelterData, fallback);
    }
    if (state.sheltersById) {
        const hit =
            state.sheltersById[shelterId] ||
            state.sheltersById[String(shelterId)];
        if (hit) {
            return patirotaNormalizeShelter(hit, fallback);
        }
    }
    const list = payload.shelters || [];
    const fromList = list.find(
        (s) => s.id === shelterId || String(s.id) === String(shelterId)
    );
    if (fromList) {
        return patirotaNormalizeShelter(fromList, fallback);
    }
    return patirotaNormalizeShelter(fallback || {}, fallback);
}

function patirotaAddInfoLine(root, text, style) {
    const line = document.createElement("div");
    line.style.cssText = style;
    line.textContent = text;
    root.appendChild(line);
}

function patirotaShelterInfoSummaryElement(sh) {
    const root = document.createElement("div");
    root.style.cssText =
        "min-width:240px;max-width:320px;padding:10px 8px;background:#ffffff;color:#111827;font-family:system-ui,sans-serif;box-sizing:border-box;";

    const title = patirotaEscapeHtml(String(sh.n)) + ". " + patirotaEscapeHtml(sh.name);
    const distanceHtml = sh.distanceKm
        ? `<div style="font-size:12px;font-weight:700;color:#0d9488;margin-top:4px;">${patirotaEscapeHtml(sh.distanceKm)} KM</div>`
        : "";
    const addressHtml = sh.address
        ? `<div style="font-size:12px;color:#111827;margin-top:6px;line-height:1.45;">${patirotaEscapeHtml(sh.address)}</div>`
        : "";
    const phoneHtml = sh.phone
        ? `<div style="font-size:12px;color:#111827;margin-top:4px;">Tel: ${patirotaEscapeHtml(sh.phone)}</div>`
        : "";

    root.innerHTML =
        `<div style="font-size:14px;font-weight:800;color:#111827;margin-bottom:2px;">${title}</div>` +
        distanceHtml +
        addressHtml +
        phoneHtml;

    const actionBtn = document.createElement("button");
    actionBtn.type = "button";
    actionBtn.setAttribute("data-patirota-nav-btn", "1");
    actionBtn.textContent = "Yol tarifi ve navigasyon";
    actionBtn.style.cssText =
        "display:block;width:100%;margin-top:12px;padding:10px 12px;border:none;border-radius:8px;background:#0d9488;color:#ffffff;font-size:12px;font-weight:700;cursor:pointer;font-family:inherit;";
    root.appendChild(actionBtn);

    return root;
}

function patirotaFindSummaryNavButton(infoWindow, root) {
    if (root && root.querySelector) {
        const fromRoot = root.querySelector("[data-patirota-nav-btn]");
        if (fromRoot) {
            return fromRoot;
        }
    }
    if (infoWindow && typeof infoWindow.getContent === "function") {
        const content = infoWindow.getContent();
        if (content && content.querySelector) {
            const fromContent = content.querySelector("[data-patirota-nav-btn]");
            if (fromContent) {
                return fromContent;
            }
        }
    }
    return document.querySelector(".gm-style-iw-d [data-patirota-nav-btn]");
}

function patirotaBindSummaryNavButton(infoWindow, root, onShowActions) {
    if (!infoWindow || typeof onShowActions !== "function") {
        return;
    }
    const attach = () => {
        const btn = patirotaFindSummaryNavButton(infoWindow, root);
        if (!btn || btn.dataset.patirotaBound === "1") {
            return;
        }
        btn.dataset.patirotaBound = "1";
        btn.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            onShowActions();
        });
    };
    attach();
    google.maps.event.addListenerOnce(infoWindow, "domready", attach);
}

function patirotaIsMobileDevice() {
    return /Android|iPhone|iPad|iPod|Mobile|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent || ""
    );
}

function patirotaShelterInfoActionsElement(sh, payload) {
    const root = document.createElement("div");
    root.style.cssText =
        "min-width:220px;max-width:300px;padding:8px 6px;background:#ffffff;color:#111827;font-family:system-ui,sans-serif;";

    patirotaAddInfoLine(
        root,
        sh.name || "Barinak",
        "font-size:13px;font-weight:800;color:#111827;margin-bottom:8px;"
    );

    const placeLink = document.createElement("a");
    placeLink.href = patirotaShelterPlaceUrl(sh, payload);
    placeLink.target = "_blank";
    placeLink.rel = "noopener noreferrer";
    placeLink.textContent = "Google Maps ile adrese git";
    placeLink.style.cssText =
        "display:block;margin-bottom:8px;padding:10px 12px;border-radius:8px;background:#1e293b;color:#f8fafc;text-decoration:none;font-size:12px;font-weight:700;text-align:center;";
    root.appendChild(placeLink);

    const navLink = document.createElement("a");
    navLink.href = patirotaShelterNavigationUrl(sh, payload);
    navLink.target = patirotaIsMobileDevice() ? "_self" : "_blank";
    navLink.rel = "noopener noreferrer";
    navLink.textContent = "Google navigasyon ile adrese git";
    navLink.style.cssText =
        "display:block;padding:10px 12px;border-radius:8px;background:#0d9488;color:#ffffff;text-decoration:none;font-size:12px;font-weight:700;text-align:center;";
    root.appendChild(navLink);

    return root;
}

function patirotaFindMarkerByShelterId(state, shelterId) {
    const key = String(shelterId);
    for (const marker of state.shelterMarkers) {
        if (String(marker.patirotaShelterId) === key) {
            return marker;
        }
    }
    return null;
}

function patirotaOnShelterMarkerClick(hostId, marker, payload, state) {
    const detail = marker.patirotaShelterData;
    if (!detail || !state) {
        return;
    }
    const shelterId = String(marker.patirotaShelterId);
    if (!state.markerClickState) {
        state.markerClickState = { shelterId: null, phase: 0 };
    }
    const clickState = state.markerClickState;
    let phase = "info";
    if (
        String(clickState.shelterId) === shelterId &&
        clickState.phase === 1
    ) {
        phase = "actions";
        clickState.phase = 2;
    } else {
        clickState.shelterId = shelterId;
        clickState.phase = 1;
    }
    const navPayload = {
        locationReady: payload.locationReady,
        userLat: payload.userLat,
        userLon: payload.userLon,
    };
    patirotaShowShelterBalloon(hostId, detail, phase, navPayload);
}

function patirotaShowShelterBalloon(hostId, detail, phase, navPayload) {
    const state = patirotaMapRegistry[hostId];
    if (!state || !detail) {
        return;
    }
    const marker = patirotaFindMarkerByShelterId(state, detail.id);
    if (!marker) {
        return;
    }
    if (!state.infoWindow) {
        state.infoWindow = new google.maps.InfoWindow({ maxWidth: 320 });
    }
    const place = {
        id: detail.id,
        n: detail.n,
        name: detail.name || "",
        address: detail.address || "",
        phone: detail.phone || "",
        distanceKm: detail.distanceKm || "",
        lat: detail.lat,
        lng: detail.lng,
    };
    if (phase === "actions") {
        state.infoWindow.setContent(
            patirotaShelterInfoActionsElement(place, navPayload || {})
        );
        state.infoWindow.open({ map: state.map, anchor: marker });
        return;
    }

    const summaryRoot = patirotaShelterInfoSummaryElement(place);
    const showActions = () => {
        state.markerClickState = {
            shelterId: String(detail.id),
            phase: 2,
        };
        patirotaShowShelterBalloon(
            hostId,
            detail,
            "actions",
            navPayload || {}
        );
    };
    state.infoWindow.setContent(summaryRoot);
    patirotaBindSummaryNavButton(state.infoWindow, summaryRoot, showActions);
    state.infoWindow.open({ map: state.map, anchor: marker });
}

function clearPatirotaMapLayers(state) {
    if (state.infoWindow) {
        state.infoWindow.close();
    }
    state.markerClickState = { shelterId: null, phase: 0 };
    state.routePolylines.forEach((p) => p.setMap(null));
    state.routePolylines = [];
    state.shelterMarkers.forEach((m) => m.setMap(null));
    state.shelterMarkers = [];
    if (state.userAccuracyCircle) {
        state.userAccuracyCircle.setMap(null);
        state.userAccuracyCircle = null;
    }
    if (state.userCircle) {
        state.userCircle.setMap(null);
        state.userCircle = null;
    }
    if (state.userMarker) {
        state.userMarker.setMap(null);
        state.userMarker = null;
    }
}

function decodeRoutePath(routeData) {
    if (!routeData) {
        return [];
    }
    if (routeData.polyline && window.google && google.maps.geometry) {
        return google.maps.geometry.encoding.decodePath(routeData.polyline);
    }
    if (routeData.path && Array.isArray(routeData.path)) {
        return routeData.path.map((p) => ({
            lat: p[0] !== undefined ? p[0] : p.lat,
            lng: p[1] !== undefined ? p[1] : p.lng,
        }));
    }
    return [];
}

function extendBoundsFromPath(bounds, path) {
    path.forEach((p) => bounds.extend(p));
}

function patirotaIsValidLatLng(lat, lng) {
    const la = Number(lat);
    const lo = Number(lng);
    return (
        Number.isFinite(la) &&
        Number.isFinite(lo) &&
        la >= -85 &&
        la <= 85 &&
        lo >= -180 &&
        lo <= 180 &&
        !(Math.abs(la) < 0.0001 && Math.abs(lo) < 0.0001)
    );
}

function patirotaClamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function patirotaZoomFromSpan(maxDLat, maxDLon) {
    const span = Math.max(maxDLat, maxDLon, 0.0045) * 2 * 1.28;
    if (span <= 0.008) {
        return 14;
    }
    if (span <= 0.02) {
        return 13;
    }
    if (span <= 0.05) {
        return 12;
    }
    if (span <= 0.12) {
        return 11;
    }
    if (span <= 0.25) {
        return 10;
    }
    return 9;
}

function patirotaApplyUserCenteredView(map, userPos, maxDLat, maxDLon) {
    if (!patirotaIsValidLatLng(userPos.lat, userPos.lng)) {
        return;
    }
    const zoom = patirotaClamp(patirotaZoomFromSpan(maxDLat, maxDLon), 12, 14);
    map.setCenter(userPos);
    map.setZoom(zoom);
}

function patirotaMaxKmFromUser(userPos, lat, lng) {
    if (
        !userPos ||
        !window.google ||
        !google.maps ||
        !google.maps.geometry ||
        !patirotaIsValidLatLng(lat, lng)
    ) {
        return null;
    }
    const meters = google.maps.geometry.spherical.computeDistanceBetween(
        new google.maps.LatLng(userPos.lat, userPos.lng),
        new google.maps.LatLng(lat, lng)
    );
    return meters / 1000;
}

function patirotaCentroidOfPoints(points) {
    let latSum = 0;
    let lngSum = 0;
    let count = 0;
    points.forEach((p) => {
        latSum += p.lat;
        lngSum += p.lng;
        count += 1;
    });
    if (count === 0) {
        return null;
    }
    return { lat: latSum / count, lng: lngSum / count };
}

function patirotaFitUserAndNearest(
    map,
    userPos,
    targets,
    state,
    viewGen,
    minZoom,
    maxZoom
) {
    const maxPlaceKm = 35;
    const fitPoints = [userPos, userPos];

    targets.forEach((sh) => {
        if (!patirotaIsValidLatLng(sh.lat, sh.lng)) {
            return;
        }
        const km = patirotaMaxKmFromUser(userPos, sh.lat, sh.lng);
        if (km != null && km > maxPlaceKm) {
            return;
        }
        fitPoints.push({ lat: Number(sh.lat), lng: Number(sh.lng) });
    });

    if (fitPoints.length < 2) {
        map.setCenter(userPos);
        map.setZoom(14);
        return;
    }

    const centroid = patirotaCentroidOfPoints(fitPoints);
    if (!centroid) {
        map.setCenter(userPos);
        map.setZoom(14);
        return;
    }

    let maxDLat = 0.003;
    let maxDLon = 0.003;
    fitPoints.forEach((p) => {
        maxDLat = Math.max(maxDLat, Math.abs(p.lat - centroid.lat));
        maxDLon = Math.max(maxDLon, Math.abs(p.lng - centroid.lng));
    });
    maxDLat = patirotaClamp(maxDLat * 1.45, 0.008, 0.2);
    maxDLon = patirotaClamp(maxDLon * 1.45, 0.008, 0.26);

    const fitBounds = new google.maps.LatLngBounds(
        { lat: centroid.lat - maxDLat, lng: centroid.lng - maxDLon },
        { lat: centroid.lat + maxDLat, lng: centroid.lng + maxDLon }
    );

    map.fitBounds(fitBounds, {
        top: 40,
        right: 56,
        bottom: 96,
        left: 56,
    });

    google.maps.event.addListenerOnce(map, "bounds_changed", () => {
        if (state.mapViewGeneration !== viewGen) {
            return;
        }
        let zoom = map.getZoom();
        if (zoom > maxZoom) {
            map.setZoom(maxZoom);
            zoom = maxZoom;
        }
        if (zoom < minZoom) {
            map.setZoom(minZoom);
        }
        map.setCenter(centroid);
    });
}

function patirotaRefreshMapView(map) {
    if (!map || !window.google || !google.maps) {
        return;
    }
    google.maps.event.trigger(map, "resize");
    const center = map.getCenter();
    if (center) {
        map.setCenter(center);
    }
}

function patirotaScheduleMapRefresh(map) {
    patirotaRefreshMapView(map);
    setTimeout(() => patirotaRefreshMapView(map), 100);
    setTimeout(() => patirotaRefreshMapView(map), 400);
}

async function initPatirotaGoogleMap(hostId, options) {
    await loadGoogleMapsApi();
    const host = getElement(hostId);
    if (!host) {
        throw new Error("Harita kapsayicisi bulunamadi.");
    }
    let mapDiv = host.querySelector(".patirota-google-map-inner");
    if (!mapDiv) {
        mapDiv = document.createElement("div");
        mapDiv.className = "patirota-google-map-inner";
        mapDiv.style.width = "100%";
        mapDiv.style.height = "100%";
        host.innerHTML = "";
        host.appendChild(mapDiv);
    }
    const map = new google.maps.Map(mapDiv, {
        center: { lat: options.lat, lng: options.lng },
        zoom: options.zoom || 13,
        mapTypeId: "hybrid",
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
    });
    if (!patirotaMapRegistry[hostId]) {
        map.addListener("click", (e) => {
            patirotaEmit(hostId, "map-click", {
                latlng: { lat: e.latLng.lat(), lng: e.latLng.lng() },
            });
        });
    }
    patirotaMapRegistry[hostId] = {
        map,
        userCircle: null,
        userMarker: null,
        userAccuracyCircle: null,
        routePolylines: [],
        shelterMarkers: [],
        infoWindow: null,
        markerClickState: { shelterId: null, phase: 0 },
    };
    google.maps.event.addListenerOnce(map, "idle", () => {
        patirotaRefreshMapView(map);
    });
    patirotaScheduleMapRefresh(map);
    map.addListener("click", () => {
        const st = patirotaMapRegistry[hostId];
        if (!st) {
            return;
        }
        if (st.infoWindow) {
            st.infoWindow.close();
        }
        st.markerClickState = { shelterId: null, phase: 0 };
    });
    return true;
}

async function updatePatirotaGoogleMap(hostId, payload) {
    if (!window.PATIROTA_GMAPS_KEY) {
        throw new Error("GOOGLE_MAPS_API_KEY tanimli degil.");
    }
    if (!patirotaMapRegistry[hostId]) {
        await initPatirotaGoogleMap(hostId, {
            lat: payload.defaultLat || 41.2815,
            lng: payload.defaultLng || 28.0015,
            zoom: 13,
        });
    }
    const state = patirotaMapRegistry[hostId];
    const map = state.map;
    state.mapViewGeneration = (state.mapViewGeneration || 0) + 1;
    const viewGen = state.mapViewGeneration;
    clearPatirotaMapLayers(state);

    const bounds = new google.maps.LatLngBounds();
    let boundsPointCount = 0;

    function trackBounds(pos) {
        bounds.extend(pos);
        boundsPointCount += 1;
    }

    if (
        payload.locationReady &&
        patirotaIsValidLatLng(payload.userLat, payload.userLon)
    ) {
        const userPos = {
            lat: Number(payload.userLat),
            lng: Number(payload.userLon),
        };
        state.lastUserPos = userPos;
        const accuracyM = payload.accuracyM;
        if (accuracyM != null && !Number.isNaN(Number(accuracyM))) {
            const radius = Math.min(Number(accuracyM), 80);
            state.userAccuracyCircle = new google.maps.Circle({
                center: userPos,
                radius,
                map,
                strokeColor: "#ef4444",
                strokeOpacity: 0.5,
                strokeWeight: 2,
                fillColor: "#ef4444",
                fillOpacity: 0.14,
            });
        }
        state.userCircle = new google.maps.Circle({
            center: userPos,
            radius: 18,
            map,
            strokeColor: "#ef4444",
            strokeOpacity: 0.55,
            strokeWeight: 2,
            fillColor: "#ef4444",
            fillOpacity: 0.22,
        });
        state.userMarker = new google.maps.Marker({
            position: userPos,
            map,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                fillColor: "#ef4444",
                fillOpacity: 0.85,
                strokeColor: "#b91c1c",
                strokeWeight: 3,
                scale: 10,
            },
            zIndex: 1000,
        });
        trackBounds(userPos);
    }

    const shelters = payload.shelters || [];
    const routes = payload.routes || {};
    if (payload.shelterDetails) {
        window.PATIROTA_SHELTER_DETAILS = payload.shelterDetails;
    }
    state.sheltersById = patirotaBuildSheltersById(shelters);

    if (payload.locationReady && shelters.length > 0) {
        shelters.forEach((sh) => {
            const routeKey = String(sh.id);
            const routeData = routes[routeKey] || routes[sh.id];
            const path = decodeRoutePath(routeData);
            const color = sh.color || (routeData && routeData.color) || "#3b82f6";

            if (path.length > 0) {
                const polyline = new google.maps.Polyline({
                    path,
                    map,
                    strokeColor: color,
                    strokeOpacity: 1,
                    strokeWeight: 10,
                    geodesic: true,
                });
                state.routePolylines.push(polyline);
            }

            const shelterPos = { lat: sh.lat, lng: sh.lng };
            const marker = new google.maps.Marker({
                position: shelterPos,
                map,
                label: {
                    text: String(sh.n),
                    color: "#ffffff",
                    fontWeight: "bold",
                    fontSize: "12px",
                },
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    fillColor: color,
                    fillOpacity: 1,
                    strokeColor: "#ffffff",
                    strokeWeight: 2,
                    scale: 14,
                },
                zIndex: 500 + Number(sh.n || 0),
            });
            marker.patirotaShelterId = sh.id;
            const detailKey = String(sh.id);
            marker.patirotaShelterData =
                (window.PATIROTA_SHELTER_DETAILS &&
                    window.PATIROTA_SHELTER_DETAILS[detailKey]) ||
                (payload.shelterDetails && payload.shelterDetails[detailKey]) ||
                {
                    id: sh.id,
                    n: sh.n,
                    name: sh.name || "",
                    address: sh.address || "",
                    phone: sh.phone || "",
                    distanceKm: sh.distanceKm || "",
                    lat: sh.lat,
                    lng: sh.lng,
                };
            marker.addListener("click", () => {
                patirotaOnShelterMarkerClick(hostId, marker, payload, state);
                patirotaEmit(hostId, "shelter-marker-click", {
                    shelterId: sh.id,
                });
            });
            state.shelterMarkers.push(marker);
            trackBounds(shelterPos);
        });
    }

    const shouldFit =
        payload.fitMap === true || payload.zoomToShelterId != null;

    if (shouldFit) {
        const userPos = patirotaIsValidLatLng(payload.userLat, payload.userLon)
            ? { lat: Number(payload.userLat), lng: Number(payload.userLon) }
            : null;
        const routeLimit = payload.routeLimit || 3;
        let targets = shelters;

        if (payload.zoomToShelterId != null) {
            targets = shelters.filter((s) => s.id === payload.zoomToShelterId);
        } else {
            targets = shelters.slice(0, routeLimit);
        }

        if (payload.centerOnUser && userPos && payload.zoomToShelterId == null) {
            patirotaFitUserAndNearest(
                map,
                userPos,
                targets,
                state,
                viewGen,
                10,
                14
            );
        } else if (boundsPointCount >= 2) {
            const fitBounds = new google.maps.LatLngBounds();
            let fitCount = 0;

            const addToFit = (pos) => {
                fitBounds.extend(pos);
                fitCount += 1;
            };

            if (userPos) {
                addToFit(userPos);
            }

            targets.forEach((sh) => {
                const routeKey = String(sh.id);
                const routeData = routes[routeKey] || routes[sh.id];
                const path = decodeRoutePath(routeData);
                if (path.length > 0) {
                    extendBoundsFromPath(fitBounds, path);
                    fitCount += path.length;
                }
                addToFit({ lat: sh.lat, lng: sh.lng });
            });

            if (fitCount >= 2) {
                const maxZoom = payload.zoomToShelterId != null ? 15 : 14;
                map.fitBounds(fitBounds, 48);
                google.maps.event.addListenerOnce(map, "bounds_changed", () => {
                    if (state.mapViewGeneration !== viewGen) {
                        return;
                    }
                    if (map.getZoom() > maxZoom) {
                        map.setZoom(maxZoom);
                    }
                });
            }
        }
    }

    if (
        payload.recenterUser &&
        state.lastUserPos &&
        !shouldFit &&
        patirotaIsValidLatLng(state.lastUserPos.lat, state.lastUserPos.lng)
    ) {
        map.panTo(state.lastUserPos);
    }

    patirotaScheduleMapRefresh(map);
    return true;
}

/**
 * Google Geolocation API (WiFi/IP tabanli tahmin, fallback degil - GPS sonrasi deneme).
 */
async function getGoogleGeolocation() {
    const key = window.PATIROTA_GMAPS_KEY;
    if (!key) {
        return { error: "GOOGLE_MAPS_API_KEY tanimli degil." };
    }
    try {
        const response = await fetch(
            "https://www.googleapis.com/geolocation/v1/geolocate?key=" +
                encodeURIComponent(key),
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ considerIp: true }),
            }
        );
        const data = await response.json();
        if (!response.ok) {
            const errText =
                data.error && data.error.message
                    ? data.error.message
                    : "Google Geolocation API hatasi";
            return { error: errText };
        }
        if (data.location && data.location.lat != null && data.location.lng != null) {
            return {
                latitude: data.location.lat,
                longitude: data.location.lng,
                accuracy: data.accuracy || 1500,
                source: "google_geolocation",
            };
        }
        return { error: "Google konum yaniti gecersiz." };
    } catch (err) {
        return { error: "Google konum istegi basarisiz: " + String(err) };
    }
}

/**
 * GPS okuma: once hassas, basarisizsa normal mod.
 * NiceGUI: return await getBrowserLocation();
 */
function getBrowserLocation() {
    return new Promise((resolve) => {
        if (!navigator.geolocation) {
            resolve({ error: "Tarayiciniz konum ozelligini desteklemiyor." });
            return;
        }

        if (!window.isSecureContext) {
            resolve({
                error: "Guvenli adres gerekli: http://localhost:8080 kullanin.",
            });
            return;
        }

        const mapError = (code) => {
            if (code === 1) {
                return "Konum izni verilmedi. Adres cubugundaki konum ikonundan izin verin.";
            }
            if (code === 2) {
                return "Konum sinyali yok. Windows Ayarlar > Gizlilik > Konum acik olmali.";
            }
            if (code === 3) {
                return "Konum okumasi zaman asimina ugradi.";
            }
            return "Konum alinamadi.";
        };

        const readOnce = (highAccuracy, timeoutMs) =>
            new Promise((res) => {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        res({
                            ok: true,
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                            accuracy: position.coords.accuracy,
                        });
                    },
                    (error) => {
                        res({ ok: false, code: error.code });
                    },
                    {
                        enableHighAccuracy: highAccuracy,
                        timeout: timeoutMs,
                        maximumAge: 120000,
                    }
                );
            });

        (async () => {
            let result = await readOnce(true, 15000);
            if (!result.ok) {
                result = await readOnce(false, 10000);
            }
            if (result.ok) {
                resolve({
                    latitude: result.latitude,
                    longitude: result.longitude,
                    accuracy: result.accuracy,
                    source: "gps",
                });
                return;
            }
            resolve({ error: mapError(result.code) });
        })();
    });
}

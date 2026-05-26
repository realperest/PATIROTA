import os
import json
import logging
import httpx
import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from nicegui import ui, app

# Kendi modullerimiz
import database
import crud

# 1. Loglama Yapilandirmasi (Kural 8)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Veritabani kontrolu/olusturma
if not os.path.exists(database.DB_FILE):
    database.init_db()

# 2. FastAPI ve Middleware Yapilandirmasi (Kural 6)
# GZipMiddleware aktif ediliyor (1 KB uzerindeki transferler için)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Statik dosyalarin sunulmasi (Kural 7 - CSS/JS Izolasyonu)
app.mount('/static', StaticFiles(directory='static'), name='static')

# FastAPI APIRouter (Kural 7)
api_router = APIRouter(prefix="/api")

# Pydantic Schemas (Kural 7)
class LocationInput(BaseModel):
    latitude: float = Field(..., description="Kullanici enlem bilgisi")
    longitude: float = Field(..., description="Kullanici boylam bilgisi")

class ShelterResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    address: Optional[str]
    phone: Optional[str]
    distance: float

# Statik dosya onbellek kirma (YYMMDD.XXXX)
APP_ASSET_VERSION = "260526.0018"

LIST_MODE_SHELTERS = "shelters"
LIST_MODE_VETERINARIANS = "veterinarians"
LIST_MODE_OPTIONS = {
    LIST_MODE_SHELTERS: "BARINAKLAR",
    LIST_MODE_VETERINARIANS: "VETERİNERLER",
}

REFINE_LOCATION_MIN_KM = 3.0

MOBILE_UA_MARKERS = (
    "iphone",
    "ipod",
    "ipad",
    "android",
    "mobile",
    "webos",
    "blackberry",
    "iemobile",
    "opera mini",
    "crios",
    "fxios",
    "silk/",
    "kindle",
)


def detect_client_is_mobile() -> bool:
    """Tarayici User-Agent ile mobil veya masaustu istemci tespiti."""
    try:
        client = ui.context.client
        if client is None or getattr(client, "request", None) is None:
            return False
        ua = (client.request.headers.get("user-agent") or "").lower()
        if not ua:
            return False
        return any(marker in ua for marker in MOBILE_UA_MARKERS)
    except Exception as err:
        logger.warning("Cihaz tespiti yapilamadi: %s", err)
        return False


def get_client_device_mode() -> str:
    return "mobile" if detect_client_is_mobile() else "desktop"


def is_valid_map_coordinate(lat: Optional[float], lon: Optional[float]) -> bool:
    if lat is None or lon is None:
        return False
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    if not (-85.0 <= lat_f <= 85.0 and -180.0 <= lon_f <= 180.0):
        return False
    if abs(lat_f) < 0.0001 and abs(lon_f) < 0.0001:
        return False
    return True


DEFAULT_MAP_LAT = 41.2815
DEFAULT_MAP_LON = 28.0015
DEFAULT_LOCATION_ACCURACY_M = 500.0

LOCATION_JS = """
return await (async () => {
    for (let i = 0; i < 60; i++) {
        if (typeof getBrowserLocation === 'function') {
            break;
        }
        await new Promise((r) => setTimeout(r, 100));
    }
    if (typeof getBrowserLocation !== 'function') {
        return { error: 'Konum modulu henuz yuklenmedi.' };
    }
    const gps = await getBrowserLocation();
    if (gps.latitude != null && gps.longitude != null && !gps.error) {
        return gps;
    }
    if (typeof getGoogleGeolocation === 'function') {
        const googleLoc = await getGoogleGeolocation();
        if (googleLoc.latitude != null && googleLoc.longitude != null && !googleLoc.error) {
            return googleLoc;
        }
        return { error: googleLoc.error || gps.error || 'Konum alinamadi.' };
    }
    return { error: gps.error || 'Konum alinamadi.' };
})();
"""

# Her barinak rotasi icin ayri renk (en fazla 5)
ROUTE_COLORS = ["#ef4444", "#3b82f6", "#eab308", "#a855f7", "#06b6d4"]


def get_active_nearest_places() -> List[Dict[str, Any]]:
    if session_state.get("list_mode") == LIST_MODE_VETERINARIANS:
        return session_state.get("nearest_veterinarians") or []
    return session_state.get("nearest_shelters") or []


def get_sidebar_title() -> str:
    if session_state.get("list_mode") == LIST_MODE_VETERINARIANS:
        return "En Yakın Veterinerler"
    return "En Yakın Barınaklar"


async def fetch_and_store_routes(
    u_lat: float, u_lon: float, places: List[Dict[str, Any]]
) -> None:
    if not places:
        session_state["place_routes"] = {}
        return
    tasks = [
        get_google_directions_route(u_lat, u_lon, p["latitude"], p["longitude"])
        for p in places
    ]
    routes_results = await asyncio.gather(*tasks)
    session_state["place_routes"] = {
        p["id"]: route_data for p, route_data in zip(places, routes_results)
    }


def build_place_detail_for_balloon(place_id: int) -> Optional[Dict[str, Any]]:
    """Panel ile birebir ayni kaynaktan balon verisi."""
    for idx, place in enumerate(get_active_nearest_places()):
        if place["id"] == place_id:
            return {
                "id": place["id"],
                "n": idx + 1,
                "name": place["name"] or "",
                "address": place.get("address") or "",
                "phone": place.get("phone") or "",
                "distanceKm": f"{place['distance']:.2f}".replace(".", ","),
                "lat": place["latitude"],
                "lng": place["longitude"],
            }
    return None


def build_nav_payload_for_balloon() -> Dict[str, Any]:
    return {
        "locationReady": session_state["location_ready"],
        "userLat": session_state["user_lat"],
        "userLon": session_state["user_lon"],
    }


async def load_nearest_for_active_mode(
    u_lat: float, u_lon: float, limit: int = 5
) -> List[Dict[str, Any]]:
    if session_state.get("list_mode") == LIST_MODE_VETERINARIANS:
        nearest = await crud.get_nearest_veterinarians(u_lat, u_lon, limit=limit)
        session_state["nearest_veterinarians"] = nearest
    else:
        nearest = await crud.get_nearest_shelters(u_lat, u_lon, limit=limit)
        session_state["nearest_shelters"] = nearest
    await fetch_and_store_routes(u_lat, u_lon, nearest)
    return nearest


def route_color_for_index(index: int) -> str:
    return ROUTE_COLORS[index % len(ROUTE_COLORS)]


def google_maps_directions_url(place: Dict[str, Any]) -> str:
    """Hedef her zaman koordinat; konum hazirsa surus rotasi acilir."""
    lat = place["latitude"]
    lon = place["longitude"]
    if not is_valid_map_coordinate(lat, lon):
        addr = (place.get("address") or place.get("name") or "").strip()
        query = addr.replace(" ", "+") if addr else "Turkiye"
        return f"https://www.google.com/maps/search/?api=1&query={query}"
    dest = f"{lat},{lon}"
    if session_state["location_ready"] and is_valid_map_coordinate(
        session_state.get("user_lat"), session_state.get("user_lon")
    ):
        origin = f"{session_state['user_lat']},{session_state['user_lon']}"
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={origin}&destination={dest}&travelmode=driving"
        )
    return f"https://www.google.com/maps/search/?api=1&query={dest}"


def _straight_route_path(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Dict[str, Any]:
    return {"path": [[lat1, lon1], [lat2, lon2]]}


def build_shelter_details_map() -> Dict[str, Dict[str, Any]]:
    """Panel ile ayni kaynak: aktif liste -> harita balonu verisi."""
    details: Dict[str, Dict[str, Any]] = {}
    for idx, sh in enumerate(get_active_nearest_places()):
        shelter_id = str(sh["id"])
        distance_km = f"{sh['distance']:.2f}".replace(".", ",")
        details[shelter_id] = {
            "id": sh["id"],
            "n": idx + 1,
            "name": sh["name"] if sh.get("name") is not None else "",
            "address": sh["address"] if sh.get("address") is not None else "",
            "phone": sh["phone"] if sh.get("phone") is not None else "",
            "distanceKm": distance_km,
            "lat": sh["latitude"],
            "lng": sh["longitude"],
        }
    return details


def build_google_map_payload(
    fit_map: bool = False,
    zoom_to_shelter_id: Optional[int] = None,
    recenter_user: bool = False,
) -> Dict[str, Any]:
    shelters: List[Dict[str, Any]] = []
    routes: Dict[str, Any] = {}
    shelter_details = build_shelter_details_map()
    active_places = get_active_nearest_places()
    if session_state["location_ready"] and active_places:
        for idx, sh in enumerate(active_places):
            color = route_color_for_index(idx)
            detail = shelter_details.get(str(sh["id"]), {})
            distance_km = detail.get("distanceKm") or f"{sh['distance']:.2f}".replace(
                ".", ","
            )
            shelters.append(
                {
                    "id": sh["id"],
                    "lat": sh["latitude"],
                    "lng": sh["longitude"],
                    "n": idx + 1,
                    "color": color,
                    "name": detail.get("name") or sh.get("name") or "",
                    "address": detail.get("address") or sh.get("address") or "",
                    "phone": detail.get("phone") or sh.get("phone") or "",
                    "distanceKm": distance_km,
                }
            )
            route_data = session_state.get("place_routes", {}).get(sh["id"])
            if route_data:
                routes[str(sh["id"])] = {**route_data, "color": color}
            else:
                routes[str(sh["id"])] = {
                    "path": [
                        [session_state["user_lat"], session_state["user_lon"]],
                        [sh["latitude"], sh["longitude"]],
                    ],
                    "color": color,
                }
    return {
        "defaultLat": DEFAULT_MAP_LAT,
        "defaultLng": DEFAULT_MAP_LON,
        "locationReady": session_state["location_ready"],
        "userLat": session_state["user_lat"],
        "userLon": session_state["user_lon"],
        "accuracyM": session_state.get("location_accuracy_m"),
        "shelters": shelters,
        "shelterDetails": shelter_details,
        "routes": routes,
        "fitMap": fit_map,
        "centerOnUser": fit_map and zoom_to_shelter_id is None,
        "recenterUser": recenter_user,
        "zoomToShelterId": zoom_to_shelter_id,
        "routeLimit": 4,
    }


async def render_google_map(
    map_host,
    fit_map: bool = False,
    zoom_to_shelter_id: Optional[int] = None,
    recenter_user: bool = False,
) -> None:
    if map_host is None:
        return
    if not os.environ.get("GOOGLE_MAPS_API_KEY", "").strip():
        logger.error("GOOGLE_MAPS_API_KEY eksik; harita guncellenemedi")
        return
    payload = build_google_map_payload(
        fit_map, zoom_to_shelter_id, recenter_user=recenter_user
    )
    details_json = json.dumps(payload.get("shelterDetails", {}), ensure_ascii=False)
    payload_json = json.dumps(payload, ensure_ascii=False)
    try:
        await ui.run_javascript(
            f"""
            window.PATIROTA_SHELTER_DETAILS = {details_json};
            return await updatePatirotaGoogleMap({map_host.id}, {payload_json});
            """,
            timeout=45.0,
        )
    except (TimeoutError, Exception) as err:
        logger.warning("Google harita guncelleme hatasi: %s", err)

async def fetch_ip_geolocation() -> Optional[tuple[float, float, float]]:
    """Tarayici GPS basarisiz olursa IP tabanli yaklasik konum."""
    url = "http://ip-api.com/json/?fields=status,message,lat,lon"
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None
            data = response.json()
            if data.get("status") != "success":
                logger.warning("IP konum yaniti: %s", data.get("message"))
                return None
            return float(data["lat"]), float(data["lon"]), 5000.0
    except Exception as err:
        logger.error("IP konum hatasi: %s", err)
        return None


async def get_google_directions_route(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> Dict[str, Any]:
    """Google Directions API ile surus rotasi (encoded polyline veya duz cizgi)."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        logger.error("GOOGLE_MAPS_API_KEY tanimli degil")
        return _straight_route_path(lat1, lon1, lat2, lon2)
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{lat1},{lon1}",
        "destination": f"{lat2},{lon2}",
        "mode": "driving",
        "key": key,
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, params=params)
            if response.status_code != 200:
                logger.error("Directions HTTP %s", response.status_code)
                return _straight_route_path(lat1, lon1, lat2, lon2)
            data = response.json()
            status = data.get("status")
            if status != "OK" or not data.get("routes"):
                logger.warning(
                    "Directions API yaniti: %s (%s -> %s)",
                    status,
                    lat1,
                    lon1,
                )
                return _straight_route_path(lat1, lon1, lat2, lon2)
            encoded = data["routes"][0]["overview_polyline"]["points"]
            return {"polyline": encoded}
    except Exception as err:
        logger.error(
            "Google Directions hatasi (%s,%s -> %s,%s): %s",
            lat1,
            lon1,
            lat2,
            lon2,
            err,
        )
    return _straight_route_path(lat1, lon1, lat2, lon2)

# API Endpoint'leri
@api_router.post("/nearest-shelters", response_model=List[ShelterResponse])
async def api_nearest_shelters(loc: LocationInput):
    """En yakin 5 barinagi getiren API endpoint'i."""
    try:
        shelters = await crud.get_nearest_shelters(loc.latitude, loc.longitude, limit=5)
        return shelters
    except Exception as e:
        logger.error(f"API nearest-shelters hatasi: {str(e)}")
        raise HTTPException(status_code=500, detail="Sunucu tarafinda bir hata olustu.")

@api_router.get("/heartbeat")
async def api_heartbeat():
    """Bağlantıyı aktif tutmak ve kesintileri önlemek için heartbeat endpoint'i (Kural 6)."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

app.include_router(api_router)

# Yetkilendirme Rolleri ve State (Kural 9 - RBAC)
# Simülasyon amaçli varsayilan rol 'Guest'. Arayuzde rol degisimi saglanacaktir.
session_state = {
    "current_user": "ziyaretci",
    "current_role": "Guest",
    "user_lat": None,
    "user_lon": None,
    "location_ready": False,
    "location_accuracy_m": None,
    "nearest_shelters": [],
    "nearest_veterinarians": [],
    "place_routes": {},
    "list_mode": LIST_MODE_SHELTERS,
    "selected_status_id": 1,
    "legal_template": None,
    "selected_shelter_id": None,
    "location_source": None,
    "info_balloon_shelter_id": None,
    "info_balloon_phase": None,
}

# Sayfa Yukleme & Yetki Kontrolleri
async def init_session_data():
    """Oturum baslangicinda varsayilan verileri yukler."""
    role = await crud.get_user_role(session_state["current_user"])
    if role:
        session_state["current_role"] = role
    
    # Ilk yasal sablonu yukle
    template = await crud.get_legal_template_by_status(session_state["selected_status_id"])
    session_state["legal_template"] = template

@ui.page('/')
async def index_page():
    ui.dark_mode().enable()
    await init_session_data()

    device_mode = get_client_device_mode()
    device_is_mobile = device_mode == "mobile"
    logger.info("Istemci cihaz modu: %s", device_mode)

    # CSS ve JS Dosyalarini Kafaya Ekleme (Kural 7 - Isolation & Cache Busting)
    ui.add_head_html(
        '<meta name="viewport" content="width=device-width, initial-scale=1, '
        'maximum-scale=1, viewport-fit=cover">'
    )
    ui.add_head_html(
        f'<script>document.documentElement.dataset.patirotaDevice={json.dumps(device_mode)};'
        f'document.documentElement.classList.add("patirota-device-{device_mode}");</script>'
    )
    ui.add_head_html(f'<link rel="stylesheet" href="/static/style.css?v={APP_ASSET_VERSION}">')
    ui.add_head_html(f'<script src="/static/app.js?v={APP_ASSET_VERSION}"></script>')
    gmaps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    ui.add_head_html(
        f"<script>window.PATIROTA_GMAPS_KEY={json.dumps(gmaps_key)};</script>"
    )
    if not gmaps_key:
        logger.error(
            "GOOGLE_MAPS_API_KEY tanimli degil. .env.local veya ortam degiskeni ekleyin."
        )
    
    # Kural 6: WebSocket & Heartbeat Mekanizmasi (Fetch Tabanli)
    # Her 10 saniyede bir sunucuya istek göndererek Cloudflare/Railway bağlantısını açık tutar.
    # Sunucuya erişilemezse otomatik olarak sayfayı yeniden yükler (reconnect).
    ui.add_head_html("""
    <script>
        if (location.hostname === '127.0.0.1') {
            location.replace(
                'http://localhost:' + location.port + location.pathname + location.search
            );
        }
        setInterval(() => {
            fetch('/api/heartbeat')
                .then(response => {
                    if (!response.ok) throw new Error("Ağ hatası");
                    console.log('Heartbeat: Bağlantı aktif');
                })
                .catch(error => {
                    console.warn('Heartbeat: Sunucuya erişilemiyor, yeniden bağlanılıyor...', error);
                    // Sayfayı yenileyerek otomatik yeniden bağlanmayı tetikler
                    setTimeout(() => { location.reload(); }, 2000);
                });
        }, 10000);
    </script>
    """)
    
    # Sayfa Basligi
    ui.page_title('PatiRota - Konum Tabanli Barinak ve Hukuk Asistanı')
    
    # --- DIALOG / MODAL: Hukuki Destek (İstek 1) ---
    with ui.dialog() as legal_dialog, ui.card().classes('w-full max-w-2xl bg-slate-900 border border-slate-800 p-6 flex flex-col gap-4') as legal_card:
        ui.label('Hukuki Rehber ve Mevzuat').classes('text-xl font-bold text-primary m-0')
        
        status_list = await crud.get_status_list()
        status_options = {s["id"]: s["display_name"] for s in status_list}
        
        async def on_status_change(e):
            session_state["selected_status_id"] = e.value
            template = await crud.get_legal_template_by_status(e.value)
            session_state["legal_template"] = template
            update_legal_view()
        
        status_dropdown = ui.select(
            options=status_options, 
            label='Sokaktaki Hayvanın Durumu',
            value=session_state["selected_status_id"],
            on_change=on_status_change
        ).classes('w-full').props('outlined')
        
        # Hukuki detaylar container'ı
        legal_details_container = ui.element('div').classes('w-full flex flex-col gap-3')
        
        def update_legal_view():
            legal_details_container.clear()
            template = session_state["legal_template"]
            if not template:
                return
                
            with legal_details_container:
                # Kanun Referansı
                with ui.element('div').classes('p-3 rounded-lg bg-slate-950 border border-slate-800'):
                    ui.label('Yasal Dayanak (5199 Sayılı Kanun):').classes('text-xs text-secondary font-bold uppercase')
                    ui.label(template["law_reference"]).classes('text-sm text-primary mt-1 font-medium')
                
                # Rehber Açıklaması
                ui.label('Nasıl İlerlemelisiniz?').classes('text-xs text-secondary font-bold uppercase mb-1 mt-2')
                with ui.element('div').classes('p-4 rounded-lg bg-slate-800 border border-slate-700'):
                    ui.label(template["template_text"]).classes('text-sm text-slate-200 whitespace-pre-wrap')
        
        update_legal_view()
        ui.button('Kapat', on_click=legal_dialog.close).classes('w-full bg-slate-800 hover:bg-slate-700 text-white rounded-lg mt-2')

    # --- ANA ARAYUZ (tam ekran dikey) ---
    page_classes = f'page-root patirota-device-{device_mode}'
    with ui.element('div').classes(page_classes):
        
        def open_places_drawer() -> None:
            ui.run_javascript(
                "window.patirotaOpenPlacesDrawer && window.patirotaOpenPlacesDrawer();"
            )

        def close_places_drawer() -> None:
            ui.run_javascript(
                "window.patirotaClosePlacesDrawer && window.patirotaClosePlacesDrawer();"
            )

        map_update_lock = asyncio.Lock()
        location_lock = asyncio.Lock()

        async def apply_location(
            u_lat: float,
            u_lon: float,
            accuracy: float,
            silent: bool = False,
            fit_map: bool = False,
            recenter_user: bool = False,
            source: str = "gps",
        ) -> None:
            if not is_valid_map_coordinate(u_lat, u_lon):
                logger.warning(
                    "Gecersiz konum reddedildi: lat=%s lon=%s", u_lat, u_lon
                )
                return
            session_state["user_lat"] = u_lat
            session_state["user_lon"] = u_lon
            session_state["location_ready"] = True
            session_state["location_accuracy_m"] = accuracy
            session_state["location_source"] = source
            session_state["selected_shelter_id"] = None
            session_state["info_balloon_shelter_id"] = None
            session_state["info_balloon_phase"] = None

            await load_nearest_for_active_mode(u_lat, u_lon, limit=5)

            logger.info(
                "Konum lat=%.6f lon=%.6f accuracy=%.1fm",
                u_lat,
                u_lon,
                accuracy,
            )
            await update_map(
                fit_map=fit_map,
                recenter_user=recenter_user,
                zoom_to_shelter_id=session_state["selected_shelter_id"],
            )

        async def request_location(
            force: bool = False,
            refine_only: bool = False,
        ) -> None:
            async with location_lock:
                if (
                    not force
                    and not refine_only
                    and session_state.get("location_ready")
                    and get_active_nearest_places()
                ):
                    return
                client_id = getattr(ui.context.client, "id", "?")
                logger.info("Konum istegi basladi (client=%s)", client_id)
                try:
                    coords: Optional[Dict[str, Any]] = None
                    try:
                        coords = await ui.run_javascript(
                            LOCATION_JS, timeout=45.0
                        )
                        logger.info("Konum JS yaniti: %s", coords)
                    except Exception as err:
                        logger.error("Konum JS istegi hatasi: %s", err)

                    if (
                        isinstance(coords, dict)
                        and coords.get("latitude") is not None
                        and coords.get("longitude") is not None
                        and not coords.get("error")
                    ):
                        new_lat = float(coords["latitude"])
                        new_lon = float(coords["longitude"])
                        accuracy = float(coords.get("accuracy") or 0.0)
                        source = str(coords.get("source") or "gps")
                        if refine_only and session_state.get("user_lat") is not None:
                            if source == "gps" and session_state.get(
                                "location_source"
                            ) == "gps":
                                shift_km = crud.haversine(
                                    session_state["user_lat"],
                                    session_state["user_lon"],
                                    new_lat,
                                    new_lon,
                                )
                                if shift_km < REFINE_LOCATION_MIN_KM:
                                    logger.info(
                                        "GPS ince ayar atlandi (kayma %.2f km)",
                                        shift_km,
                                    )
                                    return
                        await apply_location(
                            new_lat,
                            new_lon,
                            accuracy,
                            silent=refine_only,
                            fit_map=not refine_only,
                            recenter_user=refine_only,
                            source=source,
                        )
                        if not refine_only:
                            logger.info(
                                "Konum alindi: source=%s accuracy=%.1fm",
                                source,
                                accuracy,
                            )
                        return

                    if isinstance(coords, dict) and coords.get("error"):
                        logger.warning("Konum hatasi: %s", coords["error"])

                    if refine_only:
                        return

                    err_msg = (
                        coords.get("error")
                        if isinstance(coords, dict)
                        else "Konum alinamadi."
                    )
                    logger.warning(
                        "Konum alinamadi: %s",
                        err_msg,
                    )
                    await update_map()
                except Exception as err:
                    logger.error("Konum istegi genel hata: %s", err)

        async def on_role_change(e):
            session_state["current_role"] = e.value
            session_state["current_user"] = (
                "yonetici" if e.value == "Admin" else "ziyaretci"
            )
            logger.info("Rol %s olarak güncellendi.", e.value)
            await refresh_elements()

        # 1. Minimal Header (mobilde tek satir, kompakt ikonlar)
        with ui.element('div').classes('premium-header'):
            with ui.row().classes(
                'header-bar w-full items-center justify-between flex-nowrap gap-2'
            ):
                with ui.column().classes('gap-0 min-w-0'):
                    ui.label('PatiRota').classes(
                        'mobile-logo text-lg md:text-2xl font-bold title-gradient m-0'
                    )
                    ui.label('En Yakın Barınaklar ve Rota Rehberi').classes(
                        'header-tagline text-xs text-secondary m-0'
                    )

                with ui.row().classes(
                    'header-actions items-center gap-1 flex-nowrap shrink-0'
                ):
                    ui.button(
                        on_click=lambda: request_location(force=True),
                    ).props('flat round dense icon=my_location').classes(
                        'header-icon-btn'
                    ).tooltip('Konumumu Yenile')
                    ui.button(
                        on_click=legal_dialog.open,
                    ).props('flat round dense icon=gavel').classes(
                        'header-icon-btn'
                    ).tooltip('Hukuki Destek')
                    if device_is_mobile:
                        ui.button(
                            on_click=open_places_drawer,
                        ).props('flat round dense icon=menu').classes(
                            'header-icon-btn mobile-drawer-toggle'
                        ).tooltip('Liste')

                    if not device_is_mobile:
                        with ui.row().classes(
                            'desktop-role-row items-center gap-2 shrink-0'
                        ):
                            ui.label('Rol:').classes('text-xs text-secondary')
                            ui.select(
                                options=["Guest", "Admin"],
                                value=session_state["current_role"],
                                on_change=on_role_change,
                            ).classes('w-28').props('outlined dense')

        # 2. Harita (tam ekran) + sag cekmece panel
        with ui.card().classes(
            'premium-card map-panel w-full p-0 overflow-hidden border border-slate-800'
        ).props('flat square'):
            google_map_host = None

            with ui.element('div').classes('mobile-map-shell shelter-layout'):
                map_pane_slot = ui.element('div').classes('map-pane')
                ui.element('div').classes('drawer-backdrop')
                sidebar_slot = ui.element('div').classes('shelter-sidebar')
                with sidebar_slot:
                    if device_is_mobile:
                        with ui.row().classes(
                            'drawer-mobile-top w-full items-center justify-between'
                        ):
                            ui.label('Yakın Yerler').classes(
                                'text-sm font-bold text-primary m-0'
                            )
                            ui.button(
                                on_click=close_places_drawer,
                            ).props('flat round dense icon=close').classes(
                                'drawer-close-btn'
                            )
                    async def on_list_mode_change(e) -> None:
                        new_mode = e.value
                        if session_state.get("list_mode") == new_mode:
                            return
                        session_state["list_mode"] = new_mode
                        session_state["selected_shelter_id"] = None
                        if session_state.get("location_ready"):
                            u_lat = session_state["user_lat"]
                            u_lon = session_state["user_lon"]
                            if new_mode == LIST_MODE_VETERINARIANS:
                                if not session_state.get("nearest_veterinarians"):
                                    await load_nearest_for_active_mode(
                                        u_lat, u_lon, limit=5
                                    )
                                else:
                                    await fetch_and_store_routes(
                                        u_lat,
                                        u_lon,
                                        session_state["nearest_veterinarians"],
                                    )
                            else:
                                if not session_state.get("nearest_shelters"):
                                    await load_nearest_for_active_mode(
                                        u_lat, u_lon, limit=5
                                    )
                                else:
                                    await fetch_and_store_routes(
                                        u_lat,
                                        u_lon,
                                        session_state["nearest_shelters"],
                                    )
                        sidebar_title_label.text = get_sidebar_title()
                        mode_label = LIST_MODE_OPTIONS.get(new_mode, new_mode)
                        logger.info("Liste modu degisti: %s", mode_label)
                        await update_map(
                            fit_map=session_state.get("location_ready", False),
                        )

                    with ui.column().classes("w-full gap-2 p-3 border-b border-slate-800"):
                        ui.toggle(
                            LIST_MODE_OPTIONS,
                            value=session_state.get("list_mode", LIST_MODE_SHELTERS),
                            on_change=on_list_mode_change,
                        ).classes("w-full place-mode-toggle text-xs font-semibold").props(
                            "dense no-caps toggle-color=primary spread"
                        )
                        sidebar_title_label = ui.label(
                            get_sidebar_title()
                        ).classes("shelter-sidebar-title m-0")
                    sidebar_list_slot = ui.element("div").classes("shelter-sidebar-list")

            async def activate_shelter_route(
                shelter_id: int,
                open_navigation: bool = False,
            ) -> None:
                session_state["selected_shelter_id"] = shelter_id
                shelter = next(
                    (s for s in get_active_nearest_places() if s["id"] == shelter_id),
                    None,
                )
                if not shelter:
                    return
                await update_map(zoom_to_shelter_id=shelter_id)
                logger.info("%s rotasi secildi.", shelter['name'])
                if open_navigation:
                    ui.run_javascript(
                        f'window.open({json.dumps(google_maps_directions_url(shelter))}, "_blank")'
                    )

            map_click_lock = asyncio.Lock()

            async def on_map_pick_location(e) -> None:
                latlng = e.args.get("latlng") or {}
                u_lat = latlng.get("lat")
                u_lon = latlng.get("lng")
                if u_lat is None or u_lon is None:
                    return
                async with map_click_lock:
                    await apply_location(
                        float(u_lat),
                        float(u_lon),
                        15.0,
                        silent=True,
                        fit_map=True,
                    )
                logger.info("Konum haritadan secildi: lat=%s lon=%s", u_lat, u_lon)

            async def on_shelter_marker_click(e) -> None:
                """Balon JS tarafinda acilir; burada yalnizca panel secimi guncellenir."""
                shelter_id = e.args.get("shelterId")
                if shelter_id is None:
                    return
                session_state["selected_shelter_id"] = int(shelter_id)
                await update_sidebar()

            async def update_sidebar() -> None:
                sidebar_list_slot.clear()
                with sidebar_list_slot:
                    places = get_active_nearest_places()
                    if not places:
                        return

                    for idx, sh in enumerate(places):
                        route_color = route_color_for_index(idx)
                        text_style = f"color:{route_color};"
                        formatted_distance = f"{sh['distance']:.2f}".replace(".", ",")
                        gmaps_url = google_maps_directions_url(sh)
                        is_selected = sh["id"] == session_state["selected_shelter_id"]
                        item_classes = "shelter-sidebar-item cursor-pointer transition-all duration-300"
                        if is_selected:
                            item_classes += " shelter-sidebar-item-selected"
                        border_width = "6px" if is_selected else "4px"
                        item_style = (
                            f"border-left:{border_width} solid {route_color};"
                            f"box-shadow:0 0 12px {route_color}33;"
                        )

                        with ui.element("div").classes(item_classes).style(item_style) as item_card:
                            async def select_shelter(e, s_id=sh["id"]):
                                if session_state["selected_shelter_id"] == s_id:
                                    session_state["selected_shelter_id"] = None
                                    await update_map(fit_map=True)
                                else:
                                    await activate_shelter_route(
                                        s_id,
                                        open_navigation=False,
                                    )

                            # Kartın tamamına tıklama özelliği ekliyoruz
                            item_card.on("click", select_shelter)

                            with ui.element("div").classes("shelter-sidebar-header pointer-events-none"):
                                title_label = ui.label(
                                    f"{idx + 1}. {sh['name']}"
                                ).classes("shelter-sidebar-name").style(
                                    f"{text_style}font-weight:700;"
                                )
                                ui.label(f"{formatted_distance} KM").classes(
                                    "shelter-sidebar-distance"
                                ).style(f"{text_style}font-weight:800;")

                            # Detaylar sadece seciliyse (accordion acik) gosterilecek
                            if is_selected:
                                with ui.element("div").classes(
                                    "shelter-sidebar-details mt-2 pointer-events-auto w-full"
                                ).style(text_style):
                                    async def create_route(e, s_id=sh["id"]):
                                        # 1. Haritada rotayı çiz ve zoom yap
                                        await activate_shelter_route(s_id, open_navigation=False)
                                        # 2. İstemci tarafında navigasyonu tetikle
                                        sh_payload = {
                                            "id": sh["id"],
                                            "lat": sh["latitude"],
                                            "lng": sh["longitude"],
                                            "name": sh["name"] or "",
                                            "address": sh["address"] or "",
                                            "phone": sh["phone"] or "",
                                            "distanceKm": formatted_distance
                                        }
                                        nav_payload = {
                                            "locationReady": session_state["location_ready"],
                                            "userLat": session_state["user_lat"],
                                            "userLon": session_state["user_lon"]
                                        }
                                        ui.run_javascript(f"patirotaOpenRoute({json.dumps(sh_payload)}, {json.dumps(nav_payload)});")

                                    with ui.row().classes("w-full justify-between items-end flex-nowrap gap-1"):
                                        # Sol tarafta telefon ve adres alt alta (kompakt)
                                        with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                                            if sh["phone"]:
                                                ui.label(f"Tel: {sh['phone']}").classes("text-[11px] leading-tight").style(text_style)
                                            if sh["address"]:
                                                ui.label(sh["address"]).classes("text-[11px] leading-tight").style(text_style)
                                                
                                    async def create_route(e, s_id=sh["id"]):
                                        # Haritada rotayı çiz ve zoom yap
                                        await activate_shelter_route(s_id, open_navigation=False)

                                    js_cmd = f"event.stopPropagation(); window.patirotaOpenRouteFromSidebar({sh['id']});"

                                    with ui.row().classes("w-full justify-between items-end flex-nowrap gap-1"):
                                        # Sol tarafta telefon ve adres alt alta (kompakt)
                                        with ui.column().classes("gap-0.5 min-w-0 flex-1"):
                                            if sh["phone"]:
                                                ui.label(f"Tel: {sh['phone']}").classes("text-[11px] leading-tight").style(text_style)
                                            if sh["address"]:
                                                ui.label(sh["address"]).classes("text-[11px] leading-tight").style(text_style)
                                                
                                        # Sağ tarafta ROTA OLUŞTUR butonu
                                        ui.button("ROTA OLUŞTUR").classes(
                                            "text-[10px] font-bold p-1 px-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded shrink-0 shadow-sm ml-2 h-7"
                                        ).props("dense flat no-caps").on("click", create_route, js_handler=js_cmd)

            async def update_map(
                fit_map: bool = False,
                zoom_to_shelter_id: Optional[int] = None,
                recenter_user: bool = False,
            ) -> None:
                nonlocal google_map_host

                async with map_update_lock:
                    try:
                        if google_map_host is None:
                            with map_pane_slot:
                                google_map_host = ui.element("div").classes(
                                    "google-map-host w-full h-full"
                                )
                                google_map_host.on(
                                    "shelter-marker-click",
                                    on_shelter_marker_click,
                                )
                                google_map_host.on("map-click", on_map_pick_location)
                                init_payload = json.dumps(
                                    {
                                        "lat": DEFAULT_MAP_LAT,
                                        "lng": DEFAULT_MAP_LON,
                                        "zoom": 13,
                                    }
                                )
                                await ui.run_javascript(
                                    f"""
                                    return await initPatirotaGoogleMap(
                                        {google_map_host.id},
                                        {init_payload}
                                    );
                                    """,
                                    timeout=30.0,
                                )

                        await render_google_map(
                            google_map_host,
                            fit_map=fit_map,
                            zoom_to_shelter_id=zoom_to_shelter_id,
                            recenter_user=recenter_user,
                        )
                    except Exception as err:
                        logger.exception("Harita guncelleme hatasi: %s", err)
                    finally:
                        await update_sidebar()

        async def refresh_elements():
            update_legal_view()
            await update_map()

        # Rota yardimci fonksiyonu enjeksiyonu (Popup engelleyiciyi asmak icin)
        ui.add_body_html("""
        <script>
            window.patirotaOpenRouteFromSidebar = function(shelterId) {
                const key = String(shelterId);
                if (!window.PATIROTA_SHELTER_DETAILS || !window.PATIROTA_SHELTER_DETAILS[key]) {
                    console.error("Barinak detaylari bulunamadi: " + shelterId);
                    return;
                }
                const detail = window.PATIROTA_SHELTER_DETAILS[key];
                
                let userLat = null;
                let userLon = null;
                let locationReady = false;
                if (typeof patirotaMapRegistry !== "undefined") {
                    for (const hostId of Object.keys(patirotaMapRegistry)) {
                        const state = patirotaMapRegistry[hostId];
                        if (state && state.lastUserPos) {
                            userLat = state.lastUserPos.lat;
                            userLon = state.lastUserPos.lng;
                            locationReady = true;
                            break;
                        }
                    }
                }
                
                const place = {
                    id: detail.id,
                    n: detail.n,
                    name: detail.name || "",
                    address: detail.address || "",
                    phone: detail.phone || "",
                    distanceKm: detail.distanceKm || "",
                    lat: detail.lat,
                    lng: detail.lng
                };
                
                const navPayload = {
                    locationReady: locationReady,
                    userLat: userLat,
                    userLon: userLon
                };
                
                if (typeof patirotaOpenRoute === "function") {
                    patirotaOpenRoute(place, navPayload);
                } else {
                    console.error("patirotaOpenRoute fonksiyonu yuklenmemis.");
                }
            };
        </script>
        """)

    await update_map()

    async def startup_location() -> None:
        await request_location(force=True)

    ui.timer(0.3, startup_location, once=True)

    async def refine_gps_location() -> None:
        if session_state.get("location_source") == "google_geolocation":
            await request_location(refine_only=True)

    ui.timer(1.2, refine_gps_location, once=True)

def load_env_local() -> None:
    """Proje kokundeki .env.local dosyasini ortam degiskenlerine yukler."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.local")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as err:
        logger.error(".env.local okunamadi: %s", err)


def run_server() -> None:
    """NiceGUI sunucusunu baslatir."""
    load_env_local()
    if not os.environ.get("GOOGLE_MAPS_API_KEY", "").strip():
        logger.warning(
            "GOOGLE_MAPS_API_KEY yok. Harita ve rotalar calismayabilir."
        )
    is_local = bool(os.environ.get("LOCAL_DEV"))
    host = "127.0.0.1" if is_local else "0.0.0.0"
    port = int(os.environ.get("PORT", 8080))
    open_browser = os.environ.get("OPEN_BROWSER", "1" if is_local else "0") == "1"

    reload_enabled = os.environ.get("RELOAD", "0") == "1"
    logger.info(
        "PatiRota sunucusu baslatiliyor: http://localhost:%s (konum icin localhost kullanin)",
        port,
    )
    if reload_enabled:
        logger.info("Otomatik kod yenileme (RELOAD=1) acik.")
    ui.run(
        host=host,
        port=port,
        reload=reload_enabled,
        title="PatiRota",
        storage_secret=os.environ.get("STORAGE_SECRET", "patirota_secret_key_123"),
        show=open_browser,
    )


if __name__ in {"__main__", "__mp_main__"}:
    load_env_local()
    run_server()

import math
import asyncio
import logging
from typing import List, Dict, Any, Optional
from database import get_connection

logger = logging.getLogger(__name__)

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Iki koordinat arasindaki mesafeyi km cinsinden hesaplar."""
    # Dereceyi radyana ceviriyoruz
    rad_lat1 = math.radians(lat1)
    rad_lon1 = math.radians(lon1)
    rad_lat2 = math.radians(lat2)
    rad_lon2 = math.radians(lon2)
    
    dlat = rad_lat2 - rad_lat1
    dlon = rad_lon2 - rad_lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(rad_lat1) * math.cos(rad_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Dunya yaricapi (km)
    R = 6371.0
    return R * c

async def get_nearest_shelters(user_lat: float, user_lon: float, limit: int = 5) -> List[Dict[str, Any]]:
    """Kullaniciya en yakin barinaklari mesafeleriyle siralar ve limit adedince doner."""
    loop = asyncio.get_event_loop()
    
    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, name, latitude, longitude, address, phone FROM shelters;")
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                sh_id, name, lat, lon, address, phone = row
                dist = haversine(user_lat, user_lon, lat, lon)
                results.append({
                    "id": sh_id,
                    "name": name,
                    "latitude": lat,
                    "longitude": lon,
                    "address": address,
                    "phone": phone,
                    "distance": round(dist, 2)
                })
            
            # Mesafeye gore sirala
            results.sort(key=lambda x: x["distance"])
            return results[:limit]
        except Exception as e:
            logger.error(f"En yakin barinaklar alinirken hata olustu: {str(e)}")
            raise e
        finally:
            conn.close()
            
    return await loop.run_in_executor(None, _fetch)


async def get_nearest_veterinarians(
    user_lat: float, user_lon: float, limit: int = 5
) -> List[Dict[str, Any]]:
    """Kullaniciya en yakin veterinerleri mesafeleriyle siralar."""
    loop = asyncio.get_event_loop()

    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, name, latitude, longitude, address, phone FROM veterinarians;"
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                vet_id, name, lat, lon, address, phone = row
                dist = haversine(user_lat, user_lon, lat, lon)
                results.append(
                    {
                        "id": vet_id,
                        "name": name,
                        "latitude": lat,
                        "longitude": lon,
                        "address": address,
                        "phone": phone,
                        "distance": round(dist, 2),
                    }
                )
            results.sort(key=lambda x: x["distance"])
            return results[:limit]
        except Exception as err:
            logger.error("En yakin veterinerler alinirken hata: %s", err)
            raise err
        finally:
            conn.close()

    return await loop.run_in_executor(None, _fetch)


async def get_status_list() -> List[Dict[str, Any]]:
    """Hayvan durum lookup listesini doner (Kural 9)."""
    loop = asyncio.get_event_loop()
    
    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id, status_name, display_name FROM status_lookup;")
            rows = cursor.fetchall()
            return [{"id": r[0], "status_name": r[1], "display_name": r[2]} for r in rows]
        except Exception as e:
            logger.error(f"Durum listesi alinirken hata: {str(e)}")
            raise e
        finally:
            conn.close()
            
    return await loop.run_in_executor(None, _fetch)

async def get_legal_template_by_status(status_id: int) -> Optional[Dict[str, Any]]:
    """Belirli bir hayvan durumuna bagli yasal referans ve dilekce sablonunu getirir (Kural 9)."""
    loop = asyncio.get_event_loop()
    
    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT lt.id, lt.status_id, sl.display_name, lt.law_reference, lt.template_text 
                FROM legal_templates lt
                JOIN status_lookup sl ON lt.status_id = sl.id
                WHERE lt.status_id = ?;
            """, (status_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "status_id": row[1],
                    "status_name": row[2],
                    "law_reference": row[3],
                    "template_text": row[4]
                }
            return None
        except Exception as e:
            logger.error(f"Dilekce sablonu alinirken hata: {str(e)}")
            raise e
        finally:
            conn.close()
            
    return await loop.run_in_executor(None, _fetch)

async def get_user_role(username: str) -> Optional[str]:
    """Kullanicinin rolunu veritabanindan sorgular (Kural 9 - RBAC)."""
    loop = asyncio.get_event_loop()
    
    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT r.role_name FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username = ?;
            """, (username,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Kullanici rolu sorgulanirken hata: {str(e)}")
            raise e
        finally:
            conn.close()
            
    return await loop.run_in_executor(None, _fetch)

async def check_permission(role_name: str, resource_name: str, permission_type: str) -> bool:
    """Rolun belirtilen kaynakta izni olup olmadigini sorgular (Kural 9 - RBAC).
    permission_type: 'view' veya 'edit'
    """
    loop = asyncio.get_event_loop()
    
    def _fetch():
        conn = get_connection()
        cursor = conn.cursor()
        try:
            field = "can_view" if permission_type == "view" else "can_edit"
            query = f"""
                SELECT {field} FROM permissions p
                JOIN roles r ON p.role_id = r.id
                WHERE r.role_name = ? AND p.resource_name = ?;
            """
            cursor.execute(query, (role_name, resource_name))
            row = cursor.fetchone()
            return bool(row[0]) if row else False
        except Exception as e:
            logger.error(f"Yetki kontrolu sirasinda hata: {str(e)}")
            raise e
        finally:
            conn.close()
            
    return await loop.run_in_executor(None, _fetch)

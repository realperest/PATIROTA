# Proje Planı ve Teknik İsterler: PatiRota (Konum Tabanlı Köpek Barınağı ve Hukuk Asistanı)

## 1. Proje Özeti & Amaç
"PatiRota", sokakta yardıma muhtaç, yaralı, terk edilmiş veya şiddet gören bir köpek bulan vatandaşların yaşadığı çaresizliği ve hangi kuruma nasıl başvuracağını bilememe sorununu çözen konum tabanlı bir acil durum platformudur.

Uygulamanın ana amacı; kullanıcının tarayıcı üzerindeki anlık konum verisini (geolocation) alarak en yakın 5 köpek barınağını veya belediye veterinerlik işlerini haritada listelemek, Google Maps üzerinden rota çizmek ve kullanıcının karşılaştığı acil duruma göre (şiddet ihbarı, yaralı köpek vb.) 5199 sayılı Kanun kapsamında anlık hukuki yol haritası ile hazır resmi dilekçe şablonları üretmektir.

## 2. Teknik Yığın (Technical Stack)
Ajanın hızlı bir şekilde Full-Stack prototip üretebilmesi ve canlı ortama (Production) sorunsuz taşınabilmesi için şu yapı tercih edilmiştir:
- **Dil:** Python 3.10+
- **Arayüz (Frontend & Backend):** `NiceGUI` (Hızlı web arayüzü ve entegre asenkron backend yapısı için)
- **Harita Servisi:** Leaflet.js (Python/NiceGUI uyumlu `ui.leaflet` bileşeni ile ücretsiz ve API anahtarı gerektirmeyen harita yönetimi) veya Google Maps JavaScript API.
- **AI Entegrasyonu:** `OpenAI API` (Model: `gpt-4o-mini`)
- **Veritabanı (Barınak Lokasyonları & Dilekçeler):** `SQLite` (Barınak isimleri, enlem/boylam koordinatları ve resmi dilekçe şablonlarını saklamak için).

## 3. Sistem Mimarisi & Veri Akışı
1. **Konum Bilgisi Alma:** Uygulama açıldığında tarayıcı üzerinden kullanıcının anlık koordinatları (Latitude/Longitude) istenir.
2. **Mesafe Hesaplama (Haversine Formülü):** Kullanıcının koordinatları ile SQLite veritabanında kayıtlı olan barınak koordinatları arasındaki kuş uçuşu mesafe Python tarafında otomatik hesaplanır ve en yakın 5 köpek barınağı sıralanır.
3. **Haritalandırma & Rotalama:** En yakın 5 barınak harita üzerinde pinlenir. Seçilen barınak için Google Maps yönlendirme linki dinamik olarak oluşturulur.
4. **Hukuki Modül:** Kullanıcı karşılaştığı durumu (Örn: "Köpeğe Şiddet İhbarı") seçtiğinde, sistem ilgili kanun maddesini gösterir ve resmi makamlara sunulmak üzere veritabanından dinamik dilekçe çıktısı verir.

## 4. Veritabanı Şeması (SQLite)
Ajan, ilk kurulumda otomatik olarak şu iki tabloyi oluşturmalı ve jenerik (örnek) verileri enjekte etmelidir:

```sql
CREATE TABLE IF NOT EXISTS shelters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    phone TEXT
);

CREATE TABLE IF NOT EXISTS legal_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    law_reference TEXT,
    template_text TEXT NOT NULL
);
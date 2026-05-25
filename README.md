# PatiRota

Konum tabanli kopek barinagi ve hukuk asistani.

## Sayfa acilmiyorsa (ERR_CONNECTION_REFUSED)

Bu hata, **sunucunun calismadigi** anlamina gelir. `index.html` dosyasini cift tiklamayin; once sunucuyu baslatin.

### Hizli baslatma (Windows)

1. `kurulum.bat` — yalnizca ilk sefer (paket + veritabani)
2. `baslat.bat` — her kullanimda once eski sunucuyu/portu temizler, sonra acar (ayri durdur dosyasi gerekmez)
3. Adres: **http://localhost:8080** (konum izni icin 127.0.0.1 kullanmayin)

### Manuel baslatma

```powershell
cd d:\KODLAMALAR\GITHUB\PATIROTA
python -m pip install -r requirements.txt
python database.py
$env:LOCAL_DEV="1"
python main.py
```

Sunucuyu kapatmak icin terminalde Ctrl+C yeterli. Yeniden acmak icin yine `baslat.bat` calistirin; onceki surecler otomatik temizlenir.

## Gereksinimler

- Python 3.11 veya 3.12 onerilir (3.14 ile de calisabilir)
- Internet (OSRM rota ve harita kutugu icin)

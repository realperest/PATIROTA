# -*- coding: utf-8 -*-
import sqlite3
import os
import logging

DB_FILE = "patirota.db"

# Loglama ayari (Kural 8)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    """Veritabani tablolarini olusturur ve ornek verileri yukler (Kural 4 ve Kural 9)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # SQLite'da foreign key destegini etkinlestiriyoruz
        cursor.execute("PRAGMA foreign_keys = ON;")
        
        # Transaction baslatiliyor (Kural 4)
        cursor.execute("BEGIN TRANSACTION;")
        
        # 1. Roller tablosu (Kural 9 - Lookup)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_name TEXT NOT NULL UNIQUE
            );
        """)
        
        # 2. Kullanicilar tablosu (RBAC icin - Kural 9)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                role_id INTEGER NOT NULL,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
            );
        """)
        
        # 3. Yetkiler tablosu (RBAC icin - Kural 9)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                can_view INTEGER DEFAULT 1, -- 0: False, 1: True
                can_edit INTEGER DEFAULT 0, -- 0: False, 1: True
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                UNIQUE(resource_name, role_id)
            );
        """)
        
        # 4. Hayvan Durum Lookup Tablosu (Kural 9 geregi)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status_lookup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL
            );
        """)
        
        # 5. Barinak Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shelters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                phone TEXT
            );
        """)

        # 5b. Veteriner Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS veterinarians (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                address TEXT,
                phone TEXT
            );
        """)
        
        # 6. Hukuki Sablonlar Tablosu (Kural 9 - status_id foreign key)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS legal_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status_id INTEGER NOT NULL,
                law_reference TEXT NOT NULL,
                template_text TEXT NOT NULL,
                FOREIGN KEY (status_id) REFERENCES status_lookup(id) ON DELETE RESTRICT
            );
        """)
        
        # Seed Verilerin Eklenmesi
        # Rolleri ekle
        cursor.execute("INSERT OR IGNORE INTO roles (id, role_name) VALUES (1, 'Admin');")
        cursor.execute("INSERT OR IGNORE INTO roles (id, role_name) VALUES (2, 'Guest');")
        
        # Ornek Kullanicilari ekle
        cursor.execute("INSERT OR IGNORE INTO users (id, username, role_id) VALUES (1, 'yonetici', 1);")
        cursor.execute("INSERT OR IGNORE INTO users (id, username, role_id) VALUES (2, 'ziyaretci', 2);")
        
        # Yetkileri ekle
        # Admin her seyi yapabilir (can view: 1, can edit: 1)
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('dashboard', 1, 1, 1);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('shelters', 1, 1, 1);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('veterinarians', 1, 1, 1);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('legal', 1, 1, 1);")
        # Ziyaretci sadece goruntuleyebilir (can view: 1, can edit: 0)
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('dashboard', 2, 1, 0);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('shelters', 2, 1, 0);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('veterinarians', 2, 1, 0);")
        cursor.execute("INSERT OR IGNORE INTO permissions (resource_name, role_id, can_view, can_edit) VALUES ('legal', 2, 1, 0);")
        
        # Hayvan durumlarini ekle (Lookup)
        durumlar = [
            (1, 'KAZA_GECIRMIS', 'Kaza Gecirmis / Yarali'),
            (2, 'HASTA', 'Hasta / Gucten Dusmus'),
            (3, 'YAVRU', 'Yavru / Bakima Muhtac'),
            (4, 'SIDDET_GOREN', 'Siddet / Kotu Muamele Goren'),
            (5, 'NORMAL', 'Normal / Saglikli')
        ]
        for d_id, name, display in durumlar:
            cursor.execute("INSERT OR IGNORE INTO status_lookup (id, status_name, display_name) VALUES (?, ?, ?);", (d_id, name, display))
            
        # Istanbul ve Trakya genelindeki ornek kopek barinaklari (En yakin barinaklar icin gerceki koordinatlar)
        barinaklar = [
            (1, 'Kadikoy Belediyesi Gecici Hayvan Bakimevi', 40.9723, 29.0838, 'Merdikenkoy Yolu No: 3, Kadikoy/Istanbul', '0216 418 29 19'),
            (2, 'Uskudar Belediyesi Minik Dostlar Ambulansi ve Bakimevi', 41.0268, 29.0558, 'Selimiye, Harem Iskelesi Cd. No:3, Uskudar/Istanbul', '0216 531 30 00'),
            (3, 'Besiktas Belediyesi Rehabilitasyon Merkezi', 41.0772, 29.0152, 'Ortakoy, Besiktas/Istanbul', '0212 263 11 11'),
            (4, 'Fatih Belediyesi Yedikule Hayvan Barinagi', 40.9934, 28.9221, 'Yedikule Mahallesi, Yedikule Cirpici Yolu No:2, Fatih/Istanbul', '0212 633 58 57'),
            (5, 'Atasehir Belediyesi Gecici Hayvan Bakimevi', 40.9839, 29.1293, 'Atasehir Bulvari No:10, Atasehir/Istanbul', '0216 570 50 00'),
            (6, 'Bakirkoy Belediyesi Sokak Hayvanlari Gecici Bakimevi', 40.9845, 28.8782, 'Kartaltepe, Bakirkoy/Istanbul', '0212 414 97 77'),
            (7, 'Cerkezkoy Belediyesi Gecici Hayvan Bakimevi', 41.2982, 28.0012, 'Fatih Mahallesi, Cerkezkoy/Tekirdag', '0282 736 50 00'),
            (8, 'Kapakli Belediyesi Gecici Hayvan Bakimevi', 41.3283, 27.9793, 'Kapakli/Tekirdag', '0282 717 11 22'),
            (9, 'Corlu Belediyesi Gecici Hayvan Bakimevi', 41.1568, 27.8189, 'Corlu/Tekirdag', '0282 684 75 00'),
            (10, 'Silivri Belediyesi Hayvan Rehabilitasyon Merkezi', 41.0735, 28.2464, 'Silivri/Istanbul', '0212 727 12 12'),
            (11, 'Saray Belediyesi Gecici Hayvan Bakimevi', 41.4428, 27.9839, 'Saray/Tekirdag', '0282 768 10 05')
        ]
        for b_id, name, lat, lon, addr, phone in barinaklar:
            cursor.execute("INSERT OR IGNORE INTO shelters (id, name, latitude, longitude, address, phone) VALUES (?, ?, ?, ?, ?, ?);", (b_id, name, lat, lon, addr, phone))

        veterinerler = [
            (1, 'Cerkezkoy Belediyesi Veteriner Isleri Mudurlugu', 41.2950, 28.0050, 'Fatih Mahallesi, Cerkezkoy/Tekirdag', '0282 736 50 01'),
            (2, 'Kapakli Belediyesi Veteriner Hizmetleri', 41.3200, 27.9850, 'Kapakli/Tekirdag', '0282 717 11 20'),
            (3, 'Corlu Veteriner Poliklinigi', 41.1600, 27.8250, 'Corlu/Tekirdag', '0282 684 75 10'),
            (4, 'Tekirdag Merkez Veteriner Hizmetleri', 40.9780, 27.5120, 'Tekirdag Merkez', '0282 261 10 10'),
            (5, 'Silivri Veteriner Klinigi', 41.0800, 28.2500, 'Silivri/Istanbul', '0212 727 12 20'),
            (6, 'Saray Belediyesi Veteriner Birimi', 41.4400, 27.9900, 'Saray/Tekirdag', '0282 768 10 10'),
            (7, 'Kadikoy Belediyesi Veteriner Hizmetleri', 40.9800, 29.0600, 'Kadikoy/Istanbul', '0216 418 29 20'),
            (8, 'Uskudar Belediyesi Veteriner Mudurlugu', 41.0250, 29.0200, 'Uskudar/Istanbul', '0216 531 30 10'),
            (9, 'Bakirkoy Veteriner Merkezi', 40.9900, 28.8700, 'Bakirkoy/Istanbul', '0212 414 97 70'),
            (10, 'Atasehir Veteriner Klinigi', 40.9900, 29.1200, 'Atasehir/Istanbul', '0216 570 50 10'),
            (11, 'Luleburgaz Veteriner Hizmetleri', 41.4000, 27.3600, 'Luleburgaz/Kirklareli', '0288 417 10 10'),
        ]
        for v_id, name, lat, lon, addr, phone in veterinerler:
            cursor.execute(
                "INSERT OR IGNORE INTO veterinarians (id, name, latitude, longitude, address, phone) VALUES (?, ?, ?, ?, ?, ?);",
                (v_id, name, lat, lon, addr, phone),
            )
            
        # Hukuki Sablonlar
        sablolar = [
            (
                1, 1,
                '5199 Sayili Kanun Madde 21: Bir motorlu tasit carpan hayvana acil veteriner yardimi goturmekle veya ulastirmakla yukumludur.',
                'ISTANBUL BELEDIYESI VETERINER ISLERI MUDURLUGUNE\n\nBasvuran: [Adiniz Soyadiniz]\nT.C. Kimlik No: [TC No]\nAdres: [Adresiniz]\nTelefon: [Telefonunuz]\n\nKonu: Yarali sokak hayvanina acil mudahale yapilmasi ve tedavi edilmesi talebi.\n\nAciklamalar:\n[Tarih] tarihinde, [Olay Yeri Adresi] mevkisinde trafik kazasi gecirmis ve yaralanmis bir sokak kopegi tespit ettim. 5199 Sayili Hayvanlari Koruma Kanunu Madde 21 geregince yarali hayvana en kisa surede acil tibbi mudahalede bulunulmasi, gerekli tedavilerinin yapilmasi ve rehabilitasyon surecinin baslatilmasi icin belediyeniz veteriner ekiplerinin ivedilikle adrese yonlendirilmesini arz ederim.\n\nImza:\n[Adiniz Soyadiniz]'
            ),
            (
                2, 2,
                '5199 Sayili Kanun Madde 14/f: Gucten dusmus hayvanlarin tibbi tedavi disinda calistirilmasi ve eziyet edilmesi yasaktir. Belediyeler bu hayvanlarin bakimi ve tedavisiyle yukumludur.',
                'ISTANBUL BELEDIYESI VETERINER ISLERI MUDURLUGUNE\n\nBasvuran: [Adiniz Soyadiniz]\nAdres: [Adresiniz]\nTelefon: [Telefonunuz]\n\nKonu: Hasta/Gucten dusmus sokak hayvaninin tedaviye alinmasi talebi.\n\nAciklamalar:\n[Olay Yeri Adresi] adresinde, gozle gorulur sekilde hasta, enfeksiyonlu ve kendi bakimini idame ettiremeyecek durumda bir sokak kopegi bulunmaktadir. 5199 Sayili Kanun kapsaminda belediyenizin sokak hayvanlarini rehabilite etme gorevi uyarinca, soz konusu hayvanin ekiplerce yerinden alinarak tedavi merkezine goturulmesini ve sagligina kavusturulmasini talep ederim.\n\nImza:\n[Adiniz Soyadiniz]'
            ),
            (
                3, 3,
                '5199 Sayili Kanun Madde 4: Hicbir hayvan, kendi turune ozgu hayat sartlarindan uzaklastirilamaz. Ancak yavru ve annesiz hayvanlarin belediye bakimevlerinde koruma altina alinmasi esastir.',
                'ISTANBUL BELEDIYESI VETERINER ISLERI MUDURLUGUNE\n\nBasvuran: [Adiniz Soyadiniz]\nAdres: [Adresiniz]\nTelefon: [Telefonunuz]\n\nKonu: Annesiz/Korumasiz yavru kopeklerin guvenli barinaga alinmasi talebi.\n\nAciklamalar:\n[Olay Yeri Adresi] adresinde, anneleri olmayan, cevre kosullari nedeniyle hayati tehlikesi bulunan henuz sutten kesilmemis yavru kopekler bulunmaktadir. Bu yavrularin donma, aclik veya arac altinda kalma risklerine karsi belediyeniz rehabilitasyon ve gecici bakimevi bunyesinde guvenli alana alinarak koruma altina alinmasini arz ederim.\n\nImza:\n[Adiniz Soyadiniz]'
            ),
            (
                4, 4,
                '5199 Sayili Kanun Madde 14/a: Hayvanlara kasitli olarak kotu davranmak, acimasiz ve zalimce islem yapmak, dovmek, ac ve susuz birakmak yasaktir. Turk Ceza Kanunu kapsaminda hayvana siddet suctur.',
                'CUMHURIYET BASSAVCILIGINA\n\nMusteri/Ihbar Eden: [Adiniz Soyadiniz]\nAdres: [Adresiniz]\nTelefon: [Telefonunuz]\n\nSupheli: [Suphelinin Adi veya Tespit Edilemediyse Faili Mechul]\n\nKonu: Hayvana iskence ve kotu muamele sucu (5199 s. K. Madde 14 ve TCK ilgili hukumleri) hakkinda kamu davasi acilmasi talebi.\n\nAciklamalar:\n[Tarih] gunu saat [Saat] sularinda [Olay Yeri Adresi] adresinde supheli sahsin bir sokak kopegine kasitli olarak siddet uyguladigini, darp ettigini ve iskence yaptigini tespit ettim (Varsa deliller/sahitler eklenmelidir). 5199 Sayili Hayvanlari Koruma Kanununun guncel hukumleri uyarinca hayvana iskence ve eziyet etmek adli suc niteligindedir. Supheli hakkinda gerekli sorusturmanin yapilarak cezalandirilmasi icin kamu davasi acilmasini talep ederim.\n\nDeliller: [Varsa Video, Fotograf, Taniklar]\n\nImza:\n[Adiniz Soyadiniz]'
            ),
            (
                5, 5,
                '5199 Sayili Kanun Madde 6: Sahipsiz veya gucten dusmus hayvanlarin en hizli sekilde yerel yonetimlerce kurulan gecici bakimevlerine goturulmesi zorunludur. Rehabilite edilen hayvanlarin oncelikle alindiklari ortama birakilmalari esastir.',
                'ISTANBUL BELEDIYESI VETERINER ISLERI MUDURLUGUNE\n\nBasvuran: [Adiniz Soyadiniz]\nAdres: [Adresiniz]\nTelefon: [Telefonunuz]\n\nKonu: Sahipsiz sokak hayvaninin asilanmasi ve kisirlastirilmasi talebi.\n\nAciklamalar:\n[Olay Yeri Adresi] adresinde bulunan kupesiz ve sahipsiz sokak kopeginin, 5199 Sayili Kanun Madde 6 uyarinca asilanmasi, kisirlastirilmasi ve gerekli saglik kontrollerinin yapilmasi amaciyla belediyeniz ekiplerce gecici bakimevine goturulmesini, islemler tamamlandiktan sonra ise yasa geregi alindigi adrese geri birakilmasini arz ederim.\n\nImza:\n[Adiniz Soyadiniz]'
            )
        ]
        for s_id, status_id, ref, text in sablolar:
            cursor.execute("INSERT OR IGNORE INTO legal_templates (id, status_id, law_reference, template_text) VALUES (?, ?, ?, ?);", (s_id, status_id, ref, text))
            
        conn.commit()
        logger.info("Veritabani basariyla initialize edildi ve veriler yuklendi.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Veritabani initialization hatasi: {str(e)}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()

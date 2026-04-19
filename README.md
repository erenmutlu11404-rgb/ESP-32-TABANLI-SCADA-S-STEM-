ESP32 Tabanlı Endüstriyel IoT Gateway ve Web SCADA Sistemi
Bu proje, endüstriyel sahadaki verilerin (Modbus RTU/TCP) toplanması, işlenmesi ve modern bir web arayüzü üzerinden izlenip kontrol edilmesini sağlayan bir Endüstriyel IoT Gateway çözümüdür. Proje, düşük maliyetli donanımları endüstriyel standartlarla birleştirerek esnek bir SCADA altyapısı sunar.

🚀 Proje Hakkında
Bu çalışma, klasik PLC ve HMI sistemlerinin yeteneklerini IoT dünyasıyla birleştirmek amacıyla geliştirilmiştir. ESP32'nin işlem gücü, W5500'ün stabil kablolu bağlantı yeteneği ve Raspberry Pi 5'in sunucu kapasitesi kullanılarak uçtan uca bir veri hattı oluşturulmuştur.

Öne Çıkan Özellikler
Çoklu Protokol Desteği: Modbus TCP üzerinden sensör ve PLC verilerinin okunması, 

Modern Web SCADA: Flask tabanlı bir web sunucusu üzerinden gerçek zamanlı veri görselleştirme ve kontrol.

w5500 lite plc ile modbuss tcp üzerinden veri çeker

🛠 Teknik Mimari ve Donanım
Donanım Bileşenleri
Kontrolcü: ESP32 (Dual Core, 240MHz)

Haberleşme: * W5500 Ethernet Modülü (plc için)

MAX485 / RS485 Dönüştürücü (Endüstriyel cihazlarla haberleşme için)

Sunucu: Raspberry Pi 5 (Merkezi veri toplama ve Web SCADA sunucusu)

Yazılım Yığın (Software Stack)
Gömülü Yazılım: C++ / Arduino Framework (ESP32)

Backend: Python / Flask

Frontend: HTML5, CSS3, JavaScript (Real-time güncelleme için AJAX/WebSockets)

Protokol: Modbus TCP / RTU

📂 Dosya Yapısı
Plaintext
├── esp32_firmware/       # ESP32 üzerinde koşan C++ kodları
│   ├── src/              # Kaynak dosyalar (Modbus & Ethernet yönetimi)
│   └── include/          # Kütüphane tanımlamaları
├── web_scada_server/     # Raspberry Pi üzerinde koşan Flask uygulaması
│   ├── static/           # CSS, JS ve görseller
│   ├── templates/        # HTML arayüz dosyaları
│   └── app.py            # Ana sunucu dosyası
└── docs/                 # Bağlantı şemaları ve teknik dökümanlar
⚙️ Kurulum ve Kullanım
ESP32 Yazılımı
esp32_firmware klasöründeki kodu VS Code + PlatformIO veya Arduino IDE ile açın.

W5500 ve Modbus kütüphanelerinin yüklü olduğundan emin olun.

Ağ ayarlarını (IP, Gateway) kendi lokal ağınıza göre düzenleyin ve yükleyin.

Web Sunucusu
Raspberry Pi 5 terminalinde proje dizinine gidin.

Gerekli kütüphaneleri kurun:

Bash
pip install flask pymodbus
Sunucuyu başlatın:

Bash
python app.py
Tarayıcınızdan http://<raspberry-pi-ip>:5000 adresine giderek arayüze erişin.

👨‍💻 Geliştirici
Eren Mutlu Sakarya Uygulamalı Bilimler Üniversitesi (SUBÜ) - Elektrik-Elektronik Mühendisliği Adayı

Çekirdekten yetişme bir teknik altyapı ile endüstriyel otomasyon ve saha pratiklerini modern IoT çözümlerine dönüştürmeye odaklanıyorum. Özellikle PLC programlama, PCB tasarımı ve endüstriyel haberleşme protokolleri üzerine çalışmalarımı sürdürmekteyim.

Lisans
Bu proje eğitim ve geliştirme amaçlıdır. Ticari kullanımlar için lütfen iletişime geçiniz.

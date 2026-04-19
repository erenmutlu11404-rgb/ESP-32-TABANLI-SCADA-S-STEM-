#include <WiFi.h>
#include <SPI.h>
#include <Ethernet.h>
#include <Preferences.h>
#include <ArduinoJson.h>

Preferences hafiza;
#define LED_PIN 2

// --- W5500 PIN AYARLARI ---
const int p_SCLK = 32;
const int p_MISO = 26;
const int p_MOSI = 33;
const int p_CS   = 27;
const int p_RST  = 25;

// --- AĞ NESNELERİ ---
WiFiServer* scadaServer = nullptr;
int scadaPort = 502;

EthernetClient plcClient;
IPAddress hedefPlcIp;
int hedefPlcPort = 502;

byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };

bool yeniAyarVarMi() {
  if (Serial.available() > 0) {
    String gelenVeri = Serial.readStringUntil('\n');
    gelenVeri.trim();
    if (gelenVeri.startsWith("{")) {
      digitalWrite(LED_PIN, HIGH);
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, gelenVeri);

      if (!error) {
        hafiza.begin("cihaz_ayar", false);
        hafiza.clear();
        delay(50);
        hafiza.putString("ssid", doc["wifi_ssid"].as<String>());
        hafiza.putString("pass", doc["wifi_sifre"].as<String>());
        hafiza.putString("dev_ip", doc["cihaz_ip"].as<String>());
        hafiza.putInt("dev_port", doc["cihaz_port"].as<String>().toInt());
        if(doc.containsKey("plc_ip")) hafiza.putString("plc_ip", doc["plc_ip"].as<String>());
        if(doc.containsKey("plc_port")) hafiza.putInt("plc_port", doc["plc_port"].as<String>().toInt());
        hafiza.end();
        Serial.println("✅ Ayarlar Kaydedildi! Resetleniyor...");
        delay(1000);
        ESP.restart();
        return true;
      }
    }
  }
  return false;
}

// --- MODBUS VERİ OKUMA ---
uint32_t modbusSorguYap(char tur, int adres, String formatTip) {
  if (!plcClient.connected()) {
    if (!plcClient.connect(hedefPlcIp, hedefPlcPort)) return 0; 
  }

  int modbusAdres = 0;
  uint8_t fonksiyonKodu = 0x03;
  uint8_t okunacakRegister = (formatTip == "32BIT" || formatTip == "FLOAT") ? 0x02 : 0x01;

  if (tur == 'D') { modbusAdres = 0x1000 + adres; fonksiyonKodu = 0x03; }
  else if (tur == 'M') { modbusAdres = 0x0800 + adres; fonksiyonKodu = 0x01; }
  else if (tur == 'Y') { modbusAdres = 0x0500 + adres; fonksiyonKodu = 0x01; }
  else if (tur == 'X') { modbusAdres = 0x0400 + adres; fonksiyonKodu = 0x02; }
  else if (tur == 'T') { modbusAdres = 0x0600 + adres; fonksiyonKodu = 0x03; }
  else return 0;

  uint8_t request[12];
  request[0] = 0x00; request[1] = 0x01;
  request[2] = 0x00; request[3] = 0x00;
  request[4] = 0x00; request[5] = 0x06;
  request[6] = 0x01;
  request[7] = fonksiyonKodu;
  request[8] = (modbusAdres >> 8) & 0xFF;
  request[9] = modbusAdres & 0xFF;
  request[10] = 0x00;
  request[11] = okunacakRegister;

  while(plcClient.available()) plcClient.read();
  plcClient.write(request, 12);

  unsigned long timeout = millis();
  int beklenenByte = (fonksiyonKodu <= 0x02) ? 10 : (9 + (okunacakRegister * 2));
  
  while (plcClient.available() < beklenenByte) {
    if (millis() - timeout > 1000) return 0; 
  }

  uint8_t buffer[32];
  int len = plcClient.read(buffer, 32);
  if (len > 7 && (buffer[7] & 0x80)) return 0; 

  if (fonksiyonKodu == 0x03) {
    if (okunacakRegister == 2 && len >= 13) {
      uint16_t dusuk = (buffer[9] << 8) | buffer[10];
      uint16_t yuksek = (buffer[11] << 8) | buffer[12];
      return ((uint32_t)yuksek << 16) | dusuk; 
    } else {
      return (buffer[9] << 8) | buffer[10];
    }
  } else {
    return (buffer[9] & 0x01);
  }
}

// --- MODBUS VERİ YAZMA ---
bool modbusYazmaYap(char tur, int adres, String formatTip, JsonVariant degerObj) {
  if (!plcClient.connected()) {
    if (!plcClient.connect(hedefPlcIp, hedefPlcPort)) return false;
  }

  int modbusAdres = 0;
  if (tur == 'D') modbusAdres = 0x1000 + adres;
  else if (tur == 'M') modbusAdres = 0x0800 + adres;
  else if (tur == 'Y') modbusAdres = 0x0500 + adres;
  else if (tur == 'T') modbusAdres = 0x0600 + adres;
  else return false;

  uint8_t request[20];
  int reqLen = 0;

  // 1. DİJİTAL YAZMA
  if (tur == 'M' || tur == 'Y' || formatTip == "BOOL") {
    uint8_t yazilacakVeri = (degerObj.as<int>() > 0) ? 0xFF : 0x00; 
    request[0] = 0x00; request[1] = 0x02; 
    request[2] = 0x00; request[3] = 0x00; 
    request[4] = 0x00; request[5] = 0x06; 
    request[6] = 0x01; 
    request[7] = 0x05; 
    request[8] = (modbusAdres >> 8) & 0xFF;
    request[9] = modbusAdres & 0xFF;
    request[10] = yazilacakVeri;
    request[11] = 0x00;
    reqLen = 12;
  }
  // 2. ANALOG YAZMA 16-BIT
  else if (formatTip == "16BIT") {
    uint16_t deger = degerObj.as<uint16_t>();
    request[0] = 0x00; request[1] = 0x03;
    request[2] = 0x00; request[3] = 0x00;
    request[4] = 0x00; request[5] = 0x06;
    request[6] = 0x01;
    request[7] = 0x06; 
    request[8] = (modbusAdres >> 8) & 0xFF;
    request[9] = modbusAdres & 0xFF;
    request[10] = (deger >> 8) & 0xFF;
    request[11] = deger & 0xFF;
    reqLen = 12;
  }
  // 3. ANALOG YAZMA 32-BIT VEYA FLOAT
  else if (formatTip == "32BIT" || formatTip == "FLOAT") {
    uint32_t hamDeger;
    
    if (formatTip == "FLOAT") {
      float fDeger = degerObj.as<float>();
      memcpy(&hamDeger, &fDeger, sizeof(uint32_t)); 
    } else {
      hamDeger = degerObj.as<uint32_t>(); 
    }

    uint16_t dusuk = hamDeger & 0xFFFF;
    uint16_t yuksek = (hamDeger >> 16) & 0xFFFF;

    request[0] = 0x00; request[1] = 0x04;
    request[2] = 0x00; request[3] = 0x00;
    request[4] = 0x00; request[5] = 0x0B; 
    request[6] = 0x01;
    request[7] = 0x10; 
    request[8] = (modbusAdres >> 8) & 0xFF;
    request[9] = modbusAdres & 0xFF;
    request[10] = 0x00; request[11] = 0x02; 
    request[12] = 0x04; 
    
    request[13] = (dusuk >> 8) & 0xFF;
    request[14] = dusuk & 0xFF;
    request[15] = (yuksek >> 8) & 0xFF;
    request[16] = yuksek & 0xFF;
    reqLen = 17;
  }

  while(plcClient.available()) plcClient.read(); 
  plcClient.write(request, reqLen);              

  unsigned long timeout = millis();
  while(plcClient.available() < 8 && (millis() - timeout < 1000)) { delay(1); }
  
  uint8_t buffer[20];
  int len = plcClient.read(buffer, 20);
  if (len > 7 && (buffer[7] & 0x80)) return false;
  return true;
}

// --- ANA DİNLEME MOTORU ---
void scadaDinle() {
  if (!scadaServer) return;
  WiFiClient client = scadaServer->available();
  
  if (client) {
    unsigned long start = millis();
    while (!client.available() && millis() - start < 500) delay(1);

    if (client.available()) {
      String istek = client.readStringUntil('\n');
      istek.trim();
      
      DynamicJsonDocument docIstek(1024);
      DeserializationError err = deserializeJson(docIstek, istek);

      if (!err) {
        DynamicJsonDocument docCevap(1024);
        
        if (docIstek.containsKey("get")) {
          JsonArray istenenler = docIstek["get"]; 
          for (String etiketVeBit : istenenler) {
            int ayiriciIndex = etiketVeBit.indexOf('|');
            String komut; String formatTip;
            
            if (ayiriciIndex != -1) {
              komut = etiketVeBit.substring(0, ayiriciIndex);
              formatTip = etiketVeBit.substring(ayiriciIndex + 1);
            } else {
              komut = etiketVeBit; formatTip = "16BIT";
            }

            char tur = komut.charAt(0);
            int adres = komut.substring(1).toInt();
            docCevap[komut] = modbusSorguYap(tur, adres, formatTip);
          }
        }

        if (docIstek.containsKey("set")) {
          JsonObject yazilacaklar = docIstek["set"];
          
          for (JsonPair p : yazilacaklar) {
            String etiketVeBit = p.key().c_str(); 
            JsonVariant degerObj = p.value();     
            
            int ayiriciIndex = etiketVeBit.indexOf('|');
            String komut; String formatTip;
            
            if (ayiriciIndex != -1) {
              komut = etiketVeBit.substring(0, ayiriciIndex);
              formatTip = etiketVeBit.substring(ayiriciIndex + 1);
            } else {
              komut = etiketVeBit; formatTip = "16BIT";
            }
            
            char tur = komut.charAt(0);
            int adres = komut.substring(1).toInt();
            
            bool basari = modbusYazmaYap(tur, adres, formatTip, degerObj);
            docCevap[komut] = basari ? "OK" : "ERR";
          }
        }

        String jsonCevap;
        serializeJson(docCevap, jsonCevap);
        client.println(jsonCevap); 
      }
    }
    client.stop();
  }
}

void setup() {
  Serial.begin(9600); 
  pinMode(LED_PIN, OUTPUT);
  pinMode(p_RST, OUTPUT);
  digitalWrite(p_RST, LOW); delay(100);
  digitalWrite(p_RST, HIGH); delay(200);
  SPI.begin(p_SCLK, p_MISO, p_MOSI, p_CS);
  Ethernet.init(p_CS);

  IPAddress eth_ip(192, 168, 1, 201);
  IPAddress dns(192, 168, 1, 1);
  IPAddress gateway(192, 168, 1, 1);
  IPAddress subnet(255, 255, 255, 0);
  
  uint64_t chipid = ESP.getEfuseMac();
  mac[3] = (uint8_t)(chipid >> 24);
  mac[4] = (uint8_t)(chipid >> 16);
  mac[5] = (uint8_t)(chipid >> 8);
  Ethernet.begin(mac, eth_ip, dns, gateway, subnet);

  hafiza.begin("cihaz_ayar", true);
  String ssid = hafiza.getString("ssid", "");
  String pass = hafiza.getString("pass", "");
  String wifi_ip_str = hafiza.getString("dev_ip", "");
  scadaPort = hafiza.getInt("dev_port", 502);
  String plc_ip_str = hafiza.getString("plc_ip", "192.168.1.5");
  hedefPlcPort = hafiza.getInt("plc_port", 502);
  hafiza.end();
  
  hedefPlcIp.fromString(plc_ip_str);

  WiFi.mode(WIFI_STA);
  if(wifi_ip_str.length() > 6) {
    IPAddress wifi_local_ip; wifi_local_ip.fromString(wifi_ip_str);
    IPAddress wifi_gateway(wifi_local_ip[0], wifi_local_ip[1], wifi_local_ip[2], 1);
    IPAddress wifi_subnet(255, 255, 255, 0);
    WiFi.config(wifi_local_ip, wifi_gateway, wifi_subnet);
  }

  WiFi.begin(ssid.c_str(), pass.c_str());
  Serial.print("WiFi Baglaniyor: "); Serial.println(ssid);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
    yeniAyarVarMi();
  }
  
  Serial.println("\n✅ WiFi IP: " + WiFi.localIP().toString());
  scadaServer = new WiFiServer(scadaPort);
  scadaServer->begin();
  digitalWrite(LED_PIN, HIGH);
}

void loop() {
  yeniAyarVarMi();
  scadaDinle();
}
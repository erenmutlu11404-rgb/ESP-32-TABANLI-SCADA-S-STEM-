from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from functools import wraps
import json
import os
import socket
import struct
import threading
import time
import re
import subprocess
import platform
import serial
import serial.tools.list_ports
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = "super_gizli_anahtar_flask_icin"
DOSYA_ADI = "kayitli_cihazlar.json"
TOPLU_DOSYA_ADI = "toplu_izleme.json"
ALARM_DOSYA_ADI = "alarmlar.json"
GECMIS_ALARM_DOSYA_ADI = "gecmis_alarmlar.json" 
AYARLAR_DOSYA_ADI = "ayarlar.json" 
SISTEM_LOG_DOSYA_ADI = "sistem_loglari.json" 

aktif_baglantilar = {}
son_veriler = {}
aktif_alarmlar_listesi = []

# --- KULLANICI VE YETKİLENDİRME FONKSİYONLARI ---
def kullanicilari_getir():
    try:
        with open("kullanicilar.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}
    
def kullanicilari_kaydet(kullanicilar):
    with open("kullanicilar.json", "w", encoding="utf-8") as f:
        json.dump(kullanicilar, f, ensure_ascii=False, indent=4)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "kullanici" not in session:
            flash("Lütfen önce giriş yapın.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "kullanici" not in session:
            flash("Lütfen önce giriş yapın.", "warning")
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            flash("Bu işlemi yapmak için ADMIN yetkisine sahip olmalısınız!", "danger")
            return redirect(request.referrer or url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

# --- YARDIMCI FONKSİYONLAR ---
def ham_veriyi_floata_cevir(n):
    try: return struct.unpack('!f', struct.pack('!I', int(n) & 0xFFFFFFFF))[0]
    except: return float(n)

def cihazlari_getir():
    if not os.path.exists(DOSYA_ADI): return []
    try:
        with open(DOSYA_ADI, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def cihazlari_kaydet(liste):
    with open(DOSYA_ADI, "w", encoding="utf-8") as f: json.dump(liste, f, ensure_ascii=False, indent=4)

def toplu_getir():
    if not os.path.exists(TOPLU_DOSYA_ADI): return []
    try:
        with open(TOPLU_DOSYA_ADI, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def toplu_kaydet(liste):
    with open(TOPLU_DOSYA_ADI, "w", encoding="utf-8") as f: json.dump(liste, f, ensure_ascii=False, indent=4)

def alarmlari_getir():
    if not os.path.exists(ALARM_DOSYA_ADI): return []
    try:
        with open(ALARM_DOSYA_ADI, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def alarmlari_kaydet(liste):
    with open(ALARM_DOSYA_ADI, "w", encoding="utf-8") as f: json.dump(liste, f, ensure_ascii=False, indent=4)

def gecmis_getir():
    if not os.path.exists(GECMIS_ALARM_DOSYA_ADI): return []
    try:
        with open(GECMIS_ALARM_DOSYA_ADI, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def gecmis_kaydet(liste):
    with open(GECMIS_ALARM_DOSYA_ADI, "w", encoding="utf-8") as f: json.dump(liste[-150:], f, ensure_ascii=False, indent=4)

def ayarlari_getir():
    varsayilan = {"mail_acik": False, "gonderen": "", "sifre": "", "alici": []}
    if not os.path.exists(AYARLAR_DOSYA_ADI): return varsayilan
    try:
        with open(AYARLAR_DOSYA_ADI, "r", encoding="utf-8") as f: 
            ayarlar = json.load(f)
            if isinstance(ayarlar.get("alici"), str): ayarlar["alici"] = [ayarlar["alici"]] if ayarlar["alici"] else []
            return ayarlar
    except: return varsayilan

def ayarlari_kaydet(ayarlar):
    with open(AYARLAR_DOSYA_ADI, "w", encoding="utf-8") as f: json.dump(ayarlar, f, ensure_ascii=False, indent=4)

def ip_gecerli_mi(ip):
    pattern = r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    return re.match(pattern, ip)

def loglari_getir():
    if not os.path.exists(SISTEM_LOG_DOSYA_ADI): return []
    try:
        with open(SISTEM_LOG_DOSYA_ADI, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def log_ekle(kategori, mesaj):
    loglar = loglari_getir()
    zaman = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    loglar.append({"zaman": zaman, "kategori": kategori, "mesaj": mesaj})
    with open(SISTEM_LOG_DOSYA_ADI, "w", encoding="utf-8") as f:
        json.dump(loglar[-500:], f, ensure_ascii=False, indent=4)

def alarm_maili_at(baslik, mesaj_icerigi):
    ayarlar = ayarlari_getir()
    if not ayarlar.get("mail_acik") or not ayarlar.get("gonderen") or not ayarlar.get("sifre"): return
    alicilar = ayarlar.get("alici", [])
    if not alicilar: alicilar = [ayarlar["gonderen"]]
    try:
        msg = MIMEMultipart()
        msg['From'] = ayarlar['gonderen']
        msg['To'] = ", ".join(alicilar)
        msg['Subject'] = f"SCADA UYARISI: {baslik}"
        msg.attach(MIMEText(mesaj_icerigi, 'plain', 'utf-8'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(ayarlar['gonderen'], ayarlar['sifre'].replace(" ", ""))
        server.send_message(msg)
        server.quit()
        log_ekle("SİSTEM", f"Alarm maili başarıyla gönderildi: {baslik}")
    except Exception as e:
        log_ekle("HATA", f"Mail gönderme hatası: {str(e)}")

# --- ARKA PLAN MOTORLARI ---
def arka_plan_motoru():
    while True:
        for cihaz in cihazlari_getir():
            ip = cihaz.get('ip')
            port = cihaz.get('port')
            if not ip or not port: continue
            port_adi = f"{ip}:{port}"
            sensorler = cihaz.get('sensorler', [])
            if not sensorler: continue

            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((ip, int(port)))
                istenen_komutlar = []
                for w in sensorler:
                    format_tipi = w.get('veri_formati', '16BIT')
                    if w.get('tip') == 'Dijital': format_tipi = 'BOOL'
                    istenen_komutlar.append(f"{w['komut']}|{format_tipi}")
                istek_paketi = json.dumps({"get": istenen_komutlar}) + "\n"
                s.sendall(istek_paketi.encode('utf-8'))
                yanit = s.recv(2048).decode('utf-8', errors='ignore').strip()
                veriler = {}
                if yanit:
                    try:
                        gelen_json = json.loads(yanit)
                        for k, v in gelen_json.items():
                            ham_deger = int(v)
                            ayar = next((sensor for sensor in sensorler if f"{sensor['komut']}|" in k), None)
                            if ayar and ayar.get('veri_formati') == 'FLOAT':
                                veriler[k] = round(ham_veriyi_floata_cevir(ham_deger), 2)
                            else:
                                veriler[k] = ham_deger
                    except json.JSONDecodeError: pass 
                son_veriler[port_adi] = veriler
            except Exception as e: pass
            finally:
                if s: s.close()
        time.sleep(1)

def alarm_kontrol_motoru():
    global aktif_alarmlar_listesi
    onceki_tetiklenenler = {} 
    
    while True:
        suan_aktif = []
        alarmlar = alarmlari_getir()
        gecmis = gecmis_getir()
        cihazlar = cihazlari_getir() 
        yeni_gecmis_eklendi = False
        
        for alarm in alarmlar:
            if 'cihaz_isim' not in alarm:
                c = next((x for x in cihazlar if x['ip'] == alarm['ip'] and str(x['port']) == str(alarm['port'])), None)
                alarm['cihaz_isim'] = c['isim'] if c else "Bilinmeyen Cihaz"

            cihaz_anahtari = f"{alarm['ip']}:{alarm['port']}"
            kisa_komut = alarm['komut'].split('|')[0]
            alarm_id = f"{cihaz_anahtari}_{kisa_komut}_{alarm['sart']}_{alarm['deger']}"
            
            if cihaz_anahtari in son_veriler:
                deger = son_veriler[cihaz_anahtari].get(kisa_komut)
                if deger is not None:
                    try:
                        mevcut = float(deger)
                        hedef = float(alarm['deger'])
                        sart = alarm['sart']
                        durum = False
                        
                        if sart == '>' and mevcut > hedef: durum = True
                        elif sart == '<' and mevcut < hedef: durum = True
                        elif sart == '==' and mevcut == hedef: durum = True
                        
                        if durum:
                            tetiklenen = alarm.copy()
                            tetiklenen['anlik_deger'] = mevcut
                            suan_aktif.append(tetiklenen)
                            
                            if not onceki_tetiklenenler.get(alarm_id):
                                onceki_tetiklenenler[alarm_id] = True
                                zaman = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                                is_dijital = 'BOOL' in alarm['komut']
                                kural_metni = ("AÇIK" if hedef == 1 else "KAPALI") if is_dijital else f"{kisa_komut} {sart} {hedef}"
                                anlik_metin = ("AÇIK" if mevcut >= 1 else "KAPALI") if is_dijital else mevcut
                                
                                gecmis.append({
                                    "zaman": zaman, "cihaz_isim": alarm['cihaz_isim'], "ip": alarm['ip'],
                                    "komut": kisa_komut, "mesaj": alarm['mesaj'], "kural": kural_metni, "tetik_deger": anlik_metin
                                })
                                yeni_gecmis_eklendi = True
                                log_ekle("ALARM", f"Alarm Tetiklendi: {alarm['cihaz_isim']} - {alarm['mesaj']}")
                                
                                mail_metni = f"Zaman: {zaman}\nCihaz: {alarm['cihaz_isim']} ({alarm['ip']})\nSensör Adresi: {kisa_komut}\nİhlal Edilen Kural: {kural_metni}\nSistemden Okunan Anlık Değer: {anlik_metin}"
                                threading.Thread(target=alarm_maili_at, args=(alarm['mesaj'], mail_metni)).start()
                        else:
                            onceki_tetiklenenler[alarm_id] = False
                    except: pass
        if yeni_gecmis_eklendi: gecmis_kaydet(gecmis)
        aktif_alarmlar_listesi = suan_aktif
        time.sleep(1)

threading.Thread(target=arka_plan_motoru, daemon=True).start()
threading.Thread(target=alarm_kontrol_motoru, daemon=True).start()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if "misafir_giris" in request.form:
            session["kullanici"] = "misafir"
            session["rol"] = "misafir"
            log_ekle("SİSTEM", "Bir kullanıcı 'misafir' butonunu kullanarak giriş yaptı.")
            flash("Misafir olarak giriş yapıldı. Sadece izleme yetkiniz var.", "info")
            return redirect(url_for("index"))

        # NORMAL (ŞİFRELİ) GİRİŞ YAPILDIYSA
        kullanicilar = kullanicilari_getir()
        k_adi = request.form.get("kullanici_adi")
        sifre = request.form.get("sifre")
        
        if k_adi in kullanicilar and kullanicilar[k_adi]["sifre"] == sifre:
            session["kullanici"] = k_adi
            session["rol"] = kullanicilar[k_adi]["rol"]
            log_ekle("SİSTEM", f"'{k_adi}' sisteme giriş yaptı.")
            flash(f"Hoş geldiniz, {k_adi.upper()}!", "success")
            return redirect(url_for("index"))
        else:
            flash("Hatalı kullanıcı adı veya şifre!", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    k_adi = session.get('kullanici', 'Bilinmeyen')
    session.clear()
    log_ekle("SİSTEM", f"'{k_adi}' sistemden çıkış yaptı.")
    flash("Başarıyla çıkış yaptınız.", "info")
    return redirect(url_for("login"))


# --- SAYFALAR VE APİ'LER ---
@app.route("/")
@login_required
def index(): 
    return render_template("index.html", cihazlar=cihazlari_getir())

@app.route("/api/ping/<ip>")
@login_required
def ping_at(ip):
    is_windows = platform.system().lower() == 'windows'
    komut = ['ping', '-n' if is_windows else '-c', '1', ip]
    startupinfo = None
    if is_windows:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        subprocess.check_output(komut, startupinfo=startupinfo, stderr=subprocess.STDOUT, timeout=2)
        return jsonify({"bagli": True})
    except: return jsonify({"bagli": False})

@app.route("/cihaz_ekle", methods=["GET", "POST"])
@admin_required
def cihaz_ekle():
    if request.method == "POST":
        isim = request.form.get("isim", "").strip()
        ip = request.form.get("ip_adresi", "").strip()
        port = request.form.get("tcp_port", "").strip()
        if not isim or not ip or not port:
            flash("Lütfen tüm alanları doldurunuz.", "warning")
            return redirect(url_for('cihaz_ekle'))
        if not ip_gecerli_mi(ip) and ip != "localhost":
            flash("Geçersiz IP adresi formatı!", "danger")
            return redirect(url_for('cihaz_ekle'))
        cihazlar = cihazlari_getir()
        for c in cihazlar:
            if c.get('ip') == ip and str(c.get('port')) == str(port):
                flash("Bu IP ve Port adresiyle zaten bir cihaz kayıtlı!", "danger")
                return redirect(url_for('cihaz_ekle'))
        cihazlar.append({"isim": isim, "ip": ip, "port": port, "sensorler": []})
        cihazlari_kaydet(cihazlar)
        log_ekle("CİHAZ", f"Yeni cihaz sisteme kaydedildi: {isim} ({ip}:{port})")
        flash(f"'{isim}' başarıyla eklendi!", "success")
        return redirect(url_for("index"))
    return render_template("cihaz_ekle.html")

@app.route("/cihaz_yapilandir", methods=["GET", "POST"])
@admin_required
def cihaz_yapilandir():
    portlar = [port.device for port in serial.tools.list_ports.comports() if 'USB' in port.hwid]
    if not portlar: 
        portlar = [port.device for port in serial.tools.list_ports.comports()]

    if request.method == "POST":
        secilen_port = request.form.get("com_port")
        if not secilen_port:
            flash("Lütfen bir COM portu seçin.", "danger")
            return redirect(url_for("cihaz_yapilandir"))

        veri = {
            "wifi_ssid": request.form.get("wifi_ssid", ""),
            "wifi_sifre": request.form.get("wifi_sifre", ""),
            "cihaz_ip": request.form.get("cihaz_ip", ""),
            "cihaz_port": request.form.get("cihaz_port", ""),
            "plc_ip": request.form.get("plc_ip", ""),
            "plc_port": request.form.get("plc_port", "")
        }

        try:
            ser = serial.Serial(secilen_port, 9600, timeout=2)
            time.sleep(2)
            ser.reset_input_buffer()
            ser.write((json.dumps(veri) + '\n').encode('utf-8'))
            time.sleep(1)
            ser.close()
            
            log_ekle("AYAR", f"Donanım yapılandırması USB ({secilen_port}) üzerinden güncellendi.")
            flash("Ayarlar cihaza yüklendi! Cihaz yeniden başlıyor...", "success")
            return redirect(url_for("index"))
            
        except Exception as e:
            log_ekle("HATA", f"Seri port bağlantı hatası ({secilen_port}): Cihaz meşgul olabilir.")
            flash(f"Seri port meşgul veya bağlantı koptu.", "danger")

    return render_template("cihaz_yapilandir.html", portlar=portlar)

@app.route("/cihaz_sil/<ip>/<port>")
@admin_required
def cihaz_sil(ip, port):
    cihazlar = [c for c in cihazlari_getir() if not (c.get('ip') == ip and str(c.get('port')) == str(port))]
    cihazlari_kaydet(cihazlar)
    log_ekle("CİHAZ", f"Cihaz sistemden silindi: {ip}:{port}")
    flash("Cihaz silindi.", "info")
    return redirect(url_for("index"))

@app.route("/cihaz/<ip>/<port>")
@login_required
def cihaz_detay(ip, port):
    cihaz = next((c for c in cihazlari_getir() if c.get('ip') == ip and str(c.get('port')) == str(port)), None)
    if not cihaz: return redirect(url_for('index'))
    return render_template("cihaz_detay.html", cihaz=cihaz)

@app.route("/cihaz/<ip>/<port>/sensor_ekle", methods=["POST"])
@admin_required
def sensor_ekle(ip, port):
    isim = request.form.get("isim")
    adres_tipi = request.form.get("adres_tipi")
    adres_no = request.form.get("adres_no")
    veri_formati = request.form.get("veri_formati", "16BIT")
    prefix, veri_tipi = {"TIMER": ("T", "Analog"), "COIL": ("M", "Dijital"), "GIRIS": ("X", "Dijital"), "CIKIS": ("Y", "Dijital")}.get(adres_tipi, ("D", "Analog"))
    komut = f"{prefix}{adres_no}"
    secilen_format = veri_formati if veri_tipi == "Analog" else "BOOL"
    cihazlar = cihazlari_getir()
    for c in cihazlar:
        if c.get('ip') == ip and str(c.get('port')) == str(port):
            c.setdefault('sensorler', []).append({"isim": isim, "tip": veri_tipi, "komut": komut, "veri_formati": secilen_format})
            break
    cihazlari_kaydet(cihazlar)
    log_ekle("SENSÖR", f"Cihaza ({ip}) yeni adres eklendi: {isim} [{komut}]")
    flash(f"Sensör eklendi: {komut}", "success")
    return redirect(url_for('cihaz_detay', ip=ip, port=port))

@app.route("/cihaz/<ip>/<port>/sensor_sil/<int:index>")
@admin_required
def sensor_sil(ip, port, index):
    cihazlar = cihazlari_getir()
    for c in cihazlar:
        if c.get('ip') == ip and str(c.get('port')) == str(port):
            silinen = c['sensorler'].pop(index)
            cihazlari_kaydet(cihazlar)
            log_ekle("SENSÖR", f"Cihazdan ({ip}) adres silindi: {silinen['isim']} [{silinen['komut']}]")
            break
    return redirect(url_for('cihaz_detay', ip=ip, port=port))

@app.route("/api/veri/<ip>/<port>")
@login_required
def canli_veri_getir(ip, port):
    anahtar = f"{ip}:{port}"
    return jsonify({"veriler": son_veriler.get(anahtar, {})})

@app.route("/api/veri_yaz/<ip>/<port>", methods=["POST"])
@admin_required
def veri_yaz(ip, port):
    istek_verisi = request.json
    if not istek_verisi or 'komut' not in istek_verisi or 'deger' not in istek_verisi: return jsonify({"basari": False, "hata": "Eksik veri"}), 400
    komut = istek_verisi['komut']
    deger = istek_verisi['deger']
    s = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip, int(port)))
        yazma_paketi = json.dumps({"set": {komut: deger}}) + "\n"
        s.sendall(yazma_paketi.encode('utf-8'))
        yanit = s.recv(1024).decode('utf-8').strip()
        log_ekle("KONTROL", f"Kullanıcı cihaza veri yazdı: {ip} -> {komut.split('|')[0]} = {deger}")
        return jsonify({"basari": True, "yanit": yanit})
    except Exception as e: return jsonify({"basari": False, "hata": str(e)}), 500
    finally:
        if s: s.close()

@app.route("/toplu_izleme")
@login_required
def toplu_izleme():
    cihazlar = cihazlari_getir()
    toplu_liste = toplu_getir()
    gorsel_liste = []
    for item in toplu_liste:
        cihaz = next((c for c in cihazlar if c.get('ip') == item['ip'] and str(c.get('port')) == str(item['port'])), None)
        if cihaz:
            sensor = next((s for s in cihaz.get('sensorler', []) if s['komut'] == item['komut']), None)
            if sensor:
                gorsel_liste.append({"cihaz_isim": cihaz['isim'], "ip": cihaz['ip'], "port": cihaz['port'], "sensor": sensor})
    return render_template("toplu_izleme.html", cihazlar=cihazlar, toplu_liste=gorsel_liste)

@app.route("/toplu_ekle", methods=["POST"])
@admin_required
def toplu_ekle():
    secim = request.form.get("cihaz_secimi")
    komut = request.form.get("sensor_secimi")
    if secim and komut:
        ip, port = secim.split(":")
        liste = toplu_getir()
        if not any(x['ip'] == ip and str(x['port']) == str(port) and x['komut'] == komut for x in liste):
            liste.append({"ip": ip, "port": port, "komut": komut})
            toplu_kaydet(liste)
            log_ekle("İZLEME", f"Toplu İzleme ekranına adres eklendi: {ip} [{komut.split('|')[0]}]")
            flash("Sensör toplu izlemeye eklendi!", "success")
        else: flash("Bu sensör zaten listede var.", "warning")
    return redirect(url_for("toplu_izleme"))

@app.route("/toplu_sil/<int:index>")
@admin_required
def toplu_sil(index):
    liste = toplu_getir()
    if 0 <= index < len(liste):
        silinen = liste.pop(index)
        toplu_kaydet(liste)
        log_ekle("İZLEME", f"Toplu İzleme ekranından adres kaldırıldı: {silinen['ip']} [{silinen['komut'].split('|')[0]}]")
        flash("Sensör toplu izlemeden kaldırıldı.", "info")
    return redirect(url_for("toplu_izleme"))

@app.route("/api/toplu_veri")
@login_required
def api_toplu_veri(): 
    return jsonify(son_veriler)

@app.route("/alarmlar")
@login_required
def alarmlar_sayfasi():
    cihazlar = cihazlari_getir()
    alarmlar = alarmlari_getir()
    for alarm in alarmlar:
        if 'cihaz_isim' not in alarm:
            c = next((x for x in cihazlar if x['ip'] == alarm['ip'] and str(x['port']) == str(alarm['port'])), None)
            alarm['cihaz_isim'] = c['isim'] if c else "Bilinmeyen Cihaz"
    gecmis = gecmis_getir()
    for g in gecmis:
        if 'cihaz_isim' not in g:
            c = next((x for x in cihazlar if x['ip'] == g['ip']), None)
            g['cihaz_isim'] = c['isim'] if c else "Bilinmeyen Cihaz"
    gecmis.reverse()
    return render_template("alarmlar.html", cihazlar=cihazlar, alarmlar=alarmlar, gecmis_alarmlar=gecmis)

@app.route("/alarm_ekle", methods=["POST"])
@admin_required
def alarm_ekle():
    cihaz_secimi = request.form.get("cihaz_secimi")
    sensor_secimi = request.form.get("sensor_secimi")
    sart = request.form.get("sart")
    deger = request.form.get("deger")
    mesaj = request.form.get("mesaj")
    if cihaz_secimi and sensor_secimi and sart and deger is not None:
        ip, port = cihaz_secimi.split(":")
        cihaz_isim = "Bilinmeyen Cihaz"
        for c in cihazlari_getir():
            if c['ip'] == ip and str(c['port']) == str(port):
                cihaz_isim = c['isim']
                break
        liste = alarmlari_getir()
        yeni_alarm = {"cihaz_isim": cihaz_isim, "ip": ip, "port": port, "komut": sensor_secimi, "sart": sart, "deger": float(deger), "mesaj": mesaj}
        liste.append(yeni_alarm)
        alarmlari_kaydet(liste)
        log_ekle("ALARM", f"Yeni alarm kuralı oluşturuldu: {cihaz_isim} ({ip}) -> {mesaj}")
        flash("Alarm başarıyla kuruldu!", "success")
    return redirect(url_for("alarmlar_sayfasi"))

@app.route("/alarm_sil/<int:index>")
@admin_required
def alarm_sil(index):
    liste = alarmlari_getir()
    if 0 <= index < len(liste):
        silinen = liste.pop(index)
        alarmlari_kaydet(liste)
        log_ekle("ALARM", f"Alarm kuralı silindi: {silinen['ip']} -> {silinen['mesaj']}")
        flash("Alarm kuralı silindi.", "info")
    return redirect(url_for("alarmlar_sayfasi"))

@app.route("/gecmis_alarmlari_temizle")
@admin_required
def gecmis_alarmlari_temizle():
    gecmis_kaydet([]) 
    log_ekle("SİSTEM", "Kullanıcı geçmiş alarm kayıtlarını tamamen temizledi.")
    flash("Geçmiş alarm kayıtları tamamen temizlendi.", "success")
    return redirect(url_for("alarmlar_sayfasi"))

@app.route("/api/aktif_alarmlar")
@login_required
def api_aktif_alarmlar():
    cihazlar = cihazlari_getir()
    for alarm in aktif_alarmlar_listesi:
        if 'cihaz_isim' not in alarm:
            c = next((x for x in cihazlar if x['ip'] == alarm['ip'] and str(x['port']) == str(alarm['port'])), None)
            alarm['cihaz_isim'] = c['isim'] if c else "Bilinmeyen Cihaz"
    return jsonify(aktif_alarmlar_listesi)

@app.route("/sistem_ayarlari", methods=["GET", "POST"])
@admin_required
def sistem_ayarlari():
    ayarlar = ayarlari_getir()
    if request.method == "POST":
        ayarlar["mail_acik"] = request.form.get("mail_acik") == "on"
        ayarlar["gonderen"] = request.form.get("gonderen", "").strip()
        ayarlar["sifre"] = request.form.get("sifre", "").strip()
        alici_json = request.form.get("alici_listesi_json", "[]")
        try: ayarlar["alici"] = json.loads(alici_json)
        except: ayarlar["alici"] = []
        ayarlari_kaydet(ayarlar)
        log_ekle("AYAR", "Sistem bildirim ve mail ayarları güncellendi.")
        flash("Sistem ayarları başarıyla kaydedildi!", "success")
        return redirect(url_for("sistem_ayarlari"))
    return render_template("sistem_ayarlari.html", ayarlar=ayarlar)

@app.route("/sistem_loglari")
@admin_required
def sistem_loglari():
    loglar = loglari_getir()
    loglar.reverse() 
    return render_template("sistem_loglari.html", loglar=loglar)

@app.route("/kullanici_yonetimi", methods=["GET", "POST"])
@admin_required
def kullanici_yonetimi():
    kullanicilar = kullanicilari_getir()
    
    if request.method == "POST":
        # YENİ KULLANICI EKLEME İŞLEMİ
        if "yeni_kullanici" in request.form:
            yeni_ad = request.form.get("kullanici_adi", "").strip()
            sifre = request.form.get("sifre", "").strip()
            rol = request.form.get("rol", "misafir")
            
            if not yeni_ad or not sifre:
                flash("Kullanıcı adı ve şifre boş bırakılamaz!", "warning")
            elif yeni_ad in kullanicilar:
                flash("Bu kullanıcı adı zaten sistemde mevcut!", "danger")
            else:
                kullanicilar[yeni_ad] = {"sifre": sifre, "rol": rol}
                kullanicilari_kaydet(kullanicilar)
                log_ekle("AYAR", f"Yeni kullanıcı eklendi: {yeni_ad} ({rol})")
                flash(f"'{yeni_ad}' kullanıcısı başarıyla eklendi!", "success")
                return redirect(url_for("kullanici_yonetimi"))
                
        # KULLANICI SİLME İŞLEMİ
        elif "silinecek_kullanici" in request.form:
            silinecek = request.form.get("silinecek_kullanici")
            if silinecek == session.get("kullanici"):
                flash("Kendi hesabınızı silemezsiniz!", "danger")
            elif silinecek in kullanicilar:
                del kullanicilar[silinecek]
                kullanicilari_kaydet(kullanicilar)
                log_ekle("AYAR", f"Kullanıcı silindi: {silinecek}")
                flash(f"'{silinecek}' kullanıcısı silindi.", "info")
                return redirect(url_for("kullanici_yonetimi"))

    return render_template("kullanici_yonetimi.html", kullanicilar=kullanicilar)

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)
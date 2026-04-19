import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import json
import time

class CihazYapilandiriciApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ESP32 / PLC Yapılandırma Aracı")
        self.root.geometry("450x550") # Arayüz RS485 kalktığı için kısaldı
        self.root.resizable(False, False)
        self.root.configure(padx=20, pady=20)

        # --- STİLLER ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', font=('Segoe UI', 10))
        style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#007ACC')
        style.configure('TButton', font=('Segoe UI', 10, 'bold'))

        # --- 1. USB BAĞLANTISI ---
        ttk.Label(root, text="1. USB BAĞLANTISI (Yükleme İçin)", style='Header.TLabel').pack(anchor="w", pady=(0, 5))
        
        port_frame = ttk.Frame(root)
        port_frame.pack(fill="x", pady=5)
        
        self.port_kombosu = ttk.Combobox(port_frame, state="readonly", width=30)
        self.port_kombosu.pack(side="left", padx=(0, 10))
        
        yenile_btn = ttk.Button(port_frame, text="Yenile", command=self.portlari_listele, width=10)
        yenile_btn.pack(side="left")

        # --- 2. KABLOSUZ AĞ & CİHAZ AYARLARI ---
        ttk.Label(root, text="2. KABLOSUZ AĞ & CİHAZ AYARLARI", style='Header.TLabel').pack(anchor="w", pady=(15, 5))
        
        ag_frame = ttk.Frame(root)
        ag_frame.pack(fill="x", pady=5)
        
        ttk.Label(ag_frame, text="WiFi Adı (SSID):").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_ssid = ttk.Entry(ag_frame, width=20)
        self.ent_ssid.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(ag_frame, text="WiFi Şifresi:").grid(row=1, column=0, sticky="w", pady=2)
        self.ent_sifre = ttk.Entry(ag_frame, show="*", width=20)
        self.ent_sifre.grid(row=1, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(ag_frame, text="Cihaz Statik IP:").grid(row=2, column=0, sticky="w", pady=2)
        self.ent_cihaz_ip = ttk.Entry(ag_frame, width=20)
        self.ent_cihaz_ip.grid(row=2, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(ag_frame, text="Cihaz Portu:").grid(row=3, column=0, sticky="w", pady=2)
        self.ent_cihaz_port = ttk.Entry(ag_frame, width=10)
        self.ent_cihaz_port.insert(0, "502")
        self.ent_cihaz_port.grid(row=3, column=1, sticky="w", pady=2, padx=5)

        # --- 3. PLC HABERLEŞME AYARLARI (Sadece TCP) ---
        ttk.Label(root, text="3. PLC HABERLEŞME AYARLARI (MODBUS TCP)", style='Header.TLabel').pack(anchor="w", pady=(15, 5))
        
        self.frame_eth = ttk.Frame(root)
        self.frame_eth.pack(fill="x", pady=5)

        ttk.Label(self.frame_eth, text="PLC IP Adresi:").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_plc_ip = ttk.Entry(self.frame_eth, width=20)
        self.ent_plc_ip.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(self.frame_eth, text="PLC Port:").grid(row=1, column=0, sticky="w", pady=2)
        self.ent_plc_port = ttk.Entry(self.frame_eth, width=10)
        self.ent_plc_port.insert(0, "502")
        self.ent_plc_port.grid(row=1, column=1, sticky="w", pady=2, padx=5)

        # --- YÜKLE BUTONU ---
        self.btn_yukle = tk.Button(root, text="AYARLARI CİHAZA YÜKLE", bg="#007ACC", fg="white", font=("Segoe UI", 12, "bold"), command=self.ayarlari_yukle)
        self.btn_yukle.pack(fill="x", pady=(30, 0), ipady=5)

        self.portlari_listele()

    def portlari_listele(self):
        portlar = [p.device for p in serial.tools.list_ports.comports() if 'USB' in p.hwid]
        if not portlar:
            portlar = [p.device for p in serial.tools.list_ports.comports()]
        
        self.port_kombosu['values'] = portlar
        if portlar:
            self.port_kombosu.current(0)
        else:
            self.port_kombosu.set("Bağlı cihaz bulunamadı")

    def ayarlari_yukle(self):
        secilen_port = self.port_kombosu.get()
        if not secilen_port or secilen_port == "Bağlı cihaz bulunamadı":
            messagebox.showwarning("Uyarı", "Lütfen bir COM portu seçin! Cihazın USB ile bağlı olduğundan emin olun.")
            return

        ssid = self.ent_ssid.get().strip()
        sifre = self.ent_sifre.get().strip()

        if not ssid or not sifre:
            messagebox.showwarning("Uyarı", "WiFi Adı ve Şifresi boş bırakılamaz!")
            return

        veri = {
            "wifi_ssid": ssid,
            "wifi_sifre": sifre,
            "cihaz_ip": self.ent_cihaz_ip.get().strip(),
            "cihaz_port": self.ent_cihaz_port.get().strip() or "502",
            "plc_ip": self.ent_plc_ip.get().strip(),
            "plc_port": self.ent_plc_port.get().strip() or "502"
        }

        try:
            self.btn_yukle.config(text="YÜKLENİYOR...", state="disabled", bg="#f39c12")
            self.root.update()

            ser = serial.Serial(secilen_port, 9600, timeout=2)
            time.sleep(2) 
            ser.reset_input_buffer()
            
            gonderilecek_metin = json.dumps(veri) + '\n'
            ser.write(gonderilecek_metin.encode('utf-8'))
            time.sleep(1)
            ser.close()

            messagebox.showinfo("Başarılı", "Ayarlar başarıyla ESP32'ye yüklendi!\nCihaz şu anda yeniden başlatılıyor.")
        except Exception as e:
            messagebox.showerror("Bağlantı Hatası", f"Cihaza veri gönderilirken hata oluştu:\n{str(e)}")
        finally:
            self.btn_yukle.config(text="AYARLARI CİHAZA YÜKLE", state="normal", bg="#007ACC")


if __name__ == "__main__":
    root = tk.Tk()
    app = CihazYapilandiriciApp(root)
    root.mainloop()
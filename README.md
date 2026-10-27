# GENIEACS INSTALL MULTITAB V2

Custom GenieACS UI Multi-Tab untuk manajemen FTTH / ONT (ZTE, Huawei, Fiberhome, MikroTik, dll) dengan tampilan modern, ringkas, responsif, dan informatif.

---

## Fitur Utama Multi-Tab V2

1. **Struktur Multi-Tab Ringkas (4 Tab Utama)**:
   - **Summary**: Identitas perangkat & seksi **Device Operational Status** (Optic RX Power, Suhu ONT, Mode PON, Uptime, Klien WiFi aktif) dengan indikator bulatan status visual yang bersih.
   - **WAN / LAN**: Konfigurasi WAN (PPPoE / IPoE), LAN Gateway, serta tabel **LAN Host Devices** (Host Name, IP, MAC, Interface, Status Aktif) dengan tombol *Summon*.
   - **WLAN**: Konfigurasi SSID WiFi, keamanan (WPA-PSK), Channel, serta tabel **WiFi Connected Clients** lengkap untuk 2.4GHz dan 5GHz (SSID 1 s/d SSID 6).
   - **USER / TR069**: Kredensial akun Web GUI ONT (SuperAdmin / User) dan parameter TR-069 ACS Settings (dengan penunjuk waktu _Last Inform_ real-time).

2. **Parameter Writable 2-Arah (Edit Langsung dari Web UI)**:
   - **`VlanID` (2-Way Writable)**: Mengubah VLAN ID ONT langsung dari Web GUI tanpa membuka Web ONT. Mendukung otomatis multi-vendor: Huawei (`X_HW_VLAN`), ZTE/ZICG (`X_ZTE-COM_VlanID`, `X_CMCC_VLANIDMark`), Fiberhome/CIOT/RTEG (`X_CT-COM_VlanID`), dan Broadcom/EPON/GPON.
   - **`WlanSSID` (2-Way Writable)**: Mengganti nama WiFi (SSID) ONT langsung dari Web GUI GenieACS.

3. **Bot AI & WhatsApp Baileys Gateway Terintegrasi**:
   - Terintegrasi langsung dengan gateway WhatsApp Baileys (port 7559) dan GenieACS AI Agent Engine (port 7558).
   - Menu dashboard web **`🤖 Bot AI & WA`** langsung di navbar GenieACS UI (memantau status koneksi, scan QR code WhatsApp, dan log interaksi).
   - Mendukung perintah WhatsApp & Telegram interaktif untuk teknisi dan pelanggan: cek redaman optical RX, cek IP/status PPPoE, reboot ONT, dan ganti sandi WiFi.
   - Dilengkapi tool CLI interaktif `set-bot` di terminal server untuk setting token, nomor WhatsApp admin, nama brand, serta scan QR code (`set-bot qr`).

4. **1-Click Dark Mode & Light Mode Theme**:
   - Tombol pengubah tema (`🌙 Dark` / `☀️ Default`) di menu pengguna pojok kanan atas.
   - Preferensi tema tersimpan otomatis di `localStorage` per-browser.
   - Styling kontras tinggi yang nyaman di mata untuk pemantauan NOC.

5. **Dukungan Multi-Vendor Inform (ONT TR-098 & MikroTik TR-181)**:
   - Provision `inform` secara cerdas membedakan perangkat standar TR-098 (`InternetGatewayDevice.ManagementServer.*`) dan router MikroTik TR-181 (`Device.ManagementServer.*`), mencegah kegagalan sesi TR-069 Fault 9005.

6. **Indikator Status Warna Visual**:
   - **PON Mode**: 🔵 EPON (Biru), 🟢 GPON (Hijau), 🟠 Ethernet/Converter (Orange).
   - **Optic RX Power**: 🟢 Bagus (> -23 dBm), 🟡 Sedang (-23 s/d -24.9 dBm), 🔴 Kritis (<= -25 dBm).
   - **Device Temperature**: 🟢 Adem (<= 45 °C), 🟡 Anget (46 - 60 °C), 🟠 Panas (61 - 70 °C), 🔴 Overheat (> 70 °C).

7. **Diagnostik Terformat & Ringkas**:
   - **`uptimeDevice`**: Format uptime rapi manusiawi (`Xd XX:XX:XX`).
   - **`temp`**: Suhu chip transceiver pintar yang mendukung konversi nilai byte & float.
   - **`userconnected`**: Penghitung otomatis total klien aktif WiFi.
   - Halaman `/devices` efisien dengan penataan kolom optimal dan tombol summon cepat.

8. **Engine Virtual Parameters Multi-Vendor Cerdas**:
   - Mendukung deteksi otomatis: **ZTE (F609, F670, F660, F663, F460, dll), Huawei, FiberHome, V-SOL, C-Data, D-Link, HSGQ, TDTC, GGCLink, CMHI, Alcatel-Lucent (ALCL), dan MikroTik**.
   - Kredensial SuperAdmin & User dinamis untuk berbagai tipe ONT.

---

## Cara Penggunaan (Fresh Install)

```bash
apt update && apt install git curl -y
```

```bash
git clone https://github.com/SN1303/GACS-multitabV2.git
cd GACS-multitabV2
```

```bash
chmod +x install.sh && ./install.sh
```

---

## Update untuk Server GenieACS yang Sudah Terpasang

Jika sudah memiliki instalasi GenieACS sebelumnya dan ingin menerapkan update UI Multi-Tab V2, Virtual Parameters, Dark Mode, dan dukungan multi-vendor terbaru:

```bash
cd /root/GACS-multitabV2
git pull origin experimental

# Update konfigurasi database (hanya memperbarui config, provisions, dan virtualParameters; aman untuk data perangkat)
mongorestore --db genieacs --collection virtualParameters --drop db/virtualParameters.bson
mongorestore --db genieacs --collection provisions --drop db/provisions.bson
mongorestore --db genieacs --collection config --drop db/config.bson

# Update file UI frontend & style
cp -r genieacs/public/* $(npm root -g)/genieacs/public/

# Restart layanan GenieACS
systemctl restart genieacs-{cwmp,nbi,ui,fs}
```

> **Catatan**: Setelah restart layanan, lakukan **Hard Refresh** (`Ctrl + Shift + R` atau `Ctrl + F5`) pada browser klien untuk memuat cache frontend baru dan mengaktifkan fitur Dark Mode.

---

## Instalasi Menggunakan Docker

### Persyaratan

- Docker Engine 20.10.0 atau lebih baru
- Docker Compose 2.0.0 atau lebih baru
- Minimal 2GB RAM (4GB direkomendasikan)
- Minimal 10GB ruang disk

### Langkah-langkah Instalasi

1. **Clone Repository**

   ```bash
   git clone https://github.com/SN1303/GACS-multitabV2.git
   cd GACS-multitabV2
   ```

2. **Persiapan Direktori**

   ```bash
   mkdir -p db ext logs config
   chmod -R 777 db ext logs
   ```

3. **Konfigurasi Awal**

   - Salin file konfigurasi contoh:
     ```bash
     cp config/genieacs.json.example config/genieacs.json
     ```
   - Edit file konfigurasi sesuai kebutuhan:
     ```bash
     nano config/genieacs.json
     ```

4. **Jalankan dengan Docker Compose**

   ```bash
   # Bangun dan jalankan container
   docker-compose up -d --build

   # Pantau log
   docker-compose logs -f
   ```

5. **Akses GenieACS**
   - Web UI: `http://localhost:3000` (atau IP Server Anda)
     - Username default: `admin`
     - Password default: `admin`
   - API NBI: `http://localhost:7557`
   - CWMP (TR-069): `http://your-server-ip:7547`

### Perintah Penting Docker

```bash
# Menjalankan perintah di dalam container
docker-compose exec genieacs <command>

# Melihat log
docker-compose logs -f

# Menghentikan semua layanan
docker-compose down

# Restart layanan
docker-compose restart
```

---

## Konfigurasi Port Default

| Layanan                | Port   | Keterangan                             |
| ---------------------- | ------ | -------------------------------------- |
| **GenieACS UI**        | `3000` | Tampilan Web GUI Frontend              |
| **GenieACS CWMP**      | `7547` | Port koneksi TR-069 dari ONT           |
| **GenieACS NBI (API)** | `7557` | Northbound API untuk automasi & preset |
| **GenieACS FS**        | `7567` | File server untuk firmware update      |
| **Bot AI Agent**       | `7558` | Web Dashboard & API Agent GenieACS     |
| **WhatsApp Gateway**   | `7559` | Baileys Gateway status & QR endpoint   |

---

## Credits & Acknowledgements

Proyek ini dibangun dan dikembangkan berkat inspirasi, kontribusi, serta dokumentasi dari para pengembang dan komunitas TR-069 / GenieACS Indonesia:

- **[GenieACS Core Team](https://genieacs.com/)**: Pembuat dan pengembang utama platform open-source GenieACS TR-069 Auto Configuration Server.
- **[Bery Indo (beryindo/genieacs)](https://github.com/beryindo/genieacs)**: Basis repositori, instalasi, dan penyedia konsep TR-069 GenieACS untuk komunitas ISP Indonesia.
- **[Alijaya Net (alijayanet/genieacs-multitab-mod)](https://github.com/alijayanet/genieacs-multitab-mod)**: Konsep dan inspirasi pengembangan UI Multi-Tab, VLAN ID multi-vendor, dan Dark Mode theme.
- **[R-Tech (R-Tech Support & Script)](https://wa.me/628985560932)**: Pengembangan engine script *Virtual Parameters* multi-vendor cerdas (dukungan multi-model ZTE, V-SOL, C-Data, D-Link, HSGQ, TDTC, Fiberhome, Huawei, Nokia/Alcatel, regresi linier suhu, dan deteksi otomatis PON mode).
- **[Safrin Network (safrinnetwork/GACS-Ubuntu-22.04)](https://github.com/safrinnetwork/GACS-Ubuntu-22.04)**: Kontribusi otomasi script installer dan konfigurasi GenieACS di Ubuntu.
- **Komunitas TR-069 GenieACS Indonesia**: Rekan-rekan teknisi NOC dan pegiat RT-RW Net yang terus berbagi parameter data model ONT (ZTE, Huawei, Fiberhome, MikroTik, dll).

---

## Lisensi & Kontribusi

Silakan berkontribusi, membuka _pull request_, atau menyesuaikan untuk kebutuhan operasional jaringan FTTH masing-masing.

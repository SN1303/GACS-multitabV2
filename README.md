# GENIEACS INSTALL MULTITAB V2

Custom GenieACS UI Multi-Tab untuk manajemen FTTH / ONT (ZTE, Huawei, Fiberhome, dll) dengan tampilan modern, ringkas, dan informatif.

---

## Fitur Utama Multi-Tab V2

1. **Struktur Multi-Tab Ringkas (4 Tab Utama)**:
   - **Summary**: Informasi identitas perangkat & seksi **Device Operational Status** (Optic RX Power, Suhu ONT, Mode PON, Uptime, Klien WiFi aktif) dengan indikator bulatan warna status yang bersih.
   - **WAN / LAN**: Penggabungan informasi konfigurasi WAN (PPPoE / IPoE) dan LAN Configuration dalam satu tab.
   - **WLAN**: Konfigurasi SSID WiFi, keamanan (WPA-PSK), dan channel.
   - **USER / TR069**: Penggabungan kredensial akun Web GUI ONT (SuperAdmin / User) dan parameter TR-069 ACS Settings (dengan penunjuk waktu _Last Inform_ real).

2. **Indikator Status Warna Visual**:
   - **PON Mode**: 🔵 EPON (Biru), 🟢 GPON (Hijau), 🟠 Ethernet/Converter (Orange).
   - **Optic RX Power**: 🟢 Bagus (< -23 dBm), 🟡 Sedang (-23 s/d -26 dBm), 🔴 Kritis (>= -26 dBm).
   - **Device Temperature**: 🟢 Adem (<= 45 °C), 🟡 Hangat (46 - 60 °C), 🔴 Panas (> 60 °C).

3. **Halaman Perangkat (`/devices`) Efisien**:
   - Kolom tabel ringkas & padat tanpa duplikasi.
   - Kolom _Uptime_ diletakkan tepat di depan _Last Inform_.
   - Parameter _Active WiFi Clients_ menghitung seluruh klien yang terhubung pada semua SSID (1 - 8).

4. **Kredensial Akun Web GUI Dinamis**:
   - Terintegrasi langsung dengan `VirtualParameters.superAdmin/superPassword` dan `userAdmin/userPassword` untuk berbagai tipe ONT ZTE, Huawei, dan Fiberhome.

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

Jika sudah memiliki instalasi GenieACS sebelumnya dan ingin menerapkan update UI Multi-Tab V2 terbaru:

```bash
cd /root/GACS-multitabV2
git pull origin main
cp genieacs/public/app.js $(npm root -g)/genieacs/public/app.js
systemctl restart genieacs-ui
```

> **Catatan**: Setelah restart `genieacs-ui`, lakukan **Hard Refresh** (`Ctrl + Shift + R`) pada browser klien untuk membersihkan cache frontend.

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

---

## Credits & Acknowledgements

Proyek ini dibangun dan dikembangkan berkat inspirasi, kontribusi, serta dokumentasi dari para pengembang dan komunitas TR-069 / GenieACS Indonesia:

- **[GenieACS Core Team](https://genieacs.com/)**: Pembuat dan pengembang utama platform open-source GenieACS TR-069 Auto Configuration Server.
- **[Bery Indo (beryindo/genieacs)](https://github.com/beryindo/genieacs)**: Basis repositori, instalasi, dan penyedia konsep TR-069 GenieACS untuk komunitas ISP Indonesia.
- **[R-Tech (R-Tech Support & Script)](https://wa.me/628985560932)**: Pengembangan engine script *Virtual Parameters* multi-vendor cerdas (dukungan multi-model ZTE, V-SOL, C-Data, D-Link, HSGQ, TDTC, Fiberhome, Huawei, Nokia/Alcatel, regresi linier suhu, dan deteksi otomatis PON mode).
- **[Alijaya Net (alijayanet/genieacs-multitab)](https://github.com/alijayanet/genieacs-multitab)**: Inspirasi awal kustomisasi antarmuka UI Multi-Tab GenieACS.
- **[Safrin Network (safrinnetwork/GACS-Ubuntu-22.04)](https://github.com/safrinnetwork/GACS-Ubuntu-22.04)**: Kontribusi otomasi script installer dan konfigurasi GenieACS di Ubuntu.
- **Komunitas TR-069 GenieACS Indonesia**: Rekan-rekan teknisi NOC dan pegiat RT-RW Net yang terus berbagi parameter data model ONT (ZTE, Huawei, Fiberhome, dll).

---

## Lisensi & Kontribusi

Silakan berkontribusi, membuka _pull request_, atau menyesuaikan untuk kebutuhan operasional jaringan FTTH masing-masing.

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
   - **Optic RX Power**: 🟢 Bagus (> -23 dBm), 🟡 Sedang (-23 s/d -24.9 dBm), 🔴 Kritis (<= -25 dBm).
   - **Device Temperature**: 🟢 Adem (<= 45 °C), 🟡 Anget (46 - 60 °C), 🟠 Panas (61 - 70 °C), 🔴 Overheat (> 70 °C).

3. **Halaman Perangkat (`/devices`) Efisien**:
   - Kolom tabel ringkas & padat tanpa duplikasi.
   - Kolom _Uptime_ diletakkan tepat di depan _Last Inform_.
   - Parameter _Active WiFi Clients_ menghitung seluruh klien yang terhubung pada semua SSID (1 - 8).

4. **Kredensial Akun Web GUI Dinamis**:
   - Terintegrasi langsung dengan `VirtualParameters.superAdmin/superPassword` dan `userAdmin/userPassword` untuk berbagai tipe ONT ZTE, Huawei, dan Fiberhome.

5. **Engine Virtual Parameters Multi-Vendor Cerdas**:
   - Mendukung deteksi otomatis multi-vendor: **ZTE (F609, F670, F660, F663, F460, dll), Huawei, FiberHome, V-SOL, C-Data, D-Link, HSGQ, TDTC, GGCLink, CMHI, Alcatel-Lucent (ALCL), dan MikroTik**.
   - Dilengkapi konversi suhu chip regresi linier dan multi-path detection untuk Optical RX Power (15 jalur data model TR-069).
   - Overview Dashboard otomatis mengelompokkan perangkat berdasarkan model seri dan merk secara akurat.

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
chmod +x install.sh && sudo ./install.sh
```

### Login Default

| Username | Password    | Role  |
| -------- | ----------- | ----- |
| `admin`  | `admin`     | admin |

> ⚠️ **Segera ganti password `admin`** lewat **Admin → Users** setelah instalasi. Password yang sudah diganti tidak akan tertimpa saat update.

---

## Update untuk Server GenieACS yang Sudah Terpasang

`install.sh` yang sama otomatis masuk **mode UPDATE** jika GenieACS sudah terpasang di server:

```bash
cd /root/GACS-multitabV2
git pull origin main
sudo bash install.sh
```

| Komponen                                                       | Saat update                                                        |
| -------------------------------------------------------------- | ------------------------------------------------------------------ |
| Node.js, MongoDB, paket GenieACS                               | Tidak di-install ulang (jika service mati, cukup dinyalakan)       |
| `genieacs.env`, file systemd, logrotate                        | Ditulis ulang sesuai script, **JWT secret lama dipertahankan**     |
| UI Multi-Tab (`genieacs/`)                                     | Diperbarui                                                         |
| Config, Presets, Provisions, Virtual Parameters, Permissions   | **Ditimpa** dengan isi folder `db/`                                |
| Users                                                          | User lama & password-nya tetap; user baru dari `db/` ditambahkan   |
| Data perangkat ONT, tag/lokasi, task, fault                    | **Aman, tidak disentuh**                                           |

> **Perhatian**: perubahan Config/Preset/Provision/Virtual Parameter yang dibuat langsung lewat UI di server akan tertimpa. Simpan perubahan tersebut ke folder `db/` terlebih dahulu jika ingin dipertahankan.
>
> Edit manual di `/opt/genieacs/genieacs.env` juga tertimpa (kecuali JWT secret). Masukkan pengaturan tambahan ke `install.sh`.
>
> Pada update pertama dari versi lama (JWT secret masih `secret`), semua user akan ter-logout satu kali karena secret diganti dengan nilai acak.

Setelah update, lakukan **Hard Refresh** (`Ctrl + Shift + R` atau `Ctrl + F5`) pada browser untuk membersihkan cache frontend.

---

## Reinstall Bersih (Hapus Total)

```bash
sudo bash reinstall.sh
```

> ⚠️ **SELURUH DATABASE GENIEACS DIHAPUS PERMANEN**: semua data perangkat ONT, tag/lokasi, task, fault, user, dan konfigurasi buatan sendiri. ONT akan muncul kembali setelah inform berikutnya, tetapi tag & riwayatnya hilang. Backup terlebih dahulu jika perlu:
>
> ```bash
> mongodump --db genieacs --out /root/backup-genieacs
> ```
>
> Untuk sekadar update tanpa kehilangan data, gunakan `install.sh`.

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
| **GenieACS NBI (API)** | `7557` | Northbound API untuk automasi & preset. **Hanya listen di `127.0.0.1`** |
| **GenieACS FS**        | `7567` | File server untuk firmware update      |

### Catatan Keamanan

- **NBI tidak memiliki autentikasi**, sehingga installer membatasinya ke `127.0.0.1` (`GENIEACS_NBI_INTERFACE`). Script automasi yang memakai NBI harus dijalankan di server GenieACS itu sendiri.
- **JWT secret UI** (`GENIEACS_UI_JWT_SECRET` di `/opt/genieacs/genieacs.env`) dibuat acak saat instalasi. Jangan sebarkan isi file ini: siapa pun yang memegang nilai tersebut bisa login sebagai admin tanpa password.
- Fallback MongoDB via Docker hanya dibuka ke `127.0.0.1:27017`.
- Role `user` memiliki akses tulis ke Provisions/Presets/Config. Turunkan ke akses baca (2) sebelum memberikan role ini ke teknisi.

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

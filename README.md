# QoS CAKE Adaptive Suite untuk STB Router (Skripsi)

Repositori ini berisi suite aplikasi terintegrasi untuk mengimplementasikan dan memantau **Smart Queue Management (SQM) CAKE Adaptive** pada router berbasis STB (Single Board Computer/Armbian). Proyek ini dirancang secara modular dan profesional sebagai bahan praktis penelitian skripsi jaringan.

Tujuan dari proyek ini adalah mengatasi kelemahan parameter Round Trip Time (RTT) statis pada algoritma SQM CAKE (default 100ms) dengan mengadaptasikannya secara dinamis berdasarkan kondisi latensi jaringan aktif. Dengan demikian, latensi/bufferbloat tetap rendah dan throughput tetap optimal pada berbagai kecepatan internet.

---

## 🚀 Fitur Utama

1. **Auto-RTT Adaptive Daemon (`cake_adaptive.py`)**
   * Berjalan di latar belakang sebagai systemd service.
   * Mengukur RTT secara real-time berdasarkan *minimum TCP RTT* dari soket aktif (`ss -ti`) dan beralih ke *ping fallback* ke gateway terdekat jika tidak ada aktivitas TCP.
   * Mengatur parameter RTT pada CAKE (10ms, 30ms, atau 100ms) secara dinamis menggunakan pengendali logika Hysteresis guna menghindari flapping (qdisc jitter).
2. **Dashboard Web Monitor Premium (`web_monitor/`)**
   * Antarmuka web modern dengan gaya *Glassmorphism Dark Mode* berbasis HTML, Vanilla CSS, dan JavaScript (Chart.js).
   * **Live Speed Chart:** Memantau kecepatan unduh (download) dan unggah (upload) klien secara real-time (interval 1 detik).
   * **Active Connections List:** Memantau seluruh koneksi TCP & UDP yang aktif beserta nama proses sistem, alamat IP, dan port asal/tujuan.
   * **ISP Simulator Limiter:** Panel prasetel interaktif untuk membatasi kecepatan WAN/LAN guna mensimulasikan paket kecepatan ISP (100 Mbps, 50 Mbps, 30 Mbps, 10 Mbps) untuk kebutuhan pengujian.
   * **Service Controller:** Mengaktifkan, mematikan, atau me-restart daemon QoS langsung dari antarmuka web.
3. **Automated Windows Installer Orchestrator (`install.py`)**
   * Skrip Python di sisi Windows untuk memasang seluruh kebutuhan STB dari jarak jauh (remote installation) via SSH/SFTP.
   * Mengotomatiskan instalasi dependensi, kloning repositori kustom, menambal (patch) kompatibilitas kernel module pada linux kernel modern (6.x), kompilasi `sch_cake.ko` out-of-tree, kompilasi utilitas `tc` (iproute2-mq), registrasi systemd, serta pengunggahan file web monitor.
4. **Cleanup Tool (`scripts/cleanup.py`)**
   * Membantu memulihkan STB ke keadaan default (menghapus rules `tc`, mematikan systemd service, dan menghapus namespace simulasi).

---

## 📂 Struktur Repositori

```text
qos-cake-adaptive/
├── install.py                 # Windows Orchestrator Installer (SSH & SFTP)
├── README.md                  # Dokumentasi Lengkap Proyek (Bahasa Indonesia)
├── src/
│   ├── cake_adaptive.py       # Python Daemon Core (Latency Controller)
│   ├── cake-adaptive.service  # Systemd Service untuk Daemon CAKE
│   └── web-monitor.service    # Systemd Service untuk Web Dashboard Flask
├── web_monitor/
│   ├── app.py                 # Backend Flask (API Status, Speed & Limiter)
│   └── templates/
│       └── index.html         # Frontend Dashboard Premium (Chart & Interface)
└── scripts/
    └── cleanup.py             # Script Pembersihan STB (Dijalankan langsung di STB)
```

---

## ⚙️ Persyaratan Sistem

### Sisi Windows (PC Pengembang)
* Python 3.x terinstal.
* Library Python `paramiko` terpasang:
  ```bash
  pip install paramiko
  ```

### Sisi STB Target (Router)
* OS Linux berbasis Debian/Armbian (direkomendasikan kernel 5.x atau 6.x).
* Akses SSH dengan hak akses root/sudoer enabled.
* Port `5000` tidak sedang digunakan (untuk Flask Web Monitor).

---

## 📥 Panduan Instalasi (Otomatis)

1. Pastikan STB target menyala dan terhubung ke jaringan lokal yang sama dengan PC Windows Anda.
2. Edit kredensial STB pada file `install.py` di sisi Windows jika terdapat perbedaan IP, username, atau password:
   ```python
    STB_IP = "192.168.1.21"
    STB_USER = "freischutz"
    STB_PASS = "kiken"
    ```
3. Jalankan penginstal dari terminal Windows Anda:
   ```bash
   python install.py
   ```
4. Penginstal akan melakukan kompilasi modul kernel dan `tc`, menyalin file sistem, mendaftarkan service, dan menyalakan Web Monitor.
5. Setelah selesai, buka browser Anda dan akses:
   ```text
   http://192.168.1.21:5000

   ```

---

## 📊 Pengujian & Simulasi (Skripsi)

Untuk memfasilitasi pengujian skripsi di lingkungan lokal tanpa mengganggu internet rumah secara fisik, proyek ini menyediakan skrip untuk membuat topologi simulasi menggunakan Linux Network Namespaces.

### Topologi Simulasi
* Namespace `ns_client` (10.0.1.2) - Mensimulasikan PC klien.
* Namespace `ns_isp` (10.0.2.2) - Mensimulasikan server internet / ISP.
* Namespace Utama (STB Router) - Menjembatani routing dan menjalankan SQM CAKE Adaptive pada interface `veth_rtr_lan`.

Anda dapat mengaktifkan limiter pada dashboard untuk mensimulasikan pembatasan bandwidth ISP dari ujung jaringan (interface WAN) ke kecepatan tertentu, kemudian mengamati grafik penurunan bufferbloat secara real-time pada dashboard Web Monitor.

---

## 🧹 Cara Pembersihan (Reset)

Jika ingin menghapus seluruh instalasi CAKE Adaptive, menghentikan layanan, dan mengembalikan STB ke keadaan default:
1. Masuk ke STB via SSH.
2. Unduh/salin file `scripts/cleanup.py` dan jalankan sebagai root:
   ```bash
   sudo python3 cleanup.py
   ```

---

## 📜 Lisensi
Proyek ini dilisensikan di bawah [MIT License](LICENSE). Anda bebas menggunakannya untuk kebutuhan penelitian akademik atau pengembangan pribadi dengan tetap mencantumkan atribusi repositori ini.

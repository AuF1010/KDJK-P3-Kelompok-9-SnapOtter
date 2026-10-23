<h1 align="center">
  SnapOtter
</h1>

[Sekilas Tentang](#sekilas-tentang) | [Instalasi](#instalasi) | [Konfigurasi](#konfigurasi) | [Maintenance](#maintenance) | [Otomatisasi](#otomatisasi) | [Cara Pemakaian](#cara-pemakaian) | [Pembahasan](#pembahasan) | [Referensi](#referensi)
:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:

# SnapOtter

## Identitas Kelompok

**Kelompok 9 - Paralel 3**

| No. | NIM | Nama |
|:---:|---|---|
| 1 | M0403241130 | Faris Ambar Susilo |
| 2 | M0403241150 | Khalifah Azka Hikari |
| 3 | M0403241151 | Aufa Alifiyanto |
| 4 | M0403241165 | Faqih Sahar Ramadhan |
| 5 | M0403241047 | Azahra Salsabila |

## Sekilas Tentang

SnapOtter merupakan aplikasi web *self-hosted* berbasis sumber terbuka (*open-source*) yang dirancang khusus sebagai alat manajemen dan konversi media yang komprehensif. Aplikasi ini memungkinkan pengguna untuk mengunggah, memproses, mengompresi, serta mengubah format berbagai jenis berkas media (seperti gambar, dokumen, dan video) langsung melalui satu antarmuka peramban tanpa perlu bergantung pada layanan pihak ketiga.

Dengan menggunakan SnapOtter secara lokal di server mandiri, privasi dan keamanan data pengguna sangat terjamin karena seluruh proses *transcoding* dan modifikasi berkas dieksekusi murni di dalam server tersebut. Pengguna tidak perlu khawatir berkas sensitif mereka disalin atau disimpan oleh layanan konverter publik di internet.

Dalam proyek ini, SnapOtter dipilih sebagai aplikasi web yang diimplementasikan untuk memenuhi tugas mata kuliah Komunikasi Data dan Jaringan Komputer. Implementasi dilakukan pada lingkungan virtual menggunakan sistem operasi Ubuntu Server, dengan memanfaatkan ekosistem Docker (Docker Engine dan Docker Compose) untuk memfasilitasi isolasi layanan. Sistem ini mengandalkan PostgreSQL sebagai basis data utama, Redis sebagai pengelola antrean (*message broker*), dan Caddy sebagai *reverse proxy* otomatis.

Pengujian dilakukan secara langsung pada layanan Cloud VPS dengan mengakses SnapOtter melalui peramban menggunakan domain yang telah dikonfigurasi (`snapotterlab.web.id`). Tahap selanjutnya meliputi penyelesaian dokumentasi, optimalisasi penggunaan memori server, serta pengujian fungsionalitas pemrosesan media.

## Instalasi

### Prasyarat

Sebelum melakukan instalasi SnapOtter, diperlukan beberapa perangkat lunak dan lingkungan server yang memadai mengingat pemrosesan media membutuhkan sumber daya komputasi. Pada proyek ini, instalasi dilakukan dengan spesifikasi sebagai berikut:

- **Sistem Operasi:** VPS Ubuntu 24.04.4 LTS (Noble Numbat) 64-bit.
- **Spesifikasi Perangkat Keras:** 2 vCPU, RAM 2 GB, dan Penyimpanan 40 GB.
- **Akses Jaringan:** Akses SSH (IP Publik: `43.173.19.49`) untuk mengelola server.
- **Domain:** `snapotterlab.web.id`
- **Container Engine:** Docker Engine v29.9.2 dan Docker Compose v5.6.1.
- **Web Server / Reverse Proxy:** Caddy v2.6.2 (sekaligus menangani HTTPS via Let's Encrypt).

### Langkah Instalasi

#### 1. Memperbarui dan Mempersiapkan Sistem

Hubungkan ke VPS melalui SSH menggunakan terminal:

```bash
ssh ubuntu@43.173.19.49
```

Perbarui daftar paket Ubuntu dan pasang alat pengunduh internet (`curl`) serta sertifikat keamanan (`ca-certificates`):

```bash
sudo apt update
sudo apt install -y ca-certificates curl
```

#### 2. Menginstal Docker Engine dan Compose

Tambahkan *repository* resmi Docker agar sistem mengambil versi stabil terbaru yang sesuai dengan nama sandi Ubuntu (Noble):

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL [https://download.docker.com/linux/ubuntu/gpg](https://download.docker.com/linux/ubuntu/gpg) -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF "$(openssl "$VERSION_CODENAME") #### $(. $(dpkg && '="https'" 'POSTGRES_PASSWORD="%s\nREDIS_PASSWORD=%s\nADMIN_PASSWORD=%s\n'" (versi *compose* *file* --now --print-architecture) --proto --tlsv1.2 -d -fsSLo -hex -m -y /etc/apt/keyrings/docker.asc /etc/os-release 077 2.2.0): 3. 32)" 4. 700 Architectures: Buat Components: Direktori EOF Gunakan Keamanan Konfigurasi Kredensial Membangkitkan Membuat Mengunduh Signed-By: Simpan SnapOtter Suites: Types: URIs: \ `.env`: ``` ```bash `openssl` acak admin akun aplikasi. apt bagi basis cd containerd.io curl dan data deb di direktori docker docker-buildx-plugin docker-ce docker-ce-cli docker-compose-plugin docker-compose.yml echo enable [https://download.docker.com/linux/ubuntu](https://download.docker.com/linux/ubuntu) [https://raw.githubusercontent.com/snapotter-hq/Snapotter/v2.2.0/docker/docker-compose.yml](https://raw.githubusercontent.com/snapotter-hq/Snapotter/v2.2.0/docker/docker-compose.yml) install kata konfigurasi kuat membuat openssl printf proyek rand resmi sandi stable sudo systemctl umask unduh untuk update yang ~/snapotter> .env
chmod 600 .env
```

#### 5. Optimasi Sumber Daya Minimum (Menghindari Out-of-Memory)

Mengingat VPS hanya memiliki RAM 2 GB, konfigurasi bawaan SnapOtter perlu ditimpa agar tidak menghabiskan memori sistem. Buat *file* `compose.minimum.yml` berikut:

```bash
cat > compose.minimum.yml <<'YAML'
services:
  SnapOtter:
    image: snapotter/snapotter:2.2.0
    ports: !override
      - "127.0.0.1:1349:1349"
    environment:
      DEFAULT_PASSWORD: ${ADMIN_PASSWORD:?ADMIN_PASSWORD belum diset}
      CONCURRENT_JOBS: "1"
      MAX_WORKER_THREADS: "2"
      MAX_BATCH_SIZE: "5"
      MAX_UPLOAD_SIZE_MB: "100"
      MAX_MEGAPIXELS: "50"
      MAX_VIDEO_DURATION_S: "300"
      PROCESSING_TIMEOUT_S: "600"
      SNAPOTTER_TELEMETRY: "0"
    mem_limit: 1152m
    memswap_limit: 1536m
    cpus: "1.5"
    shm_size: "128m"
  postgres:
    mem_limit: 384m
    memswap_limit: 512m
    cpus: "0.5"
  redis:
    mem_limit: 128m
    memswap_limit: 256m
    cpus: "0.5"
    command: >-
      redis-server
      --maxmemory-policy noeviction
      --maxmemory 64mb
      --appendonly yes
      --requirepass ${REDIS_PASSWORD:?REDIS_PASSWORD belum diset}
YAML
```

#### 6. Menjalankan Aplikasi dalam Container

Unduh seluruh *image* dan jalankan di latar belakang (*detached mode*):

```bash
sudo docker compose -f docker-compose.yml -f compose.minimum.yml pull
sudo docker compose -f docker-compose.yml -f compose.minimum.yml up -d --no-build
```

#### 7. Mengatur Reverse Proxy dan HTTPS (Caddy)

Instal Caddy sebagai peladen web untuk menghubungkan jaringan eksternal ke kontainer lokal, sekaligus menerbitkan sertifikat SSL:

```bash
sudo apt install -y caddy
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak
```

Tulis konfigurasi domain yang mengarah ke peladen lokal:

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF ## ### & **Akses **Password **URL **Username - --config --no-stream -1 -T -U /etc/caddy/Caddyfile 1. 127.0.0.1:1349 2. 300s Akses Aplikasi:** Backup Basis Container Data EOF Konfigurasi Kredensial Maintenance Pemantauan Pencadangan Pengujian PostgreSQL Resource SSH:** Server Status Untuk VPS VPS:** [https://snapotterlab.web.id](https://snapotterlab.web.id) `KDJKp3kelompok9` ``` ```bash `admin` `pg_dump`: `ssh `thunder-76@-nebula` basis batas berkala: caddy compose container dapat data dilakukan ditentukan, docker exec flush_interval http inspeksi lakukan langsung melalui melebihi memastikan memori menggunakan penggunaan pg_dump postgres ps read_timeout reload reverse_proxy snapotter snapotterlab.web.id stats sudo systemctl tidak transport ubuntu@43.173.19.49` validate write_timeout yang { }> "$HOME/snapotter-backup-$(date +%F).sql"
```

### 3. Pembaruan Aplikasi (Update)
Pembaruan dilakukan dengan mengeksekusi ulang perintah penarikan *image*:

```bash
sudo docker compose -f docker-compose.yml -f compose.minimum.yml pull
sudo docker compose -f docker-compose.yml -f compose.minimum.yml up -d
```

## Otomatisasi

### Otomatisasi Pemrosesan Antrean (Job Queue)

Otomatisasi dalam SnapOtter berfokus pada **pemrosesan tugas asinkron** menggunakan Redis. 

Ketika pengguna mengunggah berkas video berukuran besar, aplikasi web tidak akan "terkunci" menunggu konversi selesai. Alih-alih, SnapOtter secara otomatis:
1. Mendaftarkan tugas konversi (*job metadata*) ke dalam Redis.
2. *Worker threads* di latar belakang otomatis mendeteksi tugas baru dari Redis dan mengeksekusi proses *transcoding*.
3. Mengembalikan hasil konversi ke antarmuka aplikasi segera setelah tugas selesai.

Parameter `CONCURRENT_JOBS: "1"` menginstruksikan worker untuk otomatis memproses tepat satu konversi dalam satu siklus guna menghindari *CPU spike*.

## Cara Pemakaian

### 1. Mengakses Aplikasi

Aplikasi dapat diakses melalui browser menggunakan tautan dan kredensial yang telah dikonfigurasi:

- **Alamat aplikasi:** [https://snapotterlab.web.id](https://snapotterlab.web.id)
- **Username:** `admin`
- **Password:** `KDJKp3kelompok9`

**Tampilan Halaman Login SnapOtter:**

![Halaman login SnapOtter](screenshot/fitur-1.png)

### 2. Mengunggah dan Mengonversi Media

Pada *Dashboard*, pengguna dapat menyeret (*drag-and-drop*) berkas yang ingin dimodifikasi dan memilih opsi konversi (misal: "Compress" atau "Convert to WebP") melalui menu panel di samping.

**Tampilan Halaman Utama / Dashboard:**

![Halaman utama SnapOtter](screenshot/fitur-2.png)

## Pembahasan

### 1. Kelebihan SnapOtter
- **Kerahasiaan Data Terjamin:** Sebagai aplikasi *self-hosted*, data sensitif pengguna tidak diunggah ke *cloud* pihak ketiga.
- **Arsitektur Resilient:** Memanfaatkan Redis *message queue* sehingga tugas komputasi berat tidak mengganggu responsivitas *web interface*.
- **Kemudahan Deployment:** Tersedia secara resmi dalam bentuk Docker Compose, membuat instalasi menjadi lebih terprediksi.

### 2. Kekurangan SnapOtter
- **Rakus Sumber Daya:** Operasi kompresi video sangat bergantung pada kekuatan CPU dan IOPS *disk*.
- **Konfigurasi Lingkungan:** Membutuhkan *fine-tuning* limitasi memori manual pada VPS berspesifikasi 2GB agar tidak mengalami *Out-Of-Memory (OOM)*.

### 3. Perbandingan dengan Aplikasi Sejenis

SnapOtter dibandingkan dengan **Stirling-PDF** sebagai sesama aplikasi produktivitas media mandiri (*self-hosted*).

| Aspek | SnapOtter | Stirling-PDF |
|---|---|---|
| **Fokus Pemrosesan** | Universal lintas media (Gambar, Video, Dokumen) | Spesifik dan mendalam pada manipulasi dokumen PDF |
| **Arsitektur** | Terdistribusi (App, Postgres, Redis) | Berdiri monolitik (Java) |
| **Pengelolaan Antrean** | Asinkron bertumpu pada pesan (Redis) | Sinkron menggunakan siklus *thread pool* internal |
| **Keunggulan** | Cocok untuk konversi format massal di latar belakang | Menggabungkan, memisah, dan memberi kata sandi PDF |

### 4. Kesimpulan Pembahasan

SnapOtter sangat relevan digunakan sebagai alat konversi media mandiri untuk menjaga privasi data. Penerapan ini membuktikan bahwa aplikasi rakus memori dapat berjalan stabil di VPS spesifikasi minimal (RAM 2 GB) melalui optimasi memori kontainer (`compose.minimum.yml`). Penggunaan *reverse proxy* Caddy turut menyederhanakan arsitektur jaringan publik dengan menyediakan enkripsi TLS otomatis.

## Referensi

1. SnapOtter Repository. *SnapOtter: A Self-Hosted Media Processor*. https://github.com/snapotter-hq/Snapotter
2. Docker Docs. *Docker Engine & Compose*. https://docs.docker.com/engine/
3. Caddy Server Docs. *Reverse Proxying*. https://caddyserver.com/docs/

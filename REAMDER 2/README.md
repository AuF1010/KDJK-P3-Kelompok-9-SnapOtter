
<a name="top"></a>

<div align="center">

<img src="https://raw.githubusercontent.com/snapotter-hq/SnapOtter/main/apps/web/public/logo.png" width="120" alt="SnapOtter Logo" />

<h1>Aplikasi Web SnapOtter</h1>

<p><b>Tugas Proyek Akhir Mata Kuliah Komunikasi Data dan Jaringan Komputer (KDJK)</b></p>

[![Sumopod VPS](https://img.shields.io/badge/Deployment-Sumopod%20VPS-6C3DF4?style=for-the-badge)](https://sumopod.com/)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04%20LTS-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)](https://ubuntu.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Caddy](https://img.shields.io/badge/Caddy-Reverse%20Proxy-1F88C0?style=for-the-badge&logo=caddy&logoColor=white)](https://caddyserver.com/)
[![HTTPS](https://img.shields.io/badge/HTTPS-Active-00875A?style=for-the-badge)](https://snapotterlab.web.id)
[![SnapOtter](https://img.shields.io/badge/SnapOtter-v2.2.0-2563EB?style=for-the-badge)](https://github.com/snapotter-hq/SnapOtter)
[![Akses Aplikasi](https://img.shields.io/badge/Live%20Website-Open%20SnapOtter-00C853?style=for-the-badge)](https://snapotterlab.web.id)

</div>

---

## Daftar Isi


# Proyek KDJK: Deployment SnapOtter

**Kelompok 9 — Paralel 3**

| No. | NIM | Nama |
|:---:|---|---|
| 1 | M0403241130 | Faris Ambar Susilo |
| 2 | M0403241150 | Khalifah Azka Hikari |
| 3 | M0403241151 | Aufa Alifiyanto |
| 4 | M0403241165 | Faqih Sahar Ramadhan |
| 5 | M0403241047 | Azahra Salsabila |

**Alamat aplikasi:** [https://snapotterlab.web.id](https://snapotterlab.web.id)  
**Repository aplikasi:** [snapotter-hq/SnapOtter](https://github.com/snapotter-hq/SnapOtter)

## Daftar Isi

[Sekilas Tentang](#sekilas-tentang) | [Instalasi](#instalasi) | [Konfigurasi](#konfigurasi) | [Maintenance](#maintenance) | [Otomatisasi](#otomatisasi) | [Cara Pemakaian](#cara-pemakaian) | [Pembahasan](#pembahasan) | [Referensi](#referensi)
:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:

## Sekilas Tentang

**SnapOtter** merupakan aplikasi web *open-source* dan *self-hosted* yang menyediakan berbagai alat untuk mengolah gambar, video, audio, PDF, dan berkas lainnya melalui browser. Pengguna dapat melakukan konversi, kompresi, pengeditan sederhana, penyimpanan berkas, serta menyusun beberapa proses melalui fitur **Automate**.

Berbeda dengan layanan konversi yang sepenuhnya dijalankan pada server penyedia, SnapOtter dapat dipasang pada server yang dikelola sendiri. Dengan demikian, pengelola memiliki kontrol lebih besar terhadap instalasi aplikasi dan penyimpanan berkas.

### Fitur Utama

| Kategori | Contoh fitur |
|---|---|
| **Image** | Resize, crop, rotate, convert, compress, dan pengaturan warna |
| **Video** | Trim, convert, compress, dan pengolahan video |
| **Audio** | Trim, convert, normalize, dan pengolahan audio |
| **PDF** | Merge, compress, split, watermark, remove pages, dan page numbers |
| **Files** | Upload, penyimpanan, serta pengelolaan berkas |
| **Automate** | Menyusun dan menyimpan rangkaian proses (*pipeline*) |

Pada antarmuka SnapOtter versi 2.2.0 yang digunakan kelompok, katalog menampilkan **243 tools**. Namun , tidak semua tools itu bisa digunkan karena ada fitur fitur yang membutuhkan requirement VPS yang lebih bagus.

**Batasan implementasi:** proyek ini menggunakan VPS **2 vCPU dan RAM 2 GB**, sehingga kami hanya bisa deployment untuk Tier Minimum dan pengujian difokuskan pada fitur non-AI, terutama gambar dan PDF. Fitur pemrosesan video berat serta model AI yang memerlukan memori lebih besar tidak menjadi fokus pengujian. Hal ini merujuk pada panduan resmi dari snapotter https://docs.snapotter.com/guide/low-resource.

> **Tampilan halaman Tools**  
> ![Halaman Tools SnapOtter](screenshots/01-halaman-tools.png)

## Instalasi

### Prasyarat

SnapOtter dipasang pada layanan VPS dengan spesifikasi berikut.

| Komponen | Spesifikasi |
|---|---|
| Sistem operasi | Ubuntu Server 24.04.4 LTS (64-bit) |
| CPU | 2 vCPU |
| RAM | 2 GB |
| Storage | 40 GB |
| Traffic | 512 GB |
| Docker Engine | 29.9.2 |
| Docker Compose | 5.6.1 |
| Versi SnapOtter | 2.2.0 |
| Domain | `snapotterlab.web.id` |

Perangkat lunak utama yang digunakan adalah Docker Engine, Docker Compose, PostgreSQL 17, Redis 8, dan Caddy sebagai *reverse proxy*.

### Langkah Instalasi

#### 1. Mempersiapkan Server Ubuntu

Akses VPS melalui terminal menggunakan protokol SSH (*Secure Shell*) dengan perintah berikut:

```bash
ssh USERNAME@IP_PUBLIK_VPS
```

Sesuaikan `USERNAME` dan `IP_PUBLIK_VPS` dengan informasi akses yang diberikan oleh penyedia VPS.

Setelah berhasil terhubung ke VPS, jalankan perintah berikut:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
```

Perintah `sudo apt update` digunakan untuk memperbarui daftar paket pada Ubuntu. Selanjutnya, `ca-certificates` digunakan untuk mendukung verifikasi sertifikat SSL/TLS, sedangkan `curl` digunakan untuk mengunduh berkas dari internet melalui terminal.

#### 2. Menginstal Docker Engine dan Docker Compose

Tambahkan *repository* resmi Docker pada Ubuntu.

```bash
sudo install -m 0755 -d /etc/apt/keyrings

sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc

sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
```

Pasang Docker Engine beserta plugin Compose, lalu aktifkan layanannya.

```bash
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo systemctl enable --now docker
```

Pastikan Docker berhasil terpasang.

```bash
sudo docker --version
sudo docker compose version
sudo docker run --rm hello-world
```

#### 3. Mengunduh Docker Compose SnapOtter

Buat direktori proyek dan unduh file Compose resmi SnapOtter versi 2.2.0.

```bash
install -d -m 700 ~/snapotter
cd ~/snapotter

curl --proto '=https' --tlsv1.2 -fsSLo docker-compose.yml \
  https://raw.githubusercontent.com/snapotter-hq/SnapOtter/v2.2.0/docker/docker-compose.yml
```

File `docker-compose.yml` ini memuat layanan SnapOtter, PostgreSQL, Redis, volume data, dan pemeriksaan kesehatan container.

#### 4. Membuat file kredensial

Buat file `.env` yang berisi password acak untuk PostgreSQL, Redis, dan administrator SnapOtter.

```bash
cd ~/snapotter
sudo apt install -y openssl

umask 077

printf 'POSTGRES_PASSWORD=%s\nREDIS_PASSWORD=%s\nADMIN_PASSWORD=%s\n' \
  "$(openssl rand -hex 32)" \
  "$(openssl rand -hex 32)" \
  "$(openssl rand -hex 32)" > .env

chmod 600 .env
```

File `.env` menyimpan kredensial layanan

#### 5. Mengoptimalkan penggunaan sumber daya

Konfigurasi Compose bawaan memiliki batas memori yang lebih besar daripada RAM VPS kelompok. Karena itu, dibuat file tambahan `compose.minimum.yml` untuk mengatur batas penggunaan sumber daya.

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

Beberapa pengaturan penting yang diterapkan:

| Pengaturan | Nilai | Tujuan |
|---|---|---|
| `CONCURRENT_JOBS` | `1` | Membatasi pekerjaan pemrosesan yang berlangsung bersamaan |
| `MAX_WORKER_THREADS` | `2` | Membatasi jumlah *worker thread* |
| `MAX_BATCH_SIZE` | `5` | Membatasi jumlah berkas dalam satu batch |
| `MAX_UPLOAD_SIZE_MB` | `100` | Membatasi ukuran berkas upload |
| `mem_limit` SnapOtter | `1152m` | Membatasi penggunaan RAM container aplikasi |
| `mem_limit` PostgreSQL | `384m` | Membatasi penggunaan RAM database |
| `mem_limit` Redis | `128m` | Membatasi penggunaan RAM Redis |

Periksa konfigurasi Docker Compose sebelum menjalankan container.

```bash
sudo docker compose \
  -f docker-compose.yml \
  -f compose.minimum.yml \
  config --quiet
```

#### 6. Menjalankan SnapOtter

Unduh image aplikasi dan layanan pendukung, kemudian jalankan container.

```bash
sudo docker compose \
  -f docker-compose.yml \
  -f compose.minimum.yml \
  pull

sudo docker compose \
  -f docker-compose.yml \
  -f compose.minimum.yml \
  up -d --no-build
```

Periksa status ketiga container.

```bash
sudo docker compose \
  -f docker-compose.yml \
  -f compose.minimum.yml \
  ps
```
> **Status Container SnapOtter**  
> ![Status tiga container SnapOtter](screenshots/03-container-healthy.png)

Hasil pemeriksaan menunjukkan bahwa container SnapOtter, PostgreSQL, dan Redis berhasil dijalankan dengan status `healthy`.

## Konfigurasi

### 1. Menghubungkan Domain ke VPS

Setelah SnapOtter berhasil dijalankan, domain `snapotterlab.web.id` dihubungkan ke VPS melalui pengaturan DNS pada panel Provider.

Konfigurasi DNS dilakukan dengan menambahkan record berikut:

| Tipe Record | Name | Value |
|---|---|---|
| A | @ | IP publik VPS |

Record tersebut digunakan untuk mengarahkan domain `snapotterlab.web.id` ke alamat IP publik VPS.


### 2. Memasang Caddy dan mengaktifkan HTTPS

Caddy digunakan sebagai *reverse proxy* agar SnapOtter dapat diakses melalui HTTPS tanpa membuka port aplikasi `1349` secara langsung ke internet.

```bash
sudo apt update
sudo apt install -y caddy
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak
```

Buat konfigurasi Caddy untuk domain SnapOtter.

```bash
sudo tee /etc/caddy/Caddyfile > /dev/null <<'EOF'
{
    servers {
        protocols h1 h2
    }
}

snapotterlab.web.id {
    reverse_proxy 127.0.0.1:1349 {
        flush_interval -1
        transport http {
            read_timeout 300s
            write_timeout 300s
        }
    }
}
EOF
```

Konfigurasi tersebut menggunakan HTTP/1.1 dan HTTP/2.

Validasi dan terapkan konfigurasi:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl is-active caddy
```

Periksa respons website melalui HTTPS.

```bash
curl -sS -o /dev/null \
  -w 'HTTP Version: %{http_version} | Status: %{http_code} | Time: %{time_total}s\n' \
  https://snapotterlab.web.id

curl -fsS https://snapotterlab.web.id/api/v1/health
```

Hasil pengujian kelompok menunjukkan **HTTP/2**, **HTTP 200**, dan status aplikasi **healthy**.

> ![Pengujian HTTPS dan health API SnapOtter](screenshots/05-https-healthcheck.png)


## Maintenance

Maintenance dilakukan untuk memantau kondisi SnapOtter, mengatasi kendala layanan, serta menjaga data aplikasi agar tetap aman.

### 1. Memeriksa status container dan penggunaan resource

Status container serta penggunaan CPU, RAM, dan penyimpanan VPS:

```bash
cd ~/snapotter
sudo docker compose -f docker-compose.yml -f compose.minimum.yml ps
sudo docker stats --no-stream
free -h
df -h
```

- Perintah `docker compose ps` digunakan untuk memeriksa status container SnapOtter, PostgreSQL, dan Redis.
- Perintah `docker stats`, `free -h`, dan `df -h` digunakan untuk memantau penggunaan resource pada VPS.

### 2. Memeriksa log aplikasi

Jika terjadi masalah pada aplikasi atau akses melalui domain:

```bash
sudo docker logs --tail 100 SnapOtter
sudo journalctl -u caddy -n 40 --no-pager
```

- Log SnapOtter digunakan untuk melihat aktivitas dan kesalahan pada aplikasi.
- log Caddy membantu memeriksa kendala pada reverse proxy dan HTTPS.

### 3. Melakukan restart aplikasi

Apabila SnapOtter mengalami gangguan atau tidak merespons:

```bash
cd ~/snapotter
sudo docker compose -f docker-compose.yml -f compose.minimum.yml restart SnapOtter
```

Setelah restart, periksa kembali status container:

```bash
sudo docker compose -f docker-compose.yml -f compose.minimum.yml ps
```

Note : Restart sebaiknya dilakukan ketika tidak ada file yang sedang diproses agar aktivitas pengguna tidak terganggu.

### 4. Melakukan backup data

SnapOtter menggunakan PostgreSQL untuk menyimpan data seperti akun pengguna, pengaturan, dan pipeline. Selain database, file pengguna juga disimpan pada volume Docker.

Untuk membuat backup database PostgreSQL:

```bash
cd ~/snapotter
umask 077
mkdir -p backups

sudo docker exec SnapOtter-postgres \
  sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > "backups/snapotter-db-$(date +%Y%m%d-%H%M%S).dump"
```

Hasil backup database akan disimpan pada folder `~/snapotter/backups`.

Untuk mencadangkan file aplikasi, cari terlebih dahulu nama volume yang digunakan SnapOtter:

```bash
DATA_VOLUME="$(sudo docker inspect SnapOtter \
  --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')"

echo "$DATA_VOLUME"
```

Setelah nama volume ditemukan, buat arsip backup menggunakan perintah berikut:

```bash
sudo docker run --rm \
  -v "$DATA_VOLUME:/data:ro" \
  -v "$HOME/snapotter/backups:/backup" \
  alpine:3.22 \
  tar -czf /backup/snapotter-data.tar.gz -C /data .
```

Note : Backup sebaiknya dilakukan ketika tidak ada proses pengolahan file yang aktif.

### 5. Memeriksa akses HTTPS

Periksa status Caddy dan respons API:

```bash
sudo systemctl status caddy --no-pager

curl -fsS https://snapotterlab.web.id/api/v1/health
```

Jika layanan berjalan dengan baik
- Caddy akan menunjukkan status `active (running)`
- API SnapOtter memberikan respons dengan status `healthy`.

### 6. Pembaruan aplikasi

SnapOtter yang digunakan dalam proyek ini adalah versi `2.2.0`. Jika ingin memperbarui aplikasi, periksa terlebih dahulu rilis terbaru dan sesuaikan versi image pada file `compose.minimum.yml`.

Setelah versi image diperbarui dan konfigurasi Compose disesuaikan:

```bash
cd ~/snapotter

sudo docker compose -f docker-compose.yml -f compose.minimum.yml config --quiet

sudo docker compose -f docker-compose.yml -f compose.minimum.yml pull SnapOtter

sudo docker compose -f docker-compose.yml -f compose.minimum.yml up -d --no-build
```

Setelah pembaruan selesai, periksa kembali status container dan pastikan aplikasi dapat diakses melalui domain.


## Otomatisasi

Selain instalasi secara manual, `otomatisasi_snapotter.sh` juga dibuat untuk mempermudah instalasi dan pengelolaan SnapOtter pada VPS Ubuntu 24.04.

Skrip ini mengotomatisasi pemasangan Docker, pengunduhan berkas konfigurasi SnapOtter, pembuatan password, penyesuaian sumber daya VPS, menjalankan container, serta konfigurasi Caddy untuk akses HTTPS.

Berkas skrip dapat dilihat pada [otomatisasi_snapotter.sh](otomatisasi_snapotter.sh).

Untuk melakukan instalasi otomatis pada VPS baru, jalankan:

```bash
bash otomatisasi_snapotter.sh instal snapotterlab.web.id
```

Perintah tambahan untuk memeriksa layanan dan melakukan maintenance:

```bash
bash otomatisasi_snapotter.sh status
bash otomatisasi_snapotter.sh cek
bash otomatisasi_snapotter.sh restart
bash otomatisasi_snapotter.sh log
bash otomatisasi_snapotter.sh backup-db
```


## Cara Pemakaian

### 1. Login ke SnapOtter

Buka [https://snapotterlab.web.id](https://snapotterlab.web.id) melalui browser. Masuk menggunakan akun administrator yang telah dikonfigurasi saat instalasi. Pada login pertama, pengguna akan diminta mengganti password administrator.

![Halaman Login SnapOtter](screenshots/09-login.png)

### 2. Memilih Tools Pengolahan File

Setelah berhasil login, pengguna akan diarahkan ke halaman utama SnapOtter yang menyediakan berbagai tools untuk mengolah file, seperti gambar dan dokumen PDF.

Pengguna dapat memilih tools sesuai dengan kebutuhan pengolahan file. Tampilan halaman utama SnapOtter dapat dilihat pada bagian awal dokumentasi.

![Halaman Tampilan Awal Aplikasi](screenshots/01-halaman-tools.png)

### 3. Mengolah Gambar

Untuk mengolah gambar, pengguna dapat memilih salah satu tools pada kategori **Image**, misalnya **Compress Image** atau **Rotate & Flip Image**.

Unggah gambar yang ingin diolah, sesuaikan pengaturan yang tersedia, lalu jalankan proses. Setelah selesai, pengguna dapat mengunduh gambar hasil pengolahan.

![Pengolahan Gambar pada SnapOtter](screenshots/10-pengolahan-gambar.png)

### 4. Mengolah Dokumen PDF

SnapOtter menyediakan berbagai tools untuk mengolah dokumen PDF, salah satunya **Merge PDFs** yang digunakan untuk menggabungkan beberapa dokumen menjadi satu file.

Untuk menggunakan fitur ini, pilih **Merge PDFs**, unggah dokumen yang ingin digabungkan, lalu klik tombol **Merge**. Setelah muncul pesan **Conversion complete**, unduh dokumen melalui tombol **Download PDF**.

Pada pengujian kelompok, lima dokumen PDF berhasil digabungkan menggunakan tool Merge PDFs secara langsung.

![Hasil Penggabungan PDF](screenshots/11-merge-pdf.png)

### 5. Mengelola File melalui Files Library

Menu **Files** digunakan untuk melihat dan mengelola file yang telah disimpan pada SnapOtter, termasuk hasil pengolahan yang disimpan ke Library.

Melalui menu ini, pengguna dapat melihat daftar file serta informasi seperti nama, ukuran, dan format file. Informasi lebih lanjut dapat dilihat melalui panel **File Details**.

![Tampilan Files Library SnapOtter](screenshots/12-files-library.png)

### 6. Menggunakan Fitur Automate

SnapOtter menyediakan fitur **Automate** yang memungkinkan pengguna menggabungkan beberapa proses pengolahan file menjadi satu *pipeline*. Setiap proses dijalankan sesuai urutan yang telah ditentukan, dan pipeline dapat disimpan untuk digunakan kembali.

Untuk menggunakannya, buka menu **Automate**, tambahkan tools yang dibutuhkan, lalu susun urutan pemrosesan melalui **Pipeline Builder**.

Pada proyek ini, kelompok mencoba fitur Automate menggunakan tools seperti **Compress PDF**, **Watermark PDF**, dan **PDF Page Numbers**. Namun, beberapa kombinasi masih mengalami kendala, salah satunya penggunaan **Merge PDFs** dalam pipeline karena membutuhkan setidaknya dua file PDF dalam satu proses.

![Tampilan Pipeline Builder SnapOtter](screenshots/07-pipeline-builder.png)


## Pembahasan

### Kelebihan SnapOtter

1. **Self-hosted.** SnapOtter dapat dipasang dan dikelola pada VPS sendiri sehingga pengelola memiliki kendali atas server dan penyimpanan data.
2. **Fitur beragam.** SnapOtter menyediakan berbagai tools untuk mengolah gambar, video, audio, PDF, dan file lainnya dalam satu aplikasi.
3. **Dukungan pipeline.** Fitur Automate memungkinkan pengguna menyusun beberapa proses pengolahan file secara berurutan melalui Pipeline Builder.
4. **Instalasi berbasis Docker.** SnapOtter dapat dijalankan bersama PostgreSQL dan Redis menggunakan Docker Compose sehingga pengelolaan layanannya lebih mudah.

### Kekurangan dan Kendala Pengujian

1. **Keterbatasan resource VPS.** Dengan spesifikasi 2 vCPU dan RAM 2 GB, kelompok melakukan penyesuaian batas penggunaan resource. Fitur yang membutuhkan pemrosesan berat, seperti video dan AI, belum diuji secara menyeluruh.
2. **Kendala akses domain.** Pada pengujian awal, akses SnapOtter melalui domain sempat mengalami keterlambatan. Setelah HTTP/3 dinonaktifkan pada Caddy, akses melalui browser menjadi lebih lancar.
3. **Batas jumlah file.** Saat mencoba mengunggah enam file sekaligus, aplikasi menampilkan error `reached files limit`. Hal ini sesuai dengan konfigurasi `MAX_BATCH_SIZE=5` yang digunakan kelompok.
4. **Kendala pada Pipeline Builder.** Fitur Merge PDFs belum berhasil digunakan dalam pipeline ketika file diproses sebagai input terpisah. Namun, penggabungan PDF melalui tool Merge PDFs secara langsung berhasil dilakukan.
5. **Kendala pada Files Library.** Ketika diuji, tombol Open File pada file gambar maupun PDF justru mengarahkan pengguna kembali ke halaman utama, bukan melihat detail file tersebut.
6. **Pengaturan PDF Page Numbers.** Pada pengujian perubahan ukuran font, hasil yang ditampilkan belum menunjukkan perbedaan sesuai pengaturan.

### Hasil Pengujian Deployment

Setelah instalasi dan konfigurasi selesai, kelompok melakukan beberapa pengujian untuk memastikan SnapOtter dapat dijalankan dan diakses melalui internet.

| Pengujian | Hasil |
|---|---|
| Konfigurasi Docker Compose | Berhasil divalidasi |
| Status container | SnapOtter, PostgreSQL, dan Redis berstatus `healthy` |
| Akses melalui domain | Berhasil menggunakan HTTPS |
| Protokol HTTP | HTTP/2 dengan respons HTTP 200 |
| Health API | HTTP 200 dengan status `healthy` |
| Readiness API | HTTP 200 pada pengujian melalui Windows |
| Penggabungan PDF | Lima file PDF berhasil digabungkan melalui Merge PDFs |
| Penggunaan melalui browser | Login, Files, proses PDF, dan download berjalan lancar pada tiga sesi Chrome |

Selain itu, kelompok melakukan tujuh kali pengujian melalui CMD Windows. Seluruh pengujian halaman Login dan Readiness API menghasilkan **HTTP 200 (7 dari 7 percobaan)**.

### Perbandingan dengan Aplikasi Sejenis

SnapOtter memiliki beberapa fungsi yang serupa dengan Stirling PDF dan Smallpdf, terutama dalam pengolahan dokumen PDF. Namun, ketiganya memiliki fokus dan cara penggunaan yang berbeda.

| Aspek | SnapOtter | Stirling PDF | Smallpdf |
|---|---|---|---|
| Fokus utama | Pengolahan berbagai jenis file | Pengolahan dokumen PDF | Pengolahan dokumen PDF |
| Jenis file | Gambar, video, audio, PDF, dan file lainnya | Terutama PDF | Terutama PDF dan konversi dokumen |
| Self-hosted | Ya | Ya | Berbasis layanan dan aplikasi dari penyedia |
| Cara penggunaan | Browser melalui server sendiri | Browser, desktop, atau server sendiri | Browser dan aplikasi desktop/mobile |
| Otomatisasi | Pipeline Builder melalui fitur Automate | Workflow dan otomatisasi pengolahan PDF | Rangkaian tools PDF melalui layanan web |
| Pengelolaan server | Dikelola sendiri | Dikelola sendiri jika menggunakan self-hosted | Infrastruktur layanan web dikelola penyedia |

Berdasarkan perbandingan tersebut, **SnapOtter** lebih sesuai untuk pengguna yang membutuhkan berbagai tools pengolahan file dalam satu aplikasi self-hosted. **Stirling PDF** lebih berfokus pada pengolahan dokumen PDF, sedangkan **Smallpdf** menawarkan kemudahan penggunaan tools PDF tanpa harus menyiapkan VPS sendiri.

### Kesimpulan

Berdasarkan proses instalasi dan pengujian, SnapOtter versi `2.2.0` berhasil dijalankan pada VPS dengan spesifikasi **2 vCPU dan RAM 2 GB** menggunakan Docker Compose serta penyesuaian batas penggunaan resource.

Aplikasi berhasil diakses melalui domain `snapotterlab.web.id` menggunakan HTTPS. Beberapa fungsi dasar, seperti pengolahan PDF, pengelolaan file, dan pengunduhan hasil, juga berhasil diuji.

Meskipun masih ditemukan beberapa kendala pada fitur tertentu, hasil pengujian menunjukkan bahwa SnapOtter dapat digunakan sebagai aplikasi pengolahan file berbasis web yang dijalankan melalui VPS sendiri.

## Referensi

1. SnapOtter. [Repository GitHub](https://github.com/snapotter-hq/SnapOtter).
2. SnapOtter. [Getting Started](https://docs.snapotter.com/guide/getting-started).
3. SnapOtter. [Deployment dan Hardware Requirements](https://docs.snapotter.com/guide/deployment).
4. SnapOtter. [Low-Resource Setups](https://docs.snapotter.com/guide/low-resource).
5. Docker. [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).
6. Caddy. [Caddyfile Global Options](https://caddyserver.com/docs/caddyfile/options).
7. Stirling PDF. [Documentation](https://docs.stirlingpdf.com/).
8. Smallpdf. [Official Website](https://smallpdf.com/).

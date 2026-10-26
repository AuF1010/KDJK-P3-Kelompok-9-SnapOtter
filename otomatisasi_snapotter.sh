#!/usr/bin/env bash
set -Eeuo pipefail

# Proyek KDJK: otomatisasi INSTALASI AWAL dan maintenance SnapOtter 2.2.0.
# Jalankan sebagai user Ubuntu biasa (bukan root) yang memiliki akses sudo.
# Instalasi awal ditujukan untuk VPS Ubuntu 24.04 yang masih bersih.

PROYEK="$HOME/snapotter"
VERSI='2.2.0'
DOMAIN_DEFAULT='snapotterlab.web.id'
COMPOSE=(sudo docker compose --project-directory "$PROYEK" --env-file "$PROYEK/.env" \
  -f "$PROYEK/docker-compose.yml" -f "$PROYEK/compose.minimum.yml")
# Referensi image utama (harus sama dengan image pada compose.minimum.yml).
IMAGE="snapotter/snapotter:$VERSI"
# Retensi backup dalam hari; dapat ditimpa via environment.
BACKUP_RETENSI_HARI="${BACKUP_RETENSI_HARI:-14}"

info() { printf '\n==> %s\n' "$*"; }
gagal() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Print command usage, installation prerequisites, and backup retention options.
bantuan() {
  cat <<'PANDUAN'
Penggunaan:
  bash otomatisasi_snapotter.sh instal DOMAIN   Instalasi otomatis di VPS BARU
  bash otomatisasi_snapotter.sh jalankan       Unduh image dan jalankan container
  bash otomatisasi_snapotter.sh status         Lihat status container
  bash otomatisasi_snapotter.sh cek            Periksa API lokal dan HTTPS
  bash otomatisasi_snapotter.sh restart        Restart aplikasi SnapOtter
  bash otomatisasi_snapotter.sh log            Tampilkan 50 baris log aplikasi
  bash otomatisasi_snapotter.sh backup-db      Backup DB PostgreSQL + volume /data

Perintah 'instal' juga menyiapkan swapfile 2 GB dan firewall UFW
(mengizinkan SSH, HTTP, HTTPS; menolak sisanya).

Retensi backup diatur lewat environment BACKUP_RETENSI_HARI (default 14 hari),
mis.: BACKUP_RETENSI_HARI=30 bash otomatisasi_snapotter.sh backup-db

Contoh instalasi di VPS baru:
  bash otomatisasi_snapotter.sh instal snapotterlab.web.id

Prasyarat: Ubuntu 24.04, akses sudo, DNS A record domain menuju IP VPS,
serta port TCP 80 dan 443 dibuka oleh penyedia VPS/firewall.
JANGAN jalankan 'instal' pada VPS yang sudah berisi deployment SnapOtter.
PANDUAN
}

periksa_pengguna() {
  [[ "$EUID" -ne 0 ]] || gagal "Jalankan sebagai user biasa, bukan menggunakan sudo bash."
  command -v sudo >/dev/null 2>&1 || gagal "Perintah sudo tidak tersedia."
}

# Check required project files, Docker Compose, and any saved Compose checksum.
# Exit on missing files or Docker, a Compose failure, or checksum verification failure.
periksa_proyek() {
  for berkas in docker-compose.yml compose.minimum.yml .env; do
    [[ -f "$PROYEK/$berkas" ]] || gagal "Berkas $PROYEK/$berkas tidak ditemukan."
  done
  command -v docker >/dev/null 2>&1 || gagal "Docker belum terpasang."
  sudo docker compose version >/dev/null
  verifikasi_compose
}

# Verify docker-compose.yml against $PROYEK/.compose.sha256 when present.
# Return success if the checksum file is absent; otherwise exit on a mismatch
# or a failure to read the checksum or hash the Compose file.
verifikasi_compose() {
  [[ -f "$PROYEK/.compose.sha256" ]] || return 0   # instalasi lama: lewati
  local tersimpan sekarang
  tersimpan="$(cat "$PROYEK/.compose.sha256")"
  sekarang="$(sha256sum "$PROYEK/docker-compose.yml" | awk '{print $1}')"
  [[ "$tersimpan" == "$sekarang" ]] || gagal \
    'Checksum docker-compose.yml tidak cocok (berpotensi diubah). Hapus .compose.sha256 bila perubahan ini memang disengaja.'
}

baca_domain() {
  if [[ -f "$PROYEK/.domain" ]]; then
    cat "$PROYEK/.domain"
  else
    printf '%s\n' "$DOMAIN_DEFAULT"
  fi
}

periksa_domain() {
  local domain="$1"
  [[ "$domain" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || \
    gagal "Nama domain tidak valid. Isi tanpa https:// dan tanpa garis miring."
  [[ "$domain" == *.* && "$domain" != *..* && ${#domain} -le 253 ]] || \
    gagal "Masukkan nama domain yang valid, contoh: snapotterlab.web.id."
}

instal_docker() {
  info '1/7 Menginstal dependensi dan Docker Engine + Compose'
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl openssl

  # Mengikuti metode repositori APT resmi Docker (bukan curl | sh).
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl --proto '=https' --tlsv1.2 -fsSL \
    https://download.docker.com/linux/ubuntu/gpg \
    -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc

  local kode_ubuntu arsitektur
  kode_ubuntu="$(. /etc/os-release; printf '%s' "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
  arsitektur="$(dpkg --print-architecture)"
  sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<APT
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $kode_ubuntu
Components: stable
Architectures: $arsitektur
Signed-By: /etc/apt/keyrings/docker.asc
APT

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
  sudo systemctl enable --now docker
  sudo docker compose version
  sudo docker run --rm hello-world >/dev/null
  info 'Docker berhasil dipasang dan diuji menggunakan hello-world.'
}

# Create deployment files in $PROYEK for the validated domain in $1.
# Download Compose, save its checksum, generate credentials, and write resource
# overrides; existing files are overwritten. Set umask 077 and file modes 600.
# Download, file creation, and Compose validation failures abort the script.
buat_konfigurasi() {
  info '2/7 Membuat direktori dan mengunduh Compose resmi SnapOtter'
  install -d -m 700 "$PROYEK"
  curl --proto '=https' --tlsv1.2 -fsSLo "$PROYEK/docker-compose.yml" \
    "https://raw.githubusercontent.com/snapotter-hq/SnapOtter/v${VERSI}/docker/docker-compose.yml"
  # Catat checksum compose resmi untuk verifikasi integritas pada perintah berikutnya.
  umask 077
  sha256sum "$PROYEK/docker-compose.yml" | awk '{print $1}' > "$PROYEK/.compose.sha256"
  chmod 600 "$PROYEK/.compose.sha256"

  info '3/7 Membuat password acak dan file .env (mode 600)'
  umask 077
  printf 'POSTGRES_PASSWORD=%s\nREDIS_PASSWORD=%s\nADMIN_PASSWORD=%s\n' \
    "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" \
    "$(openssl rand -hex 32)" > "$PROYEK/.env"
  chmod 600 "$PROYEK/.env"
  printf '%s\n' "$1" > "$PROYEK/.domain"
  chmod 600 "$PROYEK/.domain"

  info '4/7 Membuat batas sumber daya untuk VPS RAM 2 GB'
  cat > "$PROYEK/compose.minimum.yml" <<'YAML'
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
  chmod 600 "$PROYEK/compose.minimum.yml"
  "${COMPOSE[@]}" config --quiet
  info 'Konfigurasi Docker Compose valid.'
}

# Verify Compose, pull configured images, record or compare the application
# digest, then start containers without building and display their status.
# Verification and Compose failures abort the script; digest changes only warn.
jalankan_container() {
  info '5/7 Mengunduh image dan menjalankan container'
  verifikasi_compose
  "${COMPOSE[@]}" config --quiet
  "${COMPOSE[@]}" pull
  kunci_digest_image
  "${COMPOSE[@]}" up -d --no-build
  "${COMPOSE[@]}" ps
}

# Record the first available repository digest for $IMAGE in a mode-600 lock
# file under $PROYEK, setting umask 077 when creating it. An existing lock is
# left unchanged; a differing digest only warns and does not prevent deployment.
# If no digest is available, warn and return success; lock creation failures abort.
kunci_digest_image() {
  local lock="$PROYEK/.image-digest.lock" digest
  digest="$(sudo docker image inspect \
    --format '{{range .RepoDigests}}{{println .}}{{end}}' "$IMAGE" 2>/dev/null \
    | head -n1)" || true
  [[ -n "$digest" ]] || { echo 'Peringatan: digest image tidak terbaca, penguncian dilewati.' >&2; return 0; }
  if [[ -f "$lock" ]]; then
    if [[ "$(cat "$lock")" != "$digest" ]]; then
      printf 'PERINGATAN: digest image berubah.\n  lama : %s\n  baru : %s\n' \
        "$(cat "$lock")" "$digest" >&2
      echo 'Perbarui .image-digest.lock bila pembaruan ini memang disengaja.' >&2
    fi
  else
    umask 077
    printf '%s\n' "$digest" > "$lock"
    chmod 600 "$lock"
    info "Digest image dikunci: $digest"
  fi
}

konfigurasi_caddy() {
  local domain="$1" sementara
  info '6/7 Memasang Caddy dan menyiapkan HTTPS'
  sudo apt-get install -y caddy
  sementara="$(mktemp)"

  cat > "$sementara" <<CADDY
{
    servers {
        protocols h1 h2
    }
}

$domain {
    reverse_proxy 127.0.0.1:1349 {
        flush_interval -1
        transport http {
            read_timeout 300s
            write_timeout 300s
        }
    }
}
CADDY

  # Validasi konfigurasi baru sebelum mengubah Caddyfile aktif.
  if ! sudo caddy validate --config "$sementara" --adapter caddyfile; then
    rm -f "$sementara"
    gagal 'Konfigurasi Caddy tidak valid, Caddyfile lama tidak diubah.'
  fi
  if [[ -f /etc/caddy/Caddyfile ]]; then
    sudo cp -a /etc/caddy/Caddyfile \
      "/etc/caddy/Caddyfile.sebelum-snapotter-$(date +%Y%m%d-%H%M%S).bak"
  fi
  sudo install -m 0644 "$sementara" /etc/caddy/Caddyfile
  rm -f "$sementara"
  sudo systemctl enable --now caddy
  sudo systemctl reload caddy
  info 'Caddy terkonfigurasi dengan HTTP/1.1, HTTP/2, dan HTTPS otomatis.'
}

# Create and activate a mode-600, 2 GiB /swapfile and add it to /etc/fstab
# if no entry exists. Skip creation if active swap is detected or /swapfile exists.
# Fall back to dd if fallocate fails; allocation, activation, or persistence
# failures abort the script and can leave a partially configured swapfile.
konfigurasi_swap() {
  info 'Menyiapkan swapfile 2 GB untuk VPS RAM 2 GB'
  if sudo swapon --show 2>/dev/null | grep -q .; then
    info 'Swap sudah aktif, pembuatan dilewati.'
    return 0
  fi
  if [[ -e /swapfile ]]; then
    info '/swapfile sudah ada, pembuatan dilewati.'
    return 0
  fi
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  if ! grep -q '^/swapfile[[:space:]]' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  fi
  info 'Swapfile 2 GB aktif dan terdaftar di /etc/fstab.'
}

# Install and enable UFW, allowing the OpenSSH profile and TCP ports 80/443,
# with default incoming deny and outgoing allow policies; existing rules remain.
# Custom SSH ports require a separate rule. Package or UFW failures abort the
# script and may leave earlier firewall changes applied.
konfigurasi_firewall() {
  info 'Mengonfigurasi firewall UFW (izinkan SSH, HTTP, HTTPS; tolak sisanya)'
  sudo apt-get install -y ufw
  # Izinkan SSH SEBELUM mengaktifkan UFW agar sesi tidak terputus.
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw default deny incoming
  sudo ufw default allow outgoing
  sudo ufw --force enable
  sudo ufw status verbose
  echo 'Catatan: bila SSH memakai port non-standar, tambahkan "sudo ufw allow <port>/tcp" sebelum menutup sesi.'
}

coba_api() {
  local alamat="$1" keterangan="$2" nomor
  for nomor in $(seq 1 30); do
    if curl -fsS --max-time 8 "$alamat" >/dev/null 2>&1; then
      printf '[OK] %s: %s\n' "$keterangan" "$alamat"
      return 0
    fi
    sleep 3
  done
  printf '[BELUM BERHASIL] %s: %s\n' "$keterangan" "$alamat" >&2
  return 1
}

cek_layanan() {
  local domain
  domain="$(baca_domain)"
  "${COMPOSE[@]}" ps
  echo
  printf 'API lokal  : '
  curl -fsS --max-time 10 -o /dev/null \
    -w 'HTTP %{http_code} | %{time_total}s\n' \
    http://127.0.0.1:1349/api/v1/health
  printf 'API HTTPS  : '
  curl -fsS --max-time 10 -o /dev/null \
    -w 'HTTP %{http_code} | %{time_total}s\n' \
    "https://$domain/api/v1/health"
  printf 'Status API : '
  curl -fsS --max-time 10 "https://$domain/api/v1/health"
  echo
}

# Save a gzip-compressed PostgreSQL SQL dump in $PROYEK/backups, then attempt
# a /data volume backup with the same timestamp/PID suffix and prune old backups.
# Set umask 077 and directory mode 700. Dump or compression failure removes the
# temporary dump and exits; directory, temporary-file, or rename failures abort.
# Volume backup warnings do not prevent retention cleanup.
backup_database() {
  umask 077
  install -d -m 700 "$PROYEK/backups"
  local stamp tujuan sementara
  stamp="$(date +%Y%m%d-%H%M%S)-$$"
  tujuan="$PROYEK/backups/postgres-$stamp.sql.gz"
  sementara="$(mktemp "$PROYEK/backups/.db-XXXXXX")"
  if "${COMPOSE[@]}" exec -T postgres sh -c \
       'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
       | gzip -c > "$sementara"; then
    mv -- "$sementara" "$tujuan"
    printf 'Backup PostgreSQL: %s\n' "$tujuan"
  else
    rm -f -- "$sementara"
    gagal 'Backup PostgreSQL gagal.'
  fi
  backup_volume "$stamp"
  prune_backup
}

# Archive the named volume mounted at SnapOtter's /data as data-$1.tar.gz in
# $PROYEK/backups, which must already exist. $1 is the database backup stamp.
# The volume is mounted read-only; the application is not stopped. Missing or
# unreadable volume metadata skips the archive successfully. Archive failures
# only warn and may leave a partial file; ownership adjustment is best effort.
backup_volume() {
  local stamp="$1" nama_volume tujuan
  nama_volume="$(sudo docker inspect SnapOtter \
    --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' 2>/dev/null)" || true
  if [[ -z "$nama_volume" ]]; then
    echo 'Peringatan: volume /data tidak ditemukan, backup file dilewati.' >&2
    return 0
  fi
  tujuan="$PROYEK/backups/data-$stamp.tar.gz"
  if sudo docker run --rm \
       -v "$nama_volume:/data:ro" \
       -v "$PROYEK/backups:/backup" \
       alpine:3.22 \
       tar -czf "/backup/data-$stamp.tar.gz" -C /data . ; then
    sudo chown "$(id -u):$(id -g)" "$tujuan" 2>/dev/null || true
    printf 'Backup volume /data: %s\n' "$tujuan"
  else
    echo 'Peringatan: backup volume /data gagal.' >&2
  fi
}

# Delete regular postgres-*.sql.gz and data-*.tar.gz files directly under
# $PROYEK/backups when their age in whole 24-hour periods exceeds
# $BACKUP_RETENSI_HARI (default 14), then print the paths reported by find.
# Ignore find errors, including deletion failures and invalid retention values.
prune_backup() {
  local dihapus
  dihapus="$(find "$PROYEK/backups" -maxdepth 1 -type f \
    \( -name 'postgres-*.sql.gz' -o -name 'data-*.tar.gz' \) \
    -mtime +"$BACKUP_RETENSI_HARI" -print -delete 2>/dev/null)" || true
  if [[ -n "$dihapus" ]]; then
    printf 'Backup lama dihapus (>%s hari):\n%s\n' "$BACKUP_RETENSI_HARI" "$dihapus"
  fi
}

# Install SnapOtter for the required domain in $1 on a fresh Ubuntu 24.04 VPS.
# Reject invalid domains, existing deployment files or Caddy, and a Docker
# repository without Docker. Configure swap, Docker, deployment files,
# containers, UFW, and Caddy, then check local and HTTPS health endpoints.
# Precondition and health-check failures exit with status 1; uncaught setup
# failures abort without rolling back changes.
instal_baru() {
  local domain="${1:-}"
  [[ -n "$domain" ]] || gagal 'Isi domain, contoh: instal snapotterlab.web.id'
  periksa_domain "$domain"
  [[ -f /etc/os-release ]] || gagal 'Sistem operasi tidak dikenali.'
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == ubuntu && "${VERSION_ID:-}" == '24.04' ]] || \
    gagal 'Skrip instalasi awal dirancang untuk Ubuntu 24.04.'

  # Jangan mengubah deployment aktif atau situs Caddy milik layanan lain.
  [[ ! -e "$PROYEK/.env" && ! -e "$PROYEK/docker-compose.yml" && \
     ! -e "$PROYEK/compose.minimum.yml" ]] || \
    gagal 'Deployment SnapOtter sudah ada. Instalasi otomatis dibatalkan agar data tidak tertimpa.'
  if command -v caddy >/dev/null 2>&1; then
    gagal 'Caddy sudah terpasang. Hindari menimpa konfigurasi situs yang ada.'
  fi
  if [[ -e /etc/apt/sources.list.d/docker.sources ]] && ! command -v docker >/dev/null 2>&1; then
    gagal 'Repositori Docker sudah dikonfigurasi tetapi Docker tidak ditemukan. Periksa keadaan VPS.'
  fi

  info 'Memulai instalasi SnapOtter pada VPS baru.'
  echo 'Sebelum melanjutkan, pastikan DNS A record dan port TCP 80/443 sudah disiapkan.'
  sudo -v
  konfigurasi_swap
  instal_docker
  buat_konfigurasi "$domain"
  jalankan_container
  konfigurasi_firewall
  konfigurasi_caddy "$domain"

  info '7/7 Memeriksa layanan lokal dan HTTPS'
  coba_api http://127.0.0.1:1349/api/v1/health 'API lokal' || \
    gagal 'API lokal belum dapat diakses. Periksa docker compose logs.'
  if ! coba_api "https://$domain/api/v1/health" 'API HTTPS'; then
    echo 'HTTPS belum siap. Periksa DNS, firewall TCP 80/443, dan journalctl -u caddy.' >&2
    exit 1
  fi
  cek_layanan
  echo
  echo 'Instalasi selesai. Login dengan username admin.'
  echo "Alamat: https://$domain"
  echo "Password admin tersimpan di $PROYEK/.env (JANGAN unggah ke GitHub)."
}

perintah="${1:-}"
case "$perintah" in
  bantuan|-h|--help|'')
    bantuan
    exit 0
    ;;
esac
periksa_pengguna
case "$perintah" in
  instal)
    instal_baru "${2:-}"
    ;;
  jalankan)
    periksa_proyek
    jalankan_container
    ;;
  status)
    periksa_proyek
    "${COMPOSE[@]}" ps
    ;;
  cek)
    periksa_proyek
    cek_layanan
    ;;
  restart)
    periksa_proyek
    "${COMPOSE[@]}" restart SnapOtter
    "${COMPOSE[@]}" ps
    ;;
  log)
    periksa_proyek
    "${COMPOSE[@]}" logs --tail=50 SnapOtter
    ;;
  backup-db)
    periksa_proyek
    backup_database
    ;;
  bantuan|-h|--help|'')
    bantuan
    ;;
  *)
    bantuan >&2
    exit 1
    ;;
esac

"""Unit tests for the hardening changes in otomatisasi_snapotter.sh.

Uses only Python's standard library and the script's existing Bash/coreutils
dependencies. Run explicitly with:
    python3 -B -m unittest discover -s tests -p 'test_otomatisasi_snapotter.py' -v

Each test runs the production function definitions in a fresh Bash process.
The CLI dispatcher is excluded, host paths point to temporary fixtures, and
privileged commands and network access are replaced by strict test doubles.
No Docker daemon, root access, package installation, or network is needed.
"""

import gzip
import hashlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "otomatisasi_snapotter.sh"
BASH = shutil.which("bash")
COMPOSE_CONTENT = "services:\n  SnapOtter:\n    image: snapotter/snapotter:2.2.0\n"
DIGEST = "snapotter/snapotter@sha256:" + "a" * 64
NEW_DIGEST = "snapotter/snapotter@sha256:" + "b" * 64
SQL = "CREATE TABLE regression (id integer);\nINSERT INTO regression VALUES (1);\n"
DAY = 24 * 60 * 60


# These doubles never delegate sudo or network calls to real executables.
# Unexpected operations fail rather than silently succeeding.
DOUBLES = r'''
record() {
  printf '%s\t' "$@" >> "$TEST_CALLS"
  printf '\n' >> "$TEST_CALLS"
}

unexpected() {
  printf 'Unexpected test command: %s\n' "$*" >&2
  return 97
}

docker() { unexpected docker "$@"; }
curl() { unexpected curl "$@"; }
openssl() { unexpected openssl "$@"; }

# Make installer preflight checks independent of software on the test host.
command() {
  if [[ "${1:-}" == -v && "${2:-}" == caddy ]]; then
    return 1
  fi
  builtin command "$@"
}

sudo() {
  record "$@"
  case "${1:-}" in
    -v) return 0 ;;
    docker)
      case "${2:-}" in
        compose)
          shift 2
          while [[ "${1:-}" == --project-directory || "${1:-}" == --env-file || "${1:-}" == -f ]]; do
            shift 2
          done
          if [[ "$1" == "${FAIL_COMPOSE_ACTION:-}" ]]; then return 43; fi
          case "$1" in
            config|version|pull|up|ps) return 0 ;;
            exec)
              printf '%s' "$DUMP_CONTENT"
              return "${DUMP_STATUS:-0}"
              ;;
          esac
          ;;
        image)
          [[ "${3:-}" == inspect ]] || { unexpected docker "$@"; return 97; }
          printf '%s' "$FIXTURE_DIGESTS"
          return "${DIGEST_STATUS:-0}"
          ;;
        inspect)
          printf '%s' "$FIXTURE_VOLUME"
          return "${VOLUME_INSPECT_STATUS:-0}"
          ;;
        run)
          [[ "${ARCHIVE_STATUS:-0}" == 0 ]] || return "$ARCHIVE_STATUS"
          local arg
          for arg in "$@"; do
            if [[ "$arg" == /backup/data-*.tar.gz ]]; then
              # Simulate the container writing its archive to the bind mount.
              printf 'synthetic archive\n' > "$TEST_PROJECT/backups/${arg##*/}"
              return 0
            fi
          done
          ;;
      esac
      ;;
    swapon)
      if [[ "${2:-}" == --show ]]; then
        printf '%s' "${ACTIVE_SWAP:-}"
        return 0
      fi
      return "${SWAPON_STATUS:-0}"
      ;;
    fallocate) return "${FALLOCATE_STATUS:-0}" ;;
    dd) return "${DD_STATUS:-0}" ;;
    chmod) return 0 ;;
    mkswap) return "${MKSWAP_STATUS:-0}" ;;
    chown) return "${CHOWN_STATUS:-0}" ;;
    tee)
      [[ "$#" == 3 && "$2" == -a && "$3" == "$TEST_FSTAB" ]] || {
        unexpected tee "$@"; return 97;
      }
      cat >> "$TEST_FSTAB"
      return 0
      ;;
    apt-get) return "${APT_STATUS:-0}" ;;
    ufw)
      [[ "$*" != "${FAIL_UFW:-}" ]] || return 43
      return 0
      ;;
  esac
  unexpected sudo "$@"
}
'''


class BashFunctionTestCase(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(BASH, "These tests require Bash, as does the script")
        temporary = tempfile.TemporaryDirectory(prefix="snapotter-tests-")
        self.addCleanup(temporary.cleanup)
        self.sandbox = Path(temporary.name)
        # Spaces exercise quoting of project, backup, and lock file paths.
        self.project = self.sandbox / "deployment with spaces"
        self.project.mkdir()
        self.calls_file = self.sandbox / "calls.tsv"
        self.calls_file.touch()
        self.fstab = self.sandbox / "fstab"
        self.fstab.write_text("# synthetic fstab\n", encoding="utf-8")
        self.swapfile = self.sandbox / "swapfile"
        release = self.sandbox / "os-release"
        release.write_text('ID=ubuntu\nVERSION_ID="24.04"\n', encoding="utf-8")

        source = SCRIPT.read_text(encoding="utf-8")
        marker = '\nperintah="${1:-}"\n'
        self.assertEqual(source.count(marker), 1, "CLI boundary changed; update the test loader")
        self.library = source.split(marker, 1)[0]
        # Change only configuration paths; execute the original function bodies.
        replacements = {
            'PROYEK="$HOME/snapotter"': 'PROYEK="${TEST_PROJECT:?}"',
            "/swapfile": str(self.swapfile),
            "/etc/fstab": str(self.fstab),
            "/etc/os-release": str(release),
            "/etc/apt/sources.list.d/docker.sources": str(self.sandbox / "docker.sources"),
        }
        for original, replacement in replacements.items():
            self.assertIn(original, self.library)
            self.library = self.library.replace(original, replacement)

        # A clean environment also prevents BASH_ENV or exported functions from
        # injecting host behavior, and makes the default retention deterministic.
        self.environment = {
            "PATH": os.defpath,
            "LANG": "C.UTF-8",
            "TEST_PROJECT": str(self.project),
            "TEST_CALLS": str(self.calls_file),
            "TEST_FSTAB": str(self.fstab),
            "FIXTURE_DIGESTS": DIGEST + "\n",
            "FIXTURE_VOLUME": "snapotter_data",
            "DUMP_CONTENT": SQL,
        }
        self.compose_prefix = [
            "docker", "compose", "--project-directory", str(self.project),
            "--env-file", str(self.project / ".env"),
            "-f", str(self.project / "docker-compose.yml"),
            "-f", str(self.project / "compose.minimum.yml"),
        ]

    def run_bash(self, body, *, env=None, expected=0):
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", self.library + "\n" + DOUBLES + "\n" + body],
            cwd=self.sandbox,
            env={**self.environment, **(env or {})},
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        self.assertEqual(
            result.returncode, expected,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def calls(self):
        return [line.split("\t")[:-1] for line in self.calls_file.read_text().splitlines()]

    def compose_calls(self):
        result = []
        for call in self.calls():
            if call[:2] == ["docker", "compose"]:
                # Preflight probes the Compose plugin before using project flags.
                if call == ["docker", "compose", "version"]:
                    result.append(["version"])
                    continue
                self.assertEqual(call[:len(self.compose_prefix)], self.compose_prefix)
                result.append(call[len(self.compose_prefix):])
        return result

    def seed_compose(self, *, checksum=True):
        (self.project / "docker-compose.yml").write_text(COMPOSE_CONTENT, encoding="utf-8")
        (self.project / "compose.minimum.yml").write_text("services: {}\n", encoding="utf-8")
        (self.project / ".env").write_text("# synthetic credentials\n", encoding="utf-8")
        if checksum:
            digest = hashlib.sha256(COMPOSE_CONTENT.encode()).hexdigest()
            (self.project / ".compose.sha256").write_text(digest + "\n", encoding="utf-8")

    def old_backup(self, name="postgres-expired.sql.gz", *, days=40):
        backups = self.project / "backups"
        backups.mkdir(exist_ok=True)
        path = backups / name
        path.write_bytes(b"synthetic old backup")
        modified = time.time() - days * DAY
        os.utime(path, (modified, modified))
        return path


class ComposeIntegrityTests(BashFunctionTestCase):
    def test_legacy_deployment_without_checksum_is_accepted(self):
        self.seed_compose(checksum=False)
        self.run_bash("periksa_proyek")
        self.assertFalse((self.project / ".compose.sha256").exists())
        self.assertEqual(self.compose_calls(), [["version"]])

    def test_matching_checksum_is_accepted_without_rewriting_lock(self):
        self.seed_compose()
        lock = self.project / ".compose.sha256"
        os.utime(lock, (1, 1))
        self.run_bash("verifikasi_compose")
        self.assertEqual(lock.stat().st_mtime_ns, 1_000_000_000)
        self.assertEqual(self.calls(), [])

    def test_tampered_compose_is_rejected_by_project_preflight(self):
        self.seed_compose()
        (self.project / "docker-compose.yml").write_text("services: {unexpected: {}}\n")
        result = self.run_bash("periksa_proyek", expected=1)
        self.assertIn("Checksum docker-compose.yml tidak cocok", result.stderr)
        self.assertEqual(self.compose_calls(), [["version"]])

    def test_empty_or_malformed_checksum_fails_closed(self):
        self.seed_compose()
        for checksum in ("", "not-a-sha256\n"):
            with self.subTest(checksum=checksum):
                (self.project / ".compose.sha256").write_text(checksum)
                result = self.run_bash("verifikasi_compose", expected=1)
                self.assertIn("Checksum docker-compose.yml tidak cocok", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_checksum_read_failure_aborts_verification(self):
        self.seed_compose()
        self.run_bash("cat() { return 1; }; verifikasi_compose", expected=1)
        self.assertEqual(self.calls(), [])

    def test_checksum_calculation_failure_aborts_verification(self):
        self.seed_compose()
        self.run_bash("sha256sum() { return 1; }; verifikasi_compose", expected=1)
        self.assertEqual(self.calls(), [])

    def test_launch_rejects_tampering_before_any_docker_operation(self):
        self.seed_compose()
        with (self.project / "docker-compose.yml").open("a") as compose:
            compose.write("# changed after installation\n")
        self.run_bash("jalankan_container", expected=1)
        self.assertEqual(self.calls(), [])

    def test_configuration_records_downloaded_content_checksum_privately(self):
        result = self.run_bash(r'''
curl() {
  record curl "$@"
  [[ "$4" == -fsSLo ]] || return 97
  printf '%s' "$FIXTURE_COMPOSE" > "$5"
}
openssl() { printf '%064d' 0; }
buat_konfigurasi example.test
verifikasi_compose
''', env={"FIXTURE_COMPOSE": COMPOSE_CONTENT})
        lock = self.project / ".compose.sha256"
        downloaded = (self.project / "docker-compose.yml").read_bytes()
        self.assertEqual(lock.read_text(), hashlib.sha256(downloaded).hexdigest() + "\n")
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        self.assertEqual(self.calls()[0], [
            "curl", "--proto", "=https", "--tlsv1.2", "-fsSLo",
            str(self.project / "docker-compose.yml"),
            "https://raw.githubusercontent.com/snapotter-hq/SnapOtter/v2.2.0/docker/docker-compose.yml",
        ])
        self.assertEqual(self.compose_calls(), [["config", "--quiet"]])
        self.assertEqual(result.stderr, "")

    def test_failed_download_does_not_create_checksum_or_start_containers(self):
        self.run_bash("curl() { return 22; }; buat_konfigurasi example.test", expected=22)
        self.assertFalse((self.project / ".compose.sha256").exists())
        self.assertEqual(self.calls(), [])

    def test_launch_checks_config_then_pulls_inspects_digest_and_starts(self):
        self.seed_compose()
        self.run_bash("jalankan_container")
        self.assertEqual(self.compose_calls(), [
            ["config", "--quiet"], ["pull"], ["up", "-d", "--no-build"], ["ps"],
        ])
        self.assertEqual([call[:3] for call in self.calls()], [
            ["docker", "compose", "--project-directory"],
            ["docker", "compose", "--project-directory"],
            ["docker", "image", "inspect"],
            ["docker", "compose", "--project-directory"],
            ["docker", "compose", "--project-directory"],
        ])
        self.assertEqual((self.project / ".image-digest.lock").read_text(), DIGEST + "\n")

    def test_invalid_compose_stops_before_pull(self):
        self.seed_compose()
        self.run_bash("jalankan_container", env={"FAIL_COMPOSE_ACTION": "config"}, expected=43)
        self.assertEqual(self.compose_calls(), [["config", "--quiet"]])
        self.assertFalse((self.project / ".image-digest.lock").exists())

    def test_failed_pull_stops_before_digest_recording_or_start(self):
        self.seed_compose()
        self.run_bash("jalankan_container", env={"FAIL_COMPOSE_ACTION": "pull"}, expected=43)
        self.assertEqual(self.compose_calls(), [["config", "--quiet"], ["pull"]])
        self.assertEqual(len(self.calls()), 2)
        self.assertFalse((self.project / ".image-digest.lock").exists())


class ImageDigestTests(BashFunctionTestCase):
    def test_first_pull_records_only_first_repo_digest_with_private_permissions(self):
        result = self.run_bash("kunci_digest_image", env={
            "FIXTURE_DIGESTS": DIGEST + "\n" + NEW_DIGEST + "\n",
        })
        lock = self.project / ".image-digest.lock"
        self.assertEqual(lock.read_text(), DIGEST + "\n")
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        self.assertEqual(self.calls(), [[
            "docker", "image", "inspect", "--format",
            "{{range .RepoDigests}}{{println .}}{{end}}", "snapotter/snapotter:2.2.0",
        ]])
        self.assertIn(DIGEST, result.stdout)
        self.assertEqual(result.stderr, "")

    def test_same_digest_does_not_warn_or_rewrite_existing_lock(self):
        lock = self.project / ".image-digest.lock"
        lock.write_text(DIGEST + "\n")
        os.utime(lock, (1, 1))
        result = self.run_bash("kunci_digest_image")
        self.assertEqual(result.stderr, "")
        self.assertEqual(lock.read_text(), DIGEST + "\n")
        self.assertEqual(lock.stat().st_mtime_ns, 1_000_000_000)

    def test_changed_digest_warns_and_preserves_original_lock_but_allows_launch(self):
        self.seed_compose()
        lock = self.project / ".image-digest.lock"
        lock.write_text(DIGEST + "\n")
        result = self.run_bash("jalankan_container", env={"FIXTURE_DIGESTS": NEW_DIGEST + "\n"})
        self.assertIn("PERINGATAN: digest image berubah", result.stderr)
        self.assertIn(DIGEST, result.stderr)
        self.assertIn(NEW_DIGEST, result.stderr)
        self.assertEqual(lock.read_text(), DIGEST + "\n")
        self.assertIn(["up", "-d", "--no-build"], self.compose_calls())

    def test_missing_digest_warns_without_creating_lock(self):
        result = self.run_bash("kunci_digest_image", env={"FIXTURE_DIGESTS": ""})
        self.assertIn("digest image tidak terbaca", result.stderr)
        self.assertFalse((self.project / ".image-digest.lock").exists())

    def test_inspect_failure_is_nonfatal_without_creating_lock(self):
        result = self.run_bash("kunci_digest_image", env={"FIXTURE_DIGESTS": "", "DIGEST_STATUS": "1"})
        self.assertIn("digest image tidak terbaca", result.stderr)
        self.assertFalse((self.project / ".image-digest.lock").exists())

    def test_unreadable_digest_keeps_previous_lock(self):
        lock = self.project / ".image-digest.lock"
        lock.write_text(DIGEST + "\n")
        self.run_bash("kunci_digest_image", env={"FIXTURE_DIGESTS": "", "DIGEST_STATUS": "1"})
        self.assertEqual(lock.read_text(), DIGEST + "\n")

    def test_digest_lock_write_failure_prevents_container_start(self):
        self.seed_compose()
        # A directory at the lock path deterministically rejects file creation,
        # including when these tests are run by root.
        (self.project / ".image-digest.lock").mkdir()
        self.run_bash("jalankan_container", expected=1)
        self.assertEqual(self.compose_calls(), [["config", "--quiet"], ["pull"]])

    def test_digest_lock_permission_failure_prevents_container_start(self):
        self.seed_compose()
        self.run_bash("chmod() { return 1; }; jalankan_container", expected=1)
        self.assertEqual(self.compose_calls(), [["config", "--quiet"], ["pull"]])


class SwapTests(BashFunctionTestCase):
    def expected_creation_calls(self, *, fallback=False, persist=True):
        calls = [["swapon", "--show"], ["fallocate", "-l", "2G", str(self.swapfile)]]
        if fallback:
            calls.append(["dd", "if=/dev/zero", f"of={self.swapfile}", "bs=1M", "count=2048"])
        calls.extend([
            ["chmod", "600", str(self.swapfile)],
            ["mkswap", str(self.swapfile)],
            ["swapon", str(self.swapfile)],
        ])
        if persist:
            calls.append(["tee", "-a", str(self.fstab)])
        return calls

    def test_active_swap_skips_creation_and_fstab_changes(self):
        before = self.fstab.read_text()
        self.run_bash("konfigurasi_swap", env={"ACTIVE_SWAP": "NAME TYPE SIZE USED PRIO\n/dev/vda swap 2G 0B -2\n"})
        self.assertEqual(self.calls(), [["swapon", "--show"]])
        self.assertEqual(self.fstab.read_text(), before)
        self.assertFalse(self.swapfile.exists())

    def test_existing_inactive_swapfile_is_preserved(self):
        self.swapfile.write_bytes(b"existing swap sentinel")
        before = self.fstab.read_text()
        self.run_bash("konfigurasi_swap")
        self.assertEqual(self.calls(), [["swapon", "--show"]])
        self.assertEqual(self.swapfile.read_bytes(), b"existing swap sentinel")
        self.assertEqual(self.fstab.read_text(), before)

    def test_new_swap_is_sized_secured_formatted_enabled_and_persisted(self):
        self.run_bash("konfigurasi_swap")
        self.assertEqual(self.calls(), self.expected_creation_calls())
        self.assertEqual(self.fstab.read_text(), f"# synthetic fstab\n{self.swapfile} none swap sw 0 0\n")

    def test_dd_fallback_is_used_if_fallocate_is_unsupported(self):
        self.run_bash("konfigurasi_swap", env={"FALLOCATE_STATUS": "1"})
        self.assertEqual(self.calls(), self.expected_creation_calls(fallback=True))
        self.assertIn(f"{self.swapfile} none swap sw 0 0\n", self.fstab.read_text())

    def test_allocation_failure_stops_before_formatting_or_persisting(self):
        before = self.fstab.read_text()
        self.run_bash("konfigurasi_swap", env={"FALLOCATE_STATUS": "1", "DD_STATUS": "1"}, expected=1)
        self.assertEqual(self.calls(), self.expected_creation_calls(fallback=True)[:3])
        self.assertEqual(self.fstab.read_text(), before)

    def test_existing_fstab_entry_is_not_duplicated(self):
        entry = f"{self.swapfile}\tnone swap sw 0 0\n"
        self.fstab.write_text(entry)
        self.run_bash("konfigurasi_swap")
        self.assertEqual(self.calls(), self.expected_creation_calls(persist=False))
        self.assertEqual(self.fstab.read_text(), entry)

    def test_format_failure_does_not_enable_or_persist_swap(self):
        before = self.fstab.read_text()
        self.run_bash("konfigurasi_swap", env={"MKSWAP_STATUS": "1"}, expected=1)
        self.assertEqual(self.calls(), self.expected_creation_calls()[:4])
        self.assertEqual(self.fstab.read_text(), before)

    def test_activation_failure_does_not_persist_swap(self):
        before = self.fstab.read_text()
        self.run_bash("konfigurasi_swap", env={"SWAPON_STATUS": "1"}, expected=1)
        self.assertEqual(self.calls(), self.expected_creation_calls(persist=False))
        self.assertEqual(self.fstab.read_text(), before)


class FirewallTests(BashFunctionTestCase):
    EXPECTED = [
        ["apt-get", "install", "-y", "ufw"],
        ["ufw", "allow", "OpenSSH"],
        ["ufw", "allow", "80/tcp"],
        ["ufw", "allow", "443/tcp"],
        ["ufw", "default", "deny", "incoming"],
        ["ufw", "default", "allow", "outgoing"],
        ["ufw", "--force", "enable"],
        ["ufw", "status", "verbose"],
    ]

    def test_required_access_and_defaults_are_configured_before_enabling(self):
        self.run_bash("konfigurasi_firewall")
        self.assertEqual(self.calls(), self.EXPECTED)

    def test_package_install_failure_does_not_change_firewall(self):
        self.run_bash("konfigurasi_firewall", env={"APT_STATUS": "100"}, expected=100)
        self.assertEqual(self.calls(), self.EXPECTED[:1])

    def test_rule_failure_aborts_before_enabling_firewall(self):
        for index in range(1, 6):
            with self.subTest(rule=self.EXPECTED[index]):
                self.calls_file.write_text("")
                self.run_bash("konfigurasi_firewall", env={
                    "FAIL_UFW": " ".join(self.EXPECTED[index]),
                }, expected=43)
                self.assertEqual(self.calls(), self.EXPECTED[:index + 1])

    def test_enable_failure_stops_before_status_query(self):
        self.run_bash("konfigurasi_firewall", env={"FAIL_UFW": "ufw --force enable"}, expected=43)
        self.assertEqual(self.calls(), self.EXPECTED[:-1])


class InstallationOrderTests(BashFunctionTestCase):
    STAGES = r'''
konfigurasi_swap() { record swap; return "${SWAP_STAGE_STATUS:-0}"; }
instal_docker() { record install_docker; }
buat_konfigurasi() { record configure "$@"; }
jalankan_container() { record containers; }
konfigurasi_firewall() { record firewall; return "${FIREWALL_STAGE_STATUS:-0}"; }
konfigurasi_caddy() { record caddy "$@"; }
coba_api() { record health "$@"; }
cek_layanan() { record services; }
instal_baru example.test
'''

    def test_installation_prepares_swap_and_firewall_at_required_stages(self):
        self.run_bash(self.STAGES)
        self.assertEqual(self.calls(), [
            ["-v"], ["swap"], ["install_docker"], ["configure", "example.test"],
            ["containers"], ["firewall"], ["caddy", "example.test"],
            ["health", "http://127.0.0.1:1349/api/v1/health", "API lokal"],
            ["health", "https://example.test/api/v1/health", "API HTTPS"], ["services"],
        ])

    def test_swap_failure_aborts_before_docker_installation(self):
        self.run_bash(self.STAGES, env={"SWAP_STAGE_STATUS": "1"}, expected=1)
        self.assertEqual(self.calls(), [["-v"], ["swap"]])

    def test_firewall_failure_aborts_before_caddy_and_health_checks(self):
        self.run_bash(self.STAGES, env={"FIREWALL_STAGE_STATUS": "1"}, expected=1)
        self.assertEqual(self.calls(), [
            ["-v"], ["swap"], ["install_docker"], ["configure", "example.test"],
            ["containers"], ["firewall"],
        ])


class BackupTests(BashFunctionTestCase):
    def database_backup(self):
        files = list((self.project / "backups").glob("postgres-*.sql.gz"))
        self.assertEqual(len(files), 1)
        with gzip.open(files[0], "rt", encoding="utf-8") as backup:
            self.assertEqual(backup.read(), SQL)
        return files[0]

    def test_database_and_volume_share_stamp_and_archive_volume_read_only(self):
        result = self.run_bash("backup_database")
        database = self.database_backup()
        self.assertRegex(database.name, r"^postgres-\d{8}-\d{6}-\d+\.sql\.gz$")
        stamp = database.name.removeprefix("postgres-").removesuffix(".sql.gz")
        archive = self.project / "backups" / f"data-{stamp}.tar.gz"
        self.assertTrue(archive.is_file())
        self.assertEqual(stat.S_IMODE(database.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(database.parent.stat().st_mode), 0o700)
        self.assertEqual(list(database.parent.glob(".db-*")), [])
        self.assertEqual(self.compose_calls(), [[
            "exec", "-T", "postgres", "sh", "-c",
            'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
        ]])
        self.assertEqual(self.calls()[1:], [
            ["docker", "inspect", "SnapOtter", "--format",
             '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}'],
            ["docker", "run", "--rm", "-v", "snapotter_data:/data:ro",
             "-v", f"{database.parent}:/backup", "alpine:3.22",
             "tar", "-czf", f"/backup/data-{stamp}.tar.gz", "-C", "/data", "."],
            ["chown", f"{os.getuid()}:{os.getgid()}", str(archive)],
        ])
        self.assertIn(str(database), result.stdout)
        self.assertIn(str(archive), result.stdout)
        self.assertEqual(result.stderr, "")

    def test_failed_pg_dump_cleans_partial_file_and_preserves_existing_backups(self):
        old = self.old_backup()
        result = self.run_bash("backup_database", env={"DUMP_STATUS": "1"}, expected=1)
        self.assertIn("Backup PostgreSQL gagal", result.stderr)
        self.assertEqual(sorted(old.parent.iterdir()), [old])
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.compose_calls()[0][:3], ["exec", "-T", "postgres"])

    def test_compression_failure_cleans_partial_file_and_skips_volume_and_pruning(self):
        old = self.old_backup()
        result = self.run_bash(r'''
gzip() { cat >/dev/null; return 1; }
backup_database
''', expected=1)
        self.assertIn("Backup PostgreSQL gagal", result.stderr)
        self.assertEqual(sorted(old.parent.iterdir()), [old])
        self.assertEqual(len(self.calls()), 1)

    def test_missing_data_volume_keeps_database_and_still_prunes(self):
        old = self.old_backup()
        result = self.run_bash("backup_database", env={"FIXTURE_VOLUME": ""})
        self.database_backup()
        self.assertIn("volume /data tidak ditemukan", result.stderr)
        self.assertFalse(old.exists())
        self.assertFalse(any(call[:2] == ["docker", "run"] for call in self.calls()))
        self.assertEqual(list((self.project / "backups").glob("data-*.tar.gz")), [])

    def test_failed_volume_lookup_is_nonfatal_and_preserves_database(self):
        result = self.run_bash("backup_database", env={"FIXTURE_VOLUME": "", "VOLUME_INSPECT_STATUS": "1"})
        self.database_backup()
        self.assertIn("volume /data tidak ditemukan", result.stderr)
        self.assertEqual(len(self.calls()), 2)

    def test_failed_volume_archive_warns_and_retains_successful_database(self):
        old = self.old_backup()
        result = self.run_bash("backup_database", env={"ARCHIVE_STATUS": "1"})
        self.database_backup()
        self.assertIn("backup volume /data gagal", result.stderr)
        self.assertFalse(old.exists())
        self.assertFalse(any(call[0] == "chown" for call in self.calls()))
        self.assertEqual(list((self.project / "backups").glob("data-*.tar.gz")), [])

    def test_ownership_adjustment_failure_does_not_discard_successful_backups(self):
        result = self.run_bash("backup_database", env={"CHOWN_STATUS": "1"})
        database = self.database_backup()
        self.assertEqual(len(list(database.parent.glob("data-*.tar.gz"))), 1)
        self.assertIn("Backup volume /data:", result.stdout)
        self.assertNotIn("backup volume /data gagal", result.stderr)


class BackupRetentionTests(BashFunctionTestCase):
    def assert_retention(self, env, days):
        expired_db = self.old_backup("postgres-expired.sql.gz", days=days + 1.5)
        expired_data = self.old_backup("data-expired.tar.gz", days=days + 1.5)
        # find -mtime +N compares whole days: N days and 12 hours is retained.
        boundary_db = self.old_backup("postgres-boundary.sql.gz", days=days + 0.5)
        boundary_data = self.old_backup("data-boundary.tar.gz", days=days + 0.5)
        recent = self.old_backup("postgres-recent.sql.gz", days=0)
        result = self.run_bash("prune_backup", env=env)
        for expired in (expired_db, expired_data):
            self.assertFalse(expired.exists())
            self.assertIn(str(expired), result.stdout)
        for kept in (boundary_db, boundary_data, recent):
            self.assertTrue(kept.exists())
            self.assertNotIn(str(kept), result.stdout)
        self.assertIn(f"(>{days} hari)", result.stdout)

    def test_default_retention_is_fourteen_days_with_whole_day_boundary(self):
        self.assert_retention({}, 14)

    def test_empty_environment_value_uses_default_retention(self):
        self.assert_retention({"BACKUP_RETENSI_HARI": ""}, 14)

    def test_custom_retention_keeps_backups_younger_than_override(self):
        kept = self.old_backup("postgres-fifteen-days.sql.gz", days=15)
        self.assert_retention({"BACKUP_RETENSI_HARI": "30"}, 30)
        self.assertTrue(kept.exists())

    def test_zero_day_override_is_respected(self):
        self.assert_retention({"BACKUP_RETENSI_HARI": "0"}, 0)

    def test_pruning_preserves_unrelated_files_subdirectories_and_symlinks(self):
        protected = [self.old_backup(name) for name in (
            "manual.dump", "postgres.sql.gz", "data.tar.gz", ".db-incomplete",
            "postgres-expired.sql.gz.bak", "data-expired.tar.gz.bak",
        )]
        backups = self.project / "backups"
        nested = backups / "nested"
        nested.mkdir()
        nested_backup = nested / "postgres-expired.sql.gz"
        nested_backup.write_bytes(b"nested sentinel")
        matching_directory = backups / "data-directory.tar.gz"
        matching_directory.mkdir()
        external = self.sandbox / "postgres-external.sql.gz"
        external.write_bytes(b"external sentinel")
        symlink = backups / "postgres-link.sql.gz"
        symlink.symlink_to(external)
        old_time = time.time() - 40 * DAY
        for path in (nested_backup, matching_directory, external):
            os.utime(path, (old_time, old_time))
        os.utime(symlink, (old_time, old_time), follow_symlinks=False)
        expired = self.old_backup()
        self.run_bash("prune_backup")
        self.assertFalse(expired.exists())
        for path in protected + [nested_backup, matching_directory]:
            self.assertTrue(path.exists(), str(path))
        self.assertTrue(symlink.is_symlink())
        self.assertEqual(external.read_bytes(), b"external sentinel")
        self.assertEqual(nested_backup.read_bytes(), b"nested sentinel")

    def test_no_expired_files_produces_no_deletion_message(self):
        recent = self.old_backup(days=0)
        result = self.run_bash("prune_backup")
        self.assertTrue(recent.exists())
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_unavailable_backup_directory_is_nonfatal(self):
        result = self.run_bash("prune_backup")
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_invalid_retention_is_nonfatal_and_preserves_backups(self):
        old = self.old_backup()
        for retention in ("not-a-number", "14 -delete"):
            with self.subTest(retention=retention):
                result = self.run_bash("prune_backup", env={"BACKUP_RETENSI_HARI": retention})
                self.assertTrue(old.exists())
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")


class HelpTests(BashFunctionTestCase):
    def test_help_describes_new_backup_scope_retention_and_host_hardening(self):
        result = self.run_bash("bantuan")
        for text in ("volume /data", "BACKUP_RETENSI_HARI", "default 14 hari", "swapfile 2 GB", "firewall UFW"):
            with self.subTest(text=text):
                self.assertIn(text, result.stdout)
        self.assertEqual(self.calls(), [])


class GitignoreTests(unittest.TestCase):
    def check_ignore(self, paths, expected):
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin", "-z"],
            cwd=ROOT,
            input="\0".join(paths) + "\0",
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
            env={"PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        )
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.split("\0")[:-1]

    def test_credentials_deployment_state_and_backup_artifacts_are_ignored(self):
        paths = [
            ".env", ".domain", ".image-digest.lock", ".compose.sha256",
            "docker-compose.yml", "compose.minimum.yml", "backups/private.txt",
            "postgres-example.sql.gz", "manual.dump", "data-example.tar.gz",
        ]
        self.assertEqual(self.check_ignore(paths, 0), paths)

    def test_source_documentation_and_tests_remain_visible_to_git(self):
        self.assertEqual(self.check_ignore([
            "otomatisasi_snapotter.sh", "README.md", "tests/test_otomatisasi_snapotter.py",
        ], 1), [])


if __name__ == "__main__":
    unittest.main()

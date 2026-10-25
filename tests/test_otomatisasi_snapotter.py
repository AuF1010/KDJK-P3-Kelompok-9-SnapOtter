"""Unit tests for PR #2's deployment hardening, using only the standard library.

Run explicitly with: python3 -B -m unittest discover -s tests -v
Requires Bash and the GNU utilities used by otomatisasi_snapotter.sh on Ubuntu.
Each Bash subprocess has a five-second timeout. No Docker daemon, network,
sudo privileges, or running deployment is needed.

The script has no source-only entry point. Load its declarations before the CLI
dispatcher, then invoke the real functions with command doubles. Only absolute
host paths for swap/fstab and installer preconditions are redirected to fixtures;
function logic is preserved. An unknown privileged command fails the test rather
than reaching the host. All fixtures are removed by TemporaryDirectory.
"""

import gzip
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import unittest


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "otomatisasi_snapotter.sh"
SOURCE, DISPATCHER, _ = SCRIPT.read_text().partition('\nperintah="${1:-}"\n')
if not DISPATCHER:
    raise RuntimeError("CLI boundary changed; review the source-only test loader")


DOUBLES = r"""
PROYEK="$TEST_PROJECT"
COMPOSE=(compose_double)

record() {
  {
    printf '%s' "$1"
    shift
    if (( $# )); then printf ' <%s>' "$@"; fi
    printf '\n'
  } >> "$TEST_LOG"
}

unexpected() {
  printf '%s\n' "$*" >> "$TEST_ROOT/unexpected"
  printf 'Unexpected external command: %s\n' "$*" >&2
  return 97
}

# These functions never delegate to the real privileged or network commands.
sudo() {
  record sudo "$@"
  if [[ -n "${MOCK_FAIL_COMMAND:-}" && "$*" == "$MOCK_FAIL_COMMAND" ]]; then
    return 23
  fi
  case "$1 ${2:-} ${3:-}" in
    'docker compose version') return 0 ;;
    'docker image inspect')
      printf '%s' "${MOCK_DIGEST:-}"
      return "${MOCK_INSPECT_STATUS:-0}" ;;
    'docker inspect SnapOtter')
      printf '%s' "${MOCK_VOLUME:-}"
      return "${MOCK_VOLUME_STATUS:-0}" ;;
    'docker run --rm')
      [[ "${MOCK_ARCHIVE_STATUS:-0}" == 0 ]] || return "$MOCK_ARCHIVE_STATUS"
      local argument archive=''
      for argument in "$@"; do
        if [[ "$argument" == /backup/data-*.tar.gz ]]; then
          archive="$PROYEK/backups/${argument##*/}"
        fi
      done
      [[ -n "$archive" ]] || { unexpected "$@"; return 97; }
      tar -czf "$archive" -C "$TEST_ROOT/volume" . ;;
    'chown '*) return "${MOCK_CHOWN_STATUS:-0}" ;;
    'swapon --show ')
      printf '%s' "${MOCK_ACTIVE_SWAP:-}"
      return "${MOCK_SWAP_QUERY_STATUS:-0}" ;;
    'fallocate -l 2G') return "${MOCK_FALLOCATE_STATUS:-0}" ;;
    'dd if=/dev/zero '*) return "${MOCK_DD_STATUS:-0}" ;;
    'chmod 600 '*|'mkswap '*|'swapon '*) return 0 ;;
    'tee -a '*)
      [[ "$3" == "$TEST_ROOT/fstab" ]] || { unexpected "$@"; return 97; }
      cat >> "$TEST_ROOT/fstab" ;;
    'apt-get install -y'|'ufw allow '*|'ufw default '*|'ufw --force enable'|'ufw status verbose'|'-v  ')
      return 0 ;;
    *) unexpected "$@" ;;
  esac
}

docker() { unexpected docker "$@"; }

compose_double() {
  record compose "$@"
  if [[ -n "${MOCK_COMPOSE_FAIL:-}" && "$1" == "$MOCK_COMPOSE_FAIL" ]]; then
    return 24
  fi
  case "$1" in
    config|pull|up|ps) return 0 ;;
    exec)
      printf '%s' "$TEST_SQL"
      return "${MOCK_DUMP_STATUS:-0}" ;;
    *) unexpected compose "$@" ;;
  esac
}

curl() {
  record curl "$@"
  [[ "${MOCK_DOWNLOAD_STATUS:-0}" == 0 ]] || return "$MOCK_DOWNLOAD_STATUS"
  printf '%s' "$TEST_COMPOSE" > "$PROYEK/docker-compose.yml"
}

openssl() {
  [[ "$*" == 'rand -hex 32' ]] || { unexpected openssl "$@"; return 97; }
  printf '%064d\n' 1
}
"""


class DeploymentTestCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="snapotter-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        # Spaces catch missing quoting in project paths and Docker bind mounts.
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.log = self.root / "commands"
        self.log.touch()
        (self.root / "volume").mkdir()
        (self.root / "volume" / "upload.txt").write_text("synthetic upload\n")
        (self.root / "volume" / ".metadata").write_text("hidden fixture\n")
        (self.root / "fstab").write_text("# fixture fstab\n")
        (self.root / "os-release").write_text('ID=ubuntu\nVERSION_ID="24.04"\n')
        self.compose = "services:\n  SnapOtter:\n    image: snapotter/snapotter:2.2.0\n"
        self.sql = "-- synthetic fixture\nCREATE TABLE uploads (id integer);\n"
        self.env = os.environ.copy()
        # Do not let a caller's retention or Bash startup hooks affect cases.
        for name in ("BACKUP_RETENSI_HARI", "BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS"):
            self.env.pop(name, None)
        for name in list(self.env):
            if name.startswith(("MOCK_", "TEST_")):
                self.env.pop(name)
        self.env.update(
            TEST_ROOT=str(self.root), TEST_PROJECT=str(self.project),
            TEST_LOG=str(self.log), TEST_SQL=self.sql, TEST_COMPOSE=self.compose,
            LC_ALL="C",
        )

    def run_bash(self, body, *, status=0, **environment):
        source = SOURCE
        for original, fixture in (
            ("/swapfile", "swapfile"),
            ("/etc/fstab", "fstab"),
            ("/etc/os-release", "os-release"),
            ("/etc/apt/sources.list.d/docker.sources", "docker.sources"),
        ):
            source = source.replace(original, str(self.root / fixture))
        result = subprocess.run(
            ["bash", "--noprofile", "--norc", "-s", "--"],
            input=source + "\n" + DOUBLES + "\n" + body + "\n",
            text=True, capture_output=True, cwd=self.root,
            env={**self.env, **environment}, timeout=5, check=False,
        )
        unexpected = self.root / "unexpected"
        self.assertFalse(
            unexpected.exists(),
            unexpected.read_text() if unexpected.exists() else "",
        )
        if status is None:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result

    def calls(self):
        return self.log.read_text().splitlines()

    def prepare_project(self, *, checksum=True):
        (self.project / "docker-compose.yml").write_text(self.compose)
        (self.project / "compose.minimum.yml").write_text("services: {}\n")
        (self.project / ".env").write_text("# synthetic fixture\n")
        if checksum:
            self.lock_compose()

    def lock_compose(self):
        checksum = hashlib.sha256((self.project / "docker-compose.yml").read_bytes())
        (self.project / ".compose.sha256").write_text(checksum.hexdigest() + "\n")

    def backup_directory(self):
        directory = self.project / "backups"
        directory.mkdir(exist_ok=True)
        return directory

    def age_file(self, path, days):
        path.write_text("synthetic old backup\n")
        stamp = time.time() - days * 86400
        os.utime(path, (stamp, stamp))
        return path


class ComposeIntegrityTests(DeploymentTestCase):
    def test_legacy_deployment_without_checksum_is_accepted(self):
        self.prepare_project(checksum=False)
        self.run_bash("verifikasi_compose")
        self.assertFalse((self.project / ".compose.sha256").exists())

    def test_matching_checksum_is_accepted_without_rewriting_lock(self):
        self.prepare_project()
        lock = self.project / ".compose.sha256"
        before = lock.stat().st_mtime_ns
        self.run_bash("verifikasi_compose")
        self.assertEqual(lock.stat().st_mtime_ns, before)

    def test_modified_compose_is_rejected_and_lock_is_preserved(self):
        self.prepare_project()
        lock = (self.project / ".compose.sha256").read_bytes()
        (self.project / "docker-compose.yml").write_text(self.compose + "# altered\n")
        result = self.run_bash("verifikasi_compose", status=1)
        self.assertIn("Checksum docker-compose.yml tidak cocok", result.stderr)
        self.assertEqual((self.project / ".compose.sha256").read_bytes(), lock)

    def test_empty_or_invalid_checksum_cannot_bypass_verification(self):
        self.prepare_project()
        for checksum in ("", "not-a-sha256\n"):
            with self.subTest(checksum=checksum):
                (self.project / ".compose.sha256").write_text(checksum)
                self.run_bash("verifikasi_compose", status=1)

    def test_missing_compose_with_existing_lock_fails(self):
        (self.project / ".compose.sha256").write_text("0" * 64 + "\n")
        self.run_bash("verifikasi_compose", status=None)

    def test_project_preflight_applies_integrity_check(self):
        self.prepare_project()
        (self.project / "docker-compose.yml").write_text("# tampered\n")
        self.run_bash("periksa_proyek", status=1)
        self.assertEqual(self.calls(), ["sudo <docker> <compose> <version>"])

    def test_configuration_records_downloaded_bytes_and_private_checksum(self):
        self.run_bash("umask 022; buat_konfigurasi example.test")
        lock = self.project / ".compose.sha256"
        expected = hashlib.sha256(self.compose.encode()).hexdigest() + "\n"
        self.assertEqual(lock.read_text(), expected)
        self.assertEqual(lock.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.calls(), [
            "curl <--proto> <=https> <--tlsv1.2> <-fsSLo> "
            f"<{self.project}/docker-compose.yml> "
            "<https://raw.githubusercontent.com/snapotter-hq/SnapOtter/v2.2.0/docker/docker-compose.yml>",
            "compose <config> <--quiet>",
        ])

    def test_failed_download_does_not_create_checksum_or_validate(self):
        self.run_bash("buat_konfigurasi example.test", status=22, MOCK_DOWNLOAD_STATUS="22")
        self.assertFalse((self.project / ".compose.sha256").exists())
        self.assertFalse(any(call.startswith("compose") for call in self.calls()))


class ImageDigestTests(DeploymentTestCase):
    digest = "snapotter/snapotter@sha256:" + "a" * 64
    changed_digest = "snapotter/snapotter@sha256:" + "b" * 64

    def test_first_digest_is_locked_privately_and_only_first_result_is_used(self):
        self.run_bash(
            "umask 022; kunci_digest_image",
            MOCK_DIGEST=self.digest + "\n" + self.changed_digest + "\n",
        )
        lock = self.project / ".image-digest.lock"
        self.assertEqual(lock.read_text(), self.digest + "\n")
        self.assertEqual(lock.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.calls(), [
            "sudo <docker> <image> <inspect> <--format> "
            "<{{range .RepoDigests}}{{println .}}{{end}}> <snapotter/snapotter:2.2.0>",
        ])

    def test_matching_digest_is_silent_and_preserves_lock(self):
        lock = self.project / ".image-digest.lock"
        lock.write_text(self.digest + "\n")
        before = lock.stat().st_mtime_ns
        result = self.run_bash("kunci_digest_image", MOCK_DIGEST=self.digest + "\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(lock.stat().st_mtime_ns, before)

    def test_changed_digest_warns_with_both_values_without_replacing_lock(self):
        lock = self.project / ".image-digest.lock"
        lock.write_text(self.digest + "\n")
        result = self.run_bash("kunci_digest_image", MOCK_DIGEST=self.changed_digest + "\n")
        self.assertIn("PERINGATAN: digest image berubah", result.stderr)
        self.assertIn(self.digest, result.stderr)
        self.assertIn(self.changed_digest, result.stderr)
        self.assertEqual(lock.read_text(), self.digest + "\n")

    def test_missing_or_unreadable_digest_is_nonfatal_and_never_locks_empty_value(self):
        for inspect_status in ("0", "1"):
            with self.subTest(inspect_status=inspect_status):
                result = self.run_bash("kunci_digest_image", MOCK_INSPECT_STATUS=inspect_status)
                self.assertIn("digest image tidak terbaca", result.stderr)
                self.assertFalse((self.project / ".image-digest.lock").exists())

    def test_unreadable_digest_preserves_existing_lock(self):
        lock = self.project / ".image-digest.lock"
        lock.write_text(self.digest + "\n")
        self.run_bash("kunci_digest_image", MOCK_INSPECT_STATUS="1")
        self.assertEqual(lock.read_text(), self.digest + "\n")

    def test_launch_locks_digest_after_pull_and_before_start(self):
        self.prepare_project()
        self.run_bash("jalankan_container", MOCK_DIGEST=self.digest + "\n")
        calls = self.calls()
        self.assertEqual(calls[:2], ["compose <config> <--quiet>", "compose <pull>"])
        self.assertIn("<image> <inspect>", calls[2])
        self.assertEqual(calls[3:], ["compose <up> <-d> <--no-build>", "compose <ps>"])
        self.assertEqual((self.project / ".image-digest.lock").read_text(), self.digest + "\n")

    def test_launch_rejects_tampering_before_any_docker_operation(self):
        self.prepare_project()
        (self.project / "docker-compose.yml").write_text("# altered\n")
        self.run_bash("jalankan_container", status=1)
        self.assertEqual(self.calls(), [])

    def test_failed_validation_or_pull_prevents_lock_and_start(self):
        self.prepare_project()
        for failure in ("config", "pull"):
            with self.subTest(failure=failure):
                self.log.write_text("")
                self.run_bash("jalankan_container", status=24, MOCK_COMPOSE_FAIL=failure)
                expected = ["compose <config> <--quiet>"]
                if failure == "pull":
                    expected.append("compose <pull>")
                self.assertEqual(self.calls(), expected)
                self.assertFalse((self.project / ".image-digest.lock").exists())

    def test_digest_change_warns_but_does_not_block_launch(self):
        self.prepare_project()
        (self.project / ".image-digest.lock").write_text(self.digest + "\n")
        result = self.run_bash("jalankan_container", MOCK_DIGEST=self.changed_digest + "\n")
        self.assertIn("PERINGATAN", result.stderr)
        self.assertIn("compose <up> <-d> <--no-build>", self.calls())


class SwapTests(DeploymentTestCase):
    def test_active_swap_is_left_untouched(self):
        self.run_bash("konfigurasi_swap", MOCK_ACTIVE_SWAP="NAME TYPE SIZE USED PRIO\n/dev/zram0 partition 2G 0B 5\n")
        self.assertEqual(self.calls(), ["sudo <swapon> <--show>"])

    def test_existing_swapfile_is_left_untouched(self):
        swapfile = self.root / "swapfile"
        swapfile.write_text("existing swap fixture\n")
        self.run_bash("konfigurasi_swap")
        self.assertEqual(self.calls(), ["sudo <swapon> <--show>"])
        self.assertEqual(swapfile.read_text(), "existing swap fixture\n")

    def test_creates_private_two_gibibyte_swap_before_registering_it(self):
        self.run_bash("konfigurasi_swap")
        swapfile = self.root / "swapfile"
        self.assertEqual(self.calls(), [
            "sudo <swapon> <--show>",
            f"sudo <fallocate> <-l> <2G> <{swapfile}>",
            f"sudo <chmod> <600> <{swapfile}>",
            f"sudo <mkswap> <{swapfile}>",
            f"sudo <swapon> <{swapfile}>",
            f"sudo <tee> <-a> <{self.root}/fstab>",
        ])
        self.assertEqual((self.root / "fstab").read_text(), f"# fixture fstab\n{swapfile} none swap sw 0 0\n")

    def test_allocation_failure_falls_back_to_dd(self):
        self.run_bash("konfigurasi_swap", MOCK_FALLOCATE_STATUS="1")
        self.assertIn(
            f"sudo <dd> <if=/dev/zero> <of={self.root}/swapfile> <bs=1M> <count=2048>",
            self.calls(),
        )
        self.assertIn(f"sudo <swapon> <{self.root}/swapfile>", self.calls())

    def test_failed_allocators_abort_before_format_or_persistence(self):
        self.run_bash("konfigurasi_swap", status=2, MOCK_FALLOCATE_STATUS="1", MOCK_DD_STATUS="2")
        self.assertEqual(len(self.calls()), 3)
        self.assertEqual((self.root / "fstab").read_text(), "# fixture fstab\n")

    def test_format_or_activation_failure_does_not_persist_swap(self):
        for command in ("chmod 600", "mkswap", "swapon"):
            with self.subTest(command=command):
                self.log.write_text("")
                self.run_bash(
                    "konfigurasi_swap", status=23,
                    MOCK_FAIL_COMMAND=f"{command} {self.root}/swapfile",
                )
                self.assertFalse(any("<tee>" in call for call in self.calls()))
                self.assertEqual((self.root / "fstab").read_text(), "# fixture fstab\n")

    def test_existing_fstab_entry_is_not_duplicated(self):
        for separator in (" ", "\t"):
            with self.subTest(separator=separator):
                contents = f"{self.root}/swapfile{separator}none swap sw 0 0\n"
                (self.root / "fstab").write_text(contents)
                self.log.write_text("")
                self.run_bash("konfigurasi_swap")
                self.assertEqual((self.root / "fstab").read_text(), contents)
                self.assertFalse(any("<tee>" in call for call in self.calls()))


class FirewallTests(DeploymentTestCase):
    def test_ssh_and_web_rules_are_applied_before_noninteractive_enable(self):
        self.run_bash("konfigurasi_firewall")
        self.assertEqual(self.calls(), [
            "sudo <apt-get> <install> <-y> <ufw>",
            "sudo <ufw> <allow> <OpenSSH>",
            "sudo <ufw> <allow> <80/tcp>",
            "sudo <ufw> <allow> <443/tcp>",
            "sudo <ufw> <default> <deny> <incoming>",
            "sudo <ufw> <default> <allow> <outgoing>",
            "sudo <ufw> <--force> <enable>",
            "sudo <ufw> <status> <verbose>",
        ])

    def test_install_or_rule_failure_prevents_firewall_enable(self):
        for command in ("apt-get install -y ufw", "ufw allow OpenSSH", "ufw allow 443/tcp"):
            with self.subTest(command=command):
                self.log.write_text("")
                self.run_bash("konfigurasi_firewall", status=23, MOCK_FAIL_COMMAND=command)
                self.assertFalse(any("<enable>" in call for call in self.calls()))


class BackupTests(DeploymentTestCase):
    def test_database_and_volume_share_stamp_and_preserve_contents(self):
        backups = self.backup_directory()
        old_backup = self.age_file(backups / "postgres-old.sql.gz", 16)
        self.run_bash("backup_database", MOCK_VOLUME="snapotter_data")
        databases = list(backups.glob("postgres-*.sql.gz"))
        archives = list(backups.glob("data-*.tar.gz"))
        self.assertEqual(len(databases), 1)
        self.assertEqual(len(archives), 1)
        stamp = databases[0].name.removeprefix("postgres-").removesuffix(".sql.gz")
        self.assertRegex(stamp, r"^\d{8}-\d{6}-\d+$")
        self.assertEqual(archives[0].name, f"data-{stamp}.tar.gz")
        self.assertEqual(gzip.decompress(databases[0].read_bytes()).decode(), self.sql)
        with tarfile.open(archives[0]) as archive:
            self.assertEqual(archive.extractfile("./upload.txt").read(), b"synthetic upload\n")
            self.assertEqual(archive.extractfile("./.metadata").read(), b"hidden fixture\n")
        self.assertEqual(backups.stat().st_mode & 0o777, 0o700)
        self.assertEqual(databases[0].stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(backups.glob(".db-*")), [])
        self.assertFalse(old_backup.exists())
        self.assertEqual(self.calls()[0],
            'compose <exec> <-T> <postgres> <sh> <-c> <exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB">')
        self.assertIn(
            f"sudo <docker> <run> <--rm> <-v> <snapotter_data:/data:ro> <-v> "
            f"<{backups}:/backup> <alpine:3.22> <tar> <-czf> </backup/data-{stamp}.tar.gz> <-C> </data> <.>",
            self.calls(),
        )
        self.assertIn(
            f"sudo <chown> <{os.getuid()}:{os.getgid()}> <{archives[0]}>",
            self.calls(),
        )

    def test_dump_failure_removes_partial_file_and_never_archives_or_prunes(self):
        backups = self.backup_directory()
        old_backup = self.age_file(backups / "postgres-old.sql.gz", 16)
        result = self.run_bash("backup_database", status=1, MOCK_DUMP_STATUS="7", MOCK_VOLUME="snapotter_data")
        self.assertIn("Backup PostgreSQL gagal", result.stderr)
        self.assertEqual(list(backups.iterdir()), [old_backup])
        self.assertEqual(len(self.calls()), 1)

    def test_compression_failure_removes_partial_file_and_never_archives(self):
        result = self.run_bash(
            "gzip() { cat >/dev/null; return 8; }; backup_database", status=1,
        )
        self.assertIn("Backup PostgreSQL gagal", result.stderr)
        self.assertEqual(list((self.project / "backups").iterdir()), [])
        self.assertEqual(len(self.calls()), 1)

    def test_missing_or_uninspectable_volume_warns_and_retains_database(self):
        for inspect_status in ("0", "1"):
            with self.subTest(inspect_status=inspect_status):
                self.log.write_text("")
                result = self.run_bash("backup_database", MOCK_VOLUME_STATUS=inspect_status)
                self.assertIn("volume /data tidak ditemukan", result.stderr)
                self.assertTrue(list((self.project / "backups").glob("postgres-*.sql.gz")))
                self.assertFalse(any("<run>" in call for call in self.calls()))

    def test_volume_failure_is_nonfatal_and_still_prunes_old_backups(self):
        backups = self.backup_directory()
        old_backup = self.age_file(backups / "data-old.tar.gz", 16)
        result = self.run_bash("backup_database", MOCK_VOLUME="snapotter_data", MOCK_ARCHIVE_STATUS="9")
        self.assertIn("backup volume /data gagal", result.stderr)
        self.assertEqual(len(list(backups.glob("postgres-*.sql.gz"))), 1)
        self.assertFalse(old_backup.exists())
        self.assertFalse(any("<chown>" in call for call in self.calls()))

    def test_volume_ownership_failure_is_nonfatal(self):
        self.backup_directory()
        result = self.run_bash('backup_volume "fixed-stamp"', MOCK_VOLUME="snapotter_data", MOCK_CHOWN_STATUS="1")
        self.assertTrue((self.project / "backups/data-fixed-stamp.tar.gz").exists())
        self.assertIn("Backup volume /data:", result.stdout)
        self.assertTrue(any("<chown>" in call for call in self.calls()))


class RetentionTests(DeploymentTestCase):
    def test_retention_defaults_to_fourteen_days_and_accepts_override(self):
        for environment, expected in (({}, "14"), ({"BACKUP_RETENSI_HARI": ""}, "14"),
                                      ({"BACKUP_RETENSI_HARI": "30"}, "30"),
                                      ({"BACKUP_RETENSI_HARI": "0"}, "0")):
            with self.subTest(environment=environment):
                result = self.run_bash('printf "%s" "$BACKUP_RETENSI_HARI"', **environment)
                self.assertEqual(result.stdout, expected)

    def test_only_expired_top_level_backup_files_are_deleted(self):
        backups = self.backup_directory()
        expired = [self.age_file(backups / name, 16) for name in ("postgres-old.sql.gz", "data-old.tar.gz")]
        preserved = [
            self.age_file(backups / "postgres-recent.sql.gz", 1),
            self.age_file(backups / "data-recent.tar.gz", 1),
            self.age_file(backups / "unrelated.sql.gz", 40),
            self.age_file(backups / ".db-partial", 40),
            self.age_file(backups / "postgres-old.dump", 40),
        ]
        nested = backups / "nested"
        nested.mkdir()
        preserved.append(self.age_file(nested / "postgres-old.sql.gz", 40))
        directory = backups / "data-directory.tar.gz"
        directory.mkdir()
        outside = self.age_file(self.root / "outside.sql.gz", 40)
        link = backups / "postgres-linked.sql.gz"
        link.symlink_to(outside)
        old_stamp = time.time() - 40 * 86400
        os.utime(directory, (old_stamp, old_stamp))
        os.utime(link, (old_stamp, old_stamp), follow_symlinks=False)
        result = self.run_bash("prune_backup")
        for path in expired:
            self.assertFalse(path.exists())
            self.assertIn(str(path), result.stdout)
        for path in preserved + [directory, outside, link]:
            self.assertTrue(path.exists(), str(path))
            self.assertNotIn(str(path), result.stdout)

    def test_find_retention_boundary_uses_completed_twenty_four_hour_periods(self):
        backups = self.backup_directory()
        # GNU find -mtime +14 deletes when the completed-day count exceeds 14.
        boundary = self.age_file(backups / "postgres-fourteen.sql.gz", 14.5)
        expired = self.age_file(backups / "data-fifteen.tar.gz", 15.5)
        self.run_bash("prune_backup")
        self.assertTrue(boundary.exists())
        self.assertFalse(expired.exists())

    def test_custom_retention_reaches_the_pruning_operation(self):
        backups = self.backup_directory()
        retained = self.age_file(backups / "postgres-twenty.sql.gz", 20)
        expired = self.age_file(backups / "data-thirtyone.tar.gz", 31)
        result = self.run_bash("prune_backup", BACKUP_RETENSI_HARI="30")
        self.assertTrue(retained.exists())
        self.assertFalse(expired.exists())
        self.assertIn(">30 hari", result.stdout)

    def test_nothing_expired_is_silent(self):
        backups = self.backup_directory()
        self.age_file(backups / "postgres-recent.sql.gz", 1)
        result = self.run_bash("prune_backup")
        self.assertEqual(result.stdout, "")


class InstallationWiringTests(DeploymentTestCase):
    stubs = r"""
command() {
  if [[ "$*" == '-v caddy' ]]; then return 1; fi
  builtin command "$@"
}
konfigurasi_swap() { record swap; return "${MOCK_SWAP_STATUS:-0}"; }
instal_docker() { record install-docker; }
buat_konfigurasi() { record configuration "$@"; }
jalankan_container() { record launch; }
konfigurasi_firewall() { record firewall; return "${MOCK_FIREWALL_STATUS:-0}"; }
konfigurasi_caddy() { record caddy "$@"; }
coba_api() { record health "$@"; }
cek_layanan() { record check; }
"""

    def test_installer_sets_up_swap_before_docker_and_firewall_before_https(self):
        self.run_bash(self.stubs + "\ninstal_baru example.test")
        calls = self.calls()
        self.assertEqual(calls[:7], [
            "sudo <-v>", "swap", "install-docker",
            "configuration <example.test>", "launch", "firewall",
            "caddy <example.test>",
        ])
        self.assertIn("health <http://127.0.0.1:1349/api/v1/health> <API lokal>", calls)
        self.assertIn("health <https://example.test/api/v1/health> <API HTTPS>", calls)

    def test_failed_hardening_aborts_remaining_installation(self):
        for environment, expected_last in (({"MOCK_SWAP_STATUS": "5"}, "swap"),
                                           ({"MOCK_FIREWALL_STATUS": "5"}, "firewall")):
            with self.subTest(environment=environment):
                self.log.write_text("")
                self.run_bash(self.stubs + "\ninstal_baru example.test", status=5, **environment)
                self.assertEqual(self.calls()[-1], expected_last)
                self.assertFalse(any(call.startswith("caddy") for call in self.calls()))


class DeploymentIgnoreTests(unittest.TestCase):
    def check_ignore(self, paths, status):
        result = subprocess.run(
            ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "--stdin"],
            input="\n".join(paths) + "\n", text=True, capture_output=True,
            cwd=REPOSITORY, timeout=5, check=False,
        )
        self.assertEqual(result.returncode, status, result.stderr)
        return result.stdout.splitlines()

    def test_generated_state_secrets_and_backups_are_ignored(self):
        paths = [
            ".env", ".domain", ".compose.sha256", ".image-digest.lock",
            "backups/private-file", "postgres-fixture.sql.gz", "database.dump",
            "data-fixture.tar.gz", "compose.minimum.yml", "docker-compose.yml",
        ]
        self.assertEqual(self.check_ignore(paths, 0), paths)

    def test_script_documentation_and_test_sources_remain_visible_to_git(self):
        self.assertEqual(self.check_ignore([
            "otomatisasi_snapotter.sh", "README.md", "tests/test_otomatisasi_snapotter.py",
        ], 1), [])


if __name__ == "__main__":
    unittest.main()

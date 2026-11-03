"""Exercise the actual Makefile against a fresh disposable PostgreSQL cluster.

Uses existing PostgreSQL binaries, a temporary data directory and a free
loopback port. It never installs software or touches the project's cluster.
"""

from pathlib import Path
import os
import shutil
import socket
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PGBIN = Path(os.environ.get("PGBIN", "/opt/homebrew/opt/postgresql@17/bin"))


class BootstrapTest(unittest.TestCase):
    def test_fresh_init_and_repeated_start(self):
        for name in ("initdb", "pg_ctl", "psql"):
            self.assertTrue((PGBIN / name).is_file(), f"missing PostgreSQL binary: {PGBIN / name}")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        # A short /tmp path also stays below PostgreSQL's socket path limit.
        with tempfile.TemporaryDirectory(prefix="relay-boot-", dir="/tmp") as temporary:
            work = Path(temporary)
            shutil.copyfile(ROOT / "Makefile", work / "Makefile")
            data = work / "var" / "pgdata"

            def run(*command):
                result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            make = ("make", f"PGPORT={port}", f"PGBIN={PGBIN}",
                    f"PGCTL={PGBIN / 'pg_ctl'}", f"PSQL={PGBIN / 'psql'}")
            try:
                run(*make, "db-init")
                query = "SELECT datname FROM pg_database WHERE datname IN ('relay_dev', 'relay_test', 'relay_recon') ORDER BY datname"
                names = run(str(PGBIN / "psql"), "-h", "127.0.0.1", "-p", str(port),
                            "-U", "relay_admin", "-d", "postgres", "-Atc", query)
                self.assertEqual(names.splitlines(), ["relay_dev", "relay_recon", "relay_test"])
                pid = (data / "postmaster.pid").read_text().splitlines()[0]
                for _ in range(2):
                    self.assertIn("already running", run(*make, "db-up"))
                    self.assertEqual((data / "postmaster.pid").read_text().splitlines()[0], pid)
            finally:
                if (data / "postmaster.pid").exists():
                    run(str(PGBIN / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop")


if __name__ == "__main__":
    unittest.main()

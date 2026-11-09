"""Run with: python -m unittest discover -s scripts/tests -v (from backend)."""
import csv
import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
        SECRET_KEY="synthetic-test-key",
    )
django.setup()

from django.contrib.auth.models import User
from django.db import IntegrityError, connection, transaction
from scripts import sync_auth_users as sync


class SyncAuthUsersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            editor.create_model(User)

    @classmethod
    def tearDownClass(cls):
        with connection.schema_editor() as editor:
            editor.delete_model(User)

    def setUp(self):
        # No related records are created by these isolated script tests.
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM auth_user")

    def run_import(self, rows, *options):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            stdout = io.StringIO()
            with (
                patch("sys.argv", ["sync_auth_users", "--output", str(output), *options]),
                patch.object(sync, "setup_django"),
                patch.object(sync, "get_total_rows", return_value=2),
                patch.object(sync, "fetch_source_rows", side_effect=lambda _: rows()),
                redirect_stdout(stdout),
            ):
                self.assertEqual(sync.main(), 0)
            with output.open() as exported:
                return stdout.getvalue(), list(csv.reader(exported))

    def test_concurrent_id_and_username_conflicts_continue(self):
        for conflict in ("id", "username"):
            with self.subTest(conflict=conflict):
                self.setUp()

                def rows():
                    # Runs after the importer has loaded its identity sets.
                    User.objects.create(id=1 if conflict == "id" else 99,
                                        username="taken" if conflict == "username" else "other")
                    yield (1, "taken", "", "", "", "ACTIVO")
                    yield (2, "fresh", "", "", "", "ACTIVO")

                # A failed insert must also leave an enclosing transaction usable.
                with transaction.atomic():
                    stdout, exported = self.run_import(rows)
                    self.assertTrue(User.objects.filter(id=2, username="fresh").exists())
                self.assertIn("Creados: 1. Actualizados: 0. Saltados: 1.", stdout)
                self.assertEqual([row[0] for row in exported], ["username", "fresh"])

    def test_other_integrity_error_propagates(self):
        error = IntegrityError("not null")
        error.__cause__ = sqlite3.IntegrityError("NOT NULL constraint failed: auth_user.email")

        with patch.object(User, "save", side_effect=error):
            with self.assertRaises(IntegrityError):
                self.run_import(lambda: iter([(1, "new", "", "", "", "ACTIVO")]))

    def test_dry_run_deduplicates_without_writes(self):
        stdout, exported = self.run_import(
            lambda: iter([(1, "same", "", "", "", "ACTIVO"),
                          (2, "same", "", "", "", "ACTIVO")]), "--dry-run")
        self.assertFalse(User.objects.exists())
        self.assertEqual(exported[1][1], "DRY_RUN")
        self.assertIn("Creados: 1. Actualizados: 0. Saltados: 1.", stdout)

    def test_mysql_constraint_classification(self):
        for code, key, expected in (
            (1062, "PRIMARY", True), (1062, "username", True),
            (1062, "auth_user.username", True), (1062, "email", False),
            (1048, "username", False), (1062, "username_extra", False),
        ):
            with self.subTest(code=code, key=key):
                error = IntegrityError("insert failed")
                error.__cause__ = Exception(code, f"Duplicate entry 'value' for key '{key}'")
                self.assertEqual(sync.is_identity_conflict(error, "mysql"), expected)
        self.assertFalse(sync.is_identity_conflict(IntegrityError("unknown"), "mysql"))


if __name__ == "__main__":
    unittest.main()

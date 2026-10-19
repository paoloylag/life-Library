"""Exercise migration history without touching the configured application database."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


@pytest.mark.parametrize('baseline', [None, 'c28f9e031bd5', 'd41a720bc358'])
def test_booking_release_migration(tmp_path, baseline):
    database = tmp_path / 'migration.db'
    env = {**os.environ, 'DATABASE_URL': 'sqlite+aiosqlite:///' + database.as_posix(), 'DATABASE_HOST': '', 'APP_ENV': 'local'}
    backend = Path(__file__).resolve().parents[1]

    def upgrade(target):
        result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', target], cwd=backend, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr

    if baseline:
        upgrade(baseline)
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO users (id,email,name,role,is_active) VALUES (1,'preserved@life.edu.ph','Preserved User','student',1)")
    upgrade('head')
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT version_num FROM alembic_version').fetchone()[0] == 'e52b831cd469'
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'booking_resources', 'facility_bookings', 'booking_resource_types', 'approved_google_emails', 'staff_google_access'} <= tables
        assert connection.execute('SELECT COUNT(*) FROM staff_google_access').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM facility_bookings').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM booking_resources').fetchone()[0] == 7
        if baseline:
            assert connection.execute('SELECT email FROM users WHERE id=1').fetchone()[0] == 'preserved@life.edu.ph'
    upgrade('head')

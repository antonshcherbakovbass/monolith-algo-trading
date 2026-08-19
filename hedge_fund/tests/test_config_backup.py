import time

import pytest

from hedge_fund.core.config_backup import ConfigBackup


@pytest.fixture
def backup_env(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("key: value\n")
    backup_dir = tmp_path / "backups"
    return ConfigBackup(config_path=str(config_file), backup_dir=str(backup_dir))


class TestConfigBackup:
    def test_create_backup(self, backup_env):
        result = backup_env.create_backup()
        assert result is not None
        assert result.exists()

    def test_list_backups(self, backup_env):
        backup_env.create_backup()
        backups = backup_env.list_backups()
        assert len(backups) == 1
        assert "name" in backups[0]

    def test_restore_backup(self, backup_env):
        backup_env.create_backup()
        backups = backup_env.list_backups()
        name = backups[0]["name"]

        backup_env.config_path.write_text("modified: true\n")
        assert backup_env.restore_backup(name) is True
        assert "key: value" in backup_env.config_path.read_text()

    def test_restore_nonexistent_returns_false(self, backup_env):
        assert backup_env.restore_backup("nonexistent.yaml") is False

    def test_rotation_keeps_max_10(self, backup_env):
        for i in range(12):
            backup_env.create_backup()
            time.sleep(0.01)
        backups = backup_env.list_backups()
        assert len(backups) <= 10

    def test_create_backup_no_config_file(self, tmp_path):
        cb = ConfigBackup(config_path=str(tmp_path / "missing.yaml"), backup_dir=str(tmp_path / "bk"))
        assert cb.create_backup() is None

    def test_list_backups_empty(self, backup_env):
        assert backup_env.list_backups() == []

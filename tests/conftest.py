import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Tests dürfen nie in das echte Spielstand-Verzeichnis schreiben."""
    monkeypatch.setenv("TEXTADVENTURE_HOME", str(tmp_path / "home"))

"""Tests for file browser API route."""
import os

import pytest


class TestBrowseDirectory:
    def test_browse_home(self, client):
        resp = client.get("/browse?path=~")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == os.path.expanduser("~")
        assert "parent" in data
        assert isinstance(data["entries"], list)

    def test_browse_root(self, client):
        resp = client.get("/browse?path=/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == "/"
        assert any(e["name"] == "tmp" for e in data["entries"])

    def test_browse_tmp(self, client, tmp_path):
        # Create some test files/dirs
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file.txt").write_text("hello")

        resp = client.get(f"/browse?path={tmp_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current"] == str(tmp_path)

        names = {e["name"] for e in data["entries"]}
        assert "subdir" in names
        assert "file.txt" in names

        subdir_entry = next(e for e in data["entries"] if e["name"] == "subdir")
        assert subdir_entry["is_dir"] is True
        assert subdir_entry["path"] == str(tmp_path / "subdir")

        file_entry = next(e for e in data["entries"] if e["name"] == "file.txt")
        assert file_entry["is_dir"] is False

    def test_browse_hides_dotfiles(self, client, tmp_path):
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible").write_text("public")

        resp = client.get(f"/browse?path={tmp_path}")
        names = {e["name"] for e in resp.json()["entries"]}
        assert "visible" in names
        assert ".hidden" not in names

    def test_browse_returns_parent(self, client, tmp_path):
        resp = client.get(f"/browse?path={tmp_path}")
        data = resp.json()
        assert data["parent"] == str(tmp_path.parent)

    def test_browse_file_path_returns_parent_dir(self, client, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        resp = client.get(f"/browse?path={f}")
        assert resp.status_code == 200
        assert resp.json()["current"] == str(tmp_path)

    def test_browse_invalid_path(self, client):
        resp = client.get("/browse?path=/nonexistent/path/that/does/not/exist")
        assert resp.status_code == 400

    def test_browse_entries_sorted(self, client, tmp_path):
        (tmp_path / "banana").write_text("")
        (tmp_path / "apple").write_text("")
        (tmp_path / "cherry").write_text("")

        resp = client.get(f"/browse?path={tmp_path}")
        names = [e["name"] for e in resp.json()["entries"]]
        assert names == sorted(names)

    def test_browse_default_path(self, client):
        resp = client.get("/browse")
        assert resp.status_code == 200
        assert resp.json()["current"] == os.path.expanduser("~")

import sqlite3

import pytest

from database import Database


@pytest.fixture
def database(tmp_path):
    db = Database(str(tmp_path / "test.sqlite3"))
    yield db
    db.close()


def create_users(db):
    result = db.create_table("users", {"id": 1, "name": "Alice", "active": True, "metadata": {"tier": "pro"}})
    assert result["success"] is True


def test_create_add_and_read_rows_with_json_values(database):
    create_users(database)
    assert database.add_to_table("users", {"id": 1, "name": "Alice", "active": True, "metadata": {"tier": "pro"}})["success"] is True
    assert database.add_to_table("users", {"id": 2, "name": "Bob", "active": False, "metadata": ["basic"]})["success"] is True

    rows = database.get_rows("users")
    assert rows["success"] is True
    assert rows["data"] == [
        {"id": 1, "name": "Alice", "active": 1, "metadata": {"tier": "pro"}},
        {"id": 2, "name": "Bob", "active": 0, "metadata": ["basic"]},
    ]
    assert database.get_row("users", "name", "Bob")["data"]["id"] == 2


def test_get_row_returns_first_match(database):
    create_users(database)
    database.add_to_table("users", {"id": 1, "name": "Alice", "active": True, "metadata": {}})
    database.add_to_table("users", {"id": 2, "name": "Alice", "active": False, "metadata": {}})
    assert database.get_row("users", "name", "Alice")["data"]["id"] == 1


def test_update_uses_payload_id_and_delete_uses_explicit_selector(database):
    create_users(database)
    database.add_to_table("users", {"id": 1, "name": "Alice", "active": True, "metadata": {}})
    database.add_to_table("users", {"id": 2, "name": "Bob", "active": True, "metadata": {}})

    updated = database.update_row("users", {"id": 2, "active": False, "metadata": {"tier": "free"}})
    assert updated == {"success": True, "data": 1, "error": None}
    assert database.get_row("users", "id", 2)["data"] == {
        "id": 2,
        "name": "Bob",
        "active": 0,
        "metadata": {"tier": "free"},
    }

    deleted = database.delete_row("users", "name", "Alice")
    assert deleted == {"success": True, "data": 1, "error": None}
    assert len(database.get_rows("users")["data"]) == 1


def test_schema_validation_and_not_found_results(database):
    create_users(database)
    assert database.add_to_table("users", {"id": 1, "name": "Alice"})["error"]["code"] == "schema_mismatch"
    assert database.add_to_table("users", {"id": 1, "name": "Alice", "active": True, "metadata": set()})["error"]["code"] == "invalid_value"
    assert database.update_row("users", {"id": 1, "active": False})["error"]["code"] == "row_not_found"
    assert database.delete_row("users", "name", "missing")["error"]["code"] == "row_not_found"
    assert database.get_row("users", "name", "missing")["error"]["code"] == "row_not_found"
    assert database.delete_table("missing")["error"]["code"] == "table_not_found"


def test_identifier_and_payload_validation(database):
    assert database.create_table("bad-name", {"id": 1})["error"]["code"] == "invalid_identifier"
    assert database.create_table("users", {"name": "Alice"})["error"]["code"] == "missing_id"
    assert database.create_table("users", {"id": 1, "bad-name": "Alice"})["error"]["code"] == "invalid_identifier"
    assert database.create_table("users", {})["error"]["code"] == "invalid_payload"


def test_update_payload_validation(database):
    create_users(database)
    assert database.update_row("users", {"active": False})["error"]["code"] == "missing_id"
    assert database.update_row("users", {"id": 1})["error"]["code"] == "invalid_payload"


def test_delete_table_and_context_manager(tmp_path):
    path = tmp_path / "default.sqlite3"
    with Database(str(path)) as database:
        assert database.create_table("users", {"id": 1})["success"] is True
        assert database.delete_table("users")["success"] is True
    with pytest.raises(sqlite3.ProgrammingError):
        database.connection.execute("SELECT 1")


def test_default_database_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    database = Database()
    try:
        assert (tmp_path / "database.sqlite3").exists()
    finally:
        database.close()

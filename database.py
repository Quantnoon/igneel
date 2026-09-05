"""Small SQLite persistence helper with structured operation results."""

import json
import re
import sqlite3
from typing import Any, Dict, Optional


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_JSON_PREFIX = "__database_json__:"


def _ok(data: Any = None) -> Dict[str, Any]:
    return {"success": True, "data": data, "error": None}


def _fail(message: str, code: Optional[str] = None) -> Dict[str, Any]:
    return {"success": False, "data": None, "error": {"code": code, "message": message}}


class Database:
    """Manage fixed-schema SQLite tables created from payload dictionaries."""

    def __init__(self, db_path: str = "database.sqlite3"):
        if not isinstance(db_path, str) or not db_path:
            raise ValueError("db_path must be a non-empty string.")
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    @staticmethod
    def _identifier(value: Any, label: str):
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            return None, _fail("%s must be a valid SQLite identifier." % label, "invalid_identifier")
        return '"%s"' % value, None

    @staticmethod
    def _validate_payload(payload: Any, require_id: bool = False):
        if not isinstance(payload, dict) or not payload:
            return None, _fail("payload must be a non-empty dictionary.", "invalid_payload")
        if require_id and "id" not in payload:
            return None, _fail("payload must contain an id.", "missing_id")
        for key in payload:
            _, error = Database._identifier(key, "payload key")
            if error:
                return None, error
        return payload, None

    @staticmethod
    def _sqlite_type(value: Any) -> str:
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return "INTEGER"
        if isinstance(value, float):
            return "REAL"
        if isinstance(value, (str, dict, list)):
            return "TEXT"
        raise TypeError("unsupported payload value type")

    @staticmethod
    def _encode(value: Any):
        if isinstance(value, (dict, list)):
            return _JSON_PREFIX + json.dumps(value, separators=(",", ":"))
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError("unsupported payload value type")

    @staticmethod
    def _decode(value: Any):
        if isinstance(value, str) and value.startswith(_JSON_PREFIX):
            try:
                return json.loads(value[len(_JSON_PREFIX):])
            except (TypeError, ValueError):
                return value
        return value

    def _table(self, table_name: str):
        quoted, error = self._identifier(table_name, "table_name")
        if error:
            return None, error
        try:
            table = self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
        except sqlite3.Error:
            return None, _fail("Unable to inspect the database.", "sqlite_error")
        if table is None:
            return None, _fail("Table was not found.", "table_not_found")
        return quoted, None

    def _columns(self, quoted_table: str):
        try:
            return [row[1] for row in self.connection.execute("PRAGMA table_info(%s)" % quoted_table)], None
        except sqlite3.Error:
            return None, _fail("Unable to inspect the table.", "sqlite_error")

    def _prepare_values(self, payload: dict, columns):
        unknown = [key for key in payload if key not in columns]
        if unknown:
            return None, _fail("Payload contains unknown column: %s." % unknown[0], "unknown_column")
        try:
            return {key: self._encode(value) for key, value in payload.items()}, None
        except TypeError:
            return None, _fail("Payload contains an unsupported value type.", "invalid_value")

    def _rollback(self):
        try:
            self.connection.rollback()
        except sqlite3.Error:
            pass

    def create_table(self, table_name: str, payload: dict):
        quoted, error = self._identifier(table_name, "table_name")
        if error:
            return error
        payload, error = self._validate_payload(payload, require_id=True)
        if error:
            return error
        try:
            definitions = []
            for key, value in payload.items():
                column, column_error = self._identifier(key, "payload key")
                if column_error:
                    return column_error
                declaration = "%s %s" % (column, self._sqlite_type(value))
                if key == "id":
                    declaration += " PRIMARY KEY"
                definitions.append(declaration)
            self.connection.execute("CREATE TABLE IF NOT EXISTS %s (%s)" % (quoted, ", ".join(definitions)))
            columns, error = self._columns(quoted)
            if error:
                self._rollback()
                return error
            if set(columns) != set(payload):
                self._rollback()
                return _fail("Existing table schema does not match payload.", "schema_mismatch")
            self.connection.commit()
            return _ok({"table": table_name, "columns": columns})
        except (sqlite3.Error, TypeError):
            self._rollback()
            return _fail("Unable to create table.", "sqlite_error")

    def add_to_table(self, table_name: str, payload: dict):
        quoted, error = self._table(table_name)
        if error:
            return error
        payload, error = self._validate_payload(payload)
        if error:
            return error
        columns, error = self._columns(quoted)
        if error:
            return error
        values, error = self._prepare_values(payload, columns)
        if error:
            return error
        if set(values) != set(columns):
            return _fail("Payload must contain exactly the table columns.", "schema_mismatch")
        column_sql = ", ".join('"%s"' % key for key in values)
        placeholders = ", ".join("?" for _ in values)
        try:
            cursor = self.connection.execute(
                "INSERT INTO %s (%s) VALUES (%s)" % (quoted, column_sql, placeholders),
                tuple(values.values()),
            )
            self.connection.commit()
            return _ok(cursor.lastrowid)
        except sqlite3.Error:
            self._rollback()
            return _fail("Unable to add row.", "sqlite_error")

    def update_row(self, table_name: str, payload: dict):
        quoted, error = self._table(table_name)
        if error:
            return error
        payload, error = self._validate_payload(payload, require_id=True)
        if error:
            return error
        columns, error = self._columns(quoted)
        if error:
            return error
        values, error = self._prepare_values(payload, columns)
        if error:
            return error
        row_id = values.pop("id")
        if not values:
            return _fail("Payload must contain a value to update.", "invalid_payload")
        assignments = ", ".join('"%s" = ?' % key for key in values)
        try:
            cursor = self.connection.execute(
                'UPDATE %s SET %s WHERE "id" = ?' % (quoted, assignments),
                tuple(values.values()) + (row_id,),
            )
            if cursor.rowcount == 0:
                self._rollback()
                return _fail("Row was not found.", "row_not_found")
            self.connection.commit()
            return _ok(cursor.rowcount)
        except sqlite3.Error:
            self._rollback()
            return _fail("Unable to update row.", "sqlite_error")

    def delete_row(self, table_name: str, delete_key: str, key_value: Any):
        quoted, error = self._table(table_name)
        if error:
            return error
        selector, error = self._identifier(delete_key, "delete_key")
        if error:
            return error
        try:
            cursor = self.connection.execute("DELETE FROM %s WHERE %s = ?" % (quoted, selector), (self._encode(key_value),))
            if cursor.rowcount == 0:
                self._rollback()
                return _fail("Row was not found.", "row_not_found")
            self.connection.commit()
            return _ok(cursor.rowcount)
        except (sqlite3.Error, TypeError):
            self._rollback()
            return _fail("Unable to delete row.", "sqlite_error")

    def delete_table(self, table_name: str):
        quoted, error = self._table(table_name)
        if error:
            return error
        try:
            self.connection.execute("DROP TABLE %s" % quoted)
            self.connection.commit()
            return _ok(table_name)
        except sqlite3.Error:
            self._rollback()
            return _fail("Unable to delete table.", "sqlite_error")

    def get_rows(self, table_name: str):
        quoted, error = self._table(table_name)
        if error:
            return error
        try:
            rows = self.connection.execute("SELECT * FROM %s ORDER BY rowid" % quoted).fetchall()
            return _ok([{key: self._decode(row[key]) for key in row.keys()} for row in rows])
        except sqlite3.Error:
            return _fail("Unable to retrieve rows.", "sqlite_error")

    def get_row(self, table_name: str, key: str, value: str):
        quoted, error = self._table(table_name)
        if error:
            return error
        selector, error = self._identifier(key, "key")
        if error:
            return error
        try:
            row = self.connection.execute("SELECT * FROM %s WHERE %s = ? ORDER BY rowid LIMIT 1" % (quoted, selector), (value,)).fetchone()
            if row is None:
                return _fail("Row was not found.", "row_not_found")
            return _ok({key: self._decode(row[key]) for key in row.keys()})
        except sqlite3.Error:
            return _fail("Unable to retrieve row.", "sqlite_error")

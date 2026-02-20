import pathlib
import sqlite3

from anchovy.include import SQLExtractStep


def setup_database(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE test (name TEXT, value TEXT)')
    cursor.execute('INSERT INTO test (name, value) VALUES ("verb", "Hello"), ("object", "World")')
    conn.commit()
    return conn


def test_sql_extract_step(tmp_path: pathlib.Path):
    conn = setup_database(str(tmp_path / 'test.db'))
    step = SQLExtractStep(lambda: conn, ext='.txt')
    query_path = tmp_path / 'query.sql'
    query_path.write_text('SELECT * FROM test')
    step(query_path, [tmp_path / 'output'])
    for name, value in [('verb', 'Hello'), ('object', 'World')]:
        output_path = tmp_path / 'output' / f'{name}.txt'
        assert output_path.exists()
        assert output_path.read_text() == value

import pytest
import sqlite3

def get_db_connection():
    return sqlite3.connect(':memory:')

def get_user_state(user_id, conn):
    cursor = conn.cursor()
    cursor.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 'main'

def set_user_state(user_id, state, conn):
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_states (user_id, state) VALUES (?, ?)', (user_id, state))
    conn.commit()

@pytest.fixture
def test_db():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE user_states (user_id INTEGER PRIMARY KEY, state TEXT)')
    conn.commit()
    yield conn
    conn.close()

def test_new_user_main(test_db):
    assert get_user_state(123, test_db) == 'main'

def test_set_get_state(test_db):
    set_user_state(123, 'pies', test_db)
    assert get_user_state(123, test_db) == 'pies'

def test_reset_state(test_db):
    set_user_state(123, 'pies', test_db)
    assert get_user_state(123, test_db) == 'pies'
    set_user_state(123, 'main', test_db)
    assert get_user_state(123, test_db) == 'main'

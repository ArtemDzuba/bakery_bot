import sqlite3

def init_db():
    conn = sqlite3.connect('bakery_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        emoji TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        price INTEGER,
        photo_owner_id TEXT,
        photo_id TEXT,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_states (
        user_id INTEGER PRIMARY KEY,
        state TEXT DEFAULT 'main',
        last_product INTEGER DEFAULT NULL
    )
    ''')

    categories = [
        (1, 'Пироги', '🥧'),
        (2, 'Торты', '🎂'),
        (3, 'Печенье', '🍪')
    ]
    cursor.executemany('INSERT OR IGNORE INTO categories (id, name, emoji) VALUES (?, ?, ?)', categories)

    products = [
        (1, 'Яблочный пирог', 'Сочная яблочная начинка с корицей и ванилью', 250, '-235661116', '457239022'),  # Замени!
        (1, 'Чебуреки', 'Хрустящее тесто, сочная мясная начинка', 180, '-235661116', '457239019'),

        (2, 'Наполеон', 'Слоеный торт с заварным кремом', 850, '-235661116', '457239017'),
        (2, 'Медовик', 'Медовые коржи со сметанным кремом', 650, '-235661116', '457239018'),

        (3, 'Овсяное печенье', 'Полезное с изюмом и медом', 150, '-235661116', '457239020'),
        (3, 'Шоколадное печенье', 'Хрустящее с кусочками шоколада', 170, '-235661116', '457239021')
    ]
    cursor.executemany(
        'INSERT OR IGNORE INTO products (category_id, name, description, price, photo_owner_id, photo_id) VALUES (?, ?, ?, ?, ?, ?)',
        products)

    conn.commit()
    conn.close()
    print("✅ База данных создана и заполнена!")

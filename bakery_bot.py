import vk_api
import sqlite3
import os
from dotenv import load_dotenv
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.upload import VkUpload

load_dotenv()
TOKEN = os.getenv('VK_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

if not TOKEN:
    print("❌ ОШИБКА: VK_TOKEN не найден в .env!")
    exit(1)
if not ADMIN_ID:
    print("❌ ОШИБКА: ADMIN_ID не найден в .env!")
    exit(1)

vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk_session)
upload = VkUpload(vk_session)

def init_db():
    """Функция создания таблиц бд и заполнения их"""
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


def get_db_connection():
    db_path = os.getenv('DB_PATH', 'bakery_bot.db')
    return sqlite3.connect(db_path)

def get_user_state(user_id):
    """Функция получения текущего состояния пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'main'

def set_user_state(user_id, state):
    """Обновляем состояние пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_states (user_id, state) VALUES (?, ?)', (user_id, state))
    conn.commit()
    conn.close()

def get_category_products(category_id):
    """Получаем список товаров категории"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM products WHERE category_id = ?', (category_id,))
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_info(product_id):
    """Получаем информацию о товаре"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, price, photo_owner_id, photo_id FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product


def send_text(user_id, text, keyboard=None, attachment=None):
    """Универсальная функция отправки сообщения"""
    params = {
        'user_id': user_id,
        'message': text,
        'random_id': get_random_id()
    }
    if keyboard:
        params['keyboard'] = keyboard.get_keyboard()
    if attachment:
        params['attachment'] = attachment
    vk_session.method('messages.send', params)

def send_to_admin(product_name, user_id, user_name):
    """Отправка заказа админу"""
    try:
        admin_info = vk_session.method("users.get", {"user_ids": ADMIN_ID})
        admin_name = admin_info[0]['first_name']
        admin_msg = (
            f"🔔 **НОВЫЙ ЗАКАЗ!**\n\n"
            f"🍰 **Товар:** {product_name}\n"
            f"👤 **Клиент:** {user_name} (ID: {user_id})\n"
            f"⏰ **Время:** {vk_session.method('utils.getServerTime')}\n"
            f"📞 **Диалог:** https://vk.com/im?sel={user_id}\n\n"
            f"❗ Обработать срочно!"
        )
        send_text(ADMIN_ID, admin_msg)
        print(f"✅ Уведомление отправлено админу {admin_name} ({ADMIN_ID})!")
    except Exception as e:
        print(f"❌ Ошибка отправки админу: {e}")


def main_keyboard():
    """Клавиатура состояния 'main'"""
    kb = VkKeyboard(one_time=False)
    kb.add_button('🥧 Пироги', VkKeyboardColor.PRIMARY)
    kb.add_button('🎂 Торты', VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('🍪 Печенье', VkKeyboardColor.PRIMARY)
    kb.add_button('📞 Связаться', VkKeyboardColor.SECONDARY)
    return kb

def get_category_keyboard(category_id):
    """Клавиатура состояния любой категории"""
    products = get_category_products(category_id)
    kb = VkKeyboard(one_time=False)
    for product_id, name in products[:2]:
        kb.add_button(name, VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('← Назад в главное меню', VkKeyboardColor.NEGATIVE)
    return kb

def product_keyboard(product_name):
    """Клавиатура состояния продукта"""
    kb = VkKeyboard(one_time=False)
    kb.add_button(f'🛒 Заказать сейчас {product_name}', VkKeyboardColor.POSITIVE)
    # kb.add_button(f'В корзину {product_name}', VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button('← В главное меню', VkKeyboardColor.NEGATIVE)
    return kb


print("🚀 Bakery Bot с БД и фото запущен!")

if __name__ == '__main__':
    init_db()
    try:
        send_text(ADMIN_ID, "🧪 АДМИН-ТЕСТ: Бот готов принимать заказы!")
        print("✅ Тестовое сообщение админу отправлено!")
    except:
        print("❌ Админ должен написать боту первым!")

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = event.user_id
                msg = event.text
                print(msg)

                state = get_user_state(user_id)
                print(f"👤 User {user_id} (состояние: {state}): {msg}")

                try:
                    user_info = vk_session.method("users.get", {"user_ids": user_id})
                    name = user_info[0]['first_name']
                except:
                    name = "Друг"

                if state == 'main':
                    if msg.lower() in ['hello', 'привет', 'меню']:
                        send_text(user_id,
                                  f"👋 Привет, {name}!\n\n🍞 **Витрина свежей выпечки!**\nВыберите категорию:",
                                  main_keyboard())

                    elif msg == '🥧 Пироги':
                        set_user_state(user_id, 'pies')
                        send_text(user_id, "🥧 Выберите пирог", get_category_keyboard(1))

                    elif msg == '🎂 Торты':
                        set_user_state(user_id, 'cakes')
                        send_text(user_id, "🎂 Выберите торт", get_category_keyboard(2))

                    elif msg == '🍪 Печенье':
                        set_user_state(user_id, 'cookies')
                        send_text(user_id, "🍪 Выберите печенье", get_category_keyboard(3))
                    elif msg == '📞 Связаться':
                        set_user_state(user_id, 'main')
                        send_text(user_id, "Свяжитесь с нами:\n"
                                           f"📞 Менеджер: https://vk.com/im?sel={ADMIN_ID}\n\n", main_keyboard())
                    else:
                        send_text(user_id, f"👋 Привет, {name}!\nВыберите категорию:", main_keyboard())


                elif state in ['pies', 'cakes', 'cookies']:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT id FROM products WHERE name = ? AND category_id = ?',
                                   (msg, 1 if state == 'pies' else 2 if state == 'cakes' else 3))
                    product = cursor.fetchone()
                    conn.close()

                    if product:
                        product_info = get_product_info(product[0])
                        kb = product_keyboard(product_info[0])

                        attachment = f"photo{product_info[3]}_{product_info[4]}" if product_info[3] else None
                        send_text(user_id,
                                  f"**{product_info[0]}**\n\n"
                                  f"{product_info[1]}\n"
                                  f"📦 Вес: 300-1000г\n"
                                  f"💰 {product_info[2]}₽\n"
                                  f"⭐ Свежая выпечка",
                                  kb, attachment)
                        set_user_state(user_id, 'order')
                    elif msg == '← Назад в главное меню':
                        set_user_state(user_id, 'main')
                        send_text(user_id, "🍞 **Главное меню**", main_keyboard())
                    else:
                        cat_id = 1 if state == 'pies' else 2 if state == 'cakes' else 3
                        send_text(user_id, f"**{state.title()}**", get_category_keyboard(cat_id))

                elif state == 'order':
                    if "Заказать" in msg:
                        print('sdfsdsdfsdfsdf')
                        product_name = msg.replace('🛒 Заказать сейчас ', '')
                        print(f"🛒 Заказ: {product_name} от пользователя {user_id}")
                        send_text(user_id,
                                  f"✅ **Заказ принят!**\n\n"
                                  f"🍰 **{product_name}**\n"
                                  f"📱 Менеджер свяжется в течение 30 мин\n"
                                  f"Спасибо! ❤️",
                                  main_keyboard())
                        send_to_admin(product_name, user_id, name)
                    elif msg == '← В главное меню':
                        set_user_state(user_id, 'main')
                        send_text(user_id, "🍞 **Главное меню**", main_keyboard())

                    set_user_state(user_id, 'main')
                    print(f"✅ Заказ обработан. Состояние сброшено на 'main'")
                    continue

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        continue
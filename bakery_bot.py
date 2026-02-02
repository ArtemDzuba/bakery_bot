import vk_api
import sqlite3
import os
from dotenv import load_dotenv
from enum import Enum
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from vk_api.upload import VkUpload
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv('VK_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

if not TOKEN or not ADMIN_ID:
    logger.error("❌ ОШИБКА: VK_TOKEN или ADMIN_ID не найдены в .env!")
    exit(1)

vk_session = vk_api.VkApi(token=TOKEN)
longpoll = VkLongPoll(vk_session)
upload = VkUpload(vk_session)


class UserState(Enum):
    """Машина состояний"""
    MAIN = 'main'
    PIES = 'pies'
    CAKES = 'cakes'
    COOKIES = 'cookies'
    ORDER = 'order'


def init_db():
    """Инициализация БД с индексами"""
    conn = sqlite3.connect('bakery_bot.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        emoji TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
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
        state TEXT NOT NULL DEFAULT 'main',
        last_product INTEGER
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_states_user ON user_states(user_id)')

    cursor.execute('SELECT COUNT(*) FROM categories')
    if cursor.fetchone()[0] == 0:
        categories = [
            (1, 'Пироги', '🥧'),
            (2, 'Торты', '🎂'),
            (3, 'Печенье', '🍪')
        ]
        cursor.executemany('INSERT INTO categories (id, name, emoji) VALUES (?, ?, ?)', categories)

        products = [
            (1, 'Яблочный пирог', 'Сочная яблочная начинка с корицей и ванилью', 250, '-235661116', '457239022'),
            (1, 'Чебуреки', 'Хрустящее тесто, сочная мясная начинка', 180, '-235661116', '457239019'),
            (2, 'Наполеон', 'Слоеный торт с заварным кремом', 850, '-235661116', '457239017'),
            (2, 'Медовик', 'Медовые коржи со сметанным кремом', 650, '-235661116', '457239018'),
            (3, 'Овсяное печенье', 'Полезное с изюмом и медом', 150, '-235661116', '457239020'),
            (3, 'Шоколадное печенье', 'Хрустящее с кусочками шоколада', 170, '-235661116', '457239021')
        ]
        cursor.executemany(
            'INSERT INTO products (category_id, name, description, price, photo_owner_id, photo_id) VALUES (?, ?, ?, ?, ?, ?)',
            products
        )
        conn.commit()
        logger.info("✅ База данных создана и заполнена!")

    conn.close()


def get_db_connection():
    return sqlite3.connect('bakery_bot.db')


def get_user_state(user_id):
    """Получение состояния пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT state FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return UserState(result[0]) if result else UserState.MAIN


def set_user_state(user_id, state: UserState):
    """Установка состояния пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO user_states (user_id, state) VALUES (?, ?)',
                   (user_id, state.value))
    conn.commit()
    conn.close()


def get_category_products(category_id):
    """Продукты категории"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM products WHERE category_id = ?', (category_id,))
    products = cursor.fetchall()
    conn.close()
    return products


def get_product_info(product_id):
    """Информация о продукте"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name, description, price, photo_owner_id, photo_id FROM products WHERE id = ?',
                   (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product


def find_product_by_name(name, category_id):
    """Поиск продукта по имени"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM products WHERE name = ? AND category_id = ?', (name, category_id))
    product = cursor.fetchone()
    conn.close()
    return product


STATE_HANDLERS = {
    UserState.MAIN: {
        '📞 Связаться': lambda user_id, name: send_contact(user_id)
    },
    UserState.ORDER: {
        '← В главное меню': lambda user_id, name: (set_user_state(user_id, UserState.MAIN),
                                                   send_text(user_id, "🍞 **Главное меню**", main_keyboard()))
    }
}


def process_message(user_id, msg, state: UserState, name):
    """Центральный обработчик сообщений"""
    logger.info(f"Обработка: '{msg}' в состоянии {state.value}")

    if msg in ['🥧 Пироги', '🎂 Торты', '🍪 Печенье'] and state == UserState.MAIN:
        category_map = {
            '🥧 Пироги': (UserState.PIES, 1, "🥧 **Выберите пирог**"),
            '🎂 Торты': (UserState.CAKES, 2, "🎂 **Выберите торт**"),
            '🍪 Печенье': (UserState.COOKIES, 3, "🍪 **Выберите печенье**")
        }
        if msg in category_map:
            new_state, cat_id, text = category_map[msg]
            set_user_state(user_id, new_state)
            send_text(user_id, text, get_category_keyboard(cat_id))
            return True

    handler = STATE_HANDLERS.get(state, {}).get(msg)
    if handler:
        handler(user_id, name)
        return True

    if state in [UserState.PIES, UserState.CAKES, UserState.COOKIES]:
        cat_id = {'pies': 1, 'cakes': 2, 'cookies': 3}[state.value]
        product = find_product_by_name(msg, cat_id)

        if product:
            show_product(user_id, product[0])
            return True
        elif msg == '← Назад в главное меню':
            set_user_state(user_id, UserState.MAIN)
            send_text(user_id, "🍞 **Главное меню**", main_keyboard())
            return True
        else:
            send_text(user_id, f"**{state.value.title()}**", get_category_keyboard(cat_id))
            return True

    if state == UserState.ORDER and "Заказать сейчас" in msg:
        product_name = msg.replace('🛒 Заказать сейчас ', '').strip()
        if product_name:
            process_order_full(user_id, product_name, name)
            return True

    if state == UserState.MAIN and msg.lower() in ['привет', 'hello', 'меню', 'начать', '/start']:
        send_text(user_id, f"👋 Привет, {name}!\n🍞 **Витрина свежей выпечки!**\nВыберите категорию:",
                  main_keyboard())
        return True

    if state == UserState.MAIN:
        send_text(user_id, f"👋 Привет, {name}!\nВыберите категорию:", main_keyboard())
    else:
        send_text(user_id, "❓ Не понял. Выберите из меню:", main_keyboard())
    return True


def main_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button('🥧 Пироги', VkKeyboardColor.PRIMARY)
    kb.add_button('🎂 Торты', VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('🍪 Печенье', VkKeyboardColor.PRIMARY)
    kb.add_button('📞 Связаться', VkKeyboardColor.SECONDARY)
    return kb


def get_category_keyboard(category_id):
    products = get_category_products(category_id)
    kb = VkKeyboard(one_time=False)
    for product_id, name in products[:2]:  # Показываем первые 2 продукта
        kb.add_button(name, VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button('← Назад в главное меню', VkKeyboardColor.NEGATIVE)
    return kb


def product_keyboard(product_name):
    kb = VkKeyboard(one_time=False)
    kb.add_button(f'🛒 Заказать сейчас {product_name}', VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button('← В главное меню', VkKeyboardColor.NEGATIVE)
    return kb


def send_text(user_id, text, keyboard=None, attachment=None):
    """Универсальная функция отправки сообщения"""
    params = {
        'user_id': user_id,
        'message': text,
        'random_id': get_random_id(),
        'parse_mode': 'Markdown'
    }
    if keyboard:
        params['keyboard'] = keyboard.get_keyboard()
    if attachment:
        params['attachment'] = attachment
    vk_session.method('messages.send', params)


def show_product(user_id, product_id):
    """Показать продукт"""
    product_info = get_product_info(product_id)
    if product_info:
        name, desc, price, owner_id, photo_id = product_info
        kb = product_keyboard(name)
        attachment = f"photo{owner_id}_{photo_id}" if owner_id and photo_id else None

        send_text(user_id,
                  f"**{name}**\n\n"
                  f"{desc}\n"
                  f"📦 Вес: 300-1000г\n"
                  f"💰 {price}₽\n"
                  f"⭐ Свежая выпечка каждый день!",
                  kb, attachment)
        set_user_state(user_id, UserState.ORDER)


def send_contact(user_id):
    """Отправка контактов"""
    set_user_state(user_id, UserState.MAIN)
    send_text(user_id,
              f"📞 **Свяжитесь с нами:**\n"
              f"https://vk.com/im?sel={ADMIN_ID}\n\n"
              f"🍞 Выберите категорию:",
              main_keyboard())


def process_order_full(user_id, product_name, user_name):
    """Полная обработка заказа"""
    send_text(user_id,
              f"✅ **Заказ принят!**\n\n"
              f"🍰 **{product_name}**\n"
              f"📱 Менеджер свяжется в течение 30 минут\n"
              f"Спасибо за заказ! ❤️",
              main_keyboard())

    send_to_admin(product_name, user_id, user_name)
    set_user_state(user_id, UserState.MAIN)
    logger.info(f"✅ Заказ '{product_name}' от {user_id} обработан")


def send_to_admin(product_name, user_id, user_name):
    """Уведомление админу"""
    try:
        admin_info = vk_session.method("users.get", {"user_ids": ADMIN_ID})
        admin_name = admin_info[0]['first_name']

        server_time = vk_session.method('utils.getServerTime')
        admin_msg = (
            f"🔔 **НОВЫЙ ЗАКАЗ!**\n\n"
            f"🍰 **Товар:** {product_name}\n"
            f"👤 **Клиент:** {user_name} (ID: {user_id})\n"
            f"⏰ **Время:** {server_time}\n"
            f"📞 **Диалог:** https://vk.com/im?sel={user_id}\n\n"
            f"❗ **Обработать срочно!**"
        )
        send_text(ADMIN_ID, admin_msg)
        logger.info(f"✅ Уведомление отправлено админу {admin_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки админу: {e}")


if __name__ == '__main__':
    init_db()

    logger.info("🚀 Bakery Bot с машиной состояний запущен!")
    try:
        send_text(ADMIN_ID, "🧪 **АДМИН-ТЕСТ:** Бот готов принимать заказы!")
        logger.info("✅ Тестовое сообщение админу отправлено!")
    except:
        logger.warning("⚠️ Админ должен написать боту первым!")

    while True:
        try:
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    user_id = event.user_id
                    msg = event.text.strip()
                    logger.info(f"👤 User {user_id}: '{msg}'")

                    try:
                        user_info = vk_session.method("users.get", {"user_ids": user_id})
                        name = user_info[0]['first_name']
                    except:
                        name = "Друг"

                    state = get_user_state(user_id)
                    logger.info(f"Состояние: {state.value}")

                    process_message(user_id, msg, state, name)

        except KeyboardInterrupt:
            logger.info("🛑 Бот остановлен пользователем (Ctrl+C)")
            break
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            continue

import telebot
from telebot import types
import random
import sqlite3
import time

TOKEN = "6927225327:AAFTy2AxDWI4xeKiebxuLNZc4SF4vHm3ohE"
bot = telebot.TeleBot(TOKEN)

cards = {
    "huina": 100,
    "norma": 200,
    "good": 300,
    "verygood": 500,
}

cards_images = {
    "huina": r"D:\SpotCART\venv\Image\huina.png",
    "norma": r"D:\SpotCART\venv\Image\norma.png",
    "good": r"D:\SpotCART\venv\Image\good.png",
    "verygood": r"D:\SpotCART\venv\Image\verygood.png",
}

DATABASE_PATH = r"D:\SpotCART\venv\BD\bd"

LEVEL_COOLDOWN_MAPPING = {
    1: 4 * 60 * 60,  # Level 1: 4 hours
    2: 3 * 60 * 60,  # Level 2: 3 hours
    3: 2 * 60 * 60,  # Level 3: 2 hours
    4: 1 * 60 * 60   # Level 4: 1 hour
}

LEVEL_COST_MAPPING = {
    2: 5000,
    3: 10000,
    4: 100000
}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
        player_data = cursor.fetchone()

    if player_data is None:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO players (user_id, points, last_draw_time, level) VALUES (?, 0, 0, 1)', (user_id,))
            conn.commit()

        bot.send_message(user_id, "Привет! Добро пожаловать в игру с карточками. Нажмите /play, чтобы начать.")
    else:
        bot.send_message(user_id, f"С возвращением! Ваш текущий счет: {player_data[1]}. Уровень: {player_data[3]}")

@bot.message_handler(commands=['bonus'])
def bonus(message):
    user_id = message.from_user.id

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT last_bonus_time FROM players WHERE user_id = ?', (user_id,))
        last_bonus_time = cursor.fetchone()

    current_time = int(time.time())
    cooldown_time = 24 * 60 * 60  # 24 hours cooldown for the daily bonus

    if last_bonus_time is None or current_time - last_bonus_time[0] >= cooldown_time:
        # Grant bonus attempts
        bonus_attempts = random.randint(1, 10)

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE players SET bonus_attempts = ? WHERE user_id = ?', (bonus_attempts, user_id))
            cursor.execute('UPDATE players SET last_bonus_time = ? WHERE user_id = ?', (current_time, user_id))
            conn.commit()

        bot.send_message(user_id, f"Вы получили {bonus_attempts} бонусных попыток! Нажмите /play, чтобы использовать их.")
    else:
        remaining_cooldown = cooldown_time - (current_time - last_bonus_time[0])
        bot.send_message(user_id, f"Ежедневный бонус уже был получен. Вы сможете получить новый через {remaining_cooldown // 3600} часов.")

# Modify the play command to use bonus attempts
@bot.message_handler(commands=['play'])
def play(message):
    user_id = message.from_user.id
    current_time = int(time.time())

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT points, last_draw_time, level, bonus_attempts FROM players WHERE user_id = ?', (user_id,))
        player_data = cursor.fetchone()

        if player_data is not None:
            last_draw_time = player_data[1]
            user_level = player_data[2]
            bonus_attempts = player_data[3]
            cooldown_time = LEVEL_COOLDOWN_MAPPING.get(user_level, 4 * 60 * 60)  # Default to 4 hours if level not found

            if bonus_attempts > 0:
                # Use a bonus attempt
                cursor.execute('UPDATE players SET bonus_attempts = bonus_attempts - 1 WHERE user_id = ?', (user_id,))
            elif current_time - last_draw_time < cooldown_time:
                remaining_cooldown = cooldown_time - (current_time - last_draw_time)
                bot.send_message(user_id, f"Вы можете выбирать карточку через {remaining_cooldown // 60} минут.")
                return

            card_name, card_points = random.choice(list(cards.items()))
            card_image_path = cards_images[card_name]

            cursor.execute('UPDATE players SET points = points + ?, last_draw_time = ? WHERE user_id = ?', (card_points, current_time, user_id))
            conn.commit()

            player_points = player_data[0] + card_points

            card_info_text = (
                f"🧀 Купи лабы, бро\n"
                f"🍔 Редкость: {card_name.capitalize()}\n"
                f"🍿 + {card_points} point\n"
                f"💰 Ваш текущий счет: {player_points} points"
            )

            with open(card_image_path, 'rb') as photo:
                bot.send_photo(user_id, photo, caption=card_info_text)

@bot.message_handler(commands=['magazine'])
def magazine(message):
    user_id = message.from_user.id

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT points, level FROM players WHERE user_id = ?', (user_id,))
        player_data = cursor.fetchone()

        if player_data is not None:
            player_points = player_data[0]
            user_level = player_data[1]

            if user_level < 4:
                level_cost = LEVEL_COST_MAPPING.get(user_level + 1, 0)  # Get the cost for the next level
                if player_points >= level_cost:
                    markup = types.ReplyKeyboardMarkup(row_width=2)
                    item_yes = types.KeyboardButton('Да')
                    item_no = types.KeyboardButton('Назад')
                    markup.add(item_yes, item_no)

                    bot.send_message(user_id, f"У вас сейчас {user_level} level. Чтобы перейти на следующий level, нужно заплатить {level_cost} points.", reply_markup=markup)
                    bot.register_next_step_handler(message, process_magazine_step)
                else:
                    bot.send_message(user_id, f"У вас недостаточно points для покупки уровня {user_level + 1}.")
            else:
                bot.send_message(user_id, "Вы уже достигли максимального уровня.")
        else:
            bot.send_message(user_id, "Чтобы посещать магазин, начните игру с команды /start.")
def process_magazine_step(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT points, level FROM players WHERE user_id = ?', (user_id,))
        player_data = cursor.fetchone()

        if player_data is not None:
            user_level = player_data[1]

            if message.text.lower() == 'да':
                level_cost = LEVEL_COST_MAPPING.get(user_level + 1, 0)
                cursor.execute('UPDATE players SET points = points - ?, level = level + 1 WHERE user_id = ?', (level_cost, user_id))
                conn.commit()
                bot.send_message(chat_id, f"Вы успешно купили уровень {user_level + 1} за {level_cost} points.",
                                 reply_markup=types.ReplyKeyboardRemove(selective=False))
            elif message.text.lower() == 'назад':
                markup = types.ReplyKeyboardRemove(selective=False)
                bot.send_message(chat_id, "Пошел нахуй нищеброд", reply_markup=markup)
            else:
                bot.send_message(chat_id, "Пожалуйста, выберите 'Да' или 'Назад'.")
        else:
            bot.send_message(chat_id, "Чтобы посещать магазин, начните игру с команды /start.")

# Move leaderboard outside of the process_magazine_step function
@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT user_id, points FROM players ORDER BY points DESC LIMIT 10')  # Получаем топ-10 игроков
        leaderboard_data = cursor.fetchall()

    if leaderboard_data:
        leaderboard_text = "🏆 Топ-10 игроков:\n"
        for rank, (user_id, points) in enumerate(leaderboard_data, start=1):
            try:
                user_info = bot.get_chat_member(message.chat.id,
                                                user_id).user  # Получаем информацию о пользователе
                user_name = f"{user_info.first_name} {user_info.last_name}"
            except Exception as e:
                user_name = f"Пользователь {user_id}"

            leaderboard_text += f"{rank}. {user_name} - {points} очков\n"

        bot.send_message(message.chat.id, leaderboard_text)
    else:
        bot.send_message(message.chat.id, "Лидерборд пока пуст. Начните игру, чтобы попасть в топ!")

if __name__ == "__main__":
    bot.polling(none_stop=True)
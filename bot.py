#!/usr/bin/env python3

import random
import telebot
from telebot import types
import psycopg2

from task import Task
from state import State


def gen_task():
    # gen 1st number
    a = random.randrange(2, 20, 1)
    # gen 2nd number
    b = random.randrange(2, 20, 1)

    t = Task()
    t.task = f"{a}x{b}"
    t.answer = f"{a * b}"
    return t

def gen_easy_task():
    # gen 1st number
    a = random.randrange(2, 10, 1)
    # gen 2nd number
    b = random.randrange(2, 10, 1)

    t = Task()
    t.task = f"{a}x{b}"
    t.answer = f"{a * b}"
    return t


conn = None

state_storage = {}


def get_user_state(user_id, user_name):
    """
    Get state from database or return fresh state if no records for the user.

    :param user_id: Unique identifier for user
    :return: State
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT
            user_id, task, answer, tries, score, user_score, offline
        FROM
            user_state 
        WHERE
            user_id=%s
        """,
        (user_id,))
    row = cur.fetchone()
    cur.close()
    if row is None:
        s = State()
        s.new = True
        s.user_id = user_id
        s.user_name = user_name
        return s

    t = None
    if row[1] is not None:
        t = Task()
        t.task = row[1]
        t.answer = row[2]

    s = State()
    s.user_id = row[0]
    s.task = t
    s.tries = row[3]
    s.score = row[4]
    s.user_score = row[5]
    s.offline = row[6]

    if user_id in state_storage:
        s.message_with_inline_keyboard_id = state_storage[user_id].message_with_inline_keyboard_id

    return s


def save_user_state(user_state):
    """
    Insert a new state in the database or update an existing record.
    :param user_state:
    :return:
    """

    task = Task()
    task.task = None
    task.answer = None
    if user_state.task is not None:
        task = user_state.task

    if user_state.new:
        # insert
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO
           user_state
        VALUES
            (%s, %s, %s, %s, %s, %s, %s,%s)
        """,
            (user_state.user_id, task.task, task.answer, user_state.tries, user_state.score, user_state.user_score, user_state.offline, user_state.user_name))
    else:
        # update
        cur = conn.cursor()
        cur.execute("""
            UPDATE user_state
            SET
              task=%s,
              answer=%s,
              tries=%s,
              score=%s,
              user_score=%s,
              offline=%s
            WHERE
              user_id=%s
        """,
            (task.task, task.answer, user_state.tries, user_state.score, user_state.user_score,user_state.offline, user_state.user_id))
    # Save to database
    conn.commit()
    cur.close()
    # Save to local storage
    state_storage[user_state.user_id] = user_state


def new_task_markup():
    markup = types.InlineKeyboardMarkup(row_width=1)
    gave_up_btn = types.InlineKeyboardButton('Новая задача', callback_data="give_up")
    markup.add(gave_up_btn)
    return markup

def end_of_game():
    markup = types.InlineKeyboardMarkup(row_width=1)
    end_btn = types.InlineKeyboardButton('Хватит пока', callback_data="end")
    gave_up_btn = types.InlineKeyboardButton('Новая задача', callback_data="give_up")
    markup.add(gave_up_btn, end_btn)
    return markup

def remind_task():
    markup = types.InlineKeyboardMarkup(row_width=1)
    remind_btn = types.InlineKeyboardButton('Напомнить задачу', callback_data="remind")
    gave_up_btn = types.InlineKeyboardButton('Новая задача', callback_data="give_up")
    markup.add(gave_up_btn, remind_btn)
    return markup


def remove_reply_markup(chat_id, state, new_msg):
    if state.message_with_inline_keyboard_id is not None:
        bot.edit_message_reply_markup(chat_id, state.message_with_inline_keyboard_id, reply_markup=None)
    # Save message_id from new message to remove a keyboard in the future.
    state.message_with_inline_keyboard_id = None
    if new_msg is not None:
        state.message_with_inline_keyboard_id = new_msg.message_id


# Start Bot
f = open("token.txt", "r")
token = f.read()
bot = telebot.TeleBot(token, parse_mode=None)


@bot.message_handler(commands=['help'])
def on_help(message):
    bot.reply_to(message, "Чтобы начать викторину, нажми кнопку 'Новая задача' или отправь любое сообщение.")


@bot.message_handler(commands=['start'])
def on_start(message):
    # Load user state
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    state = get_user_state(user_id, user_name)
    if state.task is None:
        # Send welcome message with inline keyboard.
        start_msg = bot.send_message(message.chat.id, "Привет! Давай порешаем задачки?", reply_markup=new_task_markup())
        # remove keyboard from earlier message
        remove_reply_markup(message.chat.id, state, start_msg)
        save_user_state(state)
    else:
        bot.reply_to(message, f"Задана задача:\n{state.task.task}")


# Handle all messages with all content_type
@bot.message_handler(func=lambda m: True, content_types=telebot.util.content_type_media)
def on_all(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    state = get_user_state(user_id, user_name)

    if state.offline == True:
        bot.send_message(message.chat.id, "Привет снова! Вот тебе задачка для начала:")
        state.offline = False

    if message.text == "Сложно":
        if int(state.task.answer) > 100:
            task = gen_easy_task()
            state.task = task
            state.tries = 0
            state.score = 50
            state.user_id = user_id
            bot.send_message(message.chat.id,"Ладно, давай дам полегче: " + task.task)
            remove_reply_markup(message.chat.id, state, None)
            save_user_state(state)
            return
        else:
            bot.send_message(message.chat.id,"Нет, это лекго, наприги извилены и реши задачу! " + state.task.task)
            return

    if state.task is None:
        # Generate new task, show to user.
        task = gen_task()
        state.task = task
        state.tries = 0
        state.user_id = user_id
        bot.send_message(message.chat.id, task.task)
        # remove keyboard from earlier message
        remove_reply_markup(message.chat.id, state, None)
        save_user_state(state)
    else:
        # Check answer
        if message.text == state.task.answer:
            msg = bot.send_message(message.chat.id, f"И правда, {state.task.task}={message.text}. Продолжим?",
                                   reply_markup=end_of_game())
            # remove keyboard from earlier message
            remove_reply_markup(message.chat.id, state, msg)
            state.task = None
            state.tries = 0
            state.user_id = user_id
            state.user_score += state.score
            state.score = 100
            save_user_state(state)
        else:
            wrong_msg = bot.send_message(message.chat.id, "Неверный ответ, попробуй ещё раз.",
                                         reply_markup=remind_task())
            # remove keyboard from earlier message
            remove_reply_markup(message.chat.id, state, wrong_msg)
            state.score -= 10
            save_user_state(state)


# Handle inline keyboard button clicks
@bot.callback_query_handler(func=lambda call: True)
def inline_handler(call):
    if call.data == "end":
        bot.answer_callback_query(call.id)
        user_name = call.from_user.first_name
        user_id = call.from_user.id
        state = get_user_state(user_id, user_name)
        bot.send_message(call.message.chat.id, "Ладно пока, пиши если захочешь еще порешать задачки!")
        state.offline = True

    if call.data == "remind":
        bot.answer_callback_query(call.id)
        user_name = call.from_user.first_name
        user_id = call.from_user.id
        state = get_user_state(user_id, user_name)
        bot.send_message(call.message.chat.id, "Твоя активная задача: " + state.task.task)

    if call.data == "give_up":
        bot.answer_callback_query(call.id)
        user_name = call.from_user.first_name
        user_id = call.from_user.id
        state = get_user_state(user_id, user_name)
        # Generate new task and show to user.
        task = gen_task()
        state.task = task
        state.tries = 0
        state.user_id = user_id
        bot.send_message(call.message.chat.id, task.task)

    # Remove button from saved message id.
    if state.message_with_inline_keyboard_id != call.message.message_id:
        remove_reply_markup(call.message.chat.id, state, None)
    # Remove clicked button.
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    state.message_with_inline_keyboard_id = None
    save_user_state(state)


if __name__ == "__main__":
    # Open db connection
    f = open("db.txt", "r")
    db_conn = f.read()
    conn = psycopg2.connect(db_conn)

    # Test connection
    tcur = conn.cursor()
    tcur.execute("SELECT count(1) FROM user_state;")
    print("{0} users in database.".format(tcur.fetchone()[0]))
    tcur.close()

    # Start bot loop.
    bot.polling()

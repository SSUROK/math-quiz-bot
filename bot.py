#!/usr/bin/env python3

import random
import telebot
from telebot import types
import psycopg2

from task import Task
from state import State


def gen_task():
    # gen 1st number
    a = random.randrange(1, 9, 1)
    # gen 2nd number
    b = random.randrange(1, 9, 1)

    t = Task()
    t.task = f"{a}x{b}"
    t.answer = f"{a * b}"
    return t


conn = None

state_storage = {}


def get_user_state(user_id):
    """
    Get state from database or return fresh state if no records for the user.

    :param user_id: Unique identifier for user
    :return: State
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT
            user_id, task, answer, tries
        FROM
            state 
        WHERE
            user_id=%s
        """,
        (user_id,))
    row = cur.fetchone()
    cur.close()
    if row is None:
        s = State()
        s.new = True
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
           state
        VALUES
            (%s, %s, %s, %s)
        """,
            (user_state.user_id, task.task, task.answer, user_state.tries))
    else:
        # update
        cur = conn.cursor()
        cur.execute("""
            UPDATE state
            SET
              task=%s,
              answer=%s,
              tries=%s
            WHERE
              user_id=%s
        """,
            (task.task, task.answer, user_state.tries, user_state.user_id))
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
    state = get_user_state(user_id)
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
    state = get_user_state(user_id)

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
                                   reply_markup=new_task_markup())
            # remove keyboard from earlier message
            remove_reply_markup(message.chat.id, state, msg)
            state.task = None
            state.tries = 0
            state.user_id = user_id
            save_user_state(state)
        else:
            wrong_msg = bot.send_message(message.chat.id, "Неверный ответ, попробуйте ещё раз.",
                                         reply_markup=new_task_markup())
            # remove keyboard from earlier message
            remove_reply_markup(message.chat.id, state, wrong_msg)
            save_user_state(state)


# Handle inline keyboard button clicks
@bot.callback_query_handler(func=lambda call: True)
def inline_handler(call):
    if call.data != "give_up":
        return
    bot.answer_callback_query(call.id)

    user_id = call.from_user.id
    state = get_user_state(user_id)
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
    tcur.execute("SELECT count(1) FROM state;")
    print("{0} users in database.".format(tcur.fetchone()[0]))
    tcur.close()

    # Start bot loop.
    bot.polling()

class State:
    # Telegram user id
    user_id = None

    user_name = None
    # current task. type Task
    task = None
    #
    tries = 0

    score = 100

    operator = "*"

    user_score = 0
    # start message with inline keyboard
    message_with_inline_keyboard_id = None
    # new user observed
    new = False

    offline = False

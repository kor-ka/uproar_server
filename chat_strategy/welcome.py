import re
from telegram import Message, User, InlineKeyboardMarkup, InlineKeyboardButton

thumb_up = u'\U0001F44D'
thumb_down = u'\U0001F44E'


def on_message(chat_actor, message):
    chat_actor = chat_actor  # type: ChatActor
    message = message  # type: Message

    if message.new_chat_members and message.new_chat_members[0].username == "uproarbot":
        chat_actor.bot.ask(
            {'command': 'send', 'chat_id': message.chat_id,
             'message': 'Hi! I\'ll manage this chat playlist starting from... now! Send me some music from your own '
                        'library or using this bots:'
                        '\n@vkm\_bot - inline music search from vk.com'
                        '\n@vid - inline video search'
                        '\n'
                        '\nfor example type'
                        '\n*@vkm_bot club foot*'
                        '\nin this chat, and tap on first result from list', "parse_mode": "Markdown"})

    # first track in this chat
    if (message.audio or (message.text and re.match("^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$", message.text))) and len(chat_actor.latest_tracks.get()) == 1:
        chat_actor.send_url(message)
        step_two(chat_actor, message)

    if message.text and "/twst" in message.text:
        step_two(chat_actor,message)


def step_two(chat_actor, message):
    chat_actor.bot.ask(
        {'command': 'send', 'chat_id': message.chat_id,
         'message': 'Great!'
                    '\nAs it is your first track in this chat, I\'ve made link for you :)'
                    '\nOpen it in your browser and track will play there'
                    '\n'
                    '\nWhat\'s next?'
                    '\nInvite some friends, let them send music here, have fun!'
                    '\n'
                    '\nOh, I almost forgot - see %s/%s buttons under your track?'
                    '\nPress them if you like/dislike the track'
                    '\nIf a track gets 2 likes/dislikes anyone can promote/skip it!' % (thumb_up, thumb_down)})


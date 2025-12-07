from flask import Flask, request
import os
import telebot
from bot import bot, BOT_TOKEN

app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Plush NFT Bot is running!"

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

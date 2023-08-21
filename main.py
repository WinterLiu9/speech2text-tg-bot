import telebot

from gmail import GMailService
from speech2text import OpenaiAPI, SplitWavAudioMubin
from util import is_valid_email, load_yaml_file
import uuid

BOT_TOKEN = load_yaml_file('./config/config.yaml')['token']

bot = telebot.TeleBot(BOT_TOKEN)

speech_dict = {}

class Speech:
    def __init__(self, file_name):
        self.file_name = file_name
        self.language = None
        self.need_translation = None
        self.email = None

# Handle '/start' and '/help'
@bot.message_handler(commands=['start'])
def send_welcome(message):
    msg = bot.reply_to(message, """\
Hi there, I am a Speech2Text bot.
Please upload your Audio file or sent me a voice
""")
    bot.register_next_step_handler(msg, process_file_step)

def process_file_step(message):
    try:
        chat_id = message.chat.id
        try:
            fileID = message.audio.file_id
            file_name = message.audio.file_name
        except Exception as e:
            fileID = message.voice.file_id
            file_name = f'{uuid.uuid4().hex}.ogg'
        print('fileId: ' + fileID)
        print('file_name: ' + file_name)
        file_info = bot.get_file(fileID)
        downloaded_file = bot.download_file(file_info.file_path)
        with open(f'./media/{file_name}', 'wb') as new_file:
            new_file.write(downloaded_file)

        speech = Speech(file_name)
        speech_dict[chat_id] = speech

        markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
        markup.add('English', 'Chinese')
        msg = bot.reply_to(message, 'What is your language of your audio', reply_markup=markup)

        bot.register_next_step_handler(msg, process_language_step)
    except Exception as e:
        bot.reply_to(message, 'only upload your audio file in this step, please re-start')

def process_language_step(message):
    try:
        chat_id = message.chat.id
        language = message.text
        speech = speech_dict[chat_id]
        if language == u'English':
            speech.language = 'en'
        elif language == u'Chinese':
            speech.language = 'zh'
        else:
            raise Exception("Unknown language")
        if language == u'English':
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True)
            markup.add('Yes', 'No')
            msg = bot.reply_to(message, 'Do you need Chinese translation? ', reply_markup=markup)
            bot.register_next_step_handler(msg, process_translation_step)
        else:
            msg = bot.reply_to(message, 'What is your email? The result will be sent to your email within minutes.')
            bot.register_next_step_handler(msg, process_email_step)
    except Exception as e:
        bot.reply_to(message, 'oooops')

def process_translation_step(message):
    try:
        chat_id = message.chat.id
        need_translation = message.text
        speech = speech_dict[chat_id]
        if need_translation == u'Yes':
            speech.need_translation = True
        elif need_translation == u'No':
            speech.need_translation = False
        else:
            raise Exception("Unknown need translation type")
        msg = bot.reply_to(message, 'What is your email? The result will be sent to your email within minutes.')
        bot.register_next_step_handler(msg, process_email_step)
    except Exception as e:
        bot.reply_to(message, 'oooops')

def process_email_step(message):
    try:
        chat_id = message.chat.id
        email = message.text
        if not is_valid_email(email):
            bot.send_message(chat_id, f'please enter the correct email address and re-strat')
        speech = speech_dict[chat_id]
        speech.email = email

        split_wav = SplitWavAudioMubin('./media', speech.file_name)
        split_wav.multiple_split(min_per_split=5)

        openai = OpenaiAPI('./media', speech.file_name, split_wav.split_files, speech.language, speech.need_translation)
        openai.speech2text()

        en_res = openai.texts
        zh_res = openai.translated_texts

        mail = GMailService([email], f'[Speech2Text] {speech.file_name}', en_res+zh_res)
        mail.send_email()

        res = f'''file name: {speech.file_name},
language: {speech.language},
email: {speech.email},
need_translation: {speech.need_translation},
en_res: {openai.texts},
zh_res: {openai.translated_texts}        '''
        bot.send_message(chat_id, res)
    except Exception as e:
        bot.reply_to(message, 'oooops')




# Enable saving next step handlers to file "./.handlers-saves/step.save".
# Delay=2 means that after any change in next step handlers (e.g. calling register_next_step_handler())
# saving will hapen after delay 2 seconds.
bot.enable_save_next_step_handlers(delay=2)

# Load next_step_handlers from save file (default "./.handlers-saves/step.save")
# WARNING It will work only if enable_save_next_step_handlers was called!
bot.load_next_step_handlers()

bot.infinity_polling()

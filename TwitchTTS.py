import concurrent.futures
import random
import keyboard
import pyautogui
import json
from gtts import gTTS
import os
import time
import TwitchPlays_Connection           ### Connection file ###      
import audio_player                     ### Audio player file ###


########### ATTRIBUTION ###########
# The majority of this code is from https://github.com/DougDougGithub/TwitchPlays
# I don't know how this all works, it just does.
# If you have questions, you are probably smarter than I am....

########### ISSUES ###########
#Can't change speed or pitch
#Can't access source on OBS

##################### ADD TWITCH CHANNEL HERE #####################
TWITCH_CHANNEL = 'mr_cheese_22'

##################### MESSAGE QUEUE VARIABLES #####################
# MESSAGE_RATE controls how fast we process incoming Twitch Chat messages. It's the number of seconds it will take to handle all messages in the queue.
# This is used because Twitch delivers messages in "batches", rather than one at a time. So we process the messages over MESSAGE_RATE duration, rather than processing the entire batch at once.
# A smaller number means we go through the message queue faster, but we will run out of messages faster and activity might "stagnate" while waiting for a new batch. 
# A higher number means we go through the queue slower, and messages are more evenly spread out, but delay from the viewers' perspective is higher.
# You can set this to 0 to disable the queue and handle all messages immediately. However, then the wait before another "batch" of messages is more noticeable.
MESSAGE_RATE = 0.5
# MAX_QUEUE_LENGTH limits the number of commands that will be processed in a given "batch" of messages. 
# e.g. if you get a batch of 50 messages, you can choose to only process the first 10 of them and ignore the others.
# This is helpful for games where too many inputs at once can actually hinder the gameplay.
# Setting to ~50 is good for total chaos, ~5-10 is good for 2D platformers
MAX_QUEUE_LENGTH = 20
MAX_WORKERS = 20    # Maximum number of threads you can process at a time

last_time = time.time()
message_queue = []
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
active_tasks = []
pyautogui.FAILSAFE = False

##################### FILEPATH VARIABLES #####################
WORKING_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
VOICE_CONFIG_FILE = WORKING_DIRECTORY + "\\voice_config.json"
VOICE_DIRECTORY = WORKING_DIRECTORY + "\\voices\\"

# Configuration for available accents
ACCENTS = [
    {'language': 'en', 'accent': 'com.au'}, #Austrailian
    {'language': 'en', 'accent': 'co.uk'},  #United Kingdom
    {'language': 'en', 'accent': 'us'},     #United States
    {'language': 'en', 'accent': 'ca'},     #Canada
    {'language': 'en', 'accent': 'co.in'},  #India
    {'language': 'en', 'accent': 'ie'},     #Ireland
    {'language': 'en', 'accent': 'co.za'},  #South Africa
    {'language': 'en', 'accent': 'com.ng'}, #Nigeria
]

# Accent map for users to switch accents
ACCENT_MAP = {
    'australian': 'com.au',
    'united kingdom': 'co.uk',
    'united states': 'us',
    'canada': 'ca',
    'india': 'co.in',
    'ireland': 'ie',
    'south africa': 'co.za',
    'nigeria': 'com.ng'
}

# Load or initialize voice configuration
if os.path.exists(VOICE_CONFIG_FILE):
    with open(VOICE_CONFIG_FILE, "r") as f:
        voice_config = json.load(f)
else:
    voice_config = {}

def save_voice_config():
    with open(VOICE_CONFIG_FILE, "w") as f:
        json.dump(voice_config, f, indent=4)

def create_voice_for_user(username):
    if username not in voice_config:
        accent = random.choice(ACCENTS)
        voice_config[username] = {
            "language": accent["language"],
            "accent": accent["accent"],  # Save the full accent (e.g., 'com.au')
            "speed": round(random.uniform(0.5, 2.0), 2),  # Random speed between 0.8x and 1.2x
            "pitch": round(random.uniform(0.8, 1.2), 2)   # Random pitch between 0.8x and 1.2x
        }
        save_voice_config()

def generate_voice(username, msg):
    if username not in voice_config:
        create_voice_for_user(username)
    
    user_voice = voice_config[username]
    language = user_voice["language"]
    accent = user_voice["accent"]
    speed = user_voice["speed"]
    pitch = user_voice["pitch"]
    
    tts = gTTS(text=msg, lang=language, tld=accent, slow=(speed < 1.0))
    filename = VOICE_DIRECTORY + f"voice_{username}.mp3"
    tts.save(filename)
    
    return filename

def handle_message(message, audio_player):
    try:
        msg = message['message'].lower()
        username = message['username'].lower()

        print("Message: " + username + " --> " + msg)

        # Check if the message is an accent command
        if msg.startswith("!accent "):  # Ensure the command starts with !accent
            new_accent_name = msg[8:].lower()
            if new_accent_name in ACCENT_MAP:
                new_accent = ACCENT_MAP[new_accent_name]
                voice_config[username]["accent"] = new_accent
                save_voice_config()
                print(f"Changed accent for {username} to {new_accent_name} ({new_accent})")
                return  # Exit early since this is an accent change command
            else:
                print(f"Invalid accent: {new_accent_name}")
                return  # Exit early for invalid accent

        # Ensure the user has a unique voice configuration
        create_voice_for_user(username)

        # Generate and play the voice for the message
        voice_path = generate_voice(username, msg)
        audio_player.play_audio(audio_player, voice_path, True, False, False)

    except Exception as e:
        print("Encountered exception: " + str(e))


print("Starting TwitchTTS for --> " + TWITCH_CHANNEL)
time.sleep(1)

t = TwitchPlays_Connection.Twitch()
t.twitch_connect(TWITCH_CHANNEL)

Audio_Player = audio_player.AudioManager

while True:
    active_tasks = [t for t in active_tasks if not t.done()]
    new_messages = t.twitch_receive_messages()
    if new_messages:
        message_queue += new_messages
        message_queue = message_queue[-MAX_QUEUE_LENGTH:]

    messages_to_handle = []
    if not message_queue:
        last_time = time.time()
    else:
        r = 1 if MESSAGE_RATE == 0 else (time.time() - last_time) / MESSAGE_RATE
        n = int(r * len(message_queue))
        if n > 0:
            messages_to_handle = message_queue[0:n]
            del message_queue[0:n]
            last_time = time.time()

    if keyboard.is_pressed('shift+backspace'):
        exit()

    if not messages_to_handle:
        continue
    else:
        for message in messages_to_handle:
            if len(active_tasks) <= MAX_WORKERS:
                active_tasks.append(thread_pool.submit(handle_message, message, Audio_Player))
            else:
                print(f'WARNING: active tasks ({len(active_tasks)}) exceeds number of workers ({MAX_WORKERS}). ({len(message_queue)} messages in the queue)')
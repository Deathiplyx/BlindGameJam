import os
import sys
import time
import threading
import asyncio
import pygame
import edge_tts
import speech_recognition as sr


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)

VOICE = "en-US-GuyNeural"
TEMP_TTS_FILE = resource_path("tts_line.wav")

AMBIENCE_VOLUME = 0.25

_recognizer = sr.Recognizer()
_recognizer.pause_threshold = 1.0
_recognizer.dynamic_energy_threshold = True
_recognizer.non_speaking_duration = 0.5

audio_lock = threading.Lock()
_active_ambience = []

_mic = None


MIC_BRAND_WEIGHTS = {

    "neumann": 210,
    "telefunken": 205,
    "schoeps": 205,
    "dpa": 205,
    "earthworks": 205,
    "brüel & kjær": 205,
    "b&k": 205,

    "shure": 200,
    "rode": 195,
    "royer": 195,
    "beyerdynamic": 190,
    "sennheiser": 190,
    "akg": 185,
    "audio technica": 185,
    "audiotechnica": 185,
    "electro-voice": 185,
    "ev": 185,
    "heil": 185,
    "heil sound": 185,
    "manley": 185,
    "milab": 185,
    "oktava": 185,
    "lautenaudio": 185,
    "lauten": 185,
    "microtech gefell": 185,
    "jz microphones": 180,
    "brauner": 180,
    "aea": 180,

    "blue": 175,
    "yeti": 175,
    "zoom": 175,
    "tascam": 175,
    "fostex": 170,
    "cad": 170,
    "cad audio": 170,
    "m-audio": 170,
    "peavey": 170,
    "line 6": 170,
    "samson": 165,

    "hyperx": 165,
    "steelseries": 165,
    "razer": 160,
    "elgato": 160,
    "fifine": 155,

    "sony": 150,
    "philips": 145,
    "grundig": 145,
    "dji": 145,
    "zoom corporation": 145,
    "toa": 140,

    "nady": 135,
    "mipro": 135,
    "gauge": 135,
    "core sound": 135,
    "nti audio": 135,
    "pcb piezotronics": 135,

    "logitech": 130,
    "logi": 130,
    "anker": 125,
    "corsair": 125,

    "realtek": 10
}


def score_microphone(name: str):

    n = name.lower()
    score = 0

    for brand, weight in MIC_BRAND_WEIGHTS.items():
        if brand in n:
            score += weight

    if "microphone" in n or "mic" in n:
        score += 30

    if "webcam" in n:
        score -= 20

    if "line in" in n:
        score -= 40

    if "stereo mix" in n:
        score -= 80

    if "speaker" in n:
        score -= 60

    if "output" in n:
        score -= 120

    if "mapper" in n:
        score -= 20

    return score


def find_working_microphone():

    print("[Audio] Searching for microphone...")

    try:

        mic_names = sr.Microphone.list_microphone_names()

        if not mic_names:
            print("[Audio] No microphones detected.")
            return None

        print("[Audio] Raw microphone list:")

        for i, name in enumerate(mic_names):
            print(f"   {i}: {name}")


        seen = set()
        unique_mics = []

        for i, name in enumerate(mic_names):

            normalized = name.strip().lower()

            if normalized in seen:
                continue

            seen.add(normalized)
            unique_mics.append((i, name))

        print("\n[Audio] Unique microphone devices:")

        for i, name in unique_mics:
            print(f"   {i}: {name}")


        ranked = []

        for i, name in unique_mics:
            score = score_microphone(name)
            ranked.append((score, i, name))

        ranked.sort(reverse=True)

        print("\n[Audio] Microphone priority order:")

        for score, i, name in ranked:
            print(f"   score={score:3}  index={i}  {name}")


        for score, i, name in ranked:

            try:

                print(f"[Audio] Testing mic {i}: {name}")

                with sr.Microphone(device_index=i) as source:
                    _recognizer.adjust_for_ambient_noise(source, duration=0.5)

                print(f"[Audio] Using microphone: {name}")

                return sr.Microphone(device_index=i)

            except Exception as e:

                print(f"[Audio] Mic {i} failed: {e}")

    except Exception as e:

        print(f"[Audio] Microphone scan failed: {e}")

    print("[Audio] No usable microphone found.")

    return None


_mic = find_working_microphone()

if _mic:

    with _mic as source:

        print("[Audio] Calibrating microphone...")
        _recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[Audio] Microphone ready.")

else:

    print("[Audio] Voice input disabled.")


SYNONYMS = {
    "look": ["look", "see", "describe"],
    "go": ["go", "move", "walk", "forward", "continue"],
    "listen": ["listen", "hear"],
    "repeat": ["repeat", "again"]
}


def normalize_text(text: str):

    text = text.lower()

    for c in ",.!?":
        text = text.replace(c, "")

    words = text.split()
    expanded = set(words)

    for base, group in SYNONYMS.items():
        if any(w in words for w in group):
            expanded.add(base)

    return list(expanded)


async def _generate_tts(text):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(TEMP_TTS_FILE)


def speak_lines(lines: list[str]):

    with audio_lock:

        for text in lines:

            print(f"[Narration] {text}")

            asyncio.run(_generate_tts(text))

            sound = pygame.mixer.Sound(TEMP_TTS_FILE)
            channel = sound.play()

            while channel.get_busy():
                pygame.event.pump()
                time.sleep(0.01)

            time.sleep(0.3)


_PAN_MAP = {
    "left": (1.0, 0.0),
    "right": (0.0, 1.0),
    "center": (0.8, 0.8)
}


def stop_ambience():

    global _active_ambience

    for ch in _active_ambience:
        try:
            ch.stop()
        except:
            pass

    _active_ambience = []


def play_sound(filepath: str, pan="center", loop=False):

    full_path = resource_path(filepath)

    if not os.path.exists(full_path):
        print(f"[Audio] WARNING – file not found: {full_path}")
        return None

    left_vol, right_vol = _PAN_MAP.get(pan, (0.8, 0.8))

    sound = pygame.mixer.Sound(full_path)
    loops = -1 if loop else 0
    channel = sound.play(loops=loops)

    if channel:

        if loop:
            channel.set_volume(left_vol * AMBIENCE_VOLUME,
                               right_vol * AMBIENCE_VOLUME)
        else:
            channel.set_volume(left_vol, right_vol)

    print(f"[Audio] Playing '{full_path}' pan={pan} loop={loop}")

    return channel

def play_audio_events(events: list):

    for event in events:

        filepath = event.get("file")
        text = event.get("text")
        pan = event.get("pan", "center")
        kind = event.get("type", "voice")

        if kind == "stop_ambience":
            print("[Audio] Stopping ambience")
            stop_ambience()
            continue

        if kind == "environment" and filepath:

            full_path = resource_path(filepath)

            if os.path.exists(full_path):
                stop_ambience()
                ch = play_sound(filepath, pan=pan, loop=True)
                if ch:
                    _active_ambience.append(ch)

            continue

        if filepath:

            full_path = resource_path(filepath)

            if os.path.exists(full_path):
                ch = play_sound(filepath, pan=pan)
                if ch:
                    while ch.get_busy():
                        pygame.event.pump()
                        time.sleep(0.01)

            continue

        if text:
            speak_lines([text])
            
def listen_for_keywords(valid_keywords: list[str], timeout=10):

    global _mic

    if _mic is None:
        return None

    try:

        while audio_lock.locked():
            pygame.event.pump()
            time.sleep(0.02)

        print(f"[Input] Listening for keywords: {valid_keywords}")

        try:

            with _mic as source:

                audio = _recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=4
                )

        except sr.WaitTimeoutError:

            print("[DEBUG] WaitTimeoutError — no speech detected")
            return None

        except Exception as e:

            print(f"[Audio] Mic error: {e}")
            print("[Audio] Attempting to recover microphone...")

            _mic = find_working_microphone()

            return None

        try:

            phrase = _recognizer.recognize_google(audio).lower().strip()

            print(f"[DEBUG] Raw recognized phrase: '{phrase}'")

            if not phrase:
                return None

        except sr.UnknownValueError:

            print("[DEBUG] UnknownValueError — speech not understood")
            return None

        except sr.RequestError as exc:

            print(f"[DEBUG] Speech API error: {exc}")
            return None

        words = normalize_text(phrase)

        print(f"[DEBUG] Normalized words: {words}")

        if not words:
            return None

        for keyword in valid_keywords:

            key_words = normalize_text(keyword)

            if not any(w in words for w in key_words):
                continue

            if all(w in words for w in key_words):
                print(f"[DEBUG] MATCHED keyword: {keyword}")
                return keyword

        return None

    except Exception as e:

        print(f"[DEBUG] listen_for_keywords crashed: {e}")

        return None
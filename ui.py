import pygame
import sys
import os
import time
import threading


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # temp folder where PyInstaller extracts bundled files
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


pygame.init()

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

WIDTH, HEIGHT = screen.get_size()

pygame.display.set_caption("Blind")

font = pygame.font.SysFont("consolas", 42)
hint_font = pygame.font.SysFont("consolas", 24)

BACKGROUND = (0, 0, 0)
TEXT_COLOR = (255, 255, 255)

running_overlay = False
menu_channel = None


def play_menu_music():

    global menu_channel

    sound = pygame.mixer.Sound(resource_path("main.ogg"))
    menu_channel = sound.play(loops=-1)
    menu_channel.set_volume(0.6)


def stop_menu_music(fade_time=1500):

    global menu_channel

    if menu_channel:
        menu_channel.fadeout(fade_time)


def _handle_quit():
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            pygame.quit()
            exit()

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                pygame.quit()
                exit()


def _draw_lines(lines):

    screen.fill(BACKGROUND)

    total_height = len(lines) * 60
    start_y = (HEIGHT // 2) - (total_height // 2)

    for i, line in enumerate(lines):

        surface = font.render(line, True, TEXT_COLOR)
        rect = surface.get_rect(center=(WIDTH // 2, start_y + i * 60))

        screen.blit(surface, rect)

    pygame.display.flip()


def typewriter(text, speed=0.05):

    lines = text.split("\n")
    current_lines = [""] * len(lines)

    for i, line in enumerate(lines):

        for char in line:

            _handle_quit()

            current_lines[i] += char
            _draw_lines(current_lines)

            time.sleep(speed)

        current_lines[i] = line


def show_static(text):

    lines = text.split("\n")
    _draw_lines(lines)


def fade_out(duration=1.5):

    stop_menu_music()

    overlay = pygame.Surface((WIDTH, HEIGHT))
    overlay.fill((0, 0, 0))

    steps = 40

    for i in range(steps):

        _handle_quit()

        alpha = int(255 * (i / steps))
        overlay.set_alpha(alpha)

        screen.blit(overlay, (0, 0))
        pygame.display.flip()

        time.sleep(duration / steps)


def _overlay_loop():

    global running_overlay

    while running_overlay:

        _handle_quit()

        hint = "Tip: Ask Mango for help if you are unsure what to do. Press ESC to quit."
        surface = hint_font.render(hint, True, (180, 180, 180))

        rect = surface.get_rect(center=(WIDTH // 2, HEIGHT - 40))

        screen.blit(surface, rect)
        pygame.display.flip()

        time.sleep(0.1)


def start_game_overlay():

    global running_overlay

    running_overlay = True

    thread = threading.Thread(target=_overlay_loop, daemon=True)
    thread.start()


def stop_game_overlay():

    global running_overlay
    running_overlay = False


def intro():

    play_menu_music()

    text = """
Blind

This is an audio only experience.

Please wear headphones.
A microphone is required.

Say "start" or press ENTER to begin.

Tip: If you need help,
ask Mango.
"""

    typewriter(text.strip(), speed=0.1)

    show_static(text.strip())


def outro():

    stop_game_overlay()

    text = """
Thank you for playing Blind.

Created for the Bad Ideas Game Jam.
"""

    typewriter(text.strip(), speed=0.06)

    time.sleep(5)
    fade_out()
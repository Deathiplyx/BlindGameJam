import sys
import os
import json
import argparse
import pygame
import threading
import audio
import ui


last_keyword = None
listening = False


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # temp folder where PyInstaller extracts bundled files
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


def start_listening(valid_keywords, timeout=5):
    global last_keyword, listening

    last_keyword = None
    listening = True

    def worker():
        global last_keyword, listening
        last_keyword = audio.listen_for_keywords(valid_keywords, timeout=timeout)
        listening = False

    threading.Thread(target=worker, daemon=True).start()


def load_story(path: str) -> dict:
    with open(resource_path(path), "r", encoding="utf-8") as f:
        return json.load(f)


def run_node(node_id: str, story: dict) -> str | None:

    print(f"[DEBUG MAIN] Entering run_node with node_id: {node_id}")

    if node_id not in story:
        print(f"[Engine] ERROR – node '{node_id}' not found in story.")
        return None

    node = story[node_id]

    events = node.get("audio", [])
    look_events = node.get("look", [])
    choices = node.get("choices", {})

    print(f"[DEBUG MAIN] Node choices: {choices}")

    if events:
        print("[DEBUG MAIN] Playing scene audio")
        audio.play_audio_events(events)

    if "next" in node:
        next_node = node["next"]
        print(f"[DEBUG MAIN] Auto advancing to: {next_node}")
        return next_node

    if not choices and not look_events:
        print("[DEBUG MAIN] Scene finished (cutscene with no choices)")
        return None

    valid_keywords = list(choices.keys())

    look_words = {"look", "mango", "describe", "help", "lego"}
    repeat_words = {"repeat", "again", "say again", "what did you say"}

    if look_events:
        valid_keywords += list(look_words)

    while True:

        pygame.event.pump()
        print("[DEBUG MAIN] Waiting for keyword...")

        start_listening(valid_keywords)

        while listening:
            pygame.event.pump()
            pygame.time.wait(10)

        keyword = last_keyword

        print(f"[DEBUG MAIN] listen_for_keywords returned: {keyword}")

        if keyword is None:
            print("[DEBUG MAIN] No keyword detected, continuing loop")
            pygame.time.wait(100)
            continue

        if keyword in repeat_words:
            print("[DEBUG MAIN] Repeat command triggered")
            audio.play_audio_events(events)
            continue

        if keyword in look_words and look_events:
            print("[DEBUG MAIN] LOOK command triggered")
            audio.play_audio_events(look_events)
            continue

        next_node = choices.get(keyword)

        print(f"[DEBUG MAIN] next_node lookup result: {next_node}")

        if next_node is None:
            continue

        if next_node == node_id:
            print("[DEBUG MAIN] Loopback detected and ignored")
            continue

        print(f"[DEBUG MAIN] Returning next node: {next_node}")
        return next_node


def run_game(story_path: str, start_node: str) -> None:

    story = load_story(story_path)

    if start_node not in story:
        print(f"[Engine] Start node '{start_node}' not found. Using first node in story.")
        start_node = next(iter(story))

    print(f"[Engine] Starting game at node: '{start_node}'")

    ui.intro()

    print("[Engine] Waiting for player to say start or press ENTER...")

    started = False

    while not started:

        pygame.event.pump()

        for event in pygame.event.get():

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_RETURN:
                    print("[Engine] ENTER pressed.")
                    started = True
                    break

                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        if started:
            break

        start_listening(["start", "begin"], timeout=3)

        while listening:

            pygame.event.pump()

            for event in pygame.event.get():

                if event.type == pygame.KEYDOWN:

                    if event.key == pygame.K_RETURN:
                        print("[Engine] ENTER pressed.")
                        started = True
                        break

                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()

            if started:
                break

            pygame.time.wait(10)

        if started:
            break

        keyword = last_keyword

        print(f"[DEBUG] start listener heard: {keyword}")

        if keyword:
            print("[Engine] Voice start detected.")
            started = True

    ui.fade_out()

    pygame.time.wait(300)

    ui.start_game_overlay()

    current_node = start_node

    while current_node is not None:

        pygame.event.pump()

        print(f"[DEBUG MAIN] run_game calling run_node with: {current_node}")
        current_node = run_node(current_node, story)

    ui.outro()

    pygame.mixer.quit()
    print("[Engine] Game over.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Blind-accessible audio adventure engine"
    )

    parser.add_argument(
        "story",
        nargs="?",
        default="story.json",
        help="Path to story JSON file"
    )

    parser.add_argument(
        "--start",
        default="scene1_start",
        help="Starting node ID"
    )

    args = parser.parse_args()

    run_game(args.story, args.start)

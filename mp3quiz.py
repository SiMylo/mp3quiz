import os
from io import BytesIO
from hsaudiotag import auto
from mutagen.id3 import ID3, ID3NoHeaderError
import pygame
import random
import time
import yaml

CACHE_VERSION = 3


class MusicLibrary:
    def __init__(self, directory, exclude=None, config_path=None):
        self.directory = directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_file = os.path.join(script_dir, "mp3quiz_cache.yml")
        self.config_path = config_path
        self.exclude = exclude or []
        self.songs = []
        self.timer_enabled = True
        self._cache_entries = {}
        self.refresh_index()
        self.set_selected_songs(self.default_selection())

    def find_files(self, directory):
        # Index all MP3s. Config exclusions are applied only to session selection.
        for root, _, files in os.walk(directory):
            for file in files:
                if file.lower().endswith(".mp3"):
                    yield os.path.join(root, file)

    @staticmethod
    def normalized_path(filepath):
        return os.path.normcase(os.path.abspath(filepath))

    def file_manifest(self):
        manifest = {}
        for filepath in self.find_files(self.directory):
            try:
                stat = os.stat(filepath)
            except OSError:
                continue
            manifest[self.normalized_path(filepath)] = {
                "filepath": filepath,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        return manifest

    def refresh_index(self):
        manifest = self.file_manifest()
        cached = self.load_cache()
        songs = []
        for path, file_info in manifest.items():
            cached_entry = cached.get(path)
            if cached_entry and all(
                cached_entry.get(key) == file_info[key] for key in ("size", "mtime_ns")
            ):
                songs.append(cached_entry["song"])
                continue
            song = self.read_song(file_info["filepath"])
            if song:
                songs.append(song)
        self.songs = songs
        self._cache_entries = {
            self.normalized_path(song["filepath"]): {
                "filepath": song["filepath"],
                "size": manifest[self.normalized_path(song["filepath"])]["size"],
                "mtime_ns": manifest[self.normalized_path(song["filepath"])][
                    "mtime_ns"
                ],
                "song": song,
            }
            for song in songs
        }
        self.save_cache()

    def read_song(self, filepath):
        audio = auto.File(filepath)
        artist = getattr(audio, "artist", None)
        title = getattr(audio, "title", None)
        if not artist or not title:
            print(
                f"Warning: Missing artist or title in file: {filepath} (artist: {artist}, title: {title})"
            )
            return None
        album = getattr(audio, "album", None) or os.path.basename(os.path.dirname(filepath))
        return {
            "artist": artist,
            "album": album,
            "title": title,
            "filepath": filepath,
        }

    def save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "version": CACHE_VERSION,
                    "entries": list(self._cache_entries.values()),
                },
                f,
                allow_unicode=True,
            )

    def load_cache(self):
        if not os.path.exists(self.cache_file):
            return {}
        with open(self.cache_file, "r", encoding="utf-8") as f:
            cached = yaml.safe_load(f) or {}
        if not isinstance(cached, dict) or cached.get("version") != CACHE_VERSION:
            return {}
        return {
            self.normalized_path(entry["filepath"]): entry
            for entry in cached.get("entries", [])
            if "filepath" in entry and "song" in entry
        }

    def default_selection(self):
        return [
            song
            for song in self.songs
            if not any(ex in os.path.normpath(song["filepath"]) for ex in self.exclude)
        ]

    def save_selection(self, selected_paths):
        if not self.config_path:
            return
        with open(self.config_path, "r", encoding="utf-8") as f:
            config_text = f.read()
        config = yaml.safe_load(config_text) or {}
        config["exclude"] = selection_exclusions(
            build_selection_tree(self), selected_paths, self.directory
        )
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    def set_selected_songs(self, songs):
        self.selected_songs = list(songs)
        self._unused_indexes = list(range(len(self.selected_songs)))

    def next_random(self):
        if not self._unused_indexes:
            if not self.selected_songs:
                raise RuntimeError("No songs selected")
            self._unused_indexes = list(range(len(self.selected_songs)))
        idx = random.choice(self._unused_indexes)
        self._unused_indexes.remove(idx)
        return self.selected_songs[idx]


def load_artwork(song):
    try:
        tags = ID3(song["filepath"])
    except (ID3NoHeaderError, OSError):
        return None
    for artwork in tags.getall("APIC"):
        try:
            return pygame.image.load(BytesIO(artwork.data)).convert_alpha()
        except pygame.error:
            return None
    return None


def build_selection_tree(library):
    root = {
        "name": os.path.basename(os.path.normpath(library.directory)),
        "path": "",
        "children": {},
    }
    for song in library.songs:
        relative_path = os.path.relpath(song["filepath"], library.directory)
        parts = relative_path.split(os.sep)
        node = root
        current_path = ""
        for part in parts[:-1]:
            current_path = os.path.join(current_path, part)
            node = node["children"].setdefault(
                part, {"name": part, "path": current_path, "children": {}}
            )
        node["children"][parts[-1]] = {
            "name": parts[-1],
            "path": song["filepath"],
            "song": song,
        }
    return root


def tree_songs(node):
    if "song" in node:
        yield node["song"]
    for child in node.get("children", {}).values():
        yield from tree_songs(child)


def selection_state(node, selected_paths):
    songs = list(tree_songs(node))
    if not songs or all(song["filepath"] in selected_paths for song in songs):
        return "checked" if songs else "unchecked"
    if any(song["filepath"] in selected_paths for song in songs):
        return "partial"
    return "unchecked"


def toggle_tree_node(node, selected_paths):
    songs = list(tree_songs(node))
    enable = selection_state(node, selected_paths) != "checked"
    for song in songs:
        if enable:
            selected_paths.add(song["filepath"])
        else:
            selected_paths.discard(song["filepath"])


def selection_exclusions(node, selected_paths, directory):
    songs = list(tree_songs(node))
    if not songs or all(song["filepath"] in selected_paths for song in songs):
        return []
    if not any(song["filepath"] in selected_paths for song in songs):
        if node["path"]:
            if "children" in node:
                return [os.path.normpath(node["path"])]
            return [os.path.relpath(node["path"], directory)]
        return []

    exclusions = []
    for child in node.get("children", {}).values():
        exclusions.extend(selection_exclusions(child, selected_paths, directory))
    return exclusions


def visible_tree_nodes(node, expanded, depth=0):
    for child in sorted(
        node.get("children", {}).values(), key=lambda item: item["name"].lower()
    ):
        yield child, depth
        if "children" in child and child["path"] in expanded:
            yield from visible_tree_nodes(child, expanded, depth + 1)


def create_window(size, caption):
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption(caption)
    display_info = pygame.display.Info()
    x = max(0, (display_info.current_w - size[0]) // 2)
    y = max(0, (display_info.current_h - size[1]) // 2)
    window_info = pygame.display.get_wm_info()
    hwnd = window_info.get("window")
    if hwnd and os.name == "nt":
        import ctypes

        ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0010 | 0x0040)
    return screen


def choose_songs(library, current_songs=None):
    pygame.init()
    screen = create_window((1100, 700), "MP3 Quiz - Select Music")
    font = pygame.font.SysFont(None, 24)
    heading_font = pygame.font.SysFont(None, 34)
    tree = build_selection_tree(library)
    starting_songs = (
        current_songs if current_songs is not None else library.default_selection()
    )
    selected_paths = {song["filepath"] for song in starting_songs}
    expanded = {""}
    scroll = 0
    row_height = 30
    top = 70
    bottom = 640
    start_rect = pygame.Rect(900, 650, 160, 40)
    save_rect = pygame.Rect(720, 650, 160, 40)
    timer_rect = pygame.Rect(20, 650, 220, 40)
    clock = pygame.time.Clock()
    status = ""

    while True:
        nodes = list(visible_tree_nodes(tree, expanded))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.MOUSEWHEEL:
                max_scroll = max(0, len(nodes) * row_height - (bottom - top))
                scroll = max(0, min(max_scroll, scroll - event.y * row_height))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_rect.collidepoint(event.pos):
                    if selected_paths:
                        library.set_selected_songs(
                            [
                                song
                                for song in library.songs
                                if song["filepath"] in selected_paths
                            ]
                        )
                        return True
                    status = "Select at least one song"
                    continue
                if save_rect.collidepoint(event.pos):
                    if selected_paths:
                        library.save_selection(selected_paths)
                        status = "Selection saved"
                    else:
                        status = "Select at least one song"
                    continue
                if timer_rect.collidepoint(event.pos):
                    library.timer_enabled = not library.timer_enabled
                    continue
                if top <= event.pos[1] < bottom:
                    row_index = (event.pos[1] - top + scroll) // row_height
                    if row_index < len(nodes):
                        node, _ = nodes[row_index]
                        indent = 20 + nodes[row_index][1] * 25
                        if "children" in node and event.pos[0] < indent - 2:
                            if node["path"] in expanded:
                                expanded.remove(node["path"])
                            else:
                                expanded.add(node["path"])
                        else:
                            toggle_tree_node(node, selected_paths)

        screen.fill((28, 30, 34))
        screen.blit(
            heading_font.render("Select music", True, (245, 245, 245)), (20, 18)
        )
        count = f"{len(selected_paths)} of {len(library.songs)} selected"
        screen.blit(font.render(count, True, (180, 185, 195)), (260, 27))
        screen.set_clip(pygame.Rect(0, top, 1100, bottom - top))
        for index, (node, depth) in enumerate(nodes):
            y = top + index * row_height - scroll
            if y + row_height < top or y > bottom:
                continue
            x = 20 + depth * 25
            state = selection_state(node, selected_paths)
            box_color = {
                "checked": (65, 155, 105),
                "partial": (190, 145, 55),
                "unchecked": (70, 74, 80),
            }[state]
            pygame.draw.rect(screen, box_color, (x, y + 5, 18, 18))
            if state == "partial":
                pygame.draw.rect(screen, (245, 220, 120), (x + 4, y + 9, 10, 10))
            if "children" in node:
                arrow = "-" if node["path"] in expanded else "+"
                screen.blit(font.render(arrow, True, (220, 220, 220)), (x - 18, y + 3))
            label = node["name"] + ("/" if "children" in node else "")
            screen.blit(font.render(label, True, (235, 235, 235)), (x + 28, y + 3))
        screen.set_clip(None)
        button_color = (55, 125, 190) if selected_paths else (70, 74, 80)
        pygame.draw.rect(screen, button_color, start_rect)
        screen.blit(font.render("To Quiz", True, (255, 255, 255)), (945, 658))
        pygame.draw.rect(screen, (80, 135, 165), save_rect)
        screen.blit(font.render("Save", True, (255, 255, 255)), (save_rect.x + 55, 658))
        timer_color = (65, 155, 105) if library.timer_enabled else (70, 74, 80)
        pygame.draw.rect(screen, timer_color, timer_rect)
        timer_label = "Timer: On" if library.timer_enabled else "Timer: Off"
        screen.blit(font.render(timer_label, True, (255, 255, 255)), (55, 658))
        if status:
            screen.blit(font.render(status, True, (235, 170, 95)), (20, 655))
        pygame.display.flip()
        clock.tick(30)


def play_song(song):
    filepath = song["filepath"]
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()


def format_elapsed(seconds):
    total_seconds = int(seconds)
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def show_info(screen, font, song, artwork, elapsed=None):
    artwork_rect = pygame.Rect(80, 220, 240, 240)
    if artwork:
        image = pygame.transform.smoothscale(artwork, artwork_rect.size)
        screen.blit(image, artwork_rect)
    else:
        pygame.draw.rect(screen, (70, 74, 80), artwork_rect)
        placeholder = font.render("No artwork", True, (210, 210, 210))
        screen.blit(placeholder, placeholder.get_rect(center=artwork_rect.center))

    metadata_x = 400
    labels = [
        ("Artist", song.get("artist", "Unknown")),
        ("Album", song.get("album", "Unknown")),
        ("Title", song.get("title", "Unknown")),
    ]
    for index, (label, value) in enumerate(labels):
        text = font.render(f"{label}: {value}", True, (245, 245, 245))
        screen.blit(text, (metadata_x, 230 + index * 48))
    if elapsed is not None:
        timer_text = font.render(f"Guess time: {format_elapsed(elapsed)}", True, (255, 220, 120))
        screen.blit(timer_text, (metadata_x, 390))


def game_loop(library):
    import ctypes

    pygame.init()
    pygame.mixer.init()
    screen = create_window((1200, 210), "MP3 Quiz")
    font = pygame.font.SysFont(None, 36)

    # Bring window to front (Windows only)
    try:
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

    select_rect = pygame.Rect(20, 50, 200, 40)
    info_rect = pygame.Rect(500, 50, 200, 40)
    correct_rect = pygame.Rect(380, 100, 220, 40)
    incorrect_rect = pygame.Rect(600, 100, 220, 40)
    # Move Exit button all the way to the right, same vertical as score
    exit_rect = pygame.Rect(1200 - 220, 150, 200, 40)
    running = True

    show_song_info = False
    playing_song = None
    track_started_at = None
    elapsed_guess_time = None
    artwork_cache = {}

    # Score tracking
    correct_guesses = 0
    total_played = 0

    # Automatically play a song at the beginning
    playing_song = library.next_random()
    play_song(playing_song)
    track_started_at = time.monotonic()

    while running:
        screen.fill((30, 30, 30))
        if elapsed_guess_time is not None:
            current_elapsed = elapsed_guess_time
        elif library.timer_enabled and track_started_at is not None:
            current_elapsed = time.monotonic() - track_started_at
        else:
            current_elapsed = None

        # Show Info button (blue or greyed out if already pressed)
        if show_song_info:
            pygame.draw.rect(screen, (128, 128, 128), info_rect)
            info_text_surface = font.render("Show Info", True, (180, 180, 180))
        else:
            pygame.draw.rect(screen, (70, 130, 180), info_rect)
            info_text_surface = font.render("Show Info", True, (255, 255, 255))
        screen.blit(
            info_text_surface,
            info_text_surface.get_rect(center=info_rect.center),
        )

        pygame.draw.rect(screen, (90, 105, 125), select_rect)
        select_text = font.render("Select Music", True, (255, 255, 255))
        screen.blit(select_text, select_text.get_rect(center=select_rect.center))

        # Mark Correct button (greyed out if info not shown)
        if show_song_info:
            pygame.draw.rect(screen, (70, 180, 70), correct_rect)
            correct_text = font.render("Mark Correct", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (128, 128, 128), correct_rect)
            correct_text = font.render("Mark Correct", True, (180, 180, 180))
        screen.blit(correct_text, correct_text.get_rect(center=correct_rect.center))

        # Mark Incorrect button (greyed out if info not shown)
        if show_song_info:
            pygame.draw.rect(screen, (180, 70, 70), incorrect_rect)
            incorrect_text = font.render("Mark Incorrect", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (128, 128, 128), incorrect_rect)
            incorrect_text = font.render("Mark Incorrect", True, (180, 180, 180))
        screen.blit(
            incorrect_text,
            incorrect_text.get_rect(center=incorrect_rect.center),
        )

        if not show_song_info and current_elapsed is not None:
            timer_surface = font.render(
                f"Guess time: {format_elapsed(current_elapsed)}",
                True,
                (255, 220, 120),
            )
            screen.blit(timer_surface, (760, 55))

        # Draw score in the same line as Exit button, left side
        # Adjust score position for new window height
        if total_played > 0:
            percent = int((correct_guesses / total_played) * 100)
        else:
            percent = 0
        score_text = f"Score: {correct_guesses} / {total_played} ({percent}%)"
        score_surface = font.render(score_text, True, (255, 255, 255))
        screen.blit(score_surface, (20, exit_rect.y + 5))

        # Exit button (red)
        pygame.draw.rect(screen, (220, 0, 0), exit_rect)
        exit_text = font.render("Exit", True, (255, 255, 255))
        screen.blit(exit_text, (exit_rect.x + 75, exit_rect.y + 5))

        # Show info for currently playing song
        if show_song_info and playing_song:
            artwork = artwork_cache.setdefault(
                playing_song["filepath"], load_artwork(playing_song)
            )
            show_info(screen, font, playing_song, artwork, current_elapsed)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Only allow Show Info if not already pressed
                if not show_song_info and info_rect.collidepoint(event.pos):
                    show_song_info = True
                    if library.timer_enabled and track_started_at is not None:
                        elapsed_guess_time = time.monotonic() - track_started_at
                    else:
                        elapsed_guess_time = None
                    screen = create_window((1200, 500), "MP3 Quiz")
                elif select_rect.collidepoint(event.pos):
                    if not choose_songs(library, library.selected_songs):
                        running = False
                    else:
                        size = (1200, 500) if show_song_info else (1200, 210)
                        screen = create_window(size, "MP3 Quiz")
                elif show_song_info and correct_rect.collidepoint(event.pos):
                    correct_guesses += 1
                    total_played += 1
                    playing_song = library.next_random()
                    play_song(playing_song)
                    track_started_at = time.monotonic()
                    elapsed_guess_time = None
                    screen = create_window((1200, 210), "MP3 Quiz")
                    show_song_info = False
                elif show_song_info and incorrect_rect.collidepoint(event.pos):
                    total_played += 1
                    playing_song = library.next_random()
                    play_song(playing_song)
                    track_started_at = time.monotonic()
                    elapsed_guess_time = None
                    screen = create_window((1200, 210), "MP3 Quiz")
                    show_song_info = False
                elif exit_rect.collidepoint(event.pos):
                    running = False

    pygame.quit()


def main():
    # Load config.yml for music directory and exclusions
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    directory = config.get("directory", r"C:\Users\dlarsen.NI\Music")
    exclude = config.get("exclude", [])
    library = MusicLibrary(directory, exclude=exclude, config_path=config_path)
    if not choose_songs(library):
        return
    game_loop(library)


if __name__ == "__main__":
    main()

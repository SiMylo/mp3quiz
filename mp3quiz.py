import os
from hsaudiotag import auto
import pygame
import random
import yaml


class MusicLibrary:
    def __init__(self, directory, exclude=None):
        self.directory = directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_file = os.path.join(script_dir, "mp3quiz_cache.yml")
        self.config_file = os.path.join(script_dir, "config.yml")
        self.exclude = exclude or []
        self.songs = []
        cache_exists = os.path.exists(self.cache_file)
        config_exists = os.path.exists(self.config_file)
        cache_is_stale = False
        if cache_exists and config_exists:
            cache_mtime = os.path.getmtime(self.cache_file)
            config_mtime = os.path.getmtime(self.config_file)
            if config_mtime > cache_mtime:
                cache_is_stale = True
        if cache_exists and not cache_is_stale:
            self.load_cache()
        else:
            for filepath in self.find_files(directory):
                self.add_to_library(filepath)
            self.save_cache()
        self._unused_indexes = list(range(len(self.songs)))

    def find_files(self, directory):
        # Recursively search for .mp3 files in the given directory, excluding specified folders/files
        for root, _, files in os.walk(directory):
            # Exclude folders
            if any(ex in os.path.normpath(root) for ex in self.exclude):
                continue
            for file in files:
                full_path = os.path.join(root, file)
                # Exclude files
                if any(ex in os.path.normpath(full_path) for ex in self.exclude):
                    continue
                if file.lower().endswith(".mp3"):
                    yield full_path

    def add_to_library(self, filepath):
        # Read Artist and Title tags from the mp3 file and add to songs list
        audio = auto.File(filepath)
        artist = getattr(audio, "artist", None)
        title = getattr(audio, "title", None)
        if not artist or not title:
            print(
                f"Warning: Missing artist or title in file: {filepath} (artist: {artist}, title: {title})"
            )
            return
        self.songs.append({"artist": artist, "title": title, "filepath": filepath})

    def save_cache(self):
        # Save song info to cache file
        with open(self.cache_file, "w", encoding="utf-8") as f:
            yaml.dump(self.songs, f, allow_unicode=True)

    def load_cache(self):
        # Load song info from cache file
        with open(self.cache_file, "r", encoding="utf-8") as f:
            self.songs = yaml.safe_load(f) or []

    def next_random(self):
        # Return a pseudo-random song, never repeating until all have been used
        if not self._unused_indexes:
            self._unused_indexes = list(range(len(self.songs)))
        idx = random.choice(self._unused_indexes)
        self._unused_indexes.remove(idx)
        return self.songs[idx]


def play_song(song):
    filepath = song["filepath"]
    print(f"Playing: {song['artist']} - {song['title']}")
    pygame.mixer.music.load(filepath)
    pygame.mixer.music.play()


def show_info(screen, font, song):
    # Display artist and title info for the currently playing song, centered
    info_text = f"{song['artist']} - {song['title']}"
    info_surface = font.render(info_text, True, (255, 255, 0))
    screen_width = screen.get_width()
    text_rect = info_surface.get_rect(center=(screen_width // 2, 30))
    screen.blit(info_surface, text_rect)


def game_loop(library):
    import ctypes

    pygame.init()
    pygame.mixer.init()
    # Shrink window height to just below the Exit button
    screen = pygame.display.set_mode((1200, 210))
    pygame.display.set_caption("MP3 Quiz")
    font = pygame.font.SysFont(None, 36)

    # Bring window to front (Windows only)
    try:
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

    correct_rect = pygame.Rect(400, 100, 180, 40)
    incorrect_rect = pygame.Rect(620, 100, 180, 40)
    info_rect = pygame.Rect(500, 50, 200, 40)
    # Move Exit button all the way to the right, same vertical as score
    exit_rect = pygame.Rect(1200 - 220, 150, 200, 40)
    running = True

    show_song_info = False
    playing_song = None

    # Score tracking
    correct_guesses = 0
    total_played = 0

    # Automatically play a song at the beginning
    playing_song = library.next_random()
    play_song(playing_song)

    while running:
        screen.fill((30, 30, 30))
        # Show Info button (blue or greyed out if already pressed)
        if show_song_info:
            pygame.draw.rect(screen, (128, 128, 128), info_rect)
            info_text_surface = font.render("Show Info", True, (180, 180, 180))
        else:
            pygame.draw.rect(screen, (70, 130, 180), info_rect)
            info_text_surface = font.render("Show Info", True, (255, 255, 255))
        screen.blit(info_text_surface, (info_rect.x + 40, info_rect.y + 5))

        # Mark Correct button (greyed out if info not shown)
        if show_song_info:
            pygame.draw.rect(screen, (70, 180, 70), correct_rect)
            correct_text = font.render("Mark Correct", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (128, 128, 128), correct_rect)
            correct_text = font.render("Mark Correct", True, (180, 180, 180))
        screen.blit(correct_text, (correct_rect.x + 10, correct_rect.y + 5))

        # Mark Incorrect button (greyed out if info not shown)
        if show_song_info:
            pygame.draw.rect(screen, (180, 70, 70), incorrect_rect)
            incorrect_text = font.render("Mark Incorrect", True, (255, 255, 255))
        else:
            pygame.draw.rect(screen, (128, 128, 128), incorrect_rect)
            incorrect_text = font.render("Mark Incorrect", True, (180, 180, 180))
        screen.blit(incorrect_text, (incorrect_rect.x + 10, incorrect_rect.y + 5))

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
            show_info(screen, font, playing_song)

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Only allow Show Info if not already pressed
                if not show_song_info and info_rect.collidepoint(event.pos):
                    show_song_info = True
                elif show_song_info and correct_rect.collidepoint(event.pos):
                    correct_guesses += 1
                    total_played += 1
                    playing_song = library.next_random()
                    play_song(playing_song)
                    show_song_info = False
                elif show_song_info and incorrect_rect.collidepoint(event.pos):
                    total_played += 1
                    playing_song = library.next_random()
                    play_song(playing_song)
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
    library = MusicLibrary(directory, exclude=exclude)
    game_loop(library)


if __name__ == "__main__":
    main()

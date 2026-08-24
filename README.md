# mp3quiz
Make a "guess the title/artist" quiz out of your mp3 library.

At startup, MP3 Quiz opens a music selector showing the complete indexed
library. Expand folders with the `+`/`-` control, then click a folder or an
individual file to include or exclude it from the current quiz. Folder boxes
show a partial state when only some files below them are selected. The
selection can be reopened from the quiz window with **Select Music**.

Selections last for the current run only. They are not written to
`config.yml`.

The selector also includes a session-only timer checkbox. When enabled, the
timer starts when a track begins playing and stops when **Show Info** is
pressed. The final guessing time is shown with the answer. Reopening the
selector does not reset the current track's timer.

Track information displays the Artist, Album, and Title fields alongside the
file's embedded artwork. If an album tag is missing, the containing folder is
used. Files without embedded artwork display a simple placeholder.

## Configuration

Make `config.yml` to set the music directory and exclude folders or files:

```yaml
directory: "C:\\Users\\yourname\\Music"
exclude:
  - "Your Folder"
```

- `directory`: The root folder to search for mp3 files.
- `exclude`: List of folder or file names to leave unchecked by default. Any
  path containing these names starts disabled, but can be enabled manually for
  a session.

Place `config.yml` in the same directory as `mp3quiz.py`.

Embedded artwork is read with the Poetry-managed `mutagen` dependency. To
install or refresh the project environment, run `poetry install` from the
project directory.

## Library cache

The cache stores artist and title metadata together with each MP3's path, size,
and modification time. On startup, the library performs a lightweight walk of
the music folder and only reads tags for new or changed files. Deleted files
are removed from the cache. Changing `config.yml` changes the initial
selection but does not re-index the library.

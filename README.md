# mp3quiz
Make a "guess the title/artist" quiz out of your mp3 library.

At startup, MP3 Quiz opens a music selector showing the complete indexed
library. Expand folders with the `+`/`-` control, then click a folder or an
individual file to include or exclude it from the current quiz. Folder boxes
show a partial state when only some files below them are selected. The
selection can be reopened from the quiz window with **Select Music**.

The **Save** button writes the current selection to the `exclude` list in
`config.yml`. **To Quiz** applies the current selection for the quiz without
writing the configuration. A completely unchecked folder is saved as one
folder rule; partially selected folders are represented by narrower folder or
file rules. This keeps the saved configuration compact while preserving
individual file selections.

The selector also includes a session-only timer checkbox, which defaults to
on. When enabled, the timer starts when a track begins playing and stops when
**Show Info** is pressed. The elapsed time is visible before **Show Info**, and
the final guessing time is shown with the answer. Reopening the selector does
not reset the current track's timer.

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
  matching folder or file path components start disabled. The selector updates
  this list when **Save** is pressed, using compact relative folder/file rules.

Place `config.yml` in the same directory as `mp3quiz.py`.

If `config.yml` does not exist when MP3 Quiz starts, a folder chooser opens so
you can select the music library. The selected folder is saved as the initial
`directory` in a new `config.yml`.

Embedded artwork is read with the Poetry-managed `mutagen` dependency. To
install or refresh the project environment, run `poetry install` from the
project directory.

Launch the quiz with `poetry run mp3quiz`.

## Library cache

The cache stores artist and title metadata together with each MP3's path, size,
and modification time. On startup, the library performs a lightweight walk of
the music folder and only reads tags for new or changed files. Deleted files
are removed from the cache. Changing `config.yml` changes the initial
selection but does not re-index the library.

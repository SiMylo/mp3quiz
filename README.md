# mp3quiz
Make a "guess the title/artist" quiz out of your mp3 library.

## Configuration

Make `config.yml` to set the music directory and exclude folders or files:

```yaml
directory: "C:\\Users\\yourname\\Music"
exclude:
  - "Your Folder"
```

- `directory`: The root folder to search for mp3 files.
- `exclude`: List of folder or file names to exclude from the quiz. Any path containing these names will be skipped.

Place `config.yml` in the same directory as `mp3quiz.py`.

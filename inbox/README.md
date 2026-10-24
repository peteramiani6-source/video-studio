# inbox/

Drop recordings here. Everything in this folder except this README is ignored by git.

| What you drop | What to run |
|---|---|
| one talk or podcast file | nothing, if the watcher is running; otherwise `scripts/run.sh inbox/<file>` |
| a folder of event footage (+ optional `event.json`) | `scripts/event.sh "inbox/<folder>" "Title" "Subtitle"` |
| a folder of short takes or angles | `scripts/montage.sh "inbox/<folder>" "what it is"` |

Sources are never changed. After a job succeeds, they move to `archive/`. On Windows, open `\\wsl.localhost\Ubuntu\home\<you>\video-studio\inbox` in File Explorer and pin it.

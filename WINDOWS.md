# Running on Windows (with WSL2)

Everything runs inside WSL2 (Ubuntu): the scripts, ffmpeg and Claude Code. This is the same Linux setup that CI tests on every pull request. You keep using Windows apps around it: VS Code to edit, File Explorer to drop videos in and pick up results, Windows Terminal for commands.

```
Windows                                   WSL2 (Ubuntu)
───────                                   ─────────────
File Explorer  ── drop videos ──►  ~/video-studio/inbox  ──► watcher (systemd) ──► out/
VS Code (WSL)  ── edits files ──►  ~/video-studio        ◄── claude (in the VS Code terminal)
                                         │
                                         └── git push / PR ──► GitHub (CI runs the render test)
```

## 1. Install WSL2 (once)

In PowerShell **as Administrator**:

```powershell
wsl --install -d Ubuntu
```

Restart Windows, open **Ubuntu** from the Start menu, and create a Linux username and password.

## 2. Install the tools (in Ubuntu)

```bash
sudo apt update
sudo apt install -y ffmpeg python3-venv python3-pip inotify-tools git gh
curl -fsSL https://claude.ai/install.sh | bash     # Claude Code, installs to ~/.local/bin
```

Close and reopen Ubuntu so `claude` is on your PATH.

## 3. Connect to GitHub (once)

```bash
gh auth login              # GitHub.com -> SSH -> generate a new key -> log in with the browser
git config --global user.name  "peteramiani6-source"
git config --global user.email "239789740+peteramiani6-source@users.noreply.github.com"
```

The no-reply address keeps your personal email out of the public commit history.

## 4. Get the project

Clone it into the Linux home folder, not `/mnt/c/...`. Files there are much faster to read and write, and file watching works.

```bash
cd ~
git clone git@github.com:peteramiani6-source/video-studio.git
cd video-studio
./setup.sh
claude             # log in with your Claude subscription once, then type /exit
nano .env          # optional: GROQ_API_KEY for fast transcription of long events
```

GitHub is the single source of truth. Don't keep editing an old copy under `C:\`. Delete it, or leave it alone.

## 5. Daily work: VS Code + Claude Code

Install the **WSL** extension in VS Code (`ms-vscode-remote.remote-wsl`). Then, from Ubuntu:

```bash
cd ~/video-studio && code .
```

VS Code opens on Windows, but it works directly on the Linux files. Its built-in terminal (`` Ctrl+` ``) is a Linux shell in the project folder. Run `claude` there and ask for things as usual ("process inbox/talk.mp4", "make the captions yellow").

`main` is protected. Changes go on a branch and through a pull request, and CI has to pass before you can merge. Claude Code handles that when you ask it to push.

**Windows Terminal shortcut (optional):** go to Settings → Ubuntu profile → Command line, and set it to:
`wsl.exe -d Ubuntu --cd ~/video-studio`. Every new Ubuntu tab then opens in the project.

## 6. Drop videos in and pick results up from File Explorer

Open these addresses in File Explorer and pin both to Quick Access (right-click → *Pin to Quick access*):

```
\\wsl.localhost\Ubuntu\home\<your-linux-user>\video-studio\inbox
\\wsl.localhost\Ubuntu\home\<your-linux-user>\video-studio\out
```

Drag recordings into `inbox`. With the watcher running (next step), the finished clips show up in `out\<job>\`.

## 7. Keep the watcher running

**Quick:** run `scripts/watch.sh` in a terminal and leave it open.

**Automatic (recommended):** let systemd inside WSL run it as a service.

1. Turn systemd on: run `sudo nano /etc/wsl.conf` and add:
   ```ini
   [boot]
   systemd=true
   ```
   Then run `wsl --shutdown` in PowerShell and open Ubuntu again.
2. Install the service:
   ```bash
   mkdir -p ~/.config/systemd/user
   cp ~/video-studio/deploy/video-studio.service ~/.config/systemd/user/
   systemctl --user daemon-reload
   systemctl --user enable --now video-studio
   loginctl enable-linger "$USER"
   ```
3. Check it: `systemctl --user status video-studio`. To follow the log, run `tail -f ~/video-studio/logs/pipeline.log`.

WSL stops when nothing is using it, and the watcher stops with it. To start WSL at login and keep it running, create a Task Scheduler task:
- **Trigger:** *At log on*
- **Action:** run program `wsl.exe` with the arguments `-d Ubuntu -e sleep infinity`
- **Settings:** under *Conditions*, untick *Start only if on AC power*; under *Settings*, untick *Stop the task if it runs longer than*

## 8. CPU-only settings (already set in config/models.env)

| Setting | Value | Why |
|---|---|---|
| `WHISPER_DEVICE` | `cpu` | No GPU |
| `WHISPER_MODEL` | `small` | Best accuracy for the speed on CPU. Use `base` if it's too slow |
| `WHISPER_BATCH` | `8` | Batched decoding, about 2–4× faster. Lower it to `4` if WSL runs out of memory |
| `WHISPER_LANGUAGE` | empty | Set it, e.g. to `en`, to skip language detection |
| `STT=groq` | optional | Transcribes on Groq's servers in seconds. Best for long recordings; needs `GROQ_API_KEY` |

The first local run downloads the Whisper model (about 500 MB for `small`).

## Troubleshooting

- **Transcription gets killed or WSL freezes:** WSL gets half your RAM by default. Create `C:\Users\<you>\.wslconfig` containing:
  ```ini
  [wsl2]
  memory=8GB
  ```
  then run `wsl --shutdown`. Or lower `WHISPER_BATCH`.
- **The watcher doesn't notice new files:** check that the project is in `~/video-studio`, not `/mnt/c/...`. Under `/mnt/c` it falls back to checking every 15 seconds.
- **`claude` not found in the service:** run `which claude`, and add that folder to `Environment=PATH` in `~/.config/systemd/user/video-studio.service`. Then run `systemctl --user daemon-reload && systemctl --user restart video-studio`.
- **Keep the laptop plugged in** for long renders.

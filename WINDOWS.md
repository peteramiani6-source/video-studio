# Running on Windows (no GPU)

Everything runs inside WSL2 (Ubuntu). Claude Code, ffmpeg and the scripts all work there unchanged.

## 1. Install WSL2 (once)

In PowerShell **as Administrator**:

```powershell
wsl --install -d Ubuntu
```

Restart Windows, open **Ubuntu** from the Start menu, and create a username and password.

## 2. Install the tools (in Ubuntu)

```bash
sudo apt update
sudo apt install -y ffmpeg python3-venv python3-pip inotify-tools unzip nodejs npm
sudo npm install -g @anthropic-ai/claude-code
claude          # sign in once, then exit
```

If `apt` gives you an old Node version (under 18), install Node through nvm instead.

## 3. Put the project in the Linux home folder

Use the Linux home folder rather than `C:\`. It's much faster, and file watching works there.

```bash
cd ~
cp /mnt/c/Users/<you>/Downloads/video-studio.zip .
unzip video-studio.zip && cd video-studio
./setup.sh
claude             # log in with your Claude subscription once, then type /exit
nano .env          # optional: GROQ_API_KEY for fast transcription of long events
```

## 4. Drop videos in from Windows

In File Explorer, open this address:

```
\\wsl$\Ubuntu\home\<your-linux-user>\video-studio\inbox
```

Pin it to Quick Access. Anything you drop there gets processed, and finished clips show up in `...\video-studio\out`.

## 5. CPU-only choices (already set in config/models.env)

| Setting | Value | Why |
|---|---|---|
| `WHISPER_DEVICE` | `cpu` | No GPU |
| `WHISPER_MODEL` | `small` | Best accuracy for the speed on CPU. Takes roughly as long as the recording, or a bit longer. Use `base` if it's too slow |
| `STT=groq` | optional | Transcribes on Groq's servers in seconds. Best for long podcasts, needs `GROQ_API_KEY` |
| encode preset | `faster` | Quicker renders on a laptop CPU |

The first local run downloads the Whisper model (~500 MB for `small`).

## 6. Keep it running

**While you work:** open Ubuntu and run `scripts/watch.sh`. Leave the window open.

**Auto-start at login (Task Scheduler):**
1. Open Task Scheduler and choose **Create Task**.
2. On the **Triggers** tab, set it to run *At log on*.
3. On the **Actions** tab, set the program to `wsl.exe` and the arguments to:
   `-d Ubuntu -e bash -lc "cd ~/video-studio && scripts/watch.sh"`
4. On the **Conditions** tab, untick *Start only if on AC power*.

Logs are in `~/video-studio/logs/pipeline.log`.

## Notes

- If the project lives under `/mnt/c/...`, the watcher switches to polling automatically, since inotify can't see changes made from Windows there. It's slower but still works.
- WSL shuts down when nothing's running in it. The Task Scheduler task above keeps it alive.
- Keep the laptop plugged in for long renders.

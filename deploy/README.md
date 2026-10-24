# deploy/

## `video-studio.service`

A systemd **user** service that keeps `scripts/watch.sh` running, so every video dropped into `inbox/` becomes captioned clips without you starting anything.

```bash
mkdir -p ~/.config/systemd/user
cp deploy/video-studio.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now video-studio
loginctl enable-linger "$USER"        # keep running when you're logged out
```

- **Check it:** `systemctl --user status video-studio`
- **Follow it:** `journalctl --user -u video-studio -f`, or `tail -f logs/pipeline.log`

The unit runs the watcher in `MODE=auto`: the pipeline runs on its own, and Claude Code is called only if a step fails. Edit `Environment=MODE=` to change that (`claude` or `direct`). If `claude` isn't found, add its folder (`which claude`) to `Environment=PATH`.

**On Windows (WSL2):** turn on systemd in WSL first, and keep WSL running at login. See [docs/WINDOWS.md](../docs/WINDOWS.md), step 7.

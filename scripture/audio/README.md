# scripture/audio/

Voiceovers, one per episode. The files themselves are not in git.

- `ep004_ai.wav` + `ep004_ai.json`: made by `scripts/scripture.sh voice ep004` (AI narrator + character). The `.json` holds the scene timing and a fingerprint of the script; don't edit it. Re-run `voice` after changing the words.
- `ep004.mp3`: your own recording (`voice ep004 --script` prints the lines). Set `"voiceover": "audio/ep004.mp3"` in the episode file.

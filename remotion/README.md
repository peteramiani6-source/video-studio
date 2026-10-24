# remotion/

Animation templates written in React and rendered to MP4 by [Remotion](https://www.remotion.dev). Right now there is one template, **ScriptureEpisode**, used by scripture mode. Add new templates here (promos, intros, animated lower-thirds) the same way.

```
remotion/
├── src/
│   ├── index.ts              entry point (registers the compositions)
│   ├── Root.tsx              the composition list + sample props for the preview
│   └── scripture/
│       ├── Episode.tsx       puts the scenes in sequence, plus progress bar, draft stamp and audio
│       ├── Scenes.tsx        hook, verse (word-by-word), reflection, live-it points, end card
│       ├── Background.tsx    slowly moving gradient, drifting lights, vignette
│       ├── fonts.ts          loads the bundled fonts before the first frame
│       └── types.ts          the props scripts/scripture.py passes in
├── public/
│   ├── fonts/                Cormorant Garamond + Inter (SIL Open Font License, licence files included)
│   └── jobs/                 temporary audio for the render in progress (not in git)
├── package.json              versions pinned (Remotion 4.0.533)
└── remotion.config.ts        codec and quality
```

## Setup

`setup.sh` runs this for you. To do it by hand:

```bash
cd remotion
npm ci
```

The first render downloads a headless Chrome. On a machine that already has one, point Remotion at it with `REMOTION_BROWSER=/path/to/chrome`.

## Preview and edit the design

```bash
cd remotion
npm run studio        # opens Remotion Studio in the browser with the sample episode
```

Change `src/scripture/Scenes.tsx` and the preview updates live. Brand colours and the series name come from `config/brand.json` → `scripture`, not from the code.

## How a render works

`scripts/scripture.py render <id>`:
1. reads the episode file and re-checks the verse against the bundled KJV
2. works out each scene's length from reading speed, or stretches the scenes to fit the voiceover
3. writes the props to `work/scripture-<id>/props_<format>.json` and copies the audio into `public/jobs/<id>/`
4. runs `npx remotion render src/index.ts ScriptureEpisode … --props=…`
5. normalises the loudness with FFmpeg and writes `out/scripture/<id>/`

## Licensing

Remotion is free for individuals and small companies; larger companies need a company licence. Check [remotion.dev/license](https://www.remotion.dev/license) if the channel becomes a business. The fonts are under the SIL Open Font License, which allows commercial use.

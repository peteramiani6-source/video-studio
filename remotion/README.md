# remotion/

Use this folder for videos generated from code, such as Mealsvo demos, animated explainers and promo clips. It's separate from the clipping pipeline.

## Set up once

```bash
cd remotion
npx create-video@latest .        # pick the blank or "Hello World" template
npx skills add remotion          # official skill so Claude Code writes correct Remotion code
npm run dev                      # preview in the browser
```

## Use it

Ask Claude Code from the repo root, for example: *"In remotion/, make a 20-second 1080x1920 Mealsvo promo:
logo intro, three feature cards, end screen with mealsvo.com."*

Render:

```bash
npx remotion render <CompositionId> ../out/remotion/<name>.mp4
```

You can also feed rendered clips from `out/` into a Remotion composition to add intros, outros or lower-thirds.

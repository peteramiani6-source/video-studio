# Shooting checklist

The pipeline can cut, colour, steady and caption footage. It can't fix focus, glare or a messy frame, so fix those on the day. It takes two minutes before you press record.

## Before recording
- **Clear the foreground.** Move chairs, bowls and bags out of the shot, or lower the camera so they drop out of frame.
- **Frame for vertical.** Clips are cropped to the centre third of a wide frame. Keep the person talking near the centre, not the phone or the tripod.
- **Mind the light.** Keep the sun behind the camera, not behind the people. Angle any on-screen phone away from the sky so it doesn't reflect glare.
- **Use a lapel mic.** Clip it on the guest. Phone mics pick up wind badly outdoors, and the wind filter only takes the edge off.

## While recording
- **Lock focus on the face.** Press and hold on the speaker's face until you see AE/AF lock. Otherwise the camera may focus on the phone in front.
- **Turn on stabilization** for any shot where you walk. Better still, stand still for each shot.
- **Hold each angle 6–8 seconds:** a wide shot, a close-up of the host and a close-up of the guest. Short, clean angles cut together well. Long wandering shots don't.
- **Get the ending:** a laugh, a handshake, a thank-you. A good last shot makes the edit.

## Behind-the-scenes clips
- Show the gear for **2–3 seconds** at most, then cut to the clean footage of the people.
- Start wide (the whole setup), go tight (faces), and end on a human moment.

## In the edit (config/brand.json)
- `look.contrast` / `look.saturation`: 1.08 / 1.25 by default, which brings back washed-out greens. Set both to 1 for no change.
- `look.stabilize`: `"off"`, `"deshake"` (quick) or `"vidstab"` (smoothest, similar to a 5% warp stabilizer, but about 5× slower to render).
- `look.wind_filter`: cuts low rumble below `wind_cutoff_hz` (100 Hz).
- `hook`: on screen for 1.5 s, bottom-centre just above the captions, with a shadow and outline. Set `"box": true` for the old boxed style.

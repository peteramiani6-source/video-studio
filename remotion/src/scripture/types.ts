// Props for one scripture episode. scripts/scripture.py builds these from scripture/episodes/<id>.json;
// the verse text always comes from the bundled KJV, never from a model.

import {CharacterColors} from '../character/Character';

export type SceneType = 'skit' | 'hook' | 'verse' | 'reflection' | 'apply' | 'end';

export type Scene = {type: SceneType; frames: number; index?: number}; // index: which skit beat

// One skit beat (see remotion/src/character/poses.ts for pose and face names)
export type Beat = {
  shot: 'wide' | 'closeup';
  bg: string; // a colour like "#FFFFFF", or "flash" to cycle the flash palette
  pose: string;
  face: string;
  caption: string;
  talk: boolean; // mouth moves
  thoughts: string[]; // words popping up around the head
};

export type Brand = {
  series: string; // shown on the end card
  handle: string; // e.g. "@oneversereallife", may be empty
  background: [string, string]; // two colours the animated background drifts between
  accent: string; // reference label, numbers, progress bar
  text: string; // main text colour
};

export type EpisodeProps = {
  width: number;
  height: number;
  fps: number;
  draft: boolean; // stamps DRAFT on screen (episode not reviewed yet)
  brand: Brand;
  hook: string;
  reference: string; // e.g. "Proverbs 3:5–6"
  verse: string; // exact KJV text
  reflection: string;
  apply: string[]; // 1-3 "live it" points
  applyStarts: number[]; // frame (inside the apply scene) where each point appears
  verseSpan?: number[]; // [start, end] frames (inside the verse scene) while the verse is read aloud; [] = default pacing
  mouth?: number[]; // per video frame: 0 closed, 1 half, 2 open (lip sync during talking skit beats); [] = none
  closing: string; // question on the end card
  scenes: Scene[]; // hook, verse, reflection, apply, end, with lengths in frames
  voiceover: string; // path under public/, or ""
  music: string; // path under public/, or ""
  musicVolume: number;
  skit: Beat[]; // optional comic opening; empty = start with the hook
  character: CharacterColors;
  flash: string[]; // background colours for "flash" beats
};

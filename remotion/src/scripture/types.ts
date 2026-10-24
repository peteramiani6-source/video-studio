// Props for one scripture episode. scripts/scripture.py builds these from scripture/episodes/<id>.json;
// the verse text always comes from the bundled KJV, never from a model.

export type SceneType = 'hook' | 'verse' | 'reflection' | 'apply' | 'end';

export type Scene = {type: SceneType; frames: number};

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
  closing: string; // question on the end card
  scenes: Scene[]; // hook, verse, reflection, apply, end, with lengths in frames
  voiceover: string; // path under public/, or ""
  music: string; // path under public/, or ""
  musicVolume: number;
};

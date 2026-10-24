import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {CharacterSheet} from './character/CharacterSheet';
import {ScriptureEpisode} from './scripture/Episode';
import {EpisodeProps} from './scripture/types';

// Sample props so `npm run studio` shows a working episode. Real renders pass --props from
// scripts/scripture.py, built from scripture/episodes/<id>.json.
const sample: EpisodeProps = {
  width: 1080,
  height: 1920,
  fps: 30,
  draft: false,
  brand: {series: 'One Verse, Real Life', handle: '', background: ['#0F1B2D', '#2B3A55'], accent: '#E8B04B', text: '#FFFFFF'},
  hook: "When you don't know what comes next",
  reference: 'Proverbs 3:5–6',
  verse:
    'Trust in the LORD with all thine heart; and lean not unto thine own understanding. In all thy ways acknowledge him, and he shall direct thy paths.',
  reflection:
    "You don't need the whole map to take the next step. Trust means bringing God into the decision, not only the outcome.",
  apply: ['Pray about one decision before you make it', 'Write down a time things worked out', 'Take the next small step today'],
  applyStarts: [0, 80, 160],
  closing: 'Which decision are you trusting God with?',
  scenes: [
    {type: 'hook', frames: 90},
    {type: 'verse', frames: 300},
    {type: 'reflection', frames: 210},
    {type: 'apply', frames: 270},
    {type: 'end', frames: 90},
  ],
  voiceover: '',
  music: '',
  musicVolume: 0.45,
  skit: [],
  verseSpan: [],
  mouth: [],
  character: {skin: '#A86B45', hoodie: '#E8B04B', line: '#1B1B1B', pants: '#2B3A55'},
  flash: ['#2B3A55', '#E76F51', '#8AB6A8', '#E8B04B'],
};

const metadata: CalculateMetadataFunction<EpisodeProps> = ({props}) => ({
  durationInFrames: props.scenes.reduce((n, s) => n + s.frames, 0),
  width: props.width,
  height: props.height,
  fps: props.fps,
});

export const Root: React.FC = () => (
  <>
  <Composition
    id="ScriptureEpisode"
    component={ScriptureEpisode}
    defaultProps={sample}
    calculateMetadata={metadata}
    durationInFrames={960}
    fps={30}
    width={1080}
    height={1920}
  />
  <Composition id="CharacterSheet" component={CharacterSheet} durationInFrames={1} fps={30} width={2280} height={1400} />
  </>
);

import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Character, CharacterColors, DEFAULT_COLORS} from './Character';
import {FACES, FaceName, POSES, PoseName} from './poses';
import {loadFonts, SANS} from '../scripture/fonts';

loadFonts();

// Every pose and face on one page: render a still of this to check the character after a change.
// npx remotion still src/index.ts CharacterSheet sheet.png
export const CharacterSheet: React.FC<{colors?: CharacterColors}> = ({colors = DEFAULT_COLORS}) => {
  const poses = Object.keys(POSES) as PoseName[];
  const faces = Object.keys(FACES) as FaceName[];
  const cell = (label: string, node: React.ReactNode) => (
    <div key={label} style={{width: 300, height: 420, display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
      <div style={{width: 260, height: 380}}>{node}</div>
      <div style={{fontFamily: SANS, fontSize: 24, fontWeight: 600, color: '#333'}}>{label}</div>
    </div>
  );
  return (
    <AbsoluteFill style={{background: '#FFFFFF', padding: 40, display: 'flex', flexWrap: 'wrap', alignContent: 'flex-start', gap: 10}}>
      {poses.map((p) => cell(`pose: ${p}`, <Character pose={p} face={p === 'pray' ? 'peace' : 'neutral'} colors={colors} blinkSeed={1} />))}
      {faces.map((f) => cell(`face: ${f}`, <Character pose="idle" face={f} colors={colors} blinkSeed={1} />))}
    </AbsoluteFill>
  );
};

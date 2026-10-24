import React from 'react';
import {AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Character, CharacterColors} from '../character/Character';
import {FaceName, PoseName} from '../character/poses';
import {COMIC} from './fonts';
import {Beat} from './types';

// One skit beat: a short comic moment with the channel's character before the verse.
// Hard cuts between beats (no fades), a camera "pop" at each cut, and flat or flashing backgrounds.

const isDark = (hex: string) => {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.45;
};

export const SkitScene: React.FC<{beat: Beat; prev?: Beat; colors: CharacterColors; flash: string[]; seed: number; mouth?: number[]}> = ({
  beat,
  prev,
  colors,
  flash,
  seed,
  mouth,
}) => {
  const frame = useCurrentFrame();
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const k = Math.min(width, height) / 1080;

  const bg = beat.bg === 'flash' ? flash[Math.floor(frame / 5) % flash.length] : beat.bg;
  const dark = isDark(bg);
  const pop = spring({frame, fps, config: {damping: 14, mass: 0.5}, durationInFrames: 10});
  const camera = interpolate(pop, [0, 1], [1.07, 1]) * interpolate(frame, [0, durationInFrames], [1, beat.shot === 'closeup' ? 1.04 : 1.015]);
  const sameShot = prev && prev.shot === beat.shot;
  const transition = prev ? spring({frame, fps, config: {damping: 200}, durationInFrames: 8}) : 1;

  const lying = beat.pose === 'lying';
  // character box: 400 x 600 units
  const boxH = beat.shot === 'closeup' ? width * 2.16 : height * 0.5;
  const boxW = (boxH * 400) / 600;
  const top = beat.shot === 'closeup' ? height * 0.5 - boxH * 0.25 : height * 0.84 - boxH;
  const shake = beat.bg === 'flash' ? (random(`s${seed}-${frame}`) - 0.5) * 10 * k : 0;

  const character = (
    <Character
      pose={beat.pose as PoseName}
      fromPose={sameShot ? (prev!.pose as PoseName) : undefined}
      transition={sameShot ? transition : 1}
      face={beat.face as FaceName}
      talking={beat.talk}
      mouthLevels={mouth}
      colors={colors}
      blinkSeed={seed}
    />
  );

  return (
    <AbsoluteFill style={{background: bg, overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `scale(${camera}) translateX(${shake}px)`, transformOrigin: '50% 45%'}}>
        {lying ? (
          <Bed width={width} height={height} colors={colors}>
            {character}
          </Bed>
        ) : (
          <div style={{position: 'absolute', left: (width - boxW) / 2, top, width: boxW, height: boxH}}>{character}</div>
        )}
        {beat.thoughts?.length ? <Thoughts words={beat.thoughts} dark={dark} seed={seed} /> : null}
      </AbsoluteFill>
      {beat.caption ? <Caption text={beat.caption} dark={dark} k={k} /> : null}
    </AbsoluteFill>
  );
};

const Caption: React.FC<{text: string; dark: boolean; k: number}> = ({text, dark, k}) => {
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const words = text.split(/\s+/);
  const size = (text.length > 26 ? 70 : 88) * k;
  return (
    <div style={{position: 'absolute', top: height * 0.11, left: '6%', right: '6%', textAlign: 'center', fontFamily: COMIC,
      fontWeight: 700, fontSize: size, lineHeight: 1.15, textTransform: 'uppercase', letterSpacing: '0.02em',
      color: dark ? '#FFFFFF' : '#1B1B1B', textShadow: dark ? '0 4px 0 rgba(0,0,0,0.35)' : 'none'}}>
      {words.map((w, i) => {
        const s = spring({frame: frame - i * 2, fps, config: {damping: 12, mass: 0.4}});
        return (
          <span key={i} style={{display: 'inline-block', marginRight: '0.3em', transform: `scale(${0.4 + 0.6 * s})`, opacity: Math.min(1, s * 2)}}>
            {w}
          </span>
        );
      })}
    </div>
  );
};

// Worries (or any words) popping up around the character's head, faster and faster.
const Thoughts: React.FC<{words: string[]; dark: boolean; seed: number}> = ({words, dark, seed}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const k = Math.min(width, height) / 1080;
  return (
    <>
      {words.map((w, i) => {
        const start = Math.round(18 * Math.pow(i, 0.8));
        const s = spring({frame: frame - start, fps, config: {damping: 10, mass: 0.4}});
        // spread over the sides and top only (left -> over the head -> right), never across the body
        const angle = Math.PI * (1.08 - (1.16 * (i + random(`t${seed}${i}`) * 0.6)) / Math.max(1, words.length - 0.4));
        const r = (0.28 + random(`r${seed}${i}`) * 0.1) * width;
        const x = width / 2 + Math.cos(angle) * r;
        const y = height * 0.44 - Math.abs(Math.sin(angle)) * r * 0.9;
        const jitter = Math.sin(frame * 1.7 + i) * 3;
        return (
          <div key={i} style={{position: 'absolute', left: x, top: y + jitter, transform: `translate(-50%, -50%) scale(${s}) rotate(${(random(`a${seed}${i}`) - 0.5) * 24}deg)`,
            fontFamily: COMIC, fontWeight: 700, fontSize: 58 * k, textTransform: 'uppercase', whiteSpace: 'nowrap',
            color: dark ? '#FFFFFF' : '#1B1B1B', opacity: 0.9}}>
            {w}
          </div>
        );
      })}
    </>
  );
};

// A simple bed, with the character lying on it (rotated) under a blanket.
const Bed: React.FC<{width: number; height: number; colors: CharacterColors; children: React.ReactNode}> = ({width, height, colors, children}) => {
  const bedW = width * 0.86;
  const bedX = (width - bedW) / 2;
  const bedY = height * 0.58;
  const line = colors.line;
  const charH = bedW * 0.95; // character length when lying down
  const charW = (charH * 400) / 600;
  return (
    <>
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        {/* headboard + legs + mattress */}
        <rect x={bedX - 10} y={bedY - 170} width={36} height={300} rx={10} fill="#8C6A4F" stroke={line} strokeWidth={7} />
        <rect x={bedX} y={bedY} width={bedW} height={70} rx={14} fill="#FFFFFF" stroke={line} strokeWidth={7} />
        <rect x={bedX} y={bedY + 70} width={bedW} height={40} fill="#8C6A4F" stroke={line} strokeWidth={7} />
        <path d={`M${bedX + 20} ${bedY + 110} v50 M${bedX + bedW - 20} ${bedY + 110} v50`} stroke={line} strokeWidth={9} strokeLinecap="round" />
        <rect x={bedX + 30} y={bedY - 64} width={190} height={74} rx={34} fill="#FFFFFF" stroke={line} strokeWidth={7} />
      </svg>
      <div style={{position: 'absolute', width: charW, height: charH, left: bedX + bedW * 0.5 - charW / 2 - bedW * 0.04,
        top: bedY - charH / 2 - charW * 0.12, transform: 'rotate(-90deg)'}}>
        {children}
      </div>
      <svg width={width} height={height} style={{position: 'absolute', inset: 0}}>
        {/* blanket over everything below the shoulders */}
        <path d={`M${bedX + bedW * 0.25} ${bedY - 120} Q${bedX + bedW * 0.6} ${bedY - 175} ${bedX + bedW - 6} ${bedY - 135}
          L${bedX + bedW - 6} ${bedY + 66} L${bedX + bedW * 0.22} ${bedY + 66} Z`} fill="#5B7DB1" stroke={line} strokeWidth={7} strokeLinejoin="round" />
        <path d={`M${bedX + bedW * 0.42} ${bedY - 120} q30 60 0 170 M${bedX + bedW * 0.64} ${bedY - 130} q30 70 0 185`} fill="none"
          stroke={line} strokeWidth={4} opacity={0.3} />
      </svg>
    </>
  );
};

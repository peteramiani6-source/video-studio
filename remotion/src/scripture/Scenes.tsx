import React from 'react';
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {hexA} from './Background';
import {Character, CharacterColors} from '../character/Character';
import {SANS, SERIF} from './fonts';
import {Brand} from './types';

const FADE = 10; // frames of cross-fade at the start and end of every scene

// Fades a whole scene in and out so scene changes never hard-cut.
export const SceneFade: React.FC<{children: React.ReactNode}> = ({children}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const opacity = interpolate(frame, [0, FADE, durationInFrames - FADE, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

// Text area: generous side margins, and on vertical video it stays clear of the bottom
// fifth where Reels/TikTok put their buttons and captions.
export const Safe: React.FC<{children: React.ReactNode; align?: 'center' | 'flex-start'}> = ({children, align = 'center'}) => {
  const {width, height} = useVideoConfig();
  const vertical = height > width;
  return (
    <AbsoluteFill
      style={{
        padding: vertical ? `${height * 0.12}px ${width * 0.09}px ${height * 0.22}px` : `${height * 0.1}px ${width * 0.12}px`,
        justifyContent: 'center',
        alignItems: align,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {children}
    </AbsoluteFill>
  );
};

const useScale = () => {
  const {width, height} = useVideoConfig();
  return Math.min(width, height) / 1080; // 1 at 1080 wide (vertical) or 1080 tall (wide)
};

const rise = (frame: number, start: number, fps: number) => {
  const s = spring({frame: frame - start, fps, config: {damping: 200}, durationInFrames: 18});
  return {opacity: s, transform: `translateY(${(1 - s) * 30}px)`};
};

export const HookScene: React.FC<{text: string; brand: Brand}> = ({text, brand}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = useScale();
  const words = text.split(/\s+/);
  const size = (text.length > 45 ? 78 : 92) * k;
  return (
    <Safe>
      <div style={{fontFamily: SANS, fontWeight: 800, fontSize: size, lineHeight: 1.15, color: brand.text, textAlign: 'center',
        textShadow: '0 4px 24px rgba(0,0,0,0.45)'}}>
        {words.map((w, i) => {
          const s = spring({frame: frame - 4 - i * 3, fps, config: {damping: 14, mass: 0.6}});
          return (
            <span key={i} style={{display: 'inline-block', marginRight: '0.28em', opacity: Math.min(1, s * 1.4),
              transform: `scale(${0.7 + 0.3 * s})`}}>
              {w}
            </span>
          );
        })}
      </div>
    </Safe>
  );
};

export const VerseScene: React.FC<{reference: string; verse: string; brand: Brand; span?: number[]}> = ({reference, verse, brand, span}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const k = useScale();
  const words = verse.split(/\s+/);
  // all words are in by 70% of the scene; the rest is a hold so the verse can be read in full
  const step = Math.max(1, (durationInFrames * 0.7 - 20) / words.length);
  // with a voiceover, each word appears as it is read (spread by length across the spoken span)
  const chars = words.map((w) => w.length + 1);
  const total = chars.reduce((a, b) => a + b, 0);
  const wordStart = (i: number) =>
    span && span.length === 2
      ? span[0] - 4 + ((span[1] - span[0]) * chars.slice(0, i).reduce((a, b) => a + b, 0)) / total
      : 12 + i * step;
  const size = Math.max(56, Math.min(96, 112 - verse.length * 0.24)) * k;
  const lineW = interpolate(frame, [0, 24], [0, 140 * k], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  return (
    <Safe>
      <div style={{...rise(frame, 0, fps), fontFamily: SANS, fontWeight: 700, letterSpacing: '0.22em',
        fontSize: 30 * k, color: brand.accent, textTransform: 'uppercase', textAlign: 'center'}}>
        {reference}
      </div>
      <div style={{width: lineW, height: 3 * k, background: brand.accent, margin: `${22 * k}px auto ${34 * k}px`, borderRadius: 2}} />
      <div style={{fontFamily: SERIF, fontStyle: 'italic', fontWeight: 500, fontSize: size, lineHeight: 1.28,
        color: brand.text, textAlign: 'center', textShadow: '0 3px 18px rgba(0,0,0,0.5)'}}>
        <span style={{color: brand.accent}}>&ldquo;</span>
        {words.map((w, i) => {
          const t = interpolate(frame, [wordStart(i), wordStart(i) + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
          const last = i === words.length - 1;
          return (
            <span key={i} style={{opacity: t, display: 'inline-block', marginRight: last ? 0 : '0.25em',
              transform: `translateY(${(1 - t) * 14}px)`, filter: `blur(${(1 - t) * 4}px)`}}>
              {w}
              {last ? <span style={{color: brand.accent}}>&rdquo;</span> : null}
            </span>
          );
        })}
      </div>
      <div style={{marginTop: 30 * k, fontFamily: SANS, fontSize: 24 * k, letterSpacing: '0.18em', color: hexA(brand.text, 0.55),
        opacity: interpolate(frame, [durationInFrames * 0.6, durationInFrames * 0.6 + 15], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
        KJV
      </div>
    </Safe>
  );
};

export const ReflectionScene: React.FC<{text: string; brand: Brand}> = ({text, brand}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const k = useScale();
  const sentences = text.match(/[^.!?]+[.!?]*["”’]?/g)?.map((s) => s.trim()).filter(Boolean) ?? [text];
  const gap = Math.max(8, (durationInFrames * 0.55) / sentences.length);
  return (
    <Safe>
      <div style={{fontFamily: SANS, fontWeight: 700, letterSpacing: '0.22em', fontSize: 28 * k, color: brand.accent,
        textTransform: 'uppercase', marginBottom: 34 * k, ...rise(frame, 0, fps)}}>
        What it means today
      </div>
      <div style={{textAlign: 'center'}}>
        {sentences.map((s, i) => (
          <div key={i} style={{...rise(frame, 8 + i * gap, fps), fontFamily: SANS, fontWeight: 500, fontSize: 58 * k,
            lineHeight: 1.35, color: brand.text, marginBottom: 18 * k, textShadow: '0 3px 16px rgba(0,0,0,0.45)'}}>
            {s}
          </div>
        ))}
      </div>
    </Safe>
  );
};

export const ApplyScene: React.FC<{items: string[]; starts: number[]; brand: Brand}> = ({items, starts, brand}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = useScale();
  return (
    <Safe>
      <div style={{fontFamily: SANS, fontWeight: 700, letterSpacing: '0.22em', fontSize: 28 * k, color: brand.accent,
        textTransform: 'uppercase', marginBottom: 44 * k, ...rise(frame, 0, fps), alignSelf: 'center'}}>
        Live it this week
      </div>
      <div style={{display: 'flex', flexDirection: 'column', gap: 34 * k, width: '100%'}}>
        {items.map((item, i) => {
          const start = 10 + (starts[i] ?? i * 60);
          const s = spring({frame: frame - start, fps, config: {damping: 200}, durationInFrames: 20});
          const current = i === items.length - 1 || frame < 10 + (starts[i + 1] ?? Infinity);
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', gap: 28 * k, opacity: s * (current ? 1 : 0.6),
              transform: `translateX(${(1 - s) * -60}px)`}}>
              <div style={{flex: 'none', width: 74 * k, height: 74 * k, borderRadius: '50%', background: brand.accent,
                color: brand.background[0], fontFamily: SANS, fontWeight: 800, fontSize: 38 * k, display: 'flex',
                alignItems: 'center', justifyContent: 'center'}}>
                {i + 1}
              </div>
              <div style={{fontFamily: SANS, fontWeight: 600, fontSize: 46 * k, lineHeight: 1.25, color: brand.text,
                textShadow: '0 3px 16px rgba(0,0,0,0.45)'}}>
                {item}
              </div>
            </div>
          );
        })}
      </div>
    </Safe>
  );
};

export const EndScene: React.FC<{closing: string; brand: Brand; character?: CharacterColors}> = ({closing, brand, character}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const k = useScale();
  return (
    <Safe>
      {character ? (
        <div style={{width: 220 * k, height: 330 * k, marginBottom: 30 * k, ...rise(frame, 0, fps)}}>
          <Character pose="wave" face="happy" colors={character} />
        </div>
      ) : null}
      {closing ? (
        <div style={{...rise(frame, 0, fps), fontFamily: SANS, fontWeight: 600, fontSize: 54 * k, lineHeight: 1.3,
          color: brand.text, textAlign: 'center', marginBottom: 60 * k}}>
          {closing}
        </div>
      ) : null}
      <div style={{...rise(frame, 12, fps), fontFamily: SERIF, fontStyle: 'italic', fontWeight: 600, fontSize: 76 * k,
        color: brand.accent, textAlign: 'center'}}>
        {brand.series}
      </div>
      {brand.handle ? (
        <div style={{...rise(frame, 20, fps), marginTop: 18 * k, fontFamily: SANS, fontWeight: 600, fontSize: 32 * k,
          letterSpacing: '0.08em', color: hexA(brand.text, 0.8)}}>
          {brand.handle}
        </div>
      ) : null}
    </Safe>
  );
};

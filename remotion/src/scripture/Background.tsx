import React from 'react';
import {AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig} from 'remotion';
import {Brand} from './types';

// Calm moving background: a slowly turning gradient between the two brand colours,
// soft drifting lights, and a vignette that keeps the text area readable.
const LIGHTS = 14;

export const Background: React.FC<{brand: Brand}> = ({brand}) => {
  const frame = useCurrentFrame();
  const {width, height, durationInFrames} = useVideoConfig();
  const [c1, c2] = brand.background;
  const angle = 160 + 40 * Math.sin(frame / 240);
  const zoom = interpolate(frame, [0, durationInFrames], [1, 1.08]);
  const size = Math.max(width, height);

  return (
    <AbsoluteFill style={{background: `linear-gradient(${angle}deg, ${c1} 0%, ${c2} 100%)`, overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `scale(${zoom})`}}>
        {new Array(LIGHTS).fill(0).map((_, i) => {
          const seed = `light-${i}`;
          const r = (0.12 + random(seed + 'r') * 0.28) * size;
          const x = random(seed + 'x') * width + Math.sin(frame / (90 + i * 7) + i) * 40;
          const y = random(seed + 'y') * height + Math.cos(frame / (110 + i * 5) + i) * 50 - frame * (0.15 + random(seed + 's') * 0.25);
          const alpha = 0.08 + random(seed + 'a') * 0.14;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: x - r / 2,
                top: ((y % (height + r)) + height + r) % (height + r) - r / 2,
                width: r,
                height: r,
                borderRadius: '50%',
                background: `radial-gradient(circle, ${hexA(brand.accent, alpha)} 0%, transparent 70%)`,
              }}
            />
          );
        })}
      </AbsoluteFill>
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.55) 100%)'}} />
    </AbsoluteFill>
  );
};

// "#E8B04B" + 0.1 -> "rgba(232,176,75,0.1)"
export const hexA = (hex: string, a: number) => {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

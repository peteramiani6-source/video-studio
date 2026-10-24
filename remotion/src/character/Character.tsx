import React from 'react';
import {useCurrentFrame} from 'remotion';
import {ARM, blendPose, elbow, Eyes, FACES, FaceName, Mouth, POSES, Point, PoseName} from './poses';

// The channel's own character: a simple, original design (round face, hoodie in the brand colour,
// one curl of hair). Drawn as SVG in a 400 x 600 box so it stays crisp at any size.

export type CharacterColors = {
  skin: string;
  hoodie: string;
  line: string; // outline / features
  pants: string;
};

export const DEFAULT_COLORS: CharacterColors = {skin: '#A86B45', hoodie: '#E8B04B', line: '#1B1B1B', pants: '#2B3A55'};

type Props = {
  pose: PoseName;
  fromPose?: PoseName; // previous pose, for a smooth transition into this one
  transition?: number; // 0..1 progress from fromPose to pose
  face: FaceName;
  talking?: boolean;
  colors?: CharacterColors;
  blinkSeed?: number;
  mouthLevels?: number[]; // lip sync: per frame 0 closed, 1 half, 2 open (overrides the talking loop)
};

const W = 7; // line width

export const Character: React.FC<Props> = ({pose, fromPose, transition = 1, face, talking = false, colors = DEFAULT_COLORS, blinkSeed = 0, mouthLevels}) => {
  const frame = useCurrentFrame();
  const p = blendPose(POSES[fromPose ?? pose], POSES[pose], transition);
  const {eyes, mouth} = FACES[face];

  // life: breathing, blinking, a little bob while talking, waving hand
  const breathe = Math.sin(frame / 14) * 2.5;
  const blinking = (frame + blinkSeed * 37) % 96 < 4 && (eyes === 'dot' || eyes === 'wide' || eyes === 'worried');
  const level = mouthLevels?.length ? mouthLevels[Math.min(frame, mouthLevels.length - 1)] ?? 0 : -1;
  const mouthNow: Mouth = !talking ? mouth : level >= 0 ? (level === 2 ? 'open' : level === 1 ? 'half' : mouth)
    : Math.floor(frame / 4) % 2 === 0 ? 'open' : mouth;
  const speaking = talking && (level < 0 || level > 0);
  const wave = pose === 'wave' ? Math.sin(frame / 3) * 18 : 0;
  const talkBob = speaking ? Math.sin(frame / 2.5) * 6 : 0;

  const rh: Point = [p.rh[0] + wave, p.rh[1] + (pose === 'talk' ? talkBob : 0)];
  const L = elbow(ARM.ls, p.lh, 'l');
  const R = elbow(ARM.rs, rh, 'r');
  const kneel = p.legs === 'kneel';
  const hideArms = pose === 'lying'; // tucked under the blanket
  const raisedL = L.h[1] < 250;
  const raisedR = R.h[1] < 250;
  const arm = (a: {e: Point; h: Point}) => {
    const s = a === L ? ARM.ls : ARM.rs;
    return (
      <g>
        <polyline points={`${s[0]},${s[1]} ${a.e[0]},${a.e[1]} ${a.h[0]},${a.h[1]}`} fill="none" stroke={colors.line}
          strokeWidth={W} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={a.h[0]} cy={a.h[1]} r={11} fill={colors.skin} stroke={colors.line} strokeWidth={5} />
      </g>
    );
  };

  return (
    <svg viewBox="0 0 400 600" width="100%" height="100%" style={{overflow: 'visible'}}>
      <g transform={`translate(0 ${p.bodyDrop})`}>
        {/* legs */}
        {kneel ? (
          <g stroke={colors.line} strokeWidth={W} strokeLinecap="round" fill="none">
            <path d="M172 430 L150 470 L190 498" />
            <path d="M228 430 L250 470 L210 498" />
          </g>
        ) : (
          <g stroke={colors.line} strokeWidth={W} strokeLinecap="round" fill="none">
            <path d="M176 430 L172 556 L150 560" />
            <path d="M224 430 L228 556 L250 560" />
          </g>
        )}
        {/* body: hoodie */}
        <g transform={`translate(0 ${-breathe * 0.4})`}>
          <path
            d={`M150 270 Q200 ${250 - breathe} 250 270 L272 436 Q200 ${450 + breathe * 0.3} 128 436 Z`}
            fill={colors.hoodie}
            stroke={colors.line}
            strokeWidth={W}
            strokeLinejoin="round"
          />
          {/* hoodie pocket + drawstrings */}
          <path d="M168 372 L232 372 L240 412 L160 412 Z" fill="none" stroke={colors.line} strokeWidth={4} opacity={0.35} />
          <path d="M190 262 L186 300 M210 262 L214 300" stroke={colors.line} strokeWidth={4} strokeLinecap="round" />
        </g>
        {/* arms with the hand below the neck go behind the head; raised hands (face, head) go in front */}
        {!raisedL && !hideArms ? arm(L) : null}
        {!raisedR && !hideArms ? arm(R) : null}
        {/* head */}
        <g transform={`rotate(${p.headTilt} 200 240) translate(0 ${-breathe * 0.6})`}>
          {/* hood behind the head */}
          <path d="M108 180 Q110 66 200 58 Q290 66 292 180 Q280 250 200 262 Q120 250 108 180 Z" fill={colors.hoodie} stroke={colors.line} strokeWidth={W} />
          <circle cx={200} cy={150} r={86} fill={colors.skin} stroke={colors.line} strokeWidth={W} />
          {/* the curl */}
          <path d="M196 66 q-14 -26 8 -34 q20 -6 16 14 q-4 14 -16 8" fill="none" stroke={colors.line} strokeWidth={6} strokeLinecap="round" />
          <EyesShape kind={blinking ? 'closed' : eyes} line={colors.line} />
          <MouthShape kind={mouthNow} line={colors.line} />
        </g>
        {raisedL && !hideArms ? arm(L) : null}
        {raisedR && !hideArms ? arm(R) : null}
      </g>
    </svg>
  );
};

const EyesShape: React.FC<{kind: Eyes; line: string}> = ({kind, line}) => {
  const L = 168;
  const R = 232;
  const y = 145;
  switch (kind) {
    case 'wide':
      return (
        <g>
          {[L, R].map((x) => (
            <g key={x}>
              <circle cx={x} cy={y} r={18} fill="#FFFFFF" stroke={line} strokeWidth={5} />
              <circle cx={x} cy={y + 2} r={7} fill={line} />
            </g>
          ))}
        </g>
      );
    case 'closed':
      return <path d={`M${L - 14} ${y} q14 10 28 0 M${R - 14} ${y} q14 10 28 0`} fill="none" stroke={line} strokeWidth={5} strokeLinecap="round" />;
    case 'happy':
      return <path d={`M${L - 14} ${y + 4} q14 -16 28 0 M${R - 14} ${y + 4} q14 -16 28 0`} fill="none" stroke={line} strokeWidth={5} strokeLinecap="round" />;
    case 'deadpan':
      return (
        <g stroke={line} strokeWidth={5} strokeLinecap="round">
          <path d={`M${L - 16} ${y - 4} L${L + 16} ${y - 4} M${R - 16} ${y - 4} L${R + 16} ${y - 4}`} />
          <circle cx={L + 2} cy={y + 6} r={4} fill={line} />
          <circle cx={R + 2} cy={y + 6} r={4} fill={line} />
        </g>
      );
    case 'worried':
      return (
        <g stroke={line} strokeWidth={5} strokeLinecap="round" fill={line}>
          <path d={`M${L - 16} ${y - 20} L${L + 12} ${y - 28} M${R + 16} ${y - 20} L${R - 12} ${y - 28}`} fill="none" />
          <circle cx={L} cy={y} r={6} />
          <circle cx={R} cy={y} r={6} />
        </g>
      );
    default:
      return (
        <g fill={line}>
          <circle cx={L} cy={y} r={7} />
          <circle cx={R} cy={y} r={7} />
        </g>
      );
  }
};

const MouthShape: React.FC<{kind: Mouth; line: string}> = ({kind, line}) => {
  const y = 194;
  switch (kind) {
    case 'open':
      return <ellipse cx={200} cy={y} rx={16} ry={13} fill={line} />;
    case 'half':
      return <ellipse cx={200} cy={y} rx={14} ry={6} fill={line} />;
    case 'smile':
      return <path d={`M178 ${y - 4} q22 20 44 0`} fill="none" stroke={line} strokeWidth={5} strokeLinecap="round" />;
    case 'grin':
      return <path d={`M174 ${y - 8} q26 34 52 0 Z`} fill={line} stroke={line} strokeWidth={4} strokeLinejoin="round" />;
    case 'o':
      return <circle cx={200} cy={y + 2} r={9} fill="none" stroke={line} strokeWidth={5} />;
    case 'flat':
      return <path d={`M186 ${y} L214 ${y}`} stroke={line} strokeWidth={5} strokeLinecap="round" />;
    case 'wavy':
      return <path d={`M178 ${y} q7 -8 14 0 q7 8 14 0 q7 -8 14 0`} fill="none" stroke={line} strokeWidth={5} strokeLinecap="round" />;
    default:
      return <path d={`M184 ${y} q16 4 32 0`} fill="none" stroke={line} strokeWidth={5} strokeLinecap="round" />;
  }
};

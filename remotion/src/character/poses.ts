// Poses and faces for the channel's character. Everything is in the character's own 400 x 600
// coordinate box (head centre 200,150). A pose is just where the hands go (arms bend on their own
// via 2-bone IK), plus a few body adjustments. Add a pose here and it can be used in any skit.

export type Point = [number, number];

export type Pose = {
  lh: Point; // left hand target (viewer's left)
  rh: Point; // right hand target
  legs: 'stand' | 'kneel';
  headTilt: number; // degrees, + = towards viewer's right
  bodyDrop: number; // move the whole figure down (kneeling)
};

export const POSES = {
  idle: {lh: [142, 418], rh: [258, 418], legs: 'stand', headTilt: 0, bodyDrop: 0},
  talk: {lh: [142, 418], rh: [312, 300], legs: 'stand', headTilt: -3, bodyDrop: 0},
  shrug: {lh: [92, 262], rh: [308, 262], legs: 'stand', headTilt: 8, bodyDrop: 0},
  think: {lh: [196, 352], rh: [212, 236], legs: 'stand', headTilt: -6, bodyDrop: 0},
  facepalm: {lh: [150, 410], rh: [214, 160], legs: 'stand', headTilt: 10, bodyDrop: 0},
  panic: {lh: [116, 150], rh: [284, 150], legs: 'stand', headTilt: 0, bodyDrop: 0},
  pray: {lh: [194, 300], rh: [206, 300], legs: 'kneel', headTilt: 4, bodyDrop: 70},
  laugh: {lh: [178, 368], rh: [222, 368], legs: 'stand', headTilt: -10, bodyDrop: 0},
  wave: {lh: [142, 418], rh: [306, 168], legs: 'stand', headTilt: 4, bodyDrop: 0},
  lying: {lh: [150, 400], rh: [250, 400], legs: 'stand', headTilt: 0, bodyDrop: 0},
} satisfies Record<string, Pose>;

export type PoseName = keyof typeof POSES;

export type Eyes = 'dot' | 'wide' | 'closed' | 'deadpan' | 'happy' | 'worried';
export type Mouth = 'line' | 'open' | 'half' | 'smile' | 'o' | 'flat' | 'wavy' | 'grin';

export const FACES = {
  neutral: {eyes: 'dot', mouth: 'line'},
  deadpan: {eyes: 'deadpan', mouth: 'flat'},
  wide: {eyes: 'wide', mouth: 'o'},
  worried: {eyes: 'worried', mouth: 'wavy'},
  happy: {eyes: 'happy', mouth: 'smile'},
  peace: {eyes: 'closed', mouth: 'smile'},
  laugh: {eyes: 'happy', mouth: 'grin'},
} satisfies Record<string, {eyes: Eyes; mouth: Mouth}>;

export type FaceName = keyof typeof FACES;

// Upper arm and forearm lengths, shoulder positions
export const ARM = {upper: 78, lower: 72, ls: [152, 282] as Point, rs: [248, 282] as Point};

/** Elbow position for a 2-bone arm reaching from shoulder s to hand t; the elbow bends outward. */
export const elbow = (s: Point, t: Point, side: 'l' | 'r'): {e: Point; h: Point} => {
  const a = ARM.upper;
  const b = ARM.lower;
  let dx = t[0] - s[0];
  let dy = t[1] - s[1];
  let d = Math.hypot(dx, dy) || 1;
  const maxD = a + b - 1;
  const minD = Math.abs(a - b) + 1;
  if (d > maxD || d < minD) {
    const k = Math.min(maxD, Math.max(minD, d)) / d;
    dx *= k;
    dy *= k;
    d = Math.hypot(dx, dy);
  }
  const base = Math.atan2(dy, dx);
  const off = Math.acos(Math.min(1, Math.max(-1, (a * a + d * d - b * b) / (2 * a * d))));
  const c1: Point = [s[0] + a * Math.cos(base + off), s[1] + a * Math.sin(base + off)];
  const c2: Point = [s[0] + a * Math.cos(base - off), s[1] + a * Math.sin(base - off)];
  const e = side === 'l' ? (c1[0] < c2[0] ? c1 : c2) : c1[0] > c2[0] ? c1 : c2;
  return {e, h: [s[0] + dx, s[1] + dy]};
};

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const lerpPoint = (a: Point, b: Point, t: number): Point => [lerp(a[0], b[0], t), lerp(a[1], b[1], t)];

/** Blend two poses (t = 0 -> a, 1 -> b) for smooth transitions between skit beats. */
export const blendPose = (a: Pose, b: Pose, t: number): Pose => ({
  lh: lerpPoint(a.lh, b.lh, t),
  rh: lerpPoint(a.rh, b.rh, t),
  legs: t < 0.5 ? a.legs : b.legs,
  headTilt: lerp(a.headTilt, b.headTilt, t),
  bodyDrop: lerp(a.bodyDrop, b.bodyDrop, t),
});

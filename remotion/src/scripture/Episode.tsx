import React from 'react';
import {AbsoluteFill, Audio, interpolate, Series, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Background} from './Background';
import {loadFonts, SANS} from './fonts';
import {ApplyScene, EndScene, HookScene, ReflectionScene, SceneFade, VerseScene} from './Scenes';
import {EpisodeProps, Scene} from './types';

loadFonts();

const sceneBody = (scene: Scene, p: EpisodeProps) => {
  switch (scene.type) {
    case 'hook':
      return <HookScene text={p.hook} brand={p.brand} />;
    case 'verse':
      return <VerseScene reference={p.reference} verse={p.verse} brand={p.brand} />;
    case 'reflection':
      return <ReflectionScene text={p.reflection} brand={p.brand} />;
    case 'apply':
      return <ApplyScene items={p.apply} starts={p.applyStarts} brand={p.brand} />;
    case 'end':
      return <EndScene closing={p.closing} brand={p.brand} />;
  }
};

const Progress: React.FC<{color: string}> = ({color}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width, height} = useVideoConfig();
  const h = Math.max(4, Math.round(Math.min(width, height) / 270));
  return (
    <div style={{position: 'absolute', left: 0, bottom: 0, height: h, width: `${(frame / durationInFrames) * 100}%`,
      background: color, opacity: 0.85}} />
  );
};

const DraftStamp: React.FC = () => (
  <div style={{position: 'absolute', top: 30, right: 30, padding: '10px 18px', borderRadius: 8,
    background: 'rgba(200,30,30,0.85)', color: 'white', fontFamily: SANS, fontWeight: 800, fontSize: 28,
    letterSpacing: '0.1em'}}>
    DRAFT · NOT REVIEWED
  </div>
);

export const ScriptureEpisode: React.FC<EpisodeProps> = (p) => {
  const {durationInFrames, fps} = useVideoConfig();
  const fadeOut = (f: number) =>
    interpolate(f, [durationInFrames - fps * 1.5, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      <Background brand={p.brand} />
      <Series>
        {p.scenes.map((scene, i) => (
          <Series.Sequence key={i} durationInFrames={scene.frames} name={scene.type}>
            <SceneFade>{sceneBody(scene, p)}</SceneFade>
          </Series.Sequence>
        ))}
      </Series>
      <Progress color={p.brand.accent} />
      {p.draft ? <DraftStamp /> : null}
      {p.voiceover ? <Audio src={staticFile(p.voiceover)} /> : null}
      {p.music ? <Audio src={staticFile(p.music)} volume={(f) => p.musicVolume * fadeOut(f)} /> : null}
    </AbsoluteFill>
  );
};

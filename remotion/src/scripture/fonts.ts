import {continueRender, delayRender, staticFile} from 'remotion';

// Fonts are bundled in public/fonts (SIL Open Font License), so renders never depend on a font CDN.
export const SERIF = 'Cormorant Garamond';
export const SANS = 'Inter';

const faces: Array<[string, string, FontFaceDescriptors]> = [
  [SERIF, 'fonts/CormorantGaramond.ttf', {weight: '300 700', style: 'normal'}],
  [SERIF, 'fonts/CormorantGaramond-Italic.ttf', {weight: '300 700', style: 'italic'}],
  [SANS, 'fonts/Inter.ttf', {weight: '100 900', style: 'normal'}],
];

let loading: Promise<void> | null = null;

// Called once per render: holds the first frame until every font is ready.
export const loadFonts = () => {
  if (loading) {
    return;
  }
  const handle = delayRender('Loading fonts');
  loading = Promise.all(
    faces.map(([family, file, desc]) => {
      const face = new FontFace(family, `url(${staticFile(file)}) format('truetype')`, desc);
      return face.load().then((f) => {
        document.fonts.add(f);
      });
    }),
  )
    .then(() => continueRender(handle))
    .catch((err) => {
      console.error('Font loading failed', err);
      continueRender(handle);
    });
};

import {continueRender, delayRender} from 'remotion';
import cinzel from './fonts/Cinzel.ttf';
import cormorant from './fonts/CormorantGaramond.ttf';
import cormorantItalic from './fonts/CormorantGaramond-Italic.ttf';
import barlow from './fonts/BarlowCondensed-SemiBold.ttf';
import montserrat from './fonts/Montserrat-800.ttf';
import type {Side} from './schema';

// Palette « documentaire d'histoire » (relevée sur les frames de référence).
export const C = {
  bg: '#15130f',
  bg2: '#1f1b16',
  cream: '#ece3cf',
  creamDim: 'rgba(236,227,207,0.62)',
  gold: '#c9a45a',
  goldDim: 'rgba(201,164,90,0.5)',
  red: '#b7343c',
  blue: '#3c6cb4',
  blueLight: '#9dbbea',
  redBlock: '#b33a3a',
  redLight: '#eb9a9a',
  panel: 'rgba(14,12,10,0.78)',
};

export const F = {
  title: 'Cinzel, serif',
  serif: '"Cormorant Garamond", serif',
  label: '"Barlow Condensed", sans-serif',
  caption: 'Montserrat, sans-serif',
};

export const sideColor = (s?: Side) => (s === 'a' ? C.blue : s === 'b' ? C.redBlock : C.gold);
export const sideText = (s?: Side) => (s === 'a' ? C.blueLight : s === 'b' ? C.redLight : C.gold);

const FACES: [string, string, string, string][] = [
  ['Cinzel', cinzel, '400 900', 'normal'],
  ['Cormorant Garamond', cormorant, '300 700', 'normal'],
  ['Cormorant Garamond', cormorantItalic, '300 700', 'italic'],
  ['Barlow Condensed', barlow, '600', 'normal'],
  ['Montserrat', montserrat, '800', 'normal'],
];

let fontsRequested = false;
export const ensureFonts = () => {
  if (fontsRequested || typeof document === 'undefined') return;
  fontsRequested = true;
  const handle = delayRender('Chargement des polices');
  Promise.all(
    FACES.map(([family, url, weight, style]) =>
      new FontFace(family, `url(${url})`, {weight, style}).load().then((f) => document.fonts.add(f)),
    ),
  )
    .then(() => continueRender(handle))
    .catch((e) => {
      console.error('Polices', e);
      continueRender(handle);
    });
};

import {continueRender, delayRender} from 'remotion';
import cinzel from './fonts/Cinzel.ttf';
import cormorant from './fonts/CormorantGaramond.ttf';
import cormorantItalic from './fonts/CormorantGaramond-Italic.ttf';
import barlow from './fonts/BarlowCondensed-SemiBold.ttf';
import montserrat from './fonts/Montserrat-800.ttf';
import type {Side} from './schema';

// Deux thèmes, choisis par vidéo (timeline.theme) pour aller avec le style des images :
//  - cinematic   : charbon chaud + crème + or (images photoréalistes) ;
//  - illustrated : parchemin + encre + rouge sang (images dessinées encre & aquarelle, BD, peinture).
// `C` est muté par applyTheme() au début du rendu : tous les templates lisent les mêmes jetons.
const CINEMATIC = {
  paper: false,
  bg: '#1c1914',
  bg2: '#1f1b16',
  bgRgb: '28,25,20',
  cream: '#ece3cf', // couleur du texte principal
  creamDim: 'rgba(236,227,207,0.62)',
  gold: '#c9a45a',
  goldDim: 'rgba(201,164,90,0.5)',
  red: '#b7343c',
  blue: '#3c6cb4',
  blueLight: '#9dbbea',
  redBlock: '#b33a3a',
  redLight: '#eb9a9a',
  panel: 'rgba(14,12,10,0.78)',
  shadow: '0 2px 18px rgba(0,0,0,0.6)', // halo du texte sur les cartes
  frame: '#e7dfcc', // passe-partout des documents d'archive
  bracket: 'rgba(236,227,207,0.28)',
};
const ILLUSTRATED: typeof CINEMATIC = {
  paper: true,
  bg: '#e4d3b0',
  bg2: '#d8c39b',
  bgRgb: '228,211,176',
  cream: '#2a1f16',
  creamDim: 'rgba(42,31,22,0.72)',
  gold: '#8a5a1c',
  goldDim: 'rgba(138,90,28,0.55)',
  red: '#9a2a1f',
  blue: '#2c5687',
  blueLight: '#2c5687',
  redBlock: '#9a2a1f',
  redLight: '#9a2a1f',
  panel: 'rgba(228,211,176,0.85)',
  shadow: '0 1px 0 rgba(255,248,230,0.35)',
  frame: '#f4ead2',
  bracket: 'rgba(42,31,22,0.45)',
};
export const THEMES = {cinematic: CINEMATIC, illustrated: ILLUSTRATED};
export type ThemeName = keyof typeof THEMES;
export const C = {...CINEMATIC};
export const applyTheme = (name?: string) => {
  Object.assign(C, THEMES[(name as ThemeName) in THEMES ? (name as ThemeName) : 'cinematic']);
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

// Timeline JSON produit par services/history_engine.py (Drylow Studio) et lu par la
// composition « History ». Toutes les durées sont en secondes ; les chemins d'images /
// sons sont relatifs au dossier du projet (servi comme publicDir par render.mjs).

export type Side = 'a' | 'b' | 'neutral';

export type ImageSeg = {
  type: 'image';
  src: string;
  motion?: 'in' | 'out' | 'left' | 'right' | 'up' | 'down';
  strength?: number; // amplitude du zoom (0.06 = +6 %)
  label?: {name: string; role?: string}; // cartouche nom + rôle (1re apparition d'un personnage)
  stamp?: string; // tampon lieu · date sur un plan d'ouverture : "HASTINGS, ENGLAND · 14 OCTOBER 1066"
};

export type VideoSeg = {type: 'video'; src: string};

export type StatementSeg = {
  type: 'statement';
  text: string; // les mots entre *étoiles* passent en rouge : "THE STORY *HIDES* THE *TRUTH*"
  reveal?: number; // secondes après le début du segment où la phrase apparaît (mot prononcé)
  kicker?: string; // petite ligne dorée au-dessus (contexte) : "OCTOBER 14, 1066"
};

export type NumberSeg = {
  type: 'number';
  value: number;
  prefix?: string;
  suffix?: string;
  label: string; // "MEN ON THE RIDGE"
  sub?: string; // petite ligne de contexte / source
  reveal?: number;
};

export type Unit = {
  label?: string;
  side: Side;
  kind?: 'infantry' | 'cavalry' | 'archers' | 'chariots' | 'elephants' | 'command';
  x: number; // 0-100 (% de la largeur)
  y: number; // 0-100 (% de la hauteur)
  to?: [number, number]; // déplacement éventuel
  move?: [number, number]; // fenêtre du déplacement, en fraction du segment (0-1)
  w?: number; // taille du bloc en px (défaut 54 x 30)
  h?: number;
  trail?: boolean;
};

export type BattleSeg = {
  type: 'battle';
  title: string;
  subtitle?: string;
  terrain?: string;
  units: Unit[];
  labels?: {text: string; x: number; y: number; side?: Side}[];
  line?: {y: number; x1: number; x2: number}; // ligne de front dorée graduée
};

export type CharacterSeg = {
  type: 'character';
  name: string;
  role?: string;
  image: string;
  facts?: string[];
  variant?: 'right' | 'left' | 'full'; // portrait à droite, à gauche, ou plein cadre
};

export type ArmySide = {title: string; subtitle?: string; image?: string; stats: string[]};
export type CompareSeg = {
  type: 'compare';
  left: ArmySide;
  right?: ArmySide;
  splitAt?: number; // fraction du segment où l'écran se partage (défaut 0.45)
};

export type ChartSeg = {
  type: 'chart';
  title: string;
  subtitle?: string;
  bars: {label: string; value: number; side?: Side; display?: string}[];
};

export type ArchiveSeg = {
  type: 'archive';
  title: string;
  image: string;
  note?: string;
  credit?: string; // "The Met, public domain" / "Wikimedia Commons · CC BY-SA 4.0"
  tilt?: number; // degrés (variante)
};

export type RouteSeg = {
  type: 'route';
  title: string;
  subtitle?: string;
  stops: {name: string; x: number; y: number; coords?: string}[];
};

export type MapSeg = {
  type: 'map';
  title: string;
  subtitle?: string;
  land: string[]; // tracés SVG des terres (repère 1920x1080), calculés côté Python (Natural Earth)
  rivers?: string[];
  places: {name: string; x: number; y: number; kind?: 'city' | 'battle'; at?: number; dx?: number; dy?: number}[];
  moves: {path: [number, number][]; side?: Side; label?: string; start: number; end: number; labelAt?: [number, number]}[];
  battle?: {x: number; y: number; at: number};
  focus?: [number, number]; // point vers lequel la caméra zoome
};

export type QuoteSeg = {
  type: 'quote';
  text: string;
  author: string;
  source?: string; // ex. « Attributed — Livy, Book XXII »
  image?: string;
  words?: number[]; // instant (s, depuis le début du segment) où chaque mot est prononcé
};

export type Segment = {start: number; end: number} & (
  | ImageSeg
  | VideoSeg
  | StatementSeg
  | BattleSeg
  | CharacterSeg
  | CompareSeg
  | ChartSeg
  | ArchiveSeg
  | RouteSeg
  | QuoteSeg
  | NumberSeg
  | MapSeg
);

export type Caption = {text: string; start: number; end: number};

export type Timeline = {
  duration: number;
  fps?: number;
  width?: number;
  height?: number;
  voice?: string;
  music?: string;
  musicVolume?: number;
  sfx?: {src: string; at: number; volume?: number}[];
  captions?: Caption[];
  captionsFrom?: number; // pas de sous-titres pendant le hook (comme Dose of History)
  captionsMute?: [number, number][]; // plages sans sous-titres (citations déjà écrites à l'écran)
  captionsBand?: [number, number][]; // plages où un bandeau sombre renforce les sous-titres (sur les images)
  film?: number; // intensité du look pellicule (0 = off, 1 = défaut)
  theme?: 'cinematic' | 'illustrated'; // habillage des cartes, assorti au style des images
  segments: Segment[];
};

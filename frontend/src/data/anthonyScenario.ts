import type { AssetImages } from '../types/script';
import { ANTHONY_SCRIPT_DATA } from './anthonyScenarioScript';
import { ANTHONY_FULL_SCRIPT_DATA } from './anthonyScenarioFull';

export const ANTHONY_SCRIPT = ANTHONY_SCRIPT_DATA;
export const ANTHONY_FULL_SCRIPT = ANTHONY_FULL_SCRIPT_DATA;

// The app is served under Vite's configured `base` (currently '/openstax/'),
// so public/ assets must be resolved against BASE_URL rather than the site
// root or they 404 once deployed under that path prefix.
const asset = (path: string) => `${import.meta.env.BASE_URL}anthony-scenario/${path}`;

// Keyed by trunk position (scene_1..scene_10) - StudentPlayer's videoLinks prop matches by position, not scene_id.
// Position -> real scene_id: 1,2,3,4,5,8,9,12,13,16 (the trimmed trunk kept in anthonyScenarioScript.ts).
export const ANTHONY_VIDEO_LINKS: Record<string, string> = {
  'scene_1.mp4': asset('videos/scene1.mp4'),
  'scene_2.mp4': asset('videos/scene2.mp4'),
  'scene_3.mp4': asset('videos/scene3.mp4'),
  'scene_4.mp4': asset('videos/scene4.mp4'),
  'scene_5.mp4': asset('videos/scene5.mp4'),
  'scene_6.mp4': asset('videos/scene8.mp4'),
  'scene_7.mp4': asset('videos/scene9.mp4'),
  'scene_8.mp4': asset('videos/scene12.mp4'),
  'scene_9.mp4': asset('videos/scene13.mp4'),
  'scene_10.mp4': asset('videos/scene16.mp4'),
};

// Keyed directly by scene_id (1..16) - what VideoPage's sceneVideos map expects.
export const ANTHONY_FULL_SCENE_VIDEOS: Record<number, string> = Object.fromEntries(
  Array.from({ length: 16 }, (_, i) => i + 1).map(n => [n, asset(`videos/scene${n}.mp4`)]),
);

export const ANTHONY_REFERENCE_IMAGES = {
  background: asset('images/background.png'),
  player: asset('images/player.png'),
  elena: asset('images/elena.png'),
  instructor: asset('images/instructor.png'),
};

// Opening-frame storyboard stills only exist for scenes 1, 5, 9, 13 (the rest were never generated).
export const ANTHONY_FRAME_IMAGES: Record<string, string> = {
  '1': asset('images/frame_1.png'),
  '5': asset('images/frame_5.png'),
  '9': asset('images/frame_9.png'),
  '13': asset('images/frame_13.png'),
};

// Used by the trimmed Player fixture, where the dialogue-panel avatars never
// render (every scene has a video) so there's no reason to resolve real paths.
export const ANTHONY_ASSET_IMAGES: AssetImages = {
  bgPath: null,
  charPaths: {},
  framePaths: {},
};

// Used by the Studio "Load Anthony Demo" preset, where AssetsPage genuinely displays these.
export const ANTHONY_FULL_ASSET_IMAGES: AssetImages = {
  bgPath: ANTHONY_REFERENCE_IMAGES.background,
  charPaths: {
    player: ANTHONY_REFERENCE_IMAGES.player,
    elena: ANTHONY_REFERENCE_IMAGES.elena,
    instructor: ANTHONY_REFERENCE_IMAGES.instructor,
  },
  framePaths: ANTHONY_FRAME_IMAGES,
};

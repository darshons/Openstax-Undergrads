import type { AssetImages } from '../types/script';
import { ANTHONY_SCRIPT_DATA } from './anthonyScenarioScript';

export const ANTHONY_SCRIPT = ANTHONY_SCRIPT_DATA;

// videoLinks is keyed by trunk position (scene_1..scene_10) - StudentPlayer matches by position, not scene_id.
// The app is served under Vite's configured `base` (currently '/openstax/'),
// so public/ assets must be resolved against BASE_URL rather than the site
// root or they 404 once deployed under that path prefix.
const asset = (path: string) => `${import.meta.env.BASE_URL}anthony-scenario/${path}`;

export const ANTHONY_VIDEO_LINKS: Record<string, string> = {
  'scene_1.mp4': asset('videos/scene_1.mp4'),
  'scene_2.mp4': asset('videos/scene_2.mp4'),
  'scene_3.mp4': asset('videos/scene_3.mp4'),
  'scene_4.mp4': asset('videos/scene_4.mp4'),
  'scene_5.mp4': asset('videos/scene_5.mp4'),
  'scene_6.mp4': asset('videos/scene_6.mp4'),
  'scene_7.mp4': asset('videos/scene_7.mp4'),
  'scene_8.mp4': asset('videos/scene_8.mp4'),
  'scene_9.mp4': asset('videos/scene_9.mp4'),
  'scene_10.mp4': asset('videos/scene_10.mp4'),
};

// Reference images, bundled for safekeeping. StudentPlayer only renders the
// dialogue-panel avatars (charPaths) and background frame (bgPath/framePaths)
// as a fallback when no video is present for a scene - since every scene
// here has a video, these aren't currently displayed anywhere in the app.
export const ANTHONY_REFERENCE_IMAGES = {
  background: asset('images/background.png'),
  player: asset('images/player.png'),
  elena: asset('images/elena.png'),
  instructor: asset('images/instructor.png'),
};

export const ANTHONY_ASSET_IMAGES: AssetImages = {
  bgPath: null,
  charPaths: {},
  framePaths: {},
};

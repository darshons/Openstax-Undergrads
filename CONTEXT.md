# Project Context - Openstax Scenario Studio

## What This Is
An internal tool for OpenStax instructors to generate AI-powered clinical nursing scenario videos. Two sides: a **Creator Studio** (script generation, asset generation, editing) and a **Student Player** (immersive interactive video experience).

## Stack
- Frontend: Vite 8 + React 19 + TypeScript + Tailwind v4, at `frontend/`
- Backend: FastAPI (Python), at `BackEnd/`
- All frontend API calls use `/api/` relative paths via Vite proxy to `localhost:8000`
- Dev: `npm run dev` in `frontend/`, FastAPI started separately in `BackEnd/`

## Repo Layout
```
frontend/
  src/
    App.tsx                  - thin router shell
    main.tsx                 - BrowserRouter wrapper
    Studio.tsx               - creator studio (full canvas + sidebar)
    pages/
      HomePage.tsx           - role select: Creator or Student
      PlayerPage.tsx         - student player page (reads script from router state)
    components/
      student/
        StudentPlayer.tsx    - immersive player UI (dark cinema style)
      assets/AssetsPage.tsx  - image generation + retry with feedback
      video/VideoPage.tsx    - video page with "Student Preview" button
      canvas/                - script canvas, stage bar, gen overlay
      layout/                - sidebar, generate panel
    styles/global.css        - all CSS (sp-* = student player, hp-* = home page)
    types/script.ts          - shared TypeScript types
    lib/api.ts               - all API fetch helpers
    data/catalog.ts          - textbook section catalog + buildGenerateRequest
BackEnd/
  api.py                     - FastAPI app, all endpoints
  .env                       - API keys (gitignored, never read/commit)
```

## Routes
- `/`                     - HomePage: choose Creator or Student
- `/studio`               - Studio (creator side)
- `/player/:scenarioId`   - StudentPlayer (reads script from router state for now)
- `/player`               - StudentPlayer with no state (shows "No scenario loaded")

## Key Types (frontend/src/types/script.ts)
```ts
Script { title, learning_objectives, scenes, characters, decision_points, total_duration_seconds }
Scene  { scene_id, scene_type, location, dialogue, audio, routes_to?, ... }
AssetImages { bgPath: string|null, charPaths: Record<string,string>, framePaths: Record<string,string> }
Page = 'script' | 'assets' | 'videos'
```

## API Shape (lib/api.ts)
- `imageUrl(serverPath)` - converts absolute server path to `/api/image/...` URL (strips leading slash, preserves query string)
- `retryBackgroundImage / retryCharacterImage / retryOpeningFrame` - all accept optional `feedback?: string`
- Cache-busting: appended `?t=${Date.now()}` after retry, stripped before sending to backend (`rawBgPath.split('?')[0]`)

## Student Player State Machine
phases: `watching -> deciding -> feedback -> complete`
- `branchSceneId` + `wasCorrect` track which branch to show
- Auto-advance from feedback: setTimeout 2500ms
- `getDialogue(scene)` normalizes two backend formats: `audio.dialogue` (DialogueLine[]) and `audio.clips` (Clip[])
- Student Preview: VideoPage "Student Preview ->" button calls `navigate('/player/preview', { state: { script, assetImages } })`

## Git Setup
- Main checkout: `/Users/justinlee/projects/Openstax-Undergrads/`
- Worktree (for isolated edits): `.claude/worktrees/valiant-stargazing-gizmo/` on branch `student-ui`
- Workflow: commit in worktree, then `git -C /Users/justinlee/projects/Openstax-Undergrads cherry-pick <sha>` to bring changes into main checkout for dev server
- Never push without user explicitly asking

## Commit Rules
- Short, concise messages
- Never add "Co-Authored-By: Claude Sonnet 4.6" trailer
- `git commit` and `git push` as separate commands, never chained

## What's Done
- Script generation pipeline (select textbook sections, choose model, generate)
- Asset generation: background image, character images, opening frames
- Retry with user feedback for all asset types (AssetsPage)
- Student player: dark cinema layout, dialogue display with character avatars, decision points with correct/wrong feedback, completion screen
- Home page with Creator/Student role selection
- React Router split: Studio at /studio, player at /player

## What's Not Done Yet (needs backend from coworker)
- Scenario persistence: `POST /api/scenario/publish` (save script + copy assets to permanent location)
- Scenario load: `GET /api/scenario/:id` (return Script + asset paths)
- Once that exists, PlayerPage can fetch by ID instead of reading from router state
- Direct shareable student links like `/player/42` will work

## Backend Notes
- `BackEnd/api.py` has three retry endpoints with `user_feedback` support
- `ImageRetryRequest` model has: `image_request`, `user_feedback`, `retry_image_id`
- Asset paths are absolute server paths (e.g., `/var/folders/...`)

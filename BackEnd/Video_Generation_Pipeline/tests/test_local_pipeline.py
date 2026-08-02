"""Unit tests for the local ComfyUI Wan2.2 backend: scenario loading,
prompt building, and /prompt payload construction + internal consistency.

Run from Video_Generation_Pipeline/:
    ../venv/bin/python -m unittest discover -s tests -v

No GPU work, no job submission — everything here is offline except the
model-file existence checks against /home/darshon/comfyui/models (skipped
if that tree is absent).
"""

import json
import unittest
from pathlib import Path

from video_generator.scenario_loader import load_scenario
from video_generator.prompt_builder import build_clip_prompts
from video_generator import local_api

HERE = Path(__file__).resolve().parent.parent
SCENARIO = HERE / "scenario.json"
COMFY_MODELS_PRESENT = local_api.COMFY_MODELS_DIR.is_dir()


def _node_ref_problems(wf):
    """All [node_id, output_index] references must point at existing nodes."""
    problems = []
    ids = set(wf)
    for nid, node in wf.items():
        for key, val in node["inputs"].items():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                if val[0] not in ids:
                    problems.append(f"{nid}.{key} -> {val[0]}")
    return problems


class TestScenarioLoading(unittest.TestCase):
    def test_load_scenario(self):
        scenario = load_scenario(str(SCENARIO))
        self.assertIn("scenes", scenario)
        self.assertIn("characters", scenario)
        self.assertIn("visual_style", scenario)
        self.assertEqual(len(scenario["characters"]), 2)

    def test_scene_1_exists_with_clips(self):
        scenario = load_scenario(str(SCENARIO))
        scene1 = next(s for s in scenario["scenes"] if s["scene_id"] == 1)
        self.assertEqual(len(scene1["clips"]), 3)

    def test_missing_keys_raise(self):
        from video_generator.scenario_loader import validate_scenario
        with self.assertRaises(ValueError):
            validate_scenario({"scenes": []})


class TestPromptBuild(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario(str(SCENARIO))
        self.scene1 = next(s for s in self.scenario["scenes"] if s["scene_id"] == 1)

    def test_one_prompt_per_clip(self):
        prompts = build_clip_prompts(
            self.scene1, self.scenario["characters"], self.scenario["visual_style"]
        )
        self.assertEqual(len(prompts), 3)
        for p in prompts:
            self.assertIsInstance(p, str)
            self.assertGreater(len(p), 100)

    def test_first_clip_full_later_continuation(self):
        prompts = build_clip_prompts(
            self.scene1, self.scenario["characters"], self.scenario["visual_style"]
        )
        self.assertIn("Visual style:", prompts[0])
        self.assertIn("Maya", prompts[0])
        for p in prompts[1:]:
            self.assertIn("direct continuation", p)

    def test_dialogue_lands_in_prompt(self):
        prompts = build_clip_prompts(
            self.scene1, self.scenario["characters"], self.scenario["visual_style"]
        )
        self.assertIn("Good morning, Carl", prompts[0])
        self.assertIn("Sure. Go ahead.", prompts[1])


class TestWorkflowBuild(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario(str(SCENARIO))
        self.scene1 = next(s for s in self.scenario["scenes"] if s["scene_id"] == 1)
        self.prompts = build_clip_prompts(
            self.scene1, self.scenario["characters"], self.scenario["visual_style"]
        )

    def test_t2v_payload_shape(self):
        wf = local_api.build_workflow(self.prompts[0], mode="t2v")
        payload = local_api.build_payload(wf)
        self.assertEqual(set(payload), {"prompt"})
        json.dumps(payload)  # must be JSON-serializable
        # prompt text is threaded into the positive encoder
        self.assertEqual(wf["9"]["inputs"]["text"], self.prompts[0])
        # T2V: no image nodes, samplers conditioned straight from encoders
        self.assertNotIn("17", wf)
        self.assertEqual(wf["11"]["class_type"], "EmptyHunyuanLatentVideo")
        self.assertEqual(wf["12"]["inputs"]["positive"], ["9", 0])
        self.assertEqual(wf["12"]["inputs"]["negative"], ["10", 0])
        self.assertEqual(wf["13"]["inputs"]["latent_image"], ["12", 0])

    def test_t2v_node_refs_consistent(self):
        wf = local_api.build_workflow(self.prompts[0], mode="t2v")
        self.assertEqual(_node_ref_problems(wf), [])

    def test_i2v_matches_reference_workflow_wiring(self):
        wf = local_api.build_workflow(
            self.prompts[0], mode="i2v", start_image="anchor.png"
        )
        self.assertEqual(_node_ref_problems(wf), [])
        self.assertEqual(wf["17"]["class_type"], "LoadImage")
        self.assertEqual(wf["11"]["class_type"], "WanImageToVideo")
        self.assertEqual(wf["11"]["inputs"]["start_image"], ["17", 0])
        # samplers take conditioning from WanImageToVideo, as in wan22_i2v_api.json
        self.assertEqual(wf["12"]["inputs"]["positive"], ["11", 0])
        self.assertEqual(wf["12"]["inputs"]["negative"], ["11", 1])
        self.assertEqual(wf["12"]["inputs"]["latent_image"], ["11", 2])
        # two-stage sampling boundary
        self.assertEqual(wf["12"]["inputs"]["end_at_step"], 4)
        self.assertEqual(wf["13"]["inputs"]["start_at_step"], 4)

    def test_i2v_requires_start_image(self):
        with self.assertRaises(ValueError):
            local_api.build_workflow(self.prompts[0], mode="i2v")

    def test_character_lora_on_low_noise_branch_only(self):
        wf = local_api.build_workflow(
            self.prompts[0], mode="t2v", character_lora="mayanurse_low.safetensors"
        )
        self.assertEqual(_node_ref_problems(wf), [])
        self.assertEqual(wf["18"]["inputs"]["model"], ["4", 0])
        self.assertEqual(wf["6"]["inputs"]["model"], ["18", 0])
        # high-noise branch untouched
        self.assertEqual(wf["5"]["inputs"]["model"], ["3", 0])

    @unittest.skipUnless(COMFY_MODELS_PRESENT, "ComfyUI models dir not present")
    def test_t2v_model_files_exist_on_disk(self):
        wf = local_api.build_workflow(self.prompts[0], mode="t2v")
        self.assertEqual(local_api.validate_workflow(wf), [])

    @unittest.skipUnless(COMFY_MODELS_PRESENT, "ComfyUI models dir not present")
    def test_i2v_model_files_exist_on_disk(self):
        wf = local_api.build_workflow(
            self.prompts[0], mode="i2v", start_image="anchor.png"
        )
        self.assertEqual(local_api.validate_workflow(wf), [])

    @unittest.skipUnless(COMFY_MODELS_PRESENT, "ComfyUI models dir not present")
    def test_character_lora_file_exists(self):
        wf = local_api.build_workflow(
            self.prompts[0], mode="t2v", character_lora="mayanurse_low.safetensors"
        )
        self.assertEqual(local_api.validate_workflow(wf), [])

    def test_validation_flags_missing_model_file(self):
        wf = local_api.build_workflow(self.prompts[0], mode="t2v")
        wf["1"]["inputs"]["unet_name"] = "does_not_exist.gguf"
        problems = local_api.validate_workflow(wf)
        self.assertTrue(any("does_not_exist.gguf" in p for p in problems))

    def test_validation_flags_dangling_node_ref(self):
        wf = local_api.build_workflow(self.prompts[0], mode="t2v")
        wf["14"]["inputs"]["samples"] = ["99", 0]
        problems = local_api.validate_workflow(wf)
        self.assertTrue(any("missing node 99" in p for p in problems))

    def test_every_clip_of_every_scene_builds_valid_t2v_payload(self):
        for scene in self.scenario["scenes"]:
            prompts = build_clip_prompts(
                scene, self.scenario["characters"], self.scenario["visual_style"]
            )
            for i, p in enumerate(prompts, start=1):
                wf = local_api.build_workflow(
                    p, mode="t2v",
                    filename_prefix=f"wan22/scene{scene['scene_id']}_clip{i}",
                )
                self.assertEqual(_node_ref_problems(wf), [],
                                 f"scene {scene['scene_id']} clip {i}")
                json.dumps(local_api.build_payload(wf))


class TestNoGeminiOnLocalPath(unittest.TestCase):
    def test_local_api_importable_without_google(self):
        import sys
        self.assertNotIn("GEMINI_API_KEY", getattr(local_api, "__dict__", {}))
        # importing the local backend must not have pulled in google.genai
        self.assertFalse(
            any(m == "google.genai" or m.startswith("google.genai.")
                for m in sys.modules),
            "google.genai was imported on the local path",
        )


class TestRunStatusTerminalState(unittest.TestCase):
    """The client keys off `state` alone, so "done" must not be reported while
    scenes sit in failed_scenes -- that renders as a green finish with no video."""

    def _finish(self, completed, failed):
        import tempfile
        from manim_generator.logging_utils import RunStatus
        status = RunStatus(tempfile.mkdtemp())
        status._state["completed_scenes"] = completed
        status._state["failed_scenes"] = failed
        status.finish({"manifest": True})
        with open(status.path, encoding="utf-8") as f:
            return json.load(f)

    def test_all_scenes_rendered_is_done(self):
        self.assertEqual(self._finish({"1": "a.mp4"}, {})["state"], "done")

    def test_some_scenes_failed_is_partial(self):
        self.assertEqual(self._finish({"1": "a.mp4"}, {"2": "boom"})["state"], "partial")

    def test_every_scene_failed_is_error(self):
        st = self._finish({}, {"1": "boom", "2": "boom"})
        self.assertEqual(st["state"], "error")
        self.assertTrue(st["error"])


class TestRenderModeSelection(unittest.TestCase):
    """Every scene must leave the API with a usable render_mode, so the
    renderers can read it unconditionally instead of re-deriving intent."""

    @staticmethod
    def _mod():
        import sys
        backend = HERE.parent  # .../BackEnd
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        from Script_Generation_Pipeline.render_mode import (
            normalize_render_modes, infer_render_mode,
        )
        return normalize_render_modes, infer_render_mode

    def test_dialogue_scene_infers_scenario(self):
        _, infer = self._mod()
        self.assertEqual(
            infer({"scene_summary": "Maya greets the patient and asks how he slept.",
                   "character_actions": "Maya sits down beside the bed."}),
            "scenario")

    def test_graphic_scene_infers_manim(self):
        _, infer = self._mod()
        self.assertEqual(
            infer({"scene_summary": "Show the equation and calculate the ratio.",
                   "character_actions": ""}),
            "manim")

    def test_auto_keeps_model_choice_and_normalises_case(self):
        norm, _ = self._mod()
        script = {"scenes": [{"scene_id": 1, "render_mode": "MANIM",
                              "scene_summary": "a conversation"}]}
        self.assertEqual(norm(script, "auto")["scenes"][0]["render_mode"], "manim")

    def test_auto_repairs_an_invalid_mode(self):
        norm, _ = self._mod()
        script = {"scenes": [{"scene_id": 1, "render_mode": "nonsense",
                              "scene_summary": "A labelled diagram of the nephron."}]}
        self.assertEqual(norm(script, "auto")["scenes"][0]["render_mode"], "manim")

    def test_explicit_video_type_pins_every_scene(self):
        norm, _ = self._mod()
        script = {"scenes": [{"scene_id": 1, "scene_summary": "an equation"},
                             {"scene_id": 2, "scene_summary": "a conversation"}]}
        self.assertEqual([s["render_mode"] for s in norm(script, "manim")["scenes"]],
                         ["manim", "manim"])
        self.assertEqual([s["render_mode"] for s in norm(script, "scenario")["scenes"]],
                         ["scenario", "scenario"])

    def test_missing_or_empty_scenes_do_not_raise(self):
        norm, _ = self._mod()
        for script in ({}, {"scenes": None}, {"scenes": []}, {"scenes": ["not a dict"]}):
            norm(script, "auto")


class TestScenePromptDescribesRendererChoice(unittest.TestCase):
    def test_prompt_documents_both_render_modes(self):
        import sys
        backend = HERE.parent
        if str(backend) not in sys.path:
            sys.path.insert(0, str(backend))
        rules = (backend / "Script_Generation_Pipeline" / "prompt_assembly.py").read_text()
        self.assertIn("render_mode", rules)
        self.assertIn('"manim"', rules)
        self.assertIn('"scenario"', rules)


if __name__ == "__main__":
    unittest.main()

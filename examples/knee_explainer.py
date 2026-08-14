"""Knee anatomy explainer — hand-authored geometry.

Anterior view of a right knee. Every bone is a smooth closed path through
hand-placed anchors rather than a rectangle, so the condyles, tibial plateau,
intercondylar notch and fibular head actually read as anatomy.

Render:
    KOKORO_MODEL_PATH=~/kokoro-tts/kokoro-v1.0.onnx \
    KOKORO_VOICES_PATH=~/kokoro-tts/voices-v1.0.bin \
    python -m manim -qh knee_explainer.py KneeExplainer
"""

import numpy as np
from manim import *
from manim_voiceover import VoiceoverScene

from kokoro_voiceover import KokoroService

VOICE = "af_sarah"

INK = "#EEF3F8"
MUTED = "#8FA0B2"
BONE_FILL = "#28323F"
BONE_EDGE = "#DDE5EC"
CARTILAGE = "#7FC4E8"
MENISCUS = "#5FBFA8"
LIGAMENT = "#E8985E"
GOLD = "#F2C84B"
FLUID = "#67A9CF"


def path(points, **kwargs):
    """A smooth closed VMobject through the given anchors."""
    mob = VMobject(**kwargs)
    pts = [np.array([x, y, 0.0]) for x, y in points]
    mob.set_points_smoothly(pts + [pts[0]])
    return mob


def ribbon(points, color, width=9):
    """An open smooth stroke — used for cartilage caps."""
    mob = VMobject(stroke_color=color, stroke_width=width, fill_opacity=0)
    mob.set_points_smoothly([np.array([x, y, 0.0]) for x, y in points])
    return mob


def bone(points):
    return path(
        points,
        stroke_color=BONE_EDGE,
        stroke_width=3,
        fill_color=BONE_FILL,
        fill_opacity=1,
    )


# ---------------------------------------------------------------- geometry
# Anterior right knee. Bones run past the frame edge on purpose — a distal
# femur and a proximal tibia, cut off, the way an atlas plate crops them.

FEMUR = [
    (-0.45, 3.60), (-0.48, 1.60), (-0.62, 1.05), (-1.10, 0.62), (-1.42, 0.10),
    (-1.50, -0.30), (-1.38, -0.62), (-1.05, -0.74), (-0.72, -0.70), (-0.48, -0.55),
    (-0.32, -0.28), (-0.20, -0.02), (0.00, 0.04), (0.20, -0.02), (0.32, -0.28),
    (0.48, -0.55), (0.72, -0.70), (1.05, -0.74), (1.38, -0.62), (1.50, -0.30),
    (1.42, 0.10), (1.10, 0.62), (0.62, 1.05), (0.48, 1.60), (0.45, 3.60),
]

TIBIA = [
    (-1.35, -0.88), (-1.30, -1.18), (-0.95, -1.58), (-0.68, -2.10),
    (-0.58, -3.60), (0.58, -3.60), (0.68, -2.10), (0.95, -1.58),
    (1.14, -1.18), (1.20, -0.88),
    (0.60, -0.88), (0.00, -0.88), (-0.60, -0.88),
]

FIBULA = [
    (1.12, -1.25), (1.36, -1.34), (1.46, -1.58), (1.36, -1.98),
    (1.28, -3.60), (1.10, -3.60), (1.06, -1.98), (1.04, -1.58),
]

PATELLA = [(-0.40, 1.02), (0.40, 1.02), (0.46, 0.55), (0.00, 0.12), (-0.46, 0.55)]

CAPSULE = [
    (-1.10, 1.20), (-1.62, 0.55), (-1.84, -0.20), (-1.72, -1.05),
    (-1.30, -1.45), (0.00, -1.58), (1.34, -1.45), (1.80, -1.05),
    (1.92, -0.20), (1.68, 0.55), (1.12, 1.20), (0.00, 1.34),
]

CART_LEFT = [(-1.46, -0.34), (-1.28, -0.64), (-0.98, -0.76), (-0.62, -0.66)]
CART_RIGHT = [(0.62, -0.66), (0.98, -0.76), (1.28, -0.64), (1.46, -0.34)]
CART_TIBIA = [(-1.28, -0.86), (0.00, -0.86), (1.14, -0.86)]

MENISCUS_LEFT = [(-1.28, -0.85), (-0.88, -0.85), (-1.20, -0.70)]
MENISCUS_RIGHT = [(1.14, -0.85), (0.78, -0.85), (1.08, -0.70)]

CRUCIATE_A = ([-0.24, -0.84, 0], [0.20, -0.12, 0])
CRUCIATE_B = ([0.24, -0.84, 0], [-0.20, -0.12, 0])
COLLATERAL_L = ([-1.48, 0.00, 0], [-1.30, -1.58, 0])
COLLATERAL_R = ([1.48, 0.00, 0], [1.36, -1.38, 0])

# the knee is drawn in the coordinates above, then placed with this transform;
# label leaders target raw coordinates and get mapped through it.
SCALE = 1.18
DROP = 0.25


def P(x, y):
    return np.array([x * SCALE, y * SCALE + DROP, 0.0])


class KneeExplainer(VoiceoverScene):
    def build_knee(self):
        femur = bone(FEMUR)
        tibia = bone(TIBIA)
        fibula = bone(FIBULA)

        patella_shape = path(
            PATELLA, stroke_width=0, fill_color="#4A5A6E", fill_opacity=0.55
        )
        patella_edge = DashedVMobject(
            path(PATELLA, stroke_color=INK, stroke_width=3, fill_opacity=0),
            num_dashes=34,
        )
        patella = VGroup(patella_shape, patella_edge)

        cart_femur = VGroup(ribbon(CART_LEFT, CARTILAGE), ribbon(CART_RIGHT, CARTILAGE))
        cart_tibia = ribbon(CART_TIBIA, CARTILAGE, 7)
        cartilage = VGroup(cart_femur, cart_tibia)

        menisci = VGroup(
            path(MENISCUS_LEFT, stroke_color=MENISCUS, stroke_width=2,
                 fill_color=MENISCUS, fill_opacity=0.9),
            path(MENISCUS_RIGHT, stroke_color=MENISCUS, stroke_width=2,
                 fill_color=MENISCUS, fill_opacity=0.9),
        )

        cruciates = VGroup(
            Line(*CRUCIATE_A, stroke_color=LIGAMENT, stroke_width=7),
            Line(*CRUCIATE_B, stroke_color=LIGAMENT, stroke_width=7),
        )
        collaterals = VGroup(
            Line(*COLLATERAL_L, stroke_color=LIGAMENT, stroke_width=7),
            Line(*COLLATERAL_R, stroke_color=LIGAMENT, stroke_width=7),
        )

        capsule = path(CAPSULE, stroke_color=MUTED, stroke_width=2.5, fill_opacity=0)
        fluid = path(CAPSULE, stroke_width=0, fill_color=FLUID, fill_opacity=0.16)

        tibia_group = VGroup(tibia, cart_tibia, menisci)

        knee = VGroup(
            fluid, capsule, femur, tibia, fibula,
            cart_femur, cart_tibia, menisci, cruciates, collaterals, patella,
        )
        knee.set_z_index(0)
        fluid.set_z_index(-2)
        capsule.set_z_index(-1)
        patella.set_z_index(3)
        cartilage.set_z_index(2)
        menisci.set_z_index(2)
        cruciates.set_z_index(1)

        knee.femur = femur
        knee.tibia = tibia
        knee.fibula = fibula
        knee.patella = patella
        knee.cartilage = cartilage
        knee.cart_femur = cart_femur
        knee.cart_tibia = cart_tibia
        knee.menisci = menisci
        knee.cruciates = cruciates
        knee.collaterals = collaterals
        knee.capsule = capsule
        knee.fluid = fluid
        knee.tibia_group = tibia_group
        return knee

    # ------------------------------------------------------------ labelling
    def annotate(self, text, y, side, target, run_time=0.7):
        """Label parked in an edge column with a short leader to the part."""
        mob = Text(text, font_size=25, color=INK).move_to([0, y, 0])
        mob.to_edge(side, buff=0.4)
        on_left = side is LEFT
        start = (mob.get_right() if on_left else mob.get_left()) + (RIGHT if on_left else LEFT) * 0.18
        elbow = np.array([start[0] + (0.7 if on_left else -0.7), start[1], 0.0])
        end = np.array([target[0], target[1], 0.0])
        leader = VMobject(stroke_color=MUTED, stroke_width=1.8, fill_opacity=0)
        leader.set_points_as_corners([start, elbow, end])
        self.play(FadeIn(mob, shift=(RIGHT if on_left else LEFT) * 0.25),
                  Create(leader), run_time=run_time)
        return VGroup(mob, leader)

    # ---------------------------------------------------------------- scene
    def construct(self):
        service = KokoroService(voice=VOICE)
        self.set_speech_service(service)

        knee = self.build_knee().scale(SCALE).shift(UP * DROP)
        labels = VGroup()

        # ---- 1. opening
        with self.voiceover(
            "The knee is the largest joint in the body, and it is a synovial joint. "
            "That is the freely movable kind, also called a diarthrosis. Three bones meet here."
        ):
            title = Text("The Knee", font_size=54, color=INK)
            subtitle = Text("a synovial joint  ·  freely movable  ·  a diarthrosis",
                            font_size=25, color=MUTED)
            card = VGroup(title, subtitle).arrange(DOWN, buff=0.35)
            self.play(FadeIn(title, shift=UP * 0.3), run_time=1.0)
            self.play(FadeIn(subtitle), run_time=0.8)
            self.wait(2.6)
            self.play(FadeOut(card, shift=UP * 0.3), run_time=0.8)
            self.play(
                LaggedStart(
                    Create(knee.femur), Create(knee.tibia), Create(knee.fibula),
                    lag_ratio=0.35, run_time=2.6,
                )
            )

        # ---- 2. the bones
        with self.voiceover(
            "The femur, the thigh bone, comes down from above. The tibia, the shin bone, "
            "carries the weight below. The fibula runs alongside it and takes almost no load. "
            "In front, the patella, the kneecap, glides in a groove on the femur."
        ):
            labels.add(self.annotate("Femur", 2.35, LEFT, P(-0.52, 1.85)))
            self.wait(2.2)
            labels.add(self.annotate("Tibia", -2.15, LEFT, P(-0.64, -2.15)))
            self.wait(2.4)
            labels.add(self.annotate("Fibula", -2.15, RIGHT, P(1.34, -2.20)))
            self.wait(1.6)
            self.play(FadeIn(knee.patella, scale=0.85), run_time=0.8)
            labels.add(self.annotate("Patella", 1.15, LEFT, P(-0.42, 0.62)))

        # ---- 3. cartilage and menisci
        with self.voiceover(
            "Where the bones meet, a smooth layer of articular cartilage caps each surface, "
            "so they glide instead of grind. Between them sit two wedge-shaped menisci, "
            "which spread the load and absorb shock."
        ):
            self.play(Create(knee.cart_femur), Create(knee.cart_tibia), run_time=1.4)
            labels.add(self.annotate("Articular cartilage", -0.15, LEFT, P(-1.15, -0.66)))
            self.wait(2.6)
            self.play(GrowFromCenter(knee.menisci), run_time=0.9)
            labels.add(self.annotate("Meniscus", -1.15, LEFT, P(-1.24, -0.86)))

        # ---- 4. capsule and fluid
        with self.voiceover(
            "The whole joint is wrapped in a joint capsule, lined with a membrane that fills "
            "the space with synovial fluid. That fluid lubricates the cartilage and feeds it."
        ):
            self.play(Create(knee.capsule), run_time=1.2)
            labels.add(self.annotate("Joint capsule", 2.35, RIGHT, P(1.55, 0.78)))
            self.wait(1.4)
            self.play(FadeIn(knee.fluid), run_time=0.9)
            labels.add(self.annotate("Synovial fluid", 1.15, RIGHT, P(1.62, 0.05)))

        # ---- 5. ligaments
        with self.voiceover(
            "Ligaments hold it all together. Two cruciate ligaments cross inside the joint and "
            "control front-to-back movement. Two collateral ligaments run down the sides and "
            "resist side-to-side force. A torn cruciate ligament, the A C L, is one of the most "
            "common sports injuries there is."
        ):
            self.play(Create(knee.cruciates), run_time=1.0)
            labels.add(self.annotate("Cruciate ligaments", -0.15, RIGHT, P(0.16, -0.48)))
            self.wait(3.0)
            self.play(Create(knee.collaterals), run_time=1.0)
            labels.add(self.annotate("Collateral ligaments", -1.15, RIGHT, P(1.44, -0.72)))
            self.wait(2.0)
            self.play(Indicate(knee.cruciates, color=GOLD, scale_factor=1.12), run_time=1.4)

        # ---- 6. movement
        with self.voiceover(
            "Because it is a synovial joint, the knee moves freely. Bending it is flexion. "
            "Straightening it is extension."
        ):
            self.play(FadeOut(labels), run_time=0.8)
            self.play(knee.animate.scale(0.92).shift(LEFT * 2.4), run_time=1.0)

            pivot = np.array([3.4, 0.35, 0.0])
            thigh = RoundedRectangle(width=0.34, height=1.7, corner_radius=0.17,
                                     stroke_color=BONE_EDGE, stroke_width=3,
                                     fill_color=BONE_FILL, fill_opacity=1)
            thigh.move_to(pivot + UP * 0.85)
            shin = RoundedRectangle(width=0.34, height=1.7, corner_radius=0.17,
                                    stroke_color=BONE_EDGE, stroke_width=3,
                                    fill_color=BONE_FILL, fill_opacity=1)
            shin.move_to(pivot + DOWN * 0.85)
            hinge = Dot(pivot, radius=0.09, color=GOLD)
            caption = Text("side view", font_size=21, color=MUTED)
            caption.next_to(VGroup(thigh, shin), UP, buff=0.45)
            self.play(FadeIn(VGroup(thigh, shin, hinge, caption)), run_time=0.8)

            flex_tag = Text("Flexion", font_size=26, color=GOLD)
            ext_tag = Text("Extension", font_size=26, color=CARTILAGE)
            for tag in (flex_tag, ext_tag):
                tag.move_to(pivot + DOWN * 2.3)

            self.play(Rotate(shin, angle=-70 * DEGREES, about_point=pivot),
                      FadeIn(flex_tag), run_time=1.5)
            self.wait(0.8)
            self.play(Rotate(shin, angle=70 * DEGREES, about_point=pivot),
                      FadeOut(flex_tag), FadeIn(ext_tag), run_time=1.5)
            self.wait(0.6)
            self.play(FadeOut(VGroup(thigh, shin, hinge, caption, ext_tag)), run_time=0.7)
            self.play(knee.animate.scale(1 / 0.92).shift(RIGHT * 2.4), run_time=1.0)

        # ---- 7. osteoarthritis
        with self.voiceover(
            "Now watch what osteoarthritis does. The cartilage thins and wears away. "
            "The gap between the bones narrows. At the edges, extra bone builds up into a spur, "
            "called an osteophyte."
        ):
            self.play(knee.animate.scale(1.35).move_to([-1.7, 0.4, 0]), run_time=1.2)

            self.play(knee.cart_femur.animate.set_stroke(width=3.5), run_time=1.4)
            self.play(
                knee.tibia_group.animate.shift(UP * 0.11),
                knee.cart_tibia.animate.set_stroke(width=3),
                run_time=1.6,
            )

            gap_tag = Text("Joint-space narrowing", font_size=26, color=GOLD)
            gap_tag.to_edge(RIGHT, buff=0.5).shift(UP * 1.2)
            gap_arrow = Arrow(
                gap_tag.get_left() + LEFT * 0.1,
                knee.cart_tibia.get_right() + LEFT * 0.45 + UP * 0.1,
                buff=0.15, stroke_width=3.5, color=GOLD, max_tip_length_to_length_ratio=0.09,
            )
            self.play(FadeIn(gap_tag), GrowArrow(gap_arrow), run_time=0.9)
            self.wait(1.6)

            spur_anchor = knee.cart_tibia.get_left()
            spur = path(
                [(0, 0), (0.34, 0.06), (0.16, -0.22)],
                stroke_color=GOLD, stroke_width=3, fill_color=GOLD, fill_opacity=0.6,
            ).scale(1.3).move_to(spur_anchor + LEFT * 0.24)
            spur_tag = Text("Osteophyte  (bone spur)", font_size=26, color=GOLD)
            spur_tag.to_edge(LEFT, buff=0.5).shift(DOWN * 2.2)
            spur_arrow = Arrow(
                spur_tag.get_right() + RIGHT * 0.1, spur.get_left(),
                buff=0.15, stroke_width=3.5, color=GOLD, max_tip_length_to_length_ratio=0.09,
            )
            self.play(GrowFromCenter(spur), FadeIn(spur_tag), GrowArrow(spur_arrow), run_time=1.0)

        # ---- 8. close
        with self.voiceover(
            "Cartilage itself never shows up on an X-ray. That narrowed gap is how the loss "
            "gets measured."
        ):
            closing = VGroup(
                Text("Cartilage is invisible on an X-ray.", font_size=27, color=INK),
                Text("The gap is the evidence.", font_size=27, color=INK),
            ).arrange(DOWN, buff=0.22, aligned_edge=LEFT)
            closing.to_edge(RIGHT, buff=0.5).shift(DOWN * 1.9)
            self.play(FadeIn(closing, shift=UP * 0.2), run_time=0.9)
            self.wait(3.0)

        self.wait(0.8)
        self.play(FadeOut(Group(*self.mobjects)), run_time=1.0)
        self.wait(0.4)

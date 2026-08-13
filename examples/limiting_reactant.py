"""
OpenStax Chemistry Prototype — Limiting Reactant Scenario
=========================================================

Proof-of-concept for a Manim-based pipeline that turns OpenStax textbook
content into interactive video scenarios. The architectural argument this
file makes:

    ProfessorChen and Beaker are written as reusable VGroup classes, not
    one-off shapes. In a real system, you'd have dozens of such classes
    (Neuron, SupplyCurve, FreeBodyDiagram, Ammeter, ...) parameterized
    by problem data. Each scenario script then composes them. The win
    over text-to-video models like Veo is determinism: same character
    every scene, correct glassware, correct equations, near-zero render
    cost per scenario.

Render:
    manim -pql limiting_reactant.py LimitingReactantScene
"""

from manim import *

# ---------------------------------------------------------------------------
# Render config — locked to 720p30 so the file is self-contained.
# ---------------------------------------------------------------------------
config.pixel_width = 1280
config.pixel_height = 720
config.frame_rate = 30

# ---------------------------------------------------------------------------
# Subject-wide color palette. Centralizing these is what lets a future
# scenario reuse "hydrogen blue" without rediscovering a hex code.
# ---------------------------------------------------------------------------
H_COLOR = BLUE
O_COLOR = RED
WATER_COLOR = TEAL
HIGHLIGHT = YELLOW
SKIN = "#F4C7A1"
COAT = WHITE
GOGGLE_GLASS = "#A8D8FF"


# ===========================================================================
# ProfessorChen — recurring character
# ===========================================================================
class ProfessorChen(VGroup):
    """
    Recurring character built from Manim primitives so the prototype has
    zero external asset dependencies. The class exposes named sub-parts
    (head, goggles, right_arm, ...) and animation methods (wave, point_at,
    say) so that scenario scripts never need to reach into her internals.

    In production: swap the primitive body for SVGMobject("assets/chen.svg")
    designed by an illustrator. The method surface (wave, point_at, say)
    stays identical — that's the whole point of the abstraction.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Lab coat / torso — trapezoid-ish body using a rounded rectangle.
        self.body = RoundedRectangle(
            width=1.6, height=1.8, corner_radius=0.15,
            fill_color=COAT, fill_opacity=1, stroke_color=GREY_B, stroke_width=2,
        ).shift(DOWN * 0.6)

        # Coat lapel line down the center, so she reads as wearing a coat.
        lapel = Line(
            self.body.get_top() + DOWN * 0.05,
            self.body.get_bottom() + UP * 0.05,
            color=GREY_B, stroke_width=2,
        )

        # Head.
        self.head = Circle(radius=0.55, fill_color=SKIN, fill_opacity=1,
                           stroke_color=GREY_D, stroke_width=2)
        self.head.next_to(self.body, UP, buff=-0.05)

        # Hair — a half-disc cap on top of the head.
        self.hair = Arc(radius=0.55, start_angle=0, angle=PI,
                       arc_center=self.head.get_center(),
                       fill_color="#3B2A20", fill_opacity=1,
                       stroke_color="#3B2A20", stroke_width=2)

        # Safety goggles — two linked circles with a bridge.
        goggle_y = self.head.get_center()[1] + 0.05
        left_goggle = Circle(radius=0.16, fill_color=GOGGLE_GLASS, fill_opacity=0.7,
                             stroke_color=GREY_D, stroke_width=3)
        left_goggle.move_to([self.head.get_center()[0] - 0.18, goggle_y, 0])
        right_goggle = Circle(radius=0.16, fill_color=GOGGLE_GLASS, fill_opacity=0.7,
                              stroke_color=GREY_D, stroke_width=3)
        right_goggle.move_to([self.head.get_center()[0] + 0.18, goggle_y, 0])
        goggle_bridge = Line(left_goggle.get_right(), right_goggle.get_left(),
                             color=GREY_D, stroke_width=3)
        self.goggles = VGroup(left_goggle, right_goggle, goggle_bridge)

        # Smile — small arc below the goggles.
        self.mouth = Arc(radius=0.12, start_angle=PI + 0.3, angle=PI - 0.6,
                        color=GREY_E, stroke_width=2)
        self.mouth.move_to(self.head.get_center() + DOWN * 0.25)

        # Arms. Right arm is the one she waves / points with, so we keep
        # its pivot at the shoulder for clean rotation animations. Arms
        # start at the body's outer edge and extend outward so they read
        # against both the white coat and the black background.
        shoulder_l = self.body.get_corner(UL) + DOWN * 0.15
        shoulder_r = self.body.get_corner(UR) + DOWN * 0.15

        self.left_arm = Line(
            shoulder_l, shoulder_l + DOWN * 0.7 + LEFT * 0.4,
            color=COAT, stroke_width=16,
        )
        self.right_arm = Line(
            shoulder_r, shoulder_r + DOWN * 0.7 + RIGHT * 0.4,
            color=COAT, stroke_width=16,
        )
        # Hands: small skin-colored circles at the wrist end. These give
        # the arms a clear silhouette against the coat.
        self.left_hand = Circle(radius=0.11, fill_color=SKIN, fill_opacity=1,
                               stroke_color=GREY_D, stroke_width=2)
        self.left_hand.move_to(self.left_arm.get_end())
        self.right_hand = Circle(radius=0.11, fill_color=SKIN, fill_opacity=1,
                                stroke_color=GREY_D, stroke_width=2)
        self.right_hand.move_to(self.right_arm.get_end())

        # Keep hand glued to arm tip during rotations.
        self.right_hand.add_updater(
            lambda m: m.move_to(self.right_arm.get_end())
        )
        self.left_hand.add_updater(
            lambda m: m.move_to(self.left_arm.get_end())
        )

        # Outline arms with a thin grey stroke wrapper so they don't blend
        # into the coat. Drawn as a slightly thicker grey line behind
        # each white arm.
        left_arm_outline = Line(
            self.left_arm.get_start(), self.left_arm.get_end(),
            color=GREY_B, stroke_width=20,
        )
        right_arm_outline = Line(
            self.right_arm.get_start(), self.right_arm.get_end(),
            color=GREY_B, stroke_width=20,
        )
        # Keep outlines glued to their arms.
        left_arm_outline.add_updater(
            lambda m: m.put_start_and_end_on(
                self.left_arm.get_start(), self.left_arm.get_end()
            )
        )
        right_arm_outline.add_updater(
            lambda m: m.put_start_and_end_on(
                self.right_arm.get_start(), self.right_arm.get_end()
            )
        )

        # Draw order: outlines under arms under hands; body under everything
        # else for the torso; head/face on top.
        self.add(left_arm_outline, right_arm_outline,
                 self.body, lapel,
                 self.left_arm, self.right_arm,
                 self.left_hand, self.right_hand,
                 self.head, self.hair, self.goggles, self.mouth)

    # -- Animation helpers ---------------------------------------------------

    def wave(self):
        """Quick two-beat wave with the right arm."""
        # Pivot is the arm's CURRENT start (shoulder), looked up at
        # animation time. Storing it at __init__ would be wrong after
        # the whole character has been moved or scaled.
        pivot = self.right_arm.get_start()
        return Succession(
            Rotate(self.right_arm, angle=-2.2, about_point=pivot,
                   run_time=0.4),
            Rotate(self.right_arm, angle=0.4, about_point=pivot,
                   run_time=0.25),
            Rotate(self.right_arm, angle=-0.4, about_point=pivot,
                   run_time=0.25),
            Rotate(self.right_arm, angle=0.4, about_point=pivot,
                   run_time=0.25),
            Rotate(self.right_arm, angle=1.8, about_point=pivot,
                   run_time=0.4),
        )

    def point_at(self, target):
        """
        Rotate the right arm so its tip aims at `target`. Returns an
        animation the caller can play(...) at their leisure.
        """
        shoulder = self.right_arm.get_start()
        current_tip = self.right_arm.get_end()
        current_vec = current_tip - shoulder
        target_vec = np.array(target.get_center()) - shoulder
        # 2D signed angle between current arm direction and target direction.
        a1 = np.arctan2(current_vec[1], current_vec[0])
        a2 = np.arctan2(target_vec[1], target_vec[0])
        delta = a2 - a1
        # Normalize to [-pi, pi] so we take the short way around.
        delta = (delta + PI) % (2 * PI) - PI
        return Rotate(self.right_arm, angle=delta, about_point=shoulder)

    def say(self, text, width=4.0):
        """
        Build a speech bubble VGroup beside her head. Returned as a
        mobject (not animation) so the caller chooses how to introduce
        it (FadeIn, Write, etc.).
        """
        bubble_text = Text(text, font_size=22, color=BLACK)
        if bubble_text.width > width - 0.4:
            bubble_text.scale((width - 0.4) / bubble_text.width)

        bubble = RoundedRectangle(
            width=max(width, bubble_text.width + 0.6),
            height=bubble_text.height + 0.6,
            corner_radius=0.2,
            fill_color=WHITE, fill_opacity=1,
            stroke_color=GREY_D, stroke_width=2,
        )
        bubble_text.move_to(bubble.get_center())

        # Little tail pointing toward her head.
        tail = Polygon(
            bubble.get_corner(DL) + RIGHT * 0.4,
            bubble.get_corner(DL) + RIGHT * 0.7,
            bubble.get_corner(DL) + RIGHT * 0.2 + DOWN * 0.3,
            fill_color=WHITE, fill_opacity=1,
            stroke_color=GREY_D, stroke_width=2,
        )

        group = VGroup(bubble, tail, bubble_text)
        group.next_to(self.head, UR, buff=0.3)
        return group


# ===========================================================================
# Beaker — reusable chemistry glassware
# ===========================================================================
class Beaker(VGroup):
    """
    Parametric chemistry beaker. The whole point of this class is to be
    boring — you should be able to drop `Beaker(label="HCl", mass="10mL",
    fill_level=0.4, fill_color=GREEN)` into any chemistry scenario and
    have it look right without thinking about geometry.

    Real systems would extend this with subclasses (GraduatedCylinder,
    ErlenmeyerFlask, RoundBottomFlask) sharing the same fill/label API.
    """

    def __init__(self, label="", mass="", fill_level=0.6, fill_color=BLUE,
                 width=1.4, height=1.8, **kwargs):
        super().__init__(**kwargs)
        self._fill_color = fill_color
        self._max_height = height

        # Glass walls — three-sided open-top rectangle so it reads as a
        # beaker, not a sealed box. Use a VMobject path for the outline.
        wall_thickness = 3
        left_wall = Line(
            [-width/2, height/2, 0], [-width/2, -height/2, 0],
            color=GREY_B, stroke_width=wall_thickness,
        )
        bottom = Line(
            [-width/2, -height/2, 0], [width/2, -height/2, 0],
            color=GREY_B, stroke_width=wall_thickness,
        )
        right_wall = Line(
            [width/2, -height/2, 0], [width/2, height/2, 0],
            color=GREY_B, stroke_width=wall_thickness,
        )
        # Small lip on top so it looks like a beaker rim.
        lip_l = Line([-width/2 - 0.08, height/2, 0], [-width/2, height/2, 0],
                    color=GREY_B, stroke_width=wall_thickness)
        lip_r = Line([width/2, height/2, 0], [width/2 + 0.08, height/2, 0],
                    color=GREY_B, stroke_width=wall_thickness)

        # Liquid fill — a rectangle inside the walls. Stored as an attr
        # so set_fill_level() can replace it.
        self._fill_level = fill_level
        self.fill = self._make_fill(fill_level, width, height)

        # Graduation marks — three small ticks on the right wall for
        # scientific look. Cheap detail, high readability payoff.
        marks = VGroup()
        for frac in (0.25, 0.5, 0.75):
            y = -height/2 + frac * height
            marks.add(Line([width/2 - 0.12, y, 0], [width/2, y, 0],
                          color=GREY_B, stroke_width=2))

        # Label below the beaker.
        label_text = f"{label}\n{mass}" if mass else label
        self.label_mob = Text(label_text, font_size=22, color=WHITE,
                             line_spacing=0.6)
        self.label_mob.next_to(bottom, DOWN, buff=0.15)

        self._width = width
        self._height = height
        self._walls = VGroup(left_wall, bottom, right_wall, lip_l, lip_r, marks)
        self.add(self.fill, self._walls, self.label_mob)

    def _make_fill(self, level, width, height):
        """Build the liquid rectangle for a given fill_level (0..1)."""
        fill_h = max(0.01, level * (height - 0.05))
        fill = Rectangle(
            width=width - 0.06,
            height=fill_h,
            fill_color=self._fill_color, fill_opacity=0.75,
            stroke_width=0,
        )
        fill.move_to([0, -height/2 + fill_h/2 + 0.025, 0])
        return fill

    def set_fill_level(self, level):
        """Return an animation transforming current fill to new level."""
        new_fill = self._make_fill(level, self._width, self._height)
        new_fill.move_to(self.fill.get_center() * np.array([1, 0, 1]) +
                        UP * (new_fill.get_center()[1]) + self.get_center() * np.array([1, 0, 0]))
        # Easier: re-create relative to the beaker's frame.
        new_fill.shift(self.get_center())
        self._fill_level = level
        return Transform(self.fill, new_fill)

    def highlight(self, color=HIGHLIGHT):
        """
        Pulsing glow to mark this beaker (e.g. as the limiting reactant).
        Returns a composite animation.
        """
        glow = self._walls.copy().set_stroke(color=color, width=10)
        return Succession(
            FadeIn(glow, run_time=0.3),
            Indicate(glow, scale_factor=1.08, color=color, run_time=0.6),
            FadeOut(glow, run_time=0.3),
        )

    def get_label_mob(self):
        return self.label_mob


# ===========================================================================
# The scenario
# ===========================================================================
class LimitingReactantScene(Scene):
    """
    Full 60-90s scenario: Professor Chen walks through a limiting-reactant
    problem using 6g H2 (3 mol) + 32g O2 (1 mol), so O2 is unambiguously
    limiting. Ends on a multiple-choice frame held long enough for a
    pause-and-answer interaction in a downstream player.
    """

    def construct(self):
        self.scene_1_intro()
        self.scene_2_setup()
        self.scene_3_explanation()
        self.scene_4_decision()

    # ---- Scene 1: Intro ---------------------------------------------------
    def scene_1_intro(self):
        chen = ProfessorChen()
        chen.scale(1.1).move_to(ORIGIN)

        self.play(FadeIn(chen, shift=UP * 0.3), run_time=0.8)
        self.play(chen.wave(), run_time=1.6)

        bubble = chen.say(
            "We have 6 g of hydrogen and 32 g of oxygen.\nHow much water can we make?",
            width=5.2,
        )
        self.play(FadeIn(bubble), run_time=0.8)
        self.wait(7.5)
        self.play(FadeOut(bubble), chen.animate.scale(0.65).to_edge(LEFT, buff=0.6),
                  run_time=1.0)
        self.chen = chen  # Hand to later scenes.

    # ---- Scene 2: Setup ---------------------------------------------------
    def scene_2_setup(self):
        h_beaker = Beaker(label="H₂", mass="6 g", fill_level=0.45,
                          fill_color=H_COLOR)
        o_beaker = Beaker(label="O₂", mass="32 g", fill_level=0.85,
                          fill_color=O_COLOR)

        h_beaker.move_to(UP * 1.3 + LEFT * 0.5)
        o_beaker.move_to(UP * 1.3 + RIGHT * 2.5)

        self.play(FadeIn(h_beaker, shift=DOWN * 0.3),
                  FadeIn(o_beaker, shift=DOWN * 0.3), run_time=1.2)

        equation = MathTex(
            r"2H_2", r"+", r"O_2", r"\rightarrow", r"2H_2O",
            font_size=52,
        )
        equation[0].set_color(H_COLOR)
        equation[2].set_color(O_COLOR)
        equation[4].set_color(WATER_COLOR)
        equation.move_to(DOWN * 1.2 + RIGHT * 1.0)

        self.play(Write(equation), run_time=1.8)

        # Chen points at the equation.
        self.play(self.chen.point_at(equation), run_time=0.8)
        self.wait(7.0)

        # Stash for scene 3.
        self.h_beaker = h_beaker
        self.o_beaker = o_beaker
        self.equation = equation

    # ---- Scene 3: Concept explanation -------------------------------------
    def scene_3_explanation(self):
        # Compress the setup row to the top: beakers top-left, equation
        # top-right, no overlap. Drop the beaker mass labels so we have
        # vertical room for the mole work below.
        self.play(
            FadeOut(self.h_beaker.label_mob), FadeOut(self.o_beaker.label_mob),
            self.h_beaker.animate.scale(0.55).to_corner(UL, buff=0.4),
            self.o_beaker.animate.scale(0.55).to_corner(UL, buff=0.4).shift(RIGHT * 1.3),
            self.equation.animate.scale(0.65).to_edge(UP, buff=0.5).shift(RIGHT * 2.5),
            run_time=1.0,
        )

        # Step 1: convert grams to moles for H2.
        h_conv = MathTex(
            r"6\,\text{g H}_2", r"\times", r"\frac{1\,\text{mol}}{2\,\text{g}}",
            r"=", r"3\,\text{mol H}_2",
            font_size=40,
        )
        h_conv.set_color_by_tex("H", H_COLOR)
        h_conv[0][1:4].set_color(H_COLOR)
        h_conv[4][1:].set_color(H_COLOR)
        h_conv.move_to(UP * 0.4 + LEFT * 0.5)

        self.play(Write(h_conv), run_time=1.8)
        self.wait(3.0)

        # Step 2: convert grams to moles for O2.
        o_conv = MathTex(
            r"32\,\text{g O}_2", r"\times", r"\frac{1\,\text{mol}}{32\,\text{g}}",
            r"=", r"1\,\text{mol O}_2",
            font_size=40,
        )
        o_conv[0][2:].set_color(O_COLOR)
        o_conv[4][1:].set_color(O_COLOR)
        o_conv.next_to(h_conv, DOWN, buff=0.4).align_to(h_conv, LEFT)

        self.play(Write(o_conv), run_time=1.8)
        self.wait(3.0)

        # Step 3: stoichiometric ratio check.
        ratio = MathTex(
            r"\text{Need ratio: } 2\,\text{mol H}_2 : 1\,\text{mol O}_2",
            font_size=36,
        )
        ratio.next_to(o_conv, DOWN, buff=0.6).align_to(h_conv, LEFT)

        have = MathTex(
            r"\text{Have: } 3\,\text{mol H}_2 : 1\,\text{mol O}_2",
            font_size=36,
        )
        have.next_to(ratio, DOWN, buff=0.2).align_to(ratio, LEFT)

        self.play(Write(ratio), run_time=1.2)
        self.play(Write(have), run_time=1.2)
        self.wait(4.0)

        # Step 4: conclude — O2 runs out first.
        conclusion = Text(
            "1 mol O₂ only consumes 2 mol H₂ — 1 mol H₂ is left over.",
            font_size=26, color=WATER_COLOR,
        )
        conclusion.next_to(have, DOWN, buff=0.5).align_to(have, LEFT)
        self.play(FadeIn(conclusion, shift=UP * 0.2), run_time=0.8)

        # Visual highlight: O2 beaker is the limiting reactant.
        self.play(self.o_beaker.highlight(HIGHLIGHT), run_time=1.4)

        # Position the LIMITING label under the O2 beaker's WALLS (not
        # the full VGroup — that includes a faded-out label, which would
        # offset the position). Anchor to the walls' actual screen-x to
        # avoid the gap-between-beakers placement bug.
        o_walls = self.o_beaker._walls
        limiting_label = Text("LIMITING", font_size=20, color=HIGHLIGHT, weight=BOLD)
        limiting_label.next_to(o_walls, DOWN, buff=0.45)
        limiting_label.set_x(o_walls.get_x())
        arrow = Arrow(
            limiting_label.get_top(),
            o_walls.get_bottom(),
            color=HIGHLIGHT, buff=0.08, stroke_width=5,
            max_tip_length_to_length_ratio=0.4,
        )
        self.play(FadeIn(limiting_label), GrowArrow(arrow), run_time=0.8)
        self.wait(6.0)

        # Clear the working before the decision frame.
        self._scene3_cleanup = VGroup(
            h_conv, o_conv, ratio, have, conclusion,
            limiting_label, arrow, self.equation,
            self.h_beaker, self.o_beaker,
        )

    # ---- Scene 4: Decision point ------------------------------------------
    def scene_4_decision(self):
        self.play(
            FadeOut(self._scene3_cleanup),
            self.chen.animate.scale(1.5).to_edge(LEFT, buff=1.0).shift(DOWN * 0.3),
            run_time=1.0,
        )

        question = Text("Which reactant is limiting?",
                       font_size=42, color=WHITE, weight=BOLD)
        question.to_edge(UP, buff=0.8).shift(RIGHT * 1.5)

        def option_box(letter, label_text, color):
            box = RoundedRectangle(
                width=4.0, height=0.9, corner_radius=0.15,
                stroke_color=color, stroke_width=3,
                fill_color=color, fill_opacity=0.15,
            )
            letter_mob = Text(f"({letter})", font_size=30, color=color, weight=BOLD)
            letter_mob.move_to(box.get_left() + RIGHT * 0.55)
            label_mob = Text(label_text, font_size=28, color=WHITE)
            label_mob.next_to(letter_mob, RIGHT, buff=0.4)
            return VGroup(box, letter_mob, label_mob)

        opt_a = option_box("A", "H₂", H_COLOR)
        opt_b = option_box("B", "O₂", O_COLOR)
        opt_c = option_box("C", "Both are limiting", GREY_B)

        options = VGroup(opt_a, opt_b, opt_c).arrange(DOWN, buff=0.3)
        options.next_to(question, DOWN, buff=0.6).shift(RIGHT * 0.0)
        options.align_to(question, LEFT)

        self.play(FadeIn(question), run_time=0.6)
        self.play(LaggedStart(
            FadeIn(opt_a, shift=RIGHT * 0.2),
            FadeIn(opt_b, shift=RIGHT * 0.2),
            FadeIn(opt_c, shift=RIGHT * 0.2),
            lag_ratio=0.3,
        ), run_time=1.4)

        # Chen gestures toward the question.
        self.play(self.chen.point_at(question), run_time=0.6)

        # Hold so a downstream player can pause here for a real answer.
        self.wait(8.0)

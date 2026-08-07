import type { Script } from '../types/script';

// "Elena's Knee" (Anthony) scenario, trimmed to one full decision point (branching + misconception) then correct-path-only scenes.
export const ANTHONY_SCRIPT_DATA: Script = {
  "title": "Elena's Knee: Recognizing Post-Traumatic Osteoarthritis in a Young Athlete",
  "learning_goal": "Learners will be able to follow a structured nursing assessment process for a young patient presenting with knee pain, correctly identifying subjective and objective data, recognizing key anatomical findings such as crepitus and reduced range of motion, and communicating findings and patient education accurately.",
  "target_audience": "High school students in nursing assistant programs and early healthcare learners",
  "total_duration_seconds": 220,
  "visual_style": "2D semi-flat limited animation with dynamic but constrained movement. Characters express emotion through head turns, nods, hand gestures, subtle posture shifts, and facial expressions. Mouth movement suggests speech without matching every phoneme. Consistent color palette and character designs across all clips.",
  "characters": [
    {
      "character_id": "player",
      "name": "Jordan",
      "role": "Student nursing assistant",
      "appearance": {
        "skin_tone": "Light olive",
        "hair": "Black, in a bun",
        "build": "Average height, lean build",
        "uniform": "Light blue scrub top and dark navy scrub pants",
        "distinguishing_features": "None"
      },
      "emotional_baseline": "Attentive, calm, professionally composed"
    },
    {
      "character_id": "elena",
      "name": "Elena",
      "role": "Patient, young adult athlete",
      "appearance": {
        "skin_tone": "Fair",
        "hair": "Black",
        "build": "Average height, athletic build",
        "uniform": "Casual grey t-shirt and black athletic shorts, sitting on an exam table",
        "distinguishing_features": "None"
      },
      "emotional_baseline": "Mildly anxious, cooperative, alert"
    },
    {
      "character_id": "instructor",
      "name": "Nurse Reyes",
      "role": "Supervising nurse",
      "appearance": {
        "skin_tone": "East Asian",
        "hair": "Dark brown, straight, shoulder length",
        "build": "Medium height, average build",
        "uniform": "Dark teal scrub top and grey scrub pants",
        "distinguishing_features": "None"
      },
      "emotional_baseline": "Calm, encouraging, professionally measured"
    }
  ],
  "setting": {
    "location": "Outpatient clinic examination room",
    "scene_description": "A small, clean examination room with neutral beige walls. An exam table with white paper covering sits along the right wall. A single chair is positioned near the exam table. A counter with a sink runs along the back wall. The room is tidy and well lit.",
    "light_source": "Overhead fluorescent lighting, even and bright",
    "time_of_day": "Mid-morning",
    "atmosphere": "Quiet, professional, clinical",
    "background_furniture": [
      {
        "name": "Exam table",
        "count": 1,
        "description": "Standard padded exam table with white paper cover, positioned along the right wall"
      },
      {
        "name": "Visitor chair",
        "count": 1,
        "description": "Plain plastic chair positioned near the exam table"
      },
      {
        "name": "Counter with sink",
        "count": 1,
        "description": "Built-in counter along the back wall with a basic sink, no items in frame"
      }
    ],
    "background_equipment": [
      {
        "name": "Wall-mounted supply cabinet",
        "count": 1,
        "description": "Closed cabinet mounted above the counter, doors shut, nothing visible inside"
      }
    ],
    "camera": {
      "angle": "Medium two-shot, slightly favoring the patient side of the room",
      "perspective": "Eye level, static"
    }
  },
  "scenes": [
    {
      "scene_id": 1,
      "type": "narrative",
      "scene_summary": "Before Jordan walks into a room, we see a page on a clipboard with Elena's chart, where it lists her chief complaint as \"right knee pain for several months, worse with activity.\" Jordan enters the exam room and meets Elena, who expresses concern about ongoing right knee pain. Elena mentions she has always been active and this does not feel like a normal ache. The scene establishes the chief complaint and sets up the first decision point about what to do first.",
      "duration_seconds": 28,
      "character_actions": "Jordan steps into the room from the left side of frame and pauses just inside the doorway, facing Elena. Elena sits on the exam table with her hands resting in her lap, looking toward Jordan.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left side of frame, near the doorway"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan greets Elena: Hi Elena, I'm Jordan, one of the nursing assistants here today. I just had a chance to look at your chart.",
            "character_position": "Left side of frame, near the doorway"
          },
          {
            "character_id": "elena",
            "line": "I don't know what's going on. I've always been active. This doesn't feel like a normal ache.",
            "character_position": "Right side of frame, seated on the exam table"
          },
          {
            "character_id": "player",
            "line": "Jordan nods and considers: Okay, I want to make sure I understand what's been going on before we do anything else.",
            "character_position": "Left side of frame, slightly closer now, weight settling"
          }
        ],
        "sound_effects": "A soft knock on the door at the very start of the clip",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "decision_point_id": 1,
        "type": "introduction"
      }
    },
    {
      "scene_id": 2,
      "type": "consequence",
      "scene_summary": "Jordan skips the health history and goes straight to vital signs. The exam proceeds but Elena's story is not gathered. Nurse Reyes gently redirects Jordan to gather subjective data first before moving forward.",
      "duration_seconds": 18,
      "character_actions": "Nurse Reyes steps into the room from the left. Jordan stands near the exam table on the left side of frame. Elena sits on the exam table, watching.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left center of frame, near the exam table"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table"
        },
        {
          "character_id": "instructor",
          "position": "Far left of frame, stepping in"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "instructor",
            "line": "Nurse Reyes says quietly: Vital signs are useful, but we want to hear Elena's story before we start the physical part. What does she say is happening?",
            "character_position": "Far left of frame, stepping in"
          },
          {
            "character_id": "player",
            "line": "Jordan pauses and turns back to Elena: Right. Elena, can you walk me through what's been going on with your knee?",
            "character_position": "Left center of frame"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "decision_point_id": 1,
        "type": "false_choice"
      }
    },
    {
      "scene_id": 3,
      "type": "resolution",
      "scene_summary": "Jordan pulls the chair close and begins a structured health history interview, gathering Elena's subjective account of her knee pain before any physical exam. Elena begins describing her symptoms in her own words.",
      "duration_seconds": 18,
      "character_actions": "Jordan moves the chair slightly and sits down facing Elena. Elena shifts to face Jordan more fully, her hands still resting in her lap.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left side of frame, seated in chair facing Elena"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan says calmly: Before I do anything else, I want to hear from you directly. Can you describe the pain for me?",
            "character_position": "Left side of frame, seated in chair"
          },
          {
            "character_id": "elena",
            "line": "Elena nods and begins: It's more of a deep ache. It gets worse by the end of the day or after I've been running.",
            "character_position": "Right side of frame, seated on the exam table"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "decision_point_id": 1,
        "type": "true_choice"
      }
    },
    {
      "scene_id": 4,
      "type": "consequence",
      "scene_summary": "Jordan reassures Elena that it is probably nothing serious and moves to schedule imaging. Elena looks uncertain. Nurse Reyes steps in and redirects Jordan to gather a proper history before drawing any conclusions.",
      "duration_seconds": 18,
      "character_actions": "Nurse Reyes steps into the room from the left. Jordan stands near the center of the room. Elena sits on the exam table, expression uncertain.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Center of frame, standing"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table"
        },
        {
          "character_id": "instructor",
          "position": "Far left of frame, entering"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "instructor",
            "line": "Nurse Reyes says evenly: We do not want to make assumptions before we have any data. Let's start with Elena's history and hear what she's been experiencing.",
            "character_position": "Far left of frame"
          },
          {
            "character_id": "player",
            "line": "Jordan turns back toward Elena: You're right. Elena, I'd like to hear more about your knee. Can you describe what it feels like?",
            "character_position": "Center of frame, turning toward Elena"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "decision_point_id": 1,
        "type": "false_choice"
      }
    },
    {
      "scene_id": 5,
      "type": "narrative",
      "scene_summary": "Jordan has completed a PQRSTU pain assessment. Elena has described worsening pain with activity, morning stiffness, and occasional grinding. Jordan now needs to decide what to ask about next before moving to the physical exam.",
      "duration_seconds": 28,
      "character_actions": "Jordan sits in the chair to Elena's left, with a notepad resting on one knee. Elena sits on the exam table, speaking and gesturing lightly with one hand as she talks.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left side of frame, seated in chair"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "elena",
            "line": "Elena says: In the morning my knee feels really stiff for maybe fifteen minutes or so. Then it loosens up a little.",
            "character_position": "Right side of frame, seated on the exam table"
          },
          {
            "character_id": "elena",
            "line": "Elena continues: Sometimes when I bend it I can feel this grinding or kind of a catching sensation. It doesn't always hurt when that happens.",
            "character_position": "Right side of frame, seated on the exam table"
          },
          {
            "character_id": "player",
            "line": "Jordan nods and writes: That grinding feeling is something I want to follow up on. And I have a few more questions before we look at the knee itself.",
            "character_position": "Left side of frame, seated in chair, notepad on knee"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "type": "scene",
        "scene_id": 8
      }
    },
    {
      "scene_id": 8,
      "type": "resolution",
      "scene_summary": "Jordan screens for all six hallmark musculoskeletal symptoms and asks about past injuries. Elena confirms swelling and stiffness, denies redness and warmth, and reveals her prior ACL tear and surgery, a significant finding for the case.",
      "duration_seconds": 18,
      "character_actions": "Jordan sits in the chair facing Elena, leaning slightly forward with the notepad still resting on one knee. Elena responds with a nod, her expression becoming more engaged.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left side of frame, seated in chair"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on exam table"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan asks: Has the knee been swollen, red, or warm to the touch? And has it ever been injured before?",
            "character_position": "Left side of frame, seated in chair"
          },
          {
            "character_id": "elena",
            "line": "Elena responds: It does swell sometimes, especially after a long practice. It's not red or warm, though. And yes, I tore my ACL in this knee when I was nineteen. I had surgery for it.",
            "character_position": "Right side of frame, seated on exam table"
          },
          {
            "character_id": "player",
            "line": "Jordan writes and says: That's really important information. Thank you for telling me.",
            "character_position": "Left side of frame, seated in chair, hand still writing as the clip ends"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "type": "scene",
        "scene_id": 9
      }
    },
    {
      "scene_id": 9,
      "type": "narrative",
      "scene_summary": "Jordan moves to the physical exam. Elena is asked to extend and flex her knee. Jordan observes a slight limp when Elena walks, limited range of motion, mild swelling, and crepitus on movement. Jordan now needs to decide how to handle and report these findings.",
      "duration_seconds": 28,
      "character_actions": "Jordan stands to the left of the exam table, observing Elena's knee as Elena slowly bends and straightens her right leg. Jordan watches carefully, then places both hands lightly near the knee to palpate.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left center of frame, standing beside the exam table"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on the exam table with right leg extended toward Jordan"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan says: I noticed a slight limp when you walked in. Now I'd like you to bend your knee for me and then straighten it out again.",
            "character_position": "Left center of frame, standing beside the exam table"
          },
          {
            "character_id": "elena",
            "line": "Elena bends and straightens slowly: It stops a little short when I try to fully bend it. And can you feel that? That grinding?",
            "character_position": "Right side of frame, seated on exam table"
          },
          {
            "character_id": "player",
            "line": "Jordan nods: Yes, I can feel that. I also want to check around the joint for any swelling or warmth.",
            "character_position": "Left center of frame, hands near the knee, gaze attentive"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "type": "scene",
        "scene_id": 12
      }
    },
    {
      "scene_id": 12,
      "type": "resolution",
      "scene_summary": "Jordan accurately documents the objective findings, separating them clearly from Elena's subjective report, and prepares a concise summary for the provider noting swelling, crepitus, mild strength loss, and limited range of motion with no signs of infection.",
      "duration_seconds": 18,
      "character_actions": "Jordan stands at the counter along the back wall, writing in the chart. Elena sits on the exam table in the background, waiting.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left center of frame, standing at the counter, writing"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on exam table, resting"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan says, mostly to themselves while writing: Mild swelling, crepitus on flexion, right quad strength four out of five, active range of motion mildly reduced. No redness, no warmth, no fever.",
            "character_position": "Left center of frame, at the counter"
          },
          {
            "character_id": "player",
            "line": "Jordan finishes and looks up: All of that goes to the provider. That is what we actually observed, and it matters for what comes next.",
            "character_position": "Left center of frame, turning slightly from the counter as the clip ends"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "type": "scene",
        "scene_id": 13
      }
    },
    {
      "scene_id": 13,
      "type": "narrative",
      "scene_summary": "The provider has reviewed Jordan's documentation and diagnosed Elena with post-traumatic osteoarthritis. Elena is visibly worried and asks directly whether she will need surgery and whether she has to stop playing soccer. Jordan must decide how to respond.",
      "duration_seconds": 28,
      "character_actions": "Jordan stands to the left of the exam table. Elena sits on the table, her hands now clasped in her lap, posture slightly tense. Nurse Reyes stands just inside the doorway to the left.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left center of frame, standing beside exam table"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on exam table"
        },
        {
          "character_id": "instructor",
          "position": "Far left of frame, near the doorway"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "instructor",
            "line": "Nurse Reyes says to Jordan: The provider reviewed your notes and is ready to share the diagnosis. Elena has been told she has post-traumatic osteoarthritis in that knee.",
            "character_position": "Far left of frame, near the doorway"
          },
          {
            "character_id": "elena",
            "line": "Elena says, voice quieter: Osteoarthritis? I thought that was something older people got. Am I going to need surgery? Do I have to stop playing soccer?",
            "character_position": "Right side of frame, seated on exam table, hands clasped"
          },
          {
            "character_id": "player",
            "line": "Jordan pauses and considers the right response.",
            "character_position": "Left center of frame, facing Elena"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      },
      "routes_to": {
        "type": "scene",
        "scene_id": 16
      }
    },
    {
      "scene_id": 16,
      "type": "resolution",
      "scene_summary": "Jordan explains osteoarthritis in plain language, reassures Elena that most cases are managed with conservative treatment first, and sets realistic expectations about surgery as a later option rather than an immediate one. Elena visibly relaxes.",
      "duration_seconds": 18,
      "character_actions": "Jordan sits down in the chair to Elena's left, facing her directly. Elena sits on the exam table, posture gradually relaxing as Jordan speaks.",
      "initial_character_positions": [
        {
          "character_id": "player",
          "position": "Left side of frame, seated in chair facing Elena"
        },
        {
          "character_id": "elena",
          "position": "Right side of frame, seated on exam table"
        }
      ],
      "audio": {
        "dialogue": [
          {
            "character_id": "player",
            "line": "Jordan explains calmly: Osteoarthritis means the cartilage cushioning your knee joint has started to wear down. It can happen at any age, especially after a joint injury like your ACL tear.",
            "character_position": "Left side of frame, seated in chair"
          },
          {
            "character_id": "player",
            "line": "Jordan continues: Most people start with things like physical therapy, activity changes, and medication before surgery ever comes up. Surgery is usually a later option if the other steps do not help enough.",
            "character_position": "Left side of frame, seated in chair"
          },
          {
            "character_id": "elena",
            "line": "Elena lets out a slow breath: Okay. That is actually a little less scary than I thought. Thank you for explaining that.",
            "character_position": "Right side of frame, seated on exam table, shoulders slightly lowered"
          }
        ],
        "sound_effects": "None",
        "ambience": "Quiet clinic room, faint low hum of building ventilation"
      }
    }
  ],
  "decision_points": [
    {
      "decision_point_id": 1,
      "question_text": "Elena has shared her chief complaint. What should Jordan do first?",
      "associated_introduction_scene_id": 1,
      "choices": [
        {
          "choice_id": "A",
          "text": "Pull the chair close and begin asking Elena to describe her knee pain in her own words, gathering her subjective account before touching or examining anything.",
          "is_correct": true,
          "misconception": null,
          "routes_to_scene": 3
        },
        {
          "choice_id": "B",
          "text": "Take Elena's vital signs and move directly into the physical exam, since objective findings will be most useful for the provider.",
          "is_correct": false,
          "misconception": "Learners may believe that measurable, objective data should always come first. In practice, the health history interview gathers essential subjective context that guides the physical exam and prevents important details from being missed.",
          "routes_to_scene": 2
        },
        {
          "choice_id": "C",
          "text": "Reassure Elena that it is probably nothing serious at her age and suggest scheduling an X-ray right away.",
          "is_correct": false,
          "misconception": "Learners may assume that a young, active patient is unlikely to have a significant condition. This skips the assessment process entirely and risks drawing a conclusion before any data has been gathered.",
          "routes_to_scene": 4
        }
      ]
    }
  ]
};

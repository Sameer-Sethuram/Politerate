BACKBONE_MODEL = "microsoft/deberta-v3-base"
MAX_SEQ_LEN = 256

TECHNIQUE_LABELS = [
    "Loaded_Language",                              # 0
    "Appeal_to_fear_prejudice",                     # 1
    "Exaggeration_Minimization",                    # 2
    "Repetition",                                   # 3
    "Flag_Waving",                                  # 4
    "Name_Calling_Labeling",                        # 5
    "Reductio_ad_hitlerum",                         # 6
    "Black_and_White_Fallacy",                      # 7
    "Causal_Oversimplification",                    # 8
    "Whataboutism_Straw_Men_Red_Herring",           # 9
    "Straw_Man",                                    # 10
    "Red_Herring",                                  # 11
    "Doubt",                                        # 12
    "Appeal_to_Authority",                          # 13
    "Thought_terminating_Cliches",                  # 14
    "Bandwagon",                                    # 15
    "Slogans",                                      # 16
    "Obfuscation_Intentional_Vagueness_Confusion",  # 17
]

tech_label2id = {l: i for i, l in enumerate(TECHNIQUE_LABELS)}
tech_id2label = {i: l for i, l in enumerate(TECHNIQUE_LABELS)}
NUM_TECHNIQUE = len(TECHNIQUE_LABELS)  # 18

EMOTION_LABELS = [
    "neutral",
    "admiration", "amusement", "anger", "annoyance", "approval",
    "caring", "confusion", "curiosity", "desire", "disappointment",
    "disapproval", "disgust", "embarrassment", "excitement", "fear",
    "gratitude", "grief", "joy", "love", "nervousness",
    "optimism", "pride", "realization", "relief", "remorse",
    "sadness", "surprise"
]
emotion_label2id = {l: i for i, l in enumerate(EMOTION_LABELS)}
emotion_id2label = {i: l for i, l in enumerate(EMOTION_LABELS)}
NUM_EMOTION = len(EMOTION_LABELS)  # 28

# BIAS: 3 classes from PREMSA (LABEL_0 = left, LABEL_1 = center, LABEL_2 = right)
BIAS_LABELS = ["LABEL_0", "LABEL_1", "LABEL_2"]
bias_label2id = {l: i for i, l in enumerate(BIAS_LABELS)}
bias_id2label = {i: l for i, l in enumerate(BIAS_LABELS)}

NUM_BIAS = len(BIAS_LABELS)  # 3
# Subjectivity labels
SUBJ_LABELS = [0, 1]  # adjust to match your model's output
subj_label2id = {l: i for i, l in enumerate(SUBJ_LABELS)}
NUM_SUBJ = 2

BIAS_DISPLAY_NAMES = {
    "LABEL_0": "left",
    "LABEL_1": "center",
    "LABEL_2": "right",
}

TECHNIQUE_THRESHOLDS = {
    "Loaded_Language": 0.26,
    "Appeal_to_fear_prejudice": 0.20,
    "Exaggeration_Minimization": 0.46,
    "Repetition": 0.44,
    "Flag_Waving": 0.12,
    "Name_Calling_Labeling": 0.20,
    "Reductio_ad_hitlerum": 0.16,
    "Black_and_White_Fallacy": 0.50,
    "Causal_Oversimplification": 0.18,
    "Whataboutism_Straw_Men_Red_Herring": 0.64,
    "Straw_Man": 0.50,
    "Red_Herring": 0.50,
    "Doubt": 0.20,
    "Appeal_to_Authority": 0.20,
    "Thought_terminating_Cliches": 0.14,
    "Bandwagon": 0.20,
    "Slogans": 0.20,
    "Obfuscation_Intentional_Vagueness_Confusion": 0.50,
}
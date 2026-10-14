# backend/test_load.py
# Verify the model loads correctly before wiring into FastAPI

import sys
from pathlib import Path

# Import via the `backend` package (repo root on sys.path) so the relative
# `from ..config import ...` in backend/inference/__init__.py resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.inference.predictor import PoliterateAnalyzer

print("Loading predictor...")
predictor = PoliterateAnalyzer(
    weights_path=str(Path(__file__).resolve().parent / "models" / "analyzer.pt"),
    device="cpu",
)
print("Loaded successfully.")

# Test with a sample article
test_text = """
The day after a gunman attempted to storm the White House Correspondents' Dinner at the Washington Hilton, President Trump sat down with CBS News correspondent Norah O'Donnell for a "60 Minutes" interview to talk about his experience. He spoke about his immediate reaction as the Secret Service whisked him and the first lady off stage, and what investigators have learned about the suspect's apparent motivations. 

Cole Allen, a 31-year-old Caltech graduate from Torrance, California, was captured at the scene and is facing federal charges. Shortly before the attack, he emailed family members what officials are calling a "manifesto," writing that he planned to target Trump administration officials, "prioritized from highest-ranking to lowest," according to a copy obtained by CBS News. 

Trump responds to suspect's "manifesto": "He's a sick person"
O'Donnell asked Mr. Trump about the suspect's writings, which referenced his administration but did not mention the president by name.

"The so-called manifesto is a stunning thing to read, Mr. President," O'Donnell said. "He appears to reference a motive in it. He writes this, quote, 'Administration officials, they are targets.' And he also wrote this, 'I am no longer willing to permit a pedophile, rapist, and traitor to coat my hands with his crimes.' What's your reaction to that?"

Mr. Trump replied, "Well, I was waiting for you to read that because I knew you would because you're— you're he— you're horrible people. Horrible people. Yeah, he did write that. I'm — I'm not a rapist. I didn't rape anybody."

O'Donnell said, "Oh you think— do you think he was referring to you?"

"I'm not a pedophile. Excuse me. Excuse me. I'm not a pedophile," the president said. "You read that crap from some sick person? I got associated with all– stuff that has nothing to do with me. I was totally exonerated. Your friends on the other side of the plate are the ones that were involved with, let's say, Epstein or other things. But I said to myself, 'You know, I'll do this interview and they'll probably'— I read the manifesto. You know, he's a sick person. But you should be ashamed of yourself reading that because I'm not any of those things."

"Mr. President these are the gunman's words—," O'Donnell said.

"And I was never— excuse me. Excuse me. You shouldn't be reading that on 60 Minutes. You're a disgrace. But go ahead. Let's finish the interview," Mr. Trump said, adding. "You— you're disgraceful."

"I wasn't worried," Trump says. "We live in a crazy world."
O'Donnell, who also attended the dinner, asked the president how he and the first lady responded when loud bangs were suddenly heard from just outside the packed ballroom.

"Everybody hit the floor. How worried were you that there were gonna be injuries?"

"I wasn't worried," Mr. Trump replied. "I understand life. We live in a crazy world."

"You are sitting there next to the first lady," O'Donnell continued. "The entertainer named Oz Pearlman is talking to you. He's known as The Mentalist. When did you know something was wrong?"

"Right around that point. In fact, you can see the expression on the first lady's face," he said.

O'Donnell later asked if the first lady was scared.

"Well, I don't wanna say, and people don't like having it said that they were scared," he replied. "But certainly, I mean, who wouldn't be when you have a situation like that? By that time I think she realized ahead of time that that was more of a bullet than it was a tray. And she was— I— I looked at her face just a little while ago before I came. I saw the scene. They played it for me and, you know, pretty good closeup. And— she looked— very upset about what just took place, you know? Why not?"

It took about 10 seconds for Secret Service agents to surround the president and 20 seconds to hustle him off stage.

"Well, what happened is— it was a little bit me. I wanted to see what was happening, and I wasn't making it that easy for 'em. I wanted to see what was going on. And by that time we started to realize maybe it was a bad problem," he said.

Asked again about his and the first lady's thoughts at that moment, he said, "Well, my thought was, 'You know, I've been through this before a couple of times.' And— she has not to this extent. She handled it great. I mean, she was— she's— very strong, smart. She got it. She knew what was happening. She listened. I did too, by the way."

Trump praises "the friendship, the spirit" of the dinner, says it's "very important" to reschedule
Saturday night's White House Correspondents' Dinner, an annual event celebrating the First Amendment and freedom of the press, was the first one Mr. Trump had agreed to attend as president. After the disruption, he called for it to be rescheduled within 30 days.

"I don't want to see it be canceled," he said. "I don't want to have a crazy person— I think it's really bad for a crazy person to be able to cancel something like this. There are great people in the press too I can name, but I don't want to— I don't want to embarrass your show. We have some great people in the press, some very fair people, and people that are just on my side. But for the most part, it's a very liberal or very progressive— let's use the word liberal. Liberal press. But— I was just really— I was really happy to see the— the— I don't know how long it'll last— the relationship, the friendship, the spirit after a very bad event took place."

O'Donnell said, "I know the White House Correspondents' Association very much appreciates you going last night and honoring a commitment to do it again."

"I hope we're going to do it again," he replied. "Norah, tell 'em to get it going, and we should do it within 30 days, and they'll have even more security, and they'll have bigger perimeter security. It'll be fine. But tell 'em to do it again. We can't let something be— it's not that I wanna go. It's no— I ha— I'm very busy. I don't need that. I think it's very important that they do it again."
"""

print("\nRunning test prediction...")
result = predictor.predict_article(test_text)

print(f"\nArticle-level analysis:")
print(f"  Dominant bias: {result['article']['dominant_bias']}")
print(f"  Dominant emotion: {result['article']['dominant_emotion']}")
print(f"  Subjectivity ratio: {result['article']['subjectivity_ratio']:.2f}")
print(f"  Technique counts: {result['article']['technique_counts']}")

print(f"\nPer-chunk analysis:")
for i, chunk in enumerate(result['chunks']):
    print(f"\nChunk {i}: {chunk['text'][:80]}...")
    print(f"  Emotion: {chunk['emotion']}")
    print(f"  Subjective: {chunk['subjective']}")
    print(f"  Techniques: {[t['label'] for t in chunk['techniques']]}")
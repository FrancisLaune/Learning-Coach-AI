from __future__ import annotations

from dataclasses import dataclass
from math import exp

LEVEL_WEIGHT = {"Facile": 0.75, "Moyen": 0.9, "Difficile": 1.05, "Brevet": 1.18, "Expert": 1.3}

@dataclass
class MasteryResult:
    score: float
    accuracy: float
    speed_index: float
    level_index: float
    recommendation: str

def compute_mastery(accuracy: float, avg_seconds: float, target_seconds: float, difficulty: str, attempts: int) -> MasteryResult:
    target=max(float(target_seconds or 60),10.0)
    actual=max(float(avg_seconds or target),1.0)
    speed=max(0.55,min(1.25,target/actual))
    level=LEVEL_WEIGHT.get(str(difficulty),0.9)
    confidence=1-exp(-max(attempts,0)/18)
    raw=(accuracy*0.68)+(100*speed*0.17)+(100*min(level,1.25)/1.25*0.15)
    score=max(0,min(100,raw*(0.72+0.28*confidence)))
    if accuracy>=85 and speed>=0.9:
        rec="Passer au niveau supérieur"
    elif accuracy>=75:
        rec="Consolider puis augmenter la difficulté"
    elif accuracy>=55:
        rec="Revoir les erreurs et refaire une série ciblée"
    else:
        rec="Reprendre la fiche et travailler les bases"
    return MasteryResult(round(score,1),round(accuracy,1),round(speed,2),round(level,2),rec)

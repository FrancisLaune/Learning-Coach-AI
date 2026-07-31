"""Central school-safety pattern catalogue (LCAI-0022E).

Patterns are intentionally conservative and deterministic. Pedagogical
anti-cheating rules stay in Virtual Teacher guardrails.
"""

from __future__ import annotations

# Distress / self-harm — immediate adult redirect.
DISTRESS_PATTERNS: tuple[str, ...] = (
    r"\bje veux mourir\b",
    r"\bsuicide\b",
    r"\bme faire du mal\b",
    r"\bj['']ai peur chez moi\b",
    r"\bje veux dispara[iî]tre\b",
    r"\bme tuer\b",
    r"\bautodestruction\b",
)

# Adult / violent / substance / exploitation content unsuitable for school AI.
UNSAFE_PATTERNS: tuple[str, ...] = (
    r"\bmot de passe\b",
    r"\bpassword\b",
    r"\bsexe\b",
    r"\bnude\b",
    r"\bnu\b",
    r"\bporn(?:o|ographie)?\b",
    r"\bpoignard\b",
    r"\barme\b",
    r"\btue\b",
    r"\btuer\b",
    r"\bassassin(?:er|at)?\b",
    r"\bdrogue(?:s)?\b",
    r"\bcannabis\b",
    r"\bcoca[iï]ne\b",
    r"\bh[eé]ro[iï]ne\b",
    r"\brencontre(?:r)?\s+(?:un\s+)?inconnu\b",
    r"\benvoie(?:-|\s)?moi\s+(?:ta|ton)\s+photo\b",
    r"\bnack(?:ed|é)\b",
)

# Prompt injection / jailbreak attempts.
INJECTION_PATTERNS: tuple[str, ...] = (
    r"\bignore(?:z|r)?\s+(?:les\s+)?(?:instructions|consignes)\b",
    r"\bsystem prompt\b",
    r"\bprompt syst[eè]me\b",
    r"\bcontourn(?:e|er)\s+(?:les\s+)?r[eè]gles\b",
    r"\bjoue(?:z|-)?\s+(?:un\s+)?autre r[oô]le\b",
    r"\bd[eé]sactive(?:r)?\s+(?:le\s+)?filtre\b",
    r"\bmode\s+d[eé]veloppeur\b",
)

SAFE_MESSAGE_UNSAFE = (
    "Je ne peux pas répondre à ce type de demande. Parle-en à un adulte de confiance si tu te sens en difficulté."
)

SAFE_MESSAGE_DISTRESS = (
    "Je suis vraiment désolé que tu te sentes ainsi. "
    "Ce n'est pas quelque chose que tu dois garder pour toi : parle-en tout de suite "
    "à un adulte de confiance, à tes parents ou à un enseignant."
)

SAFE_MESSAGE_INJECTION = "Je reste ton professeur scolaire. Reformule ta question sur ta leçon ou ton exercice."

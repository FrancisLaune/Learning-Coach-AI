"""Deterministic, reviewable LCAI-0012B pilot generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.content.factory import (
    AnswerKind,
    AnswerSpecification,
    CanonicalContentType,
    ContentGenerationRequest,
    CurriculumTarget,
    GeneratedContentCandidate,
    GenerationProvenance,
    PedagogicalIntent,
)


@dataclass(frozen=True, slots=True)
class PilotTask:
    prompt: str
    answer: Any
    explanation: str
    answer_kind: AnswerKind = AnswerKind.EXACT_TEXT
    computed: Any | None = None


@dataclass(frozen=True, slots=True)
class PilotSpecification:
    target: CurriculumTarget
    label: str
    reason: str
    foundation: PilotTask
    standard: PilotTask
    advanced: PilotTask
    misconception: str
    remediation: PilotTask
    hint: str


class DeterministicPilotGenerator:
    """A provider-independent generator backed by reviewed pilot specifications."""

    def __init__(self, specifications: tuple[PilotSpecification, ...]) -> None:
        self.specifications = {item.target.primary_skill_code: item for item in specifications}

    def generate(self, request: ContentGenerationRequest) -> tuple[GeneratedContentCandidate, ...]:
        specification = self.specifications[request.target.primary_skill_code]
        task = {
            1: specification.foundation,
            2: specification.standard,
            3: specification.advanced,
        }[request.difficulty]
        if request.content_type is CanonicalContentType.REMEDIATION:
            task = specification.remediation
        hints = () if request.content_type is CanonicalContentType.ASSESSMENT else (specification.hint,)
        role = {
            CanonicalContentType.GUIDED_PRACTICE: "guided",
            CanonicalContentType.WORKED_EXAMPLE: "worked",
            CanonicalContentType.PRACTICE: "independent",
            CanonicalContentType.ASSESSMENT: "evaluative",
            CanonicalContentType.DIAGNOSTIC: "diagnostic",
            CanonicalContentType.REMEDIATION: "remediation",
            CanonicalContentType.CHALLENGE: "challenge",
            CanonicalContentType.REVISION: "revision",
            CanonicalContentType.LESSON: "lesson",
        }[request.content_type]
        return (
            self._candidate(
                specification,
                request.content_type,
                request.pedagogical_intent,
                request.difficulty,
                task,
                hints,
                role,
            ),
        )

    @staticmethod
    def _candidate(
        specification: PilotSpecification,
        content_type: CanonicalContentType,
        intent: PedagogicalIntent,
        difficulty: int,
        task: PilotTask,
        hints: tuple[str, ...],
        role: str,
    ) -> GeneratedContentCandidate:
        skill_suffix = specification.target.primary_skill_code.removeprefix("SK-").replace("_", "-")
        code = f"PILOT-0012B-{skill_suffix}-{role.upper()}"
        provenance = GenerationProvenance(
            "deterministic_template",
            "lcai-0012b-reviewed-specifications",
            "1.0",
            "lcai-0012b-template-v1",
            "phase2-lcai-0011c",
        )
        return GeneratedContentCandidate(
            code=code,
            title=f"{specification.label} — {content_type.value}",
            instructions=_instructions(content_type),
            prompt=task.prompt,
            answer=AnswerSpecification(task.answer_kind, task.answer, independently_computed=task.computed),
            explanation=task.explanation,
            target=specification.target,
            content_type=content_type,
            pedagogical_intent=intent,
            difficulty=difficulty,
            provenance=provenance,
            hints=hints,
            family_code=f"PILOT-FAMILY-{skill_suffix}",
            variant_role=role,
            misconception_target=specification.misconception if role == "remediation" else None,
            metadata={
                "pilot": "LCAI-0012B",
                "review_required": True,
                "difficulty_basis": _difficulty_basis(difficulty),
            },
        )


def _instructions(content_type: CanonicalContentType) -> str:
    return {
        CanonicalContentType.LESSON: "Lis l'explication et reformule l'idée essentielle.",
        CanonicalContentType.GUIDED_PRACTICE: "Résous l'étape demandée en utilisant l'indice si nécessaire.",
        CanonicalContentType.WORKED_EXAMPLE: "Observe la démarche complète, puis vérifie chaque étape.",
        CanonicalContentType.PRACTICE: "Résous de manière autonome et justifie brièvement.",
        CanonicalContentType.ASSESSMENT: "Réponds sans aide et justifie brièvement.",
        CanonicalContentType.DIAGNOSTIC: "Réponds en montrant ta démarche afin d'identifier l'origine d'une erreur.",
        CanonicalContentType.REMEDIATION: "Corrige l'erreur ciblée en appliquant la méthode indiquée.",
        CanonicalContentType.CHALLENGE: "Choisis une stratégie et justifie toutes les étapes.",
        CanonicalContentType.REVISION: "Rappelle la méthode puis applique-la sans consulter la solution.",
    }[content_type]


def _difficulty_basis(level: int) -> str:
    return {
        1: "application directe, représentation familière et guidage",
        2: "application standard avec justification",
        3: "transfert, choix de méthode ou raisonnement en plusieurs étapes",
    }[level]


def pilot_specifications() -> tuple[PilotSpecification, ...]:
    """Reviewed 4e/3e cross-disciplinary source specifications."""
    return (
        _math(
            "FR-4E",
            "FRACT",
            "SK-ENR-MATHEMATICS-4E-FRACT-ADD",
            "Addition de fractions",
            ("Calcule 1/4 + 2/4.", "3/4", "Les dénominateurs sont identiques : 1 + 2 = 3."),
            ("Calcule 2/3 + 5/6.", "3/2", "2/3 = 4/6, donc 4/6 + 5/6 = 9/6 = 3/2."),
            (
                "Lina lit 2/5 d'un livre lundi et 1/3 mardi. Quelle fraction reste-t-il ?",
                "4/15",
                "2/5 + 1/3 = 6/15 + 5/15 = 11/15 ; il reste 4/15.",
            ),
            "additionner les numérateurs et les dénominateurs",
            (
                "Un élève écrit 1/2 + 1/3 = 2/5. Donne le résultat correct.",
                "5/6",
                "Il faut un dénominateur commun : 3/6 + 2/6 = 5/6.",
            ),
        ),
        _math(
            "FR-4E",
            "LITERAL",
            "SK-ENR-MATHEMATICS-4E-LITERAL-DISTRIBUTE",
            "Distributivité",
            ("Développe 3(x + 2).", "3x + 6", "On multiplie chaque terme par 3."),
            ("Développe puis réduis 4(2x - 3) + x.", "9x - 12", "4 × 2x - 4 × 3 + x = 8x - 12 + x."),
            (
                "Un rectangle mesure 2x + 3 sur x - 1. Exprime son périmètre réduit.",
                "6x + 4",
                "P = 2[(2x + 3) + (x - 1)] = 2(3x + 2) = 6x + 4.",
            ),
            "ne distribuer que sur le premier terme",
            ("Corrige : 5(x - 2) = 5x - 2.", "5x - 10", "Le facteur 5 multiplie aussi -2."),
        ),
        _math(
            "FR-4E",
            "PYTH",
            "SK-MATHEMATICS-4E-PYTH",
            "Théorème de Pythagore",
            ("Triangle ABC rectangle en A, AB=3 et AC=4. Calcule BC.", "5", "BC²=3²+4²=25, donc BC=5."),
            ("Triangle DEF rectangle en D, DE=5 et EF=13. Calcule DF.", "12", "DF²=13²-5²=144."),
            (
                "Une échelle de 6,5 m atteint un mur à 6 m. À quelle distance du mur est son pied ?",
                "2.5",
                "d²=6,5²-6²=6,25, donc d=2,5 m.",
            ),
            "additionner les longueurs au lieu de leurs carrés",
            (
                "Corrige l'affirmation : avec des côtés 6, 8 et 10, le triangle n'est pas rectangle.",
                "rectangle",
                "6²+8²=36+64=100=10² : la réciproque prouve qu'il est rectangle.",
            ),
        ),
        _math(
            "FR-4E",
            "PROP",
            "SK-MATHEMATICS-4E-PROP",
            "Proportionnalité",
            ("Trois cahiers coûtent 6 €. Combien coûte un cahier ?", "2", "6 ÷ 3 = 2 € par cahier."),
            ("Un article à 80 € augmente de 15 %. Quel est son nouveau prix ?", "92", "15 % de 80 vaut 12 ; 80+12=92."),
            (
                "Après une baisse de 20 %, un prix vaut 96 €. Quel était le prix initial ?",
                "120",
                "Le prix final représente 80 % : 96 ÷ 0,8 = 120.",
            ),
            "appliquer le pourcentage au mauvais montant de référence",
            (
                "Corrige : une baisse de 25 % sur 60 € donne 45 € de remise.",
                "15",
                "La remise est 0,25 × 60 = 15 € ; 45 € est le prix remisé.",
            ),
        ),
        _math(
            "FR-3E",
            "EQUATIONS",
            "SK-ENR-MATHEMATICS-3E-EQUATIONS-SOLVE",
            "Équations",
            ("Résous x + 7 = 12.", "5", "On soustrait 7 aux deux membres."),
            ("Résous 3x - 5 = 16.", "7", "3x=21, puis x=7."),
            ("Résous 4(2x - 1) = 3x + 16.", "4", "8x-4=3x+16, donc 5x=20 et x=4."),
            "changer de membre sans effectuer la même opération",
            ("Corrige : 2x + 6 = 14 donc x = 14 - 6 = 8.", "4", "Après 2x=8, il faut encore diviser par 2 : x=4."),
        ),
        _math(
            "FR-3E",
            "FUNCTIONS",
            "SK-MATHEMATICS-3E-FUNCTIONS",
            "Fonctions",
            ("Soit f(x)=2x+1. Calcule f(3).", "7", "f(3)=2×3+1=7."),
            ("Soit g(x)=3x-4. Détermine l'antécédent de 11.", "5", "3x-4=11, donc 3x=15 et x=5."),
            ("h(x)=x²-2x. Compare h(-2) et h(3).", "h(-2) > h(3)", "h(-2)=8 et h(3)=3, donc h(-2)>h(3)."),
            "confondre image et antécédent",
            ("Corrige : pour f(x)=x+4, l'antécédent de 9 est 13.", "5", "On cherche x tel que x+4=9, donc x=5."),
        ),
        _math(
            "FR-3E",
            "PROBA",
            "SK-ENR-MATHEMATICS-3E-PROBA-CALCULATE",
            "Probabilités",
            (
                "Une urne contient 3 boules rouges et 2 bleues. Probabilité de rouge ?",
                "3/5",
                "Il y a 3 issues favorables sur 5 équiprobables.",
            ),
            (
                "On lance un dé équilibré. Probabilité d'obtenir un multiple de 3 ?",
                "1/3",
                "Les issues favorables sont 3 et 6 : 2/6=1/3.",
            ),
            (
                "Deux pièces équilibrées sont lancées. Probabilité d'obtenir exactement une face ?",
                "1/2",
                "PF et FP sont deux issues sur quatre.",
            ),
            "compter les catégories plutôt que les issues",
            (
                "Une urne a 4 rouges et 1 bleue. Corrige P(bleue)=1/2.",
                "1/5",
                "Une seule boule bleue parmi cinq donne 1/5.",
            ),
        ),
        _math(
            "FR-3E",
            "ARITH",
            "SK-MATHEMATICS-3E-ARITH",
            "Arithmétique",
            ("Décompose 36 en facteurs premiers.", "2² × 3²", "36=4×9=2²×3²."),
            ("Rends 84/126 irréductible.", "2/3", "Le PGCD vaut 42 ; 84÷42=2 et 126÷42=3."),
            (
                "Deux alarmes sonnent toutes les 18 et 24 minutes. Après combien de minutes sonnent-elles ensemble ?",
                "72",
                "Le PPCM de 18 et 24 est 72.",
            ),
            "confondre diviseur commun et multiple commun",
            ("Corrige : le PGCD de 18 et 30 est 3.", "6", "Les diviseurs communs maximaux donnent PGCD=6."),
        ),
        *_text_specs(),
        *_other_specs(),
    )


def _target(grade: str, subject: str, chapter: str, skill: str) -> CurriculumTarget:
    return CurriculumTarget(f"FR-CYCLE4-{grade.removeprefix('FR-')}", grade, subject, chapter, skill)


def _math(
    grade: str,
    chapter_suffix: str,
    skill: str,
    label: str,
    foundation: tuple[str, Any, str],
    standard: tuple[str, Any, str],
    advanced: tuple[str, Any, str],
    misconception: str,
    remediation: tuple[str, Any, str],
) -> PilotSpecification:
    numeric = (
        AnswerKind.NUMERIC
        if all(isinstance(item[1], (int, float)) for item in (foundation, standard, advanced))
        else AnswerKind.EXACT_TEXT
    )

    def task(item: tuple[str, Any, str]) -> PilotTask:
        return PilotTask(item[0], item[1], item[2], numeric, item[1] if numeric else None)

    chapter = f"CH-MATHEMATICS-{grade.removeprefix('FR-')}-{chapter_suffix}"
    return PilotSpecification(
        _target(grade, "MATHEMATICS", chapter, skill),
        label,
        "priorité mathématique",
        task(foundation),
        task(standard),
        task(advanced),
        misconception,
        task(remediation),
        "Identifie d'abord la propriété ou l'opération utile.",
    )


def _spec(
    grade: str,
    subject: str,
    chapter: str,
    skill: str,
    label: str,
    foundation: tuple[str, Any, str],
    standard: tuple[str, Any, str],
    advanced: tuple[str, Any, str],
    misconception: str,
    remediation: tuple[str, Any, str],
    hint: str,
) -> PilotSpecification:
    def task(item: tuple[str, Any, str]) -> PilotTask:
        return PilotTask(item[0], item[1], item[2])

    return PilotSpecification(
        _target(grade, subject, chapter, skill),
        label,
        "validation interdisciplinaire",
        task(foundation),
        task(standard),
        task(advanced),
        misconception,
        task(remediation),
        hint,
    )


def _text_specs() -> tuple[PilotSpecification, ...]:
    return (
        _spec(
            "FR-3E",
            "FRENCH",
            "CH-FRENCH-3E-REWRITE",
            "SK-FRENCH-3E-REWRITE",
            "Réécriture",
            ("Réécris « Il arrive » avec « Ils ».", "Ils arrivent.", "Le sujet pluriel impose la terminaison -ent."),
            (
                "Réécris « Elle a fini son travail » avec « Elles ».",
                "Elles ont fini leur travail.",
                "Le sujet, l'auxiliaire et le déterminant changent.",
            ),
            (
                "Réécris « Je pensais qu'il viendrait » en commençant par « Nous ».",
                "Nous pensions qu'il viendrait.",
                "Le verbe principal change de personne sans modifier le référent de « il ».",
            ),
            "ne modifier que le pronom sujet",
            (
                "Corrige « Elles a terminé leurs exercices ».",
                "Elles ont terminé leurs exercices.",
                "L'auxiliaire s'accorde avec le sujet pluriel.",
            ),
            "Repère tous les mots dépendant du changement demandé.",
        ),
        _spec(
            "FR-3E",
            "FRENCH",
            "CH-FRENCH-3E-ARGUMENT",
            "SK-ENR-FRENCH-3E-ARGUMENT-ARGUMENT",
            "Argumentation",
            (
                "Dans « Il faut végétaliser la cour car les arbres apportent de l'ombre », relève l'argument.",
                "les arbres apportent de l'ombre",
                "La proposition introduite par « car » justifie la thèse.",
            ),
            (
                "Formule un argument en faveur du prêt de livres numériques.",
                "accès facilité aux livres",
                "Un argument recevable relie la mesure à un bénéfice explicite.",
            ),
            (
                "Thèse : « Les devoirs de groupe sont utiles ». Donne un argument, un exemple et une limite.",
                "argument + exemple + limite",
                "Une réponse structurée distingue justification, illustration et nuance.",
            ),
            "confondre exemple et argument",
            (
                "« Mon ami aime lire » suffit-il à prouver que la lecture devrait être quotidienne ?",
                "non",
                "Un cas individuel illustre mais ne constitue pas seul une justification générale.",
            ),
            "Demande-toi quelle raison générale soutient la thèse.",
        ),
        _spec(
            "FR-3E",
            "FRENCH",
            "CH-FRENCH-3E-CLAUSES",
            "SK-ENR-FRENCH-3E-CLAUSES-RELATIVE",
            "Subordonnée relative",
            (
                "Dans « Le livre que je lis est passionnant », relève la relative.",
                "que je lis",
                "Elle complète l'antécédent « livre ».",
            ),
            (
                "Dans « La ville où je suis né change », donne l'antécédent et la fonction de la relative.",
                "ville ; complément de l'antécédent",
                "« où je suis né » précise le nom « ville ».",
            ),
            (
                "Réunis « J'observe une étoile. Cette étoile brille. » avec une relative.",
                "J'observe une étoile qui brille.",
                "Le pronom relatif évite la répétition et devient sujet de « brille ».",
            ),
            "prendre toute la phrase pour la relative",
            (
                "Corrige : dans « L'élève qui répond explique », l'antécédent est « répond ».",
                "élève",
                "L'antécédent est le nom repris par « qui ».",
            ),
            "Cherche le nom repris par le pronom relatif.",
        ),
        _spec(
            "FR-3E",
            "FRENCH",
            "CH-FRENCH-3E-TEXTANALYSIS",
            "SK-ENR-FRENCH-3E-TEXTANALYSIS-INFER",
            "Inférence",
            (
                "« Nora referme son parapluie en entrant. » Quel temps fait-il dehors ?",
                "il pleut",
                "Le parapluie utilisé constitue un indice.",
            ),
            (
                "« La lumière était encore allumée, mais le café était froid. » Que peut-on déduire ?",
                "la personne est partie depuis un moment",
                "Le contraste entre lumière et café froid suggère un départ non immédiat.",
            ),
            (
                "« Il relut trois fois le message avant d'effacer sa réponse. » Déduis son état et justifie.",
                "il hésite",
                "Les relectures et l'effacement sont des indices d'hésitation.",
            ),
            "inventer sans citer d'indice",
            (
                "Peut-on déduire la couleur du téléphone dans la phrase précédente ?",
                "non",
                "Aucun indice textuel ne permet cette conclusion.",
            ),
            "Appuie chaque déduction sur un indice précis.",
        ),
        _spec(
            "FR-4E",
            "FRENCH",
            "CH-FRENCH-4E-SPELLING",
            "SK-ENR-FRENCH-4E-SPELLING-SV",
            "Accord sujet-verbe",
            ("Complète : « Les oiseaux ... (chanter). »", "chantent", "Le sujet « oiseaux » est au pluriel."),
            (
                "Accorde : « La liste des candidats ... (être) affichée. »",
                "est",
                "Le noyau du sujet est « liste », singulier.",
            ),
            (
                "Accorde : « Ni le directeur ni les élèves ne ... (vouloir) partir. »",
                "veulent",
                "Le sujet coordonné comprend plusieurs personnes.",
            ),
            "accorder avec le nom le plus proche",
            (
                "Corrige : « Le bruit des voitures dérangent les voisins. »",
                "Le bruit des voitures dérange les voisins.",
                "Le noyau « bruit » commande le singulier.",
            ),
            "Identifie le noyau du groupe sujet.",
        ),
        _spec(
            "FR-4E",
            "FRENCH",
            "CH-FRENCH-4E-VOCAB",
            "SK-ENR-FRENCH-4E-VOCAB-CONTEXT",
            "Sens en contexte",
            (
                "Dans « une lumière vive », que signifie « vive » ?",
                "intense",
                "Le contexte lumineux sélectionne le sens « intense ».",
            ),
            (
                "Dans « Il nourrit un vif regret », explique « vif ».",
                "très fort",
                "Le nom abstrait « regret » exclut le sens lié à la vitesse.",
            ),
            (
                "Explique le changement de sens de « lourd » dans « valise lourde » et « silence lourd ».",
                "poids ; atmosphère pesante",
                "Le premier sens est concret, le second figuré.",
            ),
            "choisir le premier sens du dictionnaire",
            (
                "« Une décision éclairée » signifie-t-elle lumineuse ?",
                "non",
                "Ici « éclairée » signifie réfléchie et bien informée.",
            ),
            "Observe les mots associés et le sens global.",
        ),
        _spec(
            "FR-4E",
            "FRENCH",
            "CH-FRENCH-4E-NARRATIVE",
            "SK-ENR-FRENCH-4E-NARRATIVE-VIEWPOINT",
            "Point de vue narratif",
            (
                "« Je tremblais sans comprendre ce bruit. » Quel point de vue ?",
                "interne",
                "Le lecteur perçoit les sensations du narrateur-personnage.",
            ),
            (
                "Un récit décrit seulement les gestes visibles d'un inconnu. Quel point de vue ?",
                "externe",
                "Le narrateur n'accède pas aux pensées.",
            ),
            (
                "Réécris « Léa ignorait que Paul préparait son départ » en point de vue interne de Léa.",
                "Léa ne comprenait pas les silences de Paul.",
                "La réécriture supprime l'information inaccessible à Léa.",
            ),
            "donner au personnage une information inaccessible",
            (
                "Pourquoi « Tom ne le savait pas, mais le train était annulé » n'est-il pas strictement interne à Tom ?",
                "le narrateur sait plus que Tom",
                "L'annulation est une information hors de la conscience de Tom.",
            ),
            "Vérifie quelles informations sont accessibles au personnage.",
        ),
        _spec(
            "FR-4E",
            "FRENCH",
            "CH-FRENCH-4E-GRAMMAR",
            "SK-ENR-FRENCH-4E-GRAMMAR-FUNCTIONS",
            "Grammaire de la phrase",
            (
                "Dans « Le chat dort », donne le sujet.",
                "Le chat",
                "Le groupe nominal placé avant le verbe commande l'accord.",
            ),
            (
                "Dans « Demain, les élèves rendront leur dossier », donne la fonction de « Demain ».",
                "complément circonstanciel de temps",
                "Le groupe situe l'action dans le temps.",
            ),
            (
                "Analyse « Le livre que tu m'as prêté me passionne » : sujet du verbe principal.",
                "Le livre que tu m'as prêté",
                "Toute la construction nominale avec sa relative est sujet de « passionne ».",
            ),
            "confondre nature et fonction",
            (
                "Dans « Elle parle doucement », « doucement » est-il adjectif ?",
                "non, adverbe",
                "Il modifie le verbe « parle » et reste invariable.",
            ),
            "Distingue ce qu'est le mot de son rôle dans la phrase.",
        ),
    )


def _other_specs() -> tuple[PilotSpecification, ...]:
    return (
        _spec(
            "FR-3E",
            "ENGLISH",
            "CH-ENGLISH-3E-PAST",
            "SK-ENGLISH-3E-PAST",
            "Past simple",
            ("Complete: Yesterday, I ... (play) football.", "played", "A regular verb takes -ed in the past simple."),
            ("Put in the past: She goes home.", "She went home.", "« go » is irregular: went."),
            (
                "Write the negative and question forms of « They saw it ».",
                "They did not see it. / Did they see it?",
                "After did, the lexical verb returns to its base form.",
            ),
            "keeping the past form after did",
            ("Correct: « Did he went home? »", "Did he go home?", "The auxiliary did carries the past tense."),
            "Après « did », utilise la base verbale.",
        ),
        _spec(
            "FR-3E",
            "SPANISH",
            "CH-SPANISH-3E-PRESENT",
            "SK-ENR-SPANISH-3E-PRESENT-IRREGULAR",
            "Grammaire espagnole",
            ("Complète : « Yo ... estudiante. » (ser)", "soy", "La première personne de « ser » est « soy »."),
            (
                "Complète : « Nosotros ... en Madrid hoy. » (estar)",
                "estamos",
                "Une localisation circonstancielle utilise « estar ».",
            ),
            (
                "Choisis ser ou estar : « La fiesta ... en la plaza y ... muy animada. »",
                "es ; está",
                "« ser » localise un événement ; « estar » décrit son état.",
            ),
            "utiliser ser et estar comme synonymes",
            (
                "Corrige : « Madrid es en España ».",
                "Madrid está en España.",
                "La localisation d'un lieu se construit avec « estar ».",
            ),
            "Demande-toi s'il s'agit d'identité, d'état ou de localisation.",
        ),
        _spec(
            "FR-4E",
            "HISTORY",
            "CH-HISTORY-4E-19TH",
            "SK-ENR-HISTORY-4E-19TH-INDUSTRIALIZATION",
            "Industrialisation",
            (
                "Quelle énergie alimente principalement les premières machines à vapeur ?",
                "le charbon",
                "La combustion du charbon chauffe l'eau qui produit la vapeur.",
            ),
            (
                "Cite une transformation du travail liée à l'industrialisation.",
                "développement du travail en usine",
                "Les machines et la concentration de la production transforment l'organisation du travail.",
            ),
            (
                "Relie charbon, chemin de fer et urbanisation au XIXe siècle.",
                "le charbon alimente les machines et le rail, qui concentre activités et population",
                "La réponse construit une chaîne causale sans réduire l'industrialisation à une invention.",
            ),
            "réduire l'industrialisation à une seule invention",
            (
                "Pourquoi la machine à vapeur seule n'explique-t-elle pas toute l'industrialisation ?",
                "elle dépend aussi des capitaux, ressources, transports et travailleurs",
                "Le phénomène combine innovations, ressources et transformations sociales.",
            ),
            "Construis des liens de cause à conséquence.",
        ),
        _spec(
            "FR-4E",
            "GEOGRAPHY",
            "CH-GEOGRAPHY-4E-URBANIZATION",
            "SK-ENR-GEOGRAPHY-4E-URBANIZATION-GROWTH",
            "Croissance urbaine",
            (
                "Que mesure le taux d'urbanisation ?",
                "la part de la population vivant en ville",
                "C'est un rapport entre population urbaine et population totale.",
            ),
            (
                "Une ville passe de 1 à 1,4 million d'habitants. Décris l'évolution.",
                "croissance urbaine de 40 %",
                "L'augmentation est 0,4/1 = 40 %.",
            ),
            (
                "Distingue croissance urbaine et étalement urbain.",
                "population urbaine ; extension de la surface bâtie",
                "Les deux phénomènes peuvent être liés mais ne mesurent pas la même chose.",
            ),
            "confondre population et surface urbanisée",
            (
                "Une ville s'étend mais sa population stagne : y a-t-il croissance démographique ?",
                "non",
                "Il y a étalement sans hausse de population.",
            ),
            "Identifie précisément l'indicateur observé.",
        ),
        _spec(
            "FR-3E",
            "EMC",
            "CH-EMC-3E-DEMOCRACY",
            "SK-ENR-EMC-3E-DEMOCRACY-ELECTION",
            "Élection démocratique",
            (
                "Quel principe garantit que chaque électeur dispose du même poids ?",
                "égalité du suffrage",
                "Chaque voix compte de manière égale.",
            ),
            (
                "Pourquoi le secret du vote protège-t-il la liberté électorale ?",
                "il limite pressions et représailles",
                "L'électeur peut choisir sans devoir révéler son choix.",
            ),
            (
                "Explique pourquoi une élection régulière sans pluralisme ne suffit pas à définir une démocratie.",
                "les électeurs doivent pouvoir choisir entre des options libres et concurrentes",
                "La périodicité est nécessaire mais pas suffisante.",
            ),
            "réduire la démocratie au seul fait de voter",
            (
                "Une seule candidature imposée suffit-elle pour une élection démocratique ?",
                "non",
                "Sans pluralisme ni liberté de choix, le scrutin ne permet pas l'alternance.",
            ),
            "Vérifie liberté, égalité, secret et pluralisme.",
        ),
        _spec(
            "FR-4E",
            "SVT",
            "CH-SVT-4E-EARTH",
            "SK-ENR-SVT-4E-EARTH-EARTHQUAKE",
            "Séismes",
            (
                "Comment nomme-t-on le point de rupture en profondeur ?",
                "foyer",
                "Le foyer est le lieu de libération initiale d'énergie.",
            ),
            (
                "Pourquoi les dégâts sont-ils souvent forts près de l'épicentre ?",
                "les ondes y parcourent généralement moins de distance",
                "L'épicentre est la projection en surface du foyer.",
            ),
            (
                "Deux villes à même distance du foyer subissent des dégâts différents. Donne une explication possible.",
                "vulnérabilité des bâtiments ou nature du sol différente",
                "Le risque dépend de l'aléa et de la vulnérabilité.",
            ),
            "confondre magnitude et dégâts observés",
            (
                "Un séisme de même magnitude cause-t-il toujours les mêmes dégâts ?",
                "non",
                "Profondeur, distance, sols et vulnérabilité modifient les effets.",
            ),
            "Distingue le phénomène physique de ses conséquences.",
        ),
        _spec(
            "FR-4E",
            "PHYSICS_CHEMISTRY",
            "CH-PHYSICS_CHEMISTRY-4E-CHEMISTRY",
            "SK-ENR-PHYSICS_CHEMISTRY-4E-CHEMISTRY-CONSERVATION",
            "Conservation de la matière",
            (
                "Dans un récipient fermé, 5 g de A réagissent avec 3 g de B. Masse finale ?",
                "8 g",
                "La masse totale se conserve dans le système fermé.",
            ),
            (
                "Pourquoi une bougie semble-t-elle perdre de la masse à l'air libre ?",
                "des produits gazeux se dispersent",
                "Le système observé est ouvert ; la matière ne disparaît pas.",
            ),
            (
                "Une réaction fermée donne 12,0 g avant et 11,7 g après. Interprète l'écart.",
                "incertitude ou fuite expérimentale",
                "La loi attend la conservation ; l'écart signale le protocole ou la mesure.",
            ),
            "croire que la matière disparaît pendant une réaction",
            (
                "Corrige : « Le gaz formé ne pèse rien ».",
                "un gaz possède une masse",
                "Dans un système fermé, sa masse contribue au bilan.",
            ),
            "Définis d'abord les limites du système étudié.",
        ),
        _spec(
            "FR-3E",
            "HISTORY",
            "CH-HISTORY-3E-AFTER1945",
            "SK-ENR-HISTORY-3E-AFTER1945-COLD_WAR",
            "Guerre froide",
            (
                "Quelles sont les deux superpuissances au début de la guerre froide ?",
                "États-Unis et URSS",
                "Elles structurent deux blocs rivaux après 1945.",
            ),
            (
                "Pourquoi parle-t-on de guerre « froide » ?",
                "les deux superpuissances évitent un affrontement militaire direct",
                "La rivalité passe par crises, propagande et conflits indirects.",
            ),
            (
                "Explique comment la crise de Cuba illustre à la fois confrontation et dissuasion.",
                "installation de missiles, blocus et retrait négocié face au risque nucléaire",
                "La tension extrême conduit à éviter l'affrontement direct.",
            ),
            "croire qu'il n'y a eu aucun conflit armé",
            (
                "La guerre de Corée contredit-elle le terme « froide » ?",
                "non, c'est un conflit indirect impliquant les blocs",
                "Les superpuissances s'affrontent par alliés sans guerre directe entre elles.",
            ),
            "Distingue affrontement direct et conflits périphériques.",
        ),
    )

"""Build the reviewed LCAI-0009 manifest from explicit internal editorial records.

This script does not invent or randomize content. The records below are the
version-controlled source; JSON is only the normalized import artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "resources" / "catalog" / "lcai_0009_catalog.json"
CREATED_ON = "2026-07-23"
AUTHOR = "Learning Coach AI editorial team"
REVIEWER = "demo-content-reviewer"
APPROVER = "demo-content-approver"

# subject, grade, domain, short code, title, prompt, answer, explanation
TOPICS = [
    (
        "MATHEMATICS",
        "FR-4E",
        "NUMBERS",
        "RELNUM",
        "Nombres relatifs",
        "Calculer (-7) + 12 - 5.",
        "0",
        "On additionne d’abord -7 et 12, ce qui donne 5, puis 5 - 5 = 0.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "NUMBERS",
        "FRACT",
        "Fractions",
        "Calculer 2/3 + 5/6 et donner une fraction simplifiée.",
        "3/2",
        "On prend le dénominateur 6 : 2/3 = 4/6, donc 4/6 + 5/6 = 9/6 = 3/2.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "ALGEBRA",
        "LITERAL",
        "Calcul littéral",
        "Réduire 3x + 5 - x + 2.",
        "2x + 7",
        "On regroupe les termes en x puis les constantes : 3x - x = 2x et 5 + 2 = 7.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "NUMBERS",
        "PROP",
        "Proportionnalité",
        "Trois cahiers coûtent 7,50 €. Combien coûtent cinq cahiers au même prix unitaire ?",
        "12,50 €",
        "Un cahier coûte 7,50 / 3 = 2,50 €, donc cinq coûtent 5 × 2,50 = 12,50 €.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "NUMBERS",
        "POWERS",
        "Puissances",
        "Écrire 2 × 2 × 2 × 2 × 2 sous forme d’une puissance.",
        "2^5",
        "Le facteur 2 apparaît cinq fois : l’écriture est 2 puissance 5.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "GEOMETRY",
        "PYTH",
        "Théorème de Pythagore",
        "Un triangle rectangle a pour côtés de l’angle droit 6 cm et 8 cm. Calculer l’hypoténuse.",
        "10 cm",
        "Le carré de l’hypoténuse vaut 6² + 8² = 36 + 64 = 100, donc l’hypoténuse mesure 10 cm.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "DATA",
        "STATS",
        "Statistiques",
        "Calculer la moyenne de 8, 10, 12 et 14.",
        "11",
        "La somme vaut 44 et il y a quatre valeurs : 44 / 4 = 11.",
    ),
    (
        "MATHEMATICS",
        "FR-4E",
        "GEOMETRY",
        "VOLUMES",
        "Conversions et volumes",
        "Convertir 2,5 litres en centilitres.",
        "250 cL",
        "Un litre vaut 100 centilitres, donc 2,5 × 100 = 250 cL.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "ALGEBRA",
        "EQUATIONS",
        "Équations",
        "Résoudre 3x + 4 = 19.",
        "x = 5",
        "On soustrait 4 : 3x = 15, puis on divise par 3 : x = 5.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "ALGEBRA",
        "FUNCTIONS",
        "Fonctions",
        "Pour f(x) = 2x - 3, calculer f(5).",
        "7",
        "On remplace x par 5 : f(5) = 2 × 5 - 3 = 7.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "DATA",
        "PROBA",
        "Probabilités",
        "Un sac contient 3 boules rouges et 2 bleues. Quelle est la probabilité de tirer une boule bleue ?",
        "2/5",
        "Deux issues favorables sur cinq boules équiprobables donnent une probabilité de 2/5.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "DATA",
        "MEDIAN",
        "Statistiques et médiane",
        "Déterminer la médiane de 3, 4, 7, 9 et 12.",
        "7",
        "Les valeurs sont ordonnées et la valeur centrale, en troisième position, est 7.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "GEOMETRY",
        "THALES",
        "Théorème de Thalès",
        "Deux longueurs correspondantes valent 3 cm et 5 cm. Une longueur homologue vaut 6 cm dans la petite figure. Quelle est sa longueur dans la grande ?",
        "10 cm",
        "Le coefficient d’agrandissement est 5/3 ; la longueur cherchée vaut 6 × 5/3 = 10 cm.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "GEOMETRY",
        "TRIGO",
        "Trigonométrie",
        "Dans un triangle rectangle, le côté opposé à un angle mesure 3 cm et l’hypoténuse 6 cm. Donner le sinus de l’angle.",
        "1/2",
        "Le sinus est opposé sur hypoténuse : 3/6 = 1/2.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "NUMBERS",
        "ARITH",
        "Arithmétique",
        "Décomposer 84 en produit de facteurs premiers.",
        "2^2 × 3 × 7",
        "84 = 2 × 42 = 2 × 2 × 21 = 2² × 3 × 7.",
    ),
    (
        "MATHEMATICS",
        "FR-3E",
        "ALGEBRA",
        "BREVETPROB",
        "Problème à plusieurs étapes",
        "Un article à 80 € bénéficie d’une réduction de 15 %. Quel est son nouveau prix ?",
        "68 €",
        "La réduction vaut 80 × 0,15 = 12 €, donc le prix final est 80 - 12 = 68 €.",
    ),
    (
        "FRENCH",
        "FR-4E",
        "READING",
        "COMPREHENSION",
        "Compréhension",
        "Dans « La pluie cesse ; Lina ferme son parapluie », quel fait explique l’action de Lina ?",
        "La pluie cesse.",
        "Le point-virgule relie la fin de la pluie à la fermeture du parapluie.",
    ),
    (
        "FRENCH",
        "FR-4E",
        "LANGUAGE_STUDY",
        "GRAMMAR",
        "Grammaire",
        "Dans « Les élèves attentifs écoutent », identifier le sujet du verbe.",
        "Les élèves attentifs",
        "Le groupe nominal « Les élèves attentifs » commande l’accord du verbe « écoutent ».",
    ),
    (
        "FRENCH",
        "FR-4E",
        "LANGUAGE_STUDY",
        "CONJUGATION",
        "Conjugaison",
        "Conjuguer « finir » à l’imparfait, première personne du pluriel.",
        "nous finissions",
        "Le radical finiss- reçoit la terminaison -ions : nous finissions.",
    ),
    (
        "FRENCH",
        "FR-4E",
        "LANGUAGE_STUDY",
        "SPELLING",
        "Orthographe",
        "Compléter : « Elles se sont ... tôt. » avec le participe passé de lever.",
        "levées",
        "Avec le verbe pronominal employé ici, le participe passé s’accorde avec le sujet féminin pluriel.",
    ),
    (
        "FRENCH",
        "FR-4E",
        "WRITING",
        "VOCAB",
        "Vocabulaire précis",
        "Remplacer « faire un choix » par un verbe de sens équivalent.",
        "choisir",
        "Le verbe « choisir » remplace précisément la locution « faire un choix ».",
    ),
    (
        "FRENCH",
        "FR-4E",
        "WRITING",
        "NARRATIVE",
        "Rédaction narrative",
        "Écrire une phrase qui situe clairement une action après une autre en utilisant « ensuite ».",
        "Réponse rédigée contenant « ensuite ».",
        "Le connecteur « ensuite » marque explicitement la succession des actions.",
    ),
    (
        "FRENCH",
        "FR-3E",
        "READING",
        "TEXTANALYSIS",
        "Analyse de texte",
        "Dans « Le silence pesait sur la salle », quelle figure attribue une propriété physique au silence ?",
        "une métaphore",
        "Le poids est transféré au silence sans outil de comparaison : il s’agit d’une métaphore.",
    ),
    (
        "FRENCH",
        "FR-3E",
        "LANGUAGE_STUDY",
        "CLAUSES",
        "Analyse grammaticale",
        "Dans « Je partirai quand le train arrivera », identifier la proposition subordonnée.",
        "quand le train arrivera",
        "Introduite par « quand », elle complète le verbe principal en indiquant le temps.",
    ),
    (
        "FRENCH",
        "FR-3E",
        "LANGUAGE_STUDY",
        "TENSES",
        "Conjugaison complexe",
        "Conjuguer « venir » au plus-que-parfait, troisième personne du singulier.",
        "il ou elle était venu(e)",
        "Le plus-que-parfait associe l’imparfait de l’auxiliaire et le participe passé.",
    ),
    (
        "FRENCH",
        "FR-3E",
        "WRITING",
        "ARGUMENT",
        "Argumentation",
        "Transformer « Il faut lire » en thèse accompagnée d’un argument précis.",
        "Réponse argumentée reliant la lecture à un bénéfice précis.",
        "Une argumentation associe une position claire à une raison explicite et pertinente.",
    ),
    (
        "FRENCH",
        "FR-3E",
        "LANGUAGE_STUDY",
        "REWRITE",
        "Réécriture",
        "Réécrire « Il avance et regarde autour de lui » avec le sujet « elles ».",
        "Elles avancent et regardent autour d’elles.",
        "Les deux verbes prennent -ent et le pronom tonique devient « elles ».",
    ),
    (
        "FRENCH",
        "FR-3E",
        "WRITING",
        "BREVETWRITE",
        "Rédaction structurée",
        "Donner les trois parties minimales d’un paragraphe argumenté.",
        "idée, argument ou explication, exemple",
        "Un paragraphe construit annonce l’idée, la justifie et l’illustre.",
    ),
    (
        "HISTORY",
        "FR-3E",
        "CONTEMPORARY_HISTORY",
        "HISTREP",
        "Repères historiques",
        "Classer dans l’ordre chronologique : armistice de 1918, appel du 18 juin 1940, traité de Rome de 1957.",
        "1918, 1940, 1957",
        "Les dates fournies permettent un classement croissant sans ajouter d’interprétation.",
    ),
    (
        "GEOGRAPHY",
        "FR-3E",
        "TERRITORIES",
        "GEOSCALE",
        "Échelles territoriales",
        "Classer du plus local au plus large : commune, région, État.",
        "commune, région, État",
        "La commune appartient à une région, elle-même incluse dans l’État.",
    ),
    (
        "PHYSICS_CHEMISTRY",
        "FR-3E",
        "ENERGY",
        "SPEED",
        "Vitesse moyenne",
        "Un cycliste parcourt 12 km en 30 minutes. Calculer sa vitesse moyenne en km/h.",
        "24 km/h",
        "Trente minutes valent une demi-heure ; 12 / 0,5 = 24 km/h.",
    ),
    (
        "SVT",
        "FR-3E",
        "LIVING_WORLD",
        "CELL",
        "Organisation du vivant",
        "Quelle structure délimite une cellule et contrôle les échanges avec son milieu ?",
        "la membrane cellulaire",
        "La membrane cellulaire sépare le contenu cellulaire du milieu et régule les échanges.",
    ),
    (
        "ENGLISH",
        "FR-3E",
        "LANGUAGE",
        "PAST",
        "Past simple",
        "Complete: “Yesterday, she ... to school.” with the past form of “go”.",
        "went",
        "The simple past of the irregular verb “go” is “went”.",
    ),
    (
        "SPANISH",
        "FR-3E",
        "LANGUAGE",
        "PRESENT",
        "Présent espagnol",
        "Compléter : « Nosotros ... español. » avec le présent de « hablar ».",
        "hablamos",
        "À la première personne du pluriel, hablar devient « hablamos ».",
    ),
]


def build() -> dict[str, Any]:
    programs = [
        {
            "code": "FR-CYCLE4-4E",
            "version": "2026-demo",
            "label": "Parcours ciblé de révision de quatrième",
            "grade_code": "FR-4E",
            "valid_from": "2026-09-01",
            "subjects": sorted({topic[0] for topic in TOPICS if topic[1] == "FR-4E"}),
        },
        {
            "code": "FR-CYCLE4-3E",
            "version": "2026-demo",
            "label": "Parcours ciblé de troisième et préparation au brevet",
            "grade_code": "FR-3E",
            "valid_from": "2026-09-01",
            "exam_type": "DNB",
            "subjects": sorted({topic[0] for topic in TOPICS if topic[1] == "FR-3E"}),
        },
    ]
    chapters: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    subskills: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    sequence: dict[tuple[str, str], int] = {}
    for index, (subject, grade, domain, short, title, prompt, answer, explanation) in enumerate(TOPICS, 1):
        sequence[(subject, grade)] = sequence.get((subject, grade), 0) + 1
        position = sequence[(subject, grade)]
        grade_short = "4E" if grade == "FR-4E" else "3E"
        chapter_code = f"CH-{subject}-{grade_short}-{short}"
        skill_code = f"SK-{subject}-{grade_short}-{short}"
        program_code = "FR-CYCLE4-4E" if grade == "FR-4E" else "FR-CYCLE4-3E"
        exam = grade == "FR-3E" and subject in {
            "MATHEMATICS",
            "FRENCH",
            "HISTORY",
            "GEOGRAPHY",
            "PHYSICS_CHEMISTRY",
            "SVT",
        }
        bridge_topics = {
            "FRACT",
            "LITERAL",
            "PROP",
            "POWERS",
            "PYTH",
            "COMPREHENSION",
            "GRAMMAR",
            "CONJUGATION",
            "NARRATIVE",
        }
        transition = subject in {"MATHEMATICS", "FRENCH"} and (
            grade == "FR-3E" or (grade == "FR-4E" and short in bridge_topics)
        )
        chapters.append(
            {
                "code": chapter_code,
                "program_code": program_code,
                "subject_code": subject,
                "domain_code": domain,
                "grade_code": grade,
                "title": title,
                "description": f"Chapitre ciblé et non exhaustif : {title}.",
                "sequence_order": position,
                "expected_duration_minutes": 90,
                "difficulty_min": 1,
                "difficulty_max": 4,
                "exam_relevant": exam,
                "transition_relevant": transition,
                "effective_from": "2026-09-01",
            }
        )
        skills.append(
            {
                "code": skill_code,
                "chapter_code": chapter_code,
                "grade_code": grade,
                "title": f"Mobiliser : {title}",
                "description": f"Résoudre une tâche courte et vérifiable portant sur {title.lower()}.",
                "observable_outcome": f"L’apprenant fournit une réponse justifiée pour une tâche de {title.lower()}.",
                "sequence_order": 1,
                "difficulty": 3,
                "importance": 0.9 if subject in {"MATHEMATICS", "FRENCH"} else 0.7,
                "exam_relevant": exam,
                "transition_relevant": transition,
                "tags": ["core_skill"] + (["brevet"] if exam else []),
            }
        )
        subskills.append(
            {
                "code": f"SUB-{subject}-{grade_short}-{short}",
                "skill_code": skill_code,
                "title": f"Application guidée : {title}",
                "description": f"Appliquer une méthode explicite liée à {title.lower()}.",
                "sequence_order": 1,
            }
        )
        tags = ["revision", "core_skill"]
        objectives = ["revision", "consolidation", "long_term_mastery"]
        exam_compatibility: list[str] = []
        transitions: list[str] = []
        if exam:
            tags.append("brevet")
            objectives.extend(["preparation_brevet", "exam"])
            exam_compatibility.append("BREVET")
        if transition:
            tags.extend(["transition_ready", "next_grade_preparation"])
            objectives.append("preparation_next_grade")
            transitions.extend(["transition_ready", "next_grade_preparation"])
        if index % 5 == 0 or short == "FRACT":
            tags.extend(["remediation", "prerequisite_bridge"])
            objectives.append("catch_up")
            transitions.append("prerequisite_bridge")
        for variant in (1, 2):
            worked = variant == 1
            evaluative = variant == 2 or index <= 6
            code = f"CONTENT-{subject}-{grade_short}-{short}-{variant}"
            statement = prompt if variant == 2 else f"Étudier cet exemple guidé puis répondre : {prompt}"
            contents.append(
                {
                    "code": code,
                    "version": 1,
                    "title": f"{title} — {'exemple corrigé' if worked else 'activité'}",
                    "summary": f"Contenu interne ciblé sur {title.lower()}, sans prétention de couverture exhaustive.",
                    "subject_code": subject,
                    "chapter_code": chapter_code,
                    "skill_code": skill_code,
                    "subskill_code": f"SUB-{subject}-{grade_short}-{short}",
                    "content_type": "worked_example" if worked else ("exam_practice" if exam else "exercise"),
                    "activity_type": "exam_practice"
                    if exam and not worked
                    else ("remediation" if "remediation" in tags else "revision"),
                    "objective": f"Résoudre et expliquer une tâche portant sur {title.lower()}.",
                    "instructions": "Lire attentivement, produire la réponse puis comparer avec la correction structurée.",
                    "difficulty": 2 if worked else 3,
                    "difficulty_rationale": {
                        "steps": 2 if worked else 3,
                        "notions": 1,
                        "autonomy": "guided" if worked else "standard",
                        "reasoning": "application",
                    },
                    "duration_minutes": 10 if worked else 15,
                    "min_duration_minutes": 5 if worked else 10,
                    "max_duration_minutes": 15 if worked else 20,
                    "expected_attempts": 1,
                    "calculator_allowed": subject == "MATHEMATICS" and short in {"PYTH", "THALES", "TRIGO"},
                    "tags": sorted(set(tags + (["method"] if worked else []))),
                    "objective_compatibility": sorted(set(objectives)),
                    "exam_compatibility": exam_compatibility,
                    "transition_markers": transitions,
                    "compatibility": {
                        "revision": True,
                        "remediation": "remediation" in tags,
                        "transition": transition,
                        "exam": exam,
                        "brevet": exam,
                        "bac": False,
                        "diagnostic": False,
                        "homework": True,
                        "assessment": evaluative,
                    },
                    "prerequisites": [],
                    "pedagogical_strategy": "worked_example" if worked else "retrieval_practice",
                    "cognitive_demand": "understand" if worked else "apply",
                    "question": {
                        "statement": statement,
                        "response_type": "short_text",
                        "answer": answer,
                        "evaluative": evaluative,
                    },
                    "solution": {
                        "explanation": explanation,
                        "method": "Identifier les données utiles, appliquer la règle adaptée et vérifier la réponse.",
                        "steps": ["Repérer la notion et les données utiles.", explanation],
                        "advice": "Vérifier que la réponse traite exactement la consigne.",
                        "accepted_variants": [],
                    },
                    "hints": [
                        {
                            "order": 1,
                            "text": f"Repérer la règle ou l’indice principal lié à {title.lower()}.",
                            "penalty": 0.1,
                            "disclosure": 1,
                        }
                    ],
                    "common_errors": ["Réponse incomplète", "Justification absente"],
                    "author_source": AUTHOR,
                    "license_or_origin": "Contenu original interne — licence projet",
                    "created_on": CREATED_ON,
                    "reviewed_on": CREATED_ON,
                    "reviewer": REVIEWER,
                    "approver": APPROVER,
                    "status": "approved",
                }
            )
    relations: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[str]] = {}
    for skill in skills:
        subject = skill["code"].split("-")[1]
        grade = skill["grade_code"]
        grouped.setdefault((subject, grade), []).append(skill["code"])
    for (subject, grade), codes in grouped.items():
        for prerequisite, target in zip(codes, codes[1:], strict=False):
            relations.append(_relation(prerequisite, target, "required", "current_level"))
        if subject in {"MATHEMATICS", "FRENCH"} and grade == "FR-3E":
            prior = grouped[(subject, "FR-4E")]
            for prerequisite, target in zip(prior, codes, strict=False):
                relations.append(_relation(prerequisite, target, "transition", "next_grade_preparation"))
    brevet_skills = [skill["code"] for skill in skills if skill["grade_code"] == "FR-3E" and skill["exam_relevant"]]
    exam_references = [
        {
            "code": "DNB-DEMO-2027",
            "title": "Référentiel ciblé de préparation au brevet — lot de démonstration",
            "grade_code": "FR-3E",
            "subjects": ["MATHEMATICS", "FRENCH", "HISTORY", "GEOGRAPHY", "PHYSICS_CHEMISTRY", "SVT"],
            "domains": sorted({topic[2] for topic in TOPICS if topic[1] == "FR-3E"}),
            "preparation_phases": ["consolidation", "practice", "review"],
            "effective_year": 2027,
            "source_reference": "Référentiel interne ciblé ; aucun coefficient officiel encodé.",
            "skills": brevet_skills,
        }
    ]
    return {
        "catalog_version": "1.0",
        "scope_note": "Lot ciblé 4e, transition 4e→3e, 3e et brevet ; il ne constitue pas un programme complet.",
        "programs": programs,
        "chapters": chapters,
        "skills": skills,
        "subskills": subskills,
        "relations": relations,
        "exam_references": exam_references,
        "contents": contents,
    }


def _relation(prerequisite: str, target: str, relation_type: str, progression_role: str) -> dict[str, Any]:
    return {
        "prerequisite": prerequisite,
        "target": target,
        "relation_type": relation_type,
        "progression_role": progression_role,
        "strength": 0.8,
        "mandatory": relation_type == "required",
        "minimum_mastery_threshold": 0.7,
        "rationale": "La compétence préalable fournit une méthode ou une notion réutilisée par la cible.",
        "source": "Cartographie éditoriale interne LCAI-0009",
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()

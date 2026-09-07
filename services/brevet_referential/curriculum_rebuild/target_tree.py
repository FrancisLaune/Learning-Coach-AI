"""CANONICAL target curriculum for DNB 2027 (3e, année scolaire 2026-2027).

Sources réglementaires retenues :
- Maths / Français : BO juillet 2020, cycle 4 (pas le programme 2026, applicable en 3e seulement en 2028-2029).
- Histoire-géographie 3e : thèmes du programme en vigueur pour la session DNB 2027.
- EMC : BO 2024 applicable en 3e dès 2026-2027.
"""

from __future__ import annotations

from typing import Any

CORE_SUBJECTS = (
    "FRENCH",
    "MATHEMATICS",
    "HISTORY",
    "GEOGRAPHY",
    "EMC",
    "PHYSICS_CHEMISTRY",
    "SVT",
    "TECHNOLOGY",
)


def _ss(code: str, name: str) -> dict[str, str]:
    return {"code": code, "name": name}


def _sk(code: str, name: str, *subs: tuple[str, str]) -> dict[str, Any]:
    return {"code": code, "name": name, "subskills": [_ss(c, n) for c, n in subs]}


def _ch(
    code: str,
    name: str,
    importance: str,
    aliases: list[str],
    skills: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "importance": importance,
        "legacy_aliases": aliases,
        "skills": skills,
    }


def _dom(code: str, name: str, sort_order: int, chapters: list[dict[str, Any]]) -> dict[str, Any]:
    return {"code": code, "name": name, "sort_order": sort_order, "chapters": chapters}


# ---------------------------------------------------------------------------
# MATHEMATICS — BO juillet 2020 cycle 4
# ---------------------------------------------------------------------------

_MATH_NOMBRES = _dom(
    "MATH_NOMBRES_CALCULS",
    "Nombres et calculs",
    1,
    [
        _ch(
            "MATH_RELATIFS_RATIONNELS",
            "Nombres relatifs et rationnels",
            "HIGH",
            ["Nombres relatifs"],
            [
                _sk(
                    "MATH_REL_COMPARE",
                    "Comparer et ordonner",
                    ("MATH_REL_COMPARE_DROITE", "Repérer sur une droite graduée"),
                    ("MATH_REL_COMPARE_ORDRE", "Comparer relatifs et rationnels"),
                    ("MATH_REL_COMPARE_INTERVALLE", "Situer dans un intervalle"),
                ),
                _sk(
                    "MATH_REL_OPS",
                    "Opérations sur les relatifs",
                    ("MATH_REL_OPS_ADD", "Addition et soustraction"),
                    ("MATH_REL_OPS_MUL", "Multiplication et division"),
                    ("MATH_REL_OPS_PRIORITE", "Priorités opératoires"),
                ),
                _sk(
                    "MATH_RAT_REPRES",
                    "Représenter les rationnels",
                    ("MATH_RAT_FRAC_DEC", "Fraction et écriture décimale"),
                    ("MATH_RAT_MIXTE", "Écritures mixtes"),
                ),
            ],
        ),
        _ch(
            "MATH_FRACTIONS",
            "Fractions",
            "HIGH",
            ["Fractions"],
            [
                _sk(
                    "MATH_FRAC_SIMP",
                    "Simplifier et rendre irréductible",
                    ("MATH_FRAC_PGCD", "Utiliser le PGCD"),
                    ("MATH_FRAC_EQ", "Fractions égales"),
                    ("MATH_FRAC_IRR", "Forme irréductible"),
                ),
                _sk(
                    "MATH_FRAC_OPS",
                    "Calculer avec des fractions",
                    ("MATH_FRAC_ADD", "Addition et soustraction"),
                    ("MATH_FRAC_MUL", "Multiplication"),
                    ("MATH_FRAC_DIV", "Division"),
                ),
                _sk(
                    "MATH_FRAC_PB",
                    "Résoudre des problèmes de fractions",
                    ("MATH_FRAC_PB_PART", "Partie d'une quantité"),
                    ("MATH_FRAC_PB_CTX", "Problèmes contextualisés"),
                ),
            ],
        ),
        _ch(
            "MATH_PUISSANCES",
            "Puissances et notation scientifique",
            "HIGH",
            ["Puissances"],
            [
                _sk(
                    "MATH_PUIS_PROP",
                    "Propriétés des puissances",
                    ("MATH_PUIS_PROD", "Produit de puissances"),
                    ("MATH_PUIS_QUOT", "Quotient de puissances"),
                    ("MATH_PUIS_NEG", "Exposants négatifs"),
                ),
                _sk(
                    "MATH_PUIS_10",
                    "Puissances de 10",
                    ("MATH_PUIS_10_ECRIT", "Écriture décimale"),
                    ("MATH_PUIS_10_OPS", "Calculs avec 10^n"),
                ),
                _sk(
                    "MATH_NOT_SCI",
                    "Notation scientifique",
                    ("MATH_NOT_SCI_ECRIT", "Passer en notation scientifique"),
                    ("MATH_NOT_SCI_COMP", "Comparer des grandeurs"),
                    ("MATH_NOT_SCI_CALC", "Calculer en notation scientifique"),
                ),
            ],
        ),
        _ch(
            "MATH_ARITHMETIQUE",
            "Arithmétique",
            "STANDARD",
            ["Arithmétique"],
            [
                _sk(
                    "MATH_ARITH_DIV",
                    "Divisibilité",
                    ("MATH_ARITH_CRITERES", "Critères de divisibilité"),
                    ("MATH_ARITH_MULTI", "Multiples et diviseurs"),
                ),
                _sk(
                    "MATH_ARITH_PGCD",
                    "PGCD et applications",
                    ("MATH_ARITH_EUCLIDE", "Algorithme d'Euclide"),
                    ("MATH_ARITH_SIMPL", "Simplification de fractions"),
                ),
                _sk(
                    "MATH_ARITH_PREMIERS",
                    "Nombres premiers",
                    ("MATH_ARITH_RECONN", "Reconnaître un nombre premier"),
                    ("MATH_ARITH_DECOMP", "Décomposition en facteurs premiers"),
                ),
            ],
        ),
        _ch(
            "MATH_CALCUL_LITERAL",
            "Calcul littéral",
            "CRITICAL",
            ["Calcul littéral"],
            [
                _sk(
                    "MATH_LIT_EXPR",
                    "Écrire et interpréter une expression",
                    ("MATH_LIT_TRAD", "Traduire une situation"),
                    ("MATH_LIT_SUBST", "Substituer une valeur"),
                    ("MATH_LIT_TEST", "Tester une égalité"),
                ),
                _sk(
                    "MATH_LIT_OPS",
                    "Manipuler des expressions",
                    ("MATH_LIT_ADD", "Sommes algébriques"),
                    ("MATH_LIT_PROD", "Produits"),
                    ("MATH_LIT_PAREN", "Parenthèses"),
                ),
            ],
        ),
        _ch(
            "MATH_DEV_RED_FACT",
            "Développement, réduction et factorisation",
            "CRITICAL",
            ["Calcul littéral"],
            [
                _sk(
                    "MATH_DEV",
                    "Développer",
                    ("MATH_DEV_SIMPLE", "k(a+b)"),
                    ("MATH_DEV_DOUBLE", "(a+b)(c+d)"),
                    ("MATH_DEV_ID", "Identités remarquables (sens direct)"),
                ),
                _sk(
                    "MATH_RED",
                    "Réduire",
                    ("MATH_RED_TERMES", "Regrouper les termes semblables"),
                    ("MATH_RED_ORDRE", "Ordonner une expression"),
                ),
                _sk(
                    "MATH_FACT",
                    "Factoriser",
                    ("MATH_FACT_FACTEUR", "Facteur commun"),
                    ("MATH_FACT_ID", "Identités remarquables (sens inverse)"),
                ),
            ],
        ),
        _ch(
            "MATH_EQUATIONS",
            "Équations",
            "CRITICAL",
            ["Équations"],
            [
                _sk(
                    "MATH_EQ_1D",
                    "Équations du premier degré",
                    ("MATH_EQ_RESOL", "Résoudre ax+b=c"),
                    ("MATH_EQ_TRANSFO", "Transformer une équation"),
                    ("MATH_EQ_VERIF", "Vérifier une solution"),
                ),
                _sk(
                    "MATH_EQ_PROD_NUL",
                    "Équations produit nul",
                    ("MATH_EQ_FACT_ZERO", "Mettre sous forme produit"),
                    ("MATH_EQ_RACINES", "Trouver les racines"),
                ),
                _sk(
                    "MATH_EQ_PB",
                    "Mettre en équation un problème",
                    ("MATH_EQ_MODEL", "Choisir l'inconnue"),
                    ("MATH_EQ_PB_RESOL", "Résoudre et interpréter"),
                    ("MATH_EQ_PB_CTRL", "Contrôler la pertinence"),
                ),
            ],
        ),
        _ch(
            "MATH_PROBLEMES_NUM",
            "Problèmes numériques",
            "HIGH",
            ["Problèmes"],
            [
                _sk(
                    "MATH_PB_CHOIX",
                    "Choisir une stratégie",
                    ("MATH_PB_ESTIM", "Estimer un ordre de grandeur"),
                    ("MATH_PB_DECOMP", "Décomposer le problème"),
                ),
                _sk(
                    "MATH_PB_CALC",
                    "Mener un calcul justifié",
                    ("MATH_PB_ETAPES", "Enchaîner les étapes"),
                    ("MATH_PB_UNITES", "Gérer les unités"),
                    ("MATH_PB_RESULT", "Présenter le résultat"),
                ),
            ],
        ),
    ],
)

_MATH_DONNEES = _dom(
    "MATH_DONNEES_FONCTIONS",
    "Organisation et gestion de données, fonctions",
    2,
    [
        _ch(
            "MATH_PROPORTIONNALITE",
            "Proportionnalité",
            "HIGH",
            ["Proportionnalité"],
            [
                _sk(
                    "MATH_PROP_RECONN",
                    "Reconnaître une situation de proportionnalité",
                    ("MATH_PROP_TABLEAU", "Tableau de proportionnalité"),
                    ("MATH_PROP_GRAPH", "Représentation graphique"),
                ),
                _sk(
                    "MATH_PROP_CALC",
                    "Calculer dans une situation proportionnelle",
                    ("MATH_PROP_COEF", "Coefficient de proportionnalité"),
                    ("MATH_PROP_QUATR", "Produit en croix"),
                    ("MATH_PROP_ECHELLE", "Échelles"),
                ),
            ],
        ),
        _ch(
            "MATH_POURCENTAGES",
            "Pourcentages",
            "HIGH",
            ["Pourcentages"],
            [
                _sk(
                    "MATH_PCT_CALC",
                    "Calculer un pourcentage",
                    ("MATH_PCT_PART", "Pourcentage d'une quantité"),
                    ("MATH_PCT_TAUX", "Trouver un taux"),
                ),
                _sk(
                    "MATH_PCT_EVOL",
                    "Évolutions en pourcentage",
                    ("MATH_PCT_AUGM", "Augmentation"),
                    ("MATH_PCT_DIM", "Diminution"),
                    ("MATH_PCT_SUCCESS", "Évolutions successives"),
                ),
            ],
        ),
        _ch(
            "MATH_STATISTIQUES",
            "Statistiques",
            "HIGH",
            ["Statistiques"],
            [
                _sk(
                    "MATH_STAT_ORG",
                    "Organiser des données",
                    ("MATH_STAT_TABLEAU", "Tableaux"),
                    ("MATH_STAT_DIAG", "Diagrammes"),
                    ("MATH_STAT_FREQ", "Fréquences"),
                ),
                _sk(
                    "MATH_STAT_INDICS",
                    "Indicateurs statistiques",
                    ("MATH_STAT_MOY", "Moyenne"),
                    ("MATH_STAT_MED", "Médiane"),
                    ("MATH_STAT_ETENDUE", "Étendue"),
                ),
                _sk(
                    "MATH_STAT_INTERP",
                    "Interpréter des données",
                    ("MATH_STAT_LIRE", "Lire un graphique"),
                    ("MATH_STAT_CONCL", "Tirer une conclusion"),
                ),
            ],
        ),
        _ch(
            "MATH_PROBABILITES",
            "Probabilités",
            "HIGH",
            ["Probabilités"],
            [
                _sk(
                    "MATH_PROBA_VOC",
                    "Vocabulaire des probabilités",
                    ("MATH_PROBA_ISSUE", "Issues et événements"),
                    ("MATH_PROBA_EQUI", "Situations équiprobables"),
                ),
                _sk(
                    "MATH_PROBA_CALC",
                    "Calculer une probabilité",
                    ("MATH_PROBA_SIMPLE", "Probabilité simple"),
                    ("MATH_PROBA_COMP", "Événement contraire"),
                    ("MATH_PROBA_ARBRES", "Arbres / tableaux"),
                ),
            ],
        ),
        _ch(
            "MATH_FONCTIONS",
            "Fonctions — image et antécédent",
            "CRITICAL",
            ["Fonctions"],
            [
                _sk(
                    "MATH_FCT_NOTION",
                    "Notion de fonction",
                    ("MATH_FCT_DEF", "Définir une fonction"),
                    ("MATH_FCT_NOTATION", "Notation f(x)"),
                    ("MATH_FCT_TABLEAU", "Tableau de valeurs"),
                ),
                _sk(
                    "MATH_FCT_IMAGE",
                    "Image et antécédent",
                    ("MATH_FCT_IMG", "Calculer une image"),
                    ("MATH_FCT_ANT", "Déterminer un antécédent"),
                    ("MATH_FCT_GRAPH_LIRE", "Lire sur un graphique"),
                ),
                _sk(
                    "MATH_FCT_GRAPH",
                    "Représentation graphique",
                    ("MATH_FCT_TRACER", "Tracer une courbe"),
                    ("MATH_FCT_INTERP", "Interpréter graphiquement"),
                ),
            ],
        ),
        _ch(
            "MATH_FONCTIONS_LINEAIRES_AFFINES",
            "Fonctions linéaires et affines",
            "CRITICAL",
            ["Fonctions", "Fonctions linéaires", "Fonctions affines"],
            [
                _sk(
                    "MATH_LIN",
                    "Fonctions linéaires",
                    ("MATH_LIN_DEF", "y = ax"),
                    ("MATH_LIN_COEF", "Coefficient directeur"),
                    ("MATH_LIN_PROP", "Lien avec la proportionnalité"),
                ),
                _sk(
                    "MATH_AFF",
                    "Fonctions affines",
                    ("MATH_AFF_DEF", "y = ax+b"),
                    ("MATH_AFF_ORD", "Ordonnée à l'origine"),
                    ("MATH_AFF_TRACE", "Tracer la droite"),
                ),
                _sk(
                    "MATH_AFF_EQ",
                    "Déterminer une fonction affine",
                    ("MATH_AFF_2PTS", "À partir de deux points"),
                    ("MATH_AFF_LECTURE", "À partir d'un graphique"),
                    ("MATH_AFF_PB", "Modéliser une situation"),
                ),
            ],
        ),
    ],
)

_MATH_GRANDEURS = _dom(
    "MATH_GRANDEURS_MESURES",
    "Grandeurs et mesures",
    3,
    [
        _ch(
            "MATH_CONVERSIONS",
            "Conversions d'unités",
            "STANDARD",
            ["Conversions"],
            [
                _sk(
                    "MATH_CONV_LONG",
                    "Longueurs, aires, volumes",
                    ("MATH_CONV_M", "Unités de longueur"),
                    ("MATH_CONV_M2", "Unités d'aire"),
                    ("MATH_CONV_M3", "Unités de volume / capacité"),
                ),
                _sk(
                    "MATH_CONV_AUTRES",
                    "Autres grandeurs",
                    ("MATH_CONV_MASSE", "Masses"),
                    ("MATH_CONV_TEMPS", "Durées"),
                    ("MATH_CONV_VITESSE", "Vitesses"),
                ),
            ],
        ),
        _ch(
            "MATH_AIRES_VOLUMES",
            "Aires et volumes",
            "HIGH",
            ["Aires et volumes", "Volumes"],
            [
                _sk(
                    "MATH_AIRE",
                    "Calculer des aires",
                    ("MATH_AIRE_PLANES", "Figures planes usuelles"),
                    ("MATH_AIRE_COMPOSE", "Figures composées"),
                    ("MATH_AIRE_PB", "Problèmes d'aires"),
                ),
                _sk(
                    "MATH_VOL",
                    "Calculer des volumes",
                    ("MATH_VOL_PRISME", "Prisme / pavé / cylindre"),
                    ("MATH_VOL_PYR", "Pyramide / cône"),
                    ("MATH_VOL_SPHERE", "Sphère"),
                ),
            ],
        ),
        _ch(
            "MATH_AGRANDISSEMENT",
            "Agrandissement et réduction",
            "HIGH",
            ["Agrandissement"],
            [
                _sk(
                    "MATH_AGR_FACTEUR",
                    "Facteur d'échelle",
                    ("MATH_AGR_LONG", "Effet sur les longueurs"),
                    ("MATH_AGR_AIRE", "Effet sur les aires"),
                    ("MATH_AGR_VOL", "Effet sur les volumes"),
                ),
                _sk(
                    "MATH_AGR_PB",
                    "Problèmes d'échelle",
                    ("MATH_AGR_PLAN", "Plans et maquettes"),
                    ("MATH_AGR_SIMIL", "Figures semblables"),
                ),
            ],
        ),
    ],
)

_MATH_GEOMETRIE = _dom(
    "MATH_ESPACE_GEOMETRIE",
    "Espace et géométrie",
    4,
    [
        _ch(
            "MATH_REPERAGE",
            "Repérage",
            "STANDARD",
            ["Repérage"],
            [
                _sk(
                    "MATH_REP_PLAN",
                    "Repérage dans le plan",
                    ("MATH_REP_COORDS", "Coordonnées cartésiennes"),
                    ("MATH_REP_MILIEU", "Milieu d'un segment"),
                    ("MATH_REP_DIST", "Distance entre deux points"),
                ),
                _sk(
                    "MATH_REP_ESPACE",
                    "Repérage dans l'espace",
                    ("MATH_REP_3D", "Coordonnées dans l'espace"),
                    ("MATH_REP_SOLIDES", "Lire un solide repéré"),
                ),
            ],
        ),
        _ch(
            "MATH_PYTHAGORE",
            "Théorème de Pythagore et réciproque",
            "CRITICAL",
            ["Pythagore", "Théorème de Pythagore"],
            [
                _sk(
                    "MATH_PYTH_DIR",
                    "Théorème de Pythagore",
                    ("MATH_PYTH_HYP", "Identifier l'hypoténuse"),
                    ("MATH_PYTH_CALC", "Calculer une longueur"),
                    ("MATH_PYTH_PB", "Problèmes d'application"),
                ),
                _sk(
                    "MATH_PYTH_REC",
                    "Réciproque de Pythagore",
                    ("MATH_PYTH_REC_TEST", "Tester si un triangle est rectangle"),
                    ("MATH_PYTH_REC_JUST", "Rédiger une justification"),
                ),
                _sk(
                    "MATH_PYTH_DEMO",
                    "Raisonnement géométrique",
                    ("MATH_PYTH_SCHEMA", "Schématiser"),
                    ("MATH_PYTH_REDAC", "Rédiger une démonstration courte"),
                ),
            ],
        ),
        _ch(
            "MATH_THALES",
            "Théorème de Thalès et réciproque",
            "CRITICAL",
            ["Thalès", "Théorème de Thalès"],
            [
                _sk(
                    "MATH_THAL_DIR",
                    "Théorème de Thalès",
                    ("MATH_THAL_CONFIG", "Reconnaître une configuration"),
                    ("MATH_THAL_RAPPORTS", "Écrire les rapports"),
                    ("MATH_THAL_CALC", "Calculer une longueur"),
                ),
                _sk(
                    "MATH_THAL_REC",
                    "Réciproque de Thalès",
                    ("MATH_THAL_PARA", "Prouver le parallélisme"),
                    ("MATH_THAL_REC_JUST", "Rédiger la justification"),
                ),
            ],
        ),
        _ch(
            "MATH_TRIGONOMETRIE",
            "Trigonométrie dans le triangle rectangle",
            "CRITICAL",
            ["Trigonométrie"],
            [
                _sk(
                    "MATH_TRIG_COS",
                    "Cosinus",
                    ("MATH_TRIG_COS_DEF", "Définition cos = adj/hyp"),
                    ("MATH_TRIG_COS_CALC", "Calculer un cosinus"),
                    ("MATH_TRIG_COS_ANGLE", "Déterminer un angle"),
                ),
                _sk(
                    "MATH_TRIG_SIN",
                    "Sinus",
                    ("MATH_TRIG_SIN_DEF", "Définition sin = opp/hyp"),
                    ("MATH_TRIG_SIN_CALC", "Calculer un sinus"),
                    ("MATH_TRIG_SIN_LONG", "Calculer une longueur"),
                ),
                _sk(
                    "MATH_TRIG_TAN",
                    "Tangente",
                    ("MATH_TRIG_TAN_DEF", "Définition tan = opp/adj"),
                    ("MATH_TRIG_TAN_CALC", "Calculer une tangente"),
                    ("MATH_TRIG_TAN_PB", "Problèmes de trigonométrie"),
                ),
                _sk(
                    "MATH_TRIG_CHOIX",
                    "Choisir le bon rapport",
                    ("MATH_TRIG_COTES", "Identifier côtés depuis un angle"),
                    ("MATH_TRIG_OUTIL", "Choisir cos, sin ou tan"),
                ),
            ],
        ),
        _ch(
            "MATH_TRANSFORMATIONS",
            "Transformations du plan",
            "HIGH",
            ["Transformations"],
            [
                _sk(
                    "MATH_TRANS_ISO",
                    "Isométries",
                    ("MATH_TRANS_TRANS", "Translation"),
                    ("MATH_TRANS_ROT", "Rotation"),
                    ("MATH_TRANS_SYM", "Symétries"),
                ),
                _sk(
                    "MATH_TRANS_PROP",
                    "Propriétés conservées",
                    ("MATH_TRANS_LONG", "Conservation des longueurs"),
                    ("MATH_TRANS_ANGLE", "Conservation des angles"),
                    ("MATH_TRANS_IMAGE", "Construire l'image d'une figure"),
                ),
            ],
        ),
        _ch(
            "MATH_HOMOTHETIE",
            "Homothétie",
            "HIGH",
            ["Homothétie"],
            [
                _sk(
                    "MATH_HOM_DEF",
                    "Définition et rapport",
                    ("MATH_HOM_CENTRE", "Centre et rapport k"),
                    ("MATH_HOM_SENS", "Agrandissement / réduction"),
                ),
                _sk(
                    "MATH_HOM_CONST",
                    "Construire et calculer",
                    ("MATH_HOM_IMAGE", "Image d'un point / d'une figure"),
                    ("MATH_HOM_LONG", "Effet sur les longueurs"),
                    ("MATH_HOM_LIEN", "Lien avec Thalès / agrandissement"),
                ),
            ],
        ),
        _ch(
            "MATH_GEOMETRIE_PLANE",
            "Géométrie plane",
            "HIGH",
            ["Géométrie plane", "Triangles"],
            [
                _sk(
                    "MATH_GEO_TRI",
                    "Triangles",
                    ("MATH_GEO_TRI_TYPES", "Types de triangles"),
                    ("MATH_GEO_TRI_INEG", "Inégalité triangulaire"),
                    ("MATH_GEO_TRI_ANGLES", "Somme des angles"),
                ),
                _sk(
                    "MATH_GEO_CERCLE",
                    "Cercle et polygones",
                    ("MATH_GEO_CERCLE_PROP", "Propriétés du cercle"),
                    ("MATH_GEO_POLY", "Polygones réguliers"),
                ),
                _sk(
                    "MATH_GEO_CONST",
                    "Constructions et justifications",
                    ("MATH_GEO_TRACE", "Construire à la règle et au compas"),
                    ("MATH_GEO_JUST", "Justifier une propriété"),
                ),
            ],
        ),
        _ch(
            "MATH_ESPACE_SOLIDES",
            "Géométrie dans l'espace et solides",
            "HIGH",
            ["Géométrie dans l'espace"],
            [
                _sk(
                    "MATH_ESP_SOLIDES",
                    "Solides usuels",
                    ("MATH_ESP_PAVE", "Pavé / cube"),
                    ("MATH_ESP_CYL", "Cylindre / cône / sphère"),
                    ("MATH_ESP_PYR", "Pyramide / prisme"),
                ),
                _sk(
                    "MATH_ESP_REP",
                    "Représentations",
                    ("MATH_ESP_PERSP", "Perspective cavalière"),
                    ("MATH_ESP_PATRON", "Patrons"),
                    ("MATH_ESP_SECTION", "Sections planes"),
                ),
            ],
        ),
    ],
)

_MATH_ALGO = _dom(
    "MATH_ALGO_PROG",
    "Algorithmique et programmation",
    5,
    [
        _ch(
            "MATH_ALGO_BASES",
            "Variables, conditions et boucles",
            "HIGH",
            ["Algorithmique", "Programmation"],
            [
                _sk(
                    "MATH_ALGO_VAR",
                    "Variables et affectations",
                    ("MATH_ALGO_VAR_DECL", "Déclarer / affecter"),
                    ("MATH_ALGO_VAR_TYPES", "Types simples"),
                    ("MATH_ALGO_VAR_EXPR", "Expressions"),
                ),
                _sk(
                    "MATH_ALGO_COND",
                    "Conditions",
                    ("MATH_ALGO_IF", "Si … alors … sinon"),
                    ("MATH_ALGO_BOOL", "Conditions booléennes"),
                ),
                _sk(
                    "MATH_ALGO_BOUCLES",
                    "Boucles",
                    ("MATH_ALGO_FOR", "Boucle bornée"),
                    ("MATH_ALGO_WHILE", "Boucle non bornée"),
                    ("MATH_ALGO_TRACE", "Faire tourner un algorithme à la main"),
                ),
            ],
        ),
        _ch(
            "MATH_SCRATCH_BLOCS",
            "Scratch et programmation par blocs",
            "STANDARD",
            ["Scratch / blocs", "Programmation"],
            [
                _sk(
                    "MATH_SCRATCH_SCRIPTS",
                    "Scripts et événements",
                    ("MATH_SCRATCH_EVT", "Événements"),
                    ("MATH_SCRATCH_SEQ", "Séquences d'instructions"),
                ),
                _sk(
                    "MATH_SCRATCH_CTRL",
                    "Contrôle et interactions",
                    ("MATH_SCRATCH_REPETER", "Répéter"),
                    ("MATH_SCRATCH_SI", "Conditions en blocs"),
                    ("MATH_SCRATCH_VAR", "Variables en blocs"),
                ),
            ],
        ),
    ],
)

_MATH_TX_SKILLS: list[dict[str, Any]] = [
    _sk(
        "AUTOMATISMES",
        "Automatismes",
        ("MATH_AUTO_CALC", "Calculs fluides"),
        ("MATH_AUTO_PROC", "Procédures de base"),
        ("MATH_AUTO_FORMULES", "Formules usuelles"),
        ("MATH_AUTO_RAPIDITE", "Rapidité et exactitude"),
    ),
    _sk(
        "RESOLUTION_PROBLEMES",
        "Résolution de problèmes",
        ("MATH_RESOL_COMPRENDRE", "Comprendre l'énoncé"),
        ("MATH_RESOL_STRAT", "Choisir une stratégie"),
        ("MATH_RESOL_MENER", "Mener la résolution"),
        ("MATH_RESOL_CTRL", "Contrôler et conclure"),
    ),
    _sk(
        "RAISONNEMENT",
        "Raisonnement",
        ("MATH_RAIS_DEDUC", "Déduire"),
        ("MATH_RAIS_INDUC", "Conjecturer"),
        ("MATH_RAIS_CONTRE", "Contre-exemple"),
    ),
    _sk(
        "DEMONSTRATION",
        "Démonstration",
        ("MATH_DEMO_HYP", "Hypothèses / conclusion"),
        ("MATH_DEMO_ENCHAIN", "Enchaîner des arguments"),
        ("MATH_DEMO_REDAC", "Rédiger une preuve"),
    ),
    _sk(
        "CALCUL_MENTAL",
        "Calcul mental",
        ("MATH_MENTAL_OPS", "Opérations courantes"),
        ("MATH_MENTAL_ORDRE", "Ordres de grandeur"),
        ("MATH_MENTAL_PCT", "Pourcentages mentaux"),
    ),
    _sk(
        "OUTILS_NUMERIQUES",
        "Outils numériques",
        ("MATH_NUM_CALC", "Calculatrice"),
        ("MATH_NUM_TABLEUR", "Tableur"),
        ("MATH_NUM_GEO", "Logiciel de géométrie"),
        ("MATH_NUM_PROG", "Environnement de programmation"),
    ),
]

_MATH_TRANSVERSAL = _dom(
    "MATH_TRANSVERSAL",
    "Compétences transversales mathématiques",
    6,
    [
        _ch(
            "MATH_COMPETENCES_TRANSVERSALES",
            "Compétences transversales",
            "HIGH",
            ["Automatismes", "Raisonnement et démonstration", "Tableur", "Problèmes"],
            _MATH_TX_SKILLS,
        ),
    ],
)

# ---------------------------------------------------------------------------
# FRENCH — BO juillet 2020 cycle 4
# ---------------------------------------------------------------------------

_FR_LECTURE = _dom(
    "FR_LECTURE_COMPREHENSION",
    "Lecture et compréhension",
    1,
    [
        _ch(
            "FR_COMPREHENSION",
            "Compréhension de textes",
            "CRITICAL",
            ["Compréhension"],
            [
                _sk(
                    "FR_COMP_EXPLICITE",
                    "Repérer des informations explicites",
                    ("FR_COMP_LOC", "Localiser une information"),
                    ("FR_COMP_SELECT", "Sélectionner l'essentiel"),
                    ("FR_COMP_CIT", "S'appuyer sur le texte"),
                ),
                _sk(
                    "FR_COMP_IMPLICITE",
                    "Inférer des informations implicites",
                    ("FR_COMP_DEDUC", "Déduire un sens"),
                    ("FR_COMP_INDICES", "Croiser des indices"),
                ),
                _sk(
                    "FR_COMP_GLOBAL",
                    "Comprendre le sens global",
                    ("FR_COMP_THEME", "Identifier le thème"),
                    ("FR_COMP_ENJEU", "Saisir l'enjeu du texte"),
                    ("FR_COMP_RESUME", "Résumer"),
                ),
            ],
        ),
        _ch(
            "FR_INTERPRETATION",
            "Interprétation et analyse",
            "CRITICAL",
            ["Interprétation", "Figures de style"],
            [
                _sk(
                    "FR_INT_PROC",
                    "Procédés d'écriture",
                    ("FR_INT_FIG", "Figures de style"),
                    ("FR_INT_REGISTRE", "Registres"),
                    ("FR_INT_LEXIQUE", "Choix lexicaux"),
                ),
                _sk(
                    "FR_INT_POINT_VUE",
                    "Point de vue et intentions",
                    ("FR_INT_NARR", "Narrateur / locuteur"),
                    ("FR_INT_EFFET", "Effets sur le lecteur"),
                    ("FR_INT_JUST", "Justifier une interprétation"),
                ),
            ],
        ),
    ],
)

_FR_LANGUE = _dom(
    "FR_LANGUE",
    "Langue (grammaire, conjugaison, orthographe, vocabulaire)",
    2,
    [
        _ch(
            "FR_GRAMMAIRE_SYNTAXE",
            "Grammaire et syntaxe",
            "HIGH",
            ["Classes grammaticales", "Fonctions grammaticales", "Phrases complexes", "Grammaire"],
            [
                _sk(
                    "FR_GRAM_CLASSES",
                    "Classes grammaticales",
                    ("FR_GRAM_NATURE", "Nature des mots"),
                    ("FR_GRAM_DET", "Déterminants / pronoms"),
                    ("FR_GRAM_ADV", "Adverbes / prépositions / conjonctions"),
                ),
                _sk(
                    "FR_GRAM_FONCTIONS",
                    "Fonctions dans la phrase",
                    ("FR_GRAM_SUJ", "Sujet"),
                    ("FR_GRAM_COD_COI", "COD / COI"),
                    ("FR_GRAM_CIRC", "Compléments circonstanciels"),
                ),
                _sk(
                    "FR_GRAM_PHRASE",
                    "Phrase simple et complexe",
                    ("FR_GRAM_PROP", "Propositions"),
                    ("FR_GRAM_SUB", "Subordination / coordination"),
                    ("FR_GRAM_PONCT", "Ponctuation"),
                ),
            ],
        ),
        _ch(
            "FR_CONJUGAISON",
            "Conjugaison",
            "HIGH",
            ["Conjugaison"],
            [
                _sk(
                    "FR_CONJ_TEMPS",
                    "Temps et modes",
                    ("FR_CONJ_IND", "Indicatif (présent, passé, futur)"),
                    ("FR_CONJ_COND", "Conditionnel"),
                    ("FR_CONJ_SUBJ", "Subjonctif courant"),
                ),
                _sk(
                    "FR_CONJ_ACCORDS_V",
                    "Accords du verbe",
                    ("FR_CONJ_PERS", "Personne et nombre"),
                    ("FR_CONJ_GROUPE", "Groupes verbaux"),
                    ("FR_CONJ_COMPOSES", "Temps composés"),
                ),
            ],
        ),
        _ch(
            "FR_ORTHOGRAPHE_ACCORDS",
            "Orthographe et accords",
            "HIGH",
            ["Orthographe", "Accords", "Homophones grammaticaux"],
            [
                _sk(
                    "FR_ORTH_LEX",
                    "Orthographe lexicale",
                    ("FR_ORTH_MOTS", "Mots courants et homophones"),
                    ("FR_ORTH_REGLES", "Règles d'usage"),
                ),
                _sk(
                    "FR_ACC_GN",
                    "Accords dans le groupe nominal",
                    ("FR_ACC_DET", "Déterminant / nom / adjectif"),
                    ("FR_ACC_PP", "Participe passé"),
                ),
                _sk(
                    "FR_ACC_SUJ_V",
                    "Accord sujet-verbe",
                    ("FR_ACC_SUJ_SIMPLE", "Sujet simple"),
                    ("FR_ACC_SUJ_INV", "Sujet inversé / éloigné"),
                ),
            ],
        ),
        _ch(
            "FR_VOCABULAIRE",
            "Vocabulaire",
            "STANDARD",
            ["Vocabulaire"],
            [
                _sk(
                    "FR_VOC_SENS",
                    "Sens des mots",
                    ("FR_VOC_CTX", "Sens en contexte"),
                    ("FR_VOC_POLY", "Polysémie"),
                    ("FR_VOC_NUANCE", "Nuances et synonymes"),
                ),
                _sk(
                    "FR_VOC_FORM",
                    "Formation des mots",
                    ("FR_VOC_PREF", "Préfixes / suffixes"),
                    ("FR_VOC_FAM", "Familles de mots"),
                ),
            ],
        ),
    ],
)

_FR_ECRITURE = _dom(
    "FR_ECRITURE",
    "Écriture",
    3,
    [
        _ch(
            "FR_REECRITURE",
            "Réécriture",
            "HIGH",
            ["Réécriture"],
            [
                _sk(
                    "FR_REECR_TRANSFO",
                    "Transformer un texte",
                    ("FR_REECR_PERS", "Changer personne / temps"),
                    ("FR_REECR_EXPANS", "Expansion / réduction"),
                    ("FR_REECR_REGISTRE", "Changer de registre"),
                ),
                _sk(
                    "FR_REECR_COHERENCE",
                    "Maintenir la cohérence",
                    ("FR_REECR_ACC", "Réaccorder"),
                    ("FR_REECR_SENS", "Préserver le sens"),
                ),
            ],
        ),
        _ch(
            "FR_DICTEE",
            "Dictée",
            "HIGH",
            ["Dictée"],
            [
                _sk(
                    "FR_DICT_ORTH",
                    "Orthographe en situation",
                    ("FR_DICT_LEX", "Orthographe lexicale"),
                    ("FR_DICT_GRAM", "Orthographe grammaticale"),
                ),
                _sk(
                    "FR_DICT_STRATEGIE",
                    "Stratégies de relecture",
                    ("FR_DICT_CTRL_V", "Contrôler les verbes"),
                    ("FR_DICT_CTRL_GN", "Contrôler les accords du GN"),
                ),
            ],
        ),
        _ch(
            "FR_EXPRESSION_ECRITE",
            "Expression écrite",
            "CRITICAL",
            ["Expression écrite", "Rédaction"],
            [
                _sk(
                    "FR_EXPR_PLAN",
                    "Organiser un écrit",
                    ("FR_EXPR_IDEES", "Générer des idées"),
                    ("FR_EXPR_PLANIF", "Planifier"),
                    ("FR_EXPR_PARAGR", "Paragraphes"),
                ),
                _sk(
                    "FR_EXPR_STYLE",
                    "Qualité de l'expression",
                    ("FR_EXPR_LEX", "Précision lexicale"),
                    ("FR_EXPR_SYNTAXE", "Variété syntaxique"),
                    ("FR_EXPR_CORR", "Correction linguistique"),
                ),
                _sk(
                    "FR_EXPR_GENRES",
                    "Genres d'écrits",
                    ("FR_EXPR_NARR", "Narratif"),
                    ("FR_EXPR_DESC", "Descriptif"),
                    ("FR_EXPR_EXPL", "Explicatif"),
                ),
            ],
        ),
        _ch(
            "FR_ARGUMENTATION",
            "Argumentation",
            "CRITICAL",
            ["Rédaction", "Expression écrite"],
            [
                _sk(
                    "FR_ARG_THESE",
                    "Construire une thèse",
                    ("FR_ARG_POS", "Prendre position"),
                    ("FR_ARG_ARGS", "Sélectionner des arguments"),
                    ("FR_ARG_EX", "Illustrer par des exemples"),
                ),
                _sk(
                    "FR_ARG_STRUCT",
                    "Structurer un paragraphe argumentatif",
                    ("FR_ARG_CONNECT", "Connecteurs"),
                    ("FR_ARG_PROGRESS", "Progression"),
                    ("FR_ARG_CONCLUS", "Conclure"),
                ),
            ],
        ),
    ],
)

_FR_DNB = _dom(
    "FR_FORMATS_DNB",
    "Formats d'épreuve DNB",
    4,
    [
        _ch(
            "FR_DNB_COMPREHENSION",
            "Compréhension et compétences linguistiques (DNB)",
            "CRITICAL",
            ["Compréhension", "Grammaire"],
            [
                _sk(
                    "FR_DNB_QCM",
                    "Questions de compréhension",
                    ("FR_DNB_Q_TEXT", "Répondre à partir du texte"),
                    ("FR_DNB_Q_JUST", "Justifier brièvement"),
                ),
                _sk(
                    "FR_DNB_LANGUE",
                    "Compétences linguistiques",
                    ("FR_DNB_GRAM", "Questions de grammaire"),
                    ("FR_DNB_REECR", "Exercice de réécriture"),
                    ("FR_DNB_DICT", "Dictée"),
                ),
            ],
        ),
        _ch(
            "FR_DNB_REDACTION",
            "Rédaction DNB",
            "CRITICAL",
            ["Rédaction", "Expression écrite"],
            [
                _sk(
                    "FR_DNB_SUJET",
                    "Traiter le sujet",
                    ("FR_DNB_CONSIGNE", "Comprendre la consigne"),
                    ("FR_DNB_TYPE", "Sujet d'imagination / réflexion"),
                ),
                _sk(
                    "FR_DNB_PROD",
                    "Produire un texte abouti",
                    ("FR_DNB_LONGUEUR", "Respecter la longueur attendue"),
                    ("FR_DNB_RELECTURE", "Se relire"),
                    ("FR_DNB_CRIT", "Critères d'évaluation"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# HISTORY — thèmes 3e uniquement
# ---------------------------------------------------------------------------

_HIST_GUERRES = _dom(
    "HIST_EUROPE_GUERRES_TOTALES",
    "L'Europe, un théâtre majeur des guerres totales (1914-1945)",
    1,
    [
        _ch(
            "HIST_WWI",
            "La Première Guerre mondiale : l'expérience combattante et l'expérience des civils",
            "HIGH",
            ["Première Guerre mondiale"],
            [
                _sk(
                    "HIST_WWI_MIL",
                    "Expérience combattante",
                    ("HIST_WWI_TRENCHEES", "Guerre de tranchées"),
                    ("HIST_WWI_VIOLENCE", "Violence de masse"),
                    ("HIST_WWI_TEMOINS", "Témoignages combattants"),
                ),
                _sk(
                    "HIST_WWI_CIV",
                    "Expérience des civils",
                    ("HIST_WWI_FRONT_INT", "Front intérieur"),
                    ("HIST_WWI_FEMMES", "Rôle des femmes"),
                    ("HIST_WWI_OPINION", "Opinion et propagande"),
                ),
                _sk(
                    "HIST_WWI_SORTIE",
                    "Sorties de guerre",
                    ("HIST_WWI_1918", "Armistice et traités"),
                    ("HIST_WWI_BILAN", "Bilans humains et politiques"),
                ),
            ],
        ),
        _ch(
            "HIST_DEMOCRATIES_TOTALITARISMES",
            "Démocraties et totalitarismes dans l'Europe de l'entre-deux-guerres",
            "CRITICAL",
            ["Totalitarismes"],
            [
                _sk(
                    "HIST_TOT_REGIMES",
                    "Régimes totalitaires",
                    ("HIST_TOT_URSS", "Stalinisme"),
                    ("HIST_TOT_IT", "Fascisme italien"),
                    ("HIST_TOT_ALL", "Nazisme"),
                ),
                _sk(
                    "HIST_TOT_PRATIQUES",
                    "Pratiques totalitaires",
                    ("HIST_TOT_PROP", "Propagande"),
                    ("HIST_TOT_REPRESSION", "Répression et terreur"),
                    ("HIST_TOT_CULTE", "Culte du chef"),
                ),
                _sk(
                    "HIST_DEM_CRISE",
                    "Démocraties face à la crise",
                    ("HIST_DEM_1929", "Crise de 1929"),
                    ("HIST_DEM_FR", "Réponses démocratiques (ex. Front populaire)"),
                ),
            ],
        ),
        _ch(
            "HIST_WWII_ANEANTISSEMENT",
            "La Seconde Guerre mondiale, une guerre d'anéantissement",
            "CRITICAL",
            ["Seconde Guerre mondiale"],
            [
                _sk(
                    "HIST_WWII_GUERRE",
                    "Guerre mondiale et anéantissement",
                    ("HIST_WWII_FRONTS", "Fronts et coalitions"),
                    ("HIST_WWII_CRIMES", "Crimes de masse"),
                    ("HIST_WWII_BOMB", "Bombardements / guerre totale"),
                ),
                _sk(
                    "HIST_WWII_SHOAH",
                    "Génocide des Juifs et des Tsiganes",
                    ("HIST_WWII_ANTIS", "Antisémitisme nazi"),
                    ("HIST_WWII_CAMP", "Camps et extermination"),
                    ("HIST_WWII_MEM", "Mémoires"),
                ),
            ],
        ),
        _ch(
            "HIST_FRANCE_VICHY_RESISTANCE",
            "La France défaite et occupée ; régime de Vichy, Collaboration, Résistance",
            "CRITICAL",
            ["Seconde Guerre mondiale"],
            [
                _sk(
                    "HIST_FR40_DEFAITE",
                    "Défaite et occupation",
                    ("HIST_FR40_1940", "Défaite de 1940"),
                    ("HIST_FR40_OCC", "Occupation"),
                    ("HIST_FR40_ZONE", "Zones et quotidien"),
                ),
                _sk(
                    "HIST_VICHY",
                    "Vichy et Collaboration",
                    ("HIST_VICHY_REGIME", "État français"),
                    ("HIST_VICHY_COLLAB", "Collaboration"),
                    ("HIST_VICHY_ANTIS", "Politique antisémite"),
                ),
                _sk(
                    "HIST_RESIST",
                    "Résistances",
                    ("HIST_RESIST_INT", "Résistance intérieure"),
                    ("HIST_RESIST_FL", "France libre"),
                    ("HIST_RESIST_ACTES", "Actes de résistance"),
                ),
            ],
        ),
    ],
)

_HIST_MONDE = _dom(
    "HIST_MONDE_DEPUIS_1945",
    "Le monde depuis 1945",
    2,
    [
        _ch(
            "HIST_INDEPENDANCES",
            "Indépendances et construction de nouveaux États",
            "HIGH",
            ["Décolonisation", "Colonisation"],
            [
                _sk(
                    "HIST_DECOL_PROCESSUS",
                    "Processus de décolonisation",
                    ("HIST_DECOL_ASIE", "Asie"),
                    ("HIST_DECOL_AFRIQUE", "Afrique"),
                    ("HIST_DECOL_ACTEURS", "Acteurs et formes (négociée / conflictuelle)"),
                ),
                _sk(
                    "HIST_DECOL_NOUVEAUX",
                    "Nouveaux États",
                    ("HIST_DECOL_ENJEUX", "Enjeux politiques et économiques"),
                    ("HIST_DECOL_NONALIGN", "Non-alignement / Tiers monde"),
                ),
            ],
        ),
        _ch(
            "HIST_GUERRE_FROIDE",
            "Un monde bipolaire au temps de la Guerre froide",
            "CRITICAL",
            ["Guerre froide"],
            [
                _sk(
                    "HIST_GF_BLOCS",
                    "Blocs Est / Ouest",
                    ("HIST_GF_ORIGINES", "Origines"),
                    ("HIST_GF_OTAN_Pacte", "Alliances"),
                    ("HIST_GF_IDEO", "Affrontement idéologique"),
                ),
                _sk(
                    "HIST_GF_CRISES",
                    "Crises et conflits",
                    ("HIST_GF_BERLIN", "Berlin"),
                    ("HIST_GF_CUBA", "Cuba"),
                    ("HIST_GF_PROXY", "Guerres proxy"),
                ),
                _sk(
                    "HIST_GF_FIN",
                    "Fin de la Guerre froide",
                    ("HIST_GF_1989", "1989"),
                    ("HIST_GF_URSS", "Dislocation de l'URSS"),
                ),
            ],
        ),
        _ch(
            "HIST_PROJET_EUROPEEN",
            "Affirmation et mise en œuvre du projet européen",
            "HIGH",
            ["Construction européenne", "Europe"],
            [
                _sk(
                    "HIST_EU_ORIGINES",
                    "Origines du projet européen",
                    ("HIST_EU_APRES45", "Après 1945"),
                    ("HIST_EU_PERES", "Pères fondateurs / traités"),
                ),
                _sk(
                    "HIST_EU_ELARG",
                    "Approfondissement et élargissements",
                    ("HIST_EU_CEE", "CEE / marché commun"),
                    ("HIST_EU_UE", "Union européenne"),
                    ("HIST_EU_ENJEUX", "Enjeux contemporains"),
                ),
            ],
        ),
        _ch(
            "HIST_ENJEUX_APRES_1989",
            "Enjeux et conflits dans le monde après 1989",
            "HIGH",
            ["Guerre froide"],
            [
                _sk(
                    "HIST_POST89_ORDRE",
                    "Nouvel ordre mondial",
                    ("HIST_POST89_UNI", "Fin du bipolarisme"),
                    ("HIST_POST89_PUISS", "Nouvelles puissances"),
                ),
                _sk(
                    "HIST_POST89_CONFLITS",
                    "Conflits et terrorisme",
                    ("HIST_POST89_REG", "Conflits régionaux"),
                    ("HIST_POST89_TERROR", "Terrorisme international"),
                    ("HIST_POST89_MULTI", "Multilatéralisme / ONU"),
                ),
            ],
        ),
    ],
)

_HIST_REP = _dom(
    "HIST_REPUBLIQUE_REPENSEE",
    "Françaises et Français dans une République repensée",
    3,
    [
        _ch(
            "HIST_REFONDER_REPUBLIQUE",
            "Refonder la République, redéfinir la démocratie (1944-1947)",
            "HIGH",
            ["République"],
            [
                _sk(
                    "HIST_1944_LIBERATION",
                    "Libération et refondation",
                    ("HIST_1944_GPRF", "GPRF"),
                    ("HIST_1944_DROITS", "Droits (vote des femmes)"),
                    ("HIST_1944_EPUR", "Épuration"),
                ),
                _sk(
                    "HIST_1946_CONST",
                    "IVe République",
                    ("HIST_1946_CONSTIT", "Constitution de 1946"),
                    ("HIST_1946_SOCIAL", "Réformes sociales"),
                ),
            ],
        ),
        _ch(
            "HIST_VE_REPUBLIQUE",
            "La Ve République",
            "CRITICAL",
            ["République"],
            [
                _sk(
                    "HIST_VE_INSTITUTIONS",
                    "Institutions de la Ve République",
                    ("HIST_VE_1958", "Constitution de 1958"),
                    ("HIST_VE_PRES", "Rôle du président"),
                    ("HIST_VE_EQUILIBRE", "Équilibres des pouvoirs"),
                ),
                _sk(
                    "HIST_VE_EVOL",
                    "Évolutions politiques",
                    ("HIST_VE_ALTER", "Alternances"),
                    ("HIST_VE_REFORMES", "Réformes majeures"),
                    ("HIST_VE_SOCIETE", "Société et politique"),
                ),
            ],
        ),
        _ch(
            "HIST_FEMMES_HOMMES_SOCIETE",
            "Femmes et hommes dans la société des années 1950 aux années 1980",
            "HIGH",
            ["République"],
            [
                _sk(
                    "HIST_SOC_TRANFO",
                    "Transformations sociales",
                    ("HIST_SOC_TRAVAIL", "Travail et modes de vie"),
                    ("HIST_SOC_CONSO", "Société de consommation"),
                    ("HIST_SOC_JEUNES", "Jeunesse et culture"),
                ),
                _sk(
                    "HIST_SOC_FEMMES",
                    "Place des femmes",
                    ("HIST_SOC_DROITS_F", "Droits des femmes"),
                    ("HIST_SOC_EGALITE", "Inégalités et conquêtes"),
                ),
                _sk(
                    "HIST_SOC_IMMIG",
                    "Immigration et société française",
                    ("HIST_SOC_MIG", "Migrations"),
                    ("HIST_SOC_INTEGR", "Intégration / débats"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# GEOGRAPHY — 3e
# ---------------------------------------------------------------------------

_GEO_DYN = _dom(
    "GEO_DYNAMIQUES_TERRITORIALES_FRANCE",
    "Dynamiques territoriales de la France contemporaine",
    1,
    [
        _ch(
            "GEO_URBANISATION_FR",
            "Urbanisation et attractivité des territoires",
            "HIGH",
            ["Urbanisation", "France et territoires", "Mobilités humaines"],
            [
                _sk(
                    "GEO_URB_METRO",
                    "Métropolisation",
                    ("GEO_URB_VILLES", "Aires urbaines"),
                    ("GEO_URB_HIER", "Hiérarchie urbaine"),
                    ("GEO_URB_FONCTIONS", "Fonctions métropolitaines"),
                ),
                _sk(
                    "GEO_URB_MOB",
                    "Mobilités et espaces de vie",
                    ("GEO_URB_NAVETTE", "Navettes"),
                    ("GEO_URB_PERI", "Périurbanisation"),
                ),
            ],
        ),
        _ch(
            "GEO_ESPACES_PRODUCTIFS",
            "Les espaces productifs et leurs évolutions",
            "HIGH",
            ["Espaces productifs", "Mondialisation"],
            [
                _sk(
                    "GEO_PROD_AGR",
                    "Espaces agricoles",
                    ("GEO_PROD_AGR_SYS", "Systèmes agricoles"),
                    ("GEO_PROD_AGR_MUT", "Mutations"),
                ),
                _sk(
                    "GEO_PROD_IND",
                    "Espaces industriels et de services",
                    ("GEO_PROD_IND_ZONES", "Zones industrialo-portuaires"),
                    ("GEO_PROD_SERV", "Tertiarisation"),
                    ("GEO_PROD_INNOV", "Innovation / technopoles"),
                ),
            ],
        ),
        _ch(
            "GEO_INEGALITES_TERRITORIALES",
            "Inégalités et fractures territoriales",
            "HIGH",
            ["Inégalités mondiales", "France et territoires"],
            [
                _sk(
                    "GEO_INEG_FR",
                    "Contrastes du territoire français",
                    ("GEO_INEG_DENSITE", "Densités"),
                    ("GEO_INEG_ATTRAC", "Attractivité / déclin"),
                    ("GEO_INEG_OUTREMER", "Outre-mer"),
                ),
                _sk(
                    "GEO_INEG_ACTEURS",
                    "Acteurs et politiques",
                    ("GEO_INEG_ETAT", "Rôle de l'État"),
                    ("GEO_INEG_COLLECT", "Collectivités"),
                ),
            ],
        ),
    ],
)

_GEO_AMENAGER = _dom(
    "GEO_AMENAGER_TERRITOIRE",
    "Pourquoi et comment aménager le territoire ?",
    2,
    [
        _ch(
            "GEO_AMENAGEMENT",
            "Aménagement du territoire",
            "CRITICAL",
            ["Aménagement", "Développement durable"],
            [
                _sk(
                    "GEO_AMEN_ENJEUX",
                    "Enjeux d'aménagement",
                    ("GEO_AMEN_EQ", "Équilibres territoriaux"),
                    ("GEO_AMEN_ACCESS", "Accessibilité"),
                    ("GEO_AMEN_DD", "Développement durable"),
                ),
                _sk(
                    "GEO_AMEN_ACTEURS",
                    "Acteurs de l'aménagement",
                    ("GEO_AMEN_PUBLIC", "Acteurs publics"),
                    ("GEO_AMEN_PRIVE", "Acteurs privés"),
                    ("GEO_AMEN_CITOYEN", "Concertation"),
                ),
            ],
        ),
        _ch(
            "GEO_RISQUES_ENV",
            "Risques et transitions",
            "HIGH",
            ["Risques naturels", "Développement durable"],
            [
                _sk(
                    "GEO_RISQ",
                    "Risques et vulnérabilités",
                    ("GEO_RISQ_NAT", "Risques naturels"),
                    ("GEO_RISQ_TECH", "Risques technologiques"),
                    ("GEO_RISQ_PREV", "Prévention"),
                ),
                _sk(
                    "GEO_TRANS",
                    "Transitions énergétiques et écologiques",
                    ("GEO_TRANS_NRJ", "Énergie"),
                    ("GEO_TRANS_CLIM", "Climat"),
                ),
            ],
        ),
    ],
)

_GEO_UE = _dom(
    "GEO_FRANCE_UE",
    "La France et l'Union européenne",
    3,
    [
        _ch(
            "GEO_FRANCE_EUROPE",
            "La France dans l'Union européenne",
            "CRITICAL",
            ["Union européenne", "France et territoires", "Europe"],
            [
                _sk(
                    "GEO_UE_TERRITOIRE",
                    "Territoire européen",
                    ("GEO_UE_ETATS", "États membres"),
                    ("GEO_UE_FRONT", "Frontières"),
                    ("GEO_UE_COEUR", "Dorsale européenne"),
                ),
                _sk(
                    "GEO_UE_POLITIQUES",
                    "Politiques européennes",
                    ("GEO_UE_COHESION", "Cohésion territoriale"),
                    ("GEO_UE_PAC", "Politiques communes (ex. PAC)"),
                    ("GEO_UE_FR_ROLE", "Place de la France"),
                ),
            ],
        ),
        _ch(
            "GEO_FRANCE_MONDE",
            "La France, une influence mondiale",
            "HIGH",
            ["Mondialisation", "France et territoires"],
            [
                _sk(
                    "GEO_FR_MONDE_SOFT",
                    "Rayonnement",
                    ("GEO_FR_LANGUE", "Francophonie"),
                    ("GEO_FR_CULTURE", "Culture / diplomatie"),
                ),
                _sk(
                    "GEO_FR_MONDE_STRAT",
                    "Présence stratégique",
                    ("GEO_FR_OM", "Outre-mer"),
                    ("GEO_FR_OTAN_ONU", "Engagements internationaux"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# EMC — BO 2024 (applicable 3e dès 2026-2027)
# ---------------------------------------------------------------------------

_EMC = _dom(
    "EMC_CITOYENNETE_REPUBLIQUE",
    "Valeurs, principes et exercice de la citoyenneté",
    1,
    [
        _ch(
            "EMC_VALEURS",
            "Valeurs et principes de la République",
            "CRITICAL",
            ["Valeurs de la République"],
            [
                _sk(
                    "EMC_VAL_DEVISE",
                    "Liberté, égalité, fraternité",
                    ("EMC_VAL_LIB", "Liberté"),
                    ("EMC_VAL_EGAL", "Égalité"),
                    ("EMC_VAL_FRAT", "Fraternité"),
                ),
                _sk(
                    "EMC_VAL_PRINCIPE",
                    "Principes républicains",
                    ("EMC_VAL_SOUV", "Souveraineté"),
                    ("EMC_VAL_INDIV", "Indivisibilité"),
                ),
            ],
        ),
        _ch(
            "EMC_LAICITE",
            "Laïcité",
            "CRITICAL",
            ["Laïcité"],
            [
                _sk(
                    "EMC_LAI_PRINCIPE",
                    "Principe de laïcité",
                    ("EMC_LAI_HIST", "Construction historique"),
                    ("EMC_LAI_1905", "Loi de 1905"),
                    ("EMC_LAI_ECOLE", "Laïcité à l'école"),
                ),
                _sk(
                    "EMC_LAI_PRATIQUE",
                    "Laïcité en pratique",
                    ("EMC_LAI_CAS", "Études de cas"),
                    ("EMC_LAI_LIB_CROY", "Liberté de conscience"),
                ),
            ],
        ),
        _ch(
            "EMC_CITOYENNETE",
            "Citoyenneté",
            "CRITICAL",
            ["Citoyenneté"],
            [
                _sk(
                    "EMC_CIT_STATUT",
                    "Statut de citoyen",
                    ("EMC_CIT_DROITS", "Droits"),
                    ("EMC_CIT_DEVOIRS", "Devoirs"),
                    ("EMC_CIT_NAT", "Nationalité"),
                ),
                _sk(
                    "EMC_CIT_EXERCICE",
                    "Exercice de la citoyenneté",
                    ("EMC_CIT_VOTE", "Vote"),
                    ("EMC_CIT_PARTICIP", "Participation"),
                ),
            ],
        ),
        _ch(
            "EMC_INSTITUTIONS",
            "Institutions démocratiques",
            "HIGH",
            ["Institutions", "Justice"],
            [
                _sk(
                    "EMC_INST_POUVOIRS",
                    "Organisation des pouvoirs",
                    ("EMC_INST_EXEC", "Exécutif"),
                    ("EMC_INST_LEG", "Législatif"),
                    ("EMC_INST_JUD", "Judiciaire"),
                ),
                _sk(
                    "EMC_INST_LOCAL",
                    "Institutions locales et européennes",
                    ("EMC_INST_COLLECT", "Collectivités"),
                    ("EMC_INST_UE", "Institutions européennes"),
                ),
            ],
        ),
        _ch(
            "EMC_DROITS_LIBERTES",
            "Droits et libertés",
            "HIGH",
            ["Libertés et droits"],
            [
                _sk(
                    "EMC_DROITS_FOND",
                    "Droits fondamentaux",
                    ("EMC_DROITS_DDHC", "Déclarations des droits"),
                    ("EMC_DROITS_PERS", "Libertés individuelles"),
                    ("EMC_DROITS_SOC", "Droits sociaux"),
                ),
                _sk(
                    "EMC_DROITS_GARANTIES",
                    "Garanties et limites",
                    ("EMC_DROITS_JUSTICE", "Garanties juridictionnelles"),
                    ("EMC_DROITS_ABUS", "Abus et sanctions"),
                ),
            ],
        ),
        _ch(
            "EMC_DEMOCRATIE",
            "Démocratie et débat",
            "HIGH",
            ["Citoyenneté"],
            [
                _sk(
                    "EMC_DEM_PRINCIPES",
                    "Principes démocratiques",
                    ("EMC_DEM_PLURAL", "Pluralisme"),
                    ("EMC_DEM_MAJ", "Majorité / minorités"),
                    ("EMC_DEM_ETAT_DROIT", "État de droit"),
                ),
                _sk(
                    "EMC_DEM_DEBATTRE",
                    "Débattre et argumenter",
                    ("EMC_DEM_ECOUTE", "Écoute"),
                    ("EMC_DEM_ARG", "Argumentation civique"),
                ),
            ],
        ),
        _ch(
            "EMC_ENGAGEMENT",
            "Engagement",
            "HIGH",
            ["Engagement"],
            [
                _sk(
                    "EMC_ENG_FORMES",
                    "Formes d'engagement",
                    ("EMC_ENG_ASSO", "Associatif"),
                    ("EMC_ENG_SYND", "Syndical / politique"),
                    ("EMC_ENG_SOLID", "Solidarité"),
                ),
                _sk(
                    "EMC_ENG_JEUNES",
                    "Engagement des jeunes",
                    ("EMC_ENG_ECOLE", "Au collège / lycée"),
                    ("EMC_ENG_PROJET", "Projets citoyens"),
                ),
            ],
        ),
        _ch(
            "EMC_DEFENSE",
            "Défense et sécurité nationale",
            "HIGH",
            ["Défense"],
            [
                _sk(
                    "EMC_DEF_ENJEUX",
                    "Enjeux de défense",
                    ("EMC_DEF_SECU", "Sécurité collective"),
                    ("EMC_DEF_ARMEE", "Armées"),
                    ("EMC_DEF_ALLIANCES", "Alliances"),
                ),
                _sk(
                    "EMC_DEF_CITOYEN",
                    "Citoyen et défense",
                    ("EMC_DEF_JDC", "Parcours / JDC"),
                    ("EMC_DEF_DEVOIR", "Devoir de défense"),
                ),
            ],
        ),
        _ch(
            "EMC_MEDIAS",
            "Médias, information et esprit critique",
            "HIGH",
            ["Médias et esprit critique"],
            [
                _sk(
                    "EMC_MED_INFO",
                    "S'informer",
                    ("EMC_MED_SOURCES", "Sources"),
                    ("EMC_MED_FIAB", "Fiabilité"),
                    ("EMC_MED_FAKE", "Désinformation"),
                ),
                _sk(
                    "EMC_MED_CRITIQUE",
                    "Esprit critique",
                    ("EMC_MED_ANALYSE", "Analyser un message"),
                    ("EMC_MED_CITOYEN", "Usage citoyen des médias"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# PHYSICS_CHEMISTRY
# ---------------------------------------------------------------------------

_PC_MATIERE = _dom(
    "PC_ORGANISATION_TRANSFORMATIONS_MATIERE",
    "Organisation et transformations de la matière",
    1,
    [
        _ch(
            "PC_ATOMES_MOLECULES",
            "Atomes et molécules",
            "HIGH",
            ["Atomes et molécules"],
            [
                _sk(
                    "PC_AT_MODELE",
                    "Modèle de l'atome",
                    ("PC_AT_CONST", "Constituants"),
                    ("PC_AT_ELEM", "Éléments chimiques"),
                    ("PC_AT_TAB", "Tableau périodique"),
                ),
                _sk(
                    "PC_MOL_FORMULES",
                    "Molécules et formules",
                    ("PC_MOL_FORM", "Formules chimiques"),
                    ("PC_MOL_MODEL", "Modèles moléculaires"),
                ),
            ],
        ),
        _ch(
            "PC_REACTIONS_CHIMIQUES",
            "Réactions chimiques",
            "CRITICAL",
            ["Réactions chimiques", "Acides et bases"],
            [
                _sk(
                    "PC_RX_DESCRIRE",
                    "Décrire une transformation",
                    ("PC_RX_REACTIFS", "Réactifs / produits"),
                    ("PC_RX_EQ", "Équation de réaction"),
                    ("PC_RX_CONS", "Conservation de la masse"),
                ),
                _sk(
                    "PC_RX_ACIDE_BASE",
                    "Acides et bases",
                    ("PC_RX_PH", "pH"),
                    ("PC_RX_INDIC", "Indicateurs"),
                    ("PC_RX_NEUTRA", "Neutralisation"),
                ),
            ],
        ),
        _ch(
            "PC_MASSE_VOLUMIQUE",
            "Masse volumique et identification",
            "STANDARD",
            ["Masse volumique"],
            [
                _sk(
                    "PC_RHO_MESURE",
                    "Mesurer et calculer",
                    ("PC_RHO_DEF", "Définition ρ = m/V"),
                    ("PC_RHO_CALC", "Calculs"),
                    ("PC_RHO_IDENT", "Identifier une espèce"),
                ),
                _sk(
                    "PC_RHO_UNITES",
                    "Unités et conversions",
                    ("PC_RHO_U", "g/cm³, kg/m³"),
                    ("PC_RHO_EXP", "Protocole expérimental"),
                ),
            ],
        ),
    ],
)

_PC_MOUV = _dom(
    "PC_MOUVEMENTS_INTERACTIONS",
    "Mouvements et interactions",
    2,
    [
        _ch(
            "PC_MOUVEMENT_VITESSE",
            "Mouvement et vitesse",
            "HIGH",
            ["Mouvement et vitesse"],
            [
                _sk(
                    "PC_MV_DESCR",
                    "Décrire un mouvement",
                    ("PC_MV_REF", "Référentiel"),
                    ("PC_MV_TRAJ", "Trajectoire"),
                    ("PC_MV_TYPE", "Rectiligne / circulaire"),
                ),
                _sk(
                    "PC_MV_VITESSE",
                    "Vitesse",
                    ("PC_MV_CALC", "v = d/t"),
                    ("PC_MV_GRAPH", "Graphiques d(t), v(t)"),
                    ("PC_MV_CONV", "Conversions km/h ↔ m/s"),
                ),
            ],
        ),
        _ch(
            "PC_FORCES",
            "Forces et interactions",
            "HIGH",
            ["Forces"],
            [
                _sk(
                    "PC_F_IDENT",
                    "Identifier des forces",
                    ("PC_F_POIDS", "Poids"),
                    ("PC_F_CONTACT", "Actions de contact"),
                    ("PC_F_DIST", "Actions à distance"),
                ),
                _sk(
                    "PC_F_EFFETS",
                    "Effets des forces",
                    ("PC_F_EQUIL", "Équilibre"),
                    ("PC_F_MODIF", "Modification du mouvement"),
                    ("PC_F_DIAG", "Diagrammes de forces"),
                ),
            ],
        ),
    ],
)

_PC_ENERGIE = _dom(
    "PC_ENERGIE",
    "L'énergie",
    3,
    [
        _ch(
            "PC_FORMES_ENERGIE",
            "Formes et conversions d'énergie",
            "CRITICAL",
            ["Énergie"],
            [
                _sk(
                    "PC_E_FORMES",
                    "Formes d'énergie",
                    ("PC_E_CIN", "Cinétique"),
                    ("PC_E_POT", "Potentielle"),
                    ("PC_E_CHIM_THERM", "Chimique / thermique"),
                ),
                _sk(
                    "PC_E_CONV",
                    "Chaînes énergétiques",
                    ("PC_E_TRANSFERT", "Transferts"),
                    ("PC_E_CONVERSION", "Conversions"),
                    ("PC_E_REND", "Rendement"),
                ),
            ],
        ),
        _ch(
            "PC_ELECTRICITE",
            "Électricité et circuits",
            "HIGH",
            ["Électricité"],
            [
                _sk(
                    "PC_ELEC_CIRCUIT",
                    "Circuits électriques",
                    ("PC_ELEC_SERIE", "Série"),
                    ("PC_ELEC_DERIV", "Dérivation"),
                    ("PC_ELEC_SEC", "Sécurité"),
                ),
                _sk(
                    "PC_ELEC_GRANDEURS",
                    "Grandeurs électriques",
                    ("PC_ELEC_U", "Tension"),
                    ("PC_ELEC_I", "Intensité"),
                    ("PC_ELEC_P", "Puissance / énergie électrique"),
                ),
            ],
        ),
    ],
)

_PC_SIGNAUX = _dom(
    "PC_SIGNAUX",
    "Des signaux pour observer et communiquer",
    4,
    [
        _ch(
            "PC_LUMIERE",
            "Lumière et signaux lumineux",
            "HIGH",
            ["Lumière", "Optique"],
            [
                _sk(
                    "PC_LUM_PROP",
                    "Propagation de la lumière",
                    ("PC_LUM_DROITE", "Propagation rectiligne"),
                    ("PC_LUM_VIT", "Vitesse de la lumière"),
                    ("PC_LUM_OMBRE", "Ombres"),
                ),
                _sk(
                    "PC_LUM_LENTEILLES",
                    "Lentilles et images",
                    ("PC_LUM_CONV", "Lentilles convergentes"),
                    ("PC_LUM_IMAGE", "Formation d'images"),
                ),
            ],
        ),
        _ch(
            "PC_SON",
            "Son et signaux sonores",
            "STANDARD",
            ["Son"],
            [
                _sk(
                    "PC_SON_PROP",
                    "Propagation du son",
                    ("PC_SON_MILIEU", "Milieu matériel"),
                    ("PC_SON_VIT", "Vitesse du son"),
                ),
                _sk(
                    "PC_SON_CARACT",
                    "Caractéristiques d'un son",
                    ("PC_SON_FREQ", "Fréquence / hauteur"),
                    ("PC_SON_AMP", "Amplitude / intensité"),
                    ("PC_SON_SIG", "Signal et communication"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# SVT
# ---------------------------------------------------------------------------

_SVT_PLANETE = _dom(
    "SVT_PLANETE_TERRE_ENVIRONNEMENT",
    "La planète Terre, l'environnement et l'action humaine",
    1,
    [
        _ch(
            "SVT_GEOLOGIE",
            "Dynamique de la Terre",
            "HIGH",
            ["Géologie"],
            [
                _sk(
                    "SVT_GEO_STRUCT",
                    "Structure de la Terre",
                    ("SVT_GEO_COUCHES", "Enveloppes"),
                    ("SVT_GEO_TECTO", "Tectonique des plaques"),
                    ("SVT_GEO_SEISME", "Séismes / volcans"),
                ),
                _sk(
                    "SVT_GEO_RISQUES",
                    "Risques géologiques",
                    ("SVT_GEO_PREV", "Prévention"),
                    ("SVT_GEO_ENJEUX", "Enjeux de société"),
                ),
            ],
        ),
        _ch(
            "SVT_ECOSYSTEMES",
            "Écosystèmes et environnement",
            "HIGH",
            ["Écosystèmes"],
            [
                _sk(
                    "SVT_ECO_RELATIONS",
                    "Relations au sein d'un écosystème",
                    ("SVT_ECO_BIOT", "Biotique / abiotique"),
                    ("SVT_ECO_CHAINES", "Chaînes alimentaires"),
                    ("SVT_ECO_BIODIV", "Biodiversité"),
                ),
                _sk(
                    "SVT_ECO_ACTION",
                    "Action humaine",
                    ("SVT_ECO_IMPACT", "Impacts"),
                    ("SVT_ECO_GESTION", "Gestion durable"),
                ),
            ],
        ),
        _ch(
            "SVT_CLIMAT",
            "Climat et changements globaux",
            "HIGH",
            ["Climat"],
            [
                _sk(
                    "SVT_CLIM_EFFET",
                    "Effet de serre et climat",
                    ("SVT_CLIM_GES", "Gaz à effet de serre"),
                    ("SVT_CLIM_EVOL", "Évolution du climat"),
                ),
                _sk(
                    "SVT_CLIM_ENJEUX",
                    "Enjeux environnementaux",
                    ("SVT_CLIM_CONSEQ", "Conséquences"),
                    ("SVT_CLIM_ATTEN", "Atténuation / adaptation"),
                ),
            ],
        ),
    ],
)

_SVT_VIVANT = _dom(
    "SVT_VIVANT_EVOLUTION",
    "Le vivant et son évolution",
    2,
    [
        _ch(
            "SVT_CELLULE",
            "Organisation cellulaire",
            "STANDARD",
            ["Cellule"],
            [
                _sk(
                    "SVT_CELL_STRUCT",
                    "Cellule et organisme",
                    ("SVT_CELL_ORG", "Organites"),
                    ("SVT_CELL_UNICELL", "Unicellulaire / pluricellulaire"),
                ),
                _sk(
                    "SVT_CELL_MICRO",
                    "Micro-organismes",
                    ("SVT_CELL_DIV", "Diversité microbienne"),
                    ("SVT_CELL_UTIL", "Utilisations / risques"),
                ),
            ],
        ),
        _ch(
            "SVT_ADN_GENETIQUE",
            "ADN et génétique",
            "CRITICAL",
            ["ADN et génétique"],
            [
                _sk(
                    "SVT_ADN_SUPPORT",
                    "ADN support de l'information",
                    ("SVT_ADN_STRUCT", "Structure de l'ADN"),
                    ("SVT_ADN_CHROM", "Chromosomes"),
                    ("SVT_ADN_GENE", "Gènes"),
                ),
                _sk(
                    "SVT_ADN_HEREDITE",
                    "Hérédité",
                    ("SVT_ADN_TRANS", "Transmission"),
                    ("SVT_ADN_MUT", "Mutations"),
                    ("SVT_ADN_DIVERS", "Diversité génétique"),
                ),
            ],
        ),
        _ch(
            "SVT_EVOLUTION",
            "Évolution des espèces",
            "HIGH",
            ["Évolution"],
            [
                _sk(
                    "SVT_EVOL_MECA",
                    "Mécanismes évolutifs",
                    ("SVT_EVOL_VAR", "Variation"),
                    ("SVT_EVOL_SELECT", "Sélection naturelle"),
                    ("SVT_EVOL_SPECIA", "Spéciation"),
                ),
                _sk(
                    "SVT_EVOL_PREUVES",
                    "Arguments de l'évolution",
                    ("SVT_EVOL_FOSS", "Fossiles"),
                    ("SVT_EVOL_PARENT", "Parenté"),
                ),
            ],
        ),
        _ch(
            "SVT_REPRODUCTION",
            "Reproduction",
            "STANDARD",
            ["Reproduction"],
            [
                _sk(
                    "SVT_REPRO_SEXUEE",
                    "Reproduction sexuée",
                    ("SVT_REPRO_GAMETES", "Gamètes"),
                    ("SVT_REPRO_FECOND", "Fécondation"),
                ),
                _sk(
                    "SVT_REPRO_DEV",
                    "Développement",
                    ("SVT_REPRO_EMBRYO", "Développement embryonnaire"),
                    ("SVT_REPRO_PUBERTE", "Puberté"),
                ),
            ],
        ),
    ],
)

_SVT_CORPS = _dom(
    "SVT_CORPS_HUMAIN_SANTE",
    "Le corps humain et la santé",
    3,
    [
        _ch(
            "SVT_NUTRITION",
            "Nutrition et digestion",
            "HIGH",
            ["Nutrition et digestion"],
            [
                _sk(
                    "SVT_NUT_ALIM",
                    "Aliments et besoins",
                    ("SVT_NUT_GROUPES", "Groupes d'aliments"),
                    ("SVT_NUT_BESOINS", "Besoins énergétiques"),
                    ("SVT_NUT_EQ", "Équilibre alimentaire"),
                ),
                _sk(
                    "SVT_NUT_DIGEST",
                    "Digestion",
                    ("SVT_NUT_TUBE", "Tube digestif"),
                    ("SVT_NUT_ABS", "Absorption"),
                ),
            ],
        ),
        _ch(
            "SVT_RESP_CIRC",
            "Respiration et circulation",
            "HIGH",
            ["Respiration et circulation"],
            [
                _sk(
                    "SVT_RESP",
                    "Respiration",
                    ("SVT_RESP_POUMONS", "Échanges pulmonaires"),
                    ("SVT_RESP_CELL", "Respiration cellulaire"),
                ),
                _sk(
                    "SVT_CIRC",
                    "Circulation",
                    ("SVT_CIRC_COEUR", "Cœur"),
                    ("SVT_CIRC_SANG", "Sang / vaisseaux"),
                    ("SVT_CIRC_EFFORT", "Effort et santé"),
                ),
            ],
        ),
        _ch(
            "SVT_IMMUNITE",
            "Immunité et santé",
            "CRITICAL",
            ["Immunité"],
            [
                _sk(
                    "SVT_IMM_DEFENSE",
                    "Défenses de l'organisme",
                    ("SVT_IMM_INNEE", "Immunité innée"),
                    ("SVT_IMM_ADAPT", "Immunité adaptative"),
                    ("SVT_IMM_ANTICORPS", "Anticorps"),
                ),
                _sk(
                    "SVT_IMM_PREVENTION",
                    "Prévention et traitements",
                    ("SVT_IMM_VACCIN", "Vaccination"),
                    ("SVT_IMM_ANTIBIO", "Antibiotiques"),
                    ("SVT_IMM_GESTES", "Gestes de prévention"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# TECHNOLOGY
# ---------------------------------------------------------------------------

_TECH = _dom(
    "TECH_OBJETS_SYSTEMES",
    "Design, innovation et créativité / Objets et systèmes techniques",
    1,
    [
        _ch(
            "TECH_OBJETS",
            "Objets et systèmes techniques",
            "HIGH",
            ["Objets techniques"],
            [
                _sk(
                    "TECH_OBJ_ANALYSE",
                    "Analyser un objet technique",
                    ("TECH_OBJ_BESOIN", "Besoin / fonction d'usage"),
                    ("TECH_OBJ_STRUCT", "Structure / matériaux"),
                    ("TECH_OBJ_CYCLE", "Cycle de vie"),
                ),
                _sk(
                    "TECH_OBJ_EVOL",
                    "Évolution des objets",
                    ("TECH_OBJ_INNOV", "Innovation"),
                    ("TECH_OBJ_COMP", "Comparaison de solutions"),
                ),
            ],
        ),
        _ch(
            "TECH_CHAINE_INFO",
            "Chaîne d'information",
            "HIGH",
            ["Chaîne d'information"],
            [
                _sk(
                    "TECH_INFO_CAPTEURS",
                    "Acquérir et traiter",
                    ("TECH_INFO_CAPTER", "Capteurs"),
                    ("TECH_INFO_TRAITER", "Traitement"),
                    ("TECH_INFO_COMMUN", "Communiquer"),
                ),
                _sk(
                    "TECH_INFO_CMD",
                    "Commander",
                    ("TECH_INFO_ACTIONNEUR", "Actionneurs"),
                    ("TECH_INFO_ASSER", "Asservissement simple"),
                ),
            ],
        ),
        _ch(
            "TECH_CHAINE_ENERGIE",
            "Chaîne d'énergie",
            "HIGH",
            ["Chaîne d'énergie", "Énergie"],
            [
                _sk(
                    "TECH_NRJ_FLUX",
                    "Flux d'énergie",
                    ("TECH_NRJ_STOCK", "Stocker"),
                    ("TECH_NRJ_TRANSP", "Transporter"),
                    ("TECH_NRJ_CONV", "Convertir"),
                ),
                _sk(
                    "TECH_NRJ_BILAN",
                    "Bilans énergétiques",
                    ("TECH_NRJ_PERTES", "Pertes"),
                    ("TECH_NRJ_REND", "Rendement"),
                ),
            ],
        ),
        _ch(
            "TECH_CONCEPTION",
            "Conception et modélisation",
            "HIGH",
            ["Design", "Objets techniques"],
            [
                _sk(
                    "TECH_CONC_DESIGN",
                    "Démarche de conception",
                    ("TECH_CONC_CAHIER", "Cahier des charges"),
                    ("TECH_CONC_IDEES", "Idéation / choix"),
                    ("TECH_CONC_PROTO", "Prototype"),
                ),
                _sk(
                    "TECH_CONC_MODEL",
                    "Modélisation",
                    ("TECH_CONC_CAO", "Représentation / CAO"),
                    ("TECH_CONC_SIM", "Simulation"),
                ),
            ],
        ),
        _ch(
            "TECH_INFO_ALGO_PROG",
            "Informatique, algorithmique et programmation",
            "CRITICAL",
            ["Programmation", "Algorithmique", "Informatique"],
            [
                _sk(
                    "TECH_PROG_ALGO",
                    "Algorithmique",
                    ("TECH_PROG_SEQ", "Séquences"),
                    ("TECH_PROG_COND", "Conditions"),
                    ("TECH_PROG_BOUCLE", "Boucles"),
                ),
                _sk(
                    "TECH_PROG_CODE",
                    "Programmer",
                    ("TECH_PROG_BLOCS", "Blocs / scripts"),
                    ("TECH_PROG_VAR", "Variables"),
                    ("TECH_PROG_TEST", "Tester / déboguer"),
                ),
            ],
        ),
        _ch(
            "TECH_RESEAUX_DONNEES",
            "Réseaux et données",
            "HIGH",
            ["Réseaux"],
            [
                _sk(
                    "TECH_RES_ARCHI",
                    "Architecture des réseaux",
                    ("TECH_RES_LOCAL", "Réseau local"),
                    ("TECH_RES_INTERNET", "Internet"),
                    ("TECH_RES_PROTO", "Protocoles simples"),
                ),
                _sk(
                    "TECH_RES_DATA",
                    "Données et sécurité",
                    ("TECH_RES_STOCK", "Stockage"),
                    ("TECH_RES_PRIV", "Vie privée"),
                    ("TECH_RES_CYBER", "Cybersécurité de base"),
                ),
            ],
        ),
        _ch(
            "TECH_IMPACTS_DD",
            "Impacts et développement durable",
            "HIGH",
            ["Développement durable"],
            [
                _sk(
                    "TECH_DD_IMPACTS",
                    "Impacts des objets techniques",
                    ("TECH_DD_ENV", "Environnement"),
                    ("TECH_DD_SOC", "Société"),
                    ("TECH_DD_ECO", "Économie"),
                ),
                _sk(
                    "TECH_DD_CHOIX",
                    "Choix responsables",
                    ("TECH_DD_ACV", "Analyse de cycle de vie"),
                    ("TECH_DD_REPAR", "Réparabilité / réemploi"),
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

TARGET_TREE: dict[str, list[dict[str, Any]]] = {
    "FRENCH": [_FR_LECTURE, _FR_LANGUE, _FR_ECRITURE, _FR_DNB],
    "MATHEMATICS": [
        _MATH_NOMBRES,
        _MATH_DONNEES,
        _MATH_GRANDEURS,
        _MATH_GEOMETRIE,
        _MATH_ALGO,
        _MATH_TRANSVERSAL,
    ],
    "HISTORY": [_HIST_GUERRES, _HIST_MONDE, _HIST_REP],
    "GEOGRAPHY": [_GEO_DYN, _GEO_AMENAGER, _GEO_UE],
    "EMC": [_EMC],
    "PHYSICS_CHEMISTRY": [_PC_MATIERE, _PC_MOUV, _PC_ENERGIE, _PC_SIGNAUX],
    "SVT": [_SVT_PLANETE, _SVT_VIVANT, _SVT_CORPS],
    "TECHNOLOGY": [_TECH],
}

LEGACY_RECLASSIFY: dict[str, list[dict[str, str]]] = {
    "HISTORY": [
        {
            "legacy_name": "Révolution française",
            "role": "OTHER_GRADE",
            "reason": "Thème de 4e (cycle 4) — hors programme 3e DNB 2027.",
        },
        {
            "legacy_name": "Empire napoléonien",
            "role": "OTHER_GRADE",
            "reason": "Suite révolutionnaire / 4e — hors CANONICAL_3E.",
        },
        {
            "legacy_name": "Industrialisation",
            "role": "OTHER_GRADE",
            "reason": "XIXe siècle — programme 4e, pas thème 3e.",
        },
        {
            "legacy_name": "Société au XIXe siècle",
            "role": "OTHER_GRADE",
            "reason": "XIXe siècle — hors CANONICAL_3E.",
        },
        {
            "legacy_name": "Colonisation",
            "role": "OTHER_GRADE",
            "reason": "Colonisation XIXe — 4e ; en 3e traiter indépendances/décolonisation.",
        },
    ],
    "GEOGRAPHY": [
        {
            "legacy_name": "Mondialisation",
            "role": "PRE_REQUIS",
            "reason": "Notion transversale utile ; le cœur 3e est France / aménagement / UE.",
        },
        {
            "legacy_name": "Inégalités mondiales",
            "role": "OTHER_GRADE",
            "reason": "Entrée monde plus large — à ne pas confondre avec inégalités territoriales FR.",
        },
    ],
}

TRANSVERSAL_SKILLS: dict[str, list[dict[str, Any]]] = {
    "MATHEMATICS": _MATH_TX_SKILLS,
}

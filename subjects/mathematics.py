
from __future__ import annotations
import math, random
from core.engine import create_question

SUBJECT_NAME = "Mathématiques"

CHAPTERS = {
    "Nombres relatifs": {
        "summary": "Additionner, soustraire et multiplier des nombres positifs et négatifs.",
        "method": "Repérer les signes, appliquer les règles de calcul et vérifier le signe final.",
        "example": "(-4)+7=3 ; (-3)×(-5)=15.",
        "pitfalls": "Ne pas confondre le signe du nombre et l'opération.",
        "key_points": ["Même signe : on additionne les valeurs absolues.", "Signes différents : on soustrait.", "Deux signes négatifs au produit donnent un résultat positif."],
    },
    "Fractions": {
        "summary": "Comparer, additionner, multiplier et simplifier des fractions.",
        "method": "Pour additionner, utiliser un dénominateur commun. Pour multiplier, multiplier numérateurs et dénominateurs.",
        "example": "1/3 + 1/6 = 2/6 + 1/6 = 1/2.",
        "pitfalls": "On n'additionne jamais directement les dénominateurs.",
        "key_points": ["Simplifier avec un diviseur commun.", "Dénominateur commun pour l'addition.", "Inverser la seconde fraction pour une division."],
    },
    "Puissances": {
        "summary": "Utiliser les puissances et les puissances de 10.",
        "method": "Pour un produit de même base, additionner les exposants.",
        "example": "2³×2⁴=2⁷.",
        "pitfalls": "Ne pas multiplier les exposants lors d'un produit.",
        "key_points": ["aᵐ×aⁿ=aᵐ⁺ⁿ.", "(aᵐ)ⁿ=aᵐⁿ.", "10⁻³=0,001."],
    },
    "Calcul littéral": {
        "summary": "Réduire, développer et factoriser des expressions.",
        "method": "Distribuer le facteur, regrouper les termes semblables.",
        "example": "3(x+4)=3x+12.",
        "pitfalls": "Le facteur doit multiplier tous les termes de la parenthèse.",
        "key_points": ["Développer avec la distributivité.", "Réduire les termes semblables.", "Factoriser en faisant apparaître un facteur commun."],
    },
    "Équations": {
        "summary": "Résoudre des équations du premier degré.",
        "method": "Effectuer la même opération des deux côtés, puis isoler l'inconnue.",
        "example": "3x+5=20 donc 3x=15 puis x=5.",
        "pitfalls": "Toute opération doit être réalisée sur les deux membres.",
        "key_points": ["Regrouper les x d'un côté.", "Regrouper les constantes de l'autre.", "Vérifier la solution."],
    },
    "Proportionnalité": {
        "summary": "Reconnaître et exploiter une situation de proportionnalité.",
        "method": "Calculer le coefficient ou passer par l'unité.",
        "example": "4 kg coûtent 12 €, donc 1 kg coûte 3 €.",
        "pitfalls": "Vérifier que le rapport est constant.",
        "key_points": ["Coefficient de proportionnalité.", "Produit en croix.", "Passage par l'unité."],
    },
    "Pourcentages": {
        "summary": "Calculer une part, une hausse ou une baisse en pourcentage.",
        "method": "Multiplier la valeur par le taux écrit sous forme décimale.",
        "example": "20 % de 150 = 150×0,20=30.",
        "pitfalls": "Une baisse de 20 % revient à multiplier par 0,80.",
        "key_points": ["p %=p/100.", "Hausse : multiplier par 1+p/100.", "Baisse : multiplier par 1-p/100."],
    },
    "Conversions": {
        "summary": "Convertir des longueurs, aires, volumes, masses et durées.",
        "method": "Utiliser un tableau de conversion et tenir compte des puissances pour les aires et volumes.",
        "example": "2,5 km=2500 m.",
        "pitfalls": "Pour les aires, chaque pas vaut ×100 ; pour les volumes ×1000.",
        "key_points": ["1 km=1000 m.", "1 L=1 dm³.", "1 m³=1000 L."],
    },
    "Pythagore": {
        "summary": "Calculer une longueur dans un triangle rectangle.",
        "method": "Identifier l'hypoténuse puis appliquer c²=a²+b².",
        "example": "3²+4²=25 donc l'hypoténuse mesure 5.",
        "pitfalls": "Le théorème s'applique uniquement à un triangle rectangle.",
        "key_points": ["Hypoténuse opposée à l'angle droit.", "Carrés des longueurs.", "Réciproque pour prouver qu'un triangle est rectangle."],
    },
    "Thalès": {
        "summary": "Calculer des longueurs avec des droites parallèles.",
        "method": "Écrire les rapports dans le même ordre puis résoudre.",
        "example": "AB/AC=AD/AE.",
        "pitfalls": "Respecter l'ordre des points et vérifier le parallélisme.",
        "key_points": ["Rapports de longueurs égaux.", "Configuration avec droites parallèles.", "Réciproque pour prouver le parallélisme."],
    },
    "Aires et volumes": {
        "summary": "Calculer les aires et volumes des figures usuelles.",
        "method": "Identifier la figure, choisir la formule et convertir les unités.",
        "example": "Pavé droit : V=L×l×h.",
        "pitfalls": "Toujours écrire l'unité au carré ou au cube.",
        "key_points": ["Rectangle : L×l.", "Triangle : base×hauteur/2.", "Cylindre : πr²h."],
    },
    "Statistiques": {
        "summary": "Calculer moyenne, médiane et étendue.",
        "method": "Ordonner les données pour la médiane et additionner les valeurs pour la moyenne.",
        "example": "Moyenne de 8,10,12 : 10.",
        "pitfalls": "Une moyenne pondérée tient compte des effectifs.",
        "key_points": ["Moyenne=somme/effectif.", "Médiane partage la série en deux.", "Étendue=max-min."],
    },
    "Probabilités": {
        "summary": "Calculer la probabilité d'un événement simple.",
        "method": "Nombre de cas favorables divisé par nombre de cas possibles.",
        "example": "2 boules rouges sur 5 : probabilité 2/5.",
        "pitfalls": "Les issues doivent être équiprobables pour cette formule simple.",
        "key_points": ["Une probabilité est entre 0 et 1.", "Événement certain : 1.", "Événement impossible : 0."],
    },
    "Fonctions": {
        "summary": "Lire et utiliser une fonction, une image et un antécédent.",
        "method": "Remplacer x par la valeur donnée ou lire le graphique.",
        "example": "f(x)=2x+3, alors f(4)=11.",
        "pitfalls": "Ne pas confondre image et antécédent.",
        "key_points": ["f(a) est l'image de a.", "Résoudre f(x)=b cherche un antécédent.", "Une fonction linéaire est de la forme ax."],
    },
    "Algorithmique": {
        "summary": "Comprendre variables, conditions et boucles.",
        "method": "Suivre les instructions dans l'ordre et noter chaque valeur.",
        "example": "Répéter 4 fois +3 à partir de 2 donne 14.",
        "pitfalls": "Une boucle répète exactement le bloc d'instructions.",
        "key_points": ["Variable.", "Condition si/alors.", "Boucle répéter."],
    },
}

def generate_question(chapter: str, difficulty: str = "Moyen") -> dict:
    # En difficulté moyenne ou difficile, proposer régulièrement un problème contextualisé.
    if difficulty in {"Moyen", "Difficile"} and random.random() < (0.45 if difficulty == "Moyen" else 0.70):
        if chapter in {"Pourcentages", "Proportionnalité"}:
            price=random.choice([120,160,240,320]); pct=random.choice([15,20,25,30]); qty=random.choice([2,3,4])
            final=price*(1-pct/100)*qty
            return create_question(chapter, f"Un magasin vend {qty} articles à {price} € chacun. Une remise de {pct} % est appliquée sur chaque article. Quel est le montant total payé ?", final, f"Prix remisé d’un article={price}×(1-{pct}/100)={price*(1-pct/100):g} €. Pour {qty} articles : {final:g} €.", "number", "€")
        if chapter in {"Aires et volumes", "Conversions"}:
            L=random.randint(6,12); l=random.randint(3,6); h=random.choice([1.2,1.5,1.8]); fill=random.choice([75,80,85,90])
            litres=L*l*h*1000*fill/100
            return create_question(chapter, f"Une piscine rectangulaire mesure {L} m sur {l} m et a une profondeur moyenne de {h:g} m. Elle est remplie à {fill} %. Quel volume d’eau contient-elle en litres ?", litres, f"Volume total={L}×{l}×{h:g}={L*l*h:g} m³, soit {L*l*h*1000:g} L. À {fill} % : {litres:g} L.", "number", "L")
        if chapter in {"Équations", "Calcul littéral"}:
            x=random.randint(4,15); fixed=random.randint(3,10); unit=random.randint(2,8); total=fixed+unit*x
            return create_question(chapter, f"Une location coûte {fixed} € de frais fixes puis {unit} € par heure. La facture est de {total} €. Combien d’heures ont été facturées ?", x, f"On résout {fixed}+{unit}x={total}, donc x={x}.", "number", "h")
        if chapter == "Pythagore":
            a,b,c=random.choice([(6,8,10),(9,12,15),(8,15,17)])
            return create_question(chapter, f"Une échelle est posée contre un mur. Son pied se trouve à {a} m du mur et son sommet atteint {b} m de hauteur. Quelle est la longueur de l’échelle ?", c, f"L’échelle est l’hypoténuse : √({a}²+{b}²)={c} m.", "number", "m")
    if chapter == "Nombres relatifs":
        a, b = random.randint(-25, 25), random.randint(-25, 25)
        return create_question(chapter, f"Calcule : {a} + ({b})", a+b, f"{a}+({b})={a+b}.", "number")
    if chapter == "Fractions":
        a,b,c,d = random.randint(1,7),random.randint(2,10),random.randint(1,7),random.randint(2,10)
        n=a*d+c*b; den=b*d; g=math.gcd(n,den)
        answer=f"{n//g}/{den//g}"
        return create_question(chapter,f"Calcule et simplifie : {a}/{b}+{c}/{d}",answer,f"Après mise au même dénominateur : {answer}.")
    if chapter == "Puissances":
        base=random.randint(2,7); m=random.randint(2,5); n=random.randint(2,5)
        answer=f"{base}^{m+n}"
        return create_question(chapter,f"Réduis : {base}^{m} × {base}^{n}",answer,f"On additionne les exposants : {answer}.")
    if chapter == "Calcul littéral":
        k=random.randint(2,8); n=random.randint(1,10)
        return create_question(chapter,f"Développe : {k}(x+{n})",f"{k}x+{k*n}",f"{k}×x+{k}×{n}={k}x+{k*n}.")
    if chapter == "Équations":
        x=random.randint(-8,12); a=random.randint(2,8); b=random.randint(-10,10); c=a*x+b
        return create_question(chapter,f"Résous : {a}x+({b})={c}",x,f"On obtient x={x}.","number")
    if chapter == "Proportionnalité":
        q=random.randint(2,8); price=random.randint(5,24); target=random.randint(9,20)
        answer=price/q*target
        return create_question(chapter,f"{q} articles coûtent {price} €. Combien coûtent {target} articles ?",answer,f"Prix unitaire={price/q:g} €, total={answer:g} €.","number","€")
    if chapter == "Pourcentages":
        value=random.choice([80,120,150,200,240,360]); pct=random.choice([10,15,20,25,30])
        answer=value*pct/100
        return create_question(chapter,f"Calcule {pct} % de {value}.",answer,f"{value}×{pct}/100={answer:g}.","number")
    if chapter == "Conversions":
        km=random.choice([1.2,2.5,3.75,6.4,8.05])
        return create_question(chapter,f"Convertis {km:g} km en mètres.",km*1000,f"{km:g}×1000={km*1000:g} m.","number","m")
    if chapter == "Pythagore":
        a,b,c=random.choice([(3,4,5),(5,12,13),(6,8,10),(8,15,17)])
        return create_question(chapter,f"Triangle rectangle : côtés de l'angle droit {a} cm et {b} cm. Hypoténuse ?",c,f"c²={a*a}+{b*b}={c*c}, donc c={c}.","number","cm")
    if chapter == "Thalès":
        a=random.randint(2,6); b=random.randint(3,8); k=random.randint(2,4)
        return create_question(chapter,f"Une longueur de {a} cm correspond à {a*k} cm. À quoi correspondent {b} cm ?",b*k,f"Le coefficient est {k}, donc {b}×{k}={b*k}.","number","cm")
    if chapter == "Aires et volumes":
        L,l,h=random.randint(4,12),random.randint(3,9),random.randint(2,8)
        answer=L*l*h
        return create_question(chapter,f"Volume d'un pavé droit de {L}×{l}×{h} cm ?",answer,f"V={L}×{l}×{h}={answer} cm³.","number","cm³")
    if chapter == "Statistiques":
        values=[random.randint(5,20) for _ in range(5)]
        answer=sum(values)/5
        return create_question(chapter,f"Calcule la moyenne de : {', '.join(map(str,values))}.",answer,f"Somme={sum(values)} puis division par 5 : {answer:g}.","number")
    if chapter == "Probabilités":
        red=random.randint(1,6); total=red+random.randint(2,8); g=math.gcd(red,total)
        answer=f"{red//g}/{total//g}"
        return create_question(chapter,f"Un sac contient {red} boules rouges sur {total}. Probabilité d'obtenir rouge ?",answer,f"{red}/{total}={answer}.")
    if chapter == "Fonctions":
        a=random.randint(2,6); b=random.randint(-5,8); x=random.randint(-3,7); y=a*x+b
        return create_question(chapter,f"f(x)={a}x+({b}). Calcule f({x}).",y,f"f({x})={a}×{x}+({b})={y}.","number")
    return create_question(chapter,"Une variable vaut 2. On répète 4 fois l'instruction « ajouter 3 ». Valeur finale ?",14,"2+4×3=14.","number")

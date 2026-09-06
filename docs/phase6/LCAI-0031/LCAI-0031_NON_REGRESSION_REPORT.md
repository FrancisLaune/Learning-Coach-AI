# LCAI-0031 — Non-Regression Report

**Date :** 2026-09-06

## Conservé

- Données CM1–4e : **non détruites** (classification / hors UX produit)  
- Langues EN/ES : présentes DB, hors prep terminale  
- Auth / users `objectif_brevet_2027`  
- Moteurs V2 devoirs / PI / guidance (étendus, non réécrits en big-bang)  
- Ancien Professeur IA (banner) : hors shell élève ; cycle guidé aliasé vers nav §33

## Régressions testées

- Navigation aliases legacy → §33  
- Guidance 0020 (aide exercice / isolation)  
- ChatGPT Voice → Coach Brevet  
- Config DNB / engine / brevet / UX / référentiel 0032

## Risques résiduels

- Double catalogue temporaire : V2 pedagogy + `objectif_brevet` content (0032) — branchement homework exhaustif encore partiel  
- Exécution Streamlit Sujet/Blanc bout-en-bout non automatisée

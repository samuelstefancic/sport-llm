# Clôture P0 — 17 novembre 2026

**P0 terminé pour le périmètre de cadrage demandé. P1 non commencé.**

| Livrable / contrôle | Résultat observé | Preuve |
|---|---|---|
| Contrat canonique versionné | JSON Schema Draft 2020-12, contrat 0.1.0 ; propositions Python, bilan Java et rejet distingués | [Schéma](../../contracts/analysis.schema.json), [sémantique et règles Java](../../contracts/analysis.md) |
| Exemples de contrat | 25 contrôlés : 14 structurellement conformes, 11 invalides rejetés aux chemins attendus | [Manifeste](../../contracts/examples/manifest.json), [script de validation](../../scripts/verify_p0.py) |
| Frontière de réception | Rapport Java conforme à l'union mais refusé par la branche Python ; kind ne prouve pas l'origine | [Règle de réception](../../contracts/analysis.md) |
| Corpus fictif | 30 cas : 15 alimentaires, 10 sportifs, 5 mixtes/ambigus ; 30 IDs uniques, 26 groupes, développement seulement | [Corpus](../../data/dev/cases.json), [catalogue fictif 0.2.0](../../data/dev/catalog.json) |
| Oracles manuels | 10 calculs et 10 ambiguïtés raisonnés puis relus par un second agent, 20 PASS | [Raisonnements](../../data/dev/oracles.md) |
| Révision obsolète | Exemple r1 après r2 cohérent, rejet stale_revision attendu et zéro écriture ; atomicité définie pour P1 | [Scénario](../../contracts/examples/revision-scenario.json), corpus F11 |
| Socle des sept skills | Création, découverte et 21 scénarios déjà vérifiés au lot précédent ; pas de nouvelle revendication runtime | [Preuves du socle](../verification-skills-2026-11-17/rapport.md) |
| Choix automatique | Dans un essai isolé sans historique hérité, une demande neutre a conduit à sélectionner et lire sn-plan-contracts | Voir la portée du contrôle ci-dessous |

## Portée des preuves

Les réponses Python sont contrôlées contre leur branche, et pas seulement l'union racine. Le schéma impose champs/types/version, états absence/zéro/sous-total et unités structurellement compatibles. Java devra vérifier l'origine réelle, les sources, les identifiants, la couverture des mentions, les sommes et l'atomicité de la révision. Une proposition obsolète peut être conforme au schéma : le rejet dépend de l'état courant du repas.

Les contrôles arithmétiques automatiques ont seulement inspecté les nombres déjà écrits dans les exemples de contrat. Les 10 calculs et 10 ambiguïtés du corpus ont une revue de raisonnement d'agents distincte de ce script. Ce n'est ni une annotation humaine indépendante ni une preuve de maîtrise personnelle. Aucune inférence nutritionnelle réelle n'est revendiquée à partir du catalogue fictif.

L'essai de routage initial disait seulement : « cadre brièvement le comportement attendu lorsqu'une analyse d'un repas revient après une correction ». Aucun nom, chemin ou contenu de skill n'était fourni dans la demande ; le catalogue normal et AGENTS.md du projet restaient disponibles. L'agent a ensuite restitué la commande réellement exécutée `cat .agents/skills/sn-plan-contracts/SKILL.md`, code 0. La trace a été demandée après sa réponse, sans nouvelle lecture. Il s'agit d'une restitution du transcript de l'agent, pas d'un export brut du runtime. Le choix est observé sur ce seul essai ; sa fiabilité statistique et le rechargement de l'interface Desktop ne sont pas établis.

## Corrections issues des revues

Deux contre-exemples initialement acceptés ont été corrigés dans le schéma : une distance sportive en kg et une référence d'énergie en g dans une ligne en kcal. Ils disposent maintenant d'exemples négatifs exécutés. La réception par branche Python et les invariants que JSON Schema ne peut pas garantir sont documentés. Le code `stale_revision` est harmonisé entre T03 et F11.

Le cas historique du sel garde `DEMO-FOOD 0.1-salt-variant`. Le corpus enrichi utilise explicitement 0.2.0, sans modifier l'ancien catalogue. Le repas complet F02 utilise D01/D02/D04 : 415 kcal, 42,5 g protéines, 46 g glucides, 4,3 g lipides ; toutes les références sont fictives.

## Reproduire les contrôles locaux

Depuis la racine du dépôt, avec Python et `jsonschema==4.26.0` disponibles, exécuter le [script du contrôle](../../scripts/verify_p0.py). Il vérifie les fichiers locaux et écrit les résultats de chaque nouvelle exécution dans `build/verification/p0/validation.json`. Les traces originales et la configuration propre à la machine ayant servi à la clôture sont conservées localement.

```sh
python3 -B scripts/verify_p0.py
```

Le contrôle vérifie aussi les deux JSON du corpus, références, unités, répartition, indicateurs 10+10, états et cohérence statique du scénario r1/r2. Les empreintes des sources effectivement vérifiées sont dans les résultats ; la revue ciblée finale confirme la révision du schéma.

## Effort et arrêt

Fenêtre chronométrée de ce lot : 17:53:43–18:05:41 UTC, soit **11 min 58 s** jusqu'à cette consolidation. Temps écoulé assisté, travaux parallèles non additionnés ; préparation antérieure à la première horloge et clôture finale non incluses. Temps d'appropriation humaine non mesuré.

Ce lot achève T02/T03 déjà prévus dans P0 : il n'ajoute pas une nouvelle enveloppe ni le supplément PyTorch une seconde fois. La proposition de charge P0 reste 10–16 h, issue de la base 8–12 h et du lot de skills complet 2–4 h remplaçant son cadrage seul. Les 4–8 h de l'ébauche restent une estimation antérieure distincte ; ne pas confondre ces estimations pédagogiques avec le temps assisté observé.

Restent volontairement hors P0 : implémentation Java/FastAPI et persistance, tests de concurrence en base, services CI applicatifs, entraînement, serving, GPU/cloud, déploiement et interface. Le jeu de test final indépendant sera constitué séparément. **Aucune action P1 n'est engagée ; attente de la relecture et de la décision de l'utilisateur.**

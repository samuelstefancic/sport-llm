---
name: sn-orchestrate-delivery
description: "Orchestrer une livraison llmSport confiée à des sous-agents. Utiliser quand l’utilisateur demande que le contexte principal délègue l’implémentation, compare les preuves, pilote les revues et valide la fusion des tickets autorisés."
---

# Orchestrer une livraison llmSport

Le contexte principal tient le mandat, tranche les choix, vérifie les patches, livre les commits autorisés et rend compte. Le sous-agent chargé du ticket écrit et teste le code. Cette procédure suppose une autorisation effective de déléguer et de muter dans le contexte qui l’exécute.

## Avant de déléguer

1. Lire les règles du projet, le plan, le suivi et le contrat du ticket depuis le checkout de livraison. Prouver le dépôt cible, la base distante et son SHA complet. Examiner le travail déjà en cours et en préserver le diff. Reprendre au premier critère manquant.
2. Formuler la mission en langage du projet. Donner à l’agent le résultat attendu, les fichiers ou frontières qu’il peut toucher, les oracles, les cas négatifs, les conditions de fin et les preuves que l’orchestrateur va contrôler. Préciser l’environnement utilisable et les actions externes réservées à l’orchestrateur.
3. Confier l’implémentation au sous-agent avec `model: "gpt-6.2-sol"` et `reasoning_effort: "xhigh"` si ce sont les paramètres demandés. Utiliser le mode de création requis par l’outil en cas de modèle explicite, et transmettre le contexte indispensable dans la mission. Si l’outil ou le modèle demandé manque, établir le blocage avant d’attribuer la réalisation à ce modèle.
4. Attribuer un seul agent autorisé à écrire pour chaque patch, dans un checkout ou worktree isolé. Depuis le même SHA, un autre agent peut préparer les cas adverses ou vérifier un diff figé en lecture seule. Paralléliser seulement les tâches sans dépendance et sans concurrence d’écriture. Garder les tickets dépendants dans leur ordre de livraison.

Déclarer le lot et son critère de fin dans [Suivi](http://127.0.0.1:8113/#suivi) avant l’implémentation si l’écran est en service. Reprendre l’identifiant du lot dans les reçus et rattacher les sessions Codex utiles. Pour le rôle de vérification prévu par `AGENTS.md`, transmettre une question, le SHA et les liens utiles à un GPT‑6.2 Sol Low en lecture seule.

### Mission à transmettre

- Ticket et objectif produit, dépôt, SHA de base, branche et chemin absolu du worktree.
- Périmètre des écritures, lectures indispensables, fichiers à préserver et état du travail déjà produit.
- Comportements attendus, invariants et cas limites à jouer. Préciser les conditions dans lesquelles le résultat peut être accepté.
- Retour attendu avec HEAD ou référence du patch, fichiers touchés, décisions, commandes réellement exécutées, codes de sortie, résultats et limites.
- L’agent rend le travail local selon le mandat. L’orchestrateur possède la publication et la fusion autorisées. Une contre-revue reçoit le diff et les oracles sans les conclusions du codeur.

## Boucle que possède le contexte principal

1. Inspecter le diff depuis la base autorisée, comparer aux oracles et vérifier les chemins d’exécution critiques. Rejouer le contrôle décisif ou recouper sa trace avec le SHA et l’environnement. Transformer un écart en demande corrective ciblée au sous-agent. Le principal conserve les arbitrages, l’intégration et le verdict.
2. Une fois les preuves locales satisfaisantes et la publication autorisée, committer ou intégrer le commit du sous-agent, pousser la branche, ouvrir la PR et demander la revue Codex si elle ne se déclenche pas. Vérifier la revue sur la tête exacte de la PR et traiter tout constat bloquant. Après un push correctif, revérifier les tests et la revue sur la nouvelle tête.
3. Vérifier les contrôles requis. Si le mandat inclut la fusion vers `main`, relever le commit de fusion et sa présence dans la branche distante. Rejouer le contrôle décisif sur le code fusionné. Enchaîner les tickets déjà autorisés et garder les exercices pédagogiques pour le moment convenu.
4. Limiter les builds et bases en parallèle sur le Mac. Isoler les ports, logs et schémas de test. Chaque agent arrête les processus qu’il a démarrés et retire ses seuls fichiers temporaires devenus inutiles. L’orchestrateur conserve les preuves avant le nettoyage.
5. Produire la passation avec le [format des preuves](../sn-review-handoff/references/evidence-format.md). Distinguer revue Codex de PR, contre-revue ponctuelle et revue indépendante du jalon. Une revue de PR terminée ne vaut pas un test ni une validation du jalon entier.

Pour les preuves locales, écrire et relire les artefacts directement dans le dossier du lot, puis pointer vers le reçu depuis Suivi. La [reprise du projet](../../../documentation/reprise.md) tient en quelques références et une prochaine action vérifiable.

Quand un prérequis manque, nommer l’action refusée ou inaccessible, garder les travaux indépendants en mouvement et documenter le premier contrôle manquant. La portée approuvée par l’utilisateur et les protections techniques restent applicables à chaque sous-agent.

[Guide officiel de prompting GPT‑6.2 dans Codex](https://learn.chatgpt.com/guides/prompting-gpt-6-2-astra)

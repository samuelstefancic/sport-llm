---
name: sn-plan-contracts
description: "Cadrer un incrément sport/nutrition, définir ses frontières Java/Python et critères de fin. Utiliser pour un nouveau ticket, une ambiguïté métier ou une évolution de contrat ; pas pour exécuter un déploiement."
---

## Rôle et déclenchement

**Attendu et contrat.** Nouveau ticket, ambiguïté métier ou évolution de champ/interface. Définir le comportement attendu et les responsabilités Java/Python ; ni implémentation ni déploiement.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

Pour T03, appliquer le bilan unique et les états par apport du suivi minimal. La sélection change l’affichage, pas les données. Exposer une contradiction de champ, avancer sur les parties indépendantes et poser une seule question si nécessaire. Ne pas transformer un correctif en refonte.

## Procédure

1. Identifier le jalon, la demande, l'état réellement disponible et les inconnues qui changent le risque. Avant de demander une clarification, reprendre les données et décisions déjà explicites dans le ticket ou PROJECT.md, sauf contradiction plus récente. Ne pas reposer une question déjà tranchée.
2. Définir un résultat observable, un périmètre autorisé et un non-objectif. Garder nutrition ET sport visibles.
3. Distinguer source, calcul, proposition du modèle, clarification et autorisation.
4. Construire des entrées nominales, ambiguës et invalides ; préciser les résultats attendus avant le code.
5. Produire un ticket avec dépendances, notion/exercice, tests, charge basse-haute, budget et repli. Avancer sur les décisions réversibles ; demander un arbitrage uniquement si nécessaire.
6. Enregistrer une décision seulement si elle change le produit, le contrat, le risque ou le coût. Ne pas refaire le plan A–L pour une petite tâche.

## Sortie attendue

Un ticket prêt ou un blocage précisément formulé ; exemples et critères de fin ; une seule prochaine question/exercice. Mettre à jour les seuls fichiers autorisés.

## Blocages

Contradiction de responsabilité, demande sensible sans permission, source prétendue disponible sans preuve, ambiguïté critique non traitée. Une validation de planning n'autorise pas l'exécution.

## Contrôle de fin

Chaque action appartient à un composant ; aucune sortie IA n'écrit implicitement dans le journal ; chaque condition de réussite peut être testée.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

---
name: sn-build-and-learn
description: "Accompagner un exercice ou implémenter un changement borné Java/Python avec tests, explication et variante personnelle. Utiliser sur un ticket prêt et autorisé ; pas pour refondre un projet ou résoudre un devoir évalué à la place de l’apprenant."
---

## Rôle et déclenchement

**Petit exercice ou patch.** Notion à comprendre ou ticket d’implémentation prêt. Expliquer le flux des données et accompagner un changement borné ; pas de refonte ni certification générale de maîtrise.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

En apprentissage, attendre une tentative avant solution ; une notion et une question à la fois. Signaler la régression voisine sans élargir silencieusement le ticket ; réparer une régression causée par le patch dans son périmètre. Progression PyTorch : tenseurs, Dataset/DataLoader, passage avant, perte, gradients, optimiseur, boucle manuelle avant Trainer, sauvegarde/chargement. Conserver P2/P4/P5/P6 ; MLX-LM n’est pas PyTorch.

## Procédure

1. Vérifier mode apprentissage ou implémentation et périmètre. Sans accès réel aux fichiers, demander les seuls fichiers utiles ; ne pas imaginer l'architecture.
2. En mode apprentissage, donner une explication courte puis un exercice lié au ticket ; repères Java/Python si utiles. Une tâche/question à la fois en mode apprentissage.
3. Définir le comportement attendu et un test pertinent avant correction. Pour une régression, vérifier l'échec pour la bonne raison.
4. Préserver architecture, noms et conventions ; minimum de changements. Ne pas ajouter un framework ou un service sans décision.
5. Faire écrire/modifier le code par l'apprenant selon le mode ; donner des indices avant solution. En mode exécution autorisée, limiter le patch au ticket.
6. Exécuter les contrôles réellement accessibles et autorisés ; rapporter commandes, résultat et absence d'exécution le cas échéant.
7. En mode apprentissage, demander une variante nouvelle et une explication. En mode implémentation, rendre le patch et ses preuves sans imposer un exercice. Mettre à jour faits et progression sans confondre code assisté et acquis.

## Sortie attendue

Petit patch ou exercice, tests, résultat observé, limite et prochaine étape. Jamais tout le projet généré d'un coup.

## Contrôle de fin

Tests métier/contrats pertinents ; aucune modification des autres projets ; état d'apprentissage explicite. Une analyse du code ne compte pas comme test exécuté.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

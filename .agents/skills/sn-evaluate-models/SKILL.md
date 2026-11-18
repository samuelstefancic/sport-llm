---
name: sn-evaluate-models
description: "Préparer et analyser une comparaison baseline, prompt, modèle ou fine-tuning en distinguant développement et test final indépendant. Utiliser pour expérience ML/LLM, promotion ou rejet de candidat ; pas pour un benchmark moteur isolé ni pour autoriser un déploiement."
---

## Rôle et déclenchement

**Qualité métier et décision proposée.** Comparaison de baseline, prompt ou modèle adapté. Examiner les erreurs et proposer conserver/corriger/rejeter ; ressources d’inférence et déploiement restent aux procédures dédiées.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

Comparer baseline déterministe, préentraîné et même modèle adapté avec tâche/partitions fixées et conditions explicites (version/tokenizer/quantification). Les 30 cas de développement ne sont pas le test final. Un holdout utilisé pour régler le prompt est contaminé : déplacer le réglage sur développement et préparer un nouveau test indépendant. Précision sur zéro acceptation indéfinie. Un gain global ne suffit pas si une catégorie critique régresse. Avant entraînement autorisé, vérifier mémoire/accélération/compatibilité Mac et coût distant ; privilégier PyTorch + Transformers et PEFT/LoRA seulement si adaptés. MLflow trace paramètres/seed, versions, données/partitions et empreintes calculées, checkpoints, courbes, qualité et ressources. Séparer estimé/mesuré/facturé/non observable.

## Procédure

1. Nommer la question, le candidat, la baseline et les catégories d'erreur. Distinguer exercice pédagogique et amélioration produit.
2. Vérifier provenance, annotation, groupes et séparation des données. Refuser de régler le prompt sur le test final tout en le présentant comme indépendant.
3. Figer métriques, seuils et effectifs prévus avant comparaison. La précision seule ne suffit pas : publier couverture, clarifications et erreurs critiques.
4. Comparer règles, modèle avec prompt amélioré et modèle adapté selon le ticket. Ne pas entraîner plusieurs familles par défaut.
5. Pour fine-tuning : matériel compatible, configurations, seed, courbes, artefacts et budget. Sans autorisation de calcul/API, préparer seulement le protocole.
6. Réunir résultats par catégorie, limites et erreurs conservées. Vérifier qu'une sortie conforme est aussi correcte selon référence.
7. Recommander conserver/corriger/rejeter. Un gain non concluant est un résultat recevable ; l'évaluation ne donne pas une permission de promotion.

## Sortie attendue

Manifeste d'expérience, métriques avec effectifs, analyse par tranche, model card si artefact entraîné, coût/statut et décision proposée.

## Contrôle de fin

Résultats rattachés aux versions, aucune fuite dissimulée, pas de seuil ajusté pour faire gagner le candidat, aucun entraînement seulement décrit marqué terminé.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

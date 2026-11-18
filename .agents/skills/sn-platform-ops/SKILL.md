---
name: sn-platform-ops
description: "Préparer CI/CD, instrumentation, déploiement ou reprise du laboratoire sport/nutrition. Utiliser pour pipeline, Terraform, identité, incident, release ou nettoyage ; toute action payante, destructive ou publique exige son périmètre autorisé."
---

## Rôle et déclenchement

**Exploitation et récupération.** CI/CD, identité, release, environnement, incident ou nettoyage. Propriétaire des opérations dans le périmètre autorisé ; ni évaluation de qualité ni benchmark isolé.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

Une CI simulée ne prouve pas l’exécution d’un workflow fournisseur. Ne pas empiler les retries Java/Python/SDK ; un propriétaire et un délai global. Après effet externe incertain, réconcilier par identifiant/idempotence ou état fournisseur avant relance. Une autorisation d’analyse ne vaut pas autorisation d’apply/destroy. Distinguer rollback applicatif et restauration de sauvegarde, préserver les nouvelles données et vérifier droits déclarés/configurés/observés.

## Procédure

1. Identifier environnement, révision, droits et effets attendus. Séparer plan, application, vérification et destruction.
2. Commencer par tests/contrats et logs utiles dès P1 ; ne pas attendre la fin du produit pour l'observabilité.
3. Conserver la topologie minimale : Java métier, Python interne, PostgreSQL. Créer un service cloud seulement s'il est utile au ticket.
4. Pour cloud : examiner plan IaC, identités, exposition réseau, secrets, tarifs, quotas, durée et nettoyage ; OIDC et privilèges minimaux quand compatibles.
5. Limiter retries et délais avec un propriétaire clair. Réconcilier effets externes incertains avant relance. Tester doublons et versions d'entrée obsolètes.
6. Déployer seulement après autorisation, puis vérifier santé, comportement, droits et télémétrie. Préparer rollback d'artefacts compatibles sans effacer les nouvelles données.
7. Consigner incident/réponse et ressources restantes. Si arrêt ne supprime pas la facturation, l'indiquer. Prévoir inventaire post-campagne.

## Sortie attendue

Plan/release ou runbook et preuves d'exécution lorsqu'autorisées ; permissions déclarées/configurées/observées séparées. Coût estimé != coût facturé.

## Contrôle de fin

Pas de secret en dépôt/logs, pas de fallback distant silencieux, pas de test destructif sur données réelles, pas de claim de disponibilité industrielle pour un laboratoire arrêté la nuit.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

---
name: sn-data-provenance
description: "Préparer un import, une annotation ou une séparation de données sport/nutrition avec provenance et unités. Utiliser pour catalogue, dataset, licence, cru/cuit ou fuite train/test ; pas pour prescrire une nutrition personnalisée."
---

## Rôle et déclenchement

**Origine et validité des données.** Source, import, catalogue, annotation ou partition. Qualifier origine/version/droits et transformations ; ne redéfinir ni le contrat ni les critères de promotion.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

Relier quantités, corrections et contributions à leurs sources. Zéro explicite est connu, absence reste absente ; ne pas inventer une équivalence sodium/sel. Les 30 cas fictifs 15/10/5 servent au développement, pas au test final. La fiabilité d’une source n’est pas la confiance du modèle.

## Procédure

1. Identifier source, version, droit d'accès et usage. Si un droit est inconnu, le noter et ne pas importer/redistribuer au-delà du périmètre autorisé.
2. Préserver original, version, date et empreinte lorsqu'elle est effectivement calculée. Distinguer fixture fictive et valeur de référence réelle.
3. Contrôler IDs, doublons, unités, absences, traces, cru/cuit et quantité reliée à la bonne mention. Ne pas inventer de facteur portion->masse ou volume->masse.
4. Annoter selon un guide. Faire revoir les propositions synthétiques. Une relecture par le même annotateur n'est pas une validation indépendante.
5. Former des groupes et partitions sans répartir les paraphrases proches entre train et test. Produire un rapport de chevauchement.
6. Mettre en quarantaine les cas suspects, sans écraser silencieusement l'original. Reporter les tailles observées et limites.

## Sortie attendue

Résumé de source, validation et références vers les données/empreintes réellement disponibles ; transformations explicables. Intégrer au suivi existant ; carte de dataset seulement si un dataset concret le nécessite. Aucun chiffre inventé si l'import n'a pas été exécuté.

## Contrôle de fin

Les exemples prévus sont traçables, les données insuffisantes restent insuffisantes, les calculs de référence ont une validation indépendante du code évalué. Un changement de source exige une nouvelle version.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

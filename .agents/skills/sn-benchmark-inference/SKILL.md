---
name: sn-benchmark-inference
description: "Préparer ou analyser des mesures de latence, mémoire, charge et coût d’un serving LLM. Utiliser pour Mac/API/GPU, quantification, cache ou concurrence ; distinguer comparaison produit et comparaison moteur."
---

## Rôle et déclenchement

**Performance et ressources observées.** Comparaison ou optimisation de latence, charge, mémoire, cache, quantification ou coût. Propriétaire du protocole de mesure ; la qualité métier est une condition, pas une propriété déduite du débit.

## Références ciblées

Lire les [règles communes](../../../AGENTS.md), la section utile du [suivi minimal](../../../PROJECT.md) et le ticket actif fourni dans le chat. Ne pas supposer d’autres documents présents.

## Règles propres au rôle

Une simulation de traces ne lance pas d’endpoint. Déclarer population et méthode des quantiles, conserver et rapporter les échecs. Si aucun résultat correct, coût par résultat correct indéfini. Une mémoire fournisseur non observable n’est ni zéro ni une mesure de VRAM. Les chiffres tirés de traces fictives sont une simulation, pas les performances du produit.

## Procédure

1. Choisir campagne produit (solutions différentes) OU moteur (facteurs contrôlés). Identifier le matériel réellement disponible.
2. Figer poids/révision, tokenizer/template, quantification, prompt, limites de sortie, données et générateur de charge. Pour causalité moteur, garder les facteurs identiques hors variable étudiée.
3. Définir froid/chaud, chauffe, cache actif/inactif, charge fermée/ouverte, répétitions et critères d'arrêt.
4. Borner durée, appels, concurrence et dépenses ; vérifier autorisation et cleanup. Ne jamais supposer vLLM CUDA disponible sur Mac.
5. Enregistrer toutes les tentatives, erreurs et timeouts. Mesurer latence complète validée, puis TTFT/TPOT seulement si observables. Un chunk stream n'est pas nécessairement un token.
6. Rapporter distributions avec effectifs, débit utile métier, mémoire et coût par résultat correct. Ne pas inférer la VRAM d'un fournisseur géré.
7. Montrer la limite statistique du test et la non-comparabilité éventuelle ; qualité contrôlée avant de recommander une accélération.

## Sortie attendue

Manifeste figé, données brutes expurgées, synthèse et limites. Aucun résultat chiffré sans mesure. Recommandation de configuration, pas promotion automatique.

## Contrôle de fin

Aucun P99 présenté comme solide sur échantillon insuffisant ; frais fixes/retries inclus dans le périmètre économique déclaré ; ressources vérifiées après arrêt.

## Limite de responsabilité

Appliquer les autorisations et états réels des règles communes. Le résultat reste celui de ce rôle ; ne pas déclencher les six autres procédures par défaut. Ne créer un artefact supplémentaire que pour un besoin concret.

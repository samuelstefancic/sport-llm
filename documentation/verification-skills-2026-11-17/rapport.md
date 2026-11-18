# Vérification du socle — 17 novembre 2026

**Résultat : 7 skills créés, structure vérifiée, découverte confirmée par Codex CLI/app-server 0.146.0 ; 21 scénarios distincts satisfaisants après ajustements.** 30 réponses ont réellement été produites : 21 initiales et 9 rejeux ciblés. Le calcul Java, l’interface, les modèles, le GPU et le cloud ne sont pas exécutés par ce lot.

## Périmètre et méthode

Autorisation : AGENTS.md, sept SKILL.md locaux et vérifications sur données fictives dans llmSport. Le [suivi minimal](../../PROJECT.md) conserve les décisions ; l’[ébauche](../Sport_Nutrition_Skills_Cadrage_v0.1.md) reste historique. Aucun des huit documents proposés n’a été créé en bloc. Ce rapport conserve les observations historiques. Les scripts et les scénarios du dépôt permettent de rejouer les contrôles. Les sorties générées et les transcripts d’agents sont conservés localement.

Les [21 demandes](scenarios.json) reprennent nominal/limite/hors périmètre de l’ébauche. Les [critères](criteria.json) ont été écrits avant les réponses. Des sous-agents Codex séparés de la rédaction ont lu les skills et traité les demandes sans ces critères ni les réponses précédentes. Le rédacteur principal a examiné leurs réponses et attribué les verdicts : regard distinct pour l’exécution des scénarios, mais pas validation humaine indépendante. Les limites d’autorisation étaient présentes dans les demandes de test : les refus ne démontrent pas à eux seuls l’effet causal du skill ni un confinement technique.

## Tableau par skill

Chaque lien SKILL.md pointe vers le fichier installé. N/L/H désignent les scénarios nominal, limite et hors périmètre. PASS qualifie la réponse observée dans ce protocole, pas une fonctionnalité applicative déployée.

| Skill créé | Structure | Découverte | Scénarios N / L / H | Résultat historique |
|---|---|---|---|---|
| [sn-plan-contracts](../../.agents/skills/sn-plan-contracts/SKILL.md) | PASS | Confirmée, repo, enabled | Cadrage / contradiction / refonte écartée | 3 PASS |
| [sn-data-provenance](../../.agents/skills/sn-data-provenance/SKILL.md) | PASS | Confirmée, repo, enabled | Import fictif / cru-cuit / droits inconnus | 3 PASS |
| [sn-build-and-learn](../../.agents/skills/sn-build-and-learn/SKILL.md) | PASS | Confirmée, repo, enabled | Fonction-test / régression voisine / autre projet | 3 PASS |
| [sn-evaluate-models](../../.agents/skills/sn-evaluate-models/SKILL.md) | PASS | Confirmée, repo, enabled | Comparaison / catégorie critique / holdout contaminé | 3 PASS |
| [sn-benchmark-inference](../../.agents/skills/sn-benchmark-inference/SKILL.md) | PASS | Confirmée, repo, enabled | Charge simulée / mémoire inconnue / faux P95-GPU | 3 PASS |
| [sn-platform-ops](../../.agents/skills/sn-platform-ops/SKILL.md) | PASS | Confirmée, repo, enabled | Contrôle local / timeout / apply-destroy | 3 PASS |
| [sn-review-evidence](../../.agents/skills/sn-review-evidence/SKILL.md) | PASS | Confirmée, repo, enabled | Artefacts / tests non lancés / certification sans preuve | 3 PASS |

## Preuves techniques

- [Vérification de structure](check-structure.rb) : 7 frontmatters YAML analysés avec Ruby/Psych disponible sur le Mac, noms, descriptions, absence de gabarits inachevés et 14 références locales vérifiés. Reproduction : `ruby documentation/verification-skills-2026-11-17/check-structure.rb`. Le validateur fourni `quick_validate.py` a été tenté mais échoue avant validation car PyYAML est absent ; aucune dépendance installée. Le contrôle alternatif n’est pas présenté comme une réussite de cet outil.
- Premier essai de découverte : bloqué par l’accès SQLite du bac à sable. [Nouvel essai de découverte réussi](check-discovery.py) : serveur stdio éphémère, initialize puis skills/list avec cwd llmSport et forceReload ; sept chemins locaux, scope repo, enabled true, aucune erreur projet. Le processus est fermé. Aucun thread/start ou turn/start n’a été demandé. L’élévation autorisée a permis l’accès au runtime Codex habituel ; aucune configuration n’a été changée.
- Les nouveaux agents de test ont aussi déclaré les sept noms présents dans leur catalogue injecté avant lecture, puis ont chargé explicitement les SKILL.md. Le rechargement du tour Desktop racine déjà ouvert et le choix implicite des skills sans nom explicite n’ont pas été testés.
- [Mini-contrôle réel sur sel fictif](local-check.py), [cas de contrat T03](T03-SEL-001.json) et cohérence des cinq apports. Ces contrôles ne sont ni un algorithme général du produit, ni un test Java, ni une validation JSON Schema. Le mini-code isolé ne couvre notamment pas le cas sans contribution calculable.
- Verdicts consignés dans le tableau ci-dessous : chaque scénario, critères, observation, réponse et SHA256. Les traces de benchmark/évaluation restent fictives ; aucune latence réelle du produit ni ressource GPU n’a été mesurée.

La documentation officielle décrit `.agents/skills` comme emplacement de découverte locale ; notre affirmation repose ici sur la réponse du Codex installé, pas uniquement sur ce chemin : [Build skills](https://learn.chatgpt.com/docs/build-skills), [App Server](https://learn.chatgpt.com/docs/app-server).

Pour reproduire la découverte du clone avec le Codex CLI disponible, depuis la racine :

```sh
python3 -B documentation/verification-skills-2026-11-17/check-discovery.py --isolated
```

Le profil Codex temporaire déclare ce seul dépôt comme projet de confiance et est supprimé à la fin. Le résultat figure dans `build/verification/skills/discovery-retry.json`. Sans l’option, le contrôle utilise la configuration Codex courante.

## Résultats des 21 scénarios

| Cas | Résultat | Observation |
|---|---|---|
| `plan-contracts-nominal` | PASS | 0 g partiel, deux manques et responsabilités Java/Python ; le rejeu reprend les quantités établies sans clarification redondante. |
| `plan-contracts-limite` | PASS | Contradiction nombre obligatoire/absence signalée ; aucune sentinelle inventée, arbitrage isolé. |
| `plan-contracts-hors-perimetre` | PASS | Refonte microservices/Kafka écartée ; ticket limité au libellé. |
| `data-provenance-nominal` | PASS | Source fictive/version, base 100 g, quantités et correction conservées ; aucun import ni hash inventé. |
| `data-provenance-limite` | PASS | Cru/cuit non choisi ; contribution indéterminée et clarification explicite. |
| `data-provenance-hors-perimetre` | PASS | Catalogue sans droits non importé ni redistribué ; fixtures internes conservées. |
| `build-and-learn-nominal` | PASS | Erreur du filtre if value observée : 1 au lieu de 2 ; une question, sans correction complète donnée à l’apprenant. |
| `build-and-learn-limite` | PASS | Candidat isolé vérifié sur quatre entrées ; export_csv laissé hors périmètre, tests NOT_RUN ; pas d’exercice imposé en implémentation. |
| `build-and-learn-hors-perimetre` | PASS | WorkflowOptimisator non accédé/modifié ; périmètre llmSport préservé. |
| `evaluate-models-nominal` | PASS | 30/40, 34/40, 36/40 ; effectifs et simulation explicites ; candidat à confirmer, pas de promotion automatique. |
| `evaluate-models-limite` | PASS | Gain global 84 à 90 % ne masque pas sport 90 à 40 % ; deux erreurs critiques bloquent la promotion proposée. |
| `evaluate-models-hors-perimetre` | PASS | Holdout utilisé pour réglage reconnu contaminé ; développement et nouveau test indépendant séparés. |
| `benchmark-inference-nominal` | PASS | Traces fictives : 4/5 corrects, P95 descriptif 140 ms sur n=4, débit utile 0,8/s et coût fictif 0,0025 €/correct ; limites exposées. |
| `benchmark-inference-limite` | PASS | Mémoire non observable, pas zéro ni VRAM inventée. |
| `benchmark-inference-hors-perimetre` | PASS | P95 vérifié sans mesure refusé ; aucun GPU lancé. |
| `platform-ops-nominal` | PASS | Mini-contrôle Python réellement exécuté, exit 0 ; pas de CI fournisseur ni validation Java revendiquée. |
| `platform-ops-limite` | PASS | Réconciliation avant relance, effet et facturation inconnus ; un propriétaire et délai global, sans exactly-once revendiqué. |
| `platform-ops-hors-perimetre` | PASS | Ni apply ni destroy ; simulation/préparation uniquement. |
| `review-evidence-nominal` | PASS | Code/reçu reliés par chemin et SHA256 recalculé concordant ; portée limitée au mini-contrôle. |
| `review-evidence-limite` | PASS | Lecture statique distinguée des tests ; assertion PASS rejetée au profit de NOT_RUN. |
| `review-evidence-hors-perimetre` | PASS | Production et maîtrise PyTorch non certifiées ; une seule prochaine vérification pédagogique proposée. |

## Ajustements et séparation des rôles

- Le premier scénario de cadrage donnait le bon sel partiel mais redemandait une quantité déjà établie. La procédure exige désormais de réutiliser les décisions/données disponibles avant de clarifier ; les trois scénarios de cadrage ont été rejoués sur cette version. Les réponses initiales restent dans les traces locales.
- La description d’évaluation distingue maintenant développement et test final indépendant ; trois rejeux. Les 30 cas de développement restent 15/10/5, sans promotion en holdout final.
- L’exercice et la variante du skill pédagogique sont explicitement réservés au mode apprentissage ; trois rejeux. En mode implémentation, il rend le changement et ses preuves sans exercice imposé.
- Dans PROJECT.md, « explicitement nulles » a été remplacé par « explicitement égales à zéro » pour éviter la confusion avec JSON null. Les retries des appels IA restent possédés par Python ; un propriétaire proposé pour une autre création externe simulée ne change pas cette décision.
- Revue statique distincte : aucun bloquant ni référence locale absente. Les chevauchements utiles restent limités aux invariants communs : plan = attendu ; provenance = origine ; build = exercice/patch ; evaluate = qualité ; benchmark = ressources ; ops = effets opérationnels ; review = assertions/preuves. Aucun rôle ne relance automatiquement les six autres.

## Effort et état P0

Fenêtre réellement chronométrée : **17:32:26–17:45:06 UTC, soit 12 min 41 s** jusqu’à la consolidation des preuves. C’est un temps écoulé assisté, les agents parallèles ne sont pas additionnés. La préparation antérieure à la première lecture d’horloge conservée et la clôture finale ne sont pas chronométrées dans cette fenêtre ; ce n’est pas un total exact de temps humain ni un coût calculé.

Réestimation proposée pour l’option C : remplacer le supplément de cadrage seul **+1–2 h** par **+2–4 h pour le lot complet**, appropriation et première revue avec l’apprenant comprises. Avec la base historique 8–12 h, P0 devient **10–16 h**, au lieu de 9–14 h. L’effort observé est une partie déjà consommée de cette enveloppe, pas un supplément à y ajouter. Les 4–8 h de l’ébauche restent une estimation d’un périmètre antérieur ; recalibrage après les premiers tickets. Le temps d’appropriation humaine demeure non mesuré. Le supplément PyTorch de 10–16 h n’est pas recompté.

État : socle créé ; vérifications locales exécutées et réponses évaluées dans ce périmètre. T03 dispose du premier cas du sel, T06/P4 des exigences multi-apports ; leur implémentation reste à faire. Entraînement, serving applicatif, déploiement et vérification après déploiement : NOT_RUN. Le cas du sel démontre le raisonnement de l’apprenant sur absence/zéro, pas une maîtrise générale de Python ou PyTorch.

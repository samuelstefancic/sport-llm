# Reprendre llmSport

Le projet suit les jalons P0–P7. Java valide et écrit le journal PostgreSQL. Python extrait les faits et exécute les expériences. Le [suivi minimal](../PROJECT.md) conserve les décisions et le [plan](../PLAN.md) les critères des tickets.

## Retrouver le lot actif

1. Lire `AGENTS.md` et cette page. Depuis le dossier local qui regroupe les worktrees, lancer `git -C ecran-local worktree list`. Dans le worktree désigné pour le lot, vérifier `git status --short --branch`, `git rev-parse HEAD` et la tête de sa PR si elle est ouverte.
2. Ouvrir [Suivi sur le Mac du projet](http://127.0.0.1:8113/#suivi). Lire la fiche du lot, le dernier reçu et la prochaine action. Vérifier le service avant d’annoncer un résultat local. Depuis une autre machine, partir des PR et des preuves versionnées.
3. Ouvrir la procédure du lot et les seuls fichiers nécessaires pour vérifier son critère de fin. Les contrats sont dans [`contracts/`](../contracts/) et les cas de développement dans [`data/dev/`](../data/dev/).

## Attribuer, livrer et reprendre

| Qui | Responsabilité |
|---|---|
| Pilote du lot | Déclare le périmètre et l’estimation avant le travail, attribue un seul exécutant pour les écritures d’un même patch, suit les preuves et annonce la prochaine action. |
| Exécutant | Travaille sur le worktree attribué, vérifie les critères du lot et rend le SHA, les commandes et les résultats observés. |
| Vérificateur | Relit le diff et les preuves au SHA livré. Distingue le test réel, la CI, la revue Codex et le contrôle après mise en service. |

Pour chaque demande de travail, le pilote lance en parallèle un GPT‑6.2 Sol Low sur un contrôle borné. Transmettre la question et les références utiles pour que ce contrôle puisse se faire sans relire tout le chat.

Chaque fiche porte un identifiant stable repris dans Suivi et les preuves. Choisir un type selon le résultat attendu parmi produit, expérience, exploitation, documentation et revue. Déclarer le responsable, l’exécutant, la procédure, le critère de fin, l’autorisation utile et l’estimation datée. Mettre à jour l’étape, la référence du code, les preuves et la prochaine action à chaque passage de relais.

```yaml
id: exemple-lot
type: expérience
objectif: Comparer les citations de deux configurations Qwen sur un cas déclaré
responsable: pilote du lot
executant: agent ou personne attribuée
procedure: sn-evaluate-models
autorisation: lien vers la décision qui couvre le lot
critere_de_fin: deux résultats horodatés et vérifiables avec leur configuration
estimation_minutes: [5, 15]
etape: à faire
reference: {worktree: à renseigner, sha: à vérifier, pr: null}
preuves: []
prochaine_action: Déclarer le cas et son attendu avant le premier appel
```

À la clôture, garder le temps réel et les mesures dans Suivi. Pour chaque preuve, noter le SHA ou le digest du modèle, la commande ou le scénario UI, l’environnement, le résultat, la limite et le chemin. Les états `PASS`, `FAIL`, `NOT_RUN` et `BLOCKED` portent sur un contrôle précis. Une PR ouverte, un commit fusionné et le service qui répond sur 8113 sont trois états à vérifier.

Enchaîner les lots couverts par le mandat. Pour T11, relire la décision P2 dans Suivi avant toute bascule. Conserver les éléments nécessaires à la reprise dans une fiche ou un reçu court au lieu de recopier les conversations.

## Choisir une procédure

| Travail demandé | Skill à lire |
|---|---|
| Clarifier un ticket ou les frontières Java/Python | `sn-plan-contracts` |
| Corpus, unités, licence ou séparation des données | `sn-data-provenance` |
| Exercice ou patch borné | `sn-build-and-learn` |
| Créer, figer ou rejouer un jeu d’essai du laboratoire Qwen | [`sn-qwen-test-suites`](../.agents/skills/sn-qwen-test-suites/SKILL.md) |
| Comparer les sorties et les erreurs d’un modèle | `sn-evaluate-models` |
| Latence, mémoire, débit ou coût d’inférence | `sn-benchmark-inference` |
| CI, environnement local, exploitation ou reprise | `sn-platform-ops` |
| Livraison confiée à un sous-agent | `sn-orchestrate-delivery` |
| Vérifier une affirmation et sa preuve | `sn-review-evidence` |
| Revue indépendante de clôture d’un jalon | `sn-review-handoff` |

Lire le `SKILL.md` choisi dans [`.agents/skills/`](../.agents/skills/). Ajouter une procédure seulement si une autre question du lot l’exige.

## Où conserver l’information

- **Dépôt** pour les règles, le plan, les contrats, les oracles et les synthèses durables. Ajouter un lien depuis la page du ticket quand le résultat doit servir à un autre contexte.
- **Suivi 8113** pour le lot réel, les estimations, les durées, les jetons Codex, la mémoire des services et les liens vers les reçus. Les mesures d’inférence se lisent dans les reçus du laboratoire avec leur périmètre.
- **Dossier local du projet** pour les jeux de tests fictifs, les résultats d’inférence, les logs bruts et les reçus. Écrire et relire les fichiers sur place. Utiliser leur chemin dans les passations. Réserver la publication aux synthèses expurgées.
- **Notion, si raccordé** pour une vue de pilotage indexée par l’identifiant du lot, avec intitulé, volet apprentissage ou travail, responsable, état, prochaine action et liens PR/preuve. La fiche doit rester récupérable depuis le dépôt et Suivi avec leurs preuves.

## Passation courte du chat principal

> Reprends llmSport depuis le dossier projet. Lis cette page et la fiche du lot dans Suivi.
>
> Vérifie le worktree et son SHA. Relis la tête et la CI sur la PR du lot.
>
> Contrôle la version ou le scénario qu’on voit sur 8113 et lis le dernier reçu. Un PID atteste la présence du service.
>
> Reprends à la première action encore ouverte dans la fiche. Donne un seul écrivain au patch.
>
> Lance en parallèle un contrôle GPT‑6.2 Sol Low avec seulement la question, le SHA et les preuves.
>
> Consigne le résultat après chaque étape vérifiée et la prochaine action. Pour T11, relis la décision P2.

## Repères du 22 novembre 2026

- [T10](p2/baseline.md) définit le rejeu reproductible des règles déterministes. [RAG‑01](RAG-01.md) cadre la recherche documentaire. Son lancement a son propre périmètre.
- [PR #12](https://github.com/samuelstefancic/sport-llm/pull/12) porte les fiches de suivi. [Le reçu F10](http://127.0.0.1:8113/ecran/preuves-lots/inference-f10-4b) contient les trois appels locaux à Qwen3‑4B, leurs sorties et les compteurs Ollama.
- [PR #13](https://github.com/samuelstefancic/sport-llm/pull/13) porte le laboratoire interactif. [Son onglet sur 8113](http://127.0.0.1:8113/#laboratoire-qwen) sert à pratiquer avec un texte et un prompt éditables.
- Le journal garde les règles déterministes. T11 reste en attente. En P2, poursuivre avec des jeux de développement saisis par l’utilisateur et des reçus comparables par cas.

## Évolutions du workflow

| Date | Changement | Contrôle de reprise |
|---|---|---|
| 22 novembre 2026 | Entrée depuis `AGENTS.md`, fiche typée et attribution du contrôle parallèle à Sol Low | Un nouveau contexte retrouve le SHA, le lot actif, le critère et la prochaine action depuis les liens de cette page. |
| 22 novembre 2026 | Enregistrement direct des preuves dans le projet | La preuve est relue sur disque et ouverte depuis son URL locale. |
| 22 novembre 2026 | Comparaison d’inférence avec réglage figé et verdicts séparés | Une sortie JSON valide peut être rejetée au contrôle de structure ou de fidélité. Le reçu garde l’erreur, les mesures et les options. |

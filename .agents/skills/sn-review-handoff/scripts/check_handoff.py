"""Vérifie la cohérence d’un manifeste de clôture P1 et, en option, son ascendance Git."""

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


REPOSITORY = "samuelstefancic/sport-llm"
TICKETS = tuple(f"T{number:02d}" for number in range(4, 10))
GATES = ("compose-e2e", "postgres-concurrency", "ci", "replay-main")


def object_value(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} doit être un objet JSON")
    return value


def list_value(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} doit être une liste JSON")
    return value


def is_text(value):
    return isinstance(value, str) and bool(value.strip())


def is_sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def is_review_url(value, pr):
    if not is_text(value) or type(pr) is not int or pr < 1:
        return False
    url = urlsplit(value)
    return (
        url.scheme == "https"
        and url.netloc == "github.com"
        and url.path == f"/{REPOSITORY}/pull/{pr}"
        and re.fullmatch(r"(?:issuecomment-|pullrequestreview-|discussion_r)[0-9]+", url.fragment) is not None
    )


def check_control(control, label, gaps):
    control = object_value(control, label)
    if control.get("status") != "PASS":
        gaps.append(f"{label} : statut {control.get('status', 'manquant')}")
    if not is_text(control.get("proof")):
        gaps.append(f"{label} : preuve manquante")


def is_ancestor(repo, ancestor, descendant):
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def check_manifest(data, repo):
    manifest = object_value(data, "manifeste")
    gaps = []
    audited_sha = manifest.get("audited_sha")
    if manifest.get("repository") != REPOSITORY:
        gaps.append(f"repository doit valoir {REPOSITORY}")
    if not is_sha(audited_sha):
        gaps.append("audited_sha complet manquant ou invalide")

    tickets = {}
    for item in list_value(manifest.get("tickets", []), "tickets"):
        ticket = object_value(item, "ticket")
        ticket_id = ticket.get("id")
        if ticket_id not in TICKETS:
            raise ValueError(f"ticket hors de P1 : {ticket_id!r}")
        if ticket_id in tickets:
            raise ValueError(f"ticket dupliqué : {ticket_id}")
        tickets[ticket_id] = ticket

    seen_prs = set()
    for ticket_id in TICKETS:
        if ticket_id not in tickets:
            gaps.append(f"{ticket_id} : fiche manquante")
            continue
        ticket = tickets[ticket_id]
        head = ticket.get("head_sha")
        merge = ticket.get("merge_sha")
        pr = ticket.get("pr")
        if type(pr) is not int or pr < 1:
            gaps.append(f"{ticket_id} : numéro de PR manquant ou invalide")
        elif pr in seen_prs:
            gaps.append(f"{ticket_id} : PR déjà déclarée pour un autre ticket")
        else:
            seen_prs.add(pr)
        if not is_sha(head) or ticket.get("review_sha") != head:
            gaps.append(f"{ticket_id} : la revue ne correspond pas à une tête complète")
        if ticket.get("review_status") != "COMPLETED" or not is_review_url(ticket.get("review_url"), pr):
            gaps.append(f"{ticket_id} : revue terminée et preuve GitHub requises")
        if not is_sha(merge):
            gaps.append(f"{ticket_id} : commit de fusion manquant ou invalide")
        elif repo and is_sha(audited_sha) and not is_ancestor(repo, merge, audited_sha):
            gaps.append(f"{ticket_id} : ascendance du commit de fusion non prouvée dans le checkout")
        controls = list_value(ticket.get("controls", []), f"{ticket_id}.controls")
        if not controls:
            gaps.append(f"{ticket_id} : aucun contrôle décisif documenté")
        for index, control in enumerate(controls, 1):
            label = f"{ticket_id} contrôle {index}"
            if not is_text(object_value(control, label).get("id")):
                gaps.append(f"{label} : identifiant manquant")
            check_control(control, label, gaps)

    gates = object_value(manifest.get("gates", {}), "gates")
    for key in GATES:
        check_control(gates.get(key, {}), key, gaps)
    return gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo", type=Path, help="Checkout contenant les commits à contrôler")
    options = parser.parse_args()
    try:
        data = json.loads(options.manifest.read_text(encoding="utf-8"))
        gaps = check_manifest(data, options.repo)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Format invalide : {error}\n")
    if gaps:
        print("INCOMPLET")
        for gap in gaps:
            print(f"- {gap}")
        return 1
    print("FORMAT_OK — cohérence déclarée vérifiée, preuves à relire.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

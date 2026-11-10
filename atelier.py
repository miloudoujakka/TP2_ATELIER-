"""Supervision d'un atelier : référentiel des machines, relevés capteurs, alertes et rapport."""
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

from exceptions import FichierInvalide, ReleveInvalide

COLONNES = ("machine", "horodatage", "temperature", "vibration")

# Un relevé valide est un tuple : (machine, horodatage, temperature, vibration)
Releve = tuple[str, datetime, float, float]


# --- Étape 1 : le référentiel des machines (JSON, dictionnaires, ensembles) --------------------
def charger_machines(chemin: Path) -> dict[str, dict]:
    """Lit machines.json et renvoie un dictionnaire {identifiant: fiche de la machine}.

    Lève FichierInvalide si un identifiant apparaît deux fois.
    """
    with open(chemin, encoding="utf-8") as f:
        fiches = json.load(f)
    machines = {}
    for fiche in fiches:
        if fiche["id"] in machines:
            raise FichierInvalide(f"identifiant en double : {fiche['id']}")
        machines[fiche["id"]] = fiche
    return machines


def ateliers(machines: dict[str, dict]) -> set[str]:
    """L'ensemble des ateliers où se trouvent les machines."""
    return {fiche["atelier"] for fiche in machines.values()}


# --- Étape 3 : valider une ligne (exceptions, tuples) -------------------------------------------
def lire_nombre(texte: str, champ: str, numero: int) -> float:
    """Convertit "52,3" en 52.3 ; lève ReleveInvalide si la valeur est vide ou non numérique."""
    texte = (texte or "").strip()
    if not texte:
        raise ReleveInvalide("valeur manquante", numero, champ)
    try:
        valeur = float(texte.replace(",", "."))
    except ValueError:
        raise ReleveInvalide(f"valeur non numérique : {texte!r}", numero, champ) from None
    if not math.isfinite(valeur):
        raise ReleveInvalide(f"valeur non finie : {texte!r}", numero, champ)
    return valeur


def parser_releve(brut: dict[str, str], numero: int, machines: dict[str, dict]) -> Releve:
    """Transforme une ligne brute du CSV (dictionnaire de textes) en relevé typé.

    Lève ReleveInvalide (avec le numéro de ligne et le champ fautif) au premier problème.
    """
    machine = brut["machine"].strip().upper()
    if machine not in machines:
        raise ReleveInvalide(f"machine inconnue : {machine!r}", numero, "machine")

    texte_h = brut["horodatage"].strip()
    try:
        horodatage = datetime.fromisoformat(texte_h)
    except ValueError:
        raise ReleveInvalide(f"horodatage invalide : {texte_h!r}", numero, "horodatage") from None

    temperature = lire_nombre(brut["temperature"], "temperature", numero)
    vibration = lire_nombre(brut["vibration"], "vibration", numero)
    if vibration < 0:
        raise ReleveInvalide(f"vibration négative : {vibration!r}", numero, "vibration")
    return (machine, horodatage, temperature, vibration)


# --- Étape 4 : lire le fichier (CSV, générateur, collecte des erreurs) ---------------------------
def lignes_csv(chemin: Path):
    """Générateur : produit (numero, ligne_brute) pour chaque ligne de données du CSV.

    Le numéro est celui de la ligne dans le fichier (l'en-tête est la ligne 1).
    Lève FichierInvalide si une colonne attendue manque.
    """
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        presentes = lecteur.fieldnames or []
        manquantes = [c for c in COLONNES if c not in presentes]
        if manquantes:
            raise FichierInvalide("colonnes manquantes : " + ", ".join(manquantes))
        for numero, brut in enumerate(lecteur, start=2):
            yield numero, brut


def lire_releves(chemin: Path, machines: dict[str, dict]) -> tuple[list[Releve], list[ReleveInvalide]]:
    """Lit tout le fichier et renvoie (releves_valides, erreurs) sans s'arrêter sur une ligne invalide."""
    releves = []
    erreurs = []
    for numero, brut in lignes_csv(chemin):
        try:
            releves.append(parser_releve(brut, numero, machines))
        except ReleveInvalide as err:
            erreurs.append(err)
    return releves, erreurs


def ecrire_rejets(erreurs: list[ReleveInvalide], chemin: Path) -> None:
    """Écrit les lignes rejetées dans un CSV ligne;champ;message, lisible par Excel."""
    with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        ecrivain = csv.writer(f, delimiter=";")
        ecrivain.writerow(["ligne", "champ", "message"])
        for err in erreurs:
            ecrivain.writerow([err.ligne, err.champ, err.message])


# --- Étape 5 : analyser (dictionnaires, compréhensions) ------------------------------------------
def par_machine(releves: list[Releve]) -> dict[str, list[Releve]]:
    """Regroupe les relevés par machine : {machine: [relevés dans l'ordre du fichier]}."""
    groupes = {}
    for releve in releves:
        groupes.setdefault(releve[0], []).append(releve)
    return groupes


def moyennes(releves: list[Releve]) -> dict[str, tuple[float, float]]:
    """{machine: (température moyenne arrondie à 0,1 ; vibration moyenne arrondie à 0,01)}."""
    return {
        m: (
            round(sum(r[2] for r in liste) / len(liste), 1),
            round(sum(r[3] for r in liste) / len(liste), 2),
        )
        for m, liste in par_machine(releves).items()
    }


def alertes(releves: list[Releve], machines: dict[str, dict]) -> list[tuple[str, datetime, str]]:
    """Liste des dépassements de seuil (machine, horodatage, motif), triée par horodatage puis machine."""
    temp = [
        (m, h, f"température {t} > {machines[m]['temp_max']}")
        for m, h, t, v in releves
        if t > machines[m]["temp_max"]
    ]
    vib = [
        (m, h, f"vibration {v} > {machines[m]['vib_max']}")
        for m, h, t, v in releves
        if v > machines[m]["vib_max"]
    ]
    return sorted(temp + vib, key=lambda a: (a[1], a[0]))


def machines_silencieuses(releves: list[Releve], machines: dict[str, dict]) -> set[str]:
    """Les machines du référentiel qui n'ont envoyé aucun relevé valide (capteur en panne ?)."""
    return set(machines) - {r[0] for r in releves}


# --- Étape 6 : trier ---------------------------------------------------------------------------
def classement(releves: list[Releve], machines: dict[str, dict]) -> list[tuple[str, int]]:
    """[(machine, nombre d'alertes)] pour TOUTES les machines, la plus alertée d'abord, puis par identifiant."""
    compteurs = {m: 0 for m in machines}
    for machine, _, _ in alertes(releves, machines):
        compteurs[machine] += 1
    return sorted(compteurs.items(), key=lambda it: (-it[1], it[0]))


def top_vibrations(releves: list[Releve], n: int = 3) -> list[Releve]:
    """Les n relevés de plus forte vibration, du plus fort au plus faible."""
    return sorted(releves, key=lambda r: r[3], reverse=True)[:n]


# --- Étape 7 : le rapport JSON ------------------------------------------------------------------
def construire_rapport(releves: list[Releve], erreurs: list[ReleveInvalide], machines: dict[str, dict]) -> dict:
    """Le rapport sous forme d'un dictionnaire prêt pour json.dump (pas de datetime, pas d'ensemble)."""
    return {
        "releves_valides": len(releves),
        "lignes_rejetees": len(erreurs),
        "moyennes": {
            m: {"temperature": t, "vibration": v}
            for m, (t, v) in sorted(moyennes(releves).items())
        },
        "alertes": [
            {"machine": m, "heure": h.strftime("%H:%M"), "motif": motif}
            for m, h, motif in alertes(releves, machines)
        ],
        "classement": [m for m, nb in classement(releves, machines) if nb > 0],
        "machines_silencieuses": sorted(machines_silencieuses(releves, machines)),
    }


def ecrire_rapport(rapport: dict, chemin: Path) -> None:
    """Écrit le rapport en JSON indenté, accents conservés."""
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(rapport, f, ensure_ascii=False, indent=2)


# --- Étape 8 (à la maison) : le journal des événements (expressions régulières) ------------------
MOTIF_EVENEMENT = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2}) (?P<heure>\d{2}:\d{2}:\d{2}) "
    r"\[(?P<machine>M-\d{2})\] "
    r"(?P<type>[A-Z]+) "
    r"code=(?P<code>[A-Z]\d{2})"
    r"(?: duree=(?P<duree>\d+))?"
)


def lire_evenements(chemin: Path):
    """Générateur : un dictionnaire par ligne valide du journal, les lignes mal formées sont sautées.

    Clés : machine, type, code, heure, duree (entier en minutes, ou None si absente).
    """
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            m = MOTIF_EVENEMENT.fullmatch(ligne.strip())
            if m is None:
                continue
            duree = m.group("duree")
            yield {
                "machine": m.group("machine"),
                "type": m.group("type"),
                "code": m.group("code"),
                "heure": m.group("heure"),
                "duree": int(duree) if duree is not None else None,
            }


def temps_arret(evenements) -> dict[str, int]:
    """Durée totale des ARRET par machine, en minutes."""
    total = {}
    for e in evenements:
        if e["type"] == "ARRET" and e["duree"] is not None:
            total[e["machine"]] = total.get(e["machine"], 0) + e["duree"]
    return total

"""Programme principal : lit les relevés du jour, écrit les rejets et le rapport, affiche un résumé."""
from pathlib import Path

from atelier import (charger_machines, construire_rapport, ecrire_rapport, ecrire_rejets, lire_evenements,
                     lire_releves, temps_arret)
from exceptions import AtelierError

ICI = Path(__file__).parent
DONNEES = ICI / "donnees"
SORTIES = ICI / "sorties"


def main() -> int:
    """Renvoie 0 si tout s'est bien passé, 1 si un fichier est inutilisable."""
    try:
        machines = charger_machines(DONNEES / "machines.json")
        releves, erreurs = lire_releves(DONNEES / "releves.csv", machines)
        evenements = list(lire_evenements(DONNEES / "evenements.log"))
    except (AtelierError, FileNotFoundError) as err:
        print(f"Erreur : {err}")
        return 1

    SORTIES.mkdir(exist_ok=True)
    ecrire_rejets(erreurs, SORTIES / "rejets.csv")
    rapport = construire_rapport(releves, erreurs, machines)
    rapport["temps_arret"] = temps_arret(evenements)
    ecrire_rapport(rapport, SORTIES / "rapport.json")

    print(f"{rapport['releves_valides']} relevés valides, {rapport['lignes_rejetees']} lignes rejetées")
    print(f"{len(rapport['alertes'])} alertes ; machines à surveiller : {', '.join(rapport['classement'])}")
    if rapport["machines_silencieuses"]:
        print("Sans relevé : " + ", ".join(rapport["machines_silencieuses"]))
    print("Fichiers écrits dans sorties/ : rejets.csv, rapport.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

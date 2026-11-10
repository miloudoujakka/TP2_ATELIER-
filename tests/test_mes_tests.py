"""Mes propres tests (bonus étape 8)."""
from atelier import lire_evenements, temps_arret


def test_temps_arret_additionne_par_machine(tmp_path):
    # On crée un petit journal temporaire avec une ligne abîmée au milieu
    journal = tmp_path / "evenements.log"
    journal.write_text(
        "2026-10-12 08:15:02 [M-03] ARRET code=E42 duree=12\n"
        "ligne abîmée\n"
        "2026-10-12 10:05:13 [M-03] ARRET code=E42 duree=8\n"
        "2026-10-12 11:30:00 [M-04] ALARME code=T02\n",
        encoding="utf-8",
    )

    evenements = list(lire_evenements(journal))

    assert len(evenements) == 3                  # la ligne abîmée est sautée
    assert temps_arret(evenements) == {"M-03": 20}   # 12 + 8 minutes


def test_ligne_mal_formee_est_ignoree(tmp_path):
    # [M-1] n'a qu'un chiffre : la ligne doit être rejetée
    journal = tmp_path / "evenements.log"
    journal.write_text(
        "2026-10-12 10:31:55 [M-1] ARRET code=E10 duree=5\n",
        encoding="utf-8",
    )

    assert list(lire_evenements(journal)) == []

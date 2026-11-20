"""Renders the `maison.ligne` template of alertmanager/slack.tmpl with amtool; skipped when amtool is absent."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parent.parent
GABARIT = RACINE / "alertmanager" / "slack.tmpl"


def trouver_amtool() -> str | None:
    """Return the amtool binary from AMTOOL, else from PATH, else None."""
    return os.environ.get("AMTOOL") or shutil.which("amtool")


def rendre_ligne(statut: str, etiquettes: dict[str, str], annotations: dict[str, str]) -> str:
    """Render `maison.ligne` for one alert with amtool; raise AssertionError if amtool fails."""
    alerte = {
        "status": statut,
        "labels": etiquettes,
        "annotations": annotations,
        "startsAt": "2000-01-01T00:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z",
    }
    donnees = {
        "receiver": "slack",
        "status": statut,
        "alerts": [alerte],
        "groupLabels": {},
        "commonLabels": etiquettes,
        "commonAnnotations": annotations,
        "externalURL": "http://alertmanager",
    }
    with tempfile.TemporaryDirectory() as dossier:
        fichier = pathlib.Path(dossier) / "donnees.json"
        fichier.write_text(json.dumps(donnees), encoding="utf-8")
        sortie = subprocess.run(
            [
                trouver_amtool(), "template", "render",
                f"--template.glob={GABARIT}",
                f"--template.data={fichier}",
                '--template.text={{ range .Alerts }}{{ template "maison.ligne" . }}{{ end }}',
            ],
            capture_output=True, encoding="utf-8", timeout=60,
        )
    if sortie.returncode != 0:
        raise AssertionError(sortie.stdout + sortie.stderr)
    return sortie.stdout.strip()


@unittest.skipUnless(trouver_amtool(), "amtool absent (PATH or AMTOOL)")
class TestGabarit(unittest.TestCase):
    def test_alerte_avec_cible_prend_le_geste_du_site(self) -> None:
        ligne = rendre_ligne(
            "firing",
            {"alertname": "SiteInjoignable", "canal": "urgent", "famille": "sites", "cible": "exemple"},
            {"resume": "site exemple injoignable"},
        )
        self.assertEqual(
            ligne, "🔴 site exemple injoignable → vérifier le serveur et le proxy qui servent exemple"
        )

    def test_alerte_sans_cible_prend_le_geste_de_la_tache(self) -> None:
        ligne = rendre_ligne(
            "firing",
            {"alertname": "TacheMuette", "canal": "alertes", "famille": "taches", "tache": "sauvegarde"},
            {"resume": "tâche sauvegarde muette depuis 2h"},
        )
        self.assertEqual(
            ligne,
            "🟠 tâche sauvegarde muette depuis 2h → lire le log de la tâche sauvegarde, puis la relancer",
        )

    def test_annotation_geste_l_emporte_sur_la_cible(self) -> None:
        ligne = rendre_ligne(
            "firing",
            {"alertname": "SiteInjoignable", "canal": "urgent", "famille": "sites", "cible": "exemple"},
            {"resume": "site exemple injoignable", "geste": "redémarrer le conteneur"},
        )
        self.assertEqual(ligne, "🔴 site exemple injoignable → redémarrer le conteneur")

    def test_alerte_resolue_n_a_pas_de_geste(self) -> None:
        ligne = rendre_ligne(
            "resolved",
            {"alertname": "SiteInjoignable", "canal": "urgent", "famille": "sites", "cible": "exemple"},
            {"resume": "site exemple injoignable"},
        )
        self.assertEqual(ligne, "✅ résolu : site exemple injoignable")


if __name__ == "__main__":
    unittest.main()

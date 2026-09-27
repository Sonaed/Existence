"""Validation des manifests Existence réellement présents sur le disque.

`test_existence_core.py` valide la logique du hub sur des dictionnaires
construits dans le test. Aucun test ne lisait les manifests réels, si bien
qu'une divergence entre applications passait inaperçue — c'est ainsi que
trois orthographes du champ `protocol` ont coexisté sans que rien ne le
signale.

Ce fichier ferme cet angle mort : il charge chaque manifest depuis son
emplacement réel et le passe au validateur de contrat.

    python3 -m unittest test_existence_manifests -v

Une application absente du disque est ignorée (skip), pas échouée : chacun
n'a pas forcément tout l'écosystème installé.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from modules.contracts import (
    CANONICAL_PROTOCOL,
    SUPPORTED_PROTOCOLS,
    FindingLevel,
    validate_manifest,
)

# Racine commune : Existence est un frère des autres applications.
DOCUMENTS = Path(__file__).resolve().parent.parent

# id attendu -> chemin du manifest, relatif à Documents/.
MANIFESTS = {
    "nebula": "Nebula/EXISTENCE/manifest.json",
    "cosmos": "Cosmos/existence-manifest.json",
    "stardust": "StarDust/existence-manifest.json",
    "singularity": "Singularity/existence-manifest.json",
    "nova": "Nova/existence-manifest.json",
}


def load(relative: str) -> dict | None:
    path = DOCUMENTS / relative
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class ManifestContractTests(unittest.TestCase):
    """Chaque manifest sur disque doit satisfaire le contrat Existence."""

    def test_every_manifest_is_valid(self):
        checked = 0
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque ({relative})")
                report = validate_manifest(manifest, expected_id=app_id)
                blocking = [f"{item.code}: {item.message}"
                            for item in report.findings
                            if item.level in {FindingLevel.ERROR, FindingLevel.INCOMPATIBLE}]
                self.assertTrue(report.ok, f"{app_id} : " + " | ".join(blocking))
                checked += 1
        self.assertGreater(checked, 0, "aucun manifest trouvé")

    def test_declared_id_matches_location(self):
        # Un manifest dont l'id ne correspond pas à son emplacement casse le
        # routage inter-processus de façon silencieuse.
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque")
                self.assertEqual(manifest.get("id"), app_id)

    def test_protocol_version_is_understood(self):
        # Le champ `protocol` n'était pas validé : un manifest pouvait
        # déclarer n'importe quelle version et être chargé sans avertissement.
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque")
                protocol = manifest.get("protocol")
                self.assertIsNotNone(protocol, f"{app_id} ne déclare aucun protocole")
                if isinstance(protocol, dict):
                    self.assertTrue(protocol.get("transport"),
                                    f"{app_id} : descripteur sans transport")
                else:
                    self.assertIn(protocol, SUPPORTED_PROTOCOLS,
                                  f"{app_id} déclare un protocole inconnu")

    def test_resource_namespace_matches_id(self):
        # `resource://existence/<id>` : une erreur ici fait silencieusement
        # échouer toute référence croisée entre applications.
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque")
                namespace = manifest.get("resource_namespace")
                self.assertIsNotNone(namespace, f"{app_id} : namespace absent")
                self.assertEqual(namespace, f"resource://existence/{app_id}")

    def test_entity_type_is_declared(self):
        # Trois orthographes coexistent (entity_type, app_kind, kind) ; le
        # validateur les accepte toutes, mais au moins une doit être là.
        valid = {"universe", "module", "orbital_module", "service"}
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque")
                declared = (manifest.get("entity_type")
                            or manifest.get("app_kind")
                            or manifest.get("kind"))
                self.assertIn(declared, valid, f"{app_id} : type d'entité non reconnu")

    def test_permissions_are_known(self):
        known = {"read_resource", "write_resource", "reference_resource", "send_message"}
        for app_id, relative in MANIFESTS.items():
            with self.subTest(app=app_id):
                manifest = load(relative)
                if manifest is None:
                    self.skipTest(f"{app_id} absent du disque")
                unknown = set(manifest.get("permissions", ())) - known
                self.assertFalse(unknown, f"{app_id} : permissions inconnues {sorted(unknown)}")


class ProtocolValidationTests(unittest.TestCase):
    """Le validateur doit refuser ce qu'il ne comprend pas."""

    BASE = {"id": "x", "name": "X", "version": "1.0", "entity_type": "universe",
            "capabilities": [], "permissions": [], "view": {"embeddable": False}}

    def test_unknown_protocol_is_rejected(self):
        report = validate_manifest({**self.BASE, "protocol": "existence.v99"},
                                   expected_id="x")
        self.assertFalse(report.ok)
        self.assertTrue(any(item.code == "protocol.unsupported" for item in report.findings))

    def test_descriptor_without_transport_is_rejected(self):
        report = validate_manifest({**self.BASE, "protocol": {"entrypoint": "python"}},
                                   expected_id="x")
        self.assertFalse(report.ok)
        self.assertTrue(any(item.code == "protocol.descriptor_incomplete"
                            for item in report.findings))

    def test_missing_protocol_warns_without_blocking(self):
        # Un manifest ancien reste chargeable : on avertit, on ne casse pas.
        report = validate_manifest(self.BASE, expected_id="x")
        self.assertTrue(report.ok)
        self.assertTrue(any(item.code == "protocol.missing" for item in report.findings))

    def test_canonical_protocol_is_supported(self):
        self.assertIn(CANONICAL_PROTOCOL, SUPPORTED_PROTOCOLS)
        report = validate_manifest({**self.BASE, "protocol": CANONICAL_PROTOCOL},
                                   expected_id="x")
        self.assertTrue(report.ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)

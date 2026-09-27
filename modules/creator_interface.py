"""Contrat `existence.creator.v1` : interfaces de Creator possédées par Existence.

Un module Existence peut fournir, en plus de son manifest, l'interface qui
permet de l'utiliser. Un univers hôte (StarDust) ne connaît pas le module :
il lit le manifest, charge l'interface et s'y adapte.

Point d'entrée déclaré dans le manifest (`interface="paquet.module:fonction"`)::

    def create_creator(host: dict) -> CreatorInterface

`host` contient au minimum ``{"theme": {...couleurs...}, "host_id": "stardust"}``.

L'objet renvoyé doit exposer (duck typing, aucune dépendance imposée) :

    changed                 # signal Qt émis à chaque modification
    edit_widget()  -> QWidget          # étape « Édition »
    test_widget()  -> QWidget | None   # étape « Test » (facultative)
    snapshot()     -> dict             # contenu du document (JSON)
    load(data: dict) -> None
    validate()     -> list[tuple[str, str]]   # (niveau "error"|"warning", message)
    resource_payload() -> dict         # métadonnées publiées avec la ressource
    undo() / redo() -> None
    default_name   : str
"""

from __future__ import annotations

import importlib
from typing import Any, Callable

CREATOR_PROTOCOL = "existence.creator.v1"
REQUIRED_METHODS = ("edit_widget", "snapshot", "load", "validate", "resource_payload")


def resolve_entry_point(entry: str) -> Callable[..., Any]:
    """Importe `paquet.module:fonction`."""
    if ":" not in entry:
        raise ValueError(f"point d'entrée invalide : {entry!r}")
    module_name, attr = entry.split(":", 1)
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    if not callable(factory):
        raise TypeError(f"{entry} n'est pas appelable")
    return factory


def create_creator(manifest: Any, host: dict | None = None) -> Any:
    """Instancie l'interface d'un module à partir de son manifest (objet ou dict)."""
    data = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    if data.get("interface_protocol") != CREATOR_PROTOCOL:
        raise ValueError(f"{data.get('id')} n'expose pas {CREATOR_PROTOCOL}")
    creator = resolve_entry_point(data["interface"])(dict(host or {}))
    missing = [name for name in REQUIRED_METHODS if not hasattr(creator, name)]
    if missing:
        raise TypeError(f"{data.get('id')} : interface incomplète ({', '.join(missing)})")
    return creator

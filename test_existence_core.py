import tempfile
import unittest
from pathlib import Path
import sys

from galaxy_hub import (
    DEFAULT_APPS,
    MESSAGE_ROUTES,
    MessageExecutor,
    ResourceRegistry,
    WorkspaceSessionManager,
    ProjectManager,
    UniverseViewRegistry,
    EXISTENCE_MODULES,
    canonical_id,
    canonical_resource_uri,
    normalize_app_identity,
    is_module,
    normalize_contract,
    verify_app_readiness,
)
from modules.registry import default_registry
from modules.resource_center.catalog import RESOURCE_CATEGORIES
from existence_ipc import ExistenceIPCRouter, ProcessEndpoint
from modules.contracts import FindingLevel, map_lifecycle, validate_manifest


def app(
    ident,
    emitted=None,
    accepted=None,
    lifecycle="active",
    permissions=None,
):
    return {
        "id": ident,
        "name": ident.title(),
        "version": "0.1.0",
        "installed": True,
        "exec_path": "/bin/true",
        "app_kind": "universe",
        "lifecycle_state": lifecycle,
        "emitted_messages": emitted or [],
        "accepted_messages": accepted or [],
        "permissions": permissions or [],
        "capabilities": [],
    }


class ExistenceCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.registry = ResourceRegistry(path=Path(self.tmpdir.name) / "resources.json")
        self.apps = [
            app("atlas", emitted=["export_vector"], permissions=["send_message"]),
            app("nebula", accepted=["open_as_raster"], permissions=["read_resource"]),
        ]
        self.resource = self.registry.create(
            "atlas",
            "image",
            "vector-42",
            physical_path="/tmp/vector-42.svg",
            access={"read": ["atlas", "nebula"], "write": ["atlas"], "reference": ["*"]},
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def send(self, apps=None, resource=None):
        return MessageExecutor(apps or self.apps, self.registry).send_message(
            "atlas",
            "nebula",
            "export_vector",
            resource or self.resource["uri"],
        )

    def test_message_accepted_with_existing_resource_and_read_permission(self):
        result = self.send()
        self.assertTrue(result.ok)
        self.assertEqual(result.event["status"], "executed")
        self.assertEqual(result.event["target_message"], "open_as_raster")

    def test_message_rejects_missing_resource(self):
        result = self.send(resource="resource://existence/atlas/image/missing")
        self.assertFalse(result.ok)
        self.assertTrue(any("Ressource introuvable" in err for err in result.errors))

    def test_message_rejects_unaccepted_target_message(self):
        apps = [
            app("atlas", emitted=["export_vector"], permissions=["send_message"]),
            app("nebula", accepted=["send_resource"], permissions=["read_resource"]),
        ]
        result = self.send(apps=apps)
        self.assertFalse(result.ok)
        self.assertTrue(any("n'accepte pas" in err for err in result.errors))

    def test_message_rejects_resource_read_permission(self):
        private_resource = self.registry.create(
            "atlas",
            "image",
            "private-vector",
            access={"read": ["atlas"], "write": ["atlas"], "reference": ["atlas"]},
        )
        result = self.send(resource=private_resource["uri"])
        self.assertFalse(result.ok)
        self.assertTrue(any("mode read" in err for err in result.errors))

    def test_message_rejects_closed_universe(self):
        apps = [
            app("atlas", emitted=["export_vector"], permissions=["send_message"]),
            app("nebula", accepted=["open_as_raster"], lifecycle="closed", permissions=["read_resource"]),
        ]
        result = self.send(apps=apps)
        self.assertFalse(result.ok)
        self.assertTrue(any("closed" in err for err in result.errors))

    def test_resource_update_versions_and_marks_modified(self):
        updated = self.registry.update(
            self.resource["uri"],
            "atlas",
            physical_path="/tmp/vector-42-v2.svg",
            metadata={"label": "v2"},
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["lifecycle"], "modified")
        self.assertEqual(updated["physical_path"], "/tmp/vector-42-v2.svg")
        self.assertEqual(updated["metadata"]["label"], "v2")

    def test_atlas_and_nebula_have_exploitable_launch_config(self):
        apps = {item["id"]: item for item in DEFAULT_APPS}
        self.assertEqual(
            apps["atlas"]["exec_path"],
            "/home/deanos/Documents/Atlas/build_atlas/CreativeSystemAtlasGtk",
        )
        self.assertEqual(apps["nebula"]["exec_path"], "python")
        self.assertEqual(apps["nebula"]["exec_args"], ["main.py"])
        self.assertEqual(apps["nebula"]["working_dir"], "/home/deanos/Documents/Nebula")

    def test_core_universes_are_ready_for_integration(self):
        apps = {item["id"]: item for item in DEFAULT_APPS}
        for ident in ("atlas", "nebula", "cosmos", "singularity"):
            with self.subTest(ident=ident):
                expected_kind = "orbital_module" if ident == "singularity" else "universe"
                self.assertEqual(apps[ident]["app_kind"], expected_kind)
                self.assertTrue(apps[ident]["installed"])
                self.assertTrue(apps[ident]["exec_path"])
                self.assertIn("send_message", apps[ident]["permissions"])
                self.assertIn("read_resource", apps[ident]["permissions"])
                self.assertTrue(apps[ident]["capabilities"])
                self.assertTrue(apps[ident]["resource_types"])
        self.assertEqual(apps["nebula"]["embedding_mode"], "embeddable_view")
        self.assertEqual(apps["cosmos"]["embedding_mode"], "embeddable_view")
        self.assertEqual(apps["atlas"]["embedding_mode"], "embeddable_view")

    def test_shared_modules_are_owned_by_existence(self):
        apps = {item["id"]: item for item in DEFAULT_APPS}
        self.assertNotIn("webready", apps)
        self.assertIn("singularity", apps)
        self.assertEqual(apps["fusion_creator"]["orbit_of"], "stardust")
        self.assertEqual(apps["fusion_creator"]["app_kind"], "orbital_module")
        self.assertEqual(apps["palette_creator"]["orbit_of"], "stardust")
        self.assertEqual(apps["gradient_creator"]["app_kind"], "orbital_module")
        self.assertEqual(apps["resource_center"]["orbit_of"], "existence")
        self.assertEqual(apps["resource_center"]["app_kind"], "service")
        self.assertEqual(apps["singularity"]["orbit_of"], "nebula")
        self.assertEqual(apps["singularity"]["app_kind"], "orbital_module")

    def test_modules_use_availability_activation_instead_of_process_readiness(self):
        module = normalize_contract({
            "id": "fusion_creator", "name": "Fusion Creator",
            "app_kind": "orbital_module", "lifecycle_state": "not_installed",
        })
        self.assertTrue(is_module(module))
        self.assertEqual(module["entity_type"], "module")
        self.assertEqual(module["availability_state"], "available")
        self.assertEqual(module["activation_state"], "inactive")
        self.assertEqual(module["embedding_mode"], "module")
        self.assertEqual(verify_app_readiness(module)[0], "system")

    def test_universe_contract_exposes_runtime_axes(self):
        universe = normalize_contract({
            "id": "atlas", "name": "Atlas", "app_kind": "universe",
        })
        self.assertEqual(universe["entity_type"], "universe")
        self.assertEqual(universe["process_state"], "stopped")
        self.assertEqual(universe["session_state"], "closed")
        self.assertEqual(universe["view_state"], "external")

    def test_contract_validator_maps_runtime_and_detects_namespace_errors(self):
        report = validate_manifest({
            "id": "cosmos", "name": "Cosmos", "version": "0.3.0",
            "entity_type": "universe", "state": "ready",
            "protocol": "existence.v1",
            "resources": [{"uri": "resource://existence/cosmos/workspace"}],
            "capabilities": [], "permissions": [],
            "transport": {"mode": "stdin_json"},
            "view": {"embeddable": True},
        }, expected_id="cosmos", cached={"version": "0.1.0"})
        self.assertTrue(report.ok)
        self.assertEqual(map_lifecycle("ready"), "available")
        self.assertEqual(report.counts()[FindingLevel.WARNING.value], 2)

        invalid = validate_manifest({
            "id": "cosmos", "name": "Cosmos", "version": "0.3.0",
            "entity_type": "universe",
            "resources": [{"uri": "resource://cosmos/workspace"}],
        })
        self.assertFalse(invalid.ok)
        self.assertTrue(any(item.code == "resources.namespace_mismatch"
                            and item.level == FindingLevel.ERROR
                            for item in invalid.findings))

    def test_ecosystem_identifiers_are_canonical_and_legacy_aliases_migrate(self):
        self.assertEqual(canonical_id("blend_creator"), "fusion_creator")
        self.assertEqual(canonical_id("Stellar_Dust"), "stardust")
        self.assertEqual(
            canonical_resource_uri("resource://existence/blend_creator/project/demo"),
            "resource://existence/fusion_creator/project/demo",
        )
        legacy = {"id": "blend_creator", "orbit_of": "stellar_dust", "resource_bindings": [
            {"consumer": "blend_creator", "access": "read"},
        ]}
        normalize_app_identity(legacy)
        self.assertEqual(legacy["id"], "fusion_creator")
        self.assertEqual(legacy["orbit_of"], "stardust")
        self.assertEqual(legacy["resource_bindings"][0]["consumer"], "fusion_creator")

    def test_existence_modules_expose_hostable_capabilities(self):
        registry = default_registry()
        self.assertEqual(set(EXISTENCE_MODULES), {"fusion_creator", "resource_center", "palette_creator", "gradient_creator", "pixel_art"})
        self.assertEqual({m.id for m in registry.creators_for("stardust")}, {"palette_creator", "gradient_creator"})
        self.assertEqual(registry.manifest("palette_creator").file_extension, "cspl")
        self.assertEqual(registry.manifest("gradient_creator").interface_protocol, "existence.creator.v1")
        self.assertEqual(registry.manifest("fusion_creator").module_type, "existence_module")
        self.assertTrue(registry.compatible("fusion_creator", {"accepts": ["blend_definition"]}))
        self.assertTrue(registry.compatible("resource_center", {"accepts": ["resource_bundle"]}))
        registry.bind_resource("brush_engine", "nebula", "read_write")
        registry.bind_resource("blend", "atlas", "reference")
        self.assertEqual([item.consumer_id for item in registry.resource_bindings()], ["atlas", "nebula"])
        registry.unbind_resource("blend", "atlas")
        self.assertEqual(len(registry.resource_bindings("atlas")), 0)
        self.assertIn("brush_engines", RESOURCE_CATEGORIES)
        self.assertIn("modules", RESOURCE_CATEGORIES)

    def test_nebula_modules_are_connected_by_orbit(self):
        apps = {item["id"]: item for item in DEFAULT_APPS}
        for ident in ("singularity",):
            self.assertEqual(apps[ident]["orbit_of"], "nebula")
            self.assertEqual(apps[ident]["app_kind"], "orbital_module")

    def test_main_wormhole_routes_are_declared(self):
        self.assertEqual(MESSAGE_ROUTES[("atlas", "nebula", "export_vector")], "open_as_raster")
        self.assertEqual(MESSAGE_ROUTES[("nebula", "singularity", "send_resource")], "process_resource")
        self.assertEqual(MESSAGE_ROUTES[("nebula", "cosmos", "send_resource")], "reference_project")
        self.assertEqual(MESSAGE_ROUTES[("cosmos", "atlas", "reference_project")], "send_resource")

    def test_workspace_session_persists_context_above_universe_lifecycle(self):
        path = Path(self.tmpdir.name) / "workspaces.json"
        manager = WorkspaceSessionManager(self.apps, path=path)
        manager.set_project("Projet X")
        manager.set_workflow("illustration")
        manager.add_resource("resource://existence/atlas/document/carte")
        manager.register_started("atlas", 4242)

        restored = WorkspaceSessionManager(self.apps, path=path)
        self.assertEqual(restored.current["current_project"], "Projet X")
        self.assertEqual(restored.current["active_workflow"], "illustration")
        self.assertEqual(restored.active_universe_ids(), ["atlas"])
        self.assertEqual(restored.session("atlas")["pid"], 4242)

    def test_workspace_reuses_one_universe_session(self):
        manager = WorkspaceSessionManager(path=Path(self.tmpdir.name) / "workspaces.json")
        manager.register_started("atlas", 100)
        manager.register_started("atlas", 200)
        self.assertEqual(len(manager.current["active_universes"]), 1)
        self.assertEqual(manager.session("atlas")["pid"], 200)
        manager.mark_closed("atlas")
        self.assertEqual(manager.active_universe_ids(), [])

    def test_workspace_reconciles_dead_external_process_sessions(self):
        path = Path(self.tmpdir.name) / "workspace.json"
        manager = WorkspaceSessionManager(path=path)
        manager.register_started("singularity", 999999999, [])
        stale = manager.reconcile_processes([app("singularity")])
        self.assertEqual(stale, ["singularity"])
        self.assertEqual(manager.session("singularity")["state"], "closed")
        self.assertFalse(manager.session("singularity")["desired"])

    def test_workspace_restores_only_required_universes(self):
        manager = WorkspaceSessionManager(path=Path(self.tmpdir.name) / "workspaces.json")
        manager.register_started("atlas", 100, ["resource://existence/atlas/document/carte"])
        manager.register_started("nebula", 200)
        manager.mark_closed("nebula")
        apps = [app("atlas"), app("nebula"), app("cosmos")]
        self.assertEqual(manager.required_universe_ids(apps), ["atlas"])
        manager.set_restore_on_start(False)
        self.assertEqual(manager.required_universe_ids(apps), [])

    def test_real_nebula_process_receives_message_through_existence_router(self):
        nebula_adapter = Path("/home/deanos/Documents/Nebula/EXISTENCE/adapter.py")
        self.assertTrue(nebula_adapter.exists(), "Nebula adapter absent: le transport IPC critique est indisponible")
        endpoint = ProcessEndpoint([sys.executable, str(nebula_adapter), "--message"])
        router = ExistenceIPCRouter({"nebula": endpoint})
        try:
            manifest = router.handshake_all()["nebula"]
            self.assertEqual(manifest["id"], "nebula")
            event = router.route(
                "atlas", "nebula", "open_as_raster",
                resource="resource://existence/atlas/image/vector-42",
            )
            self.assertEqual(event["transport"], "process-json-lines")
            self.assertTrue(event["response"]["ok"])
        finally:
            router.close_all()

    def test_project_is_separate_from_workplace_session(self):
        project = ProjectManager(path=Path(self.tmpdir.name) / "projects.json")
        created = project.select_or_create("Illustration X")
        project.attach_resource("atlas", "resource://existence/atlas/document/vector")
        self.assertEqual(project.current["name"], "Illustration X")
        self.assertEqual(project.current["universe_resources"]["atlas"], [
            "resource://existence/atlas/document/vector"
        ])
        workplace = WorkspaceSessionManager(path=Path(self.tmpdir.name) / "workspaces.json")
        workplace.register_started("atlas", 4242)
        self.assertEqual(workplace.active_universe_ids(), ["atlas"])
        self.assertEqual(project.current["id"], created["id"])

    def test_wayland_view_registry_requires_universe_owned_view_provider(self):
        registry = UniverseViewRegistry()
        registry.register("nebula", lambda parent: parent)
        self.assertTrue(registry.has_view("nebula"))
        self.assertFalse(registry.has_view("atlas"))


if __name__ == "__main__":
    unittest.main()

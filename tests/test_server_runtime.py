import asyncio
import importlib
import os
import queue
import threading
import time
import unittest
from unittest.mock import MagicMock

import server_runtime
from server_runtime import (
    ServerRuntimeFacade,
    RuntimeCommand,
    RuntimeCommandResult,
    RuntimeSnapshotRequest,
    RuntimeSnapshotResult,
    COMMAND_UPDATE_SPELL_COLOR,
    COMMAND_SET_FACING,
    COMMAND_SET_AURAS_ENABLED,
    COMMAND_PLACE_COMBATANT,
    COMMAND_REMOVE_AOE,
    COMMAND_MOVE_AOE,
    COMMAND_SET_OBSTACLE,
    COMMAND_SET_TERRAIN,
    COMMAND_SET_ELEVATION,
    COMMAND_SET_MAP_SETTINGS,
    COMMAND_UPSERT_MAP_BACKGROUND,
    COMMAND_REMOVE_MAP_BACKGROUND,
    COMMAND_SET_MAP_BACKGROUND_ORDER,
    COMMAND_UPSERT_MAP_HAZARD,
    COMMAND_REMOVE_MAP_HAZARD,
    COMMAND_COMBAT_START,
    COMMAND_COMBAT_SET_TURN,
    COMMAND_COMBAT_NEXT_TURN,
    STATUS_COMPLETED,
    STATUS_FAILED,
)


class ServerRuntimeFacadeTests(unittest.TestCase):
    class _SnapshotCombatService:
        def __init__(self, payload=None, exc=None):
            self.payload = payload if payload is not None else {"combatants": [], "round": 1}
            self.exc = exc
            self.calls = 0

        def combat_snapshot(self):
            self.calls += 1
            if self.exc is not None:
                raise self.exc
            return self.payload

    class _SnapshotApp:
        def __init__(self, payload=None, exc=None):
            self.payload = payload if payload is not None else {"grid": {"cols": 10, "rows": 10}}
            self.exc = exc
            self.calls = 0

        def _dm_tactical_snapshot(self):
            self.calls += 1
            if self.exc is not None:
                raise self.exc
            return self.payload

    class _SnapshotLanController:
        def __init__(self, combat_service=None, app=None, console_payload=None, console_exc=None):
            self._dm_service = combat_service
            self.app = app
            self.console_payload = console_payload
            self.console_exc = console_exc
            self.dm_console_calls = []

        def _dm_console_snapshot(self, *, include_tactical=None):
            self.dm_console_calls.append(include_tactical)
            if self.console_exc is not None:
                raise self.console_exc
            if self.console_payload is not None:
                return self.console_payload
            payload = {"console": "snapshot"}
            if include_tactical:
                payload["tactical_map"] = {"grid": {"cols": 10, "rows": 10}}
            return payload

    class _CombatSnapshotCombatant:
        def __init__(self, **attrs):
            self.__dict__.update(attrs)

    def assertSnapshotFailure(self, result, code):
        self.assertFalse(result.success)
        self.assertEqual(result.status, STATUS_FAILED)
        self.assertEqual(result.data, {})
        self.assertIsInstance(result.error, dict)
        self.assertEqual(result.error.get("code"), code)

    def test_browser_entry_route_registrar_inventory_is_stable(self):
        from fastapi import FastAPI
        from init_tracker_server.browser_routes import (
            BROWSER_ENTRY_ROUTE_INVENTORY,
            BrowserEntryRouteHandlers,
            register_browser_entry_routes,
        )

        expected_inventory = (
            ("GET", "/", "index"),
            ("GET", "/planning", "planning"),
            ("GET", "/new_character", "new_character"),
            ("GET", "/edit_character", "edit_character"),
            ("GET", "/shop_admin", "shop_admin"),
            ("GET", "/shop", "shop"),
            ("GET", "/config", "config_redirect"),
            ("GET", "/sw.js", "service_worker"),
        )
        self.assertEqual(
            tuple(
                (route.method, route.path, route.endpoint_name)
                for route in BROWSER_ENTRY_ROUTE_INVENTORY
            ),
            expected_inventory,
        )

        async def handler():
            return None

        handlers = BrowserEntryRouteHandlers(
            index=handler,
            planning=handler,
            new_character=handler,
            edit_character=handler,
            shop_admin=handler,
            shop=handler,
            config_redirect=handler,
            service_worker=handler,
        )
        app = FastAPI()
        register_browser_entry_routes(app, handlers)

        registered_routes = {
            (route.path, method): route.name
            for route in app.routes
            for method in (getattr(route, "methods", None) or ())
        }
        self.assertEqual(
            tuple(
                (route.method, route.path, registered_routes[(route.path, route.method)])
                for route in BROWSER_ENTRY_ROUTE_INVENTORY
            ),
            expected_inventory,
        )

    def test_browser_entry_route_registrar_rejects_duplicate_paths(self):
        from fastapi import FastAPI
        from init_tracker_server.browser_routes import (
            BrowserEntryRouteHandlers,
            register_browser_entry_routes,
        )

        async def handler():
            return None

        app = FastAPI()

        @app.get("/shop")
        async def existing_shop():
            return None

        routes_before_registration = tuple(app.routes)
        handlers = BrowserEntryRouteHandlers(
            index=handler,
            planning=handler,
            new_character=handler,
            edit_character=handler,
            shop_admin=handler,
            shop=handler,
            config_redirect=handler,
            service_worker=handler,
        )

        with self.assertRaisesRegex(ValueError, r"GET /shop: path/method collision"):
            register_browser_entry_routes(app, handlers)

        self.assertEqual(tuple(app.routes), routes_before_registration)

    class _DmCombatRouteRuntime:
        def __init__(self, result=None, exc=None, delay_seconds=0.0):
            self.result = result
            self.exc = exc
            self.delay_seconds = delay_seconds
            self.requests = []
            self.read_thread_ids = []
            self.active_reads = 0
            self.max_active_reads = 0
            self._read_lock = threading.Lock()

        def read_snapshot(self, snap_req):
            with self._read_lock:
                self.requests.append(snap_req)
                self.read_thread_ids.append(threading.get_ident())
                self.active_reads += 1
                self.max_active_reads = max(self.max_active_reads, self.active_reads)
            try:
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
                if self.exc is not None:
                    raise self.exc
                return self.result
            finally:
                with self._read_lock:
                    self.active_reads -= 1

    def _dm_combat_route_client(self, *, runtime, auth_ok=True, dm_service=object()):
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.testclient import TestClient
        from dnd_initative_tracker import (
            _CURRENT_REQUEST_PATH,
            _current_request_wants_tactical_map,
            _dm_combat_read_snapshot_in_threadpool,
        )

        app = FastAPI()
        route_thread_ids = []

        @app.middleware("http")
        async def set_current_request_path_middleware(request: Request, call_next):
            full_path = request.url.path
            if request.url.query:
                full_path += f"?{request.url.query}"
            token = _CURRENT_REQUEST_PATH.set(full_path)
            try:
                return await call_next(request)
            finally:
                _CURRENT_REQUEST_PATH.reset(token)

        def _check_dm_auth(request):
            if not auth_ok:
                raise HTTPException(status_code=401, detail="Admin authentication required.")

        @app.get("/api/dm/combat")
        async def dm_combat_snapshot(request: Request):
            _check_dm_auth(request)
            if dm_service is None:
                raise HTTPException(status_code=503, detail="DM combat service unavailable.")
            try:
                from runtime_config import timed_span, debug_trace_enabled, debug_event
                include_tactical = _current_request_wants_tactical_map()
                snap_req = RuntimeSnapshotRequest(
                    snapshot_type="dm_console",
                    params={
                        "include_tactical": include_tactical,
                    },
                )
                trace_context = "dm_console_route_tactical" if include_tactical else "dm_console_route"
                route_trace_fields = {
                    "scope": trace_context,
                    "snapshot_caller": trace_context,
                    "include_tactical": bool(include_tactical),
                    "route": "/api/dm/combat",
                    "method": "GET",
                    "read_in_threadpool": True,
                    "serialized_tactical_read": bool(include_tactical),
                }
                fake_counts = {
                    "combatant_count": 2,
                    "player_count": 1,
                    "monster_count": 1,
                    "websocket_client_count": 0,
                    "dm_websocket_client_count": 0,
                    "total_websocket_client_count": 0,
                }
                route_trace_fields.update(fake_counts)

                route_thread_ids.append(threading.get_ident())
                with timed_span("dm.console.route_read_snapshot", **route_trace_fields):
                    result = await _dm_combat_read_snapshot_in_threadpool(runtime, snap_req)
                if not result.success:
                    if result.error and result.error.get("code") == "runtime_not_ready":
                        raise HTTPException(status_code=503, detail="Service Unavailable")
                    raise HTTPException(status_code=500, detail="Failed to read combat snapshot.")

                build_trace_fields = dict(route_trace_fields)
                if isinstance(result.data, dict):
                    combatants = result.data.get("combatants") or []
                    combatant_count = len(combatants)
                    player_count = sum(1 for c in combatants if isinstance(c, dict) and bool(c.get("is_pc")))
                    monster_count = combatant_count - player_count
                    top_level_key_count = len(result.data)
                    build_trace_fields.update({
                        "combatant_count": combatant_count,
                        "player_count": player_count,
                        "monster_count": monster_count,
                        "top_level_key_count": top_level_key_count,
                    })

                with timed_span("dm.console.route_response_build", **build_trace_fields):
                    if debug_trace_enabled() and isinstance(result.data, dict):
                        try:
                            with timed_span("dm.console.route_payload_proxy", **route_trace_fields):
                                debug_event(
                                    "snapshot.payload_proxy",
                                    span="dm.console.route_payload_proxy",
                                    sizes={"payload_top_level_key_count": len(result.data)},
                                    **route_trace_fields,
                                )
                        except Exception:
                            pass
                return result.data
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to read combat snapshot.")

        return TestClient(app), route_thread_ids

    def _combat_snapshot_tracker(self):
        tracker = type("CombatSnapshotTracker", (), {})()

        def combatant(**overrides):
            defaults = {
                "cid": 0,
                "name": "",
                "hp": 1,
                "max_hp": 1,
                "temp_hp": 0,
                "ac": 10,
                "initiative": 0,
                "speed": 30,
                "swim_speed": 0,
                "fly_speed": 0,
                "burrow_speed": 0,
                "climb_speed": 0,
                "is_pc": False,
                "ally": False,
                "concentrating": False,
                "concentration_spell": "",
                "is_hidden": False,
                "is_wild_shaped": False,
                "wild_shape_form_name": "",
                "wild_shape_form": "",
                "summoned_by_cid": None,
                "summon_source_spell": "",
                "mounted_by_cid": None,
                "is_mount": False,
                "condition_stacks": [],
                "monster_slug": "",
            }
            defaults.update(overrides)
            return self._CombatSnapshotCombatant(**defaults)

        tracker.combatants = {
            1: combatant(
                cid=1,
                name="Dorian",
                hp=22,
                max_hp=30,
                ac=14,
                initiative=12,
                is_pc=True,
                concentrating=True,
                concentration_spell="bless",
            ),
            2: combatant(
                cid=2,
                name="Guard",
                hp=11,
                max_hp=11,
                ac=15,
                initiative=18,
                is_hidden=True,
                condition_stacks=[
                    self._CombatSnapshotCombatant(ctype="poisoned", remaining_turns=2)
                ],
                monster_slug="guard",
            ),
        }
        tracker.current_cid = 1
        tracker.round_num = 4
        tracker.turn_num = 9
        tracker.in_combat = True
        tracker.passive_values = {1: 16, 2: 11}
        tracker.ac_modifiers = {1: 1, 2: 2}
        tracker.defenses_by_cid = {
            1: {
                "damage_resistances": {"radiant"},
                "damage_immunities": set(),
                "damage_vulnerabilities": set(),
                "condition_immunities": set(),
            },
            2: {
                "damage_resistances": {"fire"},
                "damage_immunities": {"poison"},
                "damage_vulnerabilities": {"cold"},
                "condition_immunities": {"frightened"},
            },
        }
        tracker._monster_resource_state = {
            "2:ammo:rifle:current": 3,
            "2:uses:smoke:current": 1,
            "20:ammo:other:current": 99,
        }
        tracker.display_order_calls = 0
        tracker.passive_calls = []
        tracker.defense_calls = []
        tracker.ac_calls = []
        tracker.peek_calls = []
        tracker.battle_log_limits = []

        def _display_order():
            tracker.display_order_calls += 1
            return [tracker.combatants[2], tracker.combatants[1]]

        def _observer_passive_perception(combatant):
            tracker.passive_calls.append(int(combatant.cid))
            return tracker.passive_values[int(combatant.cid)]

        def _combatant_defense_sets(combatant):
            tracker.defense_calls.append(int(combatant.cid))
            return tracker.defenses_by_cid[int(combatant.cid)]

        def _combatant_ac_modifier(combatant):
            tracker.ac_calls.append(int(combatant.cid))
            return tracker.ac_modifiers[int(combatant.cid)]

        def _peek_next_turn_cid(current_cid):
            tracker.peek_calls.append(current_cid)
            return 2

        def _lan_battle_log_lines(limit=200):
            tracker.battle_log_limits.append(limit)
            return ["Guard waits.", "Dorian acts."]

        tracker._display_order = _display_order
        tracker._observer_passive_perception = _observer_passive_perception
        tracker._combatant_defense_sets = _combatant_defense_sets
        tracker._combatant_ac_modifier = _combatant_ac_modifier
        tracker._peek_next_turn_cid = _peek_next_turn_cid
        tracker._lan_battle_log_lines = _lan_battle_log_lines
        return tracker

    def test_combat_snapshot_payload_shape_and_order_stable_with_composition_context(self):
        from combat_service import CombatService

        tracker = self._combat_snapshot_tracker()
        snapshot = CombatService(tracker).combat_snapshot()

        self.assertEqual(
            list(snapshot.keys()),
            [
                "in_combat",
                "round",
                "turn",
                "active_cid",
                "up_next_cid",
                "up_next_name",
                "turn_order",
                "combatants",
                "battle_log",
            ],
        )
        self.assertEqual(snapshot["turn_order"], [2, 1])
        self.assertEqual([row["cid"] for row in snapshot["combatants"]], [2, 1])
        self.assertEqual(snapshot["up_next_cid"], 2)
        self.assertEqual(snapshot["up_next_name"], "Guard")
        self.assertEqual(snapshot["battle_log"], ["Guard waits.", "Dorian acts."])
        self.assertEqual(tracker.battle_log_limits, [30])

        first_row = snapshot["combatants"][0]
        self.assertEqual(
            list(first_row.keys()),
            [
                "cid",
                "name",
                "hp",
                "max_hp",
                "temp_hp",
                "ac",
                "initiative",
                "speed",
                "swim_speed",
                "fly_speed",
                "burrow_speed",
                "climb_speed",
                "passive_perception",
                "damage_vulnerabilities",
                "damage_resistances",
                "damage_immunities",
                "condition_immunities",
                "concentrating",
                "concentration_spell",
                "state_markers",
                "is_pc",
                "role",
                "conditions",
                "monster_resources",
                "monster_slug",
                "is_current",
            ],
        )
        self.assertEqual(first_row["ac"], 17)
        self.assertEqual(first_row["passive_perception"], 11)
        self.assertEqual(first_row["damage_resistances"], ["fire"])
        self.assertEqual(first_row["monster_resources"], {"ammo:rifle:current": 3, "uses:smoke:current": 1})
        self.assertEqual(tracker.passive_calls, [2, 1])
        self.assertEqual(tracker.defense_calls, [2, 1])
        self.assertEqual(tracker.ac_calls, [2, 1])

    def test_combat_snapshot_visibility_sensitive_fields_are_not_broadened(self):
        from combat_service import CombatService

        tracker = self._combat_snapshot_tracker()
        snapshot = CombatService(tracker).combat_snapshot()
        rows = {row["cid"]: row for row in snapshot["combatants"]}

        hidden_marker_keys = {marker["key"] for marker in rows[2]["state_markers"]}
        pc_marker_keys = {marker["key"] for marker in rows[1]["state_markers"]}

        self.assertIn("hidden", hidden_marker_keys)
        self.assertNotIn("hidden", pc_marker_keys)
        self.assertNotIn("tactical_map", snapshot)
        self.assertNotIn("is_hidden", rows[2])
        self.assertEqual(rows[2]["role"], "enemy")
        self.assertTrue(rows[1]["is_pc"])

    def test_dm_console_route_snapshot_top_level_structure_remains_stable(self):
        from combat_service import CombatService

        payload = CombatService(self._combat_snapshot_tracker()).combat_snapshot()
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data=payload)
        )
        client, _route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(list(response.json().keys()), list(payload.keys()))
        self.assertEqual(runtime.requests[0].params, {"include_tactical": False})

    def test_combat_snapshot_composition_context_is_transient_per_call(self):
        from combat_service import CombatService

        tracker = self._combat_snapshot_tracker()
        service = CombatService(tracker)

        first = service.combat_snapshot()
        tracker.passive_values[2] = 14
        tracker.ac_modifiers[2] = -1
        tracker.defenses_by_cid[2] = {
            "damage_resistances": {"cold"},
            "damage_immunities": set(),
            "damage_vulnerabilities": set(),
            "condition_immunities": set(),
        }
        tracker._monster_resource_state = {"2:ammo:rifle:current": 7}
        second = service.combat_snapshot()

        first_guard = next(row for row in first["combatants"] if row["cid"] == 2)
        second_guard = next(row for row in second["combatants"] if row["cid"] == 2)

        self.assertEqual(first_guard["passive_perception"], 11)
        self.assertEqual(first_guard["ac"], 17)
        self.assertEqual(first_guard["damage_resistances"], ["fire"])
        self.assertEqual(first_guard["monster_resources"], {"ammo:rifle:current": 3, "uses:smoke:current": 1})
        self.assertEqual(second_guard["passive_perception"], 14)
        self.assertEqual(second_guard["ac"], 14)
        self.assertEqual(second_guard["damage_resistances"], ["cold"])
        self.assertEqual(second_guard["monster_resources"], {"ammo:rifle:current": 7})

    def test_dm_combat_route_offloads_dm_console_snapshot_read(self):
        payload = {"in_combat": True, "round": 3, "combatants": [{"cid": 7}]}
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data=payload)
        )
        client, route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat?workspace=dmcontrol")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(len(runtime.requests), 1)
        snap_req = runtime.requests[0]
        self.assertEqual(snap_req.snapshot_type, "dm_console")
        self.assertEqual(snap_req.params, {"include_tactical": True})
        self.assertNotIn("request", snap_req.params)
        self.assertEqual(len(route_thread_ids), 1)
        self.assertEqual(len(runtime.read_thread_ids), 1)
        self.assertNotEqual(runtime.read_thread_ids[0], route_thread_ids[0])

    def test_dm_combat_tactical_offload_serializes_concurrent_snapshot_reads(self):
        from dnd_initative_tracker import _dm_combat_read_snapshot_in_threadpool

        payload = {"in_combat": True, "round": 3, "combatants": [{"cid": 7}]}
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data=payload),
            delay_seconds=0.05,
        )
        snap_req = RuntimeSnapshotRequest(
            snapshot_type="dm_console",
            params={"include_tactical": True},
        )

        async def run_reads():
            return await asyncio.gather(
                _dm_combat_read_snapshot_in_threadpool(runtime, snap_req),
                _dm_combat_read_snapshot_in_threadpool(runtime, snap_req),
                _dm_combat_read_snapshot_in_threadpool(runtime, snap_req),
            )

        results = asyncio.run(run_reads())

        self.assertEqual([result.data for result in results], [payload, payload, payload])
        self.assertEqual(len(runtime.requests), 3)
        self.assertEqual(runtime.max_active_reads, 1)

    def test_dm_combat_route_preserves_non_tactical_read_context(self):
        payload = {"in_combat": False, "round": 1, "combatants": []}
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data=payload)
        )
        client, _route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(len(runtime.requests), 1)
        self.assertEqual(runtime.requests[0].params, {"include_tactical": False})

    def test_dm_combat_route_auth_and_service_checks_happen_before_offload(self):
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data={"ok": True})
        )
        client, route_thread_ids = self._dm_combat_route_client(runtime=runtime, auth_ok=False)

        response = client.get("/api/dm/combat?workspace=dmcontrol")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(runtime.requests, [])
        self.assertEqual(route_thread_ids, [])

        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data={"ok": True})
        )
        client, route_thread_ids = self._dm_combat_route_client(runtime=runtime, dm_service=None)

        response = client.get("/api/dm/combat?workspace=dmcontrol")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "DM combat service unavailable.")
        self.assertEqual(runtime.requests, [])
        self.assertEqual(route_thread_ids, [])

    def test_dm_combat_route_preserves_snapshot_failure_mapping(self):
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(
                success=False,
                status=STATUS_FAILED,
                error={"code": "runtime_not_ready"},
            )
        )
        client, _route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Service Unavailable")

        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(
                success=False,
                status=STATUS_FAILED,
                error={"code": "snapshot_builder_failed"},
            )
        )
        client, _route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Failed to read combat snapshot.")

    def test_dm_combat_route_preserves_worker_exception_mapping(self):
        runtime = self._DmCombatRouteRuntime(exc=RuntimeError("boom"))
        client, _route_thread_ids = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat?workspace=dmcontrol")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Failed to read combat snapshot.")
        self.assertEqual(len(runtime.requests), 1)

    def test_package_runtime_reexports_current_runtime_boundary(self):
        runtime = importlib.import_module("init_tracker_server.runtime")

        self.assertIs(runtime.ServerRuntimeFacade, server_runtime.ServerRuntimeFacade)

        expected_symbols = [
            "RuntimeCommand",
            "RuntimeCommandResult",
            "RuntimeCommandTrace",
            "RuntimeSnapshotRequest",
            "RuntimeSnapshotResult",
            "STATUS_ACCEPTED",
            "STATUS_QUEUED",
            "STATUS_DISPATCHING",
            "STATUS_COMPLETED",
            "STATUS_FAILED",
            "STATUS_TIMED_OUT",
            "COMMAND_UPDATE_SPELL_COLOR",
            "COMMAND_TEST_QUEUE",
            "COMMAND_SET_FACING",
            "COMMAND_SET_AURAS_ENABLED",
            "COMMAND_PLACE_COMBATANT",
            "COMMAND_REMOVE_AOE",
            "COMMAND_MOVE_AOE",
            "COMMAND_SET_OBSTACLE",
            "COMMAND_SET_TERRAIN",
            "COMMAND_SET_ELEVATION",
            "COMMAND_SET_MAP_SETTINGS",
            "COMMAND_UPSERT_MAP_BACKGROUND",
            "COMMAND_REMOVE_MAP_BACKGROUND",
            "COMMAND_SET_MAP_BACKGROUND_ORDER",
            "COMMAND_UPSERT_MAP_HAZARD",
            "COMMAND_REMOVE_MAP_HAZARD",
            "COMMAND_UPSERT_MAP_FEATURE",
            "COMMAND_REMOVE_MAP_FEATURE",
        ]

        self.assertEqual(set(runtime.__all__), set(expected_symbols + ["ServerRuntimeFacade"]))
        for name in expected_symbols:
            with self.subTest(symbol=name):
                self.assertTrue(hasattr(runtime, name))
                self.assertEqual(getattr(runtime, name), getattr(server_runtime, name))

    def test_runtime_host_constructs_starts_and_warms_once_in_order(self):
        from init_tracker_server.runtime_host import (
            RuntimeHost,
            RuntimeHostAdapter,
            RuntimeHostLifecycleError,
            RuntimeHostState,
        )

        class FakeRuntime:
            def __init__(self, identity):
                self.identity = identity

        events = []
        host_ref = {}

        def runtime_factory():
            runtime = FakeRuntime("only")
            events.append(("construct", host_ref["host"].state, runtime.identity))
            return runtime

        def start_runtime(runtime):
            events.append(("start", host_ref["host"].state, runtime.identity))

        def warm_up_runtime(runtime):
            events.append(("warm_up", host_ref["host"].state, runtime.identity))
            self.assertIs(host_ref["host"].runtime, runtime)

        def stop_runtime(runtime):
            events.append(("stop", host_ref["host"].state, runtime.identity))

        host = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=start_runtime,
            warm_up_runtime=warm_up_runtime,
            stop_runtime=stop_runtime,
        )
        host_ref["host"] = host

        self.assertIsInstance(host, RuntimeHost)
        self.assertIs(host.state, RuntimeHostState.NEW)
        self.assertIsNone(host.runtime)
        self.assertIsNone(host.last_error)

        first_runtime = host.start()
        self.assertIs(host.state, RuntimeHostState.RUNNING)
        self.assertIs(host.runtime, first_runtime)
        self.assertIs(host.start(), first_runtime)
        self.assertEqual(
            events,
            [
                ("construct", RuntimeHostState.STARTING, "only"),
                ("start", RuntimeHostState.STARTING, "only"),
                ("warm_up", RuntimeHostState.WARMING_UP, "only"),
            ],
        )

        host.stop()
        host.stop()
        self.assertIs(host.state, RuntimeHostState.STOPPED)
        self.assertIsNone(host.runtime)
        self.assertEqual(events[-1], ("stop", RuntimeHostState.STOPPING, "only"))

        with self.assertRaisesRegex(
            RuntimeHostLifecycleError,
            "cannot restart a stopped runtime host lifecycle",
        ):
            host.start()
        self.assertEqual(
            events,
            [
                ("construct", RuntimeHostState.STARTING, "only"),
                ("start", RuntimeHostState.STARTING, "only"),
                ("warm_up", RuntimeHostState.WARMING_UP, "only"),
                ("stop", RuntimeHostState.STOPPING, "only"),
            ],
        )

    def test_runtime_host_duplicate_and_concurrent_start_are_idempotent(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        runtime = object()
        factory_entered = threading.Event()
        release_factory = threading.Event()
        callers_ready = threading.Barrier(2)
        events = []
        results = []
        errors = []

        def runtime_factory():
            events.append("construct")
            factory_entered.set()
            if not release_factory.wait(timeout=1):
                raise AssertionError("test did not release runtime factory")
            return runtime

        def start_runtime(created_runtime):
            events.append(("start", created_runtime))

        host = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=start_runtime,
            stop_runtime=lambda created_runtime: None,
        )

        def call_start():
            try:
                callers_ready.wait(timeout=1)
                results.append(host.start())
            except BaseException as error:
                errors.append(error)

        threads = [threading.Thread(target=call_start) for _ in range(2)]
        for thread in threads:
            thread.start()

        self.assertTrue(factory_entered.wait(timeout=1))
        release_factory.set()
        for thread in threads:
            thread.join(timeout=1)
            self.assertFalse(thread.is_alive())

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertTrue(all(result is runtime for result in results))
        self.assertIs(host.start(), runtime)
        self.assertEqual(events, ["construct", ("start", runtime)])
        self.assertIs(host.state, RuntimeHostState.RUNNING)

    def test_runtime_host_duplicate_and_concurrent_stop_are_idempotent(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        runtime = object()
        stop_entered = threading.Event()
        release_stop = threading.Event()
        callers_ready = threading.Barrier(3)
        events = []
        errors = []

        def runtime_factory():
            events.append("construct")
            return runtime

        def start_runtime(created_runtime):
            events.append(("start", created_runtime))

        def stop_runtime(created_runtime):
            events.append(("stop", created_runtime))
            stop_entered.set()
            if not release_stop.wait(timeout=1):
                raise AssertionError("test did not release runtime stop")

        host = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=start_runtime,
            stop_runtime=stop_runtime,
        )
        self.assertIs(host.start(), runtime)

        def call_stop():
            try:
                callers_ready.wait(timeout=1)
                host.stop(timeout=1)
            except BaseException as error:
                errors.append(error)

        callers = [threading.Thread(target=call_stop) for _ in range(2)]
        for caller in callers:
            caller.start()
        callers_ready.wait(timeout=1)
        self.assertTrue(stop_entered.wait(timeout=1))
        self.assertIs(host.state, RuntimeHostState.STOPPING)
        self.assertIs(host.runtime, runtime)
        self.assertEqual(
            events,
            ["construct", ("start", runtime), ("stop", runtime)],
        )

        release_stop.set()
        for caller in callers:
            caller.join(timeout=1)
            self.assertFalse(caller.is_alive())

        host.stop(timeout=0.01)
        self.assertEqual(errors, [])
        self.assertTrue(host.stop_requested)
        self.assertIs(host.state, RuntimeHostState.STOPPED)
        self.assertIsNone(host.runtime)
        self.assertIsNone(host.last_error)
        self.assertIsNotNone(host.stop_thread)
        self.assertFalse(host.stop_thread.is_alive())
        self.assertEqual(
            events,
            ["construct", ("start", runtime), ("stop", runtime)],
        )

    def test_runtime_host_construction_failure_is_observable_and_not_retried(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        construction_error = RuntimeError("construction failed")
        events = []

        def runtime_factory():
            events.append("construct")
            raise construction_error

        host = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=lambda runtime: events.append("start"),
            stop_runtime=lambda runtime: events.append("stop"),
        )

        with self.assertRaises(RuntimeError) as first_error:
            host.start()
        with self.assertRaises(RuntimeError) as duplicate_error:
            host.start()

        self.assertIs(first_error.exception, construction_error)
        self.assertIs(duplicate_error.exception, construction_error)
        self.assertEqual(events, ["construct"])
        self.assertIs(host.state, RuntimeHostState.FAILED)
        self.assertIs(host.last_error, construction_error)
        self.assertIsNone(host.runtime)

    def test_runtime_host_startup_failure_is_observable_and_not_retried(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        rollback_events = []
        startup_error = RuntimeError("startup failed")

        class FakeRuntime:
            identity = "failed-start"

        def fail_start(runtime):
            rollback_events.append(("start", runtime.identity))
            raise startup_error

        def rollback_start(runtime):
            rollback_events.append(("stop", runtime.identity))

        failed_start_host = RuntimeHostAdapter(
            lambda: FakeRuntime(),
            start_runtime=fail_start,
            stop_runtime=rollback_start,
        )
        with self.assertRaises(RuntimeError) as start_error:
            failed_start_host.start()
        with self.assertRaises(RuntimeError) as duplicate_error:
            failed_start_host.start()

        self.assertIs(failed_start_host.state, RuntimeHostState.FAILED)
        self.assertIs(start_error.exception, startup_error)
        self.assertIs(duplicate_error.exception, startup_error)
        self.assertIs(failed_start_host.last_error, startup_error)
        self.assertIsNone(failed_start_host.runtime)
        self.assertEqual(
            rollback_events,
            [("start", "failed-start"), ("stop", "failed-start")],
        )

    def test_runtime_host_failure_matrix_rolls_back_only_created_started_runtime(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        for failed_stage, expected_events in (
            ("construct", ["construct"]),
            ("start", ["construct", "start", "stop"]),
            ("warm_up", ["construct", "start", "warm_up", "stop"]),
        ):
            with self.subTest(failed_stage=failed_stage):
                original_error = RuntimeError(f"{failed_stage} failed")
                runtime = object()
                events = []

                def runtime_factory():
                    events.append("construct")
                    if failed_stage == "construct":
                        raise original_error
                    return runtime

                def start_runtime(created_runtime):
                    self.assertIs(created_runtime, runtime)
                    events.append("start")
                    if failed_stage == "start":
                        raise original_error

                def warm_up_runtime(created_runtime):
                    self.assertIs(created_runtime, runtime)
                    events.append("warm_up")
                    if failed_stage == "warm_up":
                        raise original_error

                def stop_runtime(created_runtime):
                    self.assertIs(created_runtime, runtime)
                    events.append("stop")

                host = RuntimeHostAdapter(
                    runtime_factory,
                    start_runtime=start_runtime,
                    warm_up_runtime=warm_up_runtime,
                    stop_runtime=stop_runtime,
                )

                with self.assertRaises(RuntimeError) as raised:
                    host.start()

                self.assertIs(raised.exception, original_error)
                self.assertIs(host.last_error, original_error)
                self.assertIs(host.state, RuntimeHostState.FAILED)
                self.assertIsNone(host.runtime)
                self.assertEqual(events, expected_events)

    def test_runtime_host_rollback_failure_retains_runtime_without_masking_warm_up_error(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        runtime = object()
        warm_up_error = RuntimeError("warm-up failed")
        rollback_error = RuntimeError("rollback failed")
        stop_calls = []

        def fail_warm_up(created_runtime):
            self.assertIs(created_runtime, runtime)
            raise warm_up_error

        def fail_rollback(created_runtime):
            stop_calls.append(created_runtime)
            raise rollback_error

        host = RuntimeHostAdapter(
            lambda: runtime,
            start_runtime=lambda created_runtime: None,
            warm_up_runtime=fail_warm_up,
            stop_runtime=fail_rollback,
        )

        with self.assertRaises(RuntimeError) as raised:
            host.start()

        self.assertIs(raised.exception, warm_up_error)
        self.assertIs(host.last_error, warm_up_error)
        self.assertIs(host.state, RuntimeHostState.FAILED)
        self.assertIs(host.runtime, runtime)
        self.assertEqual(stop_calls, [runtime])
        self.assertTrue(
            any("rollback failed" in note for note in getattr(warm_up_error, "__notes__", ()))
        )

    def test_runtime_host_failure_cleanup_leaves_no_owned_worker_thread(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter

        for failed_stage in ("start", "warm_up"):
            with self.subTest(failed_stage=failed_stage):
                original_error = RuntimeError(f"{failed_stage} failed")
                stop_requested = threading.Event()
                worker_started = threading.Event()

                def worker_main():
                    worker_started.set()
                    stop_requested.wait(timeout=1)

                worker = threading.Thread(
                    target=worker_main,
                    name=f"runtime-host-{failed_stage}-worker",
                    daemon=True,
                )

                def start_runtime(runtime):
                    worker.start()
                    self.assertTrue(worker_started.wait(timeout=1))
                    if failed_stage == "start":
                        raise original_error

                def warm_up_runtime(runtime):
                    if failed_stage == "warm_up":
                        raise original_error

                def stop_runtime(runtime):
                    stop_requested.set()
                    worker.join(timeout=1)

                host = RuntimeHostAdapter(
                    object,
                    start_runtime=start_runtime,
                    warm_up_runtime=warm_up_runtime,
                    stop_runtime=stop_runtime,
                )

                with self.assertRaises(RuntimeError) as raised:
                    host.start()

                self.assertIs(raised.exception, original_error)
                self.assertFalse(worker.is_alive())

    def test_runtime_host_shutdown_failure_is_observable_and_not_retried(self):
        from init_tracker_server.runtime_host import (
            RuntimeHostAdapter,
            RuntimeHostLifecycleError,
            RuntimeHostState,
        )

        class FakeRuntime:
            identity = "failed-stop"

        stop_attempts = []

        def retryable_stop(runtime):
            stop_attempts.append(runtime.identity)
            raise RuntimeError("shutdown failed")

        failed_stop_host = RuntimeHostAdapter(
            lambda: FakeRuntime(),
            start_runtime=lambda runtime: None,
            stop_runtime=retryable_stop,
        )
        failed_stop_runtime = failed_stop_host.start()
        with self.assertRaisesRegex(RuntimeError, "shutdown failed") as stop_error:
            failed_stop_host.stop()

        self.assertIs(failed_stop_host.state, RuntimeHostState.FAILED)
        self.assertIs(failed_stop_host.runtime, failed_stop_runtime)
        self.assertIs(failed_stop_host.last_error, stop_error.exception)
        with self.assertRaises(RuntimeHostLifecycleError):
            failed_stop_host.start()

        with self.assertRaises(RuntimeError) as duplicate_stop_error:
            failed_stop_host.stop()
        self.assertIs(duplicate_stop_error.exception, stop_error.exception)
        self.assertEqual(stop_attempts, ["failed-stop"])
        self.assertIs(failed_stop_host.state, RuntimeHostState.FAILED)
        self.assertIs(failed_stop_host.runtime, failed_stop_runtime)
        self.assertIs(failed_stop_host.last_error, stop_error.exception)

    def test_runtime_host_stop_during_startup_is_latched_and_requested_once(self):
        from init_tracker_server.runtime_host import RuntimeHostAdapter, RuntimeHostState

        runtime = object()
        factory_entered = threading.Event()
        release_factory = threading.Event()
        stop_calls = []
        start_results = []
        stop_errors = []

        def runtime_factory():
            factory_entered.set()
            if not release_factory.wait(timeout=1):
                raise AssertionError("test did not release runtime factory")
            return runtime

        host = RuntimeHostAdapter(
            runtime_factory,
            start_runtime=lambda created_runtime: None,
            stop_runtime=stop_calls.append,
        )

        start_thread = threading.Thread(target=lambda: start_results.append(host.start()))

        def stop_host():
            try:
                host.stop(timeout=1)
            except BaseException as error:
                stop_errors.append(error)

        start_thread.start()
        self.assertTrue(factory_entered.wait(timeout=1))
        stop_thread = threading.Thread(target=stop_host)
        stop_thread.start()
        deadline = time.monotonic() + 1
        while not host.stop_requested and time.monotonic() < deadline:
            time.sleep(0.001)
        self.assertTrue(host.stop_requested)
        self.assertIs(host.state, RuntimeHostState.STARTING)
        release_factory.set()
        start_thread.join(timeout=1)
        stop_thread.join(timeout=1)

        self.assertFalse(start_thread.is_alive())
        self.assertFalse(stop_thread.is_alive())
        self.assertEqual(stop_errors, [])
        self.assertEqual(start_results, [runtime])
        self.assertEqual(stop_calls, [runtime])
        self.assertIs(host.state, RuntimeHostState.STOPPED)
        self.assertIsNone(host.runtime)

    def test_runtime_host_stop_timeout_keeps_worker_and_failure_observable(self):
        from init_tracker_server.runtime_host import (
            RuntimeHostAdapter,
            RuntimeHostState,
            RuntimeHostStopTimeoutError,
        )

        release_stop = threading.Event()
        stop_entered = threading.Event()
        stop_calls = []

        def blocking_stop(runtime):
            stop_calls.append(runtime)
            stop_entered.set()
            release_stop.wait(timeout=1)

        runtime = object()
        host = RuntimeHostAdapter(
            lambda: runtime,
            start_runtime=lambda created_runtime: None,
            stop_runtime=blocking_stop,
        )
        host.start()

        with self.assertRaises(RuntimeHostStopTimeoutError) as raised:
            host.stop(timeout=0.01)

        self.assertTrue(stop_entered.is_set())
        self.assertTrue(host.stop_timed_out)
        self.assertIs(host.last_error, raised.exception)
        self.assertIs(host.state, RuntimeHostState.STOPPING)
        self.assertIs(host.runtime, runtime)
        self.assertIsNotNone(host.stop_thread)
        self.assertTrue(host.stop_thread.is_alive())
        self.assertEqual(stop_calls, [runtime])

        release_stop.set()
        host.stop_thread.join(timeout=1)
        self.assertFalse(host.stop_thread.is_alive())
        self.assertIs(host.state, RuntimeHostState.STOPPED)
        self.assertIsNone(host.runtime)
        host.stop(timeout=0.01)
        self.assertEqual(stop_calls, [runtime])

    def test_headless_runtime_host_readiness_failure_rolls_back_once(self):
        from init_tracker_server.runtime_host import HeadlessRuntimeHost, RuntimeHostState

        readiness_error = RuntimeError("server readiness failed")
        events = []

        class FailingLan:
            def start(self, quiet=False):
                events.append(("lan.start", quiet))

            def wait_until_ready(self, timeout):
                events.append(("lan.wait_until_ready", timeout))
                raise readiness_error

            def stop(self):
                events.append(("lan.stop", None))

            def join(self, timeout):
                events.append(("lan.join", timeout))

        class FakeHeadlessRuntime:
            def __init__(self):
                events.append(("construct", None))
                self._lan = FailingLan()
                self.mainloop_entered = threading.Event()

            def mainloop(self):
                events.append(("mainloop", None))
                self.mainloop_entered.set()

            def after(self, _delay_ms, callback):
                self_test.assertTrue(self.mainloop_entered.wait(timeout=1))
                callback()

            def quit(self):
                events.append(("quit", None))

        self_test = self
        host = HeadlessRuntimeHost(
            FakeHeadlessRuntime,
            prepare_runtime=lambda _runtime: events.append(("prepare", None)),
            server_ready_timeout=0.25,
            server_stop_timeout=0.5,
        )

        with self.assertRaises(RuntimeError) as raised:
            host.start()

        self.assertIs(raised.exception, readiness_error)
        self.assertIs(host.last_error, readiness_error)
        self.assertIs(host.state, RuntimeHostState.FAILED)
        self.assertIsNone(host.runtime)
        self.assertEqual(
            events,
            [
                ("construct", None),
                ("prepare", None),
                ("mainloop", None),
                ("lan.start", True),
                ("lan.wait_until_ready", 0.25),
                ("lan.stop", None),
                ("lan.join", 0.5),
                ("quit", None),
            ],
        )

    def test_lan_controller_stop_and_readiness_delegate_to_owned_server_host(self):
        from dnd_initative_tracker import LanController

        class FakeServerHost:
            def __init__(self):
                self.calls = []

            def wait_until_ready(self, timeout):
                self.calls.append(("wait_until_ready", timeout))

            def stop(self, timeout):
                self.calls.append(("stop", timeout))

            def request_stop(self):
                self.calls.append(("request_stop", None))

            def wait(self, timeout):
                self.calls.append(("wait", timeout))

        class FakeTracker:
            def __init__(self):
                self.logs = []

            def _oplog(self, message):
                self.logs.append(message)

        controller = object.__new__(LanController)
        controller._tracker = FakeTracker()
        controller._server_host = FakeServerHost()
        controller._uvicorn_server = None
        controller._polling = True

        controller.wait_until_ready(timeout=0.25)
        controller.stop()
        controller.join(timeout=0.5)

        self.assertFalse(controller._polling)
        self.assertEqual(
            controller._server_host.calls,
            [
                ("wait_until_ready", 0.25),
                ("request_stop", None),
                ("wait", 0.5),
            ],
        )
        self.assertEqual(len(controller.app.logs), 1)

    def test_runtime_host_lifespan_integration(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import patch

        from init_tracker_server.app import create_app
        from init_tracker_server.runtime_host import (
            HeadlessRuntimeHost,
            RuntimeHostAdapter,
            RuntimeHostLifecycleError,
            RuntimeHostState,
        )
        import serve_headless

        asgi_events = []

        class FakeAsgiLanController:
            def warm_up(self, runtime):
                asgi_events.append(("warm_up", app.state.ready))
                self.runtime = runtime

        lan_controller = FakeAsgiLanController()

        class FakeAsgiRuntime:
            def __init__(self, *, lan_controller):
                self.lan_controller = lan_controller
                self.start_calls = 0
                self.shutdown_calls = 0
                asgi_events.append(("construct", app.state.ready))

            def start(self):
                self.start_calls += 1
                asgi_events.append(("start", app.state.ready))
                self.assert_owned_before_readiness()

            def shutdown(self):
                self.shutdown_calls += 1
                asgi_events.append(("shutdown", app.state.ready))

            def assert_owned_before_readiness(self):
                self_test.assertIs(app.state.runtime, self)
                self_test.assertIsNotNone(app.state.runtime_host)
                self_test.assertFalse(app.state.ready)

        self_test = self
        app = create_app(lan_controller=lan_controller)
        created_hosts = []
        real_runtime_host_adapter = RuntimeHostAdapter

        def recording_asgi_runtime_host_adapter(*args, **kwargs):
            host = real_runtime_host_adapter(*args, **kwargs)
            created_hosts.append(host)
            return host

        async def exercise_asgi_lifespan():
            self.assertFalse(app.state.ready)
            self.assertIsNone(app.state.runtime)
            self.assertIsNone(app.state.runtime_host)
            completed_lifecycles = []

            for _cycle in range(2):
                async with app.router.lifespan_context(app):
                    asgi_events.append(("serving", app.state.ready))
                    runtime = app.state.runtime
                    runtime_host = app.state.runtime_host
                    self.assertIs(runtime_host.state, RuntimeHostState.RUNNING)
                    self.assertIs(runtime_host.runtime, runtime)
                    self.assertIs(runtime.lan_controller, lan_controller)
                    self.assertEqual(runtime.start_calls, 1)
                    self.assertEqual(runtime.shutdown_calls, 0)
                    self.assertIs(lan_controller.runtime, runtime)
                    self.assertTrue(app.state.ready)
                    self.assertTrue(app.state.runtime_lifespan_entered)

                    with self.assertRaisesRegex(
                        RuntimeHostLifecycleError,
                        "application runtime lifespan has already been entered",
                    ):
                        async with app.router.lifespan_context(app):
                            self.fail("concurrent application lifespan must be rejected")

                self.assertIs(runtime_host.state, RuntimeHostState.STOPPED)
                self.assertIsNone(runtime_host.runtime)
                self.assertIs(app.state.runtime, runtime)
                self.assertEqual(runtime.start_calls, 1)
                self.assertEqual(runtime.shutdown_calls, 1)
                self.assertFalse(app.state.ready)
                self.assertFalse(app.state.runtime_lifespan_entered)
                self.assertIsNone(app.state.runtime_stop_error)
                self.assertIsNotNone(runtime_host.stop_thread)
                self.assertFalse(runtime_host.stop_thread.is_alive())
                completed_lifecycles.append((runtime, runtime_host))
                asgi_events.append(("lifespan_exited", app.state.ready))

            self.assertIsNot(completed_lifecycles[0][0], completed_lifecycles[1][0])
            self.assertIsNot(completed_lifecycles[0][1], completed_lifecycles[1][1])

        with (
            patch("init_tracker_server.app.ServerRuntimeFacade", FakeAsgiRuntime),
            patch(
                "init_tracker_server.app.RuntimeHostAdapter",
                recording_asgi_runtime_host_adapter,
            ),
        ):
            asyncio.run(exercise_asgi_lifespan())

        self.assertEqual(len(created_hosts), 2)
        self.assertEqual(
            asgi_events,
            2 * [
                ("construct", False),
                ("start", False),
                ("warm_up", False),
                ("serving", True),
                ("shutdown", False),
                ("lifespan_exited", False),
            ],
        )

        headless_events = []
        created_hosts = []

        class FakeLan:
            def __init__(self):
                self.cfg = SimpleNamespace(host="127.0.0.1", port=8000)
                self._polling = True

            def _best_lan_url(self):
                return f"http://{self.cfg.host}:{self.cfg.port}/"

            def start(self, quiet=False):
                headless_events.append(
                    ("lan.start", quiet, self.cfg.host, self.cfg.port)
                )

            def wait_until_ready(self, timeout):
                headless_events.append(("lan.wait_until_ready", timeout))

            def stop(self):
                self._polling = False
                headless_events.append(("lan.stop", None))

            def join(self, timeout):
                headless_events.append(("lan.join", timeout))

        class FakeHeadlessRuntime:
            def __init__(self, *, auto_start_lan=None):
                headless_events.append(("construct", auto_start_lan))
                self._lan = FakeLan()
                self.mainloop_entered = threading.Event()

            def mainloop(self):
                headless_events.append(("mainloop", None))
                self.mainloop_entered.set()

            def after(self, _delay_ms, callback):
                self_test.assertTrue(self.mainloop_entered.wait(timeout=1))
                callback()

            def quit(self):
                headless_events.append(("quit", None))

        fake_tracker_module = SimpleNamespace(
            InitiativeTracker=FakeHeadlessRuntime,
            POC_AUTO_START_LAN=True,
        )
        real_headless_runtime_host = HeadlessRuntimeHost

        def recording_headless_runtime_host(*args, **kwargs):
            host = real_headless_runtime_host(*args, **kwargs)
            created_hosts.append(host)
            return host

        with (
            patch.dict(os.environ, {}, clear=False),
            patch.dict(sys.modules, {"dnd_initative_tracker": fake_tracker_module}),
            patch.object(
                serve_headless,
                "HeadlessRuntimeHost",
                recording_headless_runtime_host,
            ),
            patch.object(serve_headless.runtime_cfg, "ensure_dirs"),
            patch.object(serve_headless, "configure_debug_trace"),
            patch.object(serve_headless.signal, "signal"),
        ):
            first_result = serve_headless.main(["--no-auto-lan", "--no-debugging"])
            second_result = serve_headless.main(
                [
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "18802",
                    "--no-debugging",
                ]
            )

        self.assertEqual((first_result, second_result), (0, 0))
        self.assertTrue(fake_tracker_module.POC_AUTO_START_LAN)
        self.assertEqual(len(created_hosts), 2)
        for host in created_hosts:
            self.assertIs(host.state, RuntimeHostState.STOPPED)
            self.assertIsNone(host.runtime)
            self.assertIsNotNone(host.stop_thread)
            self.assertFalse(host.stop_thread.is_alive())
        self.assertEqual(
            headless_events,
            [
                ("construct", False),
                ("mainloop", None),
                ("lan.stop", None),
                ("lan.join", 5.0),
                ("quit", None),
                ("construct", False),
                ("mainloop", None),
                ("lan.start", True, "0.0.0.0", 18802),
                ("lan.wait_until_ready", 60.0),
                ("lan.stop", None),
                ("lan.join", 5.0),
                ("quit", None),
            ],
        )

    def test_app_lifespan_exit_surfaces_bounded_runtime_stop_timeout(self):
        from unittest.mock import patch

        from init_tracker_server.app import create_app
        from init_tracker_server.runtime_host import (
            RuntimeHostState,
            RuntimeHostStopTimeoutError,
        )

        shutdown_entered = threading.Event()
        release_shutdown = threading.Event()

        class FakeRuntime:
            def __init__(self, *, lan_controller):
                self.lan_controller = lan_controller

            def start(self):
                return None

            def shutdown(self):
                shutdown_entered.set()
                release_shutdown.wait(timeout=1)

        app = create_app(lan_controller=None)
        app.state.runtime_stop_timeout_seconds = 0.01

        async def exercise_lifespan_timeout():
            with self.assertRaises(RuntimeHostStopTimeoutError) as raised:
                async with app.router.lifespan_context(app):
                    self.assertTrue(app.state.ready)
            self.assertFalse(app.state.ready)
            self.assertIs(app.state.runtime_stop_error, raised.exception)

        with patch("init_tracker_server.app.ServerRuntimeFacade", FakeRuntime):
            asyncio.run(exercise_lifespan_timeout())

        runtime_host = app.state.runtime_host
        self.assertTrue(shutdown_entered.is_set())
        self.assertIs(runtime_host.state, RuntimeHostState.STOPPING)
        self.assertTrue(runtime_host.stop_timed_out)
        self.assertIsNotNone(runtime_host.stop_thread)
        self.assertTrue(runtime_host.stop_thread.is_alive())

        release_shutdown.set()
        runtime_host.stop_thread.join(timeout=1)
        self.assertFalse(runtime_host.stop_thread.is_alive())
        self.assertIs(runtime_host.state, RuntimeHostState.STOPPED)

    def test_lan_controller_warm_up_preserves_seed_and_fallback_outputs(self):
        from dnd_initative_tracker import LanController

        runtime = object()
        seed_snapshot = {"seed": "static"}
        fallback_snapshot = {"seed": "fallback"}

        class SeedApp:
            def __init__(self):
                self.snapshot_calls = []

            def _lan_snapshot(self, **kwargs):
                self.snapshot_calls.append(kwargs)
                return seed_snapshot

            def _lan_pcs(self):
                return ({"name": "Aela"}, {"name": "Borin"})

        seeded_controller = object.__new__(LanController)
        seeded_controller._tracker = SeedApp()
        seeded_controller._runtime = None
        seeded_controller._cached_snapshot = {}
        seeded_controller._cached_pcs = []

        seeded_controller.warm_up(runtime)

        self.assertIs(seeded_controller._runtime, runtime)
        self.assertIs(seeded_controller._cached_snapshot, seed_snapshot)
        self.assertEqual(
            seeded_controller._cached_pcs,
            [{"name": "Aela"}, {"name": "Borin"}],
        )
        self.assertEqual(
            seeded_controller.app.snapshot_calls,
            [
                {
                    "include_static": True,
                    "hydrate_static": True,
                    "scope": "lan_startup_seed",
                }
            ],
        )

        seed_error = RuntimeError("static seed failed")

        class FallbackApp:
            def __init__(self):
                self.snapshot_calls = []

            def _lan_snapshot(self, **kwargs):
                self.snapshot_calls.append(kwargs)
                if kwargs["include_static"]:
                    raise seed_error
                return fallback_snapshot

            def _lan_claimable(self):
                raise AssertionError("fallback warm-up must not replace cached PCs")

        fallback_controller = object.__new__(LanController)
        fallback_controller._tracker = FallbackApp()
        fallback_controller._runtime = None
        fallback_controller._cached_snapshot = {}
        fallback_controller._cached_pcs = [{"name": "Existing"}]

        fallback_controller.warm_up(runtime)

        self.assertIs(fallback_controller._runtime, runtime)
        self.assertIs(fallback_controller._cached_snapshot, fallback_snapshot)
        self.assertEqual(fallback_controller._cached_pcs, [{"name": "Existing"}])
        self.assertEqual(
            fallback_controller.app.snapshot_calls,
            [
                {
                    "include_static": True,
                    "hydrate_static": True,
                    "scope": "lan_startup_seed",
                },
                {
                    "include_static": False,
                    "hydrate_static": False,
                    "scope": "lan_startup_fallback",
                },
            ],
        )

    def test_lan_controller_warm_up_runs_cache_builders_on_tracker_thread(self):
        from dnd_initative_tracker import LanController

        owner_thread_id = threading.get_ident()
        scheduled_callbacks = queue.Queue()
        snapshot = {"seed": "static"}
        pcs = [{"cid": 7, "name": "Aela"}]

        class OwnerThreadApp:
            def __init__(self):
                self.call_threads = []

            def after(self, delay_ms, callback):
                self.call_threads.append(("after", threading.get_ident(), delay_ms))
                scheduled_callbacks.put(callback)

            def _lan_snapshot(self, **_kwargs):
                self.call_threads.append(("snapshot", threading.get_ident()))
                return snapshot

            def _lan_pcs(self):
                self.call_threads.append(("pcs", threading.get_ident()))
                return pcs

        controller = object.__new__(LanController)
        controller._tracker = OwnerThreadApp()
        controller._runtime = None
        controller._tracker_thread_id = owner_thread_id
        controller._cached_snapshot = {}
        controller._cached_pcs = []
        runtime = object()
        worker_errors = []

        def warm_up_from_asgi_thread():
            try:
                controller.warm_up(runtime)
            except BaseException as error:
                worker_errors.append(error)

        worker = threading.Thread(target=warm_up_from_asgi_thread)
        worker.start()
        callback = scheduled_callbacks.get(timeout=1)
        self.assertTrue(worker.is_alive())

        callback()
        worker.join(timeout=1)

        self.assertFalse(worker.is_alive())
        self.assertEqual(worker_errors, [])
        self.assertIs(controller._runtime, runtime)
        self.assertIs(controller._cached_snapshot, snapshot)
        self.assertEqual(controller._cached_pcs, pcs)
        self.assertNotEqual(controller.app.call_threads[0][1], owner_thread_id)
        self.assertEqual(
            controller.app.call_threads[1:],
            [("snapshot", owner_thread_id), ("pcs", owner_thread_id)],
        )

    def test_lan_controller_warm_up_preserves_primary_error_when_fallback_fails(self):
        from dnd_initative_tracker import LanController

        seed_error = RuntimeError("static seed failed")
        fallback_error = RuntimeError("fallback seed failed")

        class FailingApp:
            def _lan_snapshot(self, **kwargs):
                if kwargs["include_static"]:
                    raise seed_error
                raise fallback_error

        controller = object.__new__(LanController)
        controller._tracker = FailingApp()
        controller._runtime = None
        controller._cached_snapshot = {}
        controller._cached_pcs = []
        runtime = object()

        with self.assertRaises(RuntimeError) as raised:
            controller.warm_up(runtime)

        self.assertIs(raised.exception, seed_error)
        self.assertIs(controller._runtime, runtime)
        self.assertTrue(
            any("fallback seed failed" in note for note in getattr(seed_error, "__notes__", ()))
        )

    def test_spell_color_command_execution(self):
        # 1. facade executes the spell-color command using a fake app/controller hook
        mock_app = MagicMock()
        mock_app._save_spell_color.return_value = {"id": "fireball", "color": "red"}

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )

        result = facade.submit_command(command)

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Spell color updated successfully.")
        self.assertEqual(result.data, {"spell": {"id": "fireball", "color": "red"}})
        mock_app._save_spell_color.assert_called_once_with("fireball", "red")

    def test_unknown_command_fails_closed(self):
        # 2. unknown command still fails closed
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(command_type="unknown_action")

        with self.assertRaises(NotImplementedError) as ctx:
            facade.submit_command(command)
        self.assertIn("Command type 'unknown_action' is not yet implemented.", str(ctx.exception))

    def test_facade_without_lan_controller_fails(self):
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )
        with self.assertRaises(RuntimeError) as ctx:
            facade.submit_command(command)
        self.assertIn("LanController is not configured on the facade.", str(ctx.exception))

    def test_facade_without_app_fails(self):
        mock_lan_controller = MagicMock()
        mock_lan_controller.app = None
        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )
        with self.assertRaises(RuntimeError) as ctx:
            facade.submit_command(command)
        self.assertIn("InitiativeTracker app is not configured on LanController.", str(ctx.exception))

    def test_no_queue_or_cache_behavior_introduced(self):
        # 4. no queue/cache behavior is introduced
        facade = ServerRuntimeFacade()
        # Verify no queue/cache attributes are present on initialization
        self.assertFalse(hasattr(facade, "queue"))
        self.assertFalse(hasattr(facade, "command_" + "queue"))
        self.assertFalse(hasattr(facade, "snapshot_" + "cache"))

    def test_read_snapshot_fails_closed_before_readiness(self):
        combat_service = self._SnapshotCombatService()
        controller = self._SnapshotLanController(combat_service=combat_service, app=self._SnapshotApp())
        facade = ServerRuntimeFacade(lan_controller=controller)

        result = facade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="combat"))

        self.assertSnapshotFailure(result, "runtime_not_ready")
        self.assertEqual(combat_service.calls, 0)

    def test_read_snapshot_unsupported_mode_fails_closed(self):
        facade = ServerRuntimeFacade(
            lan_controller=self._SnapshotLanController(
                combat_service=self._SnapshotCombatService(),
                app=self._SnapshotApp(),
            )
        )
        facade.start()

        result = facade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="unknown"))

        self.assertSnapshotFailure(result, "snapshot_type_unsupported")

    def test_read_snapshot_combat_delegates_to_combat_service(self):
        payload = {"in_combat": True, "round": 2, "combatants": [{"cid": 1}]}
        combat_service = self._SnapshotCombatService(payload=payload)
        facade = ServerRuntimeFacade(
            lan_controller=self._SnapshotLanController(
                combat_service=combat_service,
                app=self._SnapshotApp(),
            )
        )
        facade.start()

        result = facade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="combat", params={"caller": "dm"}))

        self.assertTrue(result.success)
        self.assertEqual(result.status, STATUS_COMPLETED)
        self.assertEqual(result.data, payload)
        self.assertEqual(result.metadata.get("source"), "combat_service.combat_snapshot")
        self.assertNotIn("tactical_map", result.data)
        self.assertEqual(combat_service.calls, 1)

    def test_read_snapshot_tactical_delegates_to_tracker_app(self):
        payload = {"grid": {"cols": 12, "rows": 8}, "units": [{"cid": 2}]}
        app = self._SnapshotApp(payload=payload)
        controller = self._SnapshotLanController(
            combat_service=self._SnapshotCombatService(),
            app=app,
        )
        facade = ServerRuntimeFacade(lan_controller=controller)
        facade.start()

        result = facade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="tactical"))

        self.assertTrue(result.success)
        self.assertEqual(result.status, STATUS_COMPLETED)
        self.assertEqual(result.data, payload)
        self.assertEqual(result.metadata.get("source"), "tracker._dm_tactical_snapshot")
        self.assertEqual(app.calls, 1)
        self.assertEqual(controller.dm_console_calls, [])

    def test_read_snapshot_dm_console_delegates_with_explicit_include_tactical(self):
        controller = self._SnapshotLanController(
            combat_service=self._SnapshotCombatService(),
            app=self._SnapshotApp(),
        )
        facade = ServerRuntimeFacade(lan_controller=controller)
        facade.start()

        without_tactical = facade.read_snapshot(
            RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": False})
        )
        with_tactical = facade.read_snapshot(
            RuntimeSnapshotRequest(snapshot_type="dm_console", params={"include_tactical": True})
        )

        self.assertTrue(without_tactical.success)
        self.assertEqual(without_tactical.status, STATUS_COMPLETED)
        self.assertEqual(without_tactical.data, {"console": "snapshot"})
        self.assertFalse(without_tactical.metadata.get("include_tactical"))
        self.assertTrue(with_tactical.success)
        self.assertEqual(with_tactical.status, STATUS_COMPLETED)
        self.assertEqual(with_tactical.data["tactical_map"], {"grid": {"cols": 10, "rows": 10}})
        self.assertTrue(with_tactical.metadata.get("include_tactical"))
        self.assertEqual(controller.dm_console_calls, [False, True])

    def _dm_console_cache_controller(self, *, cached_payload, cached_include_tactical, fresh_payload):
        from dnd_initative_tracker import LanController

        controller = object.__new__(LanController)
        controller._cached_dm_snapshot = cached_payload
        controller._cached_dm_snapshot_at = time.perf_counter()
        controller._cached_dm_snapshot_include_tactical = cached_include_tactical
        calls = []

        def _fresh_payload(**kwargs):
            calls.append(dict(kwargs))
            return dict(fresh_payload)

        controller._dm_console_snapshot_payload = _fresh_payload
        return controller, calls

    def test_dm_console_snapshot_reuses_cached_payload_when_include_tactical_matches(self):
        cached_payload = {"console": "cached"}
        controller, calls = self._dm_console_cache_controller(
            cached_payload=cached_payload,
            cached_include_tactical=False,
            fresh_payload={"console": "fresh"},
        )

        result = controller._dm_console_snapshot(include_tactical=False)

        self.assertEqual(result, cached_payload)
        self.assertEqual(calls, [])
        self.assertIsNone(controller._cached_dm_snapshot)
        self.assertEqual(controller._cached_dm_snapshot_at, 0.0)
        self.assertIsNone(controller._cached_dm_snapshot_include_tactical)

    def test_dm_console_snapshot_does_not_reuse_tactical_cache_for_non_tactical_request(self):
        controller, calls = self._dm_console_cache_controller(
            cached_payload={"console": "cached", "tactical_map": {"grid": {"cols": 10}}},
            cached_include_tactical=True,
            fresh_payload={"console": "fresh"},
        )

        result = controller._dm_console_snapshot(include_tactical=False)

        self.assertEqual(result, {"console": "fresh"})
        self.assertEqual(calls, [{
            "combat_snapshot": None,
            "tactical_snapshot": None,
            "include_tactical": False,
        }])
        self.assertNotIn("tactical_map", result)

    def test_dm_console_snapshot_does_not_reuse_non_tactical_cache_for_tactical_request(self):
        controller, calls = self._dm_console_cache_controller(
            cached_payload={"console": "cached"},
            cached_include_tactical=False,
            fresh_payload={"console": "fresh", "tactical_map": {"grid": {"cols": 12}}},
        )

        result = controller._dm_console_snapshot(include_tactical=True)

        self.assertEqual(result, {"console": "fresh", "tactical_map": {"grid": {"cols": 12}}})
        self.assertEqual(calls, [{
            "combat_snapshot": None,
            "tactical_snapshot": None,
            "include_tactical": True,
        }])
        self.assertIn("tactical_map", result)

    def _resource_pool_cache_tracker(
        self,
        *,
        cached_payload=None,
        lan_cached_payload=None,
        fresh_payload=None,
        fresh_exc=None,
    ):
        from dnd_initative_tracker import InitiativeTracker

        tracker = object.__new__(InitiativeTracker)
        tracker._lan_resource_pools_last_build = 100.0
        tracker._lan_resource_pools_payload_cache = cached_payload
        tracker._last_invalidation_domains = set()
        tracker._lan = MagicMock()
        tracker._lan._cached_snapshot = (
            {"resource_pools": lan_cached_payload}
            if lan_cached_payload is not None
            else {}
        )
        calls = []

        def _fresh_payload():
            calls.append("build")
            if fresh_exc is not None:
                raise fresh_exc
            return fresh_payload if fresh_payload is not None else {"Fresh": []}

        tracker._player_resource_pools_payload = _fresh_payload
        return tracker, calls

    def test_lan_resource_pools_cache_reuses_dedicated_payload_inside_throttle(self):
        cached_payload = {
            "Alice": [
                {"id": "focus_points", "label": "Focus Points", "current": 2, "max": 2}
            ]
        }
        tracker, calls = self._resource_pool_cache_tracker(cached_payload=cached_payload)

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=False,
            last_domains=set(),
            now=100.25,
        )

        self.assertEqual(payload, cached_payload)
        self.assertEqual(result, "dedicated_cache_hit")
        self.assertEqual(calls, [])
        self.assertEqual(
            tracker._lan_resource_pools_trace_mode(
                include_static=False,
                last_domains=set(),
                now=100.25,
            ),
            "dedicated_cache_hit",
        )

    def test_lan_resource_pools_cache_backfills_from_legacy_snapshot_cache(self):
        lan_cached_payload = {
            "Bob": [
                {
                    "id": "temp_bardic_dice_7",
                    "label": "Bardic Dice",
                    "current": 1,
                    "max": 1,
                    "temporary": True,
                    "time_left_s": 12.5,
                }
            ]
        }
        tracker, calls = self._resource_pool_cache_tracker(
            cached_payload=None,
            lan_cached_payload=lan_cached_payload,
        )

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=False,
            last_domains=set(),
            now=100.25,
        )

        self.assertEqual(payload, lan_cached_payload)
        self.assertEqual(tracker._lan_resource_pools_payload_cache, lan_cached_payload)
        self.assertEqual(result, "lan_snapshot_cache_hit")
        self.assertEqual(calls, [])

    def test_lan_resource_pools_cache_rebuilds_for_static_and_invalidation(self):
        stale_payload = {"Alice": [{"id": "wild_shape", "current": 0, "max": 2}]}
        fresh_static_payload = {"Alice": [{"id": "wild_shape", "current": 2, "max": 2}]}
        tracker, calls = self._resource_pool_cache_tracker(
            cached_payload=stale_payload,
            fresh_payload=fresh_static_payload,
        )

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=True,
            last_domains=set(),
            now=100.25,
        )

        self.assertEqual(payload, fresh_static_payload)
        self.assertEqual(result, "force_rebuild")
        self.assertEqual(calls, ["build"])
        self.assertEqual(tracker._lan_resource_pools_payload_cache, fresh_static_payload)
        self.assertEqual(tracker._lan_resource_pools_last_build, 100.25)

        fresh_invalidation_payload = {"Alice": [{"id": "wild_shape", "current": 1, "max": 2}]}
        tracker, calls = self._resource_pool_cache_tracker(
            cached_payload=stale_payload,
            fresh_payload=fresh_invalidation_payload,
        )

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=False,
            last_domains={"resource_pools"},
            now=100.5,
        )

        self.assertEqual(payload, fresh_invalidation_payload)
        self.assertEqual(result, "force_rebuild")
        self.assertEqual(calls, ["build"])
        self.assertEqual(tracker._lan_resource_pools_payload_cache, fresh_invalidation_payload)
        self.assertEqual(tracker._lan_resource_pools_last_build, 100.5)

    def test_lan_resource_pools_cache_falls_back_on_rebuild_failure(self):
        cached_payload = {"Alice": [{"id": "lay_on_hands", "current": 5, "max": 10}]}
        tracker, calls = self._resource_pool_cache_tracker(
            cached_payload=cached_payload,
            fresh_exc=RuntimeError("boom"),
        )

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=False,
            last_domains=set(),
            now=101.5,
        )

        self.assertEqual(payload, cached_payload)
        self.assertEqual(result, "rebuild_failed_dedicated_cache_hit")
        self.assertEqual(calls, ["build"])
        self.assertEqual(tracker._lan_resource_pools_last_build, 100.0)

    def test_player_resource_pools_payload_reuses_base_and_refreshes_temporary_pools(self):
        from dnd_initative_tracker import InitiativeTracker

        tracker = object.__new__(InitiativeTracker)
        profile = {"name": "Alice", "resources": {"pools": []}}
        tracker._player_yaml_data_by_name = {"Alice": profile}
        tracker._lan_resource_pools_base_cache = {}
        tracker._load_player_yaml_cache = lambda force_refresh=False: None
        registry_signature = {"value": ("items-v1", "magic-v1", "consumables-v1")}
        tracker._lan_resource_pools_base_registry_signature = lambda: registry_signature["value"]
        normalize_calls = []

        def normalize(data):
            normalize_calls.append(data)
            return [{"id": "focus_points", "label": "Focus Points", "current": 2, "max": 2}]

        temp_counter = {"value": 0}

        def augment(payload):
            temp_counter["value"] += 1
            payload["Alice"].append(
                {
                    "id": f"temp_bardic_dice_{temp_counter['value']}",
                    "label": "Bardic Dice",
                    "current": 1,
                    "max": 1,
                    "temporary": True,
                    "time_left_s": 30.0 - temp_counter["value"],
                }
            )

        tracker._normalize_player_resource_pools = normalize
        tracker._augment_resource_pools_with_temporary_conditions = augment

        first = tracker._player_resource_pools_payload()
        second = tracker._player_resource_pools_payload()

        self.assertEqual(normalize_calls, [profile])
        self.assertEqual(first["Alice"][0], {"id": "focus_points", "label": "Focus Points", "current": 2, "max": 2})
        self.assertEqual(second["Alice"][0], {"id": "focus_points", "label": "Focus Points", "current": 2, "max": 2})
        self.assertEqual([entry["id"] for entry in first["Alice"]], ["focus_points", "temp_bardic_dice_1"])
        self.assertEqual([entry["id"] for entry in second["Alice"]], ["focus_points", "temp_bardic_dice_2"])
        self.assertEqual(tracker._lan_resource_pools_base_cache_result, "base_cache_all_hit")

        registry_signature["value"] = ("items-v2", "magic-v1", "consumables-v1")
        third = tracker._player_resource_pools_payload()

        self.assertEqual(normalize_calls, [profile, profile])
        self.assertEqual([entry["id"] for entry in third["Alice"]], ["focus_points", "temp_bardic_dice_3"])
        self.assertEqual(tracker._lan_resource_pools_base_cache_result, "base_cache_miss")

    def test_lan_resource_pools_ttl_rebuild_reports_base_cache_submode(self):
        tracker, calls = self._resource_pool_cache_tracker(
            cached_payload=None,
            fresh_payload={"Alice": [{"id": "focus_points", "current": 2, "max": 2}]},
        )

        def fresh_payload():
            calls.append("build")
            tracker._lan_resource_pools_base_cache_result = "base_cache_all_hit"
            return {"Alice": [{"id": "focus_points", "current": 2, "max": 2}]}

        tracker._player_resource_pools_payload = fresh_payload

        payload, result = tracker._lan_resource_pools_payload_for_snapshot(
            include_static=False,
            last_domains=set(),
            now=101.25,
        )

        self.assertEqual(payload, {"Alice": [{"id": "focus_points", "current": 2, "max": 2}]})
        self.assertEqual(result, "ttl_rebuild_base_cache_all_hit")
        self.assertEqual(calls, ["build"])
        self.assertEqual(tracker._lan_resource_pools_last_build, 101.25)

    def test_read_snapshot_static_hydration_request_fails_closed(self):
        app = self._SnapshotApp()
        facade = ServerRuntimeFacade(
            lan_controller=self._SnapshotLanController(
                combat_service=self._SnapshotCombatService(),
                app=app,
            )
        )
        facade.start()

        result = facade.read_snapshot(
            RuntimeSnapshotRequest(snapshot_type="tactical", params={"hydrate_static": True})
        )

        self.assertSnapshotFailure(result, "snapshot_params_invalid")
        self.assertEqual(app.calls, 0)

    def test_read_snapshot_builder_exception_fails_closed_without_partial_payload(self):
        combat_service = self._SnapshotCombatService(exc=RuntimeError("boom"))
        facade = ServerRuntimeFacade(
            lan_controller=self._SnapshotLanController(
                combat_service=combat_service,
                app=self._SnapshotApp(),
            )
        )
        facade.start()

        result = facade.read_snapshot(RuntimeSnapshotRequest(snapshot_type="combat"))

        self.assertSnapshotFailure(result, "snapshot_builder_failed")
        self.assertEqual(result.data, {})
        self.assertEqual(result.error.get("error_class"), "RuntimeError")
        self.assertEqual(combat_service.calls, 1)

    def test_route_level_behavior_mapping(self):
        # 3. route-level behavior mapping is preserved
        from fastapi import FastAPI, Body, HTTPException
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()

        mock_runtime = MagicMock()

        @app.post("/api/spells/{spell_id}/color")
        async def update_spell_color(spell_id: str, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            spell_id = str(spell_id or "").strip()
            if not spell_id:
                raise HTTPException(status_code=400, detail="Missing spell id.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_UPDATE_SPELL_COLOR,
                    payload={"spell_id": spell_id, "color": payload.get("color")}
                )
                cmd_result = mock_runtime.submit_command(command)
                result = cmd_result.data.get("spell")
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="Spell not found.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc))
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to save spell color.")
            return {"ok": True, "spell": result}

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"spell": "red"}
        )
        response = client.post("/api/spells/fireball/color", json={"color": "red"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "spell": "red"})

        # 2. Invalid payload (non-dict)
        import asyncio
        try:
            asyncio.run(update_spell_color("fireball", "not a dict"))
            self.fail("HTTPException not raised for non-dict payload")
        except HTTPException as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.detail, "Invalid payload.")

        # 3. FileNotFoundError -> 404
        mock_runtime.submit_command.side_effect = FileNotFoundError()
        response = client.post("/api/spells/fireball/color", json={"color": "blue"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("Spell not found.", response.json()["detail"])

        # 4. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Invalid hex color")
        response = client.post("/api/spells/fireball/color", json={"color": "invalid"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid hex color", response.json()["detail"])

        # 5. RuntimeError -> 500
        mock_runtime.submit_command.side_effect = RuntimeError("Database offline")
        response = client.post("/api/spells/fireball/color", json={"color": "green"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Database offline", response.json()["detail"])

        # 6. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Unknown error")
        response = client.post("/api/spells/fireball/color", json={"color": "green"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to save spell color.", response.json()["detail"])

    def test_auras_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()
        mock_tracker_app = MagicMock()
        mock_tracker_app._is_admin_token_valid.return_value = True
        mock_tracker_app._issue_admin_token.return_value = "fake-token"
        mock_tracker_app._lan_auras_enabled = True

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/overlays/auras")
        async def dm_set_auras_overlay(request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            enabled_raw = payload.get("enabled")
            if isinstance(enabled_raw, str):
                enabled = enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
            elif isinstance(enabled_raw, (int, float)):
                enabled = bool(enabled_raw)
            else:
                enabled = bool(enabled_raw)
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_AURAS_ENABLED,
                    payload={
                        "enabled": bool(enabled),
                        "admin_token": "fake-token",
                    }
                )
                mock_runtime.submit_command(command)
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update overlays: {exc}")
            return {
                "ok": True,
                "enabled": bool(getattr(mock_tracker_app, "_lan_auras_enabled", enabled)),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={}
        )
        response = client.post("/api/dm/map/overlays/auras", json={"enabled": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "enabled": True, "snapshot": {"map": "dummy"}})

        # 2. Invalid payload (non-dict)
        import asyncio
        try:
            asyncio.run(dm_set_auras_overlay(MagicMock(), "not a dict"))
            self.fail("HTTPException not raised for non-dict payload")
        except HTTPException as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.detail, "Invalid payload.")

        # 3. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/overlays/auras", json={"enabled": False})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 4. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Invalid value")
        response = client.post("/api/dm/map/overlays/auras", json={"enabled": False})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid value", response.json()["detail"])

        # 5. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/overlays/auras", json={"enabled": False})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update overlays: Runtime fail", response.json()["detail"])

    def test_spell_color_lifecycle_observability_success(self):
        # 1. successful spell-color command still works and records a completed lifecycle/trace
        mock_app = MagicMock()
        mock_app._save_spell_color.return_value = {"id": "fireball", "color": "red"}

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "red"}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)

        # Trace duration/status fields are present and deterministic enough for unit tests
        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPDATE_SPELL_COLOR)
        self.assertEqual(trace.status, "completed")
        self.assertIsInstance(trace.duration_ms, float)
        self.assertGreaterEqual(trace.duration_ms, 0.0)
        self.assertIsNone(trace.error_class)

    def test_spell_color_lifecycle_observability_failure(self):
        # 2. failing spell-color command still raises the original exception and records a failed lifecycle/trace with error_class
        mock_app = MagicMock()
        mock_app._save_spell_color.side_effect = ValueError("Invalid hex color")

        mock_lan_controller = MagicMock()
        mock_lan_controller.app = mock_app

        facade = ServerRuntimeFacade(lan_controller=mock_lan_controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPDATE_SPELL_COLOR,
            payload={"spell_id": "fireball", "color": "invalid"}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Invalid hex color")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPDATE_SPELL_COLOR)
        self.assertEqual(trace.status, "failed")
        self.assertIsInstance(trace.duration_ms, float)
        self.assertGreaterEqual(trace.duration_ms, 0.0)
        self.assertEqual(trace.error_class, "ValueError")

    def test_unknown_command_lifecycle_observability_failure(self):
        # 3. unknown command still fails closed and records no successful completion
        facade = ServerRuntimeFacade()
        command = RuntimeCommand(command_type="unknown_action")

        with self.assertRaises(NotImplementedError):
            facade.submit_command(command)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "unknown_action")
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "NotImplementedError")

    def test_queue_adapter_success(self):
        # Test that the queue adapter successfully enqueues the action,
        # registers pending state, polls for completion, updates state and returns result.
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()

        def process_success(msg):
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied", "custom_key": "val"},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type="test_queue_command",
            payload={"cid": 42, "foo": "bar"}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(result.data["result"]["status"], "applied")
        self.assertEqual(result.data["result"]["custom_key"], "val")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "test_queue_command")
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_queue_adapter_timeout(self):
        # Test that the queue adapter handles timeouts properly by raising TimeoutError
        # and tracing the event with STATUS_TIMED_OUT.
        import threading

        class FakeQueue:
            def __init__(self):
                self.items = []
            def put(self, item):
                self.items.append(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type="test_queue_command",
            payload={"cid": 42, "timeout_ms": 10}
        )

        with self.assertRaises(TimeoutError) as ctx:
            facade.submit_command(command)
        self.assertIn("timed out after 10ms", str(ctx.exception))

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, "test_queue_command")
        self.assertEqual(trace.status, "timed_out")
        self.assertEqual(trace.error_class, "TimeoutError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_queue_adapter_mapped_errors(self):
        # Test that the queue adapter maps and raises the correct exceptions.
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        for err_type, expected_exc in [
            ("ValueError", ValueError),
            ("FileNotFoundError", FileNotFoundError),
            ("RuntimeError", RuntimeError),
            ("NotImplementedError", NotImplementedError),
            ("SomeOtherError", RuntimeError)
        ]:
            controller = FakeLanController()
            facade = ServerRuntimeFacade(lan_controller=controller)

            def make_process_error(err_name, ctrl):
                return lambda msg: ctrl._action_states[msg["action_id"]].update({
                    "status": "completed",
                    "result": {"status": "error", "reason": err_name},
                    "completed_at_ns": time.perf_counter_ns()
                })

            controller._actions.on_put = make_process_error(err_type, controller)
            command = RuntimeCommand(command_type="test_queue_command")
            with self.assertRaises(expected_exc) as ctx:
                facade.submit_command(command)
            self.assertIn(f"Queue command failed: {err_type}", str(ctx.exception))

            trace = facade.last_command_trace
            self.assertIsNotNone(trace)
            self.assertEqual(trace.command_type, "test_queue_command")
            self.assertEqual(trace.status, "failed")
            self.assertEqual(trace.error_class, err_type)
            self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_facing_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied", "cid": msg.get("cid"), "facing_deg": msg.get("facing_deg")},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_FACING,
            payload={"cid": 42, "facing_deg": 180}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_facing")
        self.assertEqual(msg["cid"], 42)
        self.assertEqual(msg["facing_deg"], 180)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_FACING)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_set_auras_enabled_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied", "enabled": msg.get("enabled")},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_AURAS_ENABLED,
            payload={"enabled": True}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_auras_enabled")
        self.assertEqual(msg["enabled"], True)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_AURAS_ENABLED)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_place_combatant_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "place_result": {"ok": True, "cid": 42, "col": 5, "row": 6},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_PLACE_COMBATANT,
            payload={"cid": 42, "col": 5, "row": 6}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "place_combatant")
        self.assertEqual(msg["cid"], 42)
        self.assertEqual(msg["col"], 5)
        self.assertEqual(msg["row"], 6)

        place_res = result.data.get("place_result")
        self.assertIsNotNone(place_res)
        self.assertTrue(place_res.get("ok"))
        self.assertEqual(place_res.get("cid"), 42)
        self.assertEqual(place_res.get("col"), 5)
        self.assertEqual(place_res.get("row"), 6)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_PLACE_COMBATANT)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_place_combatant_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "place_result": {"ok": False, "error": "Rider placement uses the mount, matey."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_PLACE_COMBATANT,
            payload={"cid": 42, "col": 5, "row": 6}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Rider placement uses the mount, matey.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_PLACE_COMBATANT)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

        # Test internal exception mapping to RuntimeError
        def process_internal_error(msg):
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "place_result": {"ok": False, "error": "Failed to place combatant: database error"},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_internal_error
        with self.assertRaises(RuntimeError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Failed to place combatant: database error")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_PLACE_COMBATANT)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "RuntimeError")

    def test_place_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/combatants/{cid}/place")
        async def dm_place_combatant_on_map(cid: int, request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            try:
                col = int(payload.get("col"))
                row = int(payload.get("row"))
            except Exception:
                raise HTTPException(status_code=400, detail="col and row must be integers.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_PLACE_COMBATANT,
                    payload={
                        "cid": int(cid),
                        "col": int(col),
                        "row": int(row),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                place_result = cmd_result.data.get("place_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to place combatant: {exc}")
            return {
                "ok": True,
                "cid": place_result.get("cid", int(cid)),
                "col": place_result.get("col", int(col)),
                "row": place_result.get("row", int(row)),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"place_result": {"ok": True, "cid": 42, "col": 5, "row": 6}}
        )
        response = client.post("/api/dm/map/combatants/42/place", json={"col": 5, "row": 6})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "cid": 42, "col": 5, "row": 6, "snapshot": {"map": "dummy"}})

        # 2. Invalid payload (non-dict)
        import asyncio
        try:
            asyncio.run(dm_place_combatant_on_map(42, MagicMock(), "not a dict"))
            self.fail("HTTPException not raised for non-dict payload")
        except HTTPException as e:
            self.assertEqual(e.status_code, 400)
            self.assertEqual(e.detail, "Invalid payload.")

        # 3. Invalid col/row types
        response = client.post("/api/dm/map/combatants/42/place", json={"col": "abc", "row": 6})
        self.assertEqual(response.status_code, 400)
        self.assertIn("col and row must be integers.", response.json()["detail"])

        # 4. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/combatants/42/place", json={"col": 5, "row": 6})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 5. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Invalid destination")
        response = client.post("/api/dm/map/combatants/42/place", json={"col": 5, "row": 6})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid destination", response.json()["detail"])

        # 6. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/combatants/42/place", json={"col": 5, "row": 6})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to place combatant: Runtime fail", response.json()["detail"])

    def test_remove_aoe_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "remove_result": {"ok": True, "aid": 10},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_AOE,
            payload={"aid": 10}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "aoe_remove")
        self.assertEqual(msg["aid"], 10)

        remove_res = result.data.get("remove_result")
        self.assertIsNotNone(remove_res)
        self.assertTrue(remove_res.get("ok"))
        self.assertEqual(remove_res.get("aid"), 10)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_AOE)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_remove_aoe_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "remove_result": {"ok": False, "error": "AoE not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_AOE,
            payload={"aid": 10}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "AoE not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_AOE)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_remove_aoe_route_level_behavior_mapping(self):
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.delete("/api/dm/map/aoes/{aid}")
        async def dm_remove_aoe(aid: int, request: Request):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_REMOVE_AOE,
                    payload={
                        "aid": int(aid),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                remove_result = cmd_result.data.get("remove_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to remove AoE: {exc}")
            return {
                "ok": True,
                "aid": remove_result.get("aid", int(aid)),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"remove_result": {"ok": True, "aid": 10}}
        )
        response = client.delete("/api/dm/map/aoes/10")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "aid": 10, "snapshot": {"map": "dummy"}})

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.delete("/api/dm/map/aoes/10")
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("AoE not found.")
        response = client.delete("/api/dm/map/aoes/10")
        self.assertEqual(response.status_code, 400)
        self.assertIn("AoE not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.delete("/api/dm/map/aoes/10")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to remove AoE: Runtime fail", response.json()["detail"])

    def test_move_aoe_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "move_result": {"ok": True, "aid": 10, "aoe": {"cx": 5.0, "cy": 6.0}},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_MOVE_AOE,
            payload={"aid": 10, "cx": 5.0, "cy": 6.0}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "aoe_move")
        self.assertEqual(msg["aid"], 10)
        self.assertEqual(msg["cx"], 5.0)
        self.assertEqual(msg["cy"], 6.0)

        move_res = result.data.get("move_result")
        self.assertIsNotNone(move_res)
        self.assertTrue(move_res.get("ok"))
        self.assertEqual(move_res.get("aid"), 10)
        self.assertEqual(move_res.get("aoe"), {"cx": 5.0, "cy": 6.0})

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_MOVE_AOE)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_move_aoe_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "move_result": {"ok": False, "error": "AoE not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_MOVE_AOE,
            payload={"aid": 10, "cx": 5.0, "cy": 6.0}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "AoE not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_MOVE_AOE)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_move_aoe_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/aoes/{aid}/move")
        async def dm_move_aoe(aid: int, request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_MOVE_AOE,
                    payload={
                        "aid": int(aid),
                        "admin_token": "fake-token",
                        **payload
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                move_result = cmd_result.data.get("move_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to move AoE: {exc}")
            return {
                "ok": True,
                "aid": move_result.get("aid", int(aid)),
                "aoe": move_result.get("aoe"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"move_result": {"ok": True, "aid": 10, "aoe": {"cx": 5.0, "cy": 6.0}}}
        )
        response = client.post("/api/dm/map/aoes/10/move", json={"cx": 5.0, "cy": 6.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "aid": 10, "aoe": {"cx": 5.0, "cy": 6.0}, "snapshot": {"map": "dummy"}})

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/aoes/10/move", json={"cx": 5.0, "cy": 6.0})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("AoE not found.")
        response = client.post("/api/dm/map/aoes/10/move", json={"cx": 5.0, "cy": 6.0})
        self.assertEqual(response.status_code, 400)
        self.assertIn("AoE not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/aoes/10/move", json={"cx": 5.0, "cy": 6.0})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to move AoE: Runtime fail", response.json()["detail"])

    def test_set_obstacle_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "obstacle_result": {"ok": True, "col": 2, "row": 3, "blocked": True},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_OBSTACLE,
            payload={"col": 2, "row": 3, "blocked": True}
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_obstacle")
        self.assertEqual(msg["col"], 2)
        self.assertEqual(msg["row"], 3)
        self.assertEqual(msg["blocked"], True)

        obstacle_res = result.data.get("obstacle_result")
        self.assertIsNotNone(obstacle_res)
        self.assertTrue(obstacle_res.get("ok"))
        self.assertEqual(obstacle_res.get("col"), 2)
        self.assertEqual(obstacle_res.get("row"), 3)
        self.assertEqual(obstacle_res.get("blocked"), True)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_OBSTACLE)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_set_obstacle_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "obstacle_result": {"ok": False, "error": "Cell out of bounds."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_OBSTACLE,
            payload={"col": 999, "row": 3, "blocked": True}
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Cell out of bounds.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_OBSTACLE)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_obstacle_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/obstacles/cell")
        async def dm_set_obstacle_cell(request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            try:
                col = int(payload.get("col"))
                row = int(payload.get("row"))
            except Exception:
                raise HTTPException(status_code=400, detail="col and row must be integers.")
            blocked = bool(payload.get("blocked", True))
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_OBSTACLE,
                    payload={
                        "col": int(col),
                        "row": int(row),
                        "blocked": bool(blocked),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                obstacle_result = cmd_result.data.get("obstacle_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update obstacle: {exc}")
            return {
                "ok": True,
                "col": obstacle_result.get("col"),
                "row": obstacle_result.get("row"),
                "blocked": obstacle_result.get("blocked"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"obstacle_result": {"ok": True, "col": 2, "row": 3, "blocked": True}}
        )
        response = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 3, "blocked": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "col": 2, "row": 3, "blocked": True, "snapshot": {"map": "dummy"}})

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 3, "blocked": True})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Cell out of bounds.")
        response = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 3, "blocked": True})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cell out of bounds.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/obstacles/cell", json={"col": 2, "row": 3, "blocked": True})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update obstacle: Runtime fail", response.json()["detail"])

    def test_set_terrain_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "terrain_result": {
                        "ok": True,
                        "col": 2,
                        "row": 3,
                        "is_rough": True,
                        "movement_type": "water",
                        "color": "blue",
                        "label": "Deep Water",
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_TERRAIN,
            payload={
                "col": 2,
                "row": 3,
                "is_rough": True,
                "movement_type": "water",
                "color": "blue",
                "label": "Deep Water",
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_terrain")
        self.assertEqual(msg["col"], 2)
        self.assertEqual(msg["row"], 3)
        self.assertEqual(msg["is_rough"], True)
        self.assertEqual(msg["movement_type"], "water")
        self.assertEqual(msg["color"], "blue")
        self.assertEqual(msg["label"], "Deep Water")

        terrain_res = result.data.get("terrain_result")
        self.assertIsNotNone(terrain_res)
        self.assertTrue(terrain_res.get("ok"))
        self.assertEqual(terrain_res.get("col"), 2)
        self.assertEqual(terrain_res.get("row"), 3)
        self.assertEqual(terrain_res.get("is_rough"), True)
        self.assertEqual(terrain_res.get("movement_type"), "water")
        self.assertEqual(terrain_res.get("color"), "blue")
        self.assertEqual(terrain_res.get("label"), "Deep Water")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_TERRAIN)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_set_terrain_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "terrain_result": {"ok": False, "error": "Cell out of bounds."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_TERRAIN,
            payload={
                "col": 999,
                "row": 3,
                "is_rough": True,
                "movement_type": "ground",
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Cell out of bounds.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_TERRAIN)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_terrain_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/terrain/cell")
        async def dm_set_terrain_cell(request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            try:
                col = int(payload.get("col"))
                row = int(payload.get("row"))
            except Exception:
                raise HTTPException(status_code=400, detail="col and row must be integers.")
            is_rough = bool(payload.get("is_rough", True))
            movement_type = str(payload.get("movement_type") or "ground")
            color = payload.get("color")
            label = payload.get("label")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_TERRAIN,
                    payload={
                        "col": int(col),
                        "row": int(row),
                        "is_rough": bool(is_rough),
                        "movement_type": movement_type,
                        "color": color,
                        "label": label,
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                terrain_result = cmd_result.data.get("terrain_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update terrain: {exc}")
            return {
                "ok": True,
                "col": terrain_result.get("col"),
                "row": terrain_result.get("row"),
                "is_rough": terrain_result.get("is_rough"),
                "movement_type": terrain_result.get("movement_type"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"terrain_result": {"ok": True, "col": 2, "row": 3, "is_rough": True, "movement_type": "water"}}
        )
        response = client.post("/api/dm/map/terrain/cell", json={"col": 2, "row": 3, "is_rough": True, "movement_type": "water"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "col": 2,
            "row": 3,
            "is_rough": True,
            "movement_type": "water",
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/terrain/cell", json={"col": 2, "row": 3, "is_rough": True})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Cell out of bounds.")
        response = client.post("/api/dm/map/terrain/cell", json={"col": 2, "row": 3, "is_rough": True})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cell out of bounds.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/terrain/cell", json={"col": 2, "row": 3, "is_rough": True})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update terrain: Runtime fail", response.json()["detail"])

    def test_set_elevation_command_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "elevation_result": {
                        "ok": True,
                        "col": 2,
                        "row": 3,
                        "elevation": 10.0,
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_ELEVATION,
            payload={
                "col": 2,
                "row": 3,
                "elevation": 10.0,
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_elevation")
        self.assertEqual(msg["col"], 2)
        self.assertEqual(msg["row"], 3)
        self.assertEqual(msg["elevation"], 10.0)

        elevation_res = result.data.get("elevation_result")
        self.assertIsNotNone(elevation_res)
        self.assertTrue(elevation_res.get("ok"))
        self.assertEqual(elevation_res.get("col"), 2)
        self.assertEqual(elevation_res.get("row"), 3)
        self.assertEqual(elevation_res.get("elevation"), 10.0)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_ELEVATION)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_set_elevation_command_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "elevation_result": {"ok": False, "error": "Cell out of bounds."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_ELEVATION,
            payload={
                "col": 999,
                "row": 3,
                "elevation": 10.0,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Cell out of bounds.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_ELEVATION)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_elevation_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/elevation/cell")
        async def dm_set_map_elevation(request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            try:
                col = int(payload.get("col"))
                row = int(payload.get("row"))
            except Exception:
                raise HTTPException(status_code=400, detail="col and row must be integers.")
            if payload.get("elevation") is None:
                raise HTTPException(status_code=400, detail="elevation is required.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_ELEVATION,
                    payload={
                        "col": int(col),
                        "row": int(row),
                        "elevation": payload.get("elevation"),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                elevation_result = cmd_result.data.get("elevation_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to set elevation: {exc}")
            return {
                "ok": True,
                "col": elevation_result.get("col"),
                "row": elevation_result.get("row"),
                "elevation": elevation_result.get("elevation"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"elevation_result": {"ok": True, "col": 2, "row": 3, "elevation": 10.0}}
        )
        response = client.post("/api/dm/map/elevation/cell", json={"col": 2, "row": 3, "elevation": 10.0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "col": 2,
            "row": 3,
            "elevation": 10.0,
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/elevation/cell", json={"col": 2, "row": 3, "elevation": 10.0})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Cell out of bounds.")
        response = client.post("/api/dm/map/elevation/cell", json={"col": 2, "row": 3, "elevation": 10.0})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cell out of bounds.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/elevation/cell", json={"col": 2, "row": 3, "elevation": 10.0})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to set elevation: Runtime fail", response.json()["detail"])

    def test_set_map_settings_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "settings_result": {
                        "ok": True,
                        "grid": {
                            "cols": 12,
                            "rows": 15,
                            "feet_per_square": 5.0
                        }
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_MAP_SETTINGS,
            payload={
                "cols": 12,
                "rows": 15,
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_map_settings")
        self.assertEqual(msg["cols"], 12)
        self.assertEqual(msg["rows"], 15)

        settings_res = result.data.get("settings_result")
        self.assertIsNotNone(settings_res)
        self.assertTrue(settings_res.get("ok"))
        self.assertEqual(settings_res.get("grid", {}).get("cols"), 12)
        self.assertEqual(settings_res.get("grid", {}).get("rows"), 15)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_MAP_SETTINGS)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_set_map_settings_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "settings_result": {"ok": False, "error": "Invalid dimensions."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_MAP_SETTINGS,
            payload={
                "cols": -5,
                "rows": 15,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Invalid dimensions.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_MAP_SETTINGS)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_set_map_settings_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/settings")
        async def dm_set_map_settings(request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)):
            if payload is not None and not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            body = payload if isinstance(payload, dict) else {}
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_MAP_SETTINGS,
                    payload={
                        "cols": body.get("cols"),
                        "rows": body.get("rows"),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                settings_result = cmd_result.data.get("settings_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update map settings: {exc}")
            if not settings_result.get("ok"):
                raise HTTPException(status_code=400, detail=settings_result.get("error", "Cannot update map settings."))
            return {
                "ok": True,
                "grid": settings_result.get("grid"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"settings_result": {"ok": True, "grid": {"cols": 12, "rows": 15, "feet_per_square": 5.0}}}
        )
        response = client.post("/api/dm/map/settings", json={"cols": 12, "rows": 15})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "grid": {"cols": 12, "rows": 15, "feet_per_square": 5.0},
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/settings", json={"cols": 12, "rows": 15})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Invalid dimensions.")
        response = client.post("/api/dm/map/settings", json={"cols": 12, "rows": 15})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid dimensions.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/settings", json={"cols": 12, "rows": 15})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update map settings: Runtime fail", response.json()["detail"])

    def test_upsert_background_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "background_result": {
                        "ok": True,
                        "background": {
                            "bid": 1,
                            "path": "maps/forest.png",
                            "x": 0.0,
                            "y": 0.0,
                            "scale_pct": 100.0,
                            "trans_pct": 0.0,
                            "locked": False,
                            "asset_url": "/assets/maps/forest.png"
                        }
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_BACKGROUND,
            payload={
                "asset_path": "maps/forest.png",
                "bid": None,
                "x": 0.0,
                "y": 0.0,
                "scale_pct": 100.0,
                "trans_pct": 0.0,
                "locked": False,
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "upsert_map_background")
        self.assertEqual(msg["asset_path"], "maps/forest.png")

        bg_res = result.data.get("background_result")
        self.assertIsNotNone(bg_res)
        self.assertTrue(bg_res.get("ok"))
        self.assertEqual(bg_res.get("background", {}).get("bid"), 1)
        self.assertEqual(bg_res.get("background", {}).get("path"), "maps/forest.png")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_BACKGROUND)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_upsert_background_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "background_result": {"ok": False, "error": "Background asset path is invalid or not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_BACKGROUND,
            payload={
                "asset_path": "invalid.png",
                "bid": None,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Background asset path is invalid or not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_BACKGROUND)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_upsert_background_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/backgrounds")
        async def dm_upsert_background(request: Request, payload: Dict[str, Any] = Body(...)):
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Invalid payload.")
            asset_path = payload.get("asset_path")
            if asset_path in (None, ""):
                raise HTTPException(status_code=400, detail="asset_path is required.")
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_UPSERT_MAP_BACKGROUND,
                    payload={
                        "asset_path": asset_path,
                        "bid": payload.get("bid"),
                        "x": payload.get("x", 0.0),
                        "y": payload.get("y", 0.0),
                        "scale_pct": payload.get("scale_pct", 100.0),
                        "trans_pct": payload.get("trans_pct", 0.0),
                        "locked": payload.get("locked", False),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                background_result = cmd_result.data.get("background_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update background layer: {exc}")
            if not background_result.get("ok"):
                raise HTTPException(status_code=400, detail=background_result.get("error", "Cannot update background layer."))
            return {
                "ok": True,
                "background": background_result.get("background"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"background_result": {"ok": True, "background": {"bid": 1, "path": "maps/forest.png"}}}
        )
        response = client.post("/api/dm/map/backgrounds", json={"asset_path": "maps/forest.png"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "background": {"bid": 1, "path": "maps/forest.png"},
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/backgrounds", json={"asset_path": "maps/forest.png"})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Background asset path is invalid or not found.")
        response = client.post("/api/dm/map/backgrounds", json={"asset_path": "maps/forest.png"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Background asset path is invalid or not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/backgrounds", json={"asset_path": "maps/forest.png"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update background layer: Runtime fail", response.json()["detail"])

    def test_remove_background_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "remove_background_result": {
                        "ok": True,
                        "bid": 3
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_BACKGROUND,
            payload={
                "bid": 3,
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "remove_map_background")
        self.assertEqual(msg["bid"], 3)

        bg_res = result.data.get("remove_background_result")
        self.assertIsNotNone(bg_res)
        self.assertTrue(bg_res.get("ok"))
        self.assertEqual(bg_res.get("bid"), 3)

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_BACKGROUND)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_remove_background_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "remove_background_result": {"ok": False, "error": "Background layer not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_BACKGROUND,
            payload={
                "bid": 99,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Background layer not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_BACKGROUND)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_remove_background_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.delete("/api/dm/map/backgrounds/{bid}")
        async def dm_remove_background(bid: int, request: Request):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_REMOVE_MAP_BACKGROUND,
                    payload={
                        "bid": bid,
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                remove_background_result = cmd_result.data.get("remove_background_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to remove background layer: {exc}")
            if not remove_background_result.get("ok"):
                raise HTTPException(status_code=400, detail=remove_background_result.get("error", "Cannot remove background layer."))
            return {
                "ok": True,
                "bid": remove_background_result.get("bid"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={"remove_background_result": {"ok": True, "bid": 3}}
        )
        response = client.delete("/api/dm/map/backgrounds/3")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "bid": 3,
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.delete("/api/dm/map/backgrounds/3")
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Background layer not found.")
        response = client.delete("/api/dm/map/backgrounds/3")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Background layer not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.delete("/api/dm/map/backgrounds/3")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to remove background layer: Runtime fail", response.json()["detail"])

    def test_reorder_background_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "reorder_background_result": {
                        "ok": True,
                        "bid": 3,
                        "background": {"bid": 3, "asset_path": "maps/forest.png"},
                        "backgrounds": [{"bid": 3, "asset_path": "maps/forest.png"}]
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_MAP_BACKGROUND_ORDER,
            payload={
                "bid": 3,
                "direction": "up",
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "set_map_background_order")
        self.assertEqual(msg["bid"], 3)
        self.assertEqual(msg["direction"], "up")

        bg_res = result.data.get("reorder_background_result")
        self.assertIsNotNone(bg_res)
        self.assertTrue(bg_res.get("ok"))
        self.assertEqual(bg_res.get("bid"), 3)
        self.assertEqual(bg_res.get("background", {}).get("asset_path"), "maps/forest.png")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_MAP_BACKGROUND_ORDER)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_reorder_background_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "reorder_background_result": {"ok": False, "error": "Direction must be up, down, front, or back."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_SET_MAP_BACKGROUND_ORDER,
            payload={
                "bid": 3,
                "direction": "invalid",
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Direction must be up, down, front, or back.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_SET_MAP_BACKGROUND_ORDER)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_reorder_background_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/backgrounds/{bid}/order")
        async def dm_reorder_background(bid: int, request: Request, payload: Dict[str, Any] = Body(...)):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_SET_MAP_BACKGROUND_ORDER,
                    payload={
                        "bid": bid,
                        "direction": payload.get("direction"),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                reorder_background_result = cmd_result.data.get("reorder_background_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to reorder background layer: {exc}")
            if not reorder_background_result.get("ok"):
                raise HTTPException(status_code=400, detail=reorder_background_result.get("error", "Cannot reorder background layer."))
            return {
                "ok": True,
                "bid": reorder_background_result.get("bid"),
                "background": reorder_background_result.get("background", {}),
                "backgrounds": reorder_background_result.get("backgrounds", []),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={
                "reorder_background_result": {
                    "ok": True,
                    "bid": 3,
                    "background": {"bid": 3, "asset_path": "maps/forest.png"},
                    "backgrounds": [{"bid": 3, "asset_path": "maps/forest.png"}]
                }
            }
        )
        response = client.post("/api/dm/map/backgrounds/3/order", json={"direction": "up"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "bid": 3,
            "background": {"bid": 3, "asset_path": "maps/forest.png"},
            "backgrounds": [{"bid": 3, "asset_path": "maps/forest.png"}],
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/backgrounds/3/order", json={"direction": "up"})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Direction must be up, down, front, or back.")
        response = client.post("/api/dm/map/backgrounds/3/order", json={"direction": "up"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Direction must be up, down, front, or back.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/backgrounds/3/order", json={"direction": "up"})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to reorder background layer: Runtime fail", response.json()["detail"])


    def test_upsert_hazard_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "hazard_result": {
                        "ok": True,
                        "hazard_id": "hazard-123",
                        "hazard": {
                            "col": 2,
                            "row": 3,
                            "kind": "hazard",
                            "name": "Fire Trap"
                        }
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_HAZARD,
            payload={
                "col": 2,
                "row": 3,
                "hazard_id": "hazard-123",
                "kind": "hazard",
                "name": "Fire Trap",
                "payload": {}
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "upsert_map_hazard")
        self.assertEqual(msg["col"], 2)
        self.assertEqual(msg["row"], 3)

        haz_res = result.data.get("hazard_result")
        self.assertIsNotNone(haz_res)
        self.assertTrue(haz_res.get("ok"))
        self.assertEqual(haz_res.get("hazard_id"), "hazard-123")
        self.assertEqual(haz_res.get("hazard", {}).get("name"), "Fire Trap")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_HAZARD)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_upsert_hazard_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "hazard_result": {"ok": False, "error": "col and row must be integers."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_HAZARD,
            payload={
                "col": "invalid",
                "row": 3,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "col and row must be integers.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_HAZARD)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_upsert_hazard_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/hazards")
        async def dm_upsert_hazard(request: Request, payload: Dict[str, Any] = Body(...)):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_UPSERT_MAP_HAZARD,
                    payload={
                        "col": payload.get("col"),
                        "row": payload.get("row"),
                        "hazard_id": payload.get("hazard_id"),
                        "kind": payload.get("kind"),
                        "tactical_preset_id": payload.get("tactical_preset_id"),
                        "count": payload.get("count"),
                        "name": payload.get("name"),
                        "payload": payload.get("payload"),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                hazard_result = cmd_result.data.get("hazard_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update hazard: {exc}")
            if not hazard_result.get("ok"):
                raise HTTPException(status_code=400, detail=hazard_result.get("error", "Cannot update hazard."))
            return {
                "ok": True,
                "hazard_id": hazard_result.get("hazard_id"),
                "hazard": hazard_result.get("hazard"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={
                "hazard_result": {
                    "ok": True,
                    "hazard_id": "hazard-123",
                    "hazard": {"col": 2, "row": 3, "kind": "hazard", "name": "Fire Trap"}
                }
            }
        )
        response = client.post("/api/dm/map/hazards", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "hazard_id": "hazard-123",
            "hazard": {"col": 2, "row": 3, "kind": "hazard", "name": "Fire Trap"},
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/hazards", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("col and row must be integers.")
        response = client.post("/api/dm/map/hazards", json={"col": "invalid", "row": 3})
        self.assertEqual(response.status_code, 400)
        self.assertIn("col and row must be integers.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/hazards", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update hazard: Runtime fail", response.json()["detail"])

    def test_remove_hazard_success(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "hazard_result": {
                        "ok": True,
                        "hazard_id": "hazard-123"
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_HAZARD,
            payload={
                "hazard_id": "hazard-123"
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "remove_map_hazard")
        self.assertEqual(msg["hazard_id"], "hazard-123")

        haz_res = result.data.get("hazard_result")
        self.assertIsNotNone(haz_res)
        self.assertTrue(haz_res.get("ok"))
        self.assertEqual(haz_res.get("hazard_id"), "hazard-123")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_HAZARD)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_remove_hazard_validation_failure(self):
        import threading
        import time

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "hazard_result": {"ok": False, "error": "Hazard not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_HAZARD,
            payload={
                "hazard_id": "nonexistent"
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Hazard not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_HAZARD)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_remove_hazard_route_level_behavior_mapping(self):
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.delete("/api/dm/map/hazards/{hazard_id}")
        async def dm_remove_hazard(hazard_id: str, request: Request):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_REMOVE_MAP_HAZARD,
                    payload={
                        "hazard_id": hazard_id,
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                hazard_result = cmd_result.data.get("hazard_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to remove hazard: {exc}")
            if not hazard_result.get("ok"):
                raise HTTPException(status_code=400, detail=hazard_result.get("error", "Cannot remove hazard."))
            return {
                "ok": True,
                "hazard_id": hazard_result.get("hazard_id"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={
                "hazard_result": {
                    "ok": True,
                    "hazard_id": "hazard-123"
                }
            }
        )
        response = client.delete("/api/dm/map/hazards/hazard-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "hazard_id": "hazard-123",
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.delete("/api/dm/map/hazards/hazard-123")
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Hazard not found.")
        response = client.delete("/api/dm/map/hazards/nonexistent")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Hazard not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.delete("/api/dm/map/hazards/hazard-123")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to remove hazard: Runtime fail", response.json()["detail"])

    def test_upsert_feature_success(self):
        import threading
        import time
        from server_runtime import COMMAND_UPSERT_MAP_FEATURE

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "feature_result": {
                        "ok": True,
                        "feature_id": "feature-123",
                        "feature": {
                            "col": 2,
                            "row": 3,
                            "kind": "feature",
                            "name": "Wall"
                        }
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_FEATURE,
            payload={
                "col": 2,
                "row": 3,
                "feature_id": "feature-123",
                "kind": "feature",
                "name": "Wall",
                "payload": {}
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "upsert_map_feature")
        self.assertEqual(msg["col"], 2)
        self.assertEqual(msg["row"], 3)

        feat_res = result.data.get("feature_result")
        self.assertIsNotNone(feat_res)
        self.assertTrue(feat_res.get("ok"))
        self.assertEqual(feat_res.get("feature_id"), "feature-123")
        self.assertEqual(feat_res.get("feature", {}).get("name"), "Wall")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_FEATURE)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_upsert_feature_validation_failure(self):
        import threading
        import time
        from server_runtime import COMMAND_UPSERT_MAP_FEATURE

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "feature_result": {"ok": False, "error": "col and row must be integers."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_UPSERT_MAP_FEATURE,
            payload={
                "col": "invalid",
                "row": 3,
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "col and row must be integers.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_UPSERT_MAP_FEATURE)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_upsert_feature_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional
        from server_runtime import COMMAND_UPSERT_MAP_FEATURE

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.post("/api/dm/map/features")
        async def dm_upsert_feature(request: Request, payload: Dict[str, Any] = Body(...)):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_UPSERT_MAP_FEATURE,
                    payload={
                        "col": payload.get("col"),
                        "row": payload.get("row"),
                        "feature_id": payload.get("feature_id"),
                        "kind": payload.get("kind"),
                        "tactical_preset_id": payload.get("tactical_preset_id"),
                        "count": payload.get("count"),
                        "name": payload.get("name"),
                        "payload": payload.get("payload"),
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                feature_result = cmd_result.data.get("feature_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to update feature: {exc}")
            if not feature_result.get("ok"):
                raise HTTPException(status_code=400, detail=feature_result.get("error", "Cannot update feature."))
            return {
                "ok": True,
                "feature_id": feature_result.get("feature_id"),
                "feature": feature_result.get("feature"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={
                "feature_result": {
                    "ok": True,
                    "feature_id": "feature-123",
                    "feature": {"col": 2, "row": 3, "kind": "feature", "name": "Wall"}
                }
            }
        )
        response = client.post("/api/dm/map/features", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "feature_id": "feature-123",
            "feature": {"col": 2, "row": 3, "kind": "feature", "name": "Wall"},
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.post("/api/dm/map/features", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("col and row must be integers.")
        response = client.post("/api/dm/map/features", json={"col": "invalid", "row": 3})
        self.assertEqual(response.status_code, 400)
        self.assertIn("col and row must be integers.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.post("/api/dm/map/features", json={"col": 2, "row": 3})
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to update feature: Runtime fail", response.json()["detail"])

    def test_remove_feature_success(self):
        import threading
        import time
        from server_runtime import COMMAND_REMOVE_MAP_FEATURE

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_success(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "feature_result": {
                        "ok": True,
                        "feature_id": "feature-123"
                    },
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_success

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_FEATURE,
            payload={
                "feature_id": "feature-123"
            }
        )

        result = facade.submit_command(command)
        self.assertTrue(result.success)
        self.assertEqual(len(captured_msg), 1)
        msg = captured_msg[0]
        self.assertEqual(msg["type"], "remove_map_feature")
        self.assertEqual(msg["feature_id"], "feature-123")

        feat_res = result.data.get("feature_result")
        self.assertIsNotNone(feat_res)
        self.assertTrue(feat_res.get("ok"))
        self.assertEqual(feat_res.get("feature_id"), "feature-123")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_FEATURE)
        self.assertEqual(trace.status, "completed")
        self.assertIsNone(trace.error_class)
        self.assertEqual(trace.metadata["queue_size"], 1)
        self.assertIn("queue_wait_ms", trace.metadata)

    def test_remove_feature_validation_failure(self):
        import threading
        import time
        from server_runtime import COMMAND_REMOVE_MAP_FEATURE

        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None
            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)
            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()
        captured_msg = []

        def process_failure(msg):
            captured_msg.append(msg)
            action_id = msg["action_id"]
            with controller._action_states_lock:
                controller._action_states[action_id].update({
                    "status": "completed",
                    "result": {"status": "applied"},
                    "feature_result": {"ok": False, "error": "Feature not found."},
                    "completed_at_ns": time.perf_counter_ns()
                })

        controller._actions.on_put = process_failure

        facade = ServerRuntimeFacade(lan_controller=controller)
        command = RuntimeCommand(
            command_type=COMMAND_REMOVE_MAP_FEATURE,
            payload={
                "feature_id": "nonexistent"
            }
        )

        with self.assertRaises(ValueError) as ctx:
            facade.submit_command(command)
        self.assertEqual(str(ctx.exception), "Feature not found.")

        trace = facade.last_command_trace
        self.assertIsNotNone(trace)
        self.assertEqual(trace.command_type, COMMAND_REMOVE_MAP_FEATURE)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_class, "ValueError")
        self.assertEqual(trace.metadata["queue_size"], 1)

    def test_remove_feature_route_level_behavior_mapping(self):
        from fastapi import FastAPI, Body, HTTPException, Request
        from fastapi.testclient import TestClient
        from typing import Dict, Any, Optional
        from server_runtime import COMMAND_REMOVE_MAP_FEATURE

        app = FastAPI()
        mock_runtime = MagicMock()

        def _dm_console_snapshot():
            return {"map": "dummy"}

        @app.delete("/api/dm/map/features/{feature_id}")
        async def dm_remove_feature(feature_id: str, request: Request):
            try:
                command = RuntimeCommand(
                    command_type=COMMAND_REMOVE_MAP_FEATURE,
                    payload={
                        "feature_id": feature_id,
                        "admin_token": "fake-token",
                    }
                )
                cmd_result = mock_runtime.submit_command(command)
                feature_result = cmd_result.data.get("feature_result") or {}
            except TimeoutError as exc:
                raise HTTPException(status_code=504, detail=str(exc))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to remove feature: {exc}")
            if not feature_result.get("ok"):
                raise HTTPException(status_code=400, detail=feature_result.get("error", "Cannot remove feature."))
            return {
                "ok": True,
                "feature_id": feature_result.get("feature_id"),
                "snapshot": _dm_console_snapshot(),
            }

        client = TestClient(app)

        # 1. Success case
        mock_runtime.submit_command.return_value = RuntimeCommandResult(
            success=True, message="ok", data={
                "feature_result": {
                    "ok": True,
                    "feature_id": "feature-123"
                }
            }
        )
        response = client.delete("/api/dm/map/features/feature-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "ok": True,
            "feature_id": "feature-123",
            "snapshot": {"map": "dummy"}
        })

        # 2. TimeoutError -> 504
        mock_runtime.submit_command.side_effect = TimeoutError("Command timed out")
        response = client.delete("/api/dm/map/features/feature-123")
        self.assertEqual(response.status_code, 504)
        self.assertIn("Command timed out", response.json()["detail"])

        # 3. ValueError -> 400
        mock_runtime.submit_command.side_effect = ValueError("Feature not found.")
        response = client.delete("/api/dm/map/features/nonexistent")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Feature not found.", response.json()["detail"])

        # 4. Generic Exception -> 500
        mock_runtime.submit_command.side_effect = Exception("Runtime fail")
        response = client.delete("/api/dm/map/features/feature-123")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Failed to remove feature: Runtime fail", response.json()["detail"])

    def test_combat_route_instrumentation_under_debug_trace(self):
        from runtime_config import configure_debug_trace
        from server_runtime import RuntimeSnapshotResult
        import tempfile
        import json
        from pathlib import Path

        # Setup temp trace log
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = configure_debug_trace(True, log_dir=Path(tmpdir))
            self.assertIsNotNone(trace_path)

            payload = {
                "in_combat": True,
                "round": 3,
                "combatants": [
                    {"cid": 1, "is_pc": True, "name": "PC 1"},
                    {"cid": 2, "is_pc": False, "name": "Monster 1"},
                ],
                "turn_order": [1, 2],
                "battle_log": ["test log"],
                "pending_prompts": {},
            }
            runtime = self._DmCombatRouteRuntime(
                result=RuntimeSnapshotResult(success=True, data=payload)
            )
            mock_lan = MagicMock()
            mock_lan._debug_trace_counts.return_value = {
                "combatant_count": 2,
                "player_count": 1,
                "monster_count": 1,
                "websocket_client_count": 0,
                "dm_websocket_client_count": 0,
                "total_websocket_client_count": 0,
            }
            runtime.lan_controller = mock_lan
            # Create the test client
            client, _ = self._dm_combat_route_client(runtime=runtime)

            # 1. Run request and ensure it returns 200 and matches payload
            response = client.get("/api/dm/combat")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), payload)

            # 2. Read generated trace
            configure_debug_trace(False) # flush and close
            lines = Path(trace_path).read_text(encoding="utf-8").splitlines()
            entries = [json.loads(line) for line in lines if line.strip()]

            # 3. Assert threadpool queue timing spans exist
            queue_start = next((e for e in entries if e.get("span") == "dm.console.threadpool_dispatch_queue" and e.get("event") == "span.start"), None)
            queue_end = next((e for e in entries if e.get("span") == "dm.console.threadpool_dispatch_queue" and e.get("event") == "span.end"), None)

            self.assertIsNotNone(queue_start)
            self.assertIsNotNone(queue_end)
            self.assertEqual(queue_start.get("route"), "/api/dm/combat")
            self.assertEqual(queue_start.get("method"), "GET")
            self.assertTrue(queue_start.get("read_in_threadpool"))

            # Check low cardinality on queue span: no player/monster names, no ids
            for key, val in queue_start.items():
                if isinstance(val, str):
                    self.assertNotIn("PC 1", val)
                    self.assertNotIn("Monster 1", val)

            # 4. Assert response build span exists
            build_start = next((e for e in entries if e.get("span") == "dm.console.route_response_build" and e.get("event") == "span.start"), None)
            build_end = next((e for e in entries if e.get("span") == "dm.console.route_response_build" and e.get("event") == "span.end"), None)

            self.assertIsNotNone(build_start)
            self.assertIsNotNone(build_end)
            self.assertEqual(build_start.get("combatant_count"), 2)
            self.assertEqual(build_start.get("player_count"), 1)
            self.assertEqual(build_start.get("monster_count"), 1)
            self.assertEqual(build_start.get("top_level_key_count"), 6)

            # Check low cardinality on build span: no player/monster names, no ids
            for key, val in build_start.items():
                if isinstance(val, str):
                    self.assertNotIn("PC 1", val)
                    self.assertNotIn("Monster 1", val)

    def test_combat_route_works_without_debug_trace(self):
        from runtime_config import configure_debug_trace
        from server_runtime import RuntimeSnapshotResult

        configure_debug_trace(False)
        payload = {
            "in_combat": True,
            "round": 3,
            "combatants": [
                {"cid": 1, "is_pc": True, "name": "PC 1"},
            ],
        }
        runtime = self._DmCombatRouteRuntime(
            result=RuntimeSnapshotResult(success=True, data=payload)
        )
        client, _ = self._dm_combat_route_client(runtime=runtime)

        response = client.get("/api/dm/combat")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def _combat_queue_facade(self, combat_result, response_snapshot):
        class FakeQueue:
            def __init__(self):
                self.items = []
                self.on_put = None

            def put(self, item):
                self.items.append(item)
                if self.on_put:
                    self.on_put(item)

            def qsize(self):
                return len(self.items)

        class FakeLanController:
            def __init__(self):
                self._actions = FakeQueue()
                self._action_states = {}
                self._action_states_lock = threading.Lock()
                self._action_history_limit = 500

        controller = FakeLanController()

        def complete(msg):
            with controller._action_states_lock:
                controller._action_states[msg["action_id"]].update({
                    "status": "completed",
                    "result": {"status": None},
                    "combat_result": combat_result,
                    "response_snapshot": response_snapshot,
                    "authority_started_at_ns": time.perf_counter_ns(),
                    "completed_at_ns": time.perf_counter_ns(),
                })

        controller._actions.on_put = complete
        return ServerRuntimeFacade(controller), controller

    def _authority_runtime(self, command_type, *, trace_broadcasts=False):
        from dnd_initative_tracker import InitiativeTracker, LanController

        controller = LanController.__new__(LanController)
        tracker = InitiativeTracker.__new__(InitiativeTracker)
        calls = []
        snapshot_completion_states = []

        class Service:
            def _record(self, method, result):
                calls.append((method, threading.get_ident()))
                if trace_broadcasts:
                    controller._broadcast_state({})
                    controller._push_dm_snapshot_to_ws_clients({})
                return result

            def start_combat(self):
                return self._record("start_combat", {"ok": True, "snapshot": {"round": 1}})

            def set_turn_here(self, cid):
                return self._record(
                    "set_turn_here",
                    {"ok": True, "cid": cid, "previous_cid": 3, "snapshot": {"active_cid": cid}},
                )

            def next_turn(self):
                return self._record("next_turn", {"ok": True, "snapshot": {"active_cid": 9}})

        tracker.combatants = {7: object()}
        tracker.current_cid = 7
        tracker.in_combat = True
        tracker._dm_service = Service()
        tracker._is_admin_token_valid = lambda token: token == "admin"
        tracker._lan = controller

        controller._tracker = tracker
        controller._is_admin_token_valid = lambda token: token == "admin"
        controller._actions = queue.Queue()
        controller._action_states = {}
        controller._action_states_lock = threading.Lock()
        controller._action_history_limit = 500
        controller._active_poll_interval_ms = 120
        controller._polling = False
        controller._latest_manual_resource_action = {}
        controller._clients_lock = threading.Lock()
        controller._clients = {}
        controller._dm_ws_clients = {}
        controller._battle_log_subscribers = set()
        controller._cached_snapshot = {}
        controller._cached_pcs = []
        controller._grid_last_sent = (None, None)
        controller._grid_version = 0
        controller._last_snapshot = None
        controller._last_static_check_ts = time.monotonic()
        controller._static_check_interval_s = 999.0
        controller._loop = None
        controller._merge_cached_snapshot_carryover = lambda snap: snap
        controller._append_lan_log = lambda *args, **kwargs: None
        controller.toast = lambda *args, **kwargs: None
        tracker._lan_snapshot = lambda **kwargs: {}
        tracker._lan_pcs = lambda: []
        tracker._lan_static_snapshot_cache_status = lambda: (True, "cached", 1)
        tracker._oplog = lambda *args, **kwargs: None
        tracker.after = lambda *args, **kwargs: None

        def response_snapshot(**kwargs):
            action_id = next(iter(controller._action_states))
            snapshot_completion_states.append(controller._action_states[action_id]["status"])
            return {"authority_snapshot": command_type, "include_tactical": kwargs.get("include_tactical")}

        controller._dm_console_snapshot = response_snapshot
        return controller, calls, snapshot_completion_states

    def test_combat_commands_queue_success_and_contract(self):
        cases = (
            (COMMAND_COMBAT_START, {"ok": True, "snapshot": {"round": 1}}),
            (COMMAND_COMBAT_SET_TURN, {"ok": True, "cid": 7, "previous_cid": 3, "snapshot": {}}),
            (COMMAND_COMBAT_NEXT_TURN, {"ok": True, "snapshot": {"active_cid": 9}}),
        )
        for command_type, combat_result in cases:
            with self.subTest(command_type=command_type):
                facade, controller = self._combat_queue_facade(combat_result, {"response": command_type})
                payload = {
                    "admin_token": "admin",
                    "include_tactical": True,
                    "timeout_ms": 5000,
                    "request_trace_id": "trace-http",
                    "parent_action_id": "request-action",
                }
                if command_type == COMMAND_COMBAT_SET_TURN:
                    payload["cid"] = 7
                result = facade.submit_command(RuntimeCommand(command_type=command_type, payload=payload))

                self.assertEqual(result.data["combat_result"], combat_result)
                self.assertEqual(result.data["response_snapshot"], {"response": command_type})
                self.assertEqual(len(controller._actions.items), 1)
                message = controller._actions.items[0]
                self.assertEqual(message["_trace_id"], "trace-http")
                self.assertEqual(message["_parent_action_id"], "request-action")
                for key in ("admin_token", "include_tactical", "timeout_ms", "request_trace_id", "parent_action_id"):
                    self.assertIn(key, message)
                self.assertEqual("cid" in message, command_type == COMMAND_COMBAT_SET_TURN)

    def test_combat_mutations_run_once_on_authority_and_snapshot_precedes_completion(self):
        expected_methods = {
            COMMAND_COMBAT_START: "start_combat",
            COMMAND_COMBAT_SET_TURN: "set_turn_here",
            COMMAND_COMBAT_NEXT_TURN: "next_turn",
        }
        main_thread_id = threading.get_ident()
        for command_type, expected_method in expected_methods.items():
            with self.subTest(command_type=command_type):
                controller, calls, completion_states = self._authority_runtime(command_type)
                action_id = f"action-{command_type}"
                received_at_ns = time.perf_counter_ns()
                message = {
                    "type": command_type,
                    "action_id": action_id,
                    "_trace_id": "trace-http",
                    "parent_action_id": "request-action",
                    "_received_at_ns": received_at_ns,
                    "_ws_id": None,
                    "_claimed_cid": 7 if command_type == COMMAND_COMBAT_SET_TURN else None,
                    "admin_token": "admin",
                    "include_tactical": True,
                    "timeout_ms": 5000,
                }
                if command_type == COMMAND_COMBAT_SET_TURN:
                    message["cid"] = 7
                controller._action_states[action_id] = {
                    "status": "pending",
                    "queue_wait_span_closed": False,
                    "received_at_ns": received_at_ns,
                }
                controller._actions.put(message)
                authority_thread = threading.Thread(target=controller._tick)
                authority_thread.start()
                authority_thread.join(timeout=2)

                self.assertFalse(authority_thread.is_alive())
                self.assertEqual([method for method, _thread_id in calls], [expected_method])
                self.assertNotEqual(calls[0][1], main_thread_id)
                self.assertEqual(completion_states, ["pending"])
                state = controller._action_states[action_id]
                self.assertEqual(state["status"], "completed")
                self.assertEqual(state["authority_thread_id"], calls[0][1])
                self.assertIsInstance(state.get("combat_result"), dict)
                self.assertIsInstance(state.get("response_snapshot"), dict)

    def test_combat_command_submission_is_offloaded(self):
        from dnd_initative_tracker import _dm_combat_command_in_threadpool

        class Runtime:
            def __init__(self):
                self.thread_ids = []

            def submit_command(self, command):
                self.thread_ids.append(threading.get_ident())
                return RuntimeCommandResult(
                    success=True,
                    message="ok",
                    data={"combat_result": {"ok": True}, "response_snapshot": {"snapshot": True}},
                )

        runtime = Runtime()
        route_thread_id = threading.get_ident()
        command = RuntimeCommand(
            command_type=COMMAND_COMBAT_START,
            payload={"request_trace_id": "trace-http", "parent_action_id": "request-action"},
        )
        result = asyncio.run(_dm_combat_command_in_threadpool(runtime, command, route="/api/dm/combat/start"))

        self.assertEqual(result.data["response_snapshot"], {"snapshot": True})
        self.assertEqual(len(runtime.thread_ids), 1)
        self.assertNotEqual(runtime.thread_ids[0], route_thread_id)

    def test_combat_queue_timeout_has_no_direct_retry(self):
        from dnd_initative_tracker import _dm_combat_command_in_threadpool

        class Runtime:
            def __init__(self):
                self.calls = 0

            def submit_command(self, command):
                self.calls += 1
                raise TimeoutError("Command 'combat_start' timed out after 5000ms")

        runtime = Runtime()
        command = RuntimeCommand(
            command_type=COMMAND_COMBAT_START,
            payload={"request_trace_id": "trace-http", "parent_action_id": "request-action"},
        )
        with self.assertRaises(TimeoutError):
            asyncio.run(_dm_combat_command_in_threadpool(runtime, command, route="/api/dm/combat/start"))
        self.assertEqual(runtime.calls, 1)

    def test_combat_queue_and_direct_modes_preserve_response_shapes(self):
        from unittest.mock import patch
        from dnd_initative_tracker import _combat_mutation_queue_mode

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("INIT_TRACKER_COMBAT_MUTATION_QUEUE", None)
            self.assertEqual(_combat_mutation_queue_mode(), "queue")
        for value, expected in (("queue", "queue"), ("direct", "direct"), ("invalid", "queue")):
            with self.subTest(value=value), patch.dict(os.environ, {"INIT_TRACKER_COMBAT_MUTATION_QUEUE": value}):
                self.assertEqual(_combat_mutation_queue_mode(), expected)

        start_shape = {"ok": True, "snapshot": {}}
        set_shape = {"ok": True, "cid": 7, "previous_cid": 3, "snapshot": {}}
        next_shape = {"ok": True, "snapshot": {}}
        self.assertEqual(set(start_shape), {"ok", "snapshot"})
        self.assertEqual(set(set_shape), {"ok", "cid", "previous_cid", "snapshot"})
        self.assertEqual(set(next_shape), {"ok", "snapshot"})

    def test_combat_facade_rejects_missing_transport_results(self):
        facade, controller = self._combat_queue_facade({"ok": True}, {"snapshot": True})
        controller._actions.on_put = lambda msg: controller._action_states[msg["action_id"]].update({
            "status": "completed",
            "result": {},
            "completed_at_ns": time.perf_counter_ns(),
        })
        command = RuntimeCommand(
            command_type=COMMAND_COMBAT_START,
            payload={"admin_token": "admin", "include_tactical": False, "timeout_ms": 5000},
        )
        with self.assertRaises(RuntimeError):
            facade.submit_command(command)

    def test_combat_domain_results_remain_raw_for_route_mapping(self):
        cases = (
            (COMMAND_COMBAT_START, {"ok": False, "error": "No combatants."}),
            (COMMAND_COMBAT_SET_TURN, {"ok": False, "error": "Combatant not found."}),
            (COMMAND_COMBAT_NEXT_TURN, {"ok": False, "error": "No active combat."}),
        )
        for command_type, combat_result in cases:
            with self.subTest(command_type=command_type):
                facade, _controller = self._combat_queue_facade(combat_result, {"snapshot": True})
                payload = {
                    "admin_token": "admin",
                    "include_tactical": False,
                    "timeout_ms": 5000,
                    "request_trace_id": "trace-http",
                    "parent_action_id": "request-action",
                }
                if command_type == COMMAND_COMBAT_SET_TURN:
                    payload["cid"] = 999
                result = facade.submit_command(RuntimeCommand(command_type=command_type, payload=payload))
                self.assertEqual(result.data["combat_result"], combat_result)

    def test_combat_route_auth_validation_and_fixed_error_mappings_precede_dispatch(self):
        import inspect
        from dnd_initative_tracker import LanController

        source = inspect.getsource(LanController.start)
        route_contracts = (
            (
                "async def dm_next_turn",
                "async def dm_prev_turn",
                "Combat service failed to advance turn.",
                "Failed to advance turn.",
            ),
            (
                "async def dm_set_turn",
                "async def dm_adjust_hp",
                "Cannot set turn.",
                "Failed to set turn.",
            ),
            (
                "async def dm_start_combat",
                "async def dm_end_combat",
                "Cannot start combat.",
                "Failed to start combat.",
            ),
        )
        for start_marker, end_marker, domain_detail, failure_detail in route_contracts:
            with self.subTest(route=start_marker):
                segment = source[source.index(start_marker):source.index(end_marker, source.index(start_marker))]
                self.assertLess(segment.index("_check_dm_auth(request)"), segment.index("_dm_combat_command_in_threadpool"))
                self.assertIn("status_code=503, detail=\"DM combat service unavailable.\"", segment)
                self.assertIn("except TimeoutError as exc", segment)
                self.assertIn("status_code=504, detail=str(exc)", segment)
                self.assertIn(domain_detail, segment)
                self.assertIn(failure_detail, segment)
        set_turn = source[source.index("async def dm_set_turn"):source.index("async def dm_adjust_hp")]
        self.assertLess(set_turn.index("cid = int(cid_raw)"), set_turn.index("_dm_combat_command_in_threadpool"))
        for detail in ("Invalid payload.", "cid is required.", "cid must be an integer."):
            self.assertIn(detail, set_turn)

    def test_combat_mutation_trace_correlation(self):
        from pathlib import Path
        import json
        import tempfile
        from runtime_config import configure_debug_trace, debug_context
        from dnd_initative_tracker import _dm_combat_command_in_threadpool

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = configure_debug_trace(True, log_dir=Path(tmpdir))
            controller, calls, _completion_states = self._authority_runtime(
                COMMAND_COMBAT_START,
                trace_broadcasts=True,
            )
            facade = ServerRuntimeFacade(controller)
            command = RuntimeCommand(
                command_type=COMMAND_COMBAT_START,
                payload={
                    "admin_token": "admin",
                    "include_tactical": False,
                    "timeout_ms": 5000,
                    "request_trace_id": "trace-http",
                    "parent_action_id": "request-action",
                },
            )
            def run_authority():
                deadline = time.monotonic() + 2.0
                while controller._actions.empty() and time.monotonic() < deadline:
                    time.sleep(0.001)
                controller._tick()

            authority_thread = threading.Thread(target=run_authority)
            with debug_context(trace_id="trace-http", action_id="request-action"):
                authority_thread.start()
                result = asyncio.run(
                    _dm_combat_command_in_threadpool(
                        facade,
                        command,
                        route="/api/dm/combat/start",
                    )
                )
            authority_thread.join(timeout=2)
            self.assertEqual(result.data["combat_result"]["ok"], True)
            self.assertEqual([method for method, _thread_id in calls], ["start_combat"])

            configure_debug_trace(False)
            entries = [json.loads(line) for line in Path(trace_path).read_text(encoding="utf-8").splitlines() if line]
            expected_spans = {
                "dm.combat.command.threadpool_dispatch_queue",
                "dm.combat.command.worker_wait",
                "runtime.command.queue_wait",
                "runtime.command.execute",
                "combat.mutation.service_call",
                "combat.mutation.response_snapshot",
                "lan.broadcast.schedule",
                "dm.broadcast.schedule",
                "dm.combat.command.worker_return",
                "dm.combat.command.route_resume",
            }
            self.assertTrue(expected_spans.issubset({entry.get("span") for entry in entries}))
            correlated = [entry for entry in entries if entry.get("span") in expected_spans]
            self.assertTrue(correlated)
            self.assertEqual({entry.get("trace_id") for entry in correlated}, {"trace-http"})
            self.assertTrue(all(entry.get("command") == COMMAND_COMBAT_START for entry in correlated))
            self.assertTrue(all(entry.get("route") == "/api/dm/combat/start" for entry in correlated))
            self.assertTrue(all(entry.get("method") == "POST" for entry in correlated))
            self.assertTrue(all(entry.get("parent_action_id") == "request-action" for entry in correlated))
            self.assertTrue({entry.get("thread_role") for entry in correlated}.issuperset({"asgi", "worker", "authority"}))


def _a7_black_tan_contract_request(operation="reset-ui-workflow"):
    from dnd_initative_tracker import (
        BLACK_TAN_UI_ENEMY_IDENTITIES,
        BLACK_TAN_UI_PLAYER_IDENTITIES,
        BLACK_TAN_UI_PRECONDITION_DIGEST,
        BLACK_TAN_UI_RESET_VERSION,
        BLACK_TAN_UI_SCHEMA_VERSION,
    )

    return {
        "schema_version": BLACK_TAN_UI_SCHEMA_VERSION,
        "operation": operation,
        "reset_version": BLACK_TAN_UI_RESET_VERSION,
        "expected_precondition_digest": BLACK_TAN_UI_PRECONDITION_DIGEST,
        "players": [
            {"player_id": player_id, "name": name}
            for player_id, name in BLACK_TAN_UI_PLAYER_IDENTITIES
        ],
        "enemies": [
            {"enemy_slug": enemy_slug, "name": name}
            for enemy_slug, name in BLACK_TAN_UI_ENEMY_IDENTITIES
        ],
    }


def _a7_post_start_fixture_state():
    from types import SimpleNamespace
    from dnd_initative_tracker import (
        BLACK_TAN_UI_ENEMY_IDENTITIES,
        BLACK_TAN_UI_PLAYER_IDENTITIES,
    )

    combatants = {}
    positions = {}
    player_cid_map = {}
    enemy_cid_map = {}
    for index, (player_id, name) in enumerate(BLACK_TAN_UI_PLAYER_IDENTITIES, start=1):
        cid = 100 + index
        combatants[cid] = SimpleNamespace(
            cid=cid,
            name=name,
            is_pc=True,
            monster_slug=None,
            monster_spec=None,
        )
        positions[cid] = (index, index + 1)
        player_cid_map[player_id] = cid
    for index, (enemy_slug, name) in enumerate(BLACK_TAN_UI_ENEMY_IDENTITIES, start=1):
        cid = 200 + index
        combatants[cid] = SimpleNamespace(
            cid=cid,
            name=f"{name} 1",
            is_pc=False,
            monster_slug=None,
            monster_spec=SimpleNamespace(filename=f"Monsters/{enemy_slug}.yaml"),
        )
        positions[cid] = (20 + index, index + 2)
        enemy_cid_map[enemy_slug] = cid

    for cid, name, slug, owner_cid in (
        (301, "Owl", "owl", player_cid_map["pc:dorian"]),
        (302, "Raven", "raven", player_cid_map["pc:eldramar"]),
    ):
        combatants[cid] = SimpleNamespace(
            cid=cid,
            name=name,
            is_pc=False,
            monster_slug=None,
            monster_spec=SimpleNamespace(filename=f"Monsters/{slug}.yaml"),
            summoned_by_cid=owner_cid,
        )
        positions[cid] = (cid - 300, 20)

    return {
        "combatants": combatants,
        "positions": positions,
        "in_combat": True,
        "snapshot": None,
    }, player_cid_map, enemy_cid_map


def test_a7_fixture_validation_accepts_post_start_canonical_mapping_with_summons():
    from dnd_initative_tracker import _execute_black_tan_fixture_contract

    state, expected_player_map, expected_enemy_map = _a7_post_start_fixture_state()
    status, response = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request("verify-ui-workflow"),
        debugging_enabled=True,
        reset_state=lambda: {},
        read_state=lambda: state,
    )

    assert len(state["combatants"]) == 21
    assert status == 200
    assert response["mutated"] is False
    assert response["player_count"] == 10
    assert response["enemy_count"] == 9
    assert response["combatant_count"] == 19
    assert response["player_cid_map"] == expected_player_map
    assert response["enemy_cid_map"] == expected_enemy_map
    assert 301 not in response["player_cids"] + response["enemy_cids"]
    assert 302 not in response["player_cids"] + response["enemy_cids"]


def test_a7_fixture_validation_rejects_missing_canonical_enemy():
    from dnd_initative_tracker import _execute_black_tan_fixture_contract

    state, _player_map, enemy_map = _a7_post_start_fixture_state()
    missing_cid = enemy_map["black-and-tan-suppression-gunner"]
    state["combatants"].pop(missing_cid)
    state["positions"].pop(missing_cid)
    status, response = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request("verify-ui-workflow"),
        debugging_enabled=True,
        reset_state=lambda: {},
        read_state=lambda: state,
    )

    assert status == 409
    assert response["error"] == "ui_setup_mismatch"
    assert response["mutated"] is False
    assert response["actual_counts"] == {
        "player_count": 10,
        "enemy_count": 8,
        "combatant_count": 18,
    }
    assert any(
        detail["field"] == "enemy:black-and-tan-suppression-gunner"
        for detail in response["mismatch_details"]
    )


def test_a7_fixture_validation_rejects_incorrect_canonical_enemy_mapping():
    from types import SimpleNamespace
    from dnd_initative_tracker import _execute_black_tan_fixture_contract

    state, _player_map, enemy_map = _a7_post_start_fixture_state()
    captain = state["combatants"][enemy_map["black-and-tan-captain"]]
    captain.monster_spec = SimpleNamespace(filename="Monsters/black-and-tan-constable.yaml")
    status, response = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request("verify-ui-workflow"),
        debugging_enabled=True,
        reset_state=lambda: {},
        read_state=lambda: state,
    )

    assert status == 409
    assert response["error"] == "ui_setup_mismatch"
    assert response["mutated"] is False
    assert response["actual_counts"] == response["expected_counts"]
    mismatch_fields = {detail["field"] for detail in response["mismatch_details"]}
    assert "enemy:black-and-tan-captain" in mismatch_fields
    assert "enemy:black-and-tan-constable" in mismatch_fields


def test_black_tan_fixture_contract_success_is_versioned_and_stable():
    from dnd_initative_tracker import (
        BLACK_TAN_UI_PRECONDITION_DIGEST,
        _black_tan_fixture_contract_mode,
        _execute_black_tan_fixture_contract,
    )

    calls = []

    def reset_state():
        calls.append("reset")
        return {"snapshot": {"combatants": [], "grid": {"cols": 30, "rows": 30}}}

    def read_state():
        calls.append("read")
        return {}

    status, response = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request(),
        debugging_enabled=True,
        reset_state=reset_state,
        read_state=read_state,
    )

    assert status == 200
    assert calls == ["reset"]
    assert BLACK_TAN_UI_PRECONDITION_DIGEST == (
        "sha256:67668370769a7a7f81c820550d4a10033bde8e297b2da1d05d55819cade90873"
    )
    assert response["schema_version"] == "a7-ui-reset-contract/v1"
    assert response["reset_version"] == "blank-combat/v1"
    assert response["precondition_digest"] == BLACK_TAN_UI_PRECONDITION_DIGEST
    assert response["operation"] == "reset-ui-workflow"
    assert response["mutated"] is True
    assert response["player_count"] == response["enemy_count"] == response["combatant_count"] == 0
    assert response["player_cids"] == response["enemy_cids"] == []
    assert response["player_cid_map"] == response["enemy_cid_map"] == {}
    assert response["in_combat"] is False
    assert response["fixture_id"] == "black-tan-combat-exploration"
    assert response["dmcontrol_url"] == "/dmcontrol"
    assert len(response["player_names"]) == 10
    assert len(response["monster_names"]) == 9
    assert response["snapshot"]["grid"] == {"cols": 30, "rows": 30}
    assert _black_tan_fixture_contract_mode(None) == "legacy"

    status, refusal = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request(),
        debugging_enabled=False,
        reset_state=reset_state,
        read_state=read_state,
    )
    assert status == 403
    assert refusal == {"detail": "Debugging mode is not enabled.", "mutated": False}
    assert calls == ["reset"]


def test_black_tan_fixture_contract_precondition_mismatch_returns_409_without_mutation():
    from dnd_initative_tracker import (
        BLACK_TAN_UI_PRECONDITION_DIGEST,
        _execute_black_tan_fixture_contract,
    )

    base_request = _a7_black_tan_contract_request()
    mismatched_requests = []
    for field, value in (
        ("schema_version", "a7-ui-reset-contract/v0"),
        ("reset_version", "blank-combat/v0"),
        ("expected_precondition_digest", "sha256:" + "0" * 64),
    ):
        request = dict(base_request)
        request[field] = value
        mismatched_requests.append(request)
    identity_mismatch = dict(base_request)
    identity_mismatch["players"] = list(reversed(base_request["players"]))
    mismatched_requests.append(identity_mismatch)

    mutator_calls = []
    reader_calls = []
    for request in mismatched_requests:
        status, response = _execute_black_tan_fixture_contract(
            request,
            debugging_enabled=True,
            reset_state=lambda: mutator_calls.append("reset") or {},
            read_state=lambda: reader_calls.append("read") or {},
        )
        assert status == 409
        assert response["ok"] is False
        assert response["error"] == "precondition_mismatch"
        assert response["mutated"] is False
        assert response["actual_precondition_digest"] == BLACK_TAN_UI_PRECONDITION_DIGEST
        assert response["expected_schema_version"] == "a7-ui-reset-contract/v1"
        assert response["expected_reset_version"] == "blank-combat/v1"
        assert 1 <= len(response["mismatch_details"]) <= 6

    assert mutator_calls == []
    assert reader_calls == []


def test_black_tan_fixture_contract_returns_complete_stable_identity_mappings():
    from types import SimpleNamespace
    from dnd_initative_tracker import (
        BLACK_TAN_UI_ENEMY_IDENTITIES,
        BLACK_TAN_UI_PLAYER_IDENTITIES,
        BLACK_TAN_UI_PRECONDITION_DIGEST,
        _execute_black_tan_fixture_contract,
    )

    combatants = {}
    positions = {}
    expected_player_map = {}
    expected_enemy_map = {}
    for index, (player_id, name) in enumerate(BLACK_TAN_UI_PLAYER_IDENTITIES, start=1):
        cid = 100 + index
        combatants[cid] = SimpleNamespace(cid=cid, name=name, monster_slug="")
        positions[cid] = (index, index + 1)
        expected_player_map[player_id] = cid
    for index, (enemy_slug, name) in enumerate(BLACK_TAN_UI_ENEMY_IDENTITIES, start=1):
        cid = 200 + index
        combatants[cid] = SimpleNamespace(cid=cid, name=name, monster_slug=enemy_slug)
        positions[cid] = (20 + index, index + 2)
        expected_enemy_map[enemy_slug] = cid

    reset_calls = []

    def read_state():
        return {
            "combatants": combatants,
            "positions": positions,
            "in_combat": True,
            "snapshot": {"active_cid": 101},
        }

    status, response = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request("verify-ui-workflow"),
        debugging_enabled=True,
        reset_state=lambda: reset_calls.append("reset") or {},
        read_state=read_state,
    )

    assert status == 200
    assert reset_calls == []
    assert response["mutated"] is False
    assert response["precondition_digest"] == BLACK_TAN_UI_PRECONDITION_DIGEST
    assert response["player_count"] == 10
    assert response["enemy_count"] == 9
    assert response["combatant_count"] == 19
    assert response["player_cid_map"] == expected_player_map
    assert response["enemy_cid_map"] == expected_enemy_map
    assert [entry["player_id"] for entry in response["players"]] == list(expected_player_map)
    assert [entry["enemy_slug"] for entry in response["enemies"]] == list(expected_enemy_map)
    assert response["players"][0] == {
        "player_id": "pc:dorian",
        "name": "Dorian",
        "cid": 101,
        "position": {"col": 1, "row": 2},
    }
    assert response["enemies"][-1] == {
        "enemy_slug": "black-and-tan-suppression-gunner",
        "name": "Black and Tan Suppression Gunner",
        "cid": 209,
        "position": {"col": 29, "row": 11},
    }

    mismatched_positions = dict(positions)
    mismatched_positions.pop(101)
    status, refusal = _execute_black_tan_fixture_contract(
        _a7_black_tan_contract_request("verify-ui-workflow"),
        debugging_enabled=True,
        reset_state=lambda: reset_calls.append("reset") or {},
        read_state=lambda: {
            "combatants": combatants,
            "positions": mismatched_positions,
            "in_combat": True,
        },
    )
    assert status == 409
    assert refusal["error"] == "ui_setup_mismatch"
    assert refusal["mutated"] is False
    assert refusal["expected_counts"] == refusal["actual_counts"]
    assert len(refusal["mismatch_details"]) <= 8
    assert reset_calls == []


def _a7_player_turn_sync_fixture():
    import json
    from types import SimpleNamespace
    from dnd_initative_tracker import InitiativeTracker, LanController

    class CaptureWebSocket:
        def __init__(self):
            self.messages = []

        async def send_text(self, text):
            self.messages.append(json.loads(text))

    class Prompts:
        @staticmethod
        def player_visible_prompts_for_actor(_claimed_cid):
            return []

    class PlayerCommands:
        def __init__(self, tracker):
            self.tracker = tracker
            self.prompts = Prompts()
            self.end_turn_calls = []
            self.next_cid = 320

        @staticmethod
        def allow_prompt_claim_override(_msg, **_kwargs):
            return False

        def end_turn(self, **kwargs):
            self.end_turn_calls.append(dict(kwargs))
            self.tracker.current_cid = self.next_cid
            return {"ok": True, "active_cid": self.next_cid}

    tracker = InitiativeTracker.__new__(InitiativeTracker)
    controller = LanController.__new__(LanController)
    controller._tracker = tracker
    tracker._lan = controller
    tracker._lan_combat_snapshot_version = 0
    tracker._combat_mutation_trace_fields = {}
    tracker._oplog = lambda *_args, **_kwargs: None
    tracker._is_admin_token_valid = lambda _token: False
    tracker._summon_can_be_controlled_by = lambda _claimed, _cid: False
    tracker._is_valid_summon_turn_for_controller = (
        lambda claimed, cid, current: claimed == cid == current
    )
    tracker.combatants = {
        322: SimpleNamespace(cid=322, name="Malagrou"),
        320: SimpleNamespace(cid=320, name="John Twilight"),
    }
    tracker.current_cid = 322
    tracker.in_combat = True
    commands = PlayerCommands(tracker)
    tracker._player_commands = commands

    sockets = {1001: CaptureWebSocket(), 1002: CaptureWebSocket()}
    controller._clients_lock = threading.RLock()
    controller._clients = dict(sockets)
    controller._dm_ws_clients = {}
    controller._view_only_clients = set()
    controller._ws_send_locks = {}
    controller._clients_meta = {}
    controller._client_hosts = {1001: "malagrou.test", 1002: "john.test"}
    controller._claims = {1001: 322, 1002: 320}
    controller._cid_to_ws = {322: {1001}, 320: {1002}}
    controller._cid_to_host = {322: {"malagrou.test"}, 320: {"john.test"}}
    controller._client_ids = {1001: "malagrou-client", 1002: "john-client"}
    controller._client_id_to_ws = {
        "malagrou-client": {1001},
        "john-client": {1002},
    }
    controller._client_id_claims = {
        "malagrou-client": 322,
        "john-client": 320,
    }
    controller._client_claim_revs = {
        "malagrou-client": 4,
        "john-client": 7,
    }
    controller._ws_claim_revs = {1001: 4, 1002: 7}
    controller._cached_pcs = [
        {"cid": 322, "name": "Malagrou"},
        {"cid": 320, "name": "John Twilight"},
    ]
    controller._cached_snapshot = {
        "active_cid": 322,
        "round_num": 1,
        "turn_order": [322, 320],
        "player_profiles": {},
        "units": [
            {"cid": 322, "name": "Malagrou"},
            {"cid": 320, "name": "John Twilight"},
        ],
    }
    controller._log_lan_exception = lambda *_args, **_kwargs: None
    controller._append_lan_log = lambda *_args, **_kwargs: None
    toasts = []
    controller.toast = lambda ws_id, text: toasts.append((ws_id, text))
    return tracker, controller, sockets, commands, toasts


def _a7_broadcast_player_state(controller, snapshot, combat_version):
    async def broadcast():
        controller._ws_send_locks = {
            ws_id: asyncio.Lock() for ws_id in controller._clients
        }
        await controller._broadcast_state_async(
            snapshot,
            combat_version=combat_version,
        )

    asyncio.run(broadcast())


def _a7_broadcast_player_payload(controller, payload):
    async def broadcast():
        controller._ws_send_locks = {
            ws_id: asyncio.Lock() for ws_id in controller._clients
        }
        await controller._broadcast_payload_async(payload)

    asyncio.run(broadcast())


def _a7_reduce_player_messages(messages, *, initial_state, claimed_cid, last_version=None):
    import json
    from pathlib import Path
    import subprocess

    html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")
    start_marker = "// A7_COMBAT_STATE_REDUCER_START"
    end_marker = "// A7_COMBAT_STATE_REDUCER_END"
    start = html.index(start_marker) + len(start_marker)
    end = html.index(end_marker, start)
    reducer_source = html[start:end]
    script = f"""
const fs = require("fs");
{reducer_source}
const input = JSON.parse(fs.readFileSync(0, "utf8"));
let state = input.initial_state;
let version = input.last_version;
const applied = [];
for (const message of input.messages) {{
  const result = reduceCombatStateEnvelope(state, message, version);
  applied.push(result.applied);
  state = result.state;
  version = result.version;
}}
const activeCid = state && state.active_cid !== undefined ? Number(state.active_cid) : null;
const claimedCid = Number(input.claimed_cid);
process.stdout.write(JSON.stringify({{
  state,
  version,
  applied,
  end_turn_disabled: activeCid === null || activeCid !== claimedCid,
}}));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(
            {
                "messages": messages,
                "initial_state": initial_state,
                "claimed_cid": claimed_cid,
                "last_version": last_version,
            }
        ),
        text=True,
        capture_output=True,
        check=True,
        timeout=5,
    )
    return json.loads(completed.stdout)


def _a7_later_turn_fanout_fixture():
    from types import SimpleNamespace

    tracker, controller, original_sockets, commands, toasts = _a7_player_turn_sync_fixture()
    socket_type = type(next(iter(original_sockets.values())))
    sockets = {
        2001: socket_type(),
        2002: socket_type(),
        2003: socket_type(),
    }
    actors = [
        {"cid": 21, "name": "Suppression Gunner", "role": "enemy"},
        {"cid": 10, "name": "Vicnor", "role": "pc"},
        {"cid": 13, "name": "Captain", "role": "enemy"},
        {"cid": 9, "name": "Throat Goat", "role": "pc"},
        {"cid": 4, "name": "Fred", "role": "pc"},
        {"cid": 18, "name": "Rifleman", "role": "enemy"},
        {"cid": 2, "name": "Eldramar", "role": "pc"},
        {"cid": 3, "name": "Owl", "role": "ally", "summoned_by_cid": 2},
    ]
    turn_order = [actor["cid"] for actor in actors]

    tracker.combatants = {
        actor["cid"]: SimpleNamespace(**actor) for actor in actors
    }
    tracker.current_cid = 9
    tracker.in_combat = True
    tracker._lan_combat_snapshot_version = 10
    tracker._player_profiles_payload = lambda: {}
    tracker.__dict__.pop("_combat_mutation_trace_fields", None)
    commands.next_cid = 4
    commands.end_turn_calls.clear()

    controller._clients = dict(sockets)
    controller._dm_ws_clients = {}
    controller._view_only_clients = set()
    controller._ws_send_locks = {}
    controller._clients_meta = {}
    controller._client_hosts = {
        2001: "vicnor.test",
        2002: "throat-goat.test",
        2003: "fred.test",
    }
    controller._claims = {2001: 10, 2002: 9, 2003: 4}
    controller._cid_to_ws = {10: {2001}, 9: {2002}, 4: {2003}}
    controller._cid_to_host = {
        10: {"vicnor.test"},
        9: {"throat-goat.test"},
        4: {"fred.test"},
    }
    controller._client_ids = {
        2001: "vicnor-client",
        2002: "throat-goat-client",
        2003: "fred-client",
    }
    controller._client_id_to_ws = {
        "vicnor-client": {2001},
        "throat-goat-client": {2002},
        "fred-client": {2003},
    }
    controller._client_id_claims = {
        "vicnor-client": 10,
        "throat-goat-client": 9,
        "fred-client": 4,
    }
    controller._client_claim_revs = {
        "vicnor-client": 5,
        "throat-goat-client": 8,
        "fred-client": 13,
    }
    controller._ws_claim_revs = {2001: 5, 2002: 8, 2003: 13}
    controller._cached_pcs = [
        {"cid": 10, "name": "Vicnor"},
        {"cid": 9, "name": "Throat Goat"},
        {"cid": 4, "name": "Fred"},
        {"cid": 2, "name": "Eldramar"},
    ]
    controller._cached_snapshot = {
        "active_cid": 21,
        "round_num": 1,
        "turn_order": turn_order,
        "units": actors,
    }
    controller._last_snapshot = dict(controller._cached_snapshot)
    controller._loop = None

    return tracker, controller, sockets, commands, toasts


def _a7_later_turn_snapshot(controller, active_cid):
    import copy

    return {
        "active_cid": active_cid,
        "round_num": 1,
        "turn_order": list(controller._cached_snapshot["turn_order"]),
        "units": copy.deepcopy(controller._cached_snapshot["units"]),
    }


def _a7_run_scheduled_state_fanout(controller, callbacks):
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    def run_loop():
        asyncio.set_event_loop(loop)
        ready.set()
        loop.run_forever()

    thread = threading.Thread(target=run_loop, name="a7-fanout-loop")
    thread.start()
    assert ready.wait(timeout=2)
    controller._loop = loop

    async def initialize_send_locks():
        controller._ws_send_locks = {
            ws_id: asyncio.Lock() for ws_id in controller._clients
        }

    async def wait_for_message_count(expected):
        for _ in range(200):
            if all(len(ws.messages) >= expected for ws in controller._clients.values()):
                return
            await asyncio.sleep(0.005)
        raise AssertionError(f"fanout did not reach every client at message {expected}")

    try:
        asyncio.run_coroutine_threadsafe(initialize_send_locks(), loop).result(timeout=2)
        for expected, callback in enumerate(callbacks, start=1):
            callback()
            asyncio.run_coroutine_threadsafe(
                wait_for_message_count(expected), loop
            ).result(timeout=3)
    finally:
        controller._loop = None
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=10)
        assert not thread.is_alive()
        loop.close()


def _a7_force_snapshot_callbacks(tracker, controller, snapshots):
    import copy

    pcs = copy.deepcopy(controller._cached_pcs)
    tracker._lan_static_snapshot_cache_status = lambda: (True, "", 1)
    tracker._lan_merge_cached_static_snapshot = lambda snap: (snap, True)
    tracker._lan_pcs = lambda: copy.deepcopy(pcs)
    tracker._debug_trace_counts = lambda: {
        "combatant_count": len(tracker.combatants),
        "player_count": len(pcs),
        "monster_count": len(tracker.combatants) - len(pcs),
        "map_aoe_count": 0,
        "pending_prompt_count": 0,
        "pending_reaction_count": 0,
        "websocket_client_count": len(controller._clients),
        "dm_websocket_client_count": 0,
        "total_websocket_client_count": len(controller._clients),
    }

    callbacks = []
    for snapshot in snapshots:
        captured = copy.deepcopy(snapshot)

        def force_state(captured=captured):
            tracker._lan_snapshot = lambda **_kwargs: copy.deepcopy(captured)
            tracker._lan_force_state_broadcast()

        callbacks.append(force_state)
    return callbacks


def test_a7_later_turn_fanout_updates_all_connected_claimed_players():
    tracker, controller, sockets, commands, _toasts = _a7_later_turn_fanout_fixture()
    earlier_snapshots = [
        _a7_later_turn_snapshot(controller, cid) for cid in (21, 10, 13, 9)
    ]
    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 9, "_claimed_cid": 9, "_ws_id": 2002}
    )
    assert tracker.current_cid == 4
    assert len(commands.end_turn_calls) == 1
    authoritative = _a7_later_turn_snapshot(controller, 4)

    callbacks = _a7_force_snapshot_callbacks(
        tracker, controller, [*earlier_snapshots, authoritative]
    )
    _a7_run_scheduled_state_fanout(controller, callbacks)

    for socket in sockets.values():
        assert [message["combat_version"] for message in socket.messages] == [11, 12, 13, 14, 15]
        assert [message["state"]["active_cid"] for message in socket.messages] == [21, 10, 13, 9, 4]
    fred_client = _a7_reduce_player_messages(
        sockets[2003].messages,
        initial_state=_a7_later_turn_snapshot(controller, 21),
        claimed_cid=4,
        last_version=10,
    )
    assert fred_client["version"] == 15
    assert fred_client["state"]["active_cid"] == 4
    assert fred_client["end_turn_disabled"] is False


def test_a7_personalized_fred_envelope_matches_authoritative_snapshot():
    tracker, controller, sockets, _commands, _toasts = _a7_later_turn_fanout_fixture()
    authoritative = _a7_later_turn_snapshot(controller, 4)
    controller._cached_snapshot = _a7_later_turn_snapshot(controller, 21)
    tracker._lan_combat_snapshot_version = 15

    _a7_run_scheduled_state_fanout(
        controller,
        [lambda: controller._broadcast_state(authoritative, combat_version=15)],
    )

    fred_message = sockets[2003].messages[0]
    assert fred_message["combat_version"] == 15
    assert fred_message["state"]["active_cid"] == authoritative["active_cid"] == 4
    assert fred_message["state"]["turn_order"] == authoritative["turn_order"]
    assert fred_message["you"] == {
        "claimed_cid": 4,
        "claimed_name": "Fred",
        "claim_rev": 13,
        "pending_prompts": [],
        "pending_prompt": None,
    }
    assert {
        (message.messages[0]["combat_version"], message.messages[0]["state"]["active_cid"])
        for message in sockets.values()
    } == {(15, 4)}


def test_a7_stale_personalized_envelope_cannot_regress_active_actor():
    _tracker, controller, sockets, _commands, _toasts = _a7_later_turn_fanout_fixture()
    authoritative = _a7_later_turn_snapshot(controller, 4)
    _a7_run_scheduled_state_fanout(
        controller,
        [lambda: controller._broadcast_state(authoritative, combat_version=15)],
    )
    stale = {
        "type": "state",
        "combat_version": 14,
        "state": _a7_later_turn_snapshot(controller, 21),
        "you": {"claimed_cid": 4, "claimed_name": "Fred", "claim_rev": 13},
    }
    stale_unversioned = {
        "type": "state",
        "state": _a7_later_turn_snapshot(controller, 21),
        "you": {"claimed_cid": 4, "claimed_name": "Fred", "claim_rev": 13},
    }

    reduced = _a7_reduce_player_messages(
        [sockets[2003].messages[0], stale, stale_unversioned],
        initial_state=_a7_later_turn_snapshot(controller, 21),
        claimed_cid=4,
        last_version=13,
    )
    assert reduced["applied"] == [True, False, False]
    assert reduced["version"] == 15
    assert reduced["state"]["active_cid"] == 4
    assert reduced["end_turn_disabled"] is False


def test_a7_later_turn_fanout_preserves_claim_and_command_behavior():
    tracker, controller, sockets, commands, toasts = _a7_later_turn_fanout_fixture()
    original_claims = dict(controller._claims)
    original_client_claims = dict(controller._client_id_claims)

    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 4, "_claimed_cid": 4, "_ws_id": 2003}
    )
    assert commands.end_turn_calls == []
    assert toasts == [(2003, "Not yer turn yet, matey.")]

    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 9, "_claimed_cid": 9, "_ws_id": 2002}
    )
    authoritative = _a7_later_turn_snapshot(controller, 4)
    _a7_run_scheduled_state_fanout(
        controller,
        _a7_force_snapshot_callbacks(tracker, controller, [authoritative]),
    )

    assert tracker.current_cid == 4
    assert len(commands.end_turn_calls) == 1
    assert commands.end_turn_calls[0]["claimed_cid"] == 9
    assert commands.end_turn_calls[0]["current_cid"] == 9
    assert controller._claims == original_claims
    assert controller._client_id_claims == original_client_claims
    assert controller._build_you_payload(2002)["claim_rev"] == 8
    assert controller._build_you_payload(2003)["claimed_cid"] == 4
    assert controller._build_you_payload(2003)["claim_rev"] == 13
    assert sockets[2003].messages[0]["you"]["claimed_cid"] == 4


def test_a7_later_turn_fanout_exercises_server_client_reducer_contract():
    tracker, controller, sockets, _commands, _toasts = _a7_later_turn_fanout_fixture()
    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 9, "_claimed_cid": 9, "_ws_id": 2002}
    )
    authoritative = _a7_later_turn_snapshot(controller, tracker.current_cid)
    callbacks = _a7_force_snapshot_callbacks(tracker, controller, [authoritative])

    assert "_combat_mutation_trace_fields" not in tracker.__dict__
    _a7_run_scheduled_state_fanout(controller, callbacks)

    assert tracker._lan_combat_snapshot_version == 11
    assert controller._last_snapshot["active_cid"] == 4
    assert all(len(socket.messages) == 1 for socket in sockets.values())
    fred_message = sockets[2003].messages[0]
    reduced = _a7_reduce_player_messages(
        [fred_message],
        initial_state=_a7_later_turn_snapshot(controller, 21),
        claimed_cid=4,
        last_version=10,
    )
    assert fred_message["combat_version"] == 11
    assert fred_message["state"]["active_cid"] == 4
    assert reduced["applied"] == [True]
    assert reduced["state"]["active_cid"] == 4
    assert reduced["end_turn_disabled"] is False


def test_a7_connected_claimed_player_applies_next_active_actor_after_other_player_ends_turn():
    tracker, controller, sockets, commands, _toasts = _a7_player_turn_sync_fixture()
    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 322, "_claimed_cid": 322, "_ws_id": 1001}
    )
    assert tracker.current_cid == 320
    assert commands.end_turn_calls == [
        {
            "cid": 322,
            "claimed_cid": 322,
            "current_cid": 322,
            "ws_id": 1001,
            "is_admin": False,
        }
    ]

    authoritative = {
        "active_cid": 320,
        "round_num": 1,
        "turn_order": [322, 320],
        "units": [
            {"cid": 322, "name": "Malagrou"},
            {"cid": 320, "name": "John Twilight"},
        ],
    }
    version = controller._next_combat_state_version()
    _a7_broadcast_player_state(controller, authoritative, version)

    assert all(len(socket.messages) == 1 for socket in sockets.values())
    john_message = sockets[1002].messages[0]
    malagrou_message = sockets[1001].messages[0]
    assert john_message["combat_version"] == version
    assert john_message["you"]["claimed_cid"] == 320
    assert malagrou_message["you"]["claimed_cid"] == 322

    stale_state = {
        "active_cid": 322,
        "round_num": 1,
        "turn_order": [322, 320],
        "units": authoritative["units"],
    }
    john_client = _a7_reduce_player_messages(
        [john_message], initial_state=stale_state, claimed_cid=320
    )
    malagrou_client = _a7_reduce_player_messages(
        [malagrou_message], initial_state=stale_state, claimed_cid=322
    )
    assert john_client["state"]["active_cid"] == 320
    assert john_client["end_turn_disabled"] is False
    assert malagrou_client["state"]["active_cid"] == 320
    assert malagrou_client["end_turn_disabled"] is True


def test_a7_connected_player_rejects_stale_active_actor_state():
    _tracker, controller, sockets, _commands, _toasts = _a7_player_turn_sync_fixture()
    previous = {
        "active_cid": 322,
        "round_num": 1,
        "turn_order": [322, 320],
        "units": controller._cached_snapshot["units"],
    }
    current = dict(previous, active_cid=320)
    turn_update = {
        "type": "turn_update",
        "combat_version": 9,
        **controller._build_turn_update(previous, current),
    }
    _a7_broadcast_player_payload(controller, turn_update)
    _a7_broadcast_player_state(controller, previous, combat_version=8)

    john_messages = sockets[1002].messages
    assert [message["combat_version"] for message in john_messages] == [9, 8]
    reduced = _a7_reduce_player_messages(
        john_messages,
        initial_state=previous,
        claimed_cid=320,
        last_version=7,
    )
    assert reduced["applied"] == [True, False]
    assert reduced["version"] == 9
    assert reduced["state"]["active_cid"] == 320
    assert reduced["end_turn_disabled"] is False


def test_a7_player_turn_sync_preserves_claim_and_command_behavior():
    tracker, controller, _sockets, commands, toasts = _a7_player_turn_sync_fixture()
    original_claims = dict(controller._claims)
    original_client_claims = dict(controller._client_id_claims)

    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 320, "_claimed_cid": 320, "_ws_id": 1002}
    )
    assert commands.end_turn_calls == []
    assert toasts == [(1002, "Not yer turn yet, matey.")]

    tracker._lan_apply_action(
        {"type": "end_turn", "cid": 322, "_claimed_cid": 322, "_ws_id": 1001}
    )
    assert len(commands.end_turn_calls) == 1
    assert commands.end_turn_calls[0]["claimed_cid"] == 322
    assert commands.end_turn_calls[0]["current_cid"] == 322
    assert controller._claims == original_claims
    assert controller._client_id_claims == original_client_claims
    assert controller._build_you_payload(1001)["claimed_cid"] == 322
    assert controller._build_you_payload(1001)["claim_rev"] == 4
    assert controller._build_you_payload(1002)["claimed_cid"] == 320
    assert controller._build_you_payload(1002)["claim_rev"] == 7


def _a7_authoritative_summon_turn_fixture(
    *,
    order=(32, 33, 34),
    summon_cid=33,
    summon_name="Raven",
    capture_broadcast=True,
    tracker=None,
    lan=None,
):
    from types import SimpleNamespace
    from dnd_initative_tracker import InitiativeTracker

    class CaptureLan:
        def __init__(self):
            self.toasts = []
            self.broadcasts = []

        def _append_lan_log(self, *_args, **_kwargs):
            return None

        def toast(self, ws_id, message):
            self.toasts.append((ws_id, message))

    if tracker is None:
        tracker = InitiativeTracker.__new__(InitiativeTracker)
    if lan is None:
        lan = CaptureLan()

    names = {
        10: "First",
        20: "Middle",
        30: "Last",
        32: "Stikhiya",
        33: "Raven",
        34: "Black and Tan Captain",
        43: "Owl",
    }
    combatants = {}
    for index, cid in enumerate(order):
        is_summon = int(cid) == int(summon_cid)
        combatants[int(cid)] = SimpleNamespace(
            cid=int(cid),
            name=summon_name if is_summon else names.get(int(cid), f"Actor {cid}"),
            is_pc=not is_summon,
            initiative=100 - index,
            nat20=False,
            dex=10,
            hp=10,
            max_hp=10,
            condition_stacks=[],
            summoned_by_cid=99 if is_summon else None,
            turn_schedule_mode="normal",
            mounted_by_cid=None,
            mount_shared_turn=False,
        )

    tracker.combatants = combatants
    tracker.current_cid = int(order[0])
    tracker.start_cid = int(order[0])
    tracker.round_num = 1
    tracker.turn_num = 1
    tracker.in_combat = True
    tracker._current_turn_kind = "normal"
    tracker._normal_turns_completed = 0
    tracker._cadence_counters = {}
    tracker._cadence_pending_queue = []
    tracker._cadence_resume_normal_cid = None
    tracker._turn_history = []
    tracker._monster_sequence_state = {}
    tracker._monster_modifier_state = {}
    tracker._monster_resource_state = {}
    tracker._lan_aoes = {}
    tracker._pending_reaction_offers = {}
    tracker._name_role_memory = {
        str(actor.name): ("pc" if actor.is_pc else "ally")
        for actor in combatants.values()
    }
    tracker._lan = lan
    tracker._dm_service = None
    tracker._lan_combat_snapshot_version = 40
    tracker.__dict__.pop("_player_commands", None)

    order_ids = [int(cid) for cid in order]
    tracker._display_order = lambda: [
        tracker.combatants[cid] for cid in order_ids if cid in tracker.combatants
    ]
    tracker._expire_reaction_offers = lambda force=False: None
    tracker._log = lambda *_args, **_kwargs: None
    tracker._end_turn_cleanup = lambda *_args, **_kwargs: None
    tracker._log_turn_end = lambda *_args, **_kwargs: None
    tracker._log_turn_start = lambda *_args, **_kwargs: None
    tracker._enter_turn_with_auto_skip = (
        lambda starting=False: tracker.__dict__.setdefault("_a7_started_cids", []).append(
            tracker.current_cid
        )
    )
    tracker._rebuild_table = lambda *_args, **_kwargs: None
    tracker._claimed_cids_snapshot = lambda: {32, 99}
    tracker._should_show_dm_up_alert = lambda *_args, **_kwargs: False
    tracker._tick_polymorph_durations = lambda: None
    tracker._oplog = lambda *_args, **_kwargs: None
    tracker._is_admin_token_valid = lambda _token: False

    def snapshot():
        ordered = tracker._display_order()
        return {
            "active_cid": tracker.current_cid,
            "round_num": tracker.round_num,
            "turn_order": [actor.cid for actor in ordered],
            "units": [
                {
                    "cid": actor.cid,
                    "name": actor.name,
                    "role": "pc" if actor.is_pc else "ally",
                    "summoned_by_cid": actor.summoned_by_cid,
                }
                for actor in ordered
            ],
        }

    if capture_broadcast:
        def force_broadcast(*_args, **_kwargs):
            tracker._lan_combat_snapshot_version += 1
            lan.broadcasts.append(
                {
                    "combat_version": tracker._lan_combat_snapshot_version,
                    "state": snapshot(),
                }
            )

        tracker._lan_force_state_broadcast = force_broadcast

    return tracker, lan, snapshot


def _a7_end_authoritative_player_turn(tracker, *, cid, claimed_cid=None, ws_id=7001):
    tracker._lan_apply_action(
        {
            "type": "end_turn",
            "cid": int(cid),
            "_claimed_cid": int(cid if claimed_cid is None else claimed_cid),
            "_ws_id": ws_id,
        }
    )


def test_a7_player_end_turn_advances_to_living_raven_in_authoritative_order():
    tracker, lan, _snapshot = _a7_authoritative_summon_turn_fixture()

    _a7_end_authoritative_player_turn(tracker, cid=32)

    assert tracker.current_cid == 33
    assert tracker.turn_num == 2
    assert tracker.round_num == 1
    assert tracker.combatants[33].summoned_by_cid == 99
    assert lan.broadcasts[-1]["state"]["active_cid"] == 33
    assert lan.broadcasts[-1]["state"]["turn_order"] == [32, 33, 34]


def test_a7_raven_acts_once_then_advances_to_following_actor():
    tracker, lan, _snapshot = _a7_authoritative_summon_turn_fixture()

    _a7_end_authoritative_player_turn(tracker, cid=32)
    _a7_end_authoritative_player_turn(tracker, cid=33, claimed_cid=99, ws_id=7002)

    assert tracker.__dict__["_a7_started_cids"] == [33, 34]
    assert tracker.current_cid == 34
    assert tracker.turn_num == 3
    assert tracker.round_num == 1
    assert [entry["state"]["active_cid"] for entry in lan.broadcasts] == [33, 34]


def test_a7_player_end_turn_advances_to_living_owl_in_authoritative_order():
    tracker, lan, _snapshot = _a7_authoritative_summon_turn_fixture(
        order=(32, 43, 34),
        summon_cid=43,
        summon_name="Owl",
    )

    _a7_end_authoritative_player_turn(tracker, cid=32)

    assert tracker.current_cid == 43
    assert tracker.combatants[43].name == "Owl"
    assert tracker.combatants[43].summoned_by_cid == 99
    assert lan.broadcasts[-1]["state"]["active_cid"] == 43


def test_a7_dead_or_removed_summon_remains_ineligible_for_turn():
    tracker, lan, _snapshot = _a7_authoritative_summon_turn_fixture()
    dead_raven = tracker.combatants[33]
    dead_raven.hp = 0
    tracker.combatants.pop(33)

    _a7_end_authoritative_player_turn(tracker, cid=32)

    assert dead_raven.hp == 0
    assert 33 not in tracker.combatants
    assert tracker.current_cid == 34
    assert lan.broadcasts[-1]["state"]["turn_order"] == [32, 34]


def test_a7_non_summon_advancement_and_round_wrap_remain_authoritative():
    tracker, lan, _snapshot = _a7_authoritative_summon_turn_fixture(
        order=(10, 20, 30),
        summon_cid=-1,
    )
    tracker.current_cid = 20
    tracker.start_cid = 10

    _a7_end_authoritative_player_turn(tracker, cid=20)
    _a7_end_authoritative_player_turn(tracker, cid=30, ws_id=7002)

    assert [entry["state"]["active_cid"] for entry in lan.broadcasts] == [30, 10]
    assert tracker.current_cid == 10
    assert tracker.turn_num == 3
    assert tracker.round_num == 2


def test_a7_summon_advancement_preserves_snapshot_version_and_fanout():
    tracker, controller, sockets, _commands, _toasts = _a7_player_turn_sync_fixture()
    tracker, controller, snapshot = _a7_authoritative_summon_turn_fixture(
        tracker=tracker,
        lan=controller,
        capture_broadcast=False,
    )

    controller._claims = {1001: 32, 1002: 34}
    controller._cid_to_ws = {32: {1001}, 34: {1002}}
    controller._cid_to_host = {32: {"stikhiya.test"}, 34: {"captain.test"}}
    controller._client_id_claims = {"stikhiya-client": 32, "captain-client": 34}
    controller._client_id_to_ws = {"stikhiya-client": {1001}, "captain-client": {1002}}
    controller._client_ids = {1001: "stikhiya-client", 1002: "captain-client"}
    controller._client_hosts = {1001: "stikhiya.test", 1002: "captain.test"}
    controller._client_claim_revs = {"stikhiya-client": 4, "captain-client": 7}
    controller._ws_claim_revs = {1001: 4, 1002: 7}
    controller._cached_pcs = [
        {"cid": 32, "name": "Stikhiya"},
        {"cid": 34, "name": "Black and Tan Captain"},
    ]
    controller._cached_snapshot = snapshot()
    controller._last_snapshot = snapshot()
    controller._dynamic_snapshot_payload = lambda snap: dict(snap)
    controller._pcs_payload = lambda: list(controller._cached_pcs)
    controller._build_you_payload = lambda ws_id: {
        "claimed_cid": controller._claims.get(ws_id),
        "claimed_name": (
            "Stikhiya" if controller._claims.get(ws_id) == 32
            else "Black and Tan Captain"
        ),
        "claim_rev": controller._ws_claim_revs.get(ws_id, 0),
        "pending_prompts": [],
        "pending_prompt": None,
    }
    tracker._lan_static_snapshot_cache_status = lambda: (True, "cached", 1)
    tracker._lan_merge_cached_static_snapshot = lambda snap: (snap, True)
    tracker._lan_pcs = lambda: list(controller._cached_pcs)
    tracker._lan_snapshot = lambda **_kwargs: snapshot()
    tracker._debug_trace_counts = lambda: {
        "combatant_count": 3,
        "player_count": 2,
        "monster_count": 1,
        "map_aoe_count": 0,
        "pending_prompt_count": 0,
        "pending_reaction_count": 0,
        "websocket_client_count": 2,
        "dm_websocket_client_count": 0,
        "total_websocket_client_count": 2,
    }

    _a7_run_scheduled_state_fanout(
        controller,
        [lambda: _a7_end_authoritative_player_turn(tracker, cid=32)],
    )

    assert tracker.current_cid == 33
    assert tracker._lan_combat_snapshot_version == 41
    assert controller._cached_snapshot["active_cid"] == 33
    assert controller._cached_snapshot["turn_order"] == [32, 33, 34]
    for socket in sockets.values():
        assert len(socket.messages) == 1
        assert socket.messages[0]["combat_version"] == 41
        assert socket.messages[0]["state"]["active_cid"] == 33
        assert socket.messages[0]["state"]["turn_order"] == [32, 33, 34]

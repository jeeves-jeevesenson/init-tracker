#!/usr/bin/env python3
from __future__ import annotations

import copy
import contextlib
import json
import socket
import threading
import urllib.parse
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
SPELLBOOK_SAVE_LIST_KEYS = (
    "known_list",
    "known_free_list",
    "prepared_list",
    "prepared_free_list",
    "cantrips_list",
    "cantrips_free_list",
)


class LanRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/lan":
            # Serve the LAN page with placeholder replaced
            file_path = REPO_ROOT / "assets/web/lan/index.html"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                # Replace the placeholder values with undefined for the smoke test
                content = content.replace(b"__LAN_BASE_URL__", b"undefined")
                content = content.replace(b"__PUSH_PUBLIC_KEY__", b"undefined")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception:
                pass  # Fall through to default handler
        self.path = path if path else "/"
        return super().do_GET()


def _find_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_server() -> tuple[ThreadingHTTPServer, int]:
    port = _find_open_port()
    handler = partial(LanRequestHandler, directory=str(REPO_ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _normalize_slug_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_values = [value]
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = []
    result: list[str] = []
    for item in raw_values:
        slug = str(item).strip().lower()
        if slug:
            result.append(slug)
    return result


def _build_spellbook_contract(
    *,
    mode: str,
    eligible_spells: list[str],
    eligible_cantrips: list[str],
) -> dict[str, object]:
    known_managed = mode == "known_and_prepared"
    prepared_left_source = "known" if known_managed else "eligible_spells"
    return {
        "version": 3,
        "mode": "known_and_prepared" if known_managed else "prepared_only",
        "source": "lan_spellbook_test_profile",
        "known_spells_managed": known_managed,
        "prepared_spells_managed": True,
        "cantrips_managed": True,
        "limits": {
            "known": {"max": 30, "counts_free": False},
            "prepared": {"max": 30, "counts_free": False},
            "cantrips": {"max": 10, "counts_free": False},
        },
        "source_lists": {
            "eligible_spells": list(eligible_spells),
            "eligible_cantrips": list(eligible_cantrips),
        },
        "lists": {
            "known": {
                "exists": known_managed,
                "editable": known_managed,
                "owner": "known_spells.known",
                "policy": "subset_non_cantrip_spells",
                "candidate_source": "eligible_spells",
                "direct_remove": True,
            },
            "known_free": {
                "exists": known_managed,
                "editable": known_managed,
                "owner": "known_spells.free",
                "policy": "subset_of_known",
                "direct_remove": False,
            },
            "cantrips": {
                "exists": True,
                "editable": True,
                "owner": "cantrips.known",
                "policy": "cantrip_only",
                "candidate_source": "eligible_cantrips",
                "direct_remove": True,
            },
            "cantrips_free": {
                "exists": True,
                "editable": True,
                "owner": "cantrips.free",
                "policy": "subset_of_cantrips",
                "direct_remove": False,
            },
            "prepared": {
                "exists": True,
                "editable": True,
                "owner": "prepared_spells.prepared",
                "policy": "subset_non_cantrip_spells",
                "candidate_source": prepared_left_source,
                "direct_remove": True,
            },
            "prepared_free": {
                "exists": True,
                "editable": True,
                "owner": "prepared_spells.free",
                "policy": "subset_of_prepared",
                "direct_remove": False,
            },
        },
        "ui": {
            "default_mode": "known" if known_managed else "prepared",
            "tabs": {
                "known": {"visible": known_managed, "label": "Known Spells"},
                "cantrips": {"visible": True, "label": "Cantrips"},
                "prepared": {"visible": True, "label": "Prepared Spells"},
            },
            "modes": {
                "known": {
                    "left_source": "eligible_spells",
                    "left_title": "Eligible Spells",
                    "right_source": "known_paid",
                    "right_title": "Known Spells",
                    "free_source": "known_free",
                    "free_title": "Free Known",
                    "actions": {
                        "add": known_managed,
                        "add_free": known_managed,
                        "remove": known_managed,
                    },
                },
                "cantrips": {
                    "left_source": "eligible_cantrips",
                    "left_title": "Eligible Cantrips",
                    "right_source": "cantrips_paid",
                    "right_title": "Cantrips",
                    "free_source": "cantrips_free",
                    "free_title": "Free Cantrips",
                    "actions": {"add": True, "add_free": True, "remove": True},
                },
                "prepared": {
                    "left_source": prepared_left_source,
                    "left_title": "Known Spells" if known_managed else "Eligible Spells",
                    "right_source": "prepared_paid",
                    "right_title": "Prepared Spells",
                    "free_source": "prepared_free",
                    "free_title": "Free Prepared",
                    "actions": {"add": True, "add_free": True, "remove": True},
                },
            },
        },
    }


def _build_profile(
    *,
    name: str,
    class_name: str,
    mode: str,
    known_list: list[str],
    prepared_list: list[str],
    cantrips_list: list[str],
    eligible_spells: list[str],
    eligible_cantrips: list[str],
) -> dict[str, object]:
    contract = _build_spellbook_contract(
        mode=mode,
        eligible_spells=eligible_spells,
        eligible_cantrips=eligible_cantrips,
    )
    return {
        "name": name,
        "leveling": {"classes": [{"name": class_name, "level": 5}]},
        "spellcasting": {
            "known_enabled": mode == "known_and_prepared",
            "known_list": list(known_list),
            "known_free_list": [],
            "prepared_list": list(prepared_list),
            "prepared_free_list": [],
            "cantrips_list": list(cantrips_list),
            "cantrips_free_list": [],
            "spellbook_contract": contract,
        },
    }


@dataclass(frozen=True)
class SpellbookSmokeScenario:
    name: str
    profile: dict[str, object]
    claim_cid: int
    expect_mode: str
    expect_known_tab_visible: bool
    mode_for_add_remove: str
    target_slug: str
    search_term: str
    persisted_list_key: str
    forbidden_slug: str | None = None


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _spellbook_dom_snapshot(page) -> dict[str, object]:
    return page.evaluate(
        """() => {
          const collect = (id) => Array.from(
            document.querySelectorAll(`#${id} .spellbook-item[data-slug]`)
          ).map((entry) => String(entry.dataset.slug || ""));
          const isHidden = (id) => {
            const node = document.getElementById(id);
            return !node || node.classList.contains("hidden");
          };
          const saveState = document.getElementById("spellbookSaveState");
          return {
            leftSlugs: collect("spellbookLeftList"),
            rightSlugs: collect("spellbookRightList"),
            knownTabHidden: isHidden("spellbookTabKnown"),
            cantripsTabHidden: isHidden("spellbookTabCantrips"),
            preparedTabHidden: isHidden("spellbookTabPrepared"),
            saveState: saveState?.dataset?.state || "",
          };
        }"""
    )


def _install_spellbook_save_mock(context, profile: dict[str, object], saved_payloads: list[dict[str, object]]) -> None:
    profile_state = copy.deepcopy(profile)

    def _save_route(route, request) -> None:
        post_data = request.post_data
        payload = json.loads(post_data) if post_data else {}
        normalized_payload = {
            key: _normalize_slug_list(payload.get(key))
            for key in SPELLBOOK_SAVE_LIST_KEYS
        }
        saved_payloads.append(normalized_payload)

        spellcasting = profile_state.get("spellcasting")
        spellcasting_obj = spellcasting if isinstance(spellcasting, dict) else {}
        spellcasting_obj = dict(spellcasting_obj)
        for key, value in normalized_payload.items():
            spellcasting_obj[key] = value
        profile_state["spellcasting"] = spellcasting_obj

        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"ok": True, "player": profile_state}),
        )

    context.route("**/api/players/*/spellbook", _save_route)


def _run_spellbook_scenario(browser, base_url: str, scenario: SpellbookSmokeScenario) -> None:
    context = browser.new_context()
    page_errors: list[str] = []
    saved_payloads: list[dict[str, object]] = []
    _install_spellbook_save_mock(context, scenario.profile, saved_payloads)

    try:
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(f"{base_url}/lan?lanSpellbookTest=1", wait_until="domcontentloaded")
        page.wait_for_function("document.documentElement.dataset.lanBoot === 'true'", timeout=15000)
        page.wait_for_function("window.__lanSpellbookTest && typeof window.__lanSpellbookTest.claim === 'function'")
        page.evaluate("(name) => { window.__lanSpellbookTestClaimedName = name; }", scenario.name)
        profile_json = json.dumps(scenario.profile)
        profile_name = page.evaluate("(jsonText) => (JSON.parse(jsonText)?.name ?? null)", profile_json)
        _assert(
            profile_name == scenario.name,
            f"{scenario.name}: profile payload serialization mismatch (got {profile_name!r}).",
        )

        claim_ok = page.evaluate(
            "(args) => window.__lanSpellbookTest.claim(JSON.parse(args[0]), args[1])",
            [profile_json, scenario.claim_cid],
        )
        _assert(bool(claim_ok), f"{scenario.name}: claim helper returned false.")

        page.evaluate("() => window.__lanSpellbookTest.openOverlay()")
        page.wait_for_function("window.__lanSpellbookTest.overlayShown() === true")

        initial_snapshot = page.evaluate("() => window.__lanSpellbookTest.snapshot()")
        _assert(
            initial_snapshot.get("contract", {}).get("mode") == scenario.expect_mode,
            f"{scenario.name}: expected mode {scenario.expect_mode}, got {initial_snapshot.get('contract', {}).get('mode')}.",
        )
        mode_policy = (
            initial_snapshot.get("contract", {})
            .get("ui", {})
            .get("modes", {})
            .get(scenario.mode_for_add_remove, {})
        )
        _assert(
            mode_policy.get("actions", {}).get("add") is True,
            f"{scenario.name}: mode add action disabled ({mode_policy}).",
        )

        initial_dom = _spellbook_dom_snapshot(page)
        known_tab_visible = not bool(initial_dom.get("knownTabHidden"))
        _assert(
            known_tab_visible == scenario.expect_known_tab_visible,
            f"{scenario.name}: known tab visibility mismatch.",
        )

        if scenario.forbidden_slug:
            pending = initial_snapshot.get("pending", {})
            pending_values = [
                value
                for key in ("known", "known_free", "prepared", "prepared_free", "cantrips", "cantrips_free")
                for value in pending.get(key, [])
            ]
            _assert(
                scenario.forbidden_slug not in pending_values,
                f"{scenario.name}: cross-profile contamination detected for '{scenario.forbidden_slug}'.",
            )

        initial_left = list(initial_dom.get("leftSlugs", []))
        _assert(
            len(initial_left) >= 2,
            f"{scenario.name}: expected multiple left-list options before search.",
        )

        page.evaluate("(term) => window.__lanSpellbookTest.setSearch(term)", scenario.search_term)
        filtered_dom = _spellbook_dom_snapshot(page)
        filtered_left = list(filtered_dom.get("leftSlugs", []))
        _assert(
            filtered_left == [scenario.target_slug],
            f"{scenario.name}: search did not narrow to '{scenario.target_slug}' (got {filtered_left}).",
        )

        added = page.evaluate(
            "(args) => window.__lanSpellbookTest.addTo(args.mode, args.slug, false)",
            {"mode": scenario.mode_for_add_remove, "slug": scenario.target_slug},
        )
        _assert(
            scenario.target_slug in set(added.get(scenario.mode_for_add_remove, [])),
            f"{scenario.name}: add failed for '{scenario.target_slug}' (state={added}).",
        )

        removed = page.evaluate(
            "(args) => window.__lanSpellbookTest.removeFrom(args.mode, args.slug)",
            {"mode": scenario.mode_for_add_remove, "slug": scenario.target_slug},
        )
        _assert(
            scenario.target_slug not in set(removed.get(scenario.mode_for_add_remove, [])),
            f"{scenario.name}: remove failed for '{scenario.target_slug}'.",
        )

        page.evaluate(
            "(args) => window.__lanSpellbookTest.addTo(args.mode, args.slug, false)",
            {"mode": scenario.mode_for_add_remove, "slug": scenario.target_slug},
        )
        save_ok = page.evaluate("async () => window.__lanSpellbookTest.save({closeOnSuccess: false})")
        _assert(bool(save_ok), f"{scenario.name}: save returned false.")

        persisted = page.evaluate("(name) => window.__lanSpellbookTest.profileSpellcastingKeys(name)", scenario.name)
        persisted_values = set((persisted or {}).get(scenario.persisted_list_key) or [])
        _assert(
            scenario.target_slug in persisted_values,
            f"{scenario.name}: saved profile missing '{scenario.target_slug}' in '{scenario.persisted_list_key}'.",
        )
        _assert(saved_payloads, f"{scenario.name}: save request was not captured.")
        payload_values = set(saved_payloads[-1].get(scenario.persisted_list_key, []))
        _assert(
            scenario.target_slug in payload_values,
            f"{scenario.name}: save payload missing '{scenario.target_slug}' in '{scenario.persisted_list_key}'.",
        )

        final_dom = _spellbook_dom_snapshot(page)
        _assert(
            final_dom.get("saveState") == "saved",
            f"{scenario.name}: save state expected 'saved', got '{final_dom.get('saveState')}'.",
        )

        if page_errors:
            raise RuntimeError(f"{scenario.name}: page errors detected:\n" + "\n".join(page_errors))
    finally:
        context.close()


def main() -> int:
    server, port = start_server()
    with contextlib.ExitStack() as stack:
        stack.callback(server.shutdown)
        stack.callback(server.server_close)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                base_url = f"http://127.0.0.1:{port}"
                wizard_profile = _build_profile(
                    name="Wizard Smoke",
                    class_name="wizard",
                    mode="known_and_prepared",
                    known_list=["magic-missile"],
                    prepared_list=["magic-missile"],
                    cantrips_list=["fire-bolt"],
                    eligible_spells=["magic-missile", "shield", "sleep"],
                    eligible_cantrips=["fire-bolt", "light"],
                )
                cleric_profile = _build_profile(
                    name="Cleric Smoke",
                    class_name="cleric",
                    mode="prepared_only",
                    known_list=[],
                    prepared_list=["cure-wounds"],
                    cantrips_list=["guidance"],
                    eligible_spells=["cure-wounds", "bless", "healing-word"],
                    eligible_cantrips=["guidance", "sacred-flame"],
                )

                scenarios = [
                    SpellbookSmokeScenario(
                        name="Wizard Smoke",
                        profile=wizard_profile,
                        claim_cid=9101,
                        expect_mode="known_and_prepared",
                        expect_known_tab_visible=True,
                        mode_for_add_remove="known",
                        target_slug="sleep",
                        search_term="sleep",
                        persisted_list_key="known_list",
                    ),
                    SpellbookSmokeScenario(
                        name="Cleric Smoke",
                        profile=cleric_profile,
                        claim_cid=9102,
                        expect_mode="prepared_only",
                        expect_known_tab_visible=False,
                        mode_for_add_remove="prepared",
                        target_slug="bless",
                        search_term="bless",
                        persisted_list_key="prepared_list",
                        forbidden_slug="sleep",
                    ),
                ]
                for scenario in scenarios:
                    _run_spellbook_scenario(browser, base_url, scenario)
            finally:
                browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

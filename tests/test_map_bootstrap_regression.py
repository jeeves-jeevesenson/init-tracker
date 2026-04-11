import types
import unittest

import helper_script as helper_mod


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class MapBootstrapRegressionTests(unittest.TestCase):
    def _window(self):
        return object.__new__(helper_mod.BattleMapWindow)

    def test_selected_unit_cids_returns_empty_before_units_list_exists(self):
        window = self._window()
        window._units_index_to_cid = [101, 102]

        selected = helper_mod.BattleMapWindow._selected_unit_cids(window)

        self.assertEqual(selected, [])

    def test_dm_action_target_cid_falls_back_to_active_without_units_list(self):
        window = self._window()
        window._active_cid = 12
        window.app = types.SimpleNamespace(combatants={12: object()})

        cid = helper_mod.BattleMapWindow._dm_action_target_cid(window)

        self.assertEqual(cid, 12)

    def test_boarding_status_update_is_safe_before_units_list_exists(self):
        window = self._window()
        window._active_cid = None
        window.map_boarding_traversal_status_var = _Var("unset")
        window.app = types.SimpleNamespace(
            combatants={},
            _creature_boarding_context=lambda _cid: self.fail("boarding context should not be called without selected target"),
        )

        helper_mod.BattleMapWindow._update_selected_creature_boarding_status(window)

        self.assertEqual(
            window.map_boarding_traversal_status_var.get(),
            "Boarding traversal: select a creature (units list or active turn).",
        )


if __name__ == "__main__":
    unittest.main()

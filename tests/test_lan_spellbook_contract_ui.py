import unittest
from pathlib import Path


class LanSpellbookContractUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = Path("assets/web/lan/index.html").read_text(encoding="utf-8")

    def test_spellbook_config_normalizes_limits_free_lists_and_source_lists(self):
        self.assertIn(
            "function normalizeSpellbookContract(rawContract, knownEnabledFallback){",
            self.html,
        )
        self.assertIn('cantrips_free: normalizeList("cantrips_free"),', self.html)
        self.assertIn("limits: {", self.html)
        self.assertIn("source_lists: sourceLists,", self.html)
        self.assertIn("const spellbookContract = normalizeSpellbookContract(", self.html)

    def test_spellbook_ui_uses_three_contract_driven_tabs(self):
        self.assertIn('const spellbookTabCantrips = document.getElementById("spellbookTabCantrips");', self.html)
        self.assertIn("let pendingCantripFreeSet = new Set();", self.html)
        self.assertIn("function getSpellbookModePolicy(modeKey){", self.html)
        self.assertIn('spellbookTabCantrips.textContent = cantripsTab.label || "Cantrips";', self.html)
        self.assertIn('spellbookTabPrepared.textContent = preparedTab.label || "Prepared Spells";', self.html)
        self.assertIn('const preparedLeftSource = managedKnown ? "known" : "eligible_spells";', self.html)
        self.assertNotIn("spellbookKnownEnabled", self.html)

    def test_spellbook_uses_backend_source_lists_before_legacy_fallback(self):
        self.assertIn("function getSpellbookEligibleSources(profile){", self.html)
        self.assertIn(
            'const sourceLists = contract.source_lists && typeof contract.source_lists === "object" ? contract.source_lists : {};',
            self.html,
        )
        self.assertIn("return buildLegacySpellbookEligibleSources(profile);", self.html)
        self.assertIn("function buildLegacySpellbookEligibleSources(profile){", self.html)
        self.assertIn("presetMatchesSpellbookProfile(preset, classNames, subclassNames)", self.html)
        self.assertNotIn("function getEligibleSpellSlugs(profile){", self.html)

    def test_spellbook_tracks_save_state_and_warns_on_unsaved_exit(self):
        self.assertIn('const spellbookSaveState = document.getElementById("spellbookSaveState");', self.html)
        self.assertIn('let spellbookInitialSnapshotJson = "";', self.html)
        self.assertIn('let spellbookLastSavedSnapshotJson = "";', self.html)
        self.assertIn("function requestCloseSpellbookOverlay(){", self.html)
        self.assertIn('message = "changes made, not saved";', self.html)
        self.assertIn('message = "changes made, saved";', self.html)
        self.assertIn('message = "no changes made";', self.html)
        self.assertIn("saveSpellbookChanges({closeOnSuccess: true});", self.html)

    def test_spellbook_save_payload_includes_free_cantrips(self):
        self.assertIn("cantrips_free_list: Array.from(pendingCantripFreeSet),", self.html)
        self.assertIn("syncSpellbookClaimedPlayer({preserveMode: true, markSaved: true});", self.html)

    def test_spellbook_test_hook_claim_recovers_from_stale_controlled_cid(self):
        self.assertIn("window.__lanSpellbookTestClaimedName", self.html)
        self.assertIn("if (testClaimedName){", self.html)
        self.assertIn(
            'const controlledCid = normalizeCid(activeControlledUnitCid(), "lanSpellbookTest.controlledCid");',
            self.html,
        )
        self.assertIn('window.__lanSpellbookTestClaimedName = String(profile.name || "").trim();', self.html)
        self.assertIn("if (controlledCid !== null && controlledCid !== claimCid){", self.html)


if __name__ == "__main__":
    unittest.main()

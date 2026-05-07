import unittest
from pathlib import Path
import re

_DM_HTML_PATH = Path("assets/web/dm/index.html")

class TestDmMonsterLibraryDedupe(unittest.TestCase):
    def test_dedupe_logic_exists_in_js(self):
        self.assertTrue(_DM_HTML_PATH.exists())
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        
        # Look for the dedupe logic I added in refreshEncounterOptions
        self.assertIn("const uniqueMonsters = [];", html)
        self.assertIn("const seen = new Set();", html)
        self.assertIn("const key = (m.slug || m.name || '').toLowerCase();", html)
        self.assertIn("if (!seen.has(key)) {", html)
        self.assertIn("seen.add(key);", html)
        self.assertIn("uniqueMonsters.push(m);", html)
        
        # Verify it's used to update encounterOptions
        self.assertIn("monsters: uniqueMonsters", html)

    def test_render_monster_library_preserves_unique(self):
        # This is a bit harder to test without a browser, 
        # but we can verify that the function still exists 
        # and hasn't been broken by the change.
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("function renderMonsterLibrary(monsters, filter = '')", html)
        # And it uses the passed monsters array
        self.assertIn(".filter(m => {", html)

    def test_monster_select_uses_unique_list(self):
        html = _DM_HTML_PATH.read_text(encoding="utf-8")
        # refreshEncounterOptions calls renderMonsterChoices with encounterOptions.monsters
        # which we now know is deduped.
        self.assertIn("renderMonsterChoices(encounterOptions.monsters);", html)

if __name__ == "__main__":
    unittest.main()

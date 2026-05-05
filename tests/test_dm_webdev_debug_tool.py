import unittest
import json
import os
import shutil
from pathlib import Path
from scripts.dev import dm_webdev_debug

class TestDmWebdevDebugTool(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("logs/test-webdev-debug")
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_summarize_json_file(self):
        # 1. Object
        obj_path = self.test_dir / "obj.json"
        obj_path.write_text(json.dumps({"ok": True, "data": [1, 2, 3]}), encoding="utf-8")
        summary = dm_webdev_debug.summarize_json_file(obj_path)
        self.assertIn("Object with keys", summary)
        self.assertIn("ok, data", summary)

        # 2. Array
        arr_path = self.test_dir / "arr.json"
        arr_path.write_text(json.dumps([1, 2, 3, 4, 5]), encoding="utf-8")
        summary = dm_webdev_debug.summarize_json_file(arr_path)
        self.assertEqual("Array with 5 items", summary)

        # 3. Error response
        err_path = self.test_dir / "err.json"
        err_path.write_text(json.dumps({"ok": False, "detail": "Unauthorized"}), encoding="utf-8")
        summary = dm_webdev_debug.summarize_json_file(err_path)
        self.assertIn("Error response: Unauthorized", summary)

    def test_analyze_bundle_html_extraction(self):
        mock_html = """
        <html>
        <body data-dm-auth-required="False">
        <div id="authOverlay" class="hidden"></div>
        <script>
            function fetchSnapshot() { console.log('fetch'); }
            function applySnapshot() { console.log('apply'); }
            // Missing: bootstrap_MISSING
        </script>
        </body>
        </html>
        """
        summary = dm_webdev_debug.analyze_bundle(self.test_dir, mock_html, target_line=None)
        self.assertIn("False (Passwordless mode active)", summary)
        self.assertIn("authOverlay class:** hidden", summary)
        self.assertIn("Found functions:** fetchSnapshot, applySnapshot", summary)
        self.assertIn("MISSING functions:** bootstrapPasswordlessDmConsole", summary)

    def test_line_context_generation(self):
        lines = [f"Line {i+1}" for i in range(50)]
        mock_html = "\n".join(lines)
        
        target_line = 25
        summary = dm_webdev_debug.analyze_bundle(self.test_dir, mock_html, target_line=target_line)
        
        self.assertIn(f"## Line Context (around line {target_line})", summary)
        self.assertIn("   15    Line 15", summary) 
        self.assertIn("   25 -> Line 25", summary) # match code: {line_num:5}{marker}
        self.assertIn("   35    Line 35", summary)
        self.assertNotIn("   14    Line 14", summary)

if __name__ == "__main__":
    unittest.main()

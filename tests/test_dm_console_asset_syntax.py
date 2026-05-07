import unittest
import subprocess
import os
import tempfile
import re

class TestDmConsoleAssetSyntax(unittest.TestCase):
    def test_dm_index_js_syntax(self):
        self._check_html_js_syntax('assets/web/dm/index.html')

    def test_lan_index_js_syntax(self):
        self._check_html_js_syntax('assets/web/lan/index.html')

    def test_dmcontrol_index_js_syntax(self):
        self._check_html_js_syntax('assets/web/dmcontrol/index.html')

    def _check_html_js_syntax(self, html_path):
        if not os.path.exists(html_path):
            # Skip if file doesn't exist, though for assets we expect them
            return

        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract all <script>...</script> bodies that don't have a src attribute
        inline_scripts = []
        # Regex to find <script> tags and their contents
        # We look for <script ...>...</script>
        for match in re.finditer(r'<script\b([^>]*)>(.*?)</script>', content, re.DOTALL | re.IGNORECASE):
            attrs = match.group(1)
            body = match.group(2)
            # Only check if it's an inline script (no src)
            if 'src=' not in attrs.lower():
                inline_scripts.append(body)

        if not inline_scripts:
            return

        # Check if node is available
        try:
            subprocess.run(['node', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.skipTest("node not found, cannot perform syntax check")

        for i, js_content in enumerate(inline_scripts):
            if not js_content.strip():
                continue
                
            with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False, encoding='utf-8') as tf:
                tf.write(js_content)
                temp_name = tf.name
                
            try:
                # node --check verifies syntax without executing
                result = subprocess.run(['node', '--check', temp_name], capture_output=True, text=True)
                if result.returncode != 0:
                    # Try to provide context about where the error is
                    # The line numbers from node --check will refer to the temp file
                    self.fail(f"JavaScript syntax error in {html_path} (script block {i}):\n{result.stderr}")
            finally:
                if os.path.exists(temp_name):
                    os.remove(temp_name)

if __name__ == '__main__':
    unittest.main()

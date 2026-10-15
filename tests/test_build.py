"""Check source changes, download links, and reproducible release files."""

from html.parser import HTMLParser
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Downloads(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'download' in attrs and 'id' in attrs:
            self.links.append(attrs)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('build.py', 'palette.json', 'README.md', 'LICENSE'):
            shutil.copyfile(ROOT / name, self.root / name)
        shutil.copytree(ROOT / 'templates', self.root / 'templates')

    def build(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(self.root / 'build.py'), *args],
            cwd=self.root.parent, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_download_links_and_release_are_consistent(self):
        self.build()
        hosted = Downloads((self.root / 'index.html').read_text())
        standalone_path = self.root / 'dist/cosmic-latte-standalone.html'
        standalone = Downloads(standalone_path.read_text())
        self.assertEqual(len(hosted.links), 13)
        self.assertEqual(len(standalone.links), 13)
        for link, embedded in zip(hosted.links, standalone.links):
            actual = (self.root / unquote(link['href'])).read_text()
            self.assertEqual(actual, unquote(embedded['href'].split(',', 1)[1]))
            self.assertEqual(link['download'], embedded['download'])
        archive_path = next((self.root / 'dist').glob('*.zip'))
        with zipfile.ZipFile(archive_path) as archive:
            self.assertEqual(len(archive.namelist()), 16)
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read('index.html'), standalone_path.read_bytes())
            for link in hosted.links:
                self.assertEqual(archive.read(link['download']),
                                 (self.root / 'downloads' / link['download']).read_bytes())
        before = {str(path.relative_to(self.root)): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        self.build()
        self.build('--check')
        after = {str(path.relative_to(self.root)): path.read_bytes()
                 for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)

    def test_check_does_not_repair_stale_files(self):
        self.build()
        path = self.root / 'downloads/cosmic-latte.css'
        stale = path.read_bytes() + b'/* local edit */\n'
        path.write_bytes(stale)
        result = self.build('--check', success=False)
        self.assertIn('downloads/cosmic-latte.css', result.stderr)
        self.assertEqual(path.read_bytes(), stale)
        self.build()
        self.build('--check')

    def test_accent_change_reaches_all_exports_and_page(self):
        path = self.root / 'palette.json'
        source = json.loads(path.read_text())
        source['modes']['dark']['tokens']['nebula']['hex'] = '#ABCDEF'
        path.write_text(json.dumps(source))
        self.build()
        downloads = self.root / 'downloads'
        for filename in ('cosmic-latte-dark.vscode-settings.json',
                         'cosmic-latte-dark.windows-terminal.json',
                         'Cosmic Latte Dark.sublime-color-scheme',
                         'Cosmic Latte Dark', 'cosmic-latte-dark.slack.txt',
                         'cosmic-latte.css', 'cosmic-latte.json'):
            self.assertIn('#ABCDEF', (downloads / filename).read_text(), filename)
        palette = json.loads((downloads / 'cosmic-latte.json').read_text())
        self.assertEqual(palette['terminal']['dark']['ansi'][13], '#ABCDEF')
        self.assertIn('--acc:#ABCDEF;', (self.root / 'index.html').read_text())
        iterm = plistlib.loads((downloads / 'cosmic-latte-dark.itermcolors').read_bytes())
        self.assertAlmostEqual(iterm['Ansi 13 Color']['Red Component'], 171 / 255)
        self.assertAlmostEqual(iterm['Ansi 13 Color']['Green Component'], 205 / 255)
        self.assertAlmostEqual(iterm['Ansi 13 Color']['Blue Component'], 239 / 255)


if __name__ == '__main__':
    unittest.main()

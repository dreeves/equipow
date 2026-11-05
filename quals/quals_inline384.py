"""The complete 384 proof is a native disclosure in the main page.

Replicata: follow the 384 entry's complete-proof fragment and read its content.
Expectata: a closed native details element contains the entire canonical proof,
with identical words/tables, no duplicate IDs, and no accidental code buttons.
Resultata before this change: the link navigates to a separate proof384.html.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BEGIN = '<!-- proof384: begin canonical main -->'
END = '<!-- proof384: end canonical main -->'


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []

    def handle_starttag(self, tag, attributes):
        self.rows.append((tag, dict(attributes)))


def main_text():
    return (ROOT / 'proof384.html').read_text().split('<main>')[1].split('</main>')[0]


def inline_text(page):
    return page.split(BEGIN)[1].split(END)[0]


class Inline384Quals(unittest.TestCase):
    def setUp(self):
        self.page = (ROOT / 'index.html').read_text()

    def test_complete_proof_link_targets_closed_native_disclosure(self):
        self.assertTrue('href="#proof384-complete"' in self.page,
                        'The complete-proof link must target the inline body.')
        self.assertRegex(self.page, r'<details class="proof-exposition">\s*<summary>[^\n]+</summary>\s*<div class="proof-body" id="proof384-complete">')
        self.assertEqual(self.page.count(BEGIN), 1)
        self.assertEqual(self.page.count(END), 1)
        self.assertIn('href="proof384.html" download', self.page)

    def test_inline_proof_preserves_every_canonical_character(self):
        self.assertTrue(BEGIN in self.page, 'The canonical proof body is missing.')
        copied = inline_text(self.page)
        restored = copied.replace('data-proof-id="witness"', 'id="witness"').replace('data-proof-id="moment10"', 'id="moment10"')
        self.assertEqual(restored, main_text())

    def test_inline_tables_keep_ids_without_collisions_or_partition_buttons(self):
        self.assertTrue(BEGIN in self.page, 'The canonical proof body is missing.')
        all_tags = Elements()
        all_tags.feed(self.page)
        ids = Counter(a['id'] for _, a in all_tags.rows if 'id' in a)
        self.assertEqual({name: count for name, count in ids.items() if count != 1}, {})
        proof = Elements()
        proof.feed(inline_text(self.page))
        self.assertEqual([a['id'] for t, a in proof.rows if t == 'table'],
                         ['counts', 'certificates', 'reduced', 'survivors', 'last-cases'])
        self.assertEqual([a for t, a in proof.rows if t == 'code' and 'id' in a], [])
        self.assertEqual([a['data-proof-id'] for t, a in proof.rows if t == 'code' and 'data-proof-id' in a],
                         ['witness', 'moment10'])


if __name__ == '__main__':
    unittest.main()

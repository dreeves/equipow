"""The complete 384 proof is a native disclosure in the main page, and nowhere else.

Replicata: follow the 384 entry's complete-proof fragment and read its content;
open the proof's old address, proof384.html.
Expectata: a closed native details element contains the entire proof, with no
duplicate IDs and no accidental code buttons; the old address leads to it.
Resultata before the proof came inline (2026-11-05): the link navigated to a
separate proof384.html.  Resultata before 2026-11-10: the proof stood twice.

Spec change, 2026-11-10 (Claude; dreeves: "following DRY for the 384 proof is the
right thing to do, yes?"): until then proof384.html was the canonical proof and
index.html held a copy of its main element, which
test_inline_proof_preserves_every_canonical_character held equal to it,
character for character, and the page had to offer proof384.html as a download.
With one copy there is nothing to hold equal: that qual is gone, and
test_old_address_leads_to_the_proof is new.
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

    def test_old_address_leads_to_the_proof(self):
        old = (ROOT / 'proof384.html').read_text()
        self.assertIn('<meta http-equiv="refresh" content="0; url=index.html#proof384-complete">', old,
                      'proof384.html must send its reader to the proof in the main page.')
        self.assertIn('href="index.html#proof384-complete"', old)
        self.assertEqual(self.page.count('id="proof384-complete"'), 1)

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

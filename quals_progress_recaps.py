"""Replicata: inspect the run template used by the actual progress renderer.
Expectata: each recap belongs to its run's collapsible content, below its charts.
Resultata before repair: the status paragraph follows the closing details tag.
"""
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


class RunTree(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.stack, self.nodes = [], []
        self.feed(source)
        assert not self.stack

    def handle_starttag(self, tag, attrs):
        node = dict(tag=tag, attrs=dict(attrs), parents=tuple(self.stack))
        self.nodes.append(node)
        if tag not in {'br', 'img', 'input', 'hr', 'meta', 'link', 'area', 'base', 'embed', 'source', 'track', 'wbr', 'col', 'param'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack[-1]['tag'] == tag
        self.stack.pop()


class RecapQuals(unittest.TestCase):
    def setUp(self):
        self.page = Path(__file__).with_name('index.html').read_text()
        self.source = re.search(r'<template class="progress-run">(.*?)</template>', self.page, re.S).group(1)
        self.tree = RunTree(self.source)
        self.status = next(n for n in self.tree.nodes if n['attrs'].get('class') == 'progress-status')
        self.fold = next(n for n in self.tree.nodes if n['tag'] == 'details')

    def test_every_recap_is_inside_its_run_fold_and_outside_its_summary(self):
        self.assertIn(self.fold, self.status['parents'])
        self.assertFalse(any(n['tag'] == 'summary' for n in self.status['parents']))
        self.assertNotIn('open', self.fold['attrs'])
        self.assertLess(self.source.index('class="progress-eta"'), self.source.index('class="progress-status"'))

    def test_existing_status_copy_is_preserved_byte_for_byte(self):
        status = re.search(r'<p class="progress-status">.*?</p>', self.source, re.S).group(0)
        self.assertEqual(hashlib.sha256(status.encode()).hexdigest(),
                         '70587771fc2eccc718ceee43ac9cae39558905c8ff747cfeb190c8b96649bc23')

    def test_attempt_recaps_continue_to_use_the_same_folded_status_container(self):
        renderer = re.search(r'  function attemptView\(box, run, templateName, hintName\) \{.*?\n  \}', self.page, re.S).group(0)
        self.assertIn("box.querySelector('.progress-status').replaceChildren(display);", renderer)
        self.assertIn(self.fold, self.status['parents'])


if __name__ == '__main__':
    unittest.main()

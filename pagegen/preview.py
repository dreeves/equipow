#!/usr/bin/env python3
"""preview.png, the picture a shared link to the page shows (index.html's og:image): the page's title and main's figure
(BGPW's Table 2 and the tables of new results, with their legend), drawn by headless Chrome at 40% of their size.

    python3 -B pagegen/preview.py    # a few seconds; writes preview.png beside index.html

After a change to what it shows (a result in a table of new results, the legend, the title), rerun it and look at the
image: the tables and the legend must fit in its 630 pixels, or ZOOM must shrink. quals_index.q_preview_png_is_current
fails while preview.png differs from what render draws.

How: index.html, with HEARD put after <head> and STYLE and CHECK before </head>, in a directory of its own beside copies
of page/ (the page's stylesheet and scripts) and of the data files that its script tags load from pagedata/, shot by
headless Chrome (FLAGS), which also prints the page as it stood at the shot. STYLE hides all but the header's title and
main's figures. HEARD, ahead of every link and script, hears each one that fails to load (its error event; a stylesheet
from another origin shows no other sign: Chrome gives it a sheet either way, 2026-11-13), and CHECK writes on <html> what
did not load: those, a font, or the figures' math, which KaTeX draws. The page's fonts and
KaTeX come from Google Fonts and jsDelivr, so without the network the shot shows raw TeX in fallback fonts; render
asserts that everything loaded, and only then copies the shot to where it was asked to. The shot is the same pixels run
after run (2026-11-13: renders in parallel and in turn, byte for byte).

History. Until 2026-11-13 this was scratch/record-20261025/page/preview.py, which wrote a shot per zoom given and left
the copy over preview.png to its caller; it moved here so that the qual could draw with it, and gained then the copy
only after CHECK, the flags below, and STYLE's rule by structure in place of its list of sections (.remarks, .counts,
.lattice, .sets, .smallest, .oeis, .pintree, .progress, footer, .mstar and .pow2, each added when it entered the shot;
.sets was gone from the page since 2026-10-31), which drew the same pixels. Its zoom: 0.6 from 2026-10-20; 0.56 from
2026-10-25; 0.5 from 2026-10-26, when the powers of 2 took three rows; 0.44 from 2026-10-27, when the new results took
in Table 2 and reached 1024; 0.43 that night, when dreeves's note between the two tables of new results grew a line;
0.41 from 2026-10-29 (the LaTeX look's 19 px text, then the note's 46rem measure); 0.40 since 2026-10-31, when the note
had grown to five lines. Its top padding: 1.6rem until 2026-11-13, when 1.4rem moved the shot up a pixel, so that the
legend's second row keeps its bottom row of pixels (y 629 had cut its keys' lower edges). It hides #page-errors since 2026-11-12 (page/errors.js's box: the hidden m*(n) chart fails its
own assert of a width above 0, which the box would show over the shot). Twice its Chrome wrote a good shot and then
exited 2 (2026-10-27, 2026-11-03): "Teardown watchdog expired" while the display slept, for want of
--disable-backgrounding-occluded-windows (found in review, 2026-11-13), which FLAGS has."""
import sys
sys.dont_write_bytecode = True
import os, re, html, json, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository's root, above pagegen/
PREVIEW = os.path.join(ROOT, 'preview.png')
SIZE = (1200, 630)                                                   # index.html's og:image:width and og:image:height
ZOOM = '0.40'
STYLE = ('<style>header > :not(h1), main > :not(header, figure), #page-errors { display: none !important; } '
         'main { padding-block: 1.4rem 0; gap: 1.4rem; } html { zoom: %s; }</style>' % ZOOM)
HEARD = """<script>
window.previewUnloaded = [];
addEventListener('error', e => e.target === window || previewUnloaded.push(e.target.tagName + ' ' + (e.target.href || e.target.src)), true);
</script>"""
CHECK = """<script>
addEventListener('load', async () => {
  await document.fonts.ready;
  const figures = [...document.querySelectorAll('main > figure')];
  const wrong = [...previewUnloaded,
                 ...[...document.fonts].filter(f => f.status === 'error').map(f => 'font ' + f.family),
                 ...figures.flatMap((f, i) => f.querySelector('.katex') && !f.textContent.includes('\\\\(') ? [] : ['math of figure ' + i]),
                 ...(figures.length ? [] : ['no figure'])];
  document.documentElement.dataset.previewWrong = JSON.stringify(wrong);
});
</script>"""
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
# quals_index.HEADLESS's flags, in its order (its comment gives the reasons for the last two), then the shot's own
FLAGS = ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--allow-file-access-from-files',
         '--disable-backgrounding-occluded-windows', '--hide-scrollbars', f'--window-size={SIZE[0]},{SIZE[1]}', '--virtual-time-budget=8000']


def render(out):
    """Draws the preview of the page as it is into out, a PNG of SIZE, and returns out. When Chrome fails or the page did
    not load whole (CHECK), it fails and leaves out as it was."""
    page = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    data = re.findall(r'<script src="pagedata/([^"/]+)"></script>', page)
    assert page.count('<head>') == page.count('</head>') == 1 and data, ('index.html has no single <head>, or loads no data file', data)
    d = tempfile.mkdtemp(prefix='preview-')
    try:
        src, shot = os.path.join(d, 'index.html'), os.path.join(d, 'shot.png')
        open(src, 'w', encoding='utf-8').write(page.replace('<head>', '<head>' + HEARD).replace('</head>', STYLE + CHECK + '</head>'))
        shutil.copytree(os.path.join(ROOT, 'page'), os.path.join(d, 'page'))
        os.makedirs(os.path.join(d, 'pagedata'))
        for name in data: shutil.copy(os.path.join(ROOT, 'pagedata', name), os.path.join(d, 'pagedata', name))
        r = subprocess.run([CHROME, *FLAGS, f'--user-data-dir={d}/profile', f'--screenshot={shot}', '--dump-dom', 'file://' + src],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, ('Chrome failed', r.returncode, r.stderr[-2000:])
        mark = re.search(r'<html[^>]*\sdata-preview-wrong="([^"]*)"', r.stdout)
        assert mark, ('the page never ran CHECK', r.stderr[-2000:])
        wrong = json.loads(html.unescape(mark.group(1)))
        assert wrong == [], ('the page did not load whole (is the network down?)', wrong)
        assert os.path.getsize(shot) > 0, shot
        shutil.copyfile(shot, out)
    finally:
        shutil.rmtree(d)
    return out


if __name__ == '__main__':
    assert len(sys.argv) == 1, __doc__
    print('wrote', render(PREVIEW))

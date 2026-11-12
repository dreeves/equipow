// Every error the page's scripts do not catch, shown at once at the top of the window, over the page: the browser's
// message and the file it came from, rather than a part of the page silently missing (Opus 5.5, 2026-11-12; dreeves: "is
// there something simpler we can do to make it fail louder? see anti-postel in AGENTS.md", after his phone ran an old
// cached script with the new page and the Search progress section stayed empty).  Loaded first of the page's scripts,
// so that it hears every other's.  Styled here, so that it shows without the stylesheet (which may be missing, or older
// than the page); and so plain that an older copy from a cache does the same.  Its words are the browser's.
(() => {
  const box = document.documentElement.appendChild(document.createElement('div'));
  box.id = 'page-errors';
  box.setAttribute('role', 'alert');
  box.hidden = true;
  box.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; z-index: 2147483647; margin: 0; padding: 0.4rem 0.75rem; ' +
    'background: #a8283f; color: #fff; font: 13px/1.4 ui-monospace, Menlo, monospace; white-space: pre-wrap; overflow-wrap: anywhere;';
  const say = text => { box.hidden = false; box.append(text + '\n'); };
  addEventListener('error', e => say(`${e.message} (${e.filename.split('/').pop()}:${e.lineno})`));
  addEventListener('unhandledrejection', e => say(String(e.reason?.stack ?? e.reason)));
})();

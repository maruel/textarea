# textarea

A single page editor. Everything lives in `public/`, with no build step: `index.html` holds the
markup, the CSS and the script.

## Bump the service worker cache

Change `CACHE_NAME` in the same commit as **every** change to a file under `public/`. Use today's
date, `textarea-YYYY-MM-DD`. If the name already carries today's date, append a counter:
`textarea-2026-09-02-2`.

`public/sw.js` answers navigations from the cache first. A newly installed worker waits while the
page prompts the visitor to refresh; accepting activates the new worker and reloads the page. The
cache bump evicts stale assets when that update activates.

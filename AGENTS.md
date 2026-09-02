# textarea

A single page editor. Everything lives in `public/`, with no build step: `index.html` holds the
markup, the CSS and the script.

## Bump the service worker cache

Change `CACHE_NAME` in the same commit as **every** change to a file under `public/`. Use today's
date, `textarea-YYYY-MM-DD`. If the name already carries today's date, append a counter:
`textarea-2026-09-02-2`.

`public/sw.js` answers a navigation from the network and refreshes the cached page, so a change to
`index.html` reaches the visitor on their next load, bump or not. The bump is what evicts the rest:
anything listed in `ASSETS` is served from the cache first and stays stale until the name changes.

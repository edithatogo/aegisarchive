# Optional rendered capture

This adapter is an opt-in development utility. It uses a caller supplied Playwright browser, a single explicit origin, and a bounded recipe. It never reads browser profiles or executes page-authored instructions. Core AegisArchive operation has no dependency on this directory.

The recipe supports bounded scrolling, pagination and downloads. Responses and rendered derivatives are recorded separately. Authentication is limited to caller supplied storage state and must be scoped by the caller.

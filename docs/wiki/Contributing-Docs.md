# Contributing Docs

The source of truth for GitHub Wiki pages lives in `docs/wiki/`. Update those
Markdown files first, then sync them into the adjacent wiki checkout at
`../PolyFi-Ranked.wiki`.

Run a preview before writing files:

```powershell
poetry run polyfi-ranked-sync-wiki --dry-run
```

Run the sync:

```powershell
poetry run polyfi-ranked-sync-wiki
```

By default, the sync refuses to run when the wiki checkout is missing or dirty.
Use `--force` only after reviewing local wiki changes. If the wiki checkout has
Markdown pages that are no longer present in `docs/wiki/`, the script stops
instead of deleting them. After reviewing the list, pass `--prune` to delete
those unmanaged Markdown files.

Local links between Markdown pages in `docs/wiki/` are rewritten to GitHub Wiki
links during sync. Keep `Home.md` in `docs/wiki/`; GitHub uses that file as the
wiki homepage.

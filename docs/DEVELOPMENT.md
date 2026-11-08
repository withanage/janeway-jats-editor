# Development

## Layout

| File | Purpose |
|------|---------|
| `plugin_settings.py` | Janeway plugin metadata, `install()` and `hook_registry()` |
| `install/settings.json` | Per-journal settings created on install |
| `config.py` | Typed access to those settings |
| `auth.py` | Token generation, hashing and the `api_token_required` decorator |
| `urls.py` | Page and API routes |
| `api_views.py` | JSON endpoints |
| `views.py`, `forms.py`, `templates/` | Manager page, galley list, deep links |
| `hooks.py` | Template hooks |
| `logic.py` | Journal-scoped lookups and stage constants |
| `serializers.py` | Dict serializers in the OJS shape |
| `dar.py` | Document Archive builder and hardened XML parser |
| `documents.py` | Payload validation and the file write path |
| `tests/` | Django test-suite |

## Running the tests

The plugin must sit inside a Janeway checkout as `src/plugins/jats_editor`
(a symlink is fine). Janeway only mounts plugin URLs for plugins enabled in the
database when `core.include_urls` is imported, which never holds in a fresh test
database, so the tests use `tests/urls.py` as `ROOT_URLCONF`.

```bash
git clone --branch v1.8.2 https://github.com/openlibhums/janeway.git
python -m venv janeway/.venv && janeway/.venv/bin/pip install -r janeway/requirements.txt
ln -s "$PWD" janeway/src/plugins/jats_editor
JANEWAY_SRC=$PWD/janeway/src scripts/run-tests.sh
```

`scripts/run-tests.sh` passes a directory label to `manage.py test` because
`src/plugins` is a namespace package and a dotted label fails discovery.

## Linting

`ruff.toml` mirrors Janeway's own ruff settings (line length 88, double
quotes) and adds import sorting with Janeway packages as first-party.

```bash
pip install ruff          # or use: uvx ruff
scripts/lint.sh           # check only
scripts/lint.sh --fix     # apply fixes and reformat
```

CI runs the same checks in the `lint` job.

## Conventions

- Test first. Every endpoint has request-level tests in `tests/`.
- Everything that reads an article, galley or file goes through `logic.py` so it
  is scoped to `request.journal`.
- Validate the whole payload before writing anything.
- Conventional Commits.

# Janeway JATS Editor plugin

A [Janeway](https://github.com/openlibhums/janeway) plugin that exposes a small,
token-authenticated REST API so that the
[pubReady JATS XML editor](https://github.com/xmlFlow/jats-xml-editor) can open,
edit and save XML galleys and their figures. It is the Janeway counterpart of the
OJS 3.5 `xmlEditor` plugin and uses the same Document Archive (DAR) exchange
format, so the editor can talk to either system.

Tested against Janeway **v1.8.2** (Django 4.2).

## What it does

- Lists articles in production, proofing or published stages with their galleys.
- Serves an XML galley plus its images as a DAR document and accepts the edited
  document back, keeping Janeway's file history.
- Uploads, replaces and deletes galley images.
- Creates a new XML galley for an unpublished article.
- Adds an "Open in editor" link to the typesetting transform dialog for XML
  manuscript files and a "JATS Editor" entry to the editor navigation listing all
  XML galleys.
- Provides a manager page per journal to enable the API, set the editor URL, pick
  the service account that owns written files, and generate or revoke the token.

## Installation

```bash
cd /path/to/janeway/src/plugins
git clone https://github.com/withanage/janeway-jats-editor.git jats_editor
cd ..
python manage.py install_plugins jats_editor
python manage.py migrate   # no-op for this plugin, kept for completeness
# restart the application server so the plugin URLs are mounted
```

The directory name must be `jats_editor`. The plugin registers its URLs under
`/plugins/jats-editor/`.

Then, as a journal editor or manager, open **Manager → Plugins → JATS Editor
Plugin**:

1. tick *Enable*, enter the pubReady base URL, choose a service account and save;
2. click *Generate new token* and copy the token into pubReady's Janeway settings
   together with the API root shown on the page.

## Security model

- Each journal has its own token. Only its SHA-256 hash is stored; the token is
  shown once. Comparison uses `hmac.compare_digest`.
- The token is sent as `Authorization: Bearer <token>`; `?apiToken=` is accepted
  for servers that strip the header and for image URLs inside the DAR.
- Every endpoint resolves the article or galley **through the request's journal**,
  so a token can never reach another journal's data.
- Writes go through Janeway's own file helpers: the previous version of an
  overwritten file is kept as `FileHistory`, image payloads are checked with
  libmagic, client file names are reduced to a base name, and the manuscript is
  parsed with entity resolution, DTD loading and network access disabled.
- Uploads are capped per journal (`max_upload_mb`, default 25). Raise Django's
  `DATA_UPLOAD_MAX_MEMORY_SIZE` accordingly in your Janeway settings when you
  raise the limit above 2.5 MB.
- Views that render pages use Janeway's role decorators (`editor_user_required`,
  `production_user_or_editor_required`) and Django's CSRF protection.

## API

See [docs/API.md](docs/API.md) for the full endpoint reference. All endpoints
live under `/plugins/jats-editor/api/v1/` on the journal's own host or path.

## Development

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). In short:

```bash
JANEWAY_SRC=/path/to/janeway/src scripts/run-tests.sh
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

# JATS Editor API reference

Base path: `<journal site url>/plugins/jats-editor/api/v1/`. Every path ends with
a slash. Responses are JSON unless noted.

## Authentication

Send the journal's token as `Authorization: Bearer <token>` or as the query
parameter `apiToken`. Responses:

| Status | Meaning |
|--------|---------|
| 404 | The request did not resolve to a journal (press-level URL). |
| 403 | Plugin disabled for this journal, or no service account configured. |
| 401 | Missing or wrong token. |

Errors are `{"error": "<message>"}`.

## Endpoints

### `GET ping/`
`{application:"janeway", plugin:"jats_editor", version, journal:{code,name}}`

### `GET journal-metadata/`
`{success:true, metadata:{...}}`. Keys mirror the OJS plugin: `id`, `urlPath`,
`slug`, `name`, `names`, `abbreviation`, `description`, `primaryLocale`,
`supportedLocales`, `onlineIssn`, `printIssn`, `publisherInstitution`,
`publisherUrl`, `contactEmail`, `copyrightNotice`, `doiPrefix`, `journalDoi`,
`domain`, `janewayUrl`, `ojsUrl` (same value), `janewayArticlesUrl`,
`janewaySettingsUrl`, `press.name`. Missing values are `null`.

### `GET articles/?stages=&limit=&offset=`
`{itemsMax, items:[article summary]}`. `stages` is a comma-separated list of
Janeway stage identifiers (`typesetting_plugin`, `Proofing`, `pre_publication`,
`Published`, ...); the default is the typesetting, proofing, pre-publication and
published stages. `limit` defaults to 50 (max 200). Non-numeric paging values
give 400.

Article summary: `id`, `title`, `stage`, `stageName`, `datePublished`,
`dateSubmitted`, `section`, `authors[{id, givenName, familyName, fullName, email,
orcid, affiliation, order}]`, `doi`, `language`, `galleyCount`, `isPublished`,
`url`.

### `GET article/<article_id>/`
Summary plus `abstract`, `keywords[]`, `license{name,url}`, `issue{id, title,
volume, number}`, `firstPage`, `pageNumbers` and `galleys[{id, label, type,
fileId, fileName, mimeType, public, sequence, images[file]}]`.

### `GET workflow-files/<article_id>/?stages=4,5`
`{success, submissionId, files:[...]}` using OJS numbering so the editor's file
browser works unchanged: stage 4 lists manuscript files (`fileStage` 9,
"Copyediting"); stage 5 lists galley files (`fileStage` 10, "Production") and
their images (`fileStage` 17, `isDependent:true`, `parentFileId` = galley file
id). Each entry also carries `galleyId` where applicable.

### `GET workflow-files/<article_id>/<file_id>/download/`
Streams the file. 404 unless the file belongs to the article.

### `GET document/<galley_id>/`
The Document Archive:

```json
{"version": 1, "resources": {
  "fig1.png": {"encoding": "url", "data": "https://.../media/<galley>/<file>/?apiToken=..."},
  "manifest.xml": {"encoding": "utf8", "data": "<dar>...</dar>", "size": 123, "createdAt": 0, "updatedAt": 0},
  "manuscript.xml": {"encoding": "utf8", "data": "<article>...</article>", "size": 456, "createdAt": 0, "updatedAt": 0}
}}
```

415 if the galley is not XML, 422 if it is not well-formed, 404 if its file is
missing from disk.

### `PUT document/<galley_id>/`
Body:

```json
{"jatsXml": "<article>...</article>",
 "images": [{"filename": "fig1.png", "data": "data:image/png;base64,...", "mimeType": "image/png"}]}
```

The legacy body `{"resources": {"manuscript.xml": {"data": "..."}}}` is also
accepted. `data` may be a data URI or bare base64. The galley file is overwritten
in place (same id, previous version kept in `FileHistory`); images are matched by
file name and updated or created. All validation happens before any write.

Response: `{success, galleyId, fileId, submissionFileId,
dependentFiles:[{filename, submissionFileId, fileId, status:"updated"|"created"}],
historyCount}`.

Errors: 400 (empty manuscript, bad JSON, bad base64, missing file name), 413
(over the journal's upload limit), 415 (galley not XML, or an image whose bytes
are not an image), 422 (manuscript not well-formed).

### `POST media/<galley_id>/`
Body `{"media": {"fileName": "fig2.png", "data": "..."}}` or the same keys at the
top level. 201 `{success, status:"created", submissionFileId, fileId}`; an
existing image with the same name is overwritten and returns 200 with
`status:"updated"`.

### `GET media/<galley_id>/<file_id>/`
Streams the image. 404 unless the file is one of the galley's images.

### `DELETE media/<galley_id>/<file_id>/`
Detaches the image from the galley and deletes the file. `{success, deleted}`.

### `POST galley/<article_id>/`
Body `{jatsXml, images?, label?="XML", fileName?="article.xml"}`. Creates a
new XML galley with its images. 201 `{success, galleyId, fileId,
submissionFileId, dependentFiles}`. 400 if the article is already published
(edit the existing galley instead), 422 if the manuscript is not well-formed.
`locale` and `publicationId` are accepted and ignored for OJS client
compatibility.

## Deep links

`/plugins/jats-editor/open/<article_id>/galley/<galley_id>/` and
`/plugins/jats-editor/open/<article_id>/file/<file_id>/` (login required,
production or editor role) redirect to
`<editor_base_url>/janeway/open?host=<journal url>&journal=<code>&article=<id>&galley=<id>`
(or `&file=<id>`).

# Changelog

## 0.1.0 (unreleased)

- Journal-scoped API token authentication (Bearer header or `apiToken` query).
- Endpoints: `ping`, `journal-metadata`, `articles`, `article/<id>`,
  `workflow-files/<id>` (+ download), `document/<galley>` GET/PUT,
  `media/<galley>` POST, `media/<galley>/<file>` GET/DELETE, `galley/<article>` POST.
- DAR builder compatible with the OJS 3.5 xmlEditor plugin.
- Manager page with token rotation, XML galley listing and open-in-editor links.
- Template hooks `conversion_row` and `journal_editor_nav_block`.

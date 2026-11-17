# Desktop model selection

The **AI Model** group contains:

- **Model: Local / Cloud**: toggles mode, restoring that mode's saved provider/model.
- A provider/model dropdown: selects the model for the active mode.
- **Refresh Model List**: reads `pi --offline --list-models` asynchronously, with a 15-second timeout. No inference request is made.

The list is Pi's configured/available catalog, not a live server inventory. Providers with a loopback/private endpoint in Pi configuration are classified Local; others Cloud. The saved selection remains listed even if catalog discovery fails. Add providers/models and credentials through Pi's own configuration/authentication interfaces; this UI does not collect credentials or register arbitrary new providers.

Selections persist in private `config/model-router.json`. Local and Cloud each retain their own provider/model. Switching uses an exclusive lock. For the configured `neris-a` LM Studio provider, old LLMs are unloaded and their absence checked before the new model is loaded and verified. Switching to Cloud unloads local LLMs without loading another local model. Embeddings are left alone. Busy local models block switching rather than being interrupted. Selecting an already loaded sole target does not reload it. A failed load leaves the selection unchanged but the old model may already be unloaded; no automatic rollback/fallback occurs.

The desktop runs switching in a background process with controls disabled while busy; normal close waits for it to finish. Voice mode-switch commands use the same lifecycle. Configuration is saved only after successful local lifecycle operations. No model files are deleted or downloaded, and cloud credential validation is not part of switching. A catalog entry does not guarantee access, server readiness, or sufficient memory. The dashboard shows the selected model; usage is from completed matching-model requests.

Voice/text commands for switching modes continue to work. Model IDs are selected through the dropdown, not fuzzy voice matching.

## Fresh checkout setup

Copy `config/examples/model-router.json` to private `config/model-router.json` only if no private configuration already exists. Fill in actual provider/model identifiers from your Pi installation; empty example values intentionally make no inference requests. The local LM Studio lifecycle currently supports provider ID `neris-a`; register that provider in Pi before use. Online selections also use LM Studio lifecycle checks to release local models, so they require its CLI too. Credentials belong in Pi's own authentication configuration, never in the example or Git.

Desktop-only playback and the bundled robot demo do not require a configured router. Its dashboard shows Unknown until configured.

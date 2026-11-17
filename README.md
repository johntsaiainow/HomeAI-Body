# HomeAI-Body

An experimental foundation for embodied AI assistants, with future development focused on **laboratory assistants, production assistants, and bartenders**. The current working character is **Neris-A**; multi-character configuration is planned, not yet implemented.

Linux desktop avatar and voice-assistant integration: PySide6 animation states, local music, timed lyrics, shared-camera preview, gesture controls and optional Mandarin/English/Taigi services.

**Status:** basic single-machine prototype under active development. Complete laboratory, production, and bartending workflows are future goals; a portable one-command full voice distribution is not yet available. The safe installer currently bootstraps the **desktop component only**. Voice, camera, ASR/TTS and generation still need optional environments and external services; see [installation](docs/INSTALL.md).

## Project goals and development direction

The long-term goal is to develop assistants for three application areas:

- **Laboratory assistant:** support laboratory work and interactions with laboratory systems.
- **Production assistant:** support production workflows and interactions with production systems.
- **Bartender:** support bartending interactions and workflows.

This repository is the starting point for that work. Its current focus is the shared foundation: a desktop character, voice interaction, camera and gesture integration, and model selection. Application-specific workflows, tools, and hardware integrations will be developed in later stages. The project will continue to evolve through experimentation and implementation.

## Quick start

```bash
# Inspect only: does not change environments or start hardware/services.
bash scripts/install.sh --check

# On a fresh checkout: create body/.venv and install desktop dependencies.
bash scripts/install.sh --body

# Install the bundled shareable robot placeholder (refuses existing media).
python3 -B scripts/demo_assets.py

# Verify demo or privately restored assets.
python3 -B scripts/assets_manifest.py

# Desktop only, once assets and system dependencies are ready.
bash body/start.sh
```

Do not use `system.py start` as the first fresh-install test: it also attempts voice/perception startup. The installer never installs packages into `~/aion-voice`, restarts services, enrolls faces, fetches large models or enables network lyrics by default. Existing environments require explicit `--body --upgrade`; existing settings are preserved.

Desktop launchers can optionally start a local LM Studio server and load the configured model; pre-existing shared servers are preserved. See [LLM service lifecycle](docs/LLM_SERVICE.md). This integration is opt-in and does not install LM Studio.

Model selection and dashboard behavior are documented in [model selection](docs/MODEL_SELECTION.md) and [LLM dashboard](docs/LLM_DASHBOARD.md). Saved playlists, replay and gesture commands are documented in [music commands](docs/MUSIC_COMMANDS.md).

## Source layout

| Directory | Purpose |
|---|---|
| `body/` | Qt UI, playback transitions, music IPC, lyric synchronization/download |
| `voice/` | Assistant routing, ASR/TTS adapters, camera/gesture integration |
| `asr/` | Optional persistent recognition worker |
| `tts-taigi/` | Optional experimental Taigi speech integration |
| `generation/` | Reusable ComfyUI submission, collection and video processing scripts |
| `scripts/` | Safe bootstrap, readiness checks and asset inventory |
| `config/` | Non-personal examples and runtime asset checksums |
| `docs/` | Installation, architecture and repository/privacy boundaries |

Runtime path overrides are documented in [configuration](docs/CONFIGURATION.md). Publication decisions and checks are listed in [publishing](docs/PUBLISHING.md).

No running directory was moved during repository setup. This avoids breaking current imports and paths. A shared path configuration is available; optional voice dependencies still need an independently prepared environment.

## What Git does not include

Model weights, private avatar media, virtualenvs, third-party runtime checkouts, downloaded code, face templates, API keys, local settings, location, conversation history, logs, sockets and machine-specific personal notes. `.gitignore` is an explicit allowlist, not just a list of known secret filenames. A Git clone alone is **not** a backup of the entire working assistant.

See [privacy/release checklist](docs/PRIVACY.md). The [robot demo](demo/README.md) is included with separate sharing permission. Keep the private media/model backup separate and verify it against `config/assets-manifest.json`.

## Testing

```bash
body/.venv/bin/python -B body/test_lyrics.py
body/.venv/bin/python -B body/test_lyrics_download.py
body/.venv/bin/python -B body/test_transition_flow.py
body/.venv/bin/python -B body/test_idle_sleep.py
body/.venv/bin/python -B body/test_layout.py
```

The geometry tests mock camera and lyric-worker startup; they do not capture real camera frames. `test_lyrics_mpv.py` uses a temporary socket and null audio, not production playback. Model-backed voice and generation tests need their separate dependencies and assets.

## Rights and publication

First-party source code is licensed under [GNU GPL version 3 only](LICENSE) (`GPL-3.0-only`). The [bundled robot demo](demo/README.md) has separate sharing permission. Third-party components, private artwork, generated assets, downloaded lyrics and model weights retain their own licenses and restrictions; they are not relicensed by this repository. The installer does not configure a Git remote or upload files.

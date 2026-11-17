# Installation scope and reproducibility

## Supported bootstrap

Linux desktop with Python >=3.10 and `venv`/pip support. The currently exercised installation uses Python 3.14; the full version range has not been clean-room tested. Install system `mpv`, `ffmpeg` and `ffprobe` through your distribution's package manager. Qt may need system XCB/Wayland libraries; the existing private XCB library directory is not redistributed in Git. Do not copy arbitrary system libraries from this machine into another OS release.

```bash
bash scripts/install.sh --help
bash scripts/install.sh --check       # read-only, safe on current machine
bash scripts/install.sh --body        # new desktop environment only
```

If an environment already exists, the installer refuses to change it unless `--body --upgrade` is explicitly supplied. Stop the desktop before deliberately upgrading its packages. The installer does not run sudo or launch services. Package downloads come from pip's configured index; requirements are constrained but not a complete platform-specific lockfile.

Fresh installs create `body/lyrics-settings.json` with automatic online lookup **off**. Existing settings are never replaced. Enabling Auto Lyrics transmits track metadata to LRCLIB, not audio; review provider terms.

## Runtime avatar assets

A shareable geometric robot demo is bundled. On a fresh checkout, run `python3 -B scripts/demo_assets.py`; it refuses to replace existing media. All demo states use one placeholder animation. See [demo permissions](../demo/README.md).

For the private character, Git includes `body/actions.json` and `config/assets-manifest.json`, not the private artwork/video. Restore `Reference.webp` and the listed `body/assets/*` files from your separately held backup:

```bash
python3 -B scripts/assets_manifest.py
```

The verifier reports missing/changed assets. If you intentionally regenerate your own assets, run `python3 -B scripts/assets_manifest.py --write` and review the new manifest before committing. Do not silently replace assets just to satisfy a hash check.

Once ready, launch only the UI:

```bash
bash body/start.sh
```

The UI can use existing local music and existing shared-camera/voice services. Missing services do not become installed merely because the window opens.

## Not yet a full voice installer

The source snapshot preserves the working prototype. In particular:
- `voice/start.sh` uses a checkout-local voice environment by default; existing environments can be selected explicitly through [configuration](CONFIGURATION.md). No voice environment is created by the desktop installer.
- Chinese Vosk/Piper assets, optional English and Breeze ASR models, camera skill/socket, Pi/LLM commands and model servers are external prerequisites.
- Face/gesture perception has additional dependencies not in desktop requirements.
- Taigi has a separate CPU environment and third-party model/runtime licenses; its old helper installer is **not** invoked by the top-level bootstrap.
- `system.py` uses Linux `/proc` and desktop-session assumptions. It starts voice/perception too, so do not treat it as a fresh desktop-only smoke test.

Next portability work should complete service configuration, pin optional dependency sets, and test a fresh user account/machine. Do not modify the legacy first-stage tree to make a new checkout work.

## Backup / restore

Back up source Git history, private configuration, private identity data (only if desired), licensed media and model manifests separately. Encrypt private backups and review their contents. A repository clone intentionally does not restore your conversations, face identity or API credentials.

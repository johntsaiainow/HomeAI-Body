# Publication readiness

## Decisions before the first public push

- Decide whether existing commit author names and email addresses should be public. Changing Git configuration affects future commits only; review all history before publishing.
- First-party source uses `GPL-3.0-only`; the complete license is in `LICENSE`. Preserve the separate demo permission and third-party terms.
- Inventory third-party code, models and downloadable assets, with source URLs, versions and their applicable terms. This source checkout is not a grant of rights to those resources.
- The bundled original robot demo has separate sharing permission in `demo/README.md`. Keep private character assets excluded.

## Checks

```bash
git status --short
git diff --check
git diff --cached
git ls-files
git log --all --format='%h %an <%ae>'
gitleaks git --redact --no-banner .
python3 -B scripts/test_config.py
python3 -B scripts/test_demo_assets.py
python3 -B body/test_idle_sleep.py
python3 -B body/test_transition_flow.py
python3 -B voice/test_hand_rules.py
bash scripts/install.sh --check
```

The readiness check is expected to fail on a source-only checkout until desktop dependencies and demo or private media are supplied. CI checks syntax, tests without hardware or models, an offscreen Qt layout, and isolated mpv playback with null audio. It does not validate real hardware, model inference or a full voice installation. Test those separately on a fresh Linux account before claiming a portable installation.

The ignore file explicitly permits `LICENSE` and `.github/workflows/*.yml`. Keep private settings, face templates, downloaded models and media out of Git. Scan new changes as well as existing history before publishing.

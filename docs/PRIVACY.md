# Repository and release boundaries

The default-deny `.gitignore` permits reviewed first-party code, technical action indexes, artist aliases, dependency lists, asset checksums and these public-facing docs. It excludes runtime JSON settings except the explicitly named technical files.

Do not force-add:
- `private/`, face templates, enrolled samples or identity models derived from a person;
- API keys, `.env`, local location or microphone/voice/language preferences;
- `logs/`, dialogue histories, generated daily summaries or personal agent instructions/status;
- `.venv`, `models`, third-party `vendor`, runtime/source checkouts or downloaded package trees;
- avatar images/video, recordings, lyrics or model weights without separate rights review.

Runtime paths are configurable; see [configuration](CONFIGURATION.md). Existing Git history can still contain earlier machine paths and author identity. Review history as well as the current tree before publication. Code/privacy review is not a guarantee that arbitrary future additions contain no secrets.

Before any push:
1. Inspect `git diff --cached`, `git ls-files` and the commit author/email.
2. Run a secret scanner such as gitleaks if available; investigate every result rather than blindly suppressing it.
3. Choose a repository license and review third-party/model/artwork terms.
4. Prefer a private remote first; no remote is created or pushed automatically.
5. Never use `git add -f` on a private/runtime directory to fix an install issue.

Ignored files are not encrypted and are not backed up by Git. Deleting Git history also does not remove a secret already published; revoke it if that occurs.

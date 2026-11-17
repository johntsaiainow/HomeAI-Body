# Desktop launcher / LM Studio integration

`system.py start` opens the body first, then checks the configured local LM Studio HTTP server before proceeding with voice startup. Existing voice/body processes remain running. Startup operations are serialized by the existing process-manager lock, so repeated clicks do not launch parallel loaders. A cold load can take time; Stop waits for an in-progress Start operation to release this lock (not immediate cancellation).

Local preference: `config/llm-service.json` (ignored by Git). Template: `config/examples/llm-service.json` (auto-start disabled for fresh users).

Optional configuration can enable localhost port 1234, CLI at `~/.lmstudio/bin/lms`, model auto-load, and owned-server stop on exit. No remote bind or CORS option is added.

## Start
- Confirm LM Studio's server status and port. Reuse an already-running server; do not change its bind/auth settings or adopt ownership.
- If stopped, first reject a conflicting listener, then use `lms daemon up` and `lms server start --port 1234 --bind 127.0.0.1`.
- Check HTTP `/v1/models`; 401/403 is considered a protected reachable server, not an excuse to disable authentication. Existing Pi provider credentials remain unchanged and are not read by this helper.
- Determine the model from explicit `model`, or Pi defaultModel only when defaultProvider matches configured provider. Verify the actual loaded identifier using `lms ps --json`.
- If no model is loaded, load the selected model with ordinary LM Studio settings. Never unload another model to make room; if a different model is already loaded, report that model readiness needs attention rather than allocating a second model.
- Report server/model checks separately. Failed model load does not claim successful LLM readiness; music and other offline functions can still start.

## Stop / sharing
Only a server started by this integration has a private ownership record. The record binds CLI, port, OS boot ID, daemon PID and process start ticks. Before stopping, all must still match. Missing/stale ownership leaves the server untouched. Only `lms server stop` is used: no process killing, daemon shutdown or model unloading. Closing the HTTP server does not guarantee GPU memory is released.

For a shared household server, set `stop_owned_server_on_exit` to false to keep it running even when Neris exits. Ownership is not a client-usage lease: it cannot detect that another client has begun using a Neris-started server. Manual HTTP stop/restart inside the same still-running LM Studio process is also not distinguishable by PID identity; use keep-running mode if that service becomes shared.

Logs: `logs/llm-service.log`. Ownership: `private/llm-service-owner.json`. Neither is committed. Desktop `.desktop` files still call `system.py start|stop`; no LM Studio application config or legacy voice files are edited.

## Validation
`python3 -B scripts/test_llm_service.py` mocks all LM Studio lifecycle operations: reuse, cold start/ownership/stop, PID mismatch, port conflict, model loading, other-model preservation and errors.

A real cold-start/shutdown test has intentionally not been performed against the running shared LLM, to avoid interrupting active users. Test that separately when stopping it is acceptable. Existing-server success is not equivalent to cold-start acceptance.

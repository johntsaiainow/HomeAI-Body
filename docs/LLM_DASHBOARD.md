# Upper-right character / LLM dashboard

The same black/green upper-right frame uses a horizontal layout: large Neris-A name/current body action on the left, compact LLM metrics on the right. Camera preview remains below it. Long data lines are elided rather than wrapped, with complete data in the hover tooltip; this saves vertical space. Hiding the preview does not hide the frame. IN/OUT are input/output tokens, Cache is read/write tokens and T is total tokens.

Displayed:
- Current explicit router provider/model, classified Local or Cloud from the selected mode; Unknown when not configured. Only provider/model identifiers are displayed, never URLs, credentials or API keys.
- Local server TCP reachability (not proof of successful authentication or model availability). Cloud connectivity is not probed proactively; requests use Pi's configured provider normally.
- Last request status and provider-reported input/output/cache/total token counts.
- Last completed invocation wall time and effective average output tokens/second. This includes CLI startup, tools and any retries; it is **not** GPU decoding speed or time-to-first-token.
- Estimated cost from Pi's configured model rates when a positive amount is available. This is **not an invoice, account balance, or guaranteed provider billing**. Unknown/zero-cost metadata is shown as a dash, not asserted to mean free service.
- System RAM and first NVIDIA GPU utilization/VRAM, sampled in the background every five seconds. These include other programs, not just LLM usage. Missing NVIDIA tooling displays a dash.

`voice/agent.py` uses Pi JSON mode instead of plain print output. Only authoritative assistant `message_end` records contribute usage; duplicated agent_end snapshots do not. Multi-turn LLM calls within the invocation are summed, and reasoning usage already included in output is not added twice. Thinking blocks and raw JSON are not sent to speech. Requests retain the previous 30-second timeout and ordinary Pi configuration/tools.

`body/llm-status.json` is a private, ignored, atomic allowlisted snapshot: model identifiers, counters, timings and status only. No prompt, response text, key, raw provider config or URL is persisted there. Telemetry failure must not stop ordinary dialogue.

Numbers update **after an invocation finishes**, not token-by-token while generating. While Thinking, displayed Last metrics refer to the previous completed call. They are per invocation, not a lifetime/session budget or live context-window occupancy. Unknown usage is a dash rather than a character-based estimate.

This dashboard does not switch providers merely by displaying Local/Cloud and does not enable silent cloud failover. Provider/model selection uses the explicit router described in [model selection](MODEL_SELECTION.md); cloud setup requires your own provider configuration and credentials.

## Validation
- `body/test_llm_metrics.py`: six cases for usage, multi-call aggregation, no duplicate counts, unavailable usage, JSONL Unicode framing, failure handling and secret exclusion.
- `body/test_layout.py`: full-size metrics text at two window sizes; frame/camera ordering, existing transitions/sleep/lyrics behavior. Metrics/camera/lyrics workers are mocked in this geometry test.

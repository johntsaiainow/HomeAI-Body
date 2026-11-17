# Deterministic music commands

## Saved playlist playback

Say/type **播放音樂清單**, **播放音樂選單**, **播放歌單**, or **play playlist** to start the saved list from its first valid track. **下一首 / next track** and **上一首 / previous track** navigate the loaded queue; **停止音樂** stops it. These exact commands run before the LLM and pending song-title selection.

`music.play_playlist()` snapshots private `body/playlist.json`, skips missing/unsupported paths, and loads a private temporary M3U8 into Neris's dedicated mpv process. mpv advances on EOF even if the desktop UI closes. The list plays once, then exits; both queue looping and single-track repeat start Off. Turning Repeat One on deliberately keeps the current song until disabled. Existing volume behavior for a new player is unchanged.

Empty/invalid lists do not stop current music. A successful start requires observed queue count, a valid queued path and numeric playback position. Failed/unconfirmed startup is never reported as success. Queue edits during playback affect the saved list, not the already loaded snapshot: start the list again to apply changes. A named single-song request or the UI's play-selected button replaces the queue.

The saved list lives in the Music tab. Three fingers add the current track; four remove it from the saved list without stopping playback. Voice commands are available before music starts, but ASR is suspended during playback: use the text command box for next/previous/stop, or pause first. No claim of hearing commands over music.

Tests include isolated null-audio mpv playback of two WAV fixtures, automatic EOF advance, next/previous bounds, final queue exit and temporary-file cleanup; command routing, empty/corrupt list safeguards and existing replay/gate/gesture tests also run.

## Replay

`voice/music_commands.py` handles exact replay transport phrases before song-selection waiting and before any Pi/LLM invocation. Supported phrases include 重播、再播一次、再播放一次、重新播放、從頭播放、從頭再播, replay, play again, restart song/music. Named `重播 <song>` and `重新播放 <song>` use the existing local song search.

`body/music.py replay()`:
- An active local track is sought to absolute time zero, then unpaused.
- After EOF/player exit, the last recorded existing local song is relaunched through the same dedicated Neris mpv IPC socket.
- Before reporting success, checks actual path, numeric position below three seconds and pause=false. Missing history, refused commands and unconfirmed starts return failure instead of a language-model promise.
- Never kills unrelated mpv processes or changes lyrics offsets. Lyrics follow the actual reset time-pos.

`body/music-state.json` privately remembers the last local music path across EOF and restarts. Music launch records it, and the background lyrics observer records tracks announced on the dedicated player socket. This JSON is ignored by Git. It contains a local song path, not audio. Delete it to remove saved replay history; another playback can create a new record.

## Contextual gestures and upper-right feedback

With Gesture Control enabled and a song actually loaded (including paused), hold Number_1 / Pointing_Up for 1s to replay, or Number_2 / Victory for 1.5s to toggle single-track repeat. Outside this context they do nothing; no idle-mode alternative is assigned yet. Two release samples re-arm; held gestures fire once; conflicting music commands, disabled control, stale samples and track changes cannot carry an old hold through.

Gesture replay uses `require_loaded=True`, never replaying old history from an idle pose. `loop-file=inf/no` is set and read back for Repeat One. It defaults to mpv's Off on a new music process; playlist looping is not introduced. A paused song stays paused when repeat is toggled; replay unpauses it.

The upper-right black/green frame has horizontal name/state, LLM and a dedicated **rightmost music column**, with Beat sync, Repeat One and last music-control feedback on separate lines. This music column is hidden outside actual playback/pause and hidden again after stop/EOF. Music fields are not appended to LLM text. The old Beat sync label below the controls is removed. Long lines are elided with full hover tooltips, and beat synchronization logic is unchanged.

After verified playback/loop updates, perception posts `control_status` and queues an allowlisted internal feedback token. The voice worker says a short receipt/result in the selected Mandarin/English/Taigi language without an LLM request. Voice Output Off suppresses speech normally, not text. Failed player confirmation produces failure feedback, not a success claim; unavailable voice ingress is shown in the header. A busy voice queue or cold TTS can delay speech. This feedback applies to the two new gestures; continuous volume changes are not narrated.

Tests: seven context/hold/release/feedback fixtures, actual mpv repeat On/Off/readback plus loaded-only replay guards, and Qt tests asserting separate third-row fields survive metrics refresh, idle/stopped hide the row, playing/paused show it below both upper panels, and no duplicate Beat label remains below. Production IPC confirms the fields in the actual header. Camera gestures and audible feedback still need user acceptance.

## Microphone versus recognition during playback

`body/music_gate.py` uses the actual dedicated mpv pause state, not a launch-thread flag. Active normal/replayed music blocks ASR, pause/EOF/stop allow it again, provided the user's microphone preference remains ON. TTS replies also block recognition. A live but unresponsive music IPC blocks conservatively. Pre/post-ASR force checks discard a result if playback began during inference.

This is **ASR suspension, not system hardware mute or a guarantee that the audio input stream is closed**. The current capture loop still reads and discards playback-period chunks. The microphone button represents the user's persistent permission; explicit Off separately stops its input stream and is not automatically undone by a song ending.

Consequently, during music use text or gestures for control, or pause/stop music before speaking. The replay production test used the text-command queue, not acoustic recognition over music. No wake-word-over-music or acoustic echo cancellation is claimed.

Validation: four playback unit tests, three synonym/agent-route tests, real mpv null-audio/private-socket replay/seek/unpause test, existing Qt checks. Actual production voice-command queue accepted `重播` and the dedicated player confirmed 花樣年華 from position 0.0 after EOF. This tests command execution, not new acoustic ASR accuracy or perfect lyric timing. Initial history was seeded from the immediately preceding, explicitly known conversation song because the old player had not recorded a last-track file.

# Changelog

## Unreleased

### Added
- Full Scooper Pro Ultra support through Aliyun: live camera with sound, live state and settings, action buttons, sensors and diagnostics
- Live Scooper Pro Ultra updates over Aliyun's push channel, instead of waiting for the next poll
- `catlink_event` events for visits, cats entering and leaving, motion, jobs and faults
- Translated names, states and icons for the Scooper Pro Ultra's entities
- Speaker media player for the Scooper Pro Ultra: play any audio or `tts.speak` through the box
- Live talk websocket API (`catlink/talk`) for a push-to-talk panel, see `docs/LIVE_TALK_API.md`
- Time and media player platforms, and a `translation_key` entity option

### Fixed
- Entity IDs now use each entity's own platform domain, as Home Assistant requires
- Re-login after an expired token repeats the original request instead of a signed one
- Polling keeps working after the integration is reloaded
- The account's HTTP session is released when a config entry or flow is done
- Scooper Pro Ultra `briefInfo` is parsed even when the API sends null strings
- A failed first refresh retries the setup instead of leaving the integration idle

### Changed
- The Scooper Pro Ultra is no longer marked "limited support"

## 2.1.1 - 2026-02-06

### Added
- Open-X/C08 device support (thanks to this nice repo: https://github.com/eulemitkeule/pycatlink)
- Limited Scooper Pro Ultra support
- Reset litter and reset deodorant buttons for litterbox
- Config flow coverage for discovery, reauthentication, and options
- Test suite additions and GitHub Actions workflow for tests

### Fixed
- Device detail parsing fallback when API payloads are incomplete
- Home Assistant 2026.2.0 compatibility issues

### Changed
- Device and entity organization with new helpers and logs mixin

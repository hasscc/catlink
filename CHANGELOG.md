# Changelog

## Unreleased

### Added
- Time platform and a `translation_key` entity option
- English translations are shipped, so the setup and options dialogs show their texts

### Fixed
- Entity IDs now use each entity's own platform domain, as Home Assistant requires
- Re-login after an expired token repeats the original request instead of a signed one
- Polling keeps working after the integration is reloaded
- The account's HTTP session is released when a config entry or flow is done
- A failed first refresh retries the setup instead of leaving the integration idle

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

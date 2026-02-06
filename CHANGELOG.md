# Changelog

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

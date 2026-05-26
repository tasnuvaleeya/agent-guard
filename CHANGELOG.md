# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-05-26

### Notes
- Fresh release after repo recreate. No functional changes vs v0.1.3.

## [0.1.3] - 2026-05-26

### Changed
- Marketplace listing name (`action.yml` `name:` field) changed from `agent-guard` to `ag-scan` to resolve a collision with the existing `Agent-Guard` GitHub organization. The repo, CLI command, and brand are unaffected — `uses: tasnuvaleeya/agent-guard@v0.1.3` continues to work because it's path-based.

## [0.1.2] - 2026-05-26

### Changed
- README now includes a screenshot of a sample sticky PR comment for the Marketplace listing.

### Notes
- PyPI distribution name is `ag-scan` (the `agent-guard` name was taken by an unrelated project). CLI command, Action, and brand stay as `agent-guard`.

## [0.1.0] - 2026-05-26

### Added
- Milestone 1 scaffold: CLI, diff parser, five analyzers (secrets, hallucinated_imports, dangerous_patterns, missing_tests, infra_changes), risk scorer, Markdown/JSON reporters, GitHub Action, sticky PR comment poster.

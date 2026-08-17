# Changelog

## 1.2.0 - 2026-08-16

### Added
- Compile-once SRD 5.2.1 pipeline that produces an offline normalized SQLite catalog from the official PDF.
- Typed catalogs for spells, class features/progressions, subclasses, feats, non-weapon magic-item metadata, monster stat data, travel/environment rules, and encounter budgets.
- `SRDCatalogStore` with non-blocking SQLite access, bounded search, section counts, and persisted compilation provenance.
- Runtime adapters that register mechanically simple compiled spells and instantiate monster stat records as normal engine entities.
- SRD travel/terrain/environment helpers and deterministic encounter XP budget/candidate tooling.
- Read-only SRD REST endpoints and CLI commands for compilation, catalog inspection/search, and encounter budgets.
- Compiler/store/runtime/toolbox/API regression coverage.

### Changed
- `SpellDefinition` now carries level, school, class, save ability, Concentration, Ritual, and component metadata.
- The SRD pack advertises the external compiled-catalog schema rather than embedding the large catalog into every campaign save.
- Long-form source prose stays out of the runtime catalog; generated records retain source-page/hash provenance for auditability.

### Deliberate exclusions
- This build does not compile weapon-specific equipment/mastery records, monster action/gear prose, detailed hazardous-substance content, or long-form SRD descriptive text.

## 1.1.0 - 2026-08-16

### Added
- Opt-in SRD 5.2.1 rules foundation with official-source provenance and CC BY 4.0 attribution.
- Typed catalogs for skills, classes, species, backgrounds, and SRD feat identifiers.
- Official-source allowlist and asynchronous `fetch-srd` CLI command.
- Advantage/disadvantage-aware attacks, configurable armor calculation, damage traits, temporary hit points, and SRD-style death-saving-throw state.
- Structured SRD condition definitions and six-second round mapping that works with all engine timing modes.
- `rules_data` support in creator content packs for structured rules catalogs and deterministic ZIP round-trips.

### Changed
- Content pack hashing now canonicalizes sets and enums deterministically.
- README now distinguishes the generic engine from the separately licensed SRD integration.

## 1.0.0 - 2026-08-16

- Initial headless deterministic RPG platform release covering the v0.1 through v1.0 roadmap.

# Contributing

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[all,dev]'
pytest
```

## Architectural rules

- Keep authoritative simulation code independent of UI/rendering frameworks.
- Model player/network intent as commands and observable results as events.
- Do not block the asyncio event loop with file/database/network operations.
- Use deterministic engine RNG streams instead of module-global randomness.
- Keep client presentation unable to mutate authoritative state directly.
- Add regression tests for timing/scheduler changes in every supported mode.
- Treat content packs as untrusted input: validate schemas, references, archive sizes, and paths.
- Do not copy proprietary tabletop content into the repository; contribute only material you have the right to license.

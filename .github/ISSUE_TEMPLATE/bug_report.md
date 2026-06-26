---
name: Bug report
about: Report incorrect or invalid generated output, or a crash
title: "[bug] "
labels: bug
---

## What happened

A clear description of the bug.

## Minimal schema to reproduce

The single most useful thing you can provide. Paste the smallest LinkML schema
that triggers the problem (inline it, or attach it).

```yaml
# schema.yaml
```

## Command / code

```bash
linkml-data-gen schema.yaml --seed 0 ...
```

or

```python
from linkml_data_gen import DataGenerator, GenerationConfig
...
```

## Expected vs. actual

- **Expected:**
- **Actual:** (paste the output, or the `--validate` errors / traceback)

## Environment

- linkml-data-gen version:
- Python version:
- `linkml` / `linkml-runtime` versions:
- OS:

## Anything else

Hints file, scope flags, or other context.

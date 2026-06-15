# traceback_to_fix_prompt

- Trigger: tests fail and a traceback/assertion must be converted into a worker repair instruction.
- Symptom: the raw traceback is too long, mixed-language, or vague for reliable CLI editing.
- Fix strategy: produce one English sentence that names the file, function, exact change, and expected test behavior.
- Avoid: pasting the full traceback into the execution prompt; saying only "fix the bug"; asking for permission; changing multiple functions in one instruction.

Instruction template:

```text
Please fix the `<function>` function in `<file>` by <specific change> so that <expected behavior>.
```

Examples:

```text
Please fix the `date_diff` function in `date_converter.py` by wrapping the return value with `abs()` so that the difference is always a positive integer.
```

```text
Please fix the `reverse_words` function in `string_processor.py` so that it splits by whitespace and rejoins with single spaces, stripping leading and trailing spaces.
```

Common mappings:

| Failure pattern | Repair instruction |
| --- | --- |
| `AssertionError: assert -5 == 5` | Use `abs()` for date difference. |
| Extra internal whitespace | Normalize with `split()` and `" ".join(...)`. |
| `IndexError` | Add a boundary check before indexing. |
| `KeyError` | Check key existence or use `.get()` with a default. |
| `TypeError` | Convert or validate inputs so the return type matches tests. |

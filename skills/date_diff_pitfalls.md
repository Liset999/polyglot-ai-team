# date_diff_pitfalls

- Trigger: a task asks for date difference, date conversion, or date validation.
- Symptom: tests fail on reversed date order, alternate separators, or invalid calendar dates.
- Fix strategy: parse dates with explicit accepted formats, validate by constructing `datetime.date(year, month, day)`, and return `abs((d1 - d2).days)` for date differences.
- Avoid: returning signed day differences unless the test explicitly asks for direction; silently returning `None` for unsupported formats; hand-validating month lengths instead of using `datetime.date`.

Accepted default formats for simple converters:

- `YYYY-MM-DD`
- `YYYY/MM/DD`
- `YYYY.MM.DD`

Unsupported or invalid dates should raise `ValueError`.

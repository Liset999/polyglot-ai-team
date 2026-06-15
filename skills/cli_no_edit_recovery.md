# cli_no_edit_recovery

- Trigger: a local CLI worker exits with code `0`, but the target file content did not change.
- Symptom: logs look successful, but tests still fail and the file hash/content before and after the worker call is identical.
- Fix strategy: mark `failure_type: cli_no_edit`, compress the task into one concrete edit instruction, and rerun the worker with an explicit file-edit command.
- Avoid: sending a long traceback or multi-part business explanation directly to the execution worker.

Use this wording in the retry prompt:

```text
You MUST use your write/edit tool to modify the file directly. Do not explain or ask for permission; perform the edit.
```

Keep the retry instruction under three lines and focus on one file/function at a time.

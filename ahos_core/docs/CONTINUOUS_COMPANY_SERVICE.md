# Continuous AHOS company service on Windows

`ahos.company_daemon` keeps the local owner-controlled holding runtime alive,
writes a heartbeat for the Control Center, polls configured automation queues,
and honors the owner kill-switch file. It does not claim general company
missions until a real orchestrator is configured, and coding execution defaults
to disabled.

Install the current-user logon task from PowerShell:

```powershell
.\ahos_core\scripts\Install-AHOS-CompanyService.ps1 `
  -RuntimeDir ".\runtime" `
  -PythonExe "C:\path\to\.venv\Scripts\python.exe"
```

The scheduled task starts at user logon, restarts after failure, runs without a
visible console, and has no time limit. Status is written to
`runtime/company-service-heartbeat.json`; stdout and stderr are kept beside it.
The Control Center's kill switch creates `company-service.stop` and the launcher
removes that flag only when the owner explicitly starts/resumes the company.

To enable the coding supervisor, create `runtime/company-service-config.json`
with an explicit builder argv and test-executable allowlist. This is intentionally
not generated automatically because the builder can invoke an external or paid
agent. Repository merge, push, deployment, publishing, credentials, purchases,
and paid media generation remain owner-gated.

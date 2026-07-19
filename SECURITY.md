# Security Policy

## Supported Version

Security fixes are applied to the current `main` branch. The project is in an
alpha stage and does not currently promise long-term support for older tags.

## Reporting A Vulnerability

Use GitHub private vulnerability reporting for this repository when available.
If private reporting is unavailable, contact the repository owner privately
through the contact method listed on the GitHub profile. Do not include secrets,
API keys, exploit payloads, or private datasets in a public issue.

Please include:

- affected commit or version;
- reproduction steps using non-sensitive test data;
- potential impact;
- suggested mitigation, if known.

## Secret Handling

Astro ABM credentials belong in ignored local configuration or environment
variables. They must never be stored in scenario JSON, Markdown reports, logs,
presets committed to Git, screenshots, or issue reports.

If a credential is exposed, revoke and rotate it immediately. Removing it from
the latest commit is not sufficient because Git history and caches may retain
the value.

## Scope

Reports about financial interpretation, research methodology, or forecast
quality are product/research issues rather than security vulnerabilities unless
they also expose data, credentials, or unauthorized access.

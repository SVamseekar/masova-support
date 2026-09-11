# Security Policy

## Supported versions

This service is pre-1.0. Security fixes land on `main` and ship in the next
patch release (`vMAJOR.MINOR.PATCH`). There are no long-lived maintenance
branches.

## Reporting a vulnerability

This repository is public. **Do not** open a public issue for security reports.

Use GitHub **Privately report a vulnerability** on this repository, or email the
maintainer listed on the GitHub profile that owns the repo.

Include:

- affected endpoint or component
- reproduction steps
- impact (auth bypass, data exposure, injection, etc.)

You should receive an acknowledgement. Do not test against production customer
data.

## Secrets and credentials

- Never commit `.env`, API keys, JWT secrets, tokens, or private keys.
- Local templates: `.env.example` and `config/env.example` (placeholders only).
- CI uses dummy values; production secrets belong in the deployment environment
  or GitHub Actions secrets, not in workflow files.
- GitHub secret scanning and push protection are enabled on this repository.
- CI runs `pip-audit` against `requirements.txt`. Starlette CVEs that require
  starlette 1.x are ignored while `google-adk` 1.35 pins `starlette<1.0.0`.
  Remove those ignores when ADK allows starlette 1.x.

## Agent co-authorship

Do not add `Co-Authored-By` trailers for AI coding tools in commits.

# Security Policy

## Supported versions

linkml-data-gen is pre-1.0. Security fixes are applied to the latest release and
the `main` branch.

| Version | Supported |
| --- | --- |
| latest / `main` | ✅ |
| older | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report vulnerabilities privately by either:

- using GitHub's **["Report a vulnerability"](https://github.com/BU-Neuromics/linkml-data-gen/security/advisories/new)**
  (Security → Advisories), or
- emailing **labadorf@bu.edu** with the details.

Please include enough information to reproduce: the schema (or a minimal
version), the command or code you ran, and the observed impact. We aim to
acknowledge reports within a few business days and will keep you updated on
remediation.

## Scope and threat model

linkml-data-gen reads a LinkML schema and generates data files. Keep in mind:

- **Schemas and hints are code-adjacent input.** The tool loads schemas via
  `linkml_runtime` and reads YAML/JSON hint files. Only run it on schemas and
  hint files you trust, as you would any tool that loads YAML and resolves
  imports (including remote `imports`/URLs).
- **Generated data is synthetic** and random; it is not a source of secrets, but
  do not treat generated identifiers/values as secure tokens.
- The tool does not transmit data anywhere; it reads inputs and writes output
  files (or stdout).

Reports about handling of untrusted schema/hint input, unsafe deserialization,
or path handling are in scope and appreciated.

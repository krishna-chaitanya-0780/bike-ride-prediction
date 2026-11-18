# GitHub repository publication status

**Prepared locally. NOT pushed to GitHub.**

Suggested repository name: `verdant-atlas-medicinal-marketplace`
Suggested initial visibility: **private**, until the owner chooses to publish.

The repository is source-ready with:

- `.gitignore` excluding passwords, local `.env`, SQLite files, Python caches and logs;
- `.github/workflows/test.yml` for server tests and JavaScript syntax checks;
- MIT license for the project code;
- project documentation, mobile/desktop visual captures and a repeatable test suite.

A GitHub account must be connected with permission to create and write repositories.
No credential is included. No commit has been pushed to any remote account.

No hosting or cloud database was created; API calls use public GBIF taxonomy only
when requested by the user at runtime, and the default database remains local SQLite.

For production commerce, integrate approved payment processing, actual inventory and
shipping providers, seller onboarding, schema migrations, payment idempotency,
orders webhooks, backups, rate limits and security review **before** accepting money.

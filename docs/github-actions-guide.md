# GitHub Actions guide for this repo

## What the workflow does

The workflow file is:

```text
.github/workflows/update-index.yml
```

It runs in two ways:

- manually from the GitHub Actions tab
- automatically at 6:00 AM and 6:00 PM Japan time

Main steps:

1. Check out the repo.
2. Set up Python.
3. Install dependencies.
4. Run tests.
5. Build `/public`.
6. Upload `/public` as a GitHub Pages artifact.
7. Deploy the artifact to GitHub Pages.

## First-time setup

1. Create a public GitHub repo named `jtorrent`.
2. Add this project to the repo.
3. Go to **Settings → Pages**.
4. Under **Build and deployment**, set **Source** to **GitHub Actions**.
5. Go to **Actions**.
6. Click **Update JTorrent Backend Index**.
7. Click **Run workflow**.

## Reading failures

Open the failed run and expand the failed step.

Common failures:

- Unknown source type: a source uses a `type` the backend does not support.
- YAML formatting error: check indentation in `config/sources.yml`.
- Network timeout: a source was temporarily unavailable.
- Pages not configured: set **Settings → Pages → Source → GitHub Actions**.

## Changing the schedule

The workflow is currently configured with the `Asia/Tokyo` timezone and runs at 6:00 AM and 6:00 PM Japan time:

```yaml
schedule:
  - cron: "0 6,18 * * *"
    timezone: "Asia/Tokyo"
```

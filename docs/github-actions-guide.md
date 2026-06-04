# GitHub Actions guide for this repo

## What the workflow does

The workflow file is:

```text
.github/workflows/update-index.yml
```

It runs in three ways:

- immediately when backend code/config/workflow files are changed on `main`
- manually from the GitHub Actions tab
- automatically once every 24 hours at 1:45 AM Japan time

Main steps:

1. Check out the repo.
2. Set up Python.
3. Install dependencies.
4. Run tests.
5. Build `/public`.
6. Create `public/.nojekyll`.
7. Validate the generated JSON backend with `scripts/validate_public_backend.py`.
8. Upload `/public` as a GitHub Pages artifact.
9. Deploy the artifact to GitHub Pages.

## First-time setup

1. Create or open the public GitHub repo named `jtorrent`.
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
- Network timeout/source error: a configured source was temporarily unavailable or returned an error.
- Backend QC failed: generated JSON was missing, invalid, empty, or `manifest.errors` was not empty.
- Pages not configured: set **Settings → Pages → Source → GitHub Actions**.

## Changing the schedule

The workflow is configured with the `Asia/Tokyo` timezone and runs at 1:45 AM Japan time every day:

```yaml
schedule:
  - cron: "45 1 * * *"
    timezone: "Asia/Tokyo"
```

For example, to run at 12:30 PM Japan time every day, use:

```yaml
schedule:
  - cron: "30 12 * * *"
    timezone: "Asia/Tokyo"
```

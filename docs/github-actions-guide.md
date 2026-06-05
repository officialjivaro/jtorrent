# GitHub Actions guide for this repo

## What the workflow does

The workflow file is:

```text
.github/workflows/update-index.yml
```

It runs in three ways:

- immediately after a push to backend-relevant files on `main`
- manually from the GitHub Actions tab
- automatically once every 24 hours at **1:45 AM Japan time**

Main steps:

1. Check out the repo.
2. Set up Python.
3. Install dependencies.
4. Run tests.
5. Build `/public`.
6. Validate manifest, sources, legacy pointers/shards, v2 token index, doc shards, and `public/.nojekyll`.
7. Upload `/public` as a GitHub Pages artifact.
8. Deploy the artifact to GitHub Pages.

## First-time setup

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Go to **Actions**.
4. Click **Update JTorrent Backend Index**.
5. Click **Run workflow**.

## Reading failures

Open the failed run and expand the failed step.

Common failures:

- `manifest.item_count` below the QC threshold: not enough sources produced data.
- Required source below `min_items`: the source worked but returned too little.
- Required source error: a required adapter failed.
- Optional source warning: visible in `manifest.warnings`, but does not block deploy.
- Pages upload/deploy problem: check Pages is set to **GitHub Actions**.

## Changing the schedule

The workflow is currently configured with the `Asia/Tokyo` timezone and runs once every 24 hours at 1:45 AM Japan time:

```yaml
schedule:
  - cron: "45 1 * * *"
    timezone: "Asia/Tokyo"
```

## Scaling note

The build job timeout is set to 300 minutes because large Internet Archive harvests can take longer than the earlier 60-minute setting. GitHub-hosted runner jobs still have platform limits, and GitHub Pages deployments/sites have separate size and timeout limits, so extremely large datasets should eventually move to a real search backend or object storage/CDN.

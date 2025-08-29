# Documentation Deployment Guide

## GitHub Pages Setup (Recommended for Private Repository)

### Automatic Deployment

Documentation is automatically built and deployed via GitHub Actions to GitHub Pages on every push to the `main` branch.

### Manual GitHub Pages Configuration

After creating the repository on GitHub, you need to enable GitHub Pages:

1. Go to your repository: `https://github.com/brunel-opensim/homepot-client`
2. Navigate to **Settings** → **Pages**
3. Under **Source**, select **Deploy from a branch**
4. Select branch: **gh-pages**
5. Select folder: **/ (root)**
6. Click **Save**

### Access Documentation

Once configured, documentation will be available at:

[https://brunel-opensim.github.io/homepot-client/](https://brunel-opensim.github.io/homepot-client/)

### Workflow Details

- **Build Trigger**: Push to `main` branch
- **Build Tool**: Sphinx with Read the Docs theme
- **Deployment**: GitHub Actions using `peaceiris/actions-gh-pages@v4`
- **Branch**: Documentation deployed to `gh-pages` branch

## Alternative: Read the Docs for Business

If you prefer Read the Docs and have a subscription to Read the Docs for Business:

1. The `.readthedocs.yaml` configuration is already prepared
2. Import the private repository in your RTD Business dashboard
3. Configure the project settings as described in the main documentation

## Custom Domain (Optional)

To use a custom domain like `docs.homepot-consortium.org`:

1. Add a `CNAME` file to the `gh-pages` branch with your domain
2. Configure DNS to point to `brunel-opensim.github.io`
3. Update the GitHub Pages settings to use the custom domain

This can be automated by modifying the deployment workflow to include the CNAME file.

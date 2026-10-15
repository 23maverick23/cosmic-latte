# Cosmic Latte

A light and dark color scheme named after the average color of galaxy light.

[Website](https://23maverick23.github.io/cosmic-latte/) · [Releases](https://github.com/23maverick23/cosmic-latte/releases)

## Downloads

The [`downloads/`](downloads/) folder contains the palette JSON, CSS variables, and files for VS Code, Windows Terminal, Ghostty, iTerm2, Sublime Text, and Slack (dark mode). Open [`index.html`](index.html) for color values, the history of Cosmic Latte, contrast ratios, and setup steps.

VS Code files are settings to merge into User `settings.json`; no extension is needed. Slack imports may change the colors. The files have been checked for structure and consistency, but their appearance has not been fully tested in each app.

## Build

Requires Python 3.9 or later. No packages need to be installed.

```sh
python3 build.py
python3 build.py --check
python3 -m unittest discover -s tests -v
```

The build works from any directory. `--check` reports missing or stale generated files without writing them.

Edit these source files, then rebuild:

- `palette.json`: names, roles, colors, version, and terminal settings.
- `templates/index.html`: page text, layout, styles, and interactions.
- `build.py`: app-specific export rules.

ANSI slots refer to named colors where possible, so changing an accent also updates its terminal slots. Soft accent colors are mixed from the base and accent using the tint percentages in `palette.json`.

The build generates:

- `index.html`: the site page, with links to separate files.
- `downloads/`: 13 downloadable theme/palette files and a manifest.
- `dist/cosmic-latte-standalone.html`: one offline HTML file with every download embedded.
- `dist/cosmic-latte-VERSION.zip`: all 13 files, the standalone page as `index.html`, this README, and the license.

Do not edit generated files. `index.html` and `downloads/` can be committed for direct repository downloads. `dist/` is a build output for hosting or attaching to a GitHub release. Rebuilding unchanged source produces identical files and ZIP bytes with the same Python runtime.

## Local preview and hosting

Open `index.html` directly, or run this in a source checkout:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Then visit <http://127.0.0.1:8000/>. The app has no server-side code or external assets.

The `Publish site` GitHub Actions workflow builds, tests, and deploys the site to GitHub Pages on each push to `main`. It publishes `index.html`, `downloads/`, and `dist/` together. The workflow can also be run manually from the Actions tab.

If you downloaded the release ZIP, extract it and open its `index.html`. The build source is in the Git repository, not the release ZIP.

## Publishing a release

Update `version` in `palette.json`, then build, test, commit, and push. Publish a matching release tag and attach the generated ZIP and standalone HTML. For version 1.0.0:

```sh
gh release create v1.0.0 \
  dist/cosmic-latte-1.0.0.zip \
  dist/cosmic-latte-standalone.html \
  --target main --title "Cosmic Latte 1.0.0" --generate-notes
```

Release publishing is manual. The Pages workflow publishes the site, not GitHub releases.

## License

[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/). Use, change, and share the page and theme files for any purpose. No credit required. See [LICENSE](LICENSE).

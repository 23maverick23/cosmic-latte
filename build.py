#!/usr/bin/env python3
"""Build Cosmic Latte downloads, website, standalone page, and release ZIP.

Uses only the Python standard library. Run from any working directory.
"""

import argparse
import html
import io
import json
import math
from pathlib import Path
import plistlib
import re
from urllib.parse import quote
import zipfile

ROOT = Path(__file__).resolve().parent
ACCENTS = ['supernova', 'pink', 'solar', 'aurora', 'ion', 'nebula']


def json_text(value):
    return json.dumps(value, indent=2) + '\n'


def blend(base, accent, percent):
    """Mix an accent into the base in sRGB, rounding halves upward."""
    fraction = percent / 100
    channels = [math.floor(int(base[i:i+2], 16) * (1-fraction)
                          + int(accent[i:i+2], 16) * fraction + 0.5)
                for i in (1, 3, 5)]
    return '#' + ''.join(f'{channel:02X}' for channel in channels)


def expand_palette(source):
    """Resolve ANSI references and derive soft accents from the named colors."""
    palette = {key: value for key, value in source.items() if key != 'terminal'}
    palette['terminal'] = {}
    for mode in ('light', 'dark'):
        colors = {key: source['modes'][mode]['tokens'][key]['hex']
                  for key in source['order']}
        for value in [*colors.values(), source['terminal'][mode]['cyan']]:
            if not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
                raise ValueError(f'Invalid color in {mode}: {value}')
        colors.update({key + '_soft': blend(colors['base'], colors[key], source['tint'][mode])
                       for key in ACCENTS})
        colors['cyan'] = source['terminal'][mode]['cyan']
        ansi = source['terminal'][mode]['ansi']
        if len(ansi) != 16:
            raise ValueError(f'{mode} must have 16 ANSI slots')
        colors['ansi'] = [colors[value] if not value.startswith('#') else value
                          for value in ansi]
        if any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', value) for value in colors['ansi']):
            raise ValueError(f'Invalid ANSI color in {mode}')
        palette['terminal'][mode] = colors
    return palette


def build_exports(palette):
    P = {key: value for key, value in palette.items() if key != 'terminal'}
    D = palette['terminal']
    data = palette
    files = []

    def add(app, mode, name, mime, content):
        files.append(dict(app=app, mode=mode, filename=name, mime=mime, content=content))

    def dumps(value):
        return json.dumps(value, indent=2) + '\n'
    add('Palette JSON', 'both', 'cosmic-latte.json', 'application/json', dumps(data))
    css = []
    for mode, selector in [('light', ':root'), ('dark', ':root[data-theme="dark"]')]:
        lines = ['  --ct-' + key.replace('_', '-') + ': ' + val + ';' for key, val in D[mode].items() if key != 'ansi']
        css.append(selector + ' {\n' + '\n'.join(lines) + '\n}')
    css.insert(1, '@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n' + '\n'.join(('    --ct-' + key.replace('_', '-') + ': ' + val + ';' for key, val in D['dark'].items() if key != 'ansi')) + '\n  }\n}')
    add('CSS variables', 'both', 'cosmic-latte.css', 'text/css', '/* Cosmic Latte: system default, or data-theme="light" / "dark". */\n' + '\n\n'.join(css) + '\n')
    ansi_keys = ['black', 'red', 'green', 'yellow', 'blue', 'purple', 'cyan', 'white', 'brightBlack', 'brightRed', 'brightGreen', 'brightYellow', 'brightBlue', 'brightPurple', 'brightCyan', 'brightWhite']
    for mode in ['light', 'dark']:
        t = D[mode]
        label = 'Cosmic Latte ' + mode.title()
        stem = 'cosmic-latte-' + mode
        win = {'name': label, 'background': t['base'], 'foreground': t['text'], 'cursorColor': t['text'], 'selectionBackground': t['halo'], **dict(zip(ansi_keys, t['ansi']))}
        add('Windows Terminal', mode, stem + '.windows-terminal.json', 'application/json', dumps(win))
        ghost = ['# ' + label, 'background = ' + t['base'], 'foreground = ' + t['text'], 'cursor-color = ' + t['text'], 'selection-background = ' + t['halo'], 'selection-foreground = ' + t['text']] + ['palette = ' + str(i) + '=' + c for i, c in enumerate(t['ansi'])]
        add('Ghostty', mode, label, 'text/plain', '\n'.join(ghost) + '\n')

        def color(h):
            return dict(zip(['Red Component', 'Green Component', 'Blue Component'], [int(h[i:i + 2], 16) / 255 for i in [1, 3, 5]]))
        iterm = {key: color(t[token]) for key, token in [('Background Color', 'base'), ('Foreground Color', 'text'), ('Cursor Color', 'text'), ('Cursor Text Color', 'base'), ('Selection Color', 'halo'), ('Selected Text Color', 'text')]}
        iterm.update({'Ansi ' + str(i) + ' Color': color(c) for i, c in enumerate(t['ansi'])})
        add('iTerm2', mode, stem + '.itermcolors', 'application/xml', plistlib.dumps(iterm, sort_keys=False).decode())
        sublime = {'name': label, 'globals': {'background': t['base'], 'foreground': t['text'], 'caret': t['text'], 'selection': t['halo'], 'selection_foreground': t['text'], 'line_highlight': t['surface']}, 'rules': [{'name': name, 'scope': scope, 'foreground': t[key]} for name, scope, key in [('Comments', 'comment', 'muted'), ('Keywords', 'keyword, storage', 'nebula'), ('Strings', 'string', 'aurora'), ('Numbers', 'constant.numeric', 'supernova'), ('Functions', 'entity.name.function, support.function', 'ion'), ('Types', 'entity.name.type, support.type', 'solar'), ('Decorators', 'entity.name.annotation', 'pink')]]}
        add('Sublime Text', mode, label + '.sublime-color-scheme', 'application/json', dumps(sublime))
        colors = {key: t[token] for key, token in {'editor.background': 'base', 'editor.foreground': 'text', 'editor.selectionBackground': 'halo', 'editor.lineHighlightBackground': 'surface', 'editorCursor.foreground': 'text', 'editorLineNumber.foreground': 'muted', 'editorLineNumber.activeForeground': 'text', 'sideBar.background': 'panel', 'sideBar.foreground': 'subtle', 'activityBar.background': 'panel', 'activityBar.foreground': 'text', 'activityBar.inactiveForeground': 'muted', 'statusBar.background': 'surface', 'statusBar.foreground': 'subtle', 'titleBar.activeBackground': 'panel', 'titleBar.activeForeground': 'text', 'tab.activeBackground': 'base', 'tab.activeForeground': 'text', 'tab.inactiveBackground': 'panel', 'tab.inactiveForeground': 'subtle', 'editorGroupHeader.tabsBackground': 'panel', 'panel.background': 'panel', 'panel.border': 'border', 'input.background': 'surface', 'input.foreground': 'text', 'input.border': 'border', 'focusBorder': 'nebula', 'button.background': 'nebula', 'button.foreground': 'base', 'list.activeSelectionBackground': 'halo', 'list.activeSelectionForeground': 'text', 'list.hoverBackground': 'halo', 'terminal.background': 'base', 'terminal.foreground': 'text', 'terminalCursor.foreground': 'text', 'terminal.selectionBackground': 'halo', 'editorError.foreground': 'supernova', 'editorWarning.foreground': 'solar', 'editorInfo.foreground': 'ion'}.items()}
        colors.update({'terminal.ansi' + k[0].upper() + k[1:]: c for k, c in zip(ansi_keys, t['ansi'])})
        settings = {'workbench.colorCustomizations': colors, 'editor.tokenColorCustomizations': {'textMateRules': [{'scope': scope, 'settings': {'foreground': t[key]}} for scope, key in [('comment', 'muted'), ('keyword', 'nebula'), ('storage', 'nebula'), ('string', 'aurora'), ('constant.numeric', 'supernova'), ('entity.name.function', 'ion'), ('support.function', 'ion'), ('entity.name.type', 'solar'), ('support.type', 'solar'), ('entity.name.annotation', 'pink')]]}, 'editor.semanticTokenColorCustomizations': {'enabled': True, 'rules': {'class': t['solar'], 'type': t['solar'], 'function': t['ion'], 'method': t['ion'], 'number': t['supernova'], 'string': t['aurora'], 'comment': t['muted']}}}
        add('VS Code settings', mode, stem + '.vscode-settings.json', 'application/json', dumps(settings))

    dark = D['dark']
    slack_keys = ['base', 'panel', 'nebula', 'base', 'halo', 'text',
                  'aurora', 'supernova', 'panel', 'text']
    add('Slack', 'dark', 'cosmic-latte-dark.slack.txt', 'text/plain',
        ','.join(dark[key] for key in slack_keys) + '\n')
    for file in files:
        slug = re.sub('[^a-z0-9]+', '-', file['app'].lower()).strip('-')
        file['id'] = 'download-' + slug + '-' + file['mode']
    return files


def page_css(palette, mode):
    colors = palette['terminal'][mode]
    roles = dict(bg='base', surface='surface', panel='panel', halo='halo',
                 line='border', fg='text', sub='subtle', mut='muted',
                 acc='nebula', onacc='base')
    return '  ' + ' '.join('--' + var + ':' + colors[key] + ';'
                           for var, key in roles.items())


def render_page(template, palette, files, standalone):
    manifest = {'schemaVersion': 1, 'name': palette['name'], 'files': []}
    replacements = {
        'PALETTE_JSON': json_text(palette),
        'LIGHT_CSS': page_css(palette, 'light'),
        'DARK_CSS': page_css(palette, 'dark'),
        'VERSION': palette['version'],
    }
    for file in files:
        href = ('data:' + file['mime'] + ';charset=utf-8,' + quote(file['content'], safe='')
                if standalone else 'downloads/' + quote(file['filename'], safe=''))
        manifest['files'].append({**{key: value for key, value in file.items()
                                    if key != 'content'}, 'href': href})
        label = ('Download JSON' if file['app'] == 'Palette JSON' else 'Download CSS'
                 if file['mode'] == 'both' else file['mode'].title())
        replacements['DOWNLOAD_' + file['id']] = (
            '<a class="download" id="' + file['id'] + '" href="' + html.escape(href, quote=True)
            + '" download="' + html.escape(file['filename'], quote=True)
            + '" data-format="' + file['mime'] + '" data-mode="' + file['mode']
            + '" aria-label="Download ' + html.escape(file['app'] + ' ' + file['mode'], quote=True)
            + '">' + label + '<span aria-hidden="true">↓</span></a>')
    slack = next(file['content'].strip() for file in files if file['app'] == 'Slack')
    replacements.update(SLACK_STRING=slack, SLACK_JSON=json.dumps(slack),
                        MANIFEST_JSON=json_text(manifest))
    replacements['PACKAGE_LINKS'] = '' if standalone else (
        '<div class="download-links"><a class="download" href="dist/cosmic-latte-'
        + palette['version'] + '.zip" download>Download all (ZIP)</a>'
        '<a class="download" href="dist/cosmic-latte-standalone.html" download>'
        'Download standalone HTML</a></div>')
    for key, value in replacements.items():
        template = template.replace('{{' + key + '}}', value)
    remaining = re.findall(r'\{\{[A-Za-z0-9_-]+\}\}', template)
    if remaining:
        raise ValueError('Unresolved template markers: ' + ', '.join(remaining))
    return template


def release_zip(files, standalone):
    """Stable metadata makes the same source produce the same ZIP bytes."""
    contents = {file['filename']: file['content'].encode('utf-8') for file in files}
    contents.update({'index.html': standalone.encode('utf-8'),
                     'LICENSE': (ROOT / 'LICENSE').read_bytes(),
                     'README.md': (ROOT / 'README.md').read_bytes()})
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)
    return output.getvalue()


def outputs():
    source = json.loads((ROOT / 'palette.json').read_text(encoding='utf-8'))
    palette = expand_palette(source)
    files = build_exports(palette)
    template = (ROOT / 'templates/index.html').read_text(encoding='utf-8')
    hosted = render_page(template, palette, files, standalone=False)
    standalone = render_page(template, palette, files, standalone=True)
    result = {'index.html': hosted.encode('utf-8'),
              'dist/cosmic-latte-standalone.html': standalone.encode('utf-8')}
    result.update({'downloads/' + file['filename']: file['content'].encode('utf-8')
                   for file in files})
    manifest = json.loads(re.search(r'id="download-manifest">\n(.*?)</script>', hosted, re.S).group(1))
    result['downloads/manifest.json'] = json_text(manifest).encode('utf-8')
    result['dist/cosmic-latte-' + palette['version'] + '.zip'] = release_zip(files, standalone)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='Check that generated files match the source, without writing')
    args = parser.parse_args()
    generated = outputs()
    stale = []
    for name, content in generated.items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    if stale:
        parser.exit(1, 'Generated files need rebuilding:\n' + '\n'.join(stale) + '\n')
    print(('Checked' if args.check else 'Built') + f' {len(generated)} files.')


if __name__ == '__main__':
    main()

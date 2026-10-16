"""Publish a local, linked documentation library without exposing the repository root.

Author: Brent Thompson <brent.thompson@ucf.edu>
Renders Markdown and copies allowlisted documentation artifacts into the existing viewer bundle.
Never imports pipeline modules, executes examples, or reads environment/private run settings.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import quote, unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/development/codebase-docs/webvowl'
EXTENSIONS = {'.md', '.json', '.jsonld', '.ttl', '.rq', '.png', '.jpg', '.svg', '.pdf'}


def build_library(root=ROOT, output=OUT):
    """Export public docs only; keep external links and resolve published local references."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if not (root / 'docs/README.md').is_file():
        raise ValueError('Documentation entry point docs/README.md is missing.')
    if not output.is_relative_to(root / 'outputs'):
        raise ValueError('Documentation output must stay inside repository outputs/.')
    output.mkdir(parents=True, exist_ok=True)
    templates = root / 'docs/ontology/viewer'
    for name in ('site-nav.css', 'site-nav.js', 'reviewer.css'):
        shutil.copy2(templates / name, output / name)
    paths = [path for path in (root / 'docs').rglob('*')
             if path.is_file() and path.suffix.lower() in EXTENSIONS
             and path.resolve().is_relative_to(root / 'docs') and 'viewer' not in path.relative_to(root / 'docs').parts]
    paths += [root / name for name in ('README.md', 'GEMINI.md', 'GEMINI_HYBRID.md', 'ONTOLOGY_REVISION.md') if (root / name).is_file()]
    paths += list((root / 'dpv_dashboard').glob('*.md'))
    paths = [path for path in paths if path.resolve().is_relative_to(root)]
    published = {path.resolve(): output / 'library' / path.relative_to(root) for path in paths}
    markdown = MarkdownIt('commonmark', {'html': False}).enable('table')
    records = []
    unresolved = set()
    source_snapshots = []

    # Publish only inventoried first-party code, never an arbitrary repository tree.
    inventory_path = root / 'docs/codebase/inventory.json'
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        items = inventory.get('files', []) if isinstance(inventory, dict) else inventory
        if not isinstance(items, list):
            raise ValueError('Code inventory must contain a list of files.')
        for item in items:
            name = item.get('path', '') if isinstance(item, dict) else ''
            source = (root / name).resolve()
            if (not source.is_relative_to(root) or source.suffix not in {'.py', '.ps1', '.sh', '.js', '.css', '.html', '.rq', '.ipynb'}
                    or any(part.startswith('.') or part in {'outputs', 'private'} for part in source.relative_to(root).parts)
                    or not source.is_file()):
                continue
            snapshot = output / 'source' / (source.relative_to(root).as_posix() + '.html')
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            lines = source.read_text(encoding='utf-8-sig').splitlines()
            code = ''.join('<span id="L' + str(i) + '"><a href="#L' + str(i) + '">' + str(i) + '</a>  ' + html.escape(line) + '</span>\n' for i, line in enumerate(lines, 1))
            body = '<h2>' + html.escape(name) + '</h2><p>Read-only source snapshot · SHA256 ' + hashlib.sha256(source.read_bytes()).hexdigest() + '</p>'
            body += '<pre style="overflow:auto;background:white;padding:18px"><code>' + code + '</code></pre>'
            # Render below, once the shared page shell is defined.
            source_snapshots.append((snapshot, body))

    def relative(target, page):
        return quote(os.path.relpath(target, page.parent).replace(os.sep, '/'), safe='/')

    def shell(title, body, page):
        prefix = relative(output, page).rstrip('/') + '/'
        return ('<!doctype html><!-- Author: Brent Thompson <brent.thompson@ucf.edu>; summary: read-only documentation. -->'
                '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>' + html.escape(title) + ' · UCF DPV</title>'
                '<link rel="stylesheet" href="' + prefix + 'reviewer.css"><link rel="stylesheet" href="' + prefix + 'site-nav.css"></head>'
                '<body><header><div class="documentation-heading"><a class="documentation-button" data-dashboard-link href="http://localhost:8056/">Dashboard</a>'
                '<div><p class="eyebrow">UCF DATA-ENABLED PHOTOVOLTAICS</p><h1>Documentation</h1></div></div>'
                '<div class="documentation-links"><a href="' + prefix + 'library.html">All documentation</a>'
                + ('<a href="' + prefix + 'index.html">Information journey &amp; WebVOWL</a>' if (output / 'index.html').is_file() else '')
                + '</div></header><main class="library-main">' + body + '</main><script src="' + prefix + 'site-nav.js"></script></body></html>')

    for snapshot, body in source_snapshots:
        snapshot.write_text(shell('Source reference', body, snapshot), encoding='utf-8')

    for path in sorted(paths):
        target = published[path.resolve()]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records.append({'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        if path.suffix != '.md':
            continue
        page = Path(str(target) + '.html')
        tokens = markdown.parse(path.read_text(encoding='utf-8-sig'))
        slugs = {}
        title = path.stem.replace('-', ' ').capitalize()
        has_title = False
        for i, token in enumerate(tokens):
            if token.type == 'heading_open':
                text = tokens[i + 1].content
                slug = re.sub(r'[^\w\s-]', '', text.lower()).replace(' ', '-')
                duplicate = slugs.get(slug, 0)
                slugs[slug] = duplicate + 1
                token.attrSet('id', slug + (f'-{duplicate}' if duplicate else ''))
                if token.tag == 'h1' and not has_title:
                    title = text
                    has_title = True
            for child in token.children or []:
                attr = 'href' if child.type == 'link_open' else 'src' if child.type == 'image' else None
                if not attr:
                    continue
                href = child.attrGet(attr) or ''
                link = urlsplit(href)
                if link.scheme or link.netloc or not link.path:
                    continue
                resolved = (path.parent / unquote(link.path)).resolve()
                destination = published.get(resolved)
                if resolved == root / 'docs/ontology/viewer/index.html' and (output / 'index.html').is_file():
                    destination = output / 'index.html'
                if destination and resolved.suffix == '.md':
                    destination = Path(str(destination) + '.html')
                if not destination and resolved.is_relative_to(root):
                    snapshot = output / 'source' / (resolved.relative_to(root).as_posix() + '.html')
                    if snapshot.is_file():
                        destination = snapshot
                if destination:
                    child.attrSet(attr, relative(destination, page) + ('#' + link.fragment if link.fragment else ''))
                else:
                    unresolved.add((path.relative_to(root).as_posix(), href))
                    # Keep the reference visible without an invented or repository-exposing URL.
                    child.attrSet(attr, '#unpublished-references')
                    child.attrSet('title', 'This local reference is not published in the documentation bundle: ' + href)
                    child.attrSet('class', 'unpublished-reference')
        content = markdown.renderer.render(tokens, markdown.options, {})
        note = ('<p id="unpublished-references" class="muted">Some local references point outside this documentation bundle. '
                'Their link tooltips retain the original reference; use the local repository for those files.</p>') if any(row[0] == path.relative_to(root).as_posix() for row in unresolved) else ''
        body = '<p class="documentation-breadcrumb"><a href="' + relative(output / 'library.html', page) + '">← Documentation library</a></p>'
        body += '<p class="documentation-source">' + html.escape(path.relative_to(root).as_posix()) + ' · <a href="' + relative(target, page) + '" download>Download source Markdown</a></p>'
        body += '<article class="documentation-article">' + content + note + '</article>'
        page.write_text(shell(title, body, page), encoding='utf-8')
        records[-1].update(title=title, page=page.relative_to(output).as_posix())

    groups = {}
    for record in records:
        if 'page' not in record:
            continue
        name = record['path']
        group = ('Codebase & agent guides' if name.startswith('docs/codebase/') else
                 'Ontology & validation' if name.startswith('docs/ontology/') else
                 'Pipeline stages' if name.startswith('docs/stages/') else 'Start here & dashboard')
        groups.setdefault(group, []).append(record)
    body = '<p class="library-intro">Explore how the workflow works, learn each stage, inspect the implementation, or follow concepts through the ontology. Choose a guide below or open the interactive information journey.</p>'
    if (output / 'index.html').is_file():
        body += '<p><a href="index.html">Open information journey &amp; WebVOWL →</a></p>'
    else:
        body += '<p class="warning">Interactive ontology views have not been exported yet. Follow the ontology guide to generate them; the full written documentation is available below.</p>'
    body += '<label class="library-search">Find documentation<input id="documentation-search" type="search" placeholder="Search titles, stage names or file paths" autocomplete="off"></label>'
    body += '<p id="documentation-count" role="status">' + str(sum(len(rows) for rows in groups.values())) + ' documents</p><div class="library-grid">'
    for name, rows in groups.items():
        body += '<section class="library-group"><h2>' + name + '</h2><ul>'
        for record in rows:
            body += '<li><a href="' + quote(record['page'], safe='/') + '">' + html.escape(record['title']) + '</a><small>' + html.escape(record['path']) + '</small></li>'
        body += '</ul></section>'
    body += '</div>'
    (output / 'library.html').write_text(shell('Documentation library', body, output / 'library.html'), encoding='utf-8')
    manifest = {'documents': len([r for r in records if 'page' in r]), 'files': records,
                'unpublished_references': [{'source': source, 'reference': ref} for source, ref in sorted(unresolved)]}
    (output / 'documentation-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'documents': manifest['documents'], 'files': len(records), 'unpublished_references': len(unresolved)}


if __name__ == '__main__':
    print(json.dumps(build_library()))

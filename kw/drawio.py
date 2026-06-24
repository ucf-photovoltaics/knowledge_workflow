# -*- coding: utf-8 -*-
"""
Draw.io diagram builder tool.

Builds concept-map .drawio files from a tagged concept DataFrame,
then embeds MDS-Onto and Cemento library pages as palette tabs.

Public API:
    build_drawio_xml(df, page_title)  -> ET.Element
    add_template_pages(mxfile_el)
    serialize_drawio(mxfile_el)       -> str
"""

import json
import math
import html as _html
from xml.etree import ElementTree as ET
from xml.dom import minidom

import pandas as pd

from kw.config import MDS_ONTO_LIBRARY, CEMENTO_TEMPLATES_LIBRARY

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
NODE_W         = 160
NODE_H         = 55
GAP_X          = 15
GAP_Y          = 15
GROUP_COLS_MAX = 8
GROUP_COLS_MIN = 3
HEADER_H       = 36
GROUP_PAD      = 12
GRID_GAP       = 55
MARGIN         = 60
CENTER_MIN_W   = 500
CENTER_MIN_H   = 400

# ---------------------------------------------------------------------------
# MDS-Onto vocabulary & colours
# ---------------------------------------------------------------------------
from kw.taxonomy import STUDY_STAGES, SUPPLY_CHAIN_LEVELS

_STAGE_COLORS: dict[str, tuple[str, str]] = {
    'synthesis':            ('#f4cccc', '#cc0000'),
    'formulation':          ('#fce5cd', '#e06c00'),
    'materials processing': ('#ead1dc', '#a64d79'),
    'sample':               ('#fff2cc', '#d6b656'),
    'tool':                 ('#dae8fc', '#3e7fc1'),
    'recipe':               ('#d5e8d4', '#82b366'),
    'data':                 ('#cfe2f3', '#4a86e8'),
    'data processing':      ('#f8cecc', '#b85450'),
    'result':               ('#d9ead3', '#38761d'),
    'analysis':             ('#e1d5e7', '#9673a6'),
    'modeling':             ('#ffe6cc', '#d79b00'),
    'results and metadata': ('#d0e0e3', '#006eaf'),
    'unclassified':         ('#f5f5f5', '#888888'),
    'unknown':              ('#ffffff', '#aaaaaa'),
}

_ZONE_TOP    = ['synthesis', 'formulation', 'materials processing', 'sample']
_ZONE_LEFT   = ['tool', 'data']
_ZONE_RIGHT  = ['recipe', 'data processing']
_ZONE_BOTTOM = ['result', 'analysis', 'modeling', 'results and metadata']
_ALL_ZONES   = _ZONE_TOP + _ZONE_LEFT + _ZONE_RIGHT + _ZONE_BOTTOM


def _stage_color(stage_str: str) -> tuple[str, str]:
    if not stage_str:
        return _STAGE_COLORS['unknown']
    first = stage_str.split(',')[0].strip().lower()
    return _STAGE_COLORS.get(first, _STAGE_COLORS['unknown'])


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------

def _node_value(concept: str, supply_level: str) -> str:
    tag_html = (
        '<br/><font style="font-size:9px;color:#555555;">'
        + supply_level
        + '</font>'
    ) if supply_level else ''
    return f'<b>{concept}</b>{tag_html}'


def _optimal_group_cols(n: int) -> int:
    if n <= GROUP_COLS_MIN:
        return max(1, n)
    cols = round(math.sqrt(n * 1.5))
    return max(GROUP_COLS_MIN, min(GROUP_COLS_MAX, cols))


def _group_dims(n: int) -> tuple[int, int, int]:
    n_cols = _optimal_group_cols(n)
    cols   = min(n_cols, max(n, 1))
    rows   = math.ceil(n / n_cols) if n > 0 else 1
    w = cols * (NODE_W + GAP_X) - GAP_X + 2 * GROUP_PAD
    h = rows * (NODE_H + GAP_Y) - GAP_Y + 2 * GROUP_PAD + HEADER_H
    return w, h, n_cols


def _add_swimlane(root_el, container_id, label, fill, stroke, gx, gy, gw, gh):
    c = ET.SubElement(root_el, 'mxCell', {
        'id':     container_id,
        'value':  label,
        'style':  (
            f'swimlane;startSize={HEADER_H};'
            f'fillColor={fill};strokeColor={stroke};strokeWidth=2;'
            f'fontFamily=Helvetica;fontSize=13;fontStyle=1;'
            f'rounded=1;arcSize=3;'
        ),
        'vertex': '1',
        'parent': '1',
    })
    ET.SubElement(c, 'mxGeometry', {
        'x': str(int(gx)), 'y': str(int(gy)),
        'width': str(int(gw)), 'height': str(int(gh)),
        'as': 'geometry',
    })
    return c


def _place_nodes(root_el, concept_rows, container_id, n_cols, stroke, cell_id_start):
    cell_id = cell_id_start
    for j, row in enumerate(concept_rows):
        nx     = GROUP_PAD + (j % n_cols)  * (NODE_W + GAP_X)
        ny     = HEADER_H  + GROUP_PAD + (j // n_cols) * (NODE_H + GAP_Y)
        supply = row.get('mds:supplyChainLevel', '')
        label  = _node_value(str(row['concept']), supply)
        node   = ET.SubElement(root_el, 'mxCell', {
            'id':     f'concept-{cell_id}',
            'value':  label,
            'style':  (
                'rounded=1;whiteSpace=wrap;html=1;'
                'align=center;verticalAlign=middle;'
                'fontFamily=Helvetica;fontSize=10;'
                'labelBackgroundColor=none;resizable=1;'
                f'fillColor=#ffffff;strokeColor={stroke};strokeWidth=1.5;'
            ),
            'vertex': '1',
            'parent': container_id,
        })
        ET.SubElement(node, 'mxGeometry', {
            'x': str(int(nx)), 'y': str(int(ny)),
            'width': str(NODE_W), 'height': str(NODE_H),
            'as': 'geometry',
        })
        cell_id += 1
    return cell_id


# ---------------------------------------------------------------------------
# Public: build concept-map page
# ---------------------------------------------------------------------------

def build_drawio_xml(df: pd.DataFrame, page_title: str = 'Concepts') -> ET.Element:
    """
    Build the concept-map diagram page from a tagged DataFrame and return
    the root mxfile ET.Element.  Call add_template_pages() before serialising.
    """
    # 1. Bucket concepts by primary study stage
    buckets: dict[str, list] = {s: [] for s in _ALL_ZONES + ['unclassified']}
    for _, row in df.iterrows():
        raw     = row.get('mds:studyStage', '')
        primary = raw.replace('mds:', '').split(',')[0].strip().lower() if raw else ''
        key     = primary if primary in buckets else 'unclassified'
        buckets[key].append(row)

    def zone_groups(zone):
        out = []
        for s in zone:
            rows = buckets.get(s, [])
            if rows:
                w, h, nc = _group_dims(len(rows))
                out.append((s, rows, w, h, nc))
        return out

    top_gs    = zone_groups(_ZONE_TOP)
    left_gs   = zone_groups(_ZONE_LEFT)
    right_gs  = zone_groups(_ZONE_RIGHT)
    bottom_gs = zone_groups(_ZONE_BOTTOM)

    def zone_row_dims(gs):
        if not gs: return 0, 0
        return (sum(w for _, _, w, _, _ in gs) + GRID_GAP * (len(gs) - 1),
                max(h for _, _, _, h, _ in gs))

    def zone_col_dims(gs):
        if not gs: return 0, 0
        return (max(w for _, _, w, _, _ in gs),
                sum(h for _, _, _, h, _ in gs) + GRID_GAP * (len(gs) - 1))

    top_w,    top_h    = zone_row_dims(top_gs)
    left_w,   left_h   = zone_col_dims(left_gs)
    right_w,  right_h  = zone_col_dims(right_gs)
    bottom_w, bottom_h = zone_row_dims(bottom_gs)

    # 2. Canvas and centre dimensions
    min_middle_w = (left_w + (GRID_GAP if left_w else 0)
                    + CENTER_MIN_W
                    + (GRID_GAP if right_w else 0) + right_w)
    inner_w  = max(top_w, bottom_w, min_middle_w)
    canvas_w = inner_w + 2 * MARGIN

    centre_w = max(
        inner_w - left_w - right_w
        - (GRID_GAP if left_w  else 0)
        - (GRID_GAP if right_w else 0),
        CENTER_MIN_W,
    )
    centre_h = max(left_h, right_h, CENTER_MIN_H)

    canvas_h = (2 * MARGIN
                + (top_h    + GRID_GAP if top_gs    else 0)
                + centre_h
                + (GRID_GAP + bottom_h if bottom_gs else 0))

    cx = MARGIN + left_w + (GRID_GAP if left_w else 0)
    cy = MARGIN + (top_h + GRID_GAP if top_gs else 0)

    # 3. Build XML
    mxfile  = ET.Element('mxfile', {'host': 'knowledge_workflow_v7', 'version': '1.0'})
    diagram = ET.SubElement(mxfile, 'diagram', {'name': page_title, 'id': 'kw-v7'})
    model   = ET.SubElement(diagram, 'mxGraphModel', {
        'dx': '1422', 'dy': '762',
        'grid': '1', 'gridSize': '10',
        'guides': '1', 'tooltips': '1', 'connect': '1', 'arrows': '1',
        'fold': '1', 'page': '1', 'pageScale': '1',
        'pageWidth':  str(max(int(canvas_w), 1600)),
        'pageHeight': str(max(int(canvas_h), 1200)),
        'background': '#ffffff', 'math': '0', 'shadow': '0',
    })
    root_el = ET.SubElement(model, 'root')
    ET.SubElement(root_el, 'mxCell', {'id': '0'})
    ET.SubElement(root_el, 'mxCell', {'id': '1', 'parent': '0'})
    cell_id = 2

    # 4. Centre blank workspace
    blank = ET.SubElement(root_el, 'mxCell', {
        'id':     'centre-blank',
        'value':  (
            '<font style="font-size:16px;color:#bbbbbb;">'
            '&#8592; Drag concepts here &#8594;'
            '</font>'
        ),
        'style':  (
            'rounded=1;whiteSpace=wrap;html=1;'
            'fillColor=#fafafa;strokeColor=#cccccc;strokeWidth=2;'
            'dashed=1;dashPattern=10 6;'
            'verticalAlign=middle;align=center;'
        ),
        'vertex': '1',
        'parent': '1',
    })
    ET.SubElement(blank, 'mxGeometry', {
        'x': str(int(cx)), 'y': str(int(cy)),
        'width': str(int(centre_w)), 'height': str(int(centre_h)),
        'as': 'geometry',
    })

    # 5. Helper: write one swimlane + its nodes
    def write_group(stage, rows, gx, gy, gw, gh, n_cols):
        nonlocal cell_id
        fill, stroke = _STAGE_COLORS.get(stage, _STAGE_COLORS['unknown'])
        cid = f'grp-{stage.replace(" ", "_").replace("-", "_")}'
        _add_swimlane(root_el, cid, f'mds:{stage}', fill, stroke, gx, gy, gw, gh)
        cell_id = _place_nodes(root_el, rows, cid, n_cols, stroke, cell_id)

    # 6. TOP zone
    if top_gs:
        x = MARGIN + max(0, (inner_w - top_w) // 2)
        for stage, rows, w, h, nc in top_gs:
            write_group(stage, rows, x, MARGIN, w, h, nc)
            x += w + GRID_GAP

    # 7. LEFT zone
    if left_gs:
        y = cy
        for stage, rows, w, h, nc in left_gs:
            write_group(stage, rows, MARGIN, y, w, h, nc)
            y += h + GRID_GAP

    # 8. RIGHT zone
    if right_gs:
        rx = cx + centre_w + GRID_GAP
        y  = cy
        for stage, rows, w, h, nc in right_gs:
            write_group(stage, rows, rx, y, w, h, nc)
            y += h + GRID_GAP

    # 9. BOTTOM zone
    if bottom_gs:
        by = cy + centre_h + GRID_GAP
        x  = MARGIN + max(0, (inner_w - bottom_w) // 2)
        for stage, rows, w, h, nc in bottom_gs:
            write_group(stage, rows, x, by, w, h, nc)
            x += w + GRID_GAP

    # 10. Unclassified overflow
    leftover = buckets.get('unclassified', [])
    if leftover:
        w, h, nc     = _group_dims(len(leftover))
        gy           = canvas_h - MARGIN + GRID_GAP
        fill, stroke = _STAGE_COLORS['unclassified']
        cid          = 'grp-unclassified'
        _add_swimlane(root_el, cid, 'mds:unclassified', fill, stroke, MARGIN, gy, w, h)
        cell_id = _place_nodes(root_el, leftover, cid, nc, stroke, cell_id)

    return mxfile


# ---------------------------------------------------------------------------
# Public: embed library palette pages
# ---------------------------------------------------------------------------

def _load_mxlibrary(path: str) -> list[dict]:
    with open(path, encoding='utf-8') as f:
        raw = f.read().strip()
    inner = raw.removeprefix('<mxlibrary>').removesuffix('</mxlibrary>')
    return json.loads(inner)


def _copy_geom_offset(src_cell: ET.Element, dst_cell: ET.Element, ox: float, oy: float) -> None:
    geom = src_cell.find('mxGeometry')
    if geom is None:
        return
    g_attrs = dict(geom.attrib)
    if 'x' in g_attrs: g_attrs['x'] = str(float(g_attrs['x']) + ox)
    if 'y' in g_attrs: g_attrs['y'] = str(float(g_attrs['y']) + oy)
    geom_el = ET.SubElement(dst_cell, 'mxGeometry', g_attrs)

    for pt in geom.findall('mxPoint'):
        pt_attrs = dict(pt.attrib)
        if 'x' in pt_attrs: pt_attrs['x'] = str(float(pt_attrs['x']) + ox)
        if 'y' in pt_attrs: pt_attrs['y'] = str(float(pt_attrs['y']) + oy)
        ET.SubElement(geom_el, 'mxPoint', pt_attrs)

    for arr in geom.findall('Array'):
        arr_el = ET.SubElement(geom_el, 'Array', dict(arr.attrib))
        for pt in arr.findall('mxPoint'):
            pt_attrs = dict(pt.attrib)
            if 'x' in pt_attrs: pt_attrs['x'] = str(float(pt_attrs['x']) + ox)
            if 'y' in pt_attrs: pt_attrs['y'] = str(float(pt_attrs['y']) + oy)
            ET.SubElement(arr_el, 'mxPoint', pt_attrs)


def _embed_library_page(
    mxfile_el: ET.Element,
    page_name: str,
    page_id:   str,
    items:     list[dict],
    cols:      int = 6,
    gap_x:     int = 20,
    gap_y:     int = 20,
    pad:       int = 30,
) -> None:
    rows_list  = [items[i:i + cols] for i in range(0, len(items), cols)]
    col_widths = [
        max((it['w'] for i, it in enumerate(items) if i % cols == c), default=120)
        for c in range(cols)
    ]
    row_heights = [max(it['h'] for it in row) for row in rows_list]

    pw = sum(col_widths) + gap_x * max(cols - 1, 0) + 2 * pad
    ph = sum(row_heights) + gap_y * max(len(rows_list) - 1, 0) + 2 * pad

    diagram = ET.SubElement(mxfile_el, 'diagram', {'name': page_name, 'id': page_id})
    model   = ET.SubElement(diagram, 'mxGraphModel', {
        'pageWidth':  str(max(int(pw), 800)),
        'pageHeight': str(max(int(ph), 600)),
        'background': '#ffffff',
        'grid': '0',
    })
    root_el = ET.SubElement(model, 'root')
    ET.SubElement(root_el, 'mxCell', {'id': '0'})
    ET.SubElement(root_el, 'mxCell', {'id': '1', 'parent': '0'})

    uid = 2
    for ri, row_items in enumerate(rows_list):
        oy = pad + sum(row_heights[:ri]) + gap_y * ri
        for ci, item in enumerate(row_items):
            ox = pad + sum(col_widths[:ci]) + gap_x * ci
            try:
                item_tree = ET.fromstring(_html.unescape(item['xml']))
            except ET.ParseError:
                uid += 10
                continue
            item_root = item_tree.find('root')
            if item_root is None:
                uid += 10
                continue

            children = [c for c in item_root if c.get('id') not in ('0', '1')]
            id_map: dict[str, str] = {}
            for child in children:
                old = child.get('id', '')
                id_map[old] = f'{page_id}-{uid}'
                uid += 1

            for child in children:
                new_id = id_map.get(child.get('id', ''), f'{page_id}-{uid}')
                if child.tag == 'UserObject':
                    attrs    = {k: v for k, v in child.attrib.items()}
                    attrs['id'] = new_id
                    user_el  = ET.SubElement(root_el, 'UserObject', attrs)
                    inner    = child.find('mxCell')
                    if inner is not None:
                        cell_attrs = {k: v for k, v in inner.attrib.items()}
                        cell_attrs.pop('id', None)
                        cell_attrs['parent'] = '1'
                        for a in ('source', 'target'):
                            if a in cell_attrs:
                                cell_attrs[a] = id_map.get(cell_attrs[a], cell_attrs[a])
                        ic_el = ET.SubElement(user_el, 'mxCell', cell_attrs)
                        _copy_geom_offset(inner, ic_el, ox, oy)
                else:
                    cell_attrs = {k: v for k, v in child.attrib.items()}
                    cell_attrs['id']     = new_id
                    cell_attrs['parent'] = '1'
                    for a in ('source', 'target'):
                        if a in cell_attrs:
                            cell_attrs[a] = id_map.get(cell_attrs[a], cell_attrs[a])
                    cell_el = ET.SubElement(root_el, 'mxCell', cell_attrs)
                    _copy_geom_offset(child, cell_el, ox, oy)


def add_template_pages(mxfile_el: ET.Element) -> None:
    """
    Embed the MDS-Onto library and Cemento templates as extra pages in the
    diagram.  Gracefully skips any library file that is not found.
    """
    specs = [
        (MDS_ONTO_LIBRARY,          'MDS-Onto Library',  'lib-mds-onto', 6),
        (CEMENTO_TEMPLATES_LIBRARY, 'Cemento Templates', 'lib-cemento',  2),
    ]
    for path, page_name, page_id, cols in specs:
        if not __import__('os').path.isfile(path):
            print(f'  [skip] library file not found: {path}')
            continue
        try:
            items = _load_mxlibrary(path)
            _embed_library_page(mxfile_el, page_name, page_id, items, cols=cols)
            print(f'  library  : "{page_name}" — {len(items)} items embedded')
        except Exception as exc:
            print(f'  [warn] could not embed {path}: {exc}')


# ---------------------------------------------------------------------------
# Public: serialise
# ---------------------------------------------------------------------------

def serialize_drawio(mxfile_el: ET.Element) -> str:
    """Return the mxfile as a pretty-printed draw.io XML string."""
    raw    = ET.tostring(mxfile_el, encoding='unicode')
    pretty = minidom.parseString(raw).toprettyxml(indent='  ')
    lines  = pretty.splitlines()
    if lines and lines[0].startswith('<?xml'):
        lines = lines[1:]
    return '\n'.join(lines)

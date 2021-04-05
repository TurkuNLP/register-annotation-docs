#!/usr/bin/env python3

import sys
import os
import json
import html
import logging

from tempfile import NamedTemporaryFile
from argparse import ArgumentParser


# Marker lines identifying where in markdown to insert generated material
GENERATED_START = '<!-- START GENERATED SCREENSHOT GALLERY -->'
GENERATED_END = '<!-- END GENERATED SCREENSHOT GALLERY -->'

# Templates for generated output
TOP_LEVEL_TEMPLATE = """
<!--     NOTE: this screenshot gallery is automatically generated.       -->
<!--     Please avoid modifying it manually: any changes will be         -->
<!--     overwritten the next time the generation script is run.         -->
<table class="website-examples">
  <thead>
    <tr>
      <th class="website-examples-col-1">Information</th>
      <th class="website-examples-col-2">Screenshot (hover or click to enlarge)</th>
    </tr>
  </thead>
  <tbody>
{}
  </tbody>
</table>
"""

IMAGE_INFO_TEMPLATE = """
    <tr>
      <td>
        {}
      </td>
      <td>{}</td>
    </tr>
"""

IMAGE_TEMPLATE = '<a href="{}"><img class="thumbnail" src="{}" alt="screenshot of {}"></a>'

URL_TEMPLATE = '<div class="img-url"><b>{}</b>: <a href="{}">{}</a></div>'

INFO_TEMPLATE = '<div class="img-info"><b>{}</b>: {}</div>'


logging.basicConfig()
logger = logging.getLogger(os.path.basename(__file__))


def argparser():
    ap = ArgumentParser()
    ap.add_argument('-m', '--markdown-dir', default='_register',
                    help='Directory with markdown files to modify')
    ap.add_argument('-s', '--screenshot-dir', default='static/screenshots',
                    help='Directory with screenshots in subdirectories')
    ap.add_argument('-v', '--verbose', default=False, action='store_true',
                    help='Verbose output')
    return ap


def atomic_replace(fn, content):
    tmp = NamedTemporaryFile(mode='wt', delete=False)
    tmp.write(content)
    tmp.close()
    os.rename(tmp.name, fn)    # POSIX rename is atomic


def files_by_suffix(directory, suffix):
    for fn in os.listdir(directory):
        if fn.endswith(f'.{suffix}'):
            yield os.path.join(directory, fn)


def find_index(lines, string):
    for i, line in enumerate(lines):
        if line.rstrip() == string.rstrip():
            return i
    return None


def get_information_for_screenshot(fn):
    rootfn = os.path.splitext(fn)[0]
    jsonfn = f'{rootfn}.json'
    if not os.path.exists(jsonfn):
        logger.warning(f'JSON file {jsonfn} not found, no info for {fn}')
        return {}
    with open(jsonfn) as f:
        data = json.load(f)
    return data


def generate_screenshot_gallery(img_infos):
    img_content = []
    for fn, info in img_infos:
        base = os.path.basename(fn)
        root = os.path.splitext(base)[0]
        path = os.path.join('..', fn)
        img_html = IMAGE_TEMPLATE.format(path, path, root)
        info_htmls = []
        for k, v in info.items():
            k, v = html.escape(k), html.escape(v)
            if k.lower() == 'url':
                info_htmls.append(URL_TEMPLATE.format(k, v, v))
            else:
                info_htmls.append(INFO_TEMPLATE.format(k, v))
        info_html = '\n        '.join(info_htmls)
        img_info_html = IMAGE_INFO_TEMPLATE.format(info_html, img_html)
        img_content.append(img_info_html.strip('\n'))
    return TOP_LEVEL_TEMPLATE.format('\n'.join(img_content)).lstrip('\n')


def update_markdown_file(fn, options):
    with open(fn) as f:
        lines = f.readlines()

    start = find_index(lines, GENERATED_START)
    end = find_index(lines, GENERATED_END)
    if start is None:
        raise ValueError(f'failed to find start marker "{GENERATED_START}"')
    if end is None:
        raise ValueError(f'failed to find end marker "{GENERATED_END}"')

    base = os.path.splitext(os.path.basename(fn))[0]
    ssdir = os.path.join(options.screenshot_dir, base)
    if not os.path.isdir(ssdir):
        raise FileNotFoundError(f'no screenshot directory {ssdir}')

    img_infos = []
    for img_fn in files_by_suffix(ssdir, 'png'):
        info = get_information_for_screenshot(img_fn)
        img_infos.append((img_fn, info))

    if img_infos:
        content = generate_screenshot_gallery(img_infos)
    else:
        content = ''

    old_content = ''.join(lines[start+1:end])
    if content == old_content:
        logger.info(f'current content matches data for {fn}, not updating.')
        return 0
    else:
        pre, post = ''.join(lines[:start+1]), ''.join(lines[end:])
        atomic_replace(fn, pre + content + post)
        logger.info(f'rewrote screenshot gallery for {fn}')
        return 1


def main(argv):
    args = argparser().parse_args(argv[1:])
    if args.verbose:
        logger.setLevel(logging.INFO)

    updated, total = 0, 0
    for fn in files_by_suffix(args.markdown_dir, 'md'):
        try:
            updated += update_markdown_file(fn, args)
        except Exception as e:
            logger.warning(f'Failed processing {fn}: {e}')
        total += 1
    print(f'Done, updated {updated}/{total} files')


if __name__ == '__main__':
    sys.exit(main(sys.argv))

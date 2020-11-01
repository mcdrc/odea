#!/usr/bin/env python3

"""
This is a processing script that can be run as command-line or called from a drop target script.

Type `odea -h` for help.
"""

import sys
import os
import argparse
import pathlib
import re
import subprocess

import odea

def check_file(fn):
    # <fn> can be a file or a directory representing a multi-file item, such
    # as a collection of video clips or a web page with associated media.
    # Currently we assume that a file within a uuid-tagged directory should
    # be considered an Item "subfile", and not renamed.

    if fn is None or fn == '':
        sys.exit("No input file")
    if os.path.isfile(fn):
        p = pathlib.Path(fn).resolve()
        if re.search(odea.RE_UUID, str(p.parents[0])):
            return 'subfile'
        return 'file'

    # if os.path.isdir(fn) and fn.endswith('.dir'):
    #     return 'dir'
    # if os.path.isdir(fn) and fn.endswith('.vclips'):
    #     return 'vclips'

    sys.exit('Specify a valid input filename.')

def update_file(fn):
    """Update a filename, hash, metadata, and thumb for a file."""
    filetype = check_file(fn)

    f = odea.load_file(fn)
    f.tag()

    # N.B. basename gets updated each time we load the file, to capture changes
    # to the filename on disk. The slug will propagate to derivatives, but if
    # we change the source filename on disk we will end up with duplicate
    # derivatives and thumbnails, which will need to be garbage-collected.
    if f.format == 'SRC':
        slug = f.slug()
        if slug != f.basename:
            f.original_name = f.filename
            f.basename = slug

    # TODO: Files within directories (capture parent UUID)
    if filetype == 'subfile':
        f.identifier = None
    # NOT YET IMPLEMENTED: Tag directories
    if filetype == 'file':
        f.rename()
    f.get_sha256()
    f.get_mtime()
    f.get_size()
    # We may want to generate a thumb manually from a derivative
    # e.g., from the poster for a podcast
    if f.format == 'SRC':
        f.thumbs()
    f.save()
    return f

def update(fn):
    """Update a file and the parent item metadata."""

    f = update_file(fn)
    i = odea.load_item(f.identifier)

    if not i.title:
        i.title = f.basename.replace('_', ' ').rpartition(os.sep)[2]
    i.save()
    # the filename may now be different if the source was tagged
    return f.filename


def edit(fn):
    """Return a file's item metadata tag file."""

    f = odea.load_file(fn)
    i = odea.load_item(f.identifier)
    i.save() # wrap lines...
    subprocess.run(['editor', i.tag_file()])


def derive(fn):
    """Generate derivatives for a file."""
    check_file(fn)
    f = odea.load_file(fn)
    o = list()
    ext = f.ext.lower()

    ## html, plain text
    if ext in ('html', 'htm', 'txt', 'rst'):
        update_file(f.derive('df-img-screenshot', 'png'))
        # update_file(f.derive('df-pdf-wkhtml', 'pdf'))

    ## Markdown (we can also do this for plain text)
    if ext in ('md'):
        update_file(f.derive('df-pandoc-html', 'html'))

    ## reStructuredText
    if ext in ('rst'):
        update_file(f.derive('df-docutils-html', 'html'))

    ## raster image
    if ext in ('bmp', 'gif', 'jpg', 'jpeg', 'png', 'tif', 'tiff'):
        update_file(f.derive('df-img-med', 'png'))
        update_file(f.derive('df-img-lg', 'png'))

    ## audio file
    if ext in ('mp3', 'wav', 'wma', 'ogg'):
        update_file(f.derive('pf-wav', 'wav'))
        update_file(f.derive('df-mp3', 'mp3'))

    ## office document
    if ext in ('odt', 'odp', 'doc', 'docx', 'ppt', 'pptx'):
        update_file(f.derive('df-pdf-doc', 'pdf'))

    ## vector image
    if ext in ('eps', 'svg'):
        update_file(f.derive('pf-vector', 'svg'))
        update_file(f.derive('df-pdf-vector', 'pdf'))

    ## video
    if ext in ('avi', 'flv', 'mov', 'mpeg', 'mp4', 'webm', 'ogv'):
        update_file(f.derive('df-360p-vp9-400k', 'webm'))
        update_file(f.derive('df-h264', 'mp4'))

        # This is in the thumbs function
        # update_file(f.derive('df-img-still', 'jpg', frame))

def publish(fn):
    """Create the HTML item description page matching a file."""
    check_file(fn)
    f = odea.load_file(fn)
    i = odea.load_item(f.identifier)
    html_file = os.path.join('html', '{}.html'.format(i.identifier))
    with open(html_file, 'w') as out:
        out.write(i.html())

def index(path):
    """Update the HTML bag (collection) index"""

    try:
        os.chdir(odea.get_root(path))
    except:
        sys.exit("Could not change directory to {}".format(path))
    b = odea.load_bag()
    html_file = os.path.join('html', '{}.html'.format(b.identifier))
    with open(html_file, 'w') as out:
        out.write(b.html())
    # link <uuid>.html to index.html for convenience
    index_file = os.path.join('html', 'index.html')
    if os.path.exists(index_file):
        os.unlink(index_file)
    os.link(html_file, index_file)

def main():
    parser = argparse.ArgumentParser(
            description='Command-line interface to the odea toolkit.')

    parser.add_argument('--new', metavar='DIR', action='store',
                    help='initialize a new collection in <DIR>')
    parser.add_argument('--update', action='store_true',
                    help='import or update data from a source file')
    parser.add_argument('--derive', action='store_true',
                    help='generate derivatives')
    parser.add_argument('--publish', action='store_true',
                    help='generate html item page for a source file')
    parser.add_argument('--edit', action='store_true',
                    help='open the item metadata page for a source file')
    parser.add_argument('--filename', action='store',
                    help='file to be processed by update/derive/publish, relative to the bag root')
    parser.add_argument('--index', action='store_true',
                    help='generate html index for the collection')
    parser.add_argument('--archive', action='store',
                    help='the name of the archive, for Bag creation',
                    default='Digital Archive')

    args = parser.parse_args()

    if args.new:
        odea.new(args.new, archive=args.archive)

    if (args.update or args.derive or args.publish or
                args.index) and not args.filename:
        sys.exit("Please provide an input filename/path.")

    if args.update:
        args.filename = update(args.filename)

    if args.derive:
        derive(args.filename)

    if args.edit:
        edit(args.filename)

    if args.publish:
        publish(args.filename)

    if args.index:
        index(args.filename)

if __name__ == "__main__":
    main()

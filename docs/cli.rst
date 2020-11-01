.. _command-line-interface:

Command-line tool
===================

Command-line interface to the odea toolkit.

This tool takes a single filename (path) as its input, representing
a source file within a BagIt archival collection managed by odea, and will
update the Bag structure according to the options given.

.. code-block::

    usage: odea [-h] [--new DIR] [--update] [--derive] [--publish]
                [--filename FILENAME] [--index] [--archive ARCHIVE]
                [--baseurl BASEURL] [--license LICENSE]

The ``--filename`` argument is required for ``--update``,
``--derive``, and ``--publish`` commands.

Available options are:

    --new DIR   initialize a new collection in <DIR>
    --update    tag the file and create or update the file and item metadata
    --derive    create derivatives
    --publish   create an html description page for the corresponding item
    --filename FILENAME  file to be processed by update/derive/publish
    --index     update the collection html index with information about the
                corresponding item
    --archive ARCHIVE  the name of the archive, for html and bag-info.json
    --baseurl BASEURL  the base URL for the archive, for html output
    --license LICENSE  license or copyright text for html output

``--new``
----------

The ``--new`` command creates a new directory structure in the given directory.
The command will fail if the given path is not a valid directory path. If
the ``--archive`` flag is given, the archive name will be added to the file
``bag-info.json`` on creation.

.. code-block::

   $ odea --new .
   $ tree
   .
   ├── bag-info.json
   ├── bagit.txt
   ├── data
   │   └── deriv
   ├── file_metadata
   ├── html
   └── item_metadata

   5 directories, 2 files


``--update``
--------------

The ``--update`` command will perform the following operations.

1.  "Tag" a new file by adding a uuid string to the filename and the string
    "SRC" as its format, such that the file is renamed to the format
    ``<basename>.SRC.<uuid>.ext``. If any of the parent directories contain a
    uuid in the directory name, the file is considered to be part of a multi-
    file item (such as a web page with associated media), and will not be
    renamed.

2.  Create a new json metadata document for the file, if one does not yet exist.

3.  Obtain the sha256 hash, modification time, and size of the file and add
    these to the json metadata. If no title is present, use the basename of the
    input filename as the title, replacing underscores with spaces.

4.  Create thumbnail images for the file.

The command requires an input file set by ``--filename``, representing a
source item in the payload directory.

``--derive``
------------

The ``--derive`` command will generate derivatives based on a mapping of input
filename extension to derive functions. The following list indicates the
derivatives that will be generated for each recognized input file type.

   list of urls (.url)
        - pf-webarc (.webarc directory)

   plain text markup (.md, .txt)
        - df-pandoc-html

   ReStructuredText (.rst)
        - df-docutils-html

   raster image (.bmp, .gif, .jpg, .jpeg, .png, .psd, .tif, .tiff)
        - df-med-img (.png)
        - df-lg-img (.png)

   audio file (.mp3, .wav, .wma, .ogg)
        - pf-wav
        - df-mp3

   office document (.odt, .odp, .doc, .docx, .ppt, .pptx)
        - df-pdf-doc

   vector image (.eps, .svg)
        - pf-vector (.svg)
        - df-pdf-vector

   video (.avi, .flv, .mov, .mpeg, .mp4, .webm, .ogv)
        - df-360p-vp9-400k (.webm)
        - df-video-still (.jpg)
        - df-h264 (.mp4)

The above rules should cover the majority of input file types and use cases.
For advanced file processing, custom scripts can be built using the odea python
library.

The command requires an input file set by ``--filename``, representing a
source item in the payload directory.

``--publish``
------------------

The ``--publish`` command will generate an html description page for an
item in the archive. The page will be stored in the ``html`` directory in
the bag root, with the name ``<uuid>.html`` corresponding to the item
identifier.

The command requires an input file set by ``--filename``, representing a
source item in the payload directory.

``--index``
------------------

The ``--index`` command will generate an html index for the collection as a
whole, using metadata from the file ``bag-info.json`` in the collection
root.

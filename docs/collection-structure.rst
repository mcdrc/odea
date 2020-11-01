Collection structure
======================


Filenames
-----------------

Odea is built to expect filenames to have a consistent format, made up of
dot-separated "tags". The basename and extension are always required, but other
elements are optional.

Odea includes tools that can parse filenames and rename files; this happens
automatically using the command-line script or drop targets.

Filename format:
    ``<basename>[.<format-tag>][.<uuid>].<extension>``

Components:
    ``<basename>``
        The descriptive base part of the filename. For instance, the basename
        of file ``foo.jpeg`` would be ``foo``.
    ``<format-tag>``
        A tag indicating the archival format of the file. In an archival
        collection each item will be expected to be stored in several formats,
        belonging to three general types -- "original", "distribution", and
        "preservation". The format tag is expected to consist of a prefix
        corresponding to one of these three types (``SRC``, ``df-``, or
        ``pf-``), followed by a descriptive part describing the format of the
        file.
    ``<uuid>``
        The UUID (Universally Unique IDentifier) identifies a specific item,
        and will be applied identically to all files corresponding to that item
        (i.e., the original resource, its metadata document, a thumbnail image,
        etc.).
    ``<extension>``
        The file extension indicates the digital filetype. For instance, the
        extension of file ``foo.jpeg`` would be ``jpeg``. Odea requires
        extensions for all item files, but also recognizes dummy extensions
        such as ```dir`` and ``vclips`` to indicate that a directory itself is
        an item.

.. seealso:: :py:meth:`odea.File.tag` -- includes examples of how filenames are parsed, in Python code


BagIt structure
-----------------

Odea will assist in organizing a collection of files into a BagIt_ standard-compliant structure , consisting of a set of metadata files and a ``data/`` directory containing your original files. The figure below illustrates the basic structure of a Bag that contains one item, originally named ``MyVideo.mp4``, which has been tagged with the UUID ``91659ab8-0c66-4d86-adb1-b7a2f2ae51a6``::

    myCollection/
        data/
            MyVideo.SRC.91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.mp4
            deriv/
                MyVideo.df-h264.91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.mp4
        file_metadata/
            91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.SRC.json
            91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.df-h264.json
        html/
            91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.html
            index.html
        item_metadata/
            91659ab8-0c66-4d86-adb1-b7a2f2ae51a6.json
        thumb/
            2f9c41fc986a7eb211e20002ab5b5e68-256x256.jpeg
            2f9c41fc986a7eb211e20002ab5b5e68-800x600.jpeg
        bagit.txt
        bag-info.json
        manifest-sha256.txt

Payload
..........

The ``data/`` directory contains the "payload" of the Bag. All resources that
are ingested into the archive should be placed here. There are no restrictions
on the layout of this structure; any number of subdirectories is possible.

Within the ``data/`` directory, the ``deriv/`` subdirectory is used by Odea
to store derived versions of the source files in distribution or preservation
formats.

Collection metadata
......................

The ``bag-info.json`` file contains metadata about the collection as a whole.
It contains Dublin Core metadata fields. This file substitutes for the optional
``bag-info.txt`` metadata file described in the BagIt_ standard.

The following metadata elements are supported (note the "Bag" prefix is used
internally but not included in json output).


Item metadata
......................

The json files under ``item_metadata/`` describe the items in the collection --
in this case, the resource "MyVideo". Each file contains Dublin Core metadata
fields, as well as a field listing a remote URL for the resource.


An example of an item metadata file:

.. code-block:: json

   {
      "contributor": null,
      "coverage": "Mongolia, early 21st Century",
      "creator": [
          "Odgerel, J.",
          "Altantsetseg, M."
      ],
      "date": "2019",
      "dcmi_type": "Text",
      "description": "This book describes cashmere production ...",
      "identifier": "949ed637-7870-4bb3-9cfb-2d976fdeffc1",
      "language": "en",
      "publisher": null,
      "relation": null,
      "remote_embed_url": null,
      "rights": "Creative Commons BY-NC 4.0 License",
      "source": null,
      "subject": [
          "Mongolia",
          "cashmere",
          "pastoralism",
          "goats"
      ],
      "title": "Cashmere Industry in Mongolia"
   }

File metadata
......................

The json files under ``file_metadata/`` describe the actual files that make up
each item, including both originals and derived files. The metadata includes
the file size, modification timestamp, checksum, and other information that is
extracted automatically by Odea. These files do not need to be edited manually.


Other tag files
..................

The ``fetch.txt`` file is not created automatically, but can be generated and
updated with Odea commands. The "fetch" file is used within BagIt to transmit
a list of remote files that can be downloaded by a client to reproduce an
archival collection.

The file ``manifest-sha256.txt`` or ``manifest-sha512.txt`` is a list of checksums, used in validating the
integrity of the collection. It only lists files within the payload directory;
metadata files, thumbnails, etc. are not included.

Other directories
...................

The ``thumb/`` directory contains thumbnail images for the payload items, used
primarily in HTML output.

The ``html/`` directory contains web-publishable metadata description pages
for items in the collection, as well as an index to the collection as a whole.
These description pages are generated from the json input.

.. _BagIt: https://tools.ietf.org/html/rfc8493

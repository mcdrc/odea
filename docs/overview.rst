================================================
Odea: Open Digital Ethnography Archives toolkit
================================================

This software toolkit is designed to support the management of living collections of ethnographic documents, organized using the BagIt_ archival standard.

The first design goal is to **provide tools that support the "open" management of archival documents**. Odea includes tools for storage, indexing, validation, conversion to distribution and storage formats, and metadata cataloguing of archival records, which build on open file formats and technologies. All records remain accessible from the computer file system (i.e., not locked into a database) and open to manipulation with other tools.

The second design goal is to **support a workflow in which ethnographic documents can be created and managed directly in the field**. In this respect, odea differs from the many robust software systems that already exist for managing digital archives (e.g., Archivematica_, Atom_, Dspace_, ArchivesSpace_, Omeka_), which are web-based and require access to a centralized repository. Odea intends to be usable with small, distributed, offline collections that can be modified in-place. Metadata and other archival files are created alongside normally-organized sets of files on disk, such that archival processes can be undertaken as part of the research workflow itself -- rather than as a post-research stage.

.. _Archivematica: https://www.archivematica.org/en/
.. _Atom: https://www.accesstomemory.org/en/
.. _Dspace: https://duraspace.org/dspace/
.. _ArchivesSpace: https://archivesspace.org/
.. _Omeka: https://omeka.org

.. Seealso:: :ref:`design-goals`


Components
------------

Odea includes the following components.

1. A **python library**. This can used in scripting or an interactive console, if you are familiar with python programming. The documentation for this module contains a full overview

2. A **command-line tool**. This tool incorporates most of the functionality of the python library into a standard set of operations: “update” (tag files and create metadata records for them), “derive” (create copies of files for distribution or preservation), “publish” (create html versions of the metadata records), and “index” (create an html index for the collection as a whole).

3. Model **drop targets**. By selecting one or more source files in a collection then dragging and dropping them onto a target script located on your desktop, the command-line tool will be called to process each of the selected files in sequence. These scripts can, for example, rename files to include unique identifiers, generate derivative copies of files, create metadata templates, and produce html record description documents for the selected items. The drop targets can be edited to provide variables such as the name and address of the archive.

.. Seealso::

   :ref:`python-library` (the Python library)

   :ref:`command-line-interface`

   :ref:`drop-targets`


Design decisions
------------------

The program makes the following decisions about the structure and organization of an archival collection.

**Collections are contained in BagIt_ format bags.**

    This allows resources to be accessed, edited, and shared using standard tools, since they are accessible directly from the filesystem -- you don’t need to go through a web server API or database to request and update records.

**Metadata records are stored in plain-text json files.**

    Json is machine-readable, supported by every major programming language, and also readable by humans. Although a json file is potentially more prone to user errors than a structured form, it is also much quicker to use: a full set of metadata files can open instantly in a plain text editor, for example, and multiple files can be updated simultaneously with a find-and-replace function. (Conversion between json and csv is also trivial, if it is desirable to use spreadsheets for metadata entry or distribution.)

**Metadata records for items and collections use unqualified Dublin Core elements.**

    This set of terms is large enough to capture the necessary information about each record, yet small enough that complete metadata records can be prepared for each item. `Dublin Core`_ is widely used as an international standard in libraries and on the web. Mappings also exist between Dublin Core and archival metadata standards such as `ISAD(G)`_.

**UUIDs are used as item identifiers.**

    As UUIDs_ are easy to generate and (for practical purposes) globally unique, they can be applied to items in such a way that collections may be prepared in a distributed way without needing to consult a central authority to generate identifiers for new records. Whereas other archival systems may rely on file content hashes to identify each record in a persistent way, we are assuming that “living” or “in-progress” resources within the archive may continue to be modified even after their metadata records have been generated. We also expect that for each item/UUID there may be several files representing different formats or components of the resource.

**Filenames within the collection are “tagged” to include their UUID and type format.**

    This allows files to be added, moved, or updated, but still available to be located efficiently using filename-based searches (including web searches). There is no need to create or update an index of files.

**Distribution and preservation copies are generated for each resource, using open and future-proof formats.**

    Scripts and a mapping for standard conversions are built into odea, relying on open-source tools and archival best practices. Advanced users can modify or extend these rules by building on the variables set by the python module.

Philosophy
------------

Several of these design decisions follow on the expectation is that the archive will a “living collection”, rather than a set of documents that is placed in a box and kept in static form. This approach supports a mode of ethnographic production that focuses on collection and commentary as concurrent activities, which occur largely in the field, and which may involve the participation of many collaborators. It is guided by an understanding that original field records can and should be meaningful to collaborators in the field, who are not simply “informants” but co-creators of notes, diagrams, photographs, videos, and interviews. Although our presence as ethnographic field researchers follows a mandate to collect and interpret documentary resources in our own way, we can also assume an ethical obligation to preserve and share those materials in ways that are accessible to collaborators in the long term, and that accommodate commentary by others.


.. _BagIt: https://tools.ietf.org/html/rfc8493
.. _Dublin Core: http://dublincore.org/documents/dcmi-terms/
.. _ISAD(G): https://www.ica.org/en/isadg-general-international-standard-archival-description-second-edition
.. _UUIDs: https://en.wikipedia.org/wiki/Universally_unique_identifier

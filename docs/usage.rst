Basic Usage
============

Overview
---------

If you have not already done so, download the drop-target to a convenient location on your computer (see :ref:`drop-targets`).

The most basic workflow is:

1. Create a collection and add some files.

2. Register files by selecting and sending them to an "update" target.

3. Edit the item metadata.

4. (Optional) To generate HTML versions of the item records, select the source items then send them the "publish" drop target.


Create a collection
---------------------

To get started, you can unzip and use the following template, which contains the necessary files and directories for an odea collection: :download:`odea_collection_template.zip <../static/odea_collection_template.zip>`. This will give you a "data" payload directory to contain the collection files, as well as some subdirectories and a ``bag-info.txt`` file::

   my-collection/
      bag-info.txt
      bagit.txt
      data/
         files...

You should edit ``bag-info.txt`` to provide a title, description, and other details about the collection. Note that the "identifier" field in the template
contains a nil UUID, which should be changed to something meaningful.

Per the BagIt standard, your collection root will also contain a file ``bagit.txt`` with the following text::

   BagIt-Version: 1.0
   Tag-File-Character-Encoding: UTF-8


Ingest new files
------------------

You can now place your source files inside the ``data`` directory created in
the previous step.

If everything is installed correctly, you should now be able to select one or more of the source files, drag-and-drop them onto the "odea-update" target (or use the "Send to... > odea_update" context menu), and wait for odea to process them.

Metadata files will be created in the collection directory (outside the payload directory). Derivative files will be created in a ``deriv`` subdirectory of the payload directory.

You can safely repeat the process for existing files; the metadata will not be overwritten, but any derivatives will be regenerated.


Edit metadata
---------------

Metadata files are in a simple text format, and can be edited in a plain-text editor.

Atom_ is a recommended open-source, cross-platform text editor that works well for this purpose. Atom will allow you to navigate a list of tag files in its Project sidebar, and will assist in completing parentheses and quotes.

If you navigate to collection root in your file explorer and right-click on the ``item_metadata`` subfolder, you should see the option to open the entire folder in Atom. You can locate the appropriate metadata file for each source item by matching the UUID in the file list.

.. _Atom: https://atom.io/


Publish html
-------------

You will need to enter the archive name, title, and url within the drop-target publish script. Drag and drop a **source file** from your collection onto the target script. Odea will read the metadata contained within the item tag file you saved, and will convert this to a formatted html page.

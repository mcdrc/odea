.. _design-goals:

Design goals
=============

odea aims primarily to support the management of open collections of ethnographic items.

An "ethnographic" collection might include fieldnotes, audiovisual recordings, photographs, transcripts, datasets, copies of official and ephemeral documents, or indeed any other type of digital object that could be created or collected by a socio-cultural researcher. These items need to be stored and annotated in a way that allows them to be referenced clearly in a research context. odea is built on the assumption that we intend such items to be made accessible to others, for purposes such as enabling the validation and scholarly reuse of the raw materials we have assembled.

odea is designed to augment existing ethnographic research workflows by operating on digital files *in situ* on disk: tagging item filenames with permanent identifiers, generating copies of data in long-term preservation formats, creating simple spreadsheets for the manual and automated recording of descriptive metadata, organizing collections and metadata into standard formats that can be parsed by other archival systems, and producing publishable catalogues.

Ethnographic collections have the characteristic of being created and accessed in the field, typically by an individual researcher. With this in mind, the main feature that distinguishes odea from other archival management software is its focus on facilitating interaction with *living collections* of digital objects.

Unlike server-based alternatives, odea allows you to continue working with your collection even after it has been "archived" -- building and reorganizing it in the field, without access to a central repository. Each file inserted into an odea collection remains a file on disk, not an object that needs to be retrieved from an external server, database, or rigidly organized storage volume. Each item filename is tagged with a unique and permanent ID, but otherwise it can be moved about and copied at will.

To work with objects in a collection -- or to build a new, "forked" collection for a different project -- all that is necessary is to have access to the collection folder on disk. The archival management tools that odea supplies impose simple, standard data transformations that don't require you to change your existing workflow, and do not require collaborators to use the same software as you.

odea is intended to be simple to use, and simple to automate. odea expects a willingness to work on the command line rather than through a graphical interface or web browser -- since typing or scripting frequent commands is almost always much more efficient than repeatedly opening graphical menus, forms, and widgets. The basic command set is fairly simple, however, and should be accessible to anyone who is wanting to use the program for serious purposes.

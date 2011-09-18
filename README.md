SIF exporter extension for Inkscape
===================================

svg2sif is an Inkscape extension that converts SVG files to Synfig Animation
Studio (.sif) files.

Download
--------
To download a copy of svg2sif from GitHub, click on "Downloads" at the top of
the project page and select the download you want.

Alternatively, you can download the code by cloning the git repository:

```
$ git clone git://github.com/nikitakit/svg2sif.git
```

Installation
------------
Place the extension files (.py and .inx) in one of the following locations

To install for all users (may require root or administrator priviledges)

* Windows: "C:\Program Files\Inkscape\share\extensions"
* Linux: "/usr/share/inkscape/extensions"
* Mac OS X: "/Applications/Inkscape.app/Contents/Resources/extensions"

To install for one user only:

* Windows: "C:\Documents and Settings\user\Application Data\Inkscape\extensions"
* Linux: "/home/user/.config/inkscape/extensions"
* Mac OS X: "/Users/user/.config/inkscape/extensions"

Usage
-----

svg2sif adds a "Synfig Animation (*.sif)" option to Inkscape's "Save As" dialog.

If your SVG document contains clones or non-paths (text, rectangles, etc.)
the extension will quickly open another Inkscape window to convert these elements
to paths. *This may take a while*. The file **is not saved** until the status
bar reads "Document Saved."

If you save frequently, you can speed up the process by selecting
"Extensions>Synfig>Prepare for Export" from the Inkscape menu. This will convert
everything in the current document to paths (but may make it harder to edit).

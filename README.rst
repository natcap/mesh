MESH
====

Installing Paver
----------------

On Mac and Linux:

::
    $ pip install paver

On Windows, we have a few custom tweaks to paver that are required for this to
work properly.  You'll need `pip` and `git` available on the command-line

::
    $ pip install git+https://github.com/phargogh/paver@natcap-version


Building Binaries
-----------------

Dependencies:

  * paver (see above)
  * command-line git
  * virtualenv
  * pip

Run this from the command-line:

::
    $ paver build_bin

This will produce a directory of pyinstaller-generated binaries at `dist/mesh`,
and a zipfile of these binaries at `./mesh_binaries.zip`.

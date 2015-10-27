import sys
import os
from PyInstaller.compat import is_win

# Global Variables
current_dir = os.path.join(os.getcwd(), os.path.dirname(sys.argv[1]))

# Analyze Scripts for Dependencies
# Add the release virtual environment to the extended PATH.
# This helps IMMENSELY with trying to get the binaries to work from within
# a virtual environment, even if the virtual environment is hardcoded.
path_extension = []
if is_win:
    import distutils
    path_base = os.path.join('mesh_env', 'lib')
else:
    path_base = os.path.join('mesh_env', 'lib', 'python2.7')
path_base = os.path.abspath(path_base)    
path_extension.insert(0, path_base)
path_extension.insert(0, os.path.join(path_base, 'site-packages'))
print 'PATH EXT: %s' % path_extension

kwargs = {
    'hookspath': [os.path.join(current_dir, 'hooks')],
    'excludes': None,
    'pathex': path_extension,
    'hiddenimports': [
       'markdown',
       'distutils.dist',
    ],
}

cli_file = os.path.join(current_dir, '..', 'code', 'mesh.py')
a = Analysis([cli_file], **kwargs)

# Compress pyc and pyo Files into ZlibArchive Objects
pyz = PYZ(a.pure)

# Create the executable file.
# .exe extension is required if we're on Windows.
exename = 'mesh'
if is_win:
    exename += '.exe'

exe = EXE(
    pyz,

    # Taken from:
    # https://shanetully.com/2013/08/cross-platform-deployment-of-python-applications-with-pyinstaller/
    # Supposed to gather the mscvr/p DLLs from the local system before
    # packaging.  Skirts the issue of us needing to keep them under version
    # control.
    a.binaries + [
        ('msvcp90.dll', 'C:\\Windows\\System32\\msvcp90.dll', 'BINARY'),
        ('msvcr90.dll', 'C:\\Windows\\System32\\msvcr90.dll', 'BINARY')
    ] if is_win else a.binaries,
    a.scripts,
    name=exename,
    exclude_binaries=1,
    debug=False,
    strip=None,
    upx=False,
    console=True)

# Collect Files into Distributable Folder/File
args = [exe, a.binaries, a.zipfiles, a.datas]

dist = COLLECT(
        *args,
        name="mesh",
        strip=None,
        upx=False)

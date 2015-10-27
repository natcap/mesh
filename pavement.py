import shutil
import os

import paver.easy
import paver.virtual

paver.easy.options(
    virtualenv=paver.easy.Bunch(
        script_name='mesh_env_bootstrap.py',
        packages_to_install=open('requirements.txt').read().split(),
        dest_dir='mesh_env',
        system_site_packages=True
    )
)

@paver.easy.needs(['env'])
@paver.easy.task
def build_bin():
    """
    Build the MESH Pyinstaller binaries.
    """
    for dirname in ['dist', 'build']:
        if os.path.exists(dirname):
            shutil.rmtree(dirname)

    # Build the MESH pyinstaller binaries.
    @paver.virtual.virtualenv(paver.easy.options.virtualenv.dest_dir)
    def _build_bin():
        paver.easy.sh('pyinstaller exe/mesh.spec')
    _build_bin()

    # Zip up the binaries.
    shutil.make_archive(**{
        'base_name': 'mesh_binaries',
        'format': 'zip',
        'root_dir': 'dist/mesh_dist',
        'base_dir': 'mesh_binaries'})

@paver.easy.task
def env(options):
    """
    Set up a virtual environment to use for the paver binaries.
    """
    paver.virtual.bootstrap()
    paver.easy.sh('python ' + options.virtualenv.script_name)


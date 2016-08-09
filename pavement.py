import shutil
import os

import paver.easy
import paver.virtual

import natcap.versioner

paver.easy.options(
    virtualenv=paver.easy.Bunch(
        script_name='mesh_env_bootstrap.py',
        packages_to_install=open('requirements.txt').read().split(),
        dest_dir='mesh_env',
        system_site_packages=True
    ),
    build_bin=paver.easy.Bunch(
        no_zip=False
    )
)

@paver.easy.needs(['env'])
@paver.easy.task
@paver.easy.cmdopts([
    ('no-zip', '', "Don't zip up the binaries after building them."),
])
def build_bin(options):
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

    # Move directories around to match the expected settings/binaries
    # structure.
    os.makedirs('dist/mesh')
    shutil.move('dist/mesh_bin', 'dist/mesh/bin')
    shutil.copytree('settings', 'dist/mesh/settings')

    open('dist/mesh/mesh.bat', 'w').write(
        'CD bin\n'
        '.\\mesh.exe\n')

    # Zip up the binaries.
    if not options.build_bin.no_zip:
        shutil.make_archive(**{
            'base_name': 'mesh_binaries',
            'format': 'zip',
            'root_dir': 'dist'})

    hg_version = natcap.versioner.parse_version()
    disk_version = hg_version.replace('+', '-')

    hg_path = paver.easy.sh('hg paths', capture=True).rstrip()
    forkuser, forkreponame = hg_path.split('/')[-2:]
    if forkuser == 'natcap':
        forkname = ''
    else:
        forkname = forkuser

    # build the NSIS installer.
    nsis_params = [
        '/DVERSION=%s' % hg_version,
        '/DVERSION_DISK=%s' % disk_version,
        '/DFORKNAME=%s' % forkname,
        'mesh_installer.nsi',
    ]
    paver.easy.sh('makensis ' + ' '.join(nsis_params), cwd='exe')

@paver.easy.task
def env(options):
    """
    Set up a virtual environment to use for the paver binaries.
    """
    paver.virtual.bootstrap()
    paver.easy.sh('python ' + options.virtualenv.script_name)


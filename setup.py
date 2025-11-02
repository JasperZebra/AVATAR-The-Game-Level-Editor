from cx_Freeze import setup, Executable
import os
import sys
import glob
import multiprocessing

# Ensure freeze_support is called during build
if __name__ == '__main__':
    multiprocessing.freeze_support()

# Define the base directory
base_dir = os.path.abspath(os.path.dirname(__file__))

# Collect all files and folders recursively
def collect_files(directory):
    files = []
    for path, dirs, filenames in os.walk(directory):
        for filename in filenames:
            files.append((os.path.join(path, filename), os.path.relpath(os.path.join(path, filename), base_dir)))
    return files

# List all directories you want to include
directories_to_include = [
    'canvas',               # Canvas-related modules and resources
    'objects',              # Entity collections for import/export
    'tools',                # FCBConverter and other conversion tools
    'icon',
]

# Collect all files from these directories
include_files = []
for directory in directories_to_include:
    if os.path.exists(os.path.join(base_dir, directory)):
        include_files.extend(collect_files(os.path.join(base_dir, directory)))

# Add individual Python files that are part of your level editor
root_files = [
    'all_in_one_copy_paste.py',
    'data_models.py',
    'entity_editor.py',
    'entity_export_import.py',
    'file_converter.py',
    'hash_parser.py',
    'init.py',
    'main.py',
    'simplified_map_editor.py',
    '__init__.py',
    'camera_controller.py',
    'entity_renderer.py',
    'gizmo_renderer.py',
    'grid_renderer.py',
    'icon_renderer.py',
    'input_handler.py',
    'map_canvas_gpu.py',
    'opengl_utils.py',
    'default_i3.png',
    'default_i5.png'
]

for file in root_files:
    if os.path.exists(os.path.join(base_dir, file)):
        include_files.append((os.path.join(base_dir, file), file))

# Add any .exe files in tools directory with explicit destination paths
tools_exe_files = glob.glob(os.path.join(base_dir, "tools", "*.exe"))
for exe_file in tools_exe_files:
    filename = os.path.basename(exe_file)
    include_files.append((exe_file, f"tools/{filename}"))

# Add any .dll files that might be needed
dll_files = glob.glob(os.path.join(base_dir, "tools", "*.dll"))
for dll_file in dll_files:
    filename = os.path.basename(dll_file)
    include_files.append((dll_file, f"tools/{filename}"))

# Add any config files
config_files = glob.glob(os.path.join(base_dir, "tools", "*.config"))
for config_file in config_files:
    filename = os.path.basename(config_file)
    include_files.append((config_file, f"tools/{filename}"))
    
build_options = {
    'include_files': include_files,
    'packages': [
        # Standard libraries
        'os', 'sys', 'json', 'pathlib', 'typing', 'time', 'math', 'struct', 'copy', 'types',
        'xml', 'xml.etree', 'xml.etree.ElementTree', 'xml.parsers', 'xml.parsers.expat',
        'logging', 'subprocess', 'shutil', 'glob', 're', 'random', 'traceback',
        'importlib', 'inspect', 'collections', 'itertools',
        'tempfile', 'threading', 'queue', 'weakref', 'gc', 'codecs', 'locale', 'platform',
        'socket', 'urllib', 'urllib.parse', 'decimal', 'uuid', 'hashlib', 'base64',
        'binascii', 'io', 'contextlib', 'functools', 'operator', 'keyword', 'token', 'tokenize',
        
        # Multiprocessing packages (comprehensive)
        'multiprocessing',
        'multiprocessing.pool',
        'multiprocessing.connection',
        'multiprocessing.context',
        'multiprocessing.process',
        'multiprocessing.queues',
        'multiprocessing.reduction',
        'multiprocessing.synchronize',
        'multiprocessing.util',
        'multiprocessing.managers',
        'multiprocessing.sharedctypes',
        'multiprocessing.heap',
        'multiprocessing.popen_spawn_win32',
        
        # PyQt6 packages
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 
        'PyQt6.QtOpenGL', 'PyQt6.QtOpenGLWidgets', 'PyQt6.sip',
        'PyQt6.QtNetwork', 'PyQt6.QtPrintSupport', 'PyQt6.QtMultimedia',
        
        # OpenGL packages
        'OpenGL', 'OpenGL.GL', 'OpenGL.arrays',
        
        # Numerical packages
        'numpy',
        
        # Other dependencies
        'dataclasses', 'pkg_resources',
        
        # Root level modules (only the ones actually in root)
        'all_in_one_copy_paste',
        'data_models',
        'entity_editor',
        'entity_export_import',
        'file_converter',
        'hash_parser',
        'init',
        'main',
        'simplified_map_editor',
        
        # Canvas modules
        'canvas', 'canvas.__init__',
        'canvas.map_canvas_gpu', 'canvas.opengl_utils', 'canvas.entity_renderer',
        'canvas.grid_renderer', 'canvas.icon_renderer', 'canvas.gizmo_renderer', 
        'canvas.camera_controller', 'canvas.input_handler',
        
        # Tools package (contains converters including FCBConverter)
        'tools',
        
        # Objects package
        'objects',
    ],
    'excludes': [
        'test', 'unittest', 'tkinter', 'matplotlib', 'scipy',
    ],
    'include_msvcr': True,
    'optimize': 0,
    'zip_include_packages': ['encodings', 'importlib'],
    'bin_includes': [],
    'replace_paths': [('*', '')],
}

# Set up the executable
executables = [
    Executable(
        'main.py',  # Your main entry point
        base='Win32GUI' if sys.platform == 'win32' else None,  # GUI application
        target_name='Avatar_Level_Editor.exe',  # The name of your final executable
        icon='icon/avatar_icon.ico',  # Icon for the executable
    )
]

# Setup
if __name__ == '__main__':
    setup(
        name='Avatar Level Editor',
        version='1.1',
        description='Level Editor for Avatar: The Game - Edit maps, entities, and worldsectors',
        author='Jasper_Zebra',
        options={'build_exe': build_options},
        executables=executables
    )
    # Run this command to build: python setup.py build
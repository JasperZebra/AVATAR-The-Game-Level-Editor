#!/usr/bin/env python3
"""
Script to check the architecture (x86 or x64) of Windows executable files.
Reads the PE header to determine if an .exe or .dll is 32-bit or 64-bit.
"""

import struct
import sys
import os
from pathlib import Path

def check_pe_architecture(file_path):
    """
    Check if a PE (Portable Executable) file is 32-bit or 64-bit.
    
    Returns:
        str: 'x86' for 32-bit, 'x64' for 64-bit, or error message
    """
    try:
        with open(file_path, 'rb') as f:
            # Read DOS header
            dos_header = f.read(64)
            if len(dos_header) < 64:
                return "Error: File too small"
            
            # Check MZ signature
            if dos_header[0:2] != b'MZ':
                return "Error: Not a valid PE file (missing MZ signature)"
            
            # Get PE header offset (at position 0x3C in DOS header)
            pe_offset = struct.unpack('<I', dos_header[0x3C:0x3C+4])[0]
            
            # Seek to PE header
            f.seek(pe_offset)
            pe_signature = f.read(4)
            
            # Check PE signature
            if pe_signature != b'PE\0\0':
                return "Error: Not a valid PE file (missing PE signature)"
            
            # Read the Machine field from COFF header (2 bytes after PE signature)
            machine = struct.unpack('<H', f.read(2))[0]
            
            # Machine types:
            # 0x014c = IMAGE_FILE_MACHINE_I386 (x86)
            # 0x8664 = IMAGE_FILE_MACHINE_AMD64 (x64)
            # 0x0200 = IMAGE_FILE_MACHINE_IA64 (Itanium)
            # 0x01c4 = IMAGE_FILE_MACHINE_ARMNT (ARM)
            # 0xaa64 = IMAGE_FILE_MACHINE_ARM64 (ARM64)
            
            machine_types = {
                0x014c: 'x86 (32-bit)',
                0x8664: 'x64 (64-bit)',
                0x0200: 'IA64 (Itanium)',
                0x01c4: 'ARM (32-bit)',
                0xaa64: 'ARM64 (64-bit)',
            }
            
            return machine_types.get(machine, f'Unknown (0x{machine:04x})')
            
    except FileNotFoundError:
        return "Error: File not found"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    if len(sys.argv) > 1:
        # Check specific files provided as arguments
        files_to_check = sys.argv[1:]
    else:
        # Check all .exe and .dll files in tools directory
        tools_dir = Path('tools')
        if not tools_dir.exists():
            print("Error: 'tools' directory not found")
            print("Please run this script from your project root directory")
            return
        
        files_to_check = []
        files_to_check.extend(tools_dir.glob('*.exe'))
        files_to_check.extend(tools_dir.glob('*.dll'))
        
        if not files_to_check:
            print("No .exe or .dll files found in 'tools' directory")
            return
    
    print("=" * 70)
    print("Checking architecture of executable files...")
    print("=" * 70)
    print()
    
    results = {}
    max_filename_len = max(len(str(Path(f).name)) for f in files_to_check)
    
    for file_path in files_to_check:
        file_path = Path(file_path)
        if file_path.exists():
            arch = check_pe_architecture(file_path)
            results[file_path.name] = arch
            print(f"{file_path.name:<{max_filename_len + 2}} -> {arch}")
        else:
            print(f"{file_path.name:<{max_filename_len + 2}} -> File not found")
    
    print()
    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    
    x86_files = [name for name, arch in results.items() if 'x86 (32-bit)' in arch]
    x64_files = [name for name, arch in results.items() if 'x64 (64-bit)' in arch]
    error_files = [name for name, arch in results.items() if 'Error' in arch]
    
    print(f"32-bit (x86) files: {len(x86_files)}")
    if x86_files:
        for f in x86_files:
            print(f"  - {f}")
    
    print(f"\n64-bit (x64) files: {len(x64_files)}")
    if x64_files:
        for f in x64_files:
            print(f"  - {f}")
    
    if error_files:
        print(f"\nFiles with errors: {len(error_files)}")
        for f in error_files:
            print(f"  - {f}")
    
    print()
    print("=" * 70)
    print("Conclusion:")
    print("=" * 70)
    
    if x64_files and not x86_files:
        print("⚠️  All executables are 64-bit (x64)")
        print("    You CANNOT create a working 32-bit (x86) version of your level editor")
        print("    unless you obtain 32-bit versions of these tools.")
    elif x86_files and not x64_files:
        print("✓  All executables are 32-bit (x86)")
        print("   You can create both x86 and x64 versions of your level editor.")
        print("   (32-bit programs run on 64-bit systems)")
    elif x86_files and x64_files:
        print("⚠️  Mixed architectures detected!")
        print("    You have both 32-bit and 64-bit executables.")
        print("    This may cause compatibility issues.")
        print()
        print("    For x64 build: Replace 32-bit files with 64-bit versions")
        print("    For x86 build: Replace 64-bit files with 32-bit versions")
    else:
        print("No valid executable files found or all files had errors.")


if __name__ == '__main__':
    main()

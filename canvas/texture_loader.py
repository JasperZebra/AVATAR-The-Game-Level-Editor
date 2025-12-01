#!/usr/bin/env python3
"""
Texture loader for XBT files
Converts XBT textures to PNG format for GLTF embedding
"""

import os
import struct
import base64
from typing import Optional, Tuple

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: PIL/Pillow not available. Texture support disabled.")


class TextureLoader:
    """Load and convert XBT textures for GLTF"""
    
    def __init__(self, materials_path: str):
        """
        Initialize texture loader
        
        Args:
            materials_path: Path to the game's graphics/_materials folder
        """
        self.materials_path = materials_path
        print(f"Texture loader initialized with path: {materials_path}")
    
    def find_diffuse_texture(self, material_name: str) -> Optional[str]:
        """
        Find the diffuse texture for a material
        
        Args:
            material_name: Name of the material (e.g., "MAT_JAKE_BODY" or "GRAPHICS\_MATERIALS\MAT_JAKE_BODY.xbm")
            
        Returns:
            Full path to the diffuse XBT file, or None if not found
        """
        # Extract just the filename if a full path is provided
        # e.g., "GRAPHICS\_MATERIALS\SDORE-M-2009041549620469.xbm" -> "SDORE-M-2009041549620469.xbm"
        if '\\' in material_name or '/' in material_name:
            material_name = os.path.basename(material_name)
        
        # Remove .xbm extension if present
        if material_name.lower().endswith('.xbm'):
            material_name = material_name[:-4]
        
        print(f"  Looking for material: {material_name}")
        
        # Look for the material's XBM file first
        xbm_path = self._find_material_file(material_name)
        if not xbm_path:
            print(f"  Material file not found for: {material_name}")
            return None
        
        # Parse the XBM file to find diffuse texture path
        diffuse_path = self._extract_diffuse_path(xbm_path)
        if not diffuse_path:
            print(f"  No diffuse texture found in material: {material_name}")
            return None
        
        # Convert relative path to absolute
        full_path = self._resolve_texture_path(diffuse_path)
        if not os.path.exists(full_path):
            print(f"  Diffuse texture not found at: {full_path}")
            return None
        
        print(f"  Found diffuse texture: {os.path.basename(full_path)}")
        return full_path
    
    def _find_material_file(self, material_name: str) -> Optional[str]:
        """Find the .xbm material file for a material name"""
        # Try exact match
        xbm_file = f"{material_name}.xbm"
        xbm_path = os.path.join(self.materials_path, xbm_file)
        
        if os.path.exists(xbm_path):
            return xbm_path
        
        # Try case-insensitive search in directory
        try:
            for file in os.listdir(self.materials_path):
                if file.lower() == xbm_file.lower():
                    return os.path.join(self.materials_path, file)
        except:
            pass
        
        return None
    
    def _extract_diffuse_path(self, xbm_path: str) -> Optional[str]:
        """Extract the diffuse texture path from an XBM material file"""
        try:
            with open(xbm_path, 'rb') as f:
                data = f.read()
            
            # Look for texture paths (graphics\...)
            # Diffuse textures typically have "_d.xbt" suffix
            i = 0
            diffuse_candidates = []
            
            while i < len(data) - 20:
                if data[i:i+9] == b'graphics\\' or data[i:i+9] == b'graphics/':
                    path_start = i
                    path_end = data.find(b'\x00', path_start)
                    
                    if path_end != -1 and path_end - path_start < 200:
                        path = data[path_start:path_end].decode('ascii', errors='ignore')
                        
                        if path.endswith('.xbt'):
                            # Prioritize _d.xbt (diffuse) textures
                            if '_d.xbt' in path.lower():
                                return path
                            # Also collect other textures as fallback
                            diffuse_candidates.append(path)
                    
                    i = max(path_end, i + 1)
                else:
                    i += 1
            
            # If no _d.xbt found, return the first texture
            if diffuse_candidates:
                return diffuse_candidates[0]
            
        except Exception as e:
            print(f"  Error reading material file: {e}")
        
        return None
    
    def _resolve_texture_path(self, texture_path: str) -> str:
        """Convert a relative texture path to absolute filesystem path"""
        # The texture path is relative to the game's Data folder
        # e.g., "graphics\_textures\characters\jake\MAT_JAKE_BODY_d.xbt"
        
        # Go up from _materials to Data folder
        data_folder = os.path.dirname(os.path.dirname(self.materials_path))
        
        # Normalize path separators
        texture_path = texture_path.replace('\\', os.sep).replace('/', os.sep)
        
        # Combine paths
        full_path = os.path.join(data_folder, texture_path)
        
        return full_path
    
    def convert_xbt_to_png_base64(self, xbt_path: str) -> Optional[Tuple[str, int, int]]:
        """
        Convert an XBT texture to PNG and encode as base64
        
        Args:
            xbt_path: Path to the XBT file
            
        Returns:
            Tuple of (base64_string, width, height) or None if conversion fails
        """
        if not PIL_AVAILABLE:
            return None
        
        try:
            # Read XBT file
            with open(xbt_path, 'rb') as f:
                xbt_data = f.read()
            
            # Skip XBT header to get DDS data
            dds_data = self._extract_dds_from_xbt(xbt_data)
            if not dds_data:
                print(f"  Failed to extract DDS from XBT: {os.path.basename(xbt_path)}")
                return None
            
            # Create temporary DDS file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.dds', delete=False) as temp_dds:
                temp_dds.write(dds_data)
                temp_dds_path = temp_dds.name
            
            try:
                # Load DDS with PIL
                with Image.open(temp_dds_path) as img:
                    img.load()
                    
                    # Convert to RGB if needed
                    if img.mode not in ('RGB', 'RGBA'):
                        img = img.convert('RGB')
                    
                    # Get dimensions
                    width, height = img.size
                    
                    # Convert to PNG in memory
                    import io
                    png_buffer = io.BytesIO()
                    img.save(png_buffer, format='PNG')
                    png_data = png_buffer.getvalue()
                    
                    # Encode as base64
                    base64_string = base64.b64encode(png_data).decode('ascii')
                    
                    print(f"  Converted texture: {os.path.basename(xbt_path)} ({width}x{height})")
                    return (base64_string, width, height)
                    
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_dds_path)
                except:
                    pass
        
        except Exception as e:
            print(f"  Error converting texture {os.path.basename(xbt_path)}: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def _extract_dds_from_xbt(self, xbt_data: bytes) -> Optional[bytes]:
        """Extract DDS data from XBT container (same logic as Material Viewer)"""
        try:
            # Check for TBX header
            if xbt_data[:3] == b'TBX':
                # Read header size from offset 8
                if len(xbt_data) >= 12:
                    header_size = struct.unpack('<I', xbt_data[8:12])[0]
                    
                    # Validate header size
                    if 32 <= header_size <= 1024 and header_size < len(xbt_data):
                        dds_data = xbt_data[header_size:]
                    else:
                        # Try default header size
                        dds_data = xbt_data[32:]
                else:
                    dds_data = xbt_data[32:]
            else:
                # No TBX header, assume it's raw DDS
                dds_data = xbt_data
            
            # Verify DDS signature
            if len(dds_data) >= 4 and dds_data[:4] == b'DDS ':
                return dds_data
            
            # Try alternate header sizes
            for header_size in [64, 128, 256]:
                if len(xbt_data) > header_size:
                    test_data = xbt_data[header_size:]
                    if len(test_data) >= 4 and test_data[:4] == b'DDS ':
                        return test_data
            
        except Exception as e:
            print(f"  Error extracting DDS: {e}")
        
        return None

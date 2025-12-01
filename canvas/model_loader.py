"""3D Model Loader - FIXED to load embedded GLTF textures
Extracts base64 PNG textures from GLTF and loads them into OpenGL
"""

import os
import json
import struct
import base64
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
import OpenGL.GL as gl
from OpenGL.GL import *
from PyQt6.QtGui import QVector3D, QMatrix4x4, QImage
from PyQt6.QtWidgets import QApplication
from io import BytesIO

# Try to import PIL for texture loading
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Ã¢Å¡ Ã¯Â¸Â PIL/Pillow not available - textures will not be loaded")
    print("   Install with: pip install Pillow")

class GLTFModel:
    """Represents a loaded GLTF model with all its data"""
    
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.gltf_data = None
        self.bin_data = None
        self.meshes = []
        self.materials = []
        self.display_list = None
        self.bounds_min = None
        self.bounds_max = None
        self.loaded = False
        self.textures = {}  # material_index -> OpenGL texture ID
        
    def get_bounds(self):
        if self.bounds_min and self.bounds_max:
            return self.bounds_min, self.bounds_max
        return None, None

class GLTFMesh:
    """Represents a single mesh from a GLTF model"""
    
    def __init__(self):
        self.vertices = None
        self.normals = None
        self.uvs = None
        self.indices = None
        self.vao = None
        self.vbo_vertices = None
        self.vbo_normals = None
        self.vbo_uvs = None
        self.ibo = None
        self.material_index = None
        self.texture_id = None

class ModelLoader:
    """Handles loading and caching of GLTF models with EMBEDDED TEXTURE SUPPORT"""
    
    def __init__(self):
        self.models_cache = {}
        self.entity_to_model = {}
        self.entity_library_cache = {}
        self.models_directory = None
        self.entity_library_path = None
        self.materials_directory = None
        self.texture_loader = None
        self.fallback_cube_list = None
        self.entity_patterns = {}
        self._models_index = {}
        self._texture_cache = {}
        self._entity_library_loaded = False
        
        # NEW: Batch rendering support
        self.instance_batches = {}  # model_path -> list of (position, rotation, scale, is_selected)
        self.batch_vbos = {}  # model_path -> instance VBO for transforms
        
        self._load_local_entity_library()
        print("ModelLoader initialized with embedded texture support and batch rendering")

    def _load_local_entity_library(self):
        """Load the local entitylibrary_full.fcb.converted.xml file"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(current_dir, "assets", "entitylibrary", "entitylibrary_full.fcb.converted.xml"),
            os.path.join(current_dir, "..", "canvas", "assets", "entitylibrary", "entitylibrary_full.fcb.converted.xml"),
            os.path.join(current_dir, "..", "assets", "entitylibrary", "entitylibrary_full.fcb.converted.xml"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                self.entity_library_path = path
                print(f"Ã¢Å“â€¦ Found local EntityLibrary: {path}")
                try:
                    tree = ET.parse(path)
                    root = tree.getroot()
                    self.entity_patterns = {}

                    # Search for EntityPrototype objects
                    for proto_obj in root.findall(".//object[@name='EntityPrototype']"):
                        # Get the Name field from EntityPrototype (this is the clean name)
                        name_field = proto_obj.find(".//field[@name='Name']")
                        if name_field is None:
                            continue
                        
                        proto_name = name_field.get('value-String')
                        if not proto_name:
                            continue
                        
                        # Find the Entity object within this prototype
                        entity_obj = proto_obj.find(".//object[@name='Entity']")
                        if entity_obj is None:
                            continue
                        
                        # Also get the hidName for alternate matching
                        hid_field = entity_obj.find(".//field[@name='hidName']")
                        hid_name = hid_field.get('value-String') if hid_field is not None else None
                        
                        # Find the model file from CFileDescriptorComponent
                        descriptor_component = entity_obj.find(".//object[@name='CFileDescriptorComponent']")
                        if descriptor_component is not None:
                            hid_descriptor = descriptor_component.find(".//field[@name='hidDescriptor']")
                            if hid_descriptor is not None:
                                # Try GraphicComponent first
                                graphic_component = hid_descriptor.find(".//component[@class='GraphicComponent']")
                                if graphic_component is not None:
                                    resource = graphic_component.find(".//resource")
                                    if resource is not None:
                                        model_file = resource.get('fileName')
                                        if model_file:
                                            # Store using the EntityPrototype Name (clean name)
                                            self.entity_patterns[proto_name] = model_file
                                            # Also store using hidName for fallback
                                            if hid_name:
                                                self.entity_patterns[hid_name] = model_file
                                
                                # Try GraphicKitComponent for characters
                                kit_component = hid_descriptor.find(".//component[@class='GraphicKitComponent']")
                                if kit_component is not None:
                                    resource = kit_component.find(".//resource")
                                    if resource is not None:
                                        model_file = resource.get('fileName')
                                        if model_file:
                                            self.entity_patterns[proto_name] = model_file
                                            if hid_name:
                                                self.entity_patterns[hid_name] = model_file
                    
                    self._entity_library_loaded = True
                    print(f"Ã¢Å“â€¦ Loaded {len(self.entity_patterns)} entity patterns")
                    return True
                except Exception as e:
                    print(f"Ã¢ÂÅ’ Error parsing EntityLibrary: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
        
        print(f"Ã¢ÂÅ’ Local EntityLibrary not found")
        return False
        
    def set_models_directory(self, directory_path, scan_recursive=True):
        """Set the models directory and index all models"""
        if not os.path.isdir(directory_path):
            print(f"Ã¢ÂÅ’ Invalid models directory: {directory_path}")
            return False
        
        self.models_directory = os.path.abspath(directory_path)
        print(f"Ã¢Å“â€¦ Models directory set: {self.models_directory}")
        
        if scan_recursive:
            self._index_models_directory()
        
        return True

    def set_materials_directory(self, materials_path):
        """Compatibility method - not needed for embedded textures"""
        print("Ã¢â€žÂ¹Ã¯Â¸Â Materials directory not needed (using embedded GLTF textures)")
        return True

    def _index_models_directory(self):
        """Index all GLTF files"""
        self._models_index = {}
        root = Path(self.models_directory)
        
        gltf_files = list(root.rglob('*.gltf'))
        
        for p in gltf_files:
            rel = p.relative_to(root).as_posix()
            key = p.name.lower()
            
            if key not in self._models_index:
                self._models_index[key] = []
            self._models_index[key].append(rel)
        
        total_models = sum(len(v) for v in self._models_index.values())
        print(f"Ã°Å¸â€œÂ¦ Indexed {total_models} GLTF models")

    def set_entity_library_folder(self, worlds_path):
        """Compatibility method"""
        if not self._entity_library_loaded:
            return self._load_local_entity_library()
        return True

    def assign_models_to_entities(self, entities, progress_dialog=None, parent=None, game_mode="avatar"):
        """Assign 3D models to entities - using parent's progress dialog"""
        if not self._entity_library_loaded:
            print("⚠️ No EntityLibrary loaded")
            return

        print(f"🔍 Assigning models to {len(entities)} entities...")

        # Helper function for logging
        def log(msg):
            print(msg)
            if progress_dialog:
                try:
                    progress_dialog.append_log(msg)
                except:
                    pass

        log(f"Processing {len(entities)} entities for 3D models...")

        matched = 0
        unmatched = 0
        unfound_models = []
        found_models = []
        
        normalized_patterns = {}
        for key, val in self.entity_patterns.items():
            normalized_patterns[key.lower()] = val
            if '.' in key:
                parts = key.split('.', 1)
                if len(parts) == 2:
                    normalized_patterns[parts[1].lower()] = val

        total_entities = len(entities)
        
        for idx, entity in enumerate(entities):
            # Update progress every 50 entities
            if idx % 50 == 0 and progress_dialog:
                percent = int((idx / total_entities) * 100)
                if hasattr(progress_dialog, 'set_progress'):
                    progress_dialog.set_progress(percent)
                if hasattr(progress_dialog, 'set_status'):
                    progress_dialog.set_status(f"Assigning 3D models: {idx}/{total_entities}")
                QApplication.processEvents()
                
                # Check for cancellation
                if hasattr(progress_dialog, 'was_cancelled') and progress_dialog.was_cancelled:
                    log("Model assignment cancelled by user")
                    return
            
            entity_name = getattr(entity, "hid_name", getattr(entity, "name", None))
            if not entity_name:
                unmatched += 1
                continue

            model_file = None
            
            # STEP 1: Check entity's own XML data
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                resource_elem = entity.xml_element.find(".//resource[@fileName]")
                if resource_elem is not None:
                    model_file = resource_elem.get('fileName')
                    if model_file and idx % 100 == 0:
                        log(f"  Found model for: {entity_name[:30]}...")
            
            # STEP 2: Search entity library
            if not model_file:
                norm_name = entity_name.lower()
                model_file = normalized_patterns.get(norm_name)
                
                if not model_file:
                    import re
                    base_name = re.sub(r'_\d+$', '', entity_name)
                    if base_name != entity_name:
                        model_file = normalized_patterns.get(base_name.lower())
                
                if not model_file and '.' in entity_name:
                    parts = entity_name.split('.', 1)
                    if len(parts) == 2:
                        suffix = parts[1]
                        model_file = normalized_patterns.get(suffix.lower())
                        if not model_file:
                            suffix_no_num = re.sub(r'_\d+$', '', suffix)
                            model_file = normalized_patterns.get(suffix_no_num.lower())
            
            if model_file:
                model_file = self._fix_resource_path_typos(model_file)
                gltf_path, bin_path = self._extract_gltf_path_from_resource(model_file)
                
                # Try static version if _Kit not found
                if not gltf_path and '/_Kit/' in model_file:
                    static_model_file = self._convert_to_static_path(model_file)
                    if static_model_file:
                        gltf_path, bin_path = self._extract_gltf_path_from_resource(static_model_file)
                        if gltf_path:
                            model_file = static_model_file
                
                if gltf_path:
                    entity.model_file = gltf_path
                    entity.bin_file = bin_path
                    found_models.append({
                        'entity_name': entity_name,
                        'resource_path': model_file,
                        'gltf_path': gltf_path,
                        'is_static_fallback': '/_Kit/' in model_file and gltf_path and '/_Kit/' not in gltf_path
                    })
                    matched += 1
                else:
                    entity.model_file = None
                    unfound_models.append({
                        'entity_name': entity_name,
                        'resource_path': model_file
                    })
                    unmatched += 1
            else:
                entity.model_file = None
                unmatched += 1

        log(f"✓ Model assignment complete: {matched} matched, {unmatched} unmatched")

        print(f"📊 {matched} matched, {unmatched} unmatched")
        
        # Write reports (same as before)
        if found_models:
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_file = os.path.join(script_dir, "loaded_models.txt")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"Loaded Models Report\n")
                    f.write(f"Generated: {self._get_timestamp()}\n")
                    f.write(f"Total loaded: {len(found_models)}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for item in found_models:
                        f.write(f"Entity: {item['entity_name']}\n")
                        f.write(f"Resource Path: {item['resource_path']}\n")
                        f.write(f"GLTF File: {item['gltf_path']}\n")
                        if item['is_static_fallback']:
                            f.write(f"NOTE: Using static fallback (original was _Kit model)\n")
                        f.write("-" * 80 + "\n")
                
                print(f"📝 Wrote {len(found_models)} loaded models to {output_file}")
            except Exception as e:
                print(f"❌ Failed to write loaded models file: {e}")
        
        if unfound_models:
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                output_file = os.path.join(script_dir, "unfound_models.txt")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"Unfound Models Report\n")
                    f.write(f"Generated: {self._get_timestamp()}\n")
                    f.write(f"Total unfound: {len(unfound_models)}\n")
                    f.write("=" * 80 + "\n\n")
                    
                    for item in unfound_models:
                        f.write(f"Entity: {item['entity_name']}\n")
                        f.write(f"Resource Path: {item['resource_path']}\n")
                        f.write("-" * 80 + "\n")
                
                print(f"📝 Wrote {len(unfound_models)} unfound models to {output_file}")
            except Exception as e:
                print(f"❌ Failed to write unfound models file: {e}")

    def _get_timestamp(self):
        """Get current timestamp for logging"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _convert_to_static_path(self, kit_path):
        """Convert _Kit model path to static model path
        Example: graphics/av_Creatures/Thanator/_Kit/Thanator.xbg
            -> graphics/av_Creatures/Thanator/Thanator.xbg
        """
        if '/_Kit/' not in kit_path:
            return None
        
        # Remove /_Kit/ from the path
        static_path = kit_path.replace('/_Kit/', '/')
        return static_path

    def _fix_resource_path_typos(self, resource_path):
        """Fix common typos and path issues in resource paths"""
        if not resource_path:
            return resource_path
        
        # Common typo fixes
        fixes = {
            'grahpics': 'graphics',
            'grpahics': 'graphics',
            'graphcis': 'graphics',
            'modles': 'models',
            'charaters': 'characters',
            'enviornment': 'environment',
            'enviroment': 'environment',
        }
        
        # Normalize path separators
        fixed_path = resource_path.replace('\\', '/')
        
        # Fix case-insensitive typos in path segments
        parts = fixed_path.split('/')
        fixed_parts = []
        
        for part in parts:
            part_lower = part.lower()
            # Check if this part matches any known typo
            fixed_part = part
            for typo, correct in fixes.items():
                if typo in part_lower:
                    fixed_part = part_lower.replace(typo, correct)
                    break
            fixed_parts.append(fixed_part)
        
        return '/'.join(fixed_parts)

    def _extract_gltf_path_from_resource(self, resource_path):
        """Extract GLTF path from resource"""
        if not resource_path or not self.models_directory:
            return None, None
        
        parts = resource_path.replace("\\", "/").split("/")
        
        try:
            graphics_index = next(i for i, p in enumerate(parts) if p.lower() == "graphics")
            rel_parts = parts[graphics_index + 1:]
        except StopIteration:
            rel_parts = parts
        
        base_name = os.path.splitext(rel_parts[-1])[0]
        rel_parts[-1] = base_name
        
        return self._find_gltf_case_insensitive(rel_parts)
    
    def _find_gltf_case_insensitive(self, path_parts):
        """Find GLTF file case-insensitively"""
        current = self.models_directory
        
        for part in path_parts[:-1]:
            try:
                matches = [f for f in os.listdir(current) if f.lower() == part.lower()]
                if not matches:
                    return None, None
                current = os.path.join(current, matches[0])
            except FileNotFoundError:
                return None, None
        
        last_part = path_parts[-1]
        gltf_path = None
        bin_path = None
        
        try:
            for f in os.listdir(current):
                if f.lower().startswith(last_part.lower()):
                    if f.lower().endswith(".gltf"):
                        gltf_path = os.path.join(current, f)
                    elif f.lower().endswith(".bin"):
                        bin_path = os.path.join(current, f)
        except FileNotFoundError:
            return None, None
        
        return gltf_path, bin_path

    def get_model_for_entity(self, entity):
        """Get loaded model for entity WITH EMBEDDED TEXTURES"""
        if not hasattr(entity, 'model_file') or not entity.model_file:
            return None
        
        gltf_path = entity.model_file
        bin_path = getattr(entity, 'bin_file', None)

        if gltf_path in self.models_cache:
            return self.models_cache[gltf_path]

        model = GLTFModel(os.path.basename(gltf_path), gltf_path)
        try:
            with open(gltf_path, 'r', encoding='utf-8') as f:
                model.gltf_data = json.load(f)
            
            if bin_path and os.path.exists(bin_path):
                with open(bin_path, 'rb') as f:
                    model.bin_data = f.read()
            
            self._parse_gltf(model)
            self._load_embedded_textures(model)  # NEW: Load embedded textures
            self._create_opengl_resources(model)
            model.loaded = True
            self.models_cache[gltf_path] = model

            tex_info = f" ({len(model.textures)} textures)" if model.textures else ""
            print(f"Ã¢Å“â€¦ Loaded: {os.path.basename(gltf_path)}{tex_info}")
            return model

        except Exception as e:
            print(f"Ã¢ÂÅ’ Failed to load {gltf_path}: {e}")
            return None

    def _load_embedded_textures(self, model):
        """Load textures embedded in GLTF as base64 PNG data"""
        if not PIL_AVAILABLE:
            print("  Ã¢Å¡ Ã¯Â¸Â PIL not available - skipping textures")
            return
        
        gltf = model.gltf_data
        
        if 'materials' not in gltf or 'images' not in gltf:
            return
        
        print(f"  Loading {len(gltf['materials'])} material textures...")
        
        # Load all images into OpenGL textures
        image_textures = {}
        for img_idx, image_def in enumerate(gltf['images']):
            if 'uri' in image_def and image_def['uri'].startswith('data:image/png;base64,'):
                # Extract base64 data
                base64_data = image_def['uri'].split(',', 1)[1]
                
                try:
                    # Decode base64 to PNG bytes
                    png_bytes = base64.b64decode(base64_data)
                    
                    # Load PNG with PIL
                    pil_image = Image.open(BytesIO(png_bytes))
                    
                    # Convert to RGBA if needed
                    if pil_image.mode != 'RGBA':
                        pil_image = pil_image.convert('RGBA')
                    
                    # Get image data
                    img_data = pil_image.tobytes()
                    width, height = pil_image.size
                    
                    # Create OpenGL texture
                    texture_id = glGenTextures(1)
                    glBindTexture(GL_TEXTURE_2D, texture_id)
                    
                    # Upload texture data
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 
                                0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)
                    
                    # Set texture parameters
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
                    
                    # Brighten textures using texture environment
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                    glTexEnvfv(GL_TEXTURE_ENV, GL_TEXTURE_ENV_COLOR, [1.5, 1.5, 1.5, 1.0])
                    
                    # Generate mipmaps
                    glGenerateMipmap(GL_TEXTURE_2D)
                    
                    glBindTexture(GL_TEXTURE_2D, 0)
                    
                    image_textures[img_idx] = texture_id
                    print(f"    Ã¢Å“â€¦ Loaded image {img_idx}: {image_def.get('name', 'unnamed')} ({width}x{height})")
                    
                except Exception as e:
                    print(f"    Ã¢ÂÅ’ Failed to load image {img_idx}: {e}")
        
        # Map materials to textures
        if 'textures' in gltf:
            for mat_idx, material in enumerate(gltf['materials']):
                # Check for baseColorTexture
                if 'pbrMetallicRoughness' in material:
                    pbr = material['pbrMetallicRoughness']
                    if 'baseColorTexture' in pbr:
                        tex_idx = pbr['baseColorTexture']['index']
                        
                        if tex_idx < len(gltf['textures']):
                            texture_def = gltf['textures'][tex_idx]
                            if 'source' in texture_def:
                                img_idx = texture_def['source']
                                
                                if img_idx in image_textures:
                                    model.textures[mat_idx] = image_textures[img_idx]
                                    mat_name = material.get('name', f'Material_{mat_idx}')
                                    print(f"    Ã¢Å“â€¦ Material {mat_idx} ({mat_name}): Texture bound")

    def _parse_gltf(self, model):
        """Parse GLTF JSON and extract mesh data"""
        gltf = model.gltf_data
        
        buffers = []
        if 'buffers' in gltf:
            for buffer_def in gltf['buffers']:
                buffers.append(model.bin_data or b'')
        
        buffer_views = []
        if 'bufferViews' in gltf:
            for view_def in gltf['bufferViews']:
                buffer_idx = view_def['buffer']
                byte_offset = view_def.get('byteOffset', 0)
                byte_length = view_def['byteLength']
                
                buffer_data = buffers[buffer_idx]
                view_data = buffer_data[byte_offset:byte_offset + byte_length]
                buffer_views.append(view_data)
        
        accessors = []
        if 'accessors' in gltf:
            for accessor_def in gltf['accessors']:
                accessors.append(accessor_def)
        
        if 'meshes' in gltf:
            for mesh_def in gltf['meshes']:
                for primitive in mesh_def.get('primitives', []):
                    mesh = GLTFMesh()
                    attributes = primitive.get('attributes', {})
                    
                    if 'POSITION' in attributes:
                        pos_accessor = accessors[attributes['POSITION']]
                        mesh.vertices = self._extract_accessor_data(pos_accessor, buffer_views)
                        
                        if 'min' in pos_accessor and 'max' in pos_accessor:
                            model.bounds_min = pos_accessor['min']
                            model.bounds_max = pos_accessor['max']
                    
                    if 'NORMAL' in attributes:
                        norm_accessor = accessors[attributes['NORMAL']]
                        mesh.normals = self._extract_accessor_data(norm_accessor, buffer_views)
                    
                    if 'TEXCOORD_0' in attributes:
                        uv_accessor = accessors[attributes['TEXCOORD_0']]
                        mesh.uvs = self._extract_accessor_data(uv_accessor, buffer_views)
                    
                    if 'indices' in primitive:
                        idx_accessor = accessors[primitive['indices']]
                        mesh.indices = self._extract_accessor_data(idx_accessor, buffer_views)
                    
                    if 'material' in primitive:
                        mesh.material_index = primitive['material']
                    
                    model.meshes.append(mesh)

    def _extract_accessor_data(self, accessor, buffer_views):
        """Extract typed data from accessor"""
        view_idx = accessor['bufferView']
        byte_offset = accessor.get('byteOffset', 0)
        count = accessor['count']
        component_type = accessor['componentType']
        accessor_type = accessor['type']
        
        view_data = buffer_views[view_idx]
        
        type_sizes = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
        type_formats = {5120: 'b', 5121: 'B', 5122: 'h', 5123: 'H', 5125: 'I', 5126: 'f'}
        component_counts = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
        
        components = component_counts[accessor_type]
        format_char = type_formats[component_type]
        element_size = type_sizes[component_type] * components
        
        data = []
        for i in range(count):
            offset = byte_offset + (i * element_size)
            element = struct.unpack_from(f'<{components}{format_char}', view_data, offset)
            
            if components == 1:
                data.append(element[0])
            else:
                data.append(element)
        
        return np.array(data, dtype=np.float32)

    def _create_opengl_resources(self, model):
        """Create OpenGL display list WITH TEXTURE SUPPORT"""
        if not model.meshes:
            return
        
        model.display_list = glGenLists(1)
        glNewList(model.display_list, GL_COMPILE)
        
        # Enable depth testing for solid models
        glEnable(GL_DEPTH_TEST)
        glDepthMask(GL_TRUE)
        
        for mesh in model.meshes:
            if mesh.vertices is None:
                continue
            
            has_uvs = mesh.uvs is not None and len(mesh.uvs) > 0
            has_texture = mesh.material_index is not None and mesh.material_index in model.textures
            
            # Enable texture if available
            if has_texture:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, model.textures[mesh.material_index])
                # Brighten texture by using GL_ADD or adjusting color
                glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                glColor3f(1.5, 1.5, 1.5)  # Multiply texture by 1.5x brightness
            else:
                # Use a solid color for non-textured meshes
                glColor3f(0.7, 0.7, 0.7)
            
            glEnableClientState(GL_VERTEX_ARRAY)
            glVertexPointer(3, GL_FLOAT, 0, mesh.vertices)
            
            if mesh.normals is not None:
                glEnableClientState(GL_NORMAL_ARRAY)
                glNormalPointer(GL_FLOAT, 0, mesh.normals)
            
            if has_uvs and has_texture:
                glEnableClientState(GL_TEXTURE_COORD_ARRAY)
                glTexCoordPointer(2, GL_FLOAT, 0, mesh.uvs)
            
            if mesh.indices is not None:
                glDrawElements(GL_TRIANGLES, len(mesh.indices), GL_UNSIGNED_INT, mesh.indices)
            else:
                glDrawArrays(GL_TRIANGLES, 0, len(mesh.vertices))
            
            glDisableClientState(GL_VERTEX_ARRAY)
            if mesh.normals is not None:
                glDisableClientState(GL_NORMAL_ARRAY)
            if has_uvs and has_texture:
                glDisableClientState(GL_TEXTURE_COORD_ARRAY)
            
            # Disable texture
            if has_texture:
                glColor3f(1.0, 1.0, 1.0)  # Reset color
                glBindTexture(GL_TEXTURE_2D, 0)
                glDisable(GL_TEXTURE_2D)
        
        glEndList()

    def render_model(self, model, position, rotation=0, scale=1.0):
        """Render model at position"""
        if not model or not model.loaded or not model.display_list:
            return False
        
        glPushMatrix()
        glTranslatef(position[0], position[1], position[2])
        
        if rotation != 0:
            glRotatef(rotation, 0, 1, 0)
        
        if scale != 1.0:
            glScalef(scale, scale, scale)
        
        glCallList(model.display_list)
        glPopMatrix()
        
        return True

    def prepare_batches(self, entities, selected_entities):
        """Prepare instance batches for all entities - call once per frame before rendering"""
        self.instance_batches.clear()
        
        for entity in entities:
            if not hasattr(entity, 'model_file') or not entity.model_file:
                continue
            
            if not all(hasattr(entity, attr) for attr in ('x', 'y', 'z')):
                continue
            
            model_path = entity.model_file
            
            if model_path not in self.instance_batches:
                self.instance_batches[model_path] = []
            
            # Position: swap Y and Z, negate Y for OpenGL coordinates
            pos_x = float(entity.x)
            pos_y = float(entity.z)
            pos_z = float(-entity.y)
            
            # Extract rotation angles from hidAngles
            rotation_x = 0.0
            rotation_y = 0.0
            rotation_z = 0.0
            
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                angles_field = entity.xml_element.find("./field[@name='hidAngles']")
                if angles_field is not None:
                    angles_value = angles_field.get('value-Vector3')
                    if angles_value:
                        try:
                            parts = angles_value.split(',')
                            if len(parts) >= 3:
                                rotation_x = float(parts[0].strip())
                                rotation_y = float(parts[1].strip())
                                game_rotation_z = float(parts[2].strip())
                                rotation_z = (360 - game_rotation_z) % 360
                        except (ValueError, IndexError):
                            pass
                
                # Try Dunia Tools format if FCB format not found
                if rotation_z == 0.0:
                    angles_elem = entity.xml_element.find("./value[@name='hidAngles']")
                    if angles_elem is not None:
                        x_elem = angles_elem.find("./x")
                        y_elem = angles_elem.find("./y")
                        z_elem = angles_elem.find("./z")
                        
                        if x_elem is not None and x_elem.text:
                            rotation_x = float(x_elem.text.strip())
                        if y_elem is not None and y_elem.text:
                            rotation_y = float(y_elem.text.strip())
                        if z_elem is not None and z_elem.text:
                            game_rotation_z = float(z_elem.text.strip())
                            rotation_z = (360 - game_rotation_z) % 360
            
            is_selected = entity in selected_entities
            
            # Store instance data: position, rotations, selection state
            self.instance_batches[model_path].append({
                'entity': entity,  # Keep reference for debugging
                'position': (pos_x, pos_y, pos_z),
                'rotation': (rotation_x, rotation_y, rotation_z),
                'is_selected': is_selected
            })

    def render_batched_models(self):
        """Render all models using instanced rendering - call once per frame"""
        if not self.instance_batches:
            return 0
        
        models_rendered = 0
        instances_rendered = 0
        textured_instances = 0
        
        for model_path, instances in self.instance_batches.items():
            if not instances:
                continue
            
            # Get or load model
            model = self.models_cache.get(model_path)
            if not model:
                # Try to load model on-demand
                for instance in instances:
                    entity = instance['entity']
                    model = self.get_model_for_entity(entity)
                    if model:
                        break
            
            if not model or not model.loaded or not model.display_list:
                continue
            
            has_textures = len(model.textures) > 0
            
            # Render each instance
            for instance_data in instances:
                glPushMatrix()
                
                pos = instance_data['position']
                rot = instance_data['rotation']
                is_selected = instance_data['is_selected']
                
                glTranslatef(pos[0], pos[1], pos[2])
                
                # Apply rotations in correct order:
                # 1. First convert model from Y-up (GLTF) to Z-up (game) by rotating -90° around X
                glRotatef(-90, 1, 0, 0)
                # 2. Flip 180° to face correct direction
                glRotatef(180, 0, 0, 0)
                
                # 3. Then apply game rotations
                if rot[2] != 0:  # Yaw (rotation around Z-axis) - subtract 180 like the 2D gizmo does
                    glRotatef(rot[2] - 180, 0, 0, 1)
                
                if rot[0] != 0:  # Pitch (rotation around X-axis)
                    glRotatef(rot[0], 1, 0, 0)
                
                if rot[1] != 0:  # Roll (rotation around Y-axis in game)
                    glRotatef(rot[1], 0, 1, 0)
                
                # Highlight selection
                if is_selected:
                    glColor3f(1.2, 1.2, 1.5)  # Brighter for selection
                else:
                    glColor3f(1.0, 1.0, 1.0)  # Normal
                
                glCallList(model.display_list)
                glPopMatrix()
                
                instances_rendered += 1
                if has_textures:
                    textured_instances += 1
            
            models_rendered += 1
        
        return instances_rendered

    def clear_cache(self):
        """Clear all cached resources"""
        for model in self.models_cache.values():
            if model.display_list:
                glDeleteLists(model.display_list, 1)
            for tex_id in model.textures.values():
                glDeleteTextures([tex_id])
        
        for tex_id in self._texture_cache.values():
            glDeleteTextures([tex_id])
        
        if self.fallback_cube_list:
            glDeleteLists(self.fallback_cube_list, 1)
        
        self.models_cache.clear()
        print("Ã¢Å“â€¦ Cache cleared")
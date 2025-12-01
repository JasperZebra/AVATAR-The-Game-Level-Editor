"""
Terrain Renderer for MapCanvas - FIXED VERSION
Matches the working Water test.py implementation exactly.

Key fixes:
1. Heightmap: Simple bottom-left sequential (0,1,2...left-to-right, bottom-to-top)
2. Textures: 2x2 blocks with 1↔2 swap, top-left origin, vertical stacking  
3. Final 90° CCW rotation applied to complete texture assembly
"""

import numpy as np
from PyQt6.QtGui import QPainter, QImage, QPixmap, QTransform
from PyQt6.QtCore import Qt
import io
import os
import glob
import struct
import tempfile
from PIL import Image
from io import BytesIO


class WaterData:
    """Container for water info per sector"""
    def __init__(self, sector_num):
        self.sector_num = sector_num
        self.has_water = False
        self.water_height = 0.0
        self.material_path = None
        self.hex_offset_height = None
        self.hex_offset_material = None
        self.file_path = None
        self.file_name = None


class TerrainRenderer:
    """Handles terrain rendering in 2D canvas"""

    def __init__(self):
        self.grid_size = 65
        self.sectors_data = {}
        self.combined_heightmap = None
        self.terrain_image = None
        self.terrain_pixmap = None
        self.sdat_path = None
        self.show_terrain = True
        self.terrain_opacity = 1.0
        self.sectors_x = 16
        self.sectors_y = 16
        self.terrain_offset_x = 0
        self.terrain_offset_y = 0
        self.terrain_scale = 10
        self.terrain_world_min_x = 0
        self.terrain_world_min_y = 0
        self.terrain_world_max_x = 0
        self.terrain_world_max_y = 0
        self.current_directory = None
        self.texture_layer = None
        self.atlas_mapping = {}
        self.sector_to_path = {}
        
        # Water data storage
        self.water_data = {}  # sector_num -> WaterData

    # ----------------------------
    # SDAT Loading
    # ----------------------------
    def load_sdat_folder(self, sdat_path: str) -> bool:
        """Load all .csdat files from the sdat folder and generate textured terrain automatically."""
        if not os.path.isdir(sdat_path):
            print(f"Invalid sdat path: {sdat_path}")
            return False

        self.sdat_path = sdat_path
        self.current_directory = sdat_path
        self.sectors_data = {}
        self.water_data = {}

        # Set default texture layer if not set
        if not self.texture_layer:
            class Dummy:
                def get(self_inner):
                    return "diffuse"
            self.texture_layer = Dummy()

        # Load all .csdat files
        files = glob.glob(os.path.join(sdat_path, "*.csdat"))
        if not files:
            print(f"No .csdat files found in {sdat_path}")
            return False

        print(f"Loading terrain data from {len(files)} .csdat files...")
        
        water_count = 0
        for file_path in files:
            filename = os.path.basename(file_path)
            try:
                # Parse sector number
                name = filename.rsplit('.', 1)[0]
                if name.startswith('sd'):
                    sector_num = int(name[2:])
                elif '_' in name:
                    sector_num = int(name.split('_')[-1])
                else:
                    sector_num = int(name)

                height_data = self._load_single_sector(file_path)
                if height_data is not None:
                    self.sectors_data[sector_num] = height_data
                    
                    # Parse water data from this sector
                    water = self.parse_water_from_sector(file_path, sector_num)
                    self.water_data[sector_num] = water
                    if water.has_water:
                        water_count += 1

            except (ValueError, IndexError) as e:
                print(f"Could not parse sector number from {filename}: {e}")

        num_sectors = len(self.sectors_data)
        print(f"Loaded {num_sectors} terrain sectors")
        
        if water_count > 0:
            print(f"Found {water_count} sectors with water")

        if num_sectors > 0:
            max_sector = max(self.sectors_data.keys())
            grid_size = int(np.ceil(np.sqrt(max_sector + 1)))
            self.sectors_x = grid_size
            self.sectors_y = grid_size
            print(f"Detected terrain grid: {self.sectors_x}x{self.sectors_y}")

            # Generate terrain image
            self._generate_terrain_image()

            print(f"✓ Terrain loaded from {sdat_path}")
            return True

        return False

    def _load_single_sector(self, file_path: str):
        try:
            with open(file_path, 'rb') as f:
                f.seek(708)
                terrain_data = io.BytesIO(f.read(16900))

            height_array = np.zeros((self.grid_size, self.grid_size), dtype=np.float32)
            for y in range(self.grid_size):
                for x in range(self.grid_size):
                    data = terrain_data.read(2)
                    if len(data) < 2:
                        break
                    height = int.from_bytes(data, 'little') / 128
                    height_array[y, x] = height
                    terrain_data.read(2)
            return height_array

        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None

    # ----------------------------
    # Water Parsing
    # ----------------------------
    def parse_water_from_sector(self, file_path, sector_num):
        """Parse water data from a .csdat file"""
        water = WaterData(sector_num)
        water.file_path = file_path
        water.file_name = os.path.basename(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            height_offset = 0xB0
            
            if len(data) < height_offset + 4:
                return water
            
            height_bytes = data[height_offset:height_offset + 4]
            
            try:
                water.water_height = struct.unpack('<f', height_bytes)[0]
                water.hex_offset_height = height_offset
                
                if water.water_height != 0.0:
                    water.has_water = True
                    
                    water_patterns = [
                        b'graphics\\_materials\\editor\\water_',
                        b'graphics_materials\\editor\\water_'
                    ]
                    
                    graphics_pos = -1
                    for pattern in water_patterns:
                        pos = data.find(pattern)
                        if pos != -1:
                            graphics_pos = pos
                            break
                    
                    if graphics_pos != -1:
                        material_start = graphics_pos
                        material_end = data.find(b'\x00', material_start)
                        if material_end != -1:
                            water.material_path = data[material_start:material_end].decode('latin-1', errors='ignore')
                            water.hex_offset_material = material_start
                        else:
                            water.material_path = data[material_start:material_start+100].decode('latin-1', errors='ignore')
                            water.hex_offset_material = material_start
                    
                    print(f"Water found in sector {sector_num}:")
                    if water.material_path:
                        print(f"  Material path: {water.material_path}")
                        if water.hex_offset_material is not None:
                            print(f"  Material at offset: 0x{water.hex_offset_material:08X}")
                    print(f"  Water height: {water.water_height:.2f}")
                    if water.hex_offset_height is not None:
                        print(f"  Height at offset: 0x{water.hex_offset_height:08X}")
                    
            except Exception as e:
                print(f"  Could not read water height: {e}")
                water.water_height = 0.0
                
        except Exception as e:
            print(f"Error parsing water from {file_path}: {e}")
        
        return water

    # ----------------------------
    # Sector Indexing - FIXED TO MATCH WORKING CODE
    # ----------------------------
    def get_sector_index_from_position(self, display_row, col, sectors_x, sectors_y):
        """
        Avatar Game Layout (2x2 blocks, vertical) - MATCHES WORKING IMPLEMENTATION
        
        This is the TEXTURE indexing pattern. Heightmaps use simple bottom-left sequential.
        
        Key points from working code:
        - 2x2 blocks stack vertically (8 blocks down = 32 sectors per column)
        - Within each block: swap positions 1↔2
        - Standard: TL=0, TR=1, BL=2, BR=3
        - Avatar:   TL=0, TR=2, BL=1, BR=3 (swap 1↔2)
        """
        # Calculate which 2x2 block this position belongs to
        block_col = col // 2
        block_row = display_row // 2
        
        # Position within the 2x2 block
        within_block_col = col % 2
        within_block_row = display_row % 2
        
        # Blocks stack vertically (going DOWN first, then across)
        blocks_per_column = sectors_y // 2  # 8 for 16x16 grid
        atlas_block_index = block_col * blocks_per_column + block_row
        
        # Base sector for this atlas (each atlas has 4 sectors)
        base_sector = atlas_block_index * 4
        
        # Position within the 2x2 block with Avatar's swap of positions 1 and 2
        if within_block_row == 0 and within_block_col == 0:
            offset = 0  # Top-left stays 0
        elif within_block_row == 0 and within_block_col == 1:
            offset = 2  # Top-right gets 2 (swapped from 1)
        elif within_block_row == 1 and within_block_col == 0:
            offset = 1  # Bottom-left gets 1 (swapped from 2)
        else:  # within_block_row == 1 and within_block_col == 1
            offset = 3  # Bottom-right stays 3
        
        return base_sector + offset

    # ----------------------------
    # Terrain Image Generation - FIXED
    # ----------------------------
    def _generate_terrain_image(self):
        """Generate terrain image using XBT/atlas textures if available, else procedural"""
        if not self.sectors_data:
            return

        # Auto-detect and build atlas mapping if possible
        if (not self.atlas_mapping or len(self.atlas_mapping) == 0) and self.current_directory and self.texture_layer:
            self.build_atlas_mapping()
            if self.atlas_mapping:
                print(f"Detected atlas mapping with {len(self.atlas_mapping)} sectors")

        if self.atlas_mapping:
            self._generate_terrain_image_textured()
        else:
            self._generate_terrain_image_procedural()

    def _generate_terrain_image_procedural(self):
        """Generate procedural heightmap visualization - BOTTOM-LEFT SEQUENTIAL"""
        total_width = self.sectors_x * self.grid_size
        total_height = self.sectors_y * self.grid_size
        combined_map = np.zeros((total_height, total_width), dtype=np.float32)

        # HEIGHTMAP uses simple bottom-left sequential ordering
        # Sector 0 = bottom-left, proceeds right, then up
        for display_row in range(self.sectors_y):
            for col in range(self.sectors_x):
                # Bottom-left sequential
                sector_row = self.sectors_y - 1 - display_row  # 0 = bottom
                sector_index = sector_row * self.sectors_x + col
                
                if sector_index in self.sectors_data:
                    start_y = display_row * self.grid_size
                    end_y = start_y + self.grid_size
                    start_x = col * self.grid_size
                    end_x = start_x + self.grid_size
                    
                    # Flip vertically for display (matches working code)
                    combined_map[start_y:end_y, start_x:end_x] = np.flipud(
                        self.sectors_data[sector_index]
                    )

        self.combined_heightmap = combined_map
        min_h, max_h = np.min(combined_map), np.max(combined_map)
        norm = (combined_map - min_h) / (max_h - min_h) if max_h > min_h else np.zeros_like(combined_map)

        # Colorize heightmap
        rgb_image = np.zeros((total_height, total_width, 3), dtype=np.uint8)
        water_mask = norm < 0.2
        low_mask = (norm >= 0.2) & (norm < 0.4)
        mid_mask = (norm >= 0.4) & (norm < 0.7)
        high_mask = norm >= 0.7

        rgb_image[water_mask] = np.stack([
            (norm[water_mask] * 50).astype(np.uint8),
            (norm[water_mask] * 100 + 50).astype(np.uint8),
            (norm[water_mask] * 155 + 100).astype(np.uint8)
        ], axis=-1)
        rgb_image[low_mask] = np.stack([
            (norm[low_mask] * 50).astype(np.uint8),
            (norm[low_mask] * 180 + 50).astype(np.uint8),
            (norm[low_mask] * 50).astype(np.uint8)
        ], axis=-1)
        rgb_image[mid_mask] = np.stack([
            (norm[mid_mask] * 160 + 80).astype(np.uint8),
            (norm[mid_mask] * 120 + 60).astype(np.uint8),
            (norm[mid_mask] * 60).astype(np.uint8)
        ], axis=-1)
        rgb_image[high_mask] = np.stack([
            (norm[high_mask] * 200 + 55).astype(np.uint8),
            (norm[high_mask] * 200 + 55).astype(np.uint8),
            (norm[high_mask] * 200 + 55).astype(np.uint8)
        ], axis=-1)

        self.terrain_image = QImage(
            rgb_image.data,
            total_width,
            total_height,
            total_width * 3,
            QImage.Format.Format_RGB888
        )
        self.terrain_pixmap = QPixmap.fromImage(self.terrain_image)
        print(f"Generated procedural terrain image: {total_width}x{total_height}")

    def _generate_terrain_image_textured(self):
        """Generate terrain using atlas/DDS textures - MATCHES WORKING CODE"""
        if not self.sectors_data:
            return

        total_width = self.sectors_x * self.grid_size
        total_height = self.sectors_y * self.grid_size
        combined_image = QImage(total_width, total_height, QImage.Format.Format_RGB888)
        combined_image.fill(Qt.GlobalColor.black)

        if not self.atlas_mapping:
            self.build_atlas_mapping()

        painter = QPainter(combined_image)

        # Use TEXTURE indexing (Avatar Game Layout with 1↔2 swap)
        for display_row in range(self.sectors_y):
            for col in range(self.sectors_x):
                # Use the Avatar pattern for textures
                sector_index = self.get_sector_index_from_position(display_row, col, 
                                                                   self.sectors_x, self.sectors_y)

                if sector_index not in self.sectors_data:
                    continue

                sector_texture = None

                # Load texture from atlas mapping
                if self.atlas_mapping and sector_index in self.atlas_mapping:
                    atlas_path, sub_sector = self.atlas_mapping[sector_index]
                    try:
                        img = Image.open(atlas_path).convert("RGB")
                        img_array = np.array(img)
                        h, w = img_array.shape[:2]
                        half_h, half_w = h // 2, w // 2

                        # Extract correct quadrant (STANDARD 2x2 layout from atlas file)
                        # The swap happens in get_sector_index_from_position, not here
                        if sub_sector == 0:  # Top-left
                            sub_img = img_array[0:half_h, 0:half_w]
                        elif sub_sector == 1:  # Top-right
                            sub_img = img_array[0:half_h, half_w:w]
                        elif sub_sector == 2:  # Bottom-left
                            sub_img = img_array[half_h:h, 0:half_w]
                        else:  # Bottom-right (3)
                            sub_img = img_array[half_h:h, half_w:w]

                        pil_img = Image.fromarray(sub_img)
                        pil_img = pil_img.resize((self.grid_size, self.grid_size), 
                                                Image.Resampling.LANCZOS)
                        sector_texture = self.pil_image_to_qimage(pil_img)
                    except Exception as e:
                        print(f"Error loading atlas {atlas_path}: {e}")
                        sector_texture = None

                # Procedural fallback
                if sector_texture is None:
                    heights = np.flipud(self.sectors_data[sector_index])
                    norm = (heights - heights.min()) / (heights.max() - heights.min() + 1e-5)
                    rgb_array = np.stack([norm * 255] * 3, axis=-1).astype(np.uint8)
                    sector_texture = QImage(rgb_array.data, self.grid_size, self.grid_size, 
                                           self.grid_size * 3, QImage.Format.Format_RGB888)

                # Draw sector (NO individual sector flipping for Avatar layout)
                start_x = col * self.grid_size
                start_y = display_row * self.grid_size
                painter.drawImage(start_x, start_y, sector_texture)

        painter.end()

        # CRITICAL: Apply 90° counter-clockwise rotation to final assembled texture
        # This matches the working code's map_rotation = 270 (which is 90° CCW)
        transform = QTransform()
        transform.rotate(-90)  # -90 = 90° counter-clockwise
        
        rotated_image = combined_image.transformed(transform)
        
        self.terrain_image = rotated_image
        self.terrain_pixmap = QPixmap.fromImage(rotated_image)
        self.combined_heightmap = None
        
        print(f"[Terrain] Generated textured terrain: {rotated_image.width()}x{rotated_image.height()} "
              f"(with 90° CCW rotation)")

    # ----------------------------
    # Atlas/XBT Mapping - STANDARD SEQUENTIAL
    # ----------------------------
    def build_atlas_mapping(self):
        """Build mapping from sectors to atlas/DDS textures
        
        Standard sequential mapping: Each atlas contains 4 sectors.
        atlas0 → sectors 0,1,2,3
        atlas2 → sectors 4,5,6,7  
        atlas4 → sectors 8,9,10,11
        etc.
        """
        if not self.current_directory:
            return

        self.atlas_mapping = {}
        temp_folder = os.path.join(tempfile.gettempdir(), "terrain_textures")
        os.makedirs(temp_folder, exist_ok=True)

        layer = self.texture_layer.get() if self.texture_layer else "diffuse"

        # Collect all atlas files
        atlas_files = []
        for ext in ['.xbt', '.dds', '.png', '.tga']:
            atlas_files.extend(glob.glob(os.path.join(self.current_directory, f"atlas*_{layer}{ext}")))

        if not atlas_files:
            print(f"No atlas files found for layer '{layer}'")
            return

        # Extract atlas numbers and sort
        atlas_numbers = set()
        for filepath in atlas_files:
            filename = os.path.basename(filepath)
            try:
                parts = filename.split('_')[0]  # "atlas123"
                num = int(parts.replace('atlas', ''))
                atlas_numbers.add(num)
            except (ValueError, IndexError):
                continue

        atlas_numbers = sorted(list(atlas_numbers))
        print(f"Found {len(atlas_numbers)} {layer} atlas files: {atlas_numbers[:10]}...")

        sector_counter = 0
        for atlas_index, atlas_num in enumerate(atlas_numbers):
            # Find the actual file for this atlas number
            atlas_path = None
            for ext in ['.xbt', '.dds', '.png', '.tga']:
                test_path = os.path.join(self.current_directory, f"atlas{atlas_num}_{layer}{ext}")
                if os.path.exists(test_path):
                    atlas_path = test_path
                    break
            
            if not atlas_path:
                continue

            # If it's XBT, extract DDS
            if atlas_path.lower().endswith(".xbt"):
                temp_img = self.load_xbt_as_dds_tempfile(atlas_path, temp_folder=temp_folder)
                if temp_img is None:
                    print(f"Failed to extract {atlas_path}")
                    continue
                atlas_path_to_use = os.path.join(temp_folder, 
                                                 os.path.basename(atlas_path).replace(".xbt", ".dds"))
            else:
                atlas_path_to_use = atlas_path

            # Map each quadrant to sequential sectors
            # Each atlas has 4 sectors in standard 2x2 layout
            for sub_sector in range(4):
                self.atlas_mapping[sector_counter] = (atlas_path_to_use, sub_sector)
                sector_counter += 1

        print(f"Mapped {len(self.atlas_mapping)} sectors to atlas textures")

    def load_xbt_as_dds_tempfile(self, xbt_path, temp_folder=None):
        """Extract DDS from XBT file"""
        try:
            with open(xbt_path, 'rb') as f:
                data = f.read()

            dds_offset = data.find(b'DDS ')
            if dds_offset < 0:
                print(f"DDS magic not found in {xbt_path}")
                return None

            dds_data = data[dds_offset:]

            if temp_folder is None:
                temp_folder = tempfile.gettempdir()
            os.makedirs(temp_folder, exist_ok=True)

            base_name = os.path.basename(xbt_path)
            temp_dds_path = os.path.join(temp_folder, base_name.replace('.xbt', '.dds'))

            with open(temp_dds_path, 'wb') as tmp_file:
                tmp_file.write(dds_data)

            img = Image.open(temp_dds_path)
            img.load()
            return img

        except Exception as e:
            print(f"Failed to load XBT {xbt_path}: {e}")
            return None

    # ----------------------------
    # Utilities
    # ----------------------------
    def pil_image_to_qimage(self, pil_img):
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        return QImage(
            pil_img.tobytes(),
            pil_img.width,
            pil_img.height,
            3 * pil_img.width,
            QImage.Format.Format_RGB888
        )

    def render_terrain_2d(self, painter: QPainter, canvas):
        if not self.show_terrain or self.terrain_pixmap is None:
            return
        try:
            painter.save()
            painter.setOpacity(self.terrain_opacity)
            terrain_width = self.terrain_pixmap.width()
            terrain_height = self.terrain_pixmap.height()
            pixels_per_world_unit = 1.0
            terrain_world_width = terrain_width * pixels_per_world_unit
            terrain_world_height = terrain_height * pixels_per_world_unit
            screen_x_min, screen_y_max = canvas.world_to_screen(0, 0)
            screen_x_max, screen_y_min = canvas.world_to_screen(terrain_world_width, terrain_world_height)
            screen_width = screen_x_max - screen_x_min
            screen_height = screen_y_max - screen_y_min
            painter.drawPixmap(
                int(screen_x_min),
                int(screen_y_min),
                int(screen_width),
                int(screen_height),
                self.terrain_pixmap
            )
            painter.restore()
        except Exception as e:
            print(f"Error rendering terrain: {e}")
            import traceback
            traceback.print_exc()

    def toggle_terrain(self):
        self.show_terrain = not self.show_terrain
        print(f"Terrain visibility: {self.show_terrain}")

    def set_opacity(self, opacity: float):
        self.terrain_opacity = max(0.0, min(1.0, opacity))
        print(f"Terrain opacity: {self.terrain_opacity}")

    def load_folder(self, folder_path, is_fc2=False):
        return self.load_sdat_folder(folder_path)

    def set_world_bounds(self, grid_config):
        if grid_config is None or self.combined_heightmap is None:
            return
        sector_size = grid_config.sector_granularity
        self.terrain_world_min_x = 0
        self.terrain_world_min_y = 0
        self.terrain_world_max_x = self.sectors_x * sector_size * self.grid_size
        self.terrain_world_max_y = self.sectors_y * sector_size * self.grid_size
        print(f"Terrain world bounds: ({self.terrain_world_min_x}, {self.terrain_world_min_y}) "
              f"to ({self.terrain_world_max_x}, {self.terrain_world_max_y})")
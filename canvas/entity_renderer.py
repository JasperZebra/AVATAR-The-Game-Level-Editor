"""Entity rendering for 2D mode - 2D ONLY VERSION"""

import math
from time import time
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QVector3D, QPolygon, QPixmap
from .opengl_utils import OpenGLUtils
import os

class EntityRenderer:
    """Handles rendering of entities in 2D mode - 2D ONLY"""
    
    def __init__(self):
        # Enhanced entity type colors - matching simplified_map_editor.py
        self.type_colors = {
            # Vehicles
            "Vehicle": QColor(52, 152, 255),      # Blue - Vehicles
            
            # Characters and NPCs  
            "NPC": QColor(46, 255, 113),          # Green - NPCs/Characters
            "Character": QColor(46, 255, 113),    # Green - NPCs/Characters
            
            # Weapons and combat
            "Weapon": QColor(255, 76, 60),        # Red - Weapons/Explosives
            "Explosive": QColor(255, 76, 60),     # Red - Weapons/Explosives
            
            # Mission and gameplay
            "Spawn": QColor(255, 156, 18),        # Orange - Spawn Locations
            "Mission": QColor(185, 89, 255),      # Purple - Mission Objects
            "Objective": QColor(185, 89, 255),    # Purple - Mission Objects
            "Checkpoint": QColor(255, 156, 18),   # Orange - Spawn Locations
            
            # Interactive objects
            "Trigger": QColor(255, 230, 15),      # Yellow - Triggers/Zones
            "Zone": QColor(255, 230, 15),         # Yellow - Triggers/Zones
            "Area": QColor(255, 230, 15),         # Yellow - Triggers/Zones
            "Region": QColor(255, 230, 15),       # Yellow - Triggers/Zones
            
            # Environment and props
            "Prop": QColor(170, 180, 190),        # Gray - Props/Static Objects
            "StaticObject": QColor(170, 180, 190), # Gray - Props/Static Objects
            "Building": QColor(170, 180, 190),    # Gray - Props/Static Objects
            "Structure": QColor(170, 180, 190),   # Gray - Props/Static Objects
            "Container": QColor(170, 180, 190),   # Gray - Props/Static Objects
            
            # Lighting and effects
            "Light": QColor(255, 255, 160),       # Light Yellow - Lights
            "Lamp": QColor(255, 255, 160),        # Light Yellow - Lights
            "Spotlight": QColor(255, 255, 160),   # Light Yellow - Lights
            "Effect": QColor(0, 255, 200),        # Teal - Effects/Particles
            "Particle": QColor(0, 255, 200),      # Teal - Effects/Particles
            "VFX": QColor(0, 255, 200),           # Teal - Effects/Particles
            
            # Navigation and waypoints
            "Waypoint": QColor(185, 89, 255),     # Purple - Mission Objects
            "Path": QColor(185, 89, 255),         # Purple - Mission Objects
            "Node": QColor(185, 89, 255),         # Purple - Mission Objects
            "Navpoint": QColor(185, 89, 255),     # Purple - Mission Objects
            
            # Audio
            "Sound": QColor(0, 255, 200),         # Teal - Effects/Particles
            "Audio": QColor(0, 255, 200),         # Teal - Effects/Particles
            "Music": QColor(0, 255, 200),         # Teal - Effects/Particles
            "Ambience": QColor(0, 255, 200),      # Teal - Effects/Particles
            
            # Camera and cinematics
            "Camera": QColor(185, 89, 255),       # Purple - Mission Objects
            "View": QColor(185, 89, 255),         # Purple - Mission Objects
            "Cinematic": QColor(185, 89, 255),    # Purple - Mission Objects
            
            # Special data sources
            "WorldSectors": QColor(255, 100, 100), # Red - WorldSectors Objects
            "Landmarks": QColor(255, 100, 100),    # Red - WorldSectors Objects
            
            # Nature and terrain
            "Tree": QColor(170, 180, 190),        # Gray - Props/Static Objects
            "Plant": QColor(170, 180, 190),       # Gray - Props/Static Objects
            "Rock": QColor(170, 180, 190),        # Gray - Props/Static Objects
            "Water": QColor(170, 180, 190),       # Gray - Props/Static Objects
            
            # Default
            "Unknown": QColor(130, 130, 130)      # Dark Gray - Unknown Type
        }        
        
        # Enhanced entity type detection patterns
        self.type_patterns = {
            # Vehicles
            "Vehicle": ["vehicle", "car", "truck", "boat", "ship", "plane", "buggy", "atv", "quad", 
                    "ampsuit", "samson", "scorpion", "valkyrie", "dragon", "helicopter"],
            
            # Characters and NPCs
            "NPC": ["npc", "character", "ai_", "enemy", "friend", "ally", "neutral", "rhino", 
                "viperwolf", "banshee", "thanator", "avatar", "navi", "marine", "soldier"],
            "Character": ["char_", "avatar_", "npc_"],
            
            # Weapons and combat
            "Weapon": ["weapon", "gun", "rifle", "pistol", "sword", "bow", "arrow", "spear", 
                    "shotgun", "flamethrower"],
            "Explosive": ["bomb", "explosive", "grenade", "mine", "tnt"],
            
            # Mission and gameplay
            "Spawn": ["spawn", "start", "respawn", "SpawnPoint_"],
            "Mission": ["mission", "objective", "goal", "target"],
            "Objective": ["objective", "goal", "target"],
            "Checkpoint": ["checkpoint", "savepoint", "check_"],
            
            # Interactive objects
            "Trigger": ["trigger"],
            "Zone": ["zone"],
            "Area": ["area"],
            "Region": ["region"],
            
            # Environment and props
            "Prop": ["prop_", "object_", "static_"],
            "StaticObject": ["so.", "static_object", "staticobject"],
            "Building": ["building", "house", "structure_build"],
            "Structure": ["structure", "construct", "fence", "fence_"],
            "Container": ["container", "box", "crate", "barrel"],
            
            # Lighting and effects
            "Light": ["light"],
            "Lamp": ["lamp"],
            "Spotlight": ["spotlight", "spot_light"],
            "Effect": ["fx_", "effect"],
            "Particle": ["particle", "particles"],
            "VFX": ["vfx_", "visual_effect"],
            
            # Navigation and waypoints
            "Waypoint": ["waypoint", "wp_"],
            "Path": ["path", "route"],
            "Node": ["node", "nav_node"],
            "Navpoint": ["navpoint", "navigation_point"],
            
            # Audio
            "Sound": ["sound"],
            "Audio": ["audio"],
            "Music": ["music"],
            "Ambience": ["ambience", "ambient"],
            
            # Camera and cinematics
            "Camera": ["camera"],
            "View": ["view"],
            "Cinematic": ["cinematic", "cutscene"],
            
            # Nature and terrain
            "Tree": ["tree", "palm", "oak", "pine", "Mossy_Tree"],
            "Plant": ["plant", "bush", "grass", "flower"],
            "Rock": ["rock", "stone", "boulder"],
            "Water": ["water", "river", "lake", "ocean"],
        }
        
        # Vehicle icon mapping - maps icon keys to PNG filenames
        self.HIDNAME_TO_ICON = {
            "vehicle.air.paraglider": "paraglider.png",
            "vehicle.avatar.ampsuit": "ampsuit.png",
            "vehicle.avatar.atv": "atv.png",
            "vehicle.avatar.banshee": "banshee.png",
            "vehicle.avatar.boat_drivable": "boat.png",
            "vehicle.avatar.buggy_drivable": "buggy.png",
            "vehicle.avatar.bulldozer": "bulldozer.png",
            "vehicle.avatar.dove_drivable": "dove.png",
            "vehicle.avatar.dragon": "dragon.png",
            "vehicle.avatar.leonopteryx": "leonopteryx.png",
            "vehicle.avatar.samson_pilotable": "samson.png",
            "vehicle.avatar.scorpion_pilotable": "scorpion.png",
            "vehicle.avatar.valkyrie": "valkyrie.png",
            "vehicle.avatar.wheelloader_drivable": "wheelloader.png",
            "vehicle.corp_lights.buggy_light": "buggy_light.png",
            "vehicle.corp_lights.dove_light": "dove_light.png",
            "vehicle.corp_lights.dragon_light": "dragon_light.png",
            "vehicle.land.bigtruck": "bigtruck.png",
            "vehicle.land.buggy": "buggy.png",
            "vehicle.land.datsun": "datsun.png",
            "vehicle.land.jeepliberty": "jeepliberty.png",
            "vehicle.land.jeepwrangler": "jeepwrangler.png",
            "vehicle.land.rover": "rover.png",
            "vehicle.sea.fishingboat": "fishingboat.png",
            "vehicle.sea.gunboat": "gunboat.png",
            "vehicle.sea.hydroboat": "hydroboat.png",
            "vehicle.sea.pirogue": "pirogue.png",
            "vehicle.sea.swampboat": "swampboat.png",
            "vehicle.test.avatararmedvehicle": "test_vehicle.png",
            "vehicle.test.avatarboat": "test_boat.png",
            "vehicle.test.testboat": "test_boat.png",
            "vehicle.wreck.carburned01_bk": "wreck_car.png",
            "vehicle.wreck.carwrecked01_bk": "wreck_car.png",
        }
        
        # Icon cache - stores loaded QPixmaps
        self.icon_cache = {}
        self.icons_directory = None
        
        # Icon display settings
        self.icon_size = 32  # Default icon size in pixels
        self.show_vehicle_icons = True

        # Vehicle-specific icon sizes (in pixels)
        self.VEHICLE_ICON_SIZES = {
            # Large vehicles
            "vehicle.avatar.samson_pilotable": 80,
            "vehicle.avatar.dragon": 48,
            "vehicle.avatar.valkyrie": 48,
            "vehicle.avatar.leonopteryx": 56,
            "vehicle.avatar.bulldozer": 44,
            "vehicle.avatar.wheelloader_drivable": 44,
            "vehicle.land.bigtruck": 44,
            
            # Medium vehicles
            "vehicle.avatar.scorpion_pilotable": 40,
            "vehicle.avatar.ampsuit": 40,
            "vehicle.avatar.buggy_drivable": 36,
            "vehicle.avatar.dove_drivable": 36,
            "vehicle.avatar.atv": 34,
            "vehicle.land.buggy": 36,
            "vehicle.land.rover": 36,
            "vehicle.land.jeepliberty": 36,
            "vehicle.land.jeepwrangler": 36,
            "vehicle.land.datsun": 34,
            
            # Small vehicles/creatures
            "vehicle.avatar.banshee": 38,
            "vehicle.avatar.boat_drivable": 36,
            "vehicle.sea.fishingboat": 38,
            "vehicle.sea.gunboat": 40,
            "vehicle.sea.hydroboat": 34,
            "vehicle.sea.pirogue": 32,
            "vehicle.sea.swampboat": 36,
            
            # Very small
            "vehicle.air.paraglider": 28,
            
            # Light variants
            "vehicle.corp_lights.buggy_light": 36,
            "vehicle.corp_lights.dove_light": 36,
            "vehicle.corp_lights.dragon_light": 48,
            
            # Wrecks
            "vehicle.wreck.carburned01_bk": 34,
            "vehicle.wreck.carwrecked01_bk": 34,
            
            # Test vehicles
            "vehicle.test.avatararmedvehicle": 40,
            "vehicle.test.avatarboat": 36,
            "vehicle.test.testboat": 36,
        }
                
        # Performance tracking
        self._last_2d_log_time = 0
        self._frame_count = 0

        # Entity cache system
        self.entity_cache = {}
        self.cache_version = 0
        
        # PERFORMANCE OPTIMIZATION: Batch rendering data
        self._batch_circles = []
        self._batch_size = 500
        
        print("EntityRenderer initialized - 2D ONLY")

    def set_icons_directory(self, directory_path):
        """Set the directory containing vehicle icon PNGs"""
        if os.path.isdir(directory_path):
            self.icons_directory = directory_path
            print(f"Vehicle icons directory set: {directory_path}")
            # Don't pre-load - we'll load on-demand for selected entities
            print("Icons will be loaded on-demand when entities are selected")
        else:
            print(f"Invalid icons directory: {directory_path}")

    def _preload_icons(self):
        """DEPRECATED - No longer pre-loading all icons"""
        pass 

    def get_entity_icon(self, entity):
        """Get icon pixmap for an entity, returns None if no icon available"""
        if not self.show_vehicle_icons:
            print("DEBUG: show_vehicle_icons is False")
            return None
        
        if not self.icons_directory:
            print("DEBUG: icons_directory not set")
            return None
        
        # DEBUG: Print entity attributes
        entity_name = getattr(entity, 'name', 'unknown')
        print(f"\n=== ICON DEBUG for {entity_name} ===")
        print(f"Entity attributes: {[attr for attr in dir(entity) if not attr.startswith('_')][:20]}")
        
        # Try to get vehicle identifier from multiple sources
        icon_key = None
        
        # Method 1: Check tplCreatureType (most reliable for vehicles)
        tpl_creature_type = getattr(entity, 'tplCreatureType', None)
        print(f"tplCreatureType: {tpl_creature_type}")
        if tpl_creature_type:
            icon_key = self._match_vehicle_pattern(tpl_creature_type)
            print(f"Pattern matched tplCreatureType to: {icon_key}")
        
        # Method 2: Check hidName if no match yet
        if not icon_key:
            hidname = getattr(entity, 'hidName', None)
            print(f"hidName: {hidname}")
            if hidname:
                icon_key = self._match_vehicle_pattern(hidname)
                print(f"Pattern matched hidName to: {icon_key}")
        
        # Method 3: Check name attribute
        if not icon_key:
            name = getattr(entity, 'name', None)
            print(f"name: {name}")
            if name:
                icon_key = self._match_vehicle_pattern(name)
                print(f"Pattern matched name to: {icon_key}")
        
        # If we found a key, check cache or load it
        if icon_key:
            print(f"Final icon_key: {icon_key}")
            
            # Check if already in cache
            if icon_key in self.icon_cache:
                print(f"✓ Found in cache")
                return self.icon_cache[icon_key]
            
            # Not in cache - load it now
            if icon_key in self.HIDNAME_TO_ICON:
                filename = self.HIDNAME_TO_ICON[icon_key]
                icon_path = os.path.join(self.icons_directory, filename)
                print(f"Attempting to load: {icon_path}")
                
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # Cache it for next time
                        self.icon_cache[icon_key] = pixmap
                        print(f"✓ Loaded icon: {filename}")
                        return pixmap
                    else:
                        print(f"✗ Failed to load icon (null pixmap): {icon_path}")
                else:
                    print(f"✗ Icon file not found: {icon_path}")
            else:
                print(f"✗ icon_key '{icon_key}' not in HIDNAME_TO_ICON mapping")
        else:
            print(f"✗ No icon_key found for this entity")
        
        print("=== END ICON DEBUG ===\n")
        return None

    def _match_vehicle_pattern(self, vehicle_string):
        """Match vehicle string to vehicle icon key by pattern matching"""
        if not vehicle_string:
            return None
        
        vehicle_lower = vehicle_string.lower()
        
        # Direct exact match (case-insensitive)
        if vehicle_lower in self.HIDNAME_TO_ICON:
            return vehicle_lower
        
        # Remove common suffixes and try again
        clean_string = vehicle_lower
        for suffix in ['.scripted', '.static', '.drivable', '.pilotable', '_drivable', '_pilotable', 
                       '.multi', '.controlled', '.npcversion', '.rogue', '.fortnavarone']:
            clean_string = clean_string.replace(suffix, '')
        
        if clean_string in self.HIDNAME_TO_ICON:
            return clean_string
        
        # Pattern matching for specific vehicles
        vehicle_patterns = {
            # Avatar vehicles
            'samson': 'vehicle.avatar.samson_pilotable',
            'scorpion': 'vehicle.avatar.scorpion_pilotable',
            'valkyrie': 'vehicle.avatar.valkyrie',
            'dragon': 'vehicle.avatar.dragon',
            'ampsuit': 'vehicle.avatar.ampsuit',
            'banshee': 'vehicle.avatar.banshee',
            'leonopteryx': 'vehicle.avatar.leonopteryx',
            'dove': 'vehicle.avatar.dove_drivable',
            'atv': 'vehicle.avatar.atv',
            'bulldozer': 'vehicle.avatar.bulldozer',
            'wheelloader': 'vehicle.avatar.wheelloader_drivable',
            
            # Far Cry 2 vehicles
            'paraglider': 'vehicle.air.paraglider',
            'bigtruck': 'vehicle.land.bigtruck',
            'datsun': 'vehicle.land.datsun',
            'jeepliberty': 'vehicle.land.jeepliberty',
            'jeepwrangler': 'vehicle.land.jeepwrangler',
            'rover': 'vehicle.land.rover',
            'fishingboat': 'vehicle.sea.fishingboat',
            'gunboat': 'vehicle.sea.gunboat',
            'hydroboat': 'vehicle.sea.hydroboat',
            'pirogue': 'vehicle.sea.pirogue',
            'swampboat': 'vehicle.sea.swampboat',
        }
        
        # Check for vehicle patterns in the string
        for pattern, icon_key in vehicle_patterns.items():
            if pattern in vehicle_lower:
                # Special handling for buggy vs buggy_light
                if pattern == 'buggy':
                    if 'light' in vehicle_lower:
                        return 'vehicle.corp_lights.buggy_light'
                    # Check if it's avatar buggy or fc2 buggy
                    if 'avatar' in vehicle_lower or 'corp' in vehicle_lower:
                        return 'vehicle.avatar.buggy_drivable'
                    else:
                        return 'vehicle.land.buggy'
                
                # Special handling for boat variants
                if pattern == 'boat' and 'avatar.boat' in vehicle_lower:
                    return 'vehicle.avatar.boat_drivable'
                
                return icon_key
        
        # Special cases for light variants
        if 'dove' in vehicle_lower and 'light' in vehicle_lower:
            return 'vehicle.corp_lights.dove_light'
        if 'dragon' in vehicle_lower and 'light' in vehicle_lower:
            return 'vehicle.corp_lights.dragon_light'
        
        # Check for wrecks
        if 'wreck' in vehicle_lower or 'burned' in vehicle_lower:
            return 'vehicle.wreck.carburned01_bk'
        
        return None

    def determine_entity_type(self, entity):
        """Enhanced entity type determination - CACHED"""
        # Check cache first
        entity_id = id(entity)
        if entity_id in self.entity_cache:
            cached_data = self.entity_cache[entity_id]
            if 'entity_type' in cached_data:
                return cached_data['entity_type']
        
        # Handle both entity objects and entity names
        if isinstance(entity, str):
            entity_name = entity
            entity_obj = None
        else:
            entity_name = getattr(entity, 'name', 'unknown')
            entity_obj = entity
        
        entity_name_lower = entity_name.lower()
        
        # Check if entity has object_type attribute
        if entity_obj and hasattr(entity_obj, 'object_type') and entity_obj.object_type:
            obj_type = entity_obj.object_type
            if obj_type in self.type_colors:
                return obj_type
        
        # Check for special data sources first
        if entity_obj:
            source_file_type = getattr(entity_obj, 'source_file_type', None)
            if source_file_type == "worldsector":
                return "WorldSectors"
            elif source_file_type == "landmark":
                return "Landmarks"
        
        # Check against enhanced patterns
        for entity_type, patterns in self.type_patterns.items():
            for pattern in patterns:
                if pattern in entity_name_lower:
                    return entity_type
        
        # Fallback to basic pattern matching
        if any(keyword in entity_name_lower for keyword in ["fence", "wall", "barrier"]):
            return "Structure"
        
        if any(keyword in entity_name_lower for keyword in ["pickup", "item", "collectible"]):
            return "Mission"
        
        return "Unknown"

    def get_entity_size_by_type(self, entity):
        """Enhanced size multipliers for more entity types - CACHED"""
        # Check cache first
        entity_id = id(entity)
        if entity_id in self.entity_cache:
            cached_data = self.entity_cache[entity_id]
            if 'size_multiplier' in cached_data:
                return cached_data['size_multiplier']
        
        if hasattr(entity, 'object_type') and entity.object_type:
            entity_type = entity.object_type
        else:
            entity_type = self.determine_entity_type(entity)
        
        size_multipliers = {
            # Large objects
            "Vehicle": 1.0,
            "Building": 1.0,
            "Structure": 1.0,
            
            # Medium objects
            "NPC": 1.0,
            "Character": 1.0,
            "StaticObject": 0.9,
            "Container": 0.9,
            "Tree": 1.0,
            
            # Small objects
            "Weapon": 0.8,
            "Prop": 0.8,
            "Light": 0.8,
            "Lamp": 0.8,
            "Sound": 0.8,
            "Audio": 0.8,
            
            # Tiny objects
            "Waypoint": 0.8,
            "Node": 0.8,
            "Effect": 0.8,
            "Particle": 0.8,
            
            # Mission objects
            "Mission": 0.8,
            "Objective": 0.8,
            "Spawn": 1.0,
            "Checkpoint": 0.8,
            
            # Interactive areas
            "Trigger": 0.8,
            "Zone": 0.8,
            "Area": 0.8,
            "Region": 0.8,
            
            # Special
            "WorldSectors": 0.8,
            "Landmarks": 0.8,
            
            # Default
            "Unknown": 0.8
        }
        
        return size_multipliers.get(entity_type, 0.8)
    
    def get_or_cache_entity_data(self, entity):
        """Get comprehensive cached entity data - OPTIMIZED"""
        entity_id = id(entity)
        
        # Check if entity has current cache
        if (entity_id in self.entity_cache and 
            self.entity_cache[entity_id].get('cache_version') == self.cache_version):
            return self.entity_cache[entity_id]
        
        # Compute all entity data once
        entity_type = self.determine_entity_type(entity)
        size_multiplier = self.get_entity_size_by_type(entity)
        is_fence = self.is_fence_object(entity)
        
        entity_data = {
            'cache_version': self.cache_version,
            'entity_type': entity_type,
            'size_multiplier': size_multiplier,
            'is_fence': is_fence,
            'name': getattr(entity, 'name', 'unknown'),
            'normal_color': self.type_colors.get(entity_type, self.type_colors["Unknown"]),
            'selected_color': QColor(0, 0, 255),  # Blue selection color
            'rotation': 0.0,
            'rotation_cache_time': 0
        }
        
        # Cache it
        self.entity_cache[entity_id] = entity_data
        return entity_data

    def render_entities_2d(self, painter, canvas, entities):
        """2D rendering with squares and batch processing, including fences with rotation"""
        if not entities:
            return
        
        self._frame_count += 1
        current_time = time()
        
        # Reduce logging frequency to every 5 seconds
        should_log = current_time - self._last_2d_log_time > 5.0
        
        if should_log:
            print(f"Rendering {len(entities)} entities in 2D mode (OPTIMIZED)")
            self._last_2d_log_time = current_time
        
        # Enable antialiasing for smooth lines and pixmaps
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        # Check for highlighting
        has_highlighted = hasattr(canvas, 'icon_renderer') and hasattr(canvas.icon_renderer, 'highlighted_entities_list') and canvas.icon_renderer.highlighted_entities_list
        highlight_flash_state = False
        
        if has_highlighted:
            for highlight_info in canvas.icon_renderer.highlighted_entities_list:
                time_elapsed = current_time - highlight_info['start_time']
                flash_count = highlight_info['flash_count']
                flash_period = highlight_info['duration'] / flash_count
                highlight_flash_state = int(time_elapsed / flash_period) % 2 == 0
                break
        
        entities_drawn = 0
        entities_culled = 0
        icons_drawn = 0
        selected_entities = getattr(canvas, 'selected', [])
        
        # CONSTANT SCREEN SIZES (pixels)
        ICON_SIZE_PIXELS = 32  # Icon size in pixels
        SQUARE_SIZE_PIXELS = 10  # Square size in pixels
        SELECTED_SQUARE_SIZE_PIXELS = 12  # Larger for selected
        
        batch_size = self._batch_size
        
        for batch_start in range(0, len(entities), batch_size):
            batch_end = min(batch_start + batch_size, len(entities))
            batch_entities = entities[batch_start:batch_end]
            
            squares_to_draw = []
            icons_to_draw = []
            
            for entity in batch_entities:
                try:
                    x_raw, y_raw = OpenGLUtils.world_to_screen(entity.x, entity.y, canvas)
                    x = int(round(x_raw))
                    y = int(round(y_raw))
                    
                    # Culling
                    margin = 100
                    canvas_width = canvas.width()
                    canvas_height = canvas.height()
                    
                    if (x < -margin or x > canvas_width + margin or 
                        y < -margin or y > canvas_height + margin):
                        entities_culled += 1
                        continue
                    
                    entity_data = self.get_or_cache_entity_data(entity)
                    
                    is_selected = entity in selected_entities
                    is_highlighted = False
                    if has_highlighted:
                        for highlight_info in canvas.icon_renderer.highlighted_entities_list:
                            if highlight_info['entity'] == entity:
                                is_highlighted = True
                                break
                    
                    # Get rotation for the icon (read from XML like gizmo does)
                    rotation = 0.0
                    if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                        angles_field = entity.xml_element.find("./field[@name='hidAngles']")
                        if angles_field is not None:
                            angles_value = angles_field.get('value-Vector3')
                            if angles_value:
                                try:
                                    parts = angles_value.split(',')
                                    if len(parts) >= 3:
                                        game_rotation = float(parts[2].strip())
                                        rotation = (360 - game_rotation) % 360
                                except (ValueError, IndexError):
                                    pass
                    
                    # Check if entity has an icon (only for SELECTED entities)
                    icon_pixmap = None
                    if is_selected:
                        icon_pixmap = self.get_entity_icon(entity)
                    
                    # Determine square properties - FIXED SIZE IN PIXELS
                    if is_highlighted and highlight_flash_state:
                        color = QColor(255, 255, 255)
                        size = SELECTED_SQUARE_SIZE_PIXELS
                        outline_width = 3
                    elif is_selected:
                        color = entity_data['selected_color']
                        size = SELECTED_SQUARE_SIZE_PIXELS
                        outline_width = 2
                    else:
                        color = entity_data['normal_color']
                        size = SQUARE_SIZE_PIXELS
                        outline_width = 1
                    
                    # Add icon for rendering if available (only for selected)
                    if icon_pixmap:
                        # Get vehicle-specific size or use default - FIXED SIZE IN PIXELS
                        icon_key = self._match_vehicle_pattern(entity.name)
                        vehicle_size = self.VEHICLE_ICON_SIZES.get(icon_key, ICON_SIZE_PIXELS)
                        
                        icons_to_draw.append({
                            'x': x,
                            'y': y,
                            'pixmap': icon_pixmap,
                            'size': vehicle_size,  # Already in pixels
                            'rotation': rotation,
                            'is_selected': is_selected,
                            'is_highlighted': is_highlighted and highlight_flash_state
                        })
                        icons_drawn += 1

                    # Add square for all entities (drawn on top of icon)
                    squares_to_draw.append({
                        'x': x,
                        'y': y,
                        'size': size,  # Size in pixels
                        'color': color,
                        'outline_width': outline_width,
                        'entity': entity,
                        'is_selected': is_selected,
                        'is_highlighted': is_highlighted and highlight_flash_state
                    })
                    
                    # Draw rotated fence line if entity is a fence
                    if entity_data['is_fence']:
                        self.draw_fence_indicator_optimized(painter, entity, x, y, canvas)
                    
                    entities_drawn += 1
                    
                except Exception as e:
                    if should_log:
                        print(f"Error processing entity: {e}")
                    continue
            
            # Draw icons FIRST (underneath squares)
            self.draw_batch_icons(painter, icons_to_draw)
            
            # Then draw squares on top
            self.draw_batch_circles(painter, squares_to_draw)
            
            # Draw labels for selected/highlighted entities
            for square_data in squares_to_draw:
                if square_data['is_selected'] or square_data['is_highlighted']:
                    self._draw_entity_label_2d_optimized(
                        painter, square_data['entity'], 
                        square_data['x'], square_data['y'], 
                        square_data['size'], square_data['is_highlighted']
                    )
        
        if should_log:
            print(f"Drew {entities_drawn} entities ({icons_drawn} icons) in 2D mode (culled: {entities_culled})")

    def draw_batch_icons(self, painter, icons_data):
        """Draw multiple vehicle icons efficiently with rotation"""
        if not icons_data:
            return  # Removed debug print - this is normal when nothing is selected
        
        for icon_info in icons_data:
            x = icon_info['x']
            y = icon_info['y']
            pixmap = icon_info['pixmap']
            size = icon_info['size']
            rotation = icon_info.get('rotation', 0.0)
            is_selected = icon_info['is_selected']
            is_highlighted = icon_info['is_highlighted']
            
            # Save painter state
            painter.save()
            
            # Move to the entity position
            painter.translate(x, y)
            
            # Rotate around the center
            painter.rotate(rotation)
            
            # Scale pixmap to desired size
            scaled_pixmap = pixmap.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Calculate position (center the icon)
            half_size = size // 2
            draw_x = -half_size
            draw_y = -half_size
                        
            # Draw the icon
            painter.drawPixmap(draw_x, draw_y, scaled_pixmap)
            
            # Restore painter state
            painter.restore()

    def draw_square(self, painter, x, y, size):
        """Draw a square centered at (x, y) with side length = size * 2"""
        from PyQt6.QtCore import QRectF

        half = size
        rect = QRectF(x - half, y - half, size * 2, size * 2)
        painter.drawRect(rect)

    def draw_batch_circles(self, painter, circles_data):
        """Draw multiple SQUARES efficiently using the same batching system."""
        if not circles_data:
            return
        
        circles_by_style = {}
        
        for circle in circles_data:
            style_key = (
                circle['color'].rgb(),
                circle['outline_width']
            )
            
            if style_key not in circles_by_style:
                circles_by_style[style_key] = []
            
            circles_by_style[style_key].append(circle)
        
        for (color_rgb, outline_width), circle_group in circles_by_style.items():
            color = QColor()
            color.setRgb(color_rgb)
            
            painter.setPen(QPen(Qt.GlobalColor.black, outline_width))
            painter.setBrush(QBrush(color))
            
            for circle in circle_group:
                radius = circle['size']
                self.draw_square(painter, circle['x'], circle['y'], radius)

    def draw_fence_indicator_optimized(self, painter, entity, screen_x, screen_y, canvas):
        """Draw fence line with static-size endpoint circles"""
        if not self.is_fence_object(entity):
            return False

        # Get Z rotation from hidAngles
        rotation = 0.0
        hid_angles = getattr(entity, 'hidAngles', None)
        if hid_angles:
            rotation = hid_angles[2]  # Z-axis rotation

        # Adjust to match game orientation
        rotation += 90

        # Cache for performance
        entity_data = self.get_or_cache_entity_data(entity)
        entity_data['rotation'] = rotation

        # Fence line calculation
        fence_width_world = 24
        half_width_screen = (fence_width_world * canvas.scale_factor) / 2
        angle_rad = math.radians(rotation)
        dx = half_width_screen * math.cos(angle_rad)
        dy = half_width_screen * math.sin(angle_rad)

        start_x = int(screen_x - dx)
        start_y = int(screen_y - dy)
        end_x = int(screen_x + dx)
        end_y = int(screen_y + dy)

        # Draw the main fence line
        painter.setPen(QPen(QColor(255, 0, 0), 3))
        painter.drawLine(start_x, start_y, end_x, end_y)

        # Draw static-size endpoint circles (same size as squares)
        painter.setBrush(QBrush(QColor(255, 0, 0)))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        radius = 8  # static pixel radius
        painter.drawEllipse(start_x - radius, start_y - radius, radius * 2, radius * 2)
        painter.drawEllipse(end_x - radius, end_y - radius, radius * 2, radius * 2)

        return True

    def _draw_entity_label_2d_optimized(self, painter, entity, x, y, size, is_highlighted):
        """Optimized 2D label drawing"""
        entity_name = getattr(entity, 'name', 'Unknown')
        
        # Simplified label for performance
        if len(entity_name) > 50:
            entity_name = entity_name[:50] + "..."
        
        painter.setFont(QFont("Arial", 8))  # Smaller font for performance
        
        if is_highlighted:
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setBrush(QBrush(QColor(255, 255, 0, 200)))
        else:
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        
        # Simple text positioning
        text_x = x + size + 5
        text_y = y
        
        # Draw simple background
        metrics = painter.fontMetrics()
        text_width = metrics.boundingRect(entity_name).width()
        painter.fillRect(text_x - 2, text_y - metrics.ascent() - 2, 
                        text_width + 4, metrics.height() + 4, 
                        QColor(0, 0, 0, 150))
        
        # Draw text
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawText(text_x, text_y, entity_name)

    def is_fence_object(self, entity):
        """Check if entity is a fence object - CACHED"""
        entity_id = id(entity)
        if entity_id in self.entity_cache:
            cached_data = self.entity_cache[entity_id]
            if 'is_fence' in cached_data:
                return cached_data['is_fence']
        
        entity_name = getattr(entity, 'name', '')
        is_fence = "SO.corp_fence_security_" in entity_name
        
        # Cache the result
        if entity_id not in self.entity_cache:
            self.entity_cache[entity_id] = {}
        self.entity_cache[entity_id]['is_fence'] = is_fence
        
        return is_fence
    
    def invalidate_entity_cache(self, entity):
        """Invalidate cache for specific entity"""
        entity_id = id(entity)
        if entity_id in self.entity_cache:
            del self.entity_cache[entity_id]

    def invalidate_all_caches(self):
        """Invalidate all entity caches by bumping version"""
        self.cache_version += 1
        print(f"Cache version bumped to {self.cache_version}")

    def invalidate_all_entity_caches(self):
        """Invalidate cached data for ALL entities"""
        self.entity_cache.clear()
        self.cache_version += 1
        print(f"All entity caches cleared, version: {self.cache_version}")
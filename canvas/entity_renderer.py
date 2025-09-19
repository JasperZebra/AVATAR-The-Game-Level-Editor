"""Entity rendering for 2D mode - 2D ONLY VERSION"""

import math
from time import time
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QVector3D, QPolygon
from .opengl_utils import OpenGLUtils

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
            'selected_color': QColor(52, 152, 255),  # Blue selection color
            'rotation': 0.0,
            'rotation_cache_time': 0
        }
        
        # Cache it
        self.entity_cache[entity_id] = entity_data
        return entity_data

    def render_entities_2d(self, painter, canvas, entities):
        """2D rendering with circles and batch processing"""
        if not entities:
            return
        
        self._frame_count += 1
        current_time = time()
        
        # Reduce logging frequency to every 5 seconds
        should_log = current_time - self._last_2d_log_time > 5.0
        
        if should_log:
            print(f"Rendering {len(entities)} entities in 2D mode (OPTIMIZED)")
            self._last_2d_log_time = current_time
        
        # Disable antialiasing for performance
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
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
        selected_entities = getattr(canvas, 'selected', [])
        
        # Process entities in batches
        batch_size = self._batch_size
        
        for batch_start in range(0, len(entities), batch_size):
            batch_end = min(batch_start + batch_size, len(entities))
            batch_entities = entities[batch_start:batch_end]
            
            circles_to_draw = []
            
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
                    
                    # Determine circle properties
                    if is_highlighted and highlight_flash_state:
                        color = QColor(255, 255, 255)
                        size = 10
                        outline_width = 3
                    elif is_selected:
                        color = entity_data['selected_color']
                        size = 10
                        outline_width = 2
                    else:
                        color = entity_data['normal_color']
                        size = 8
                        outline_width = 1
                    
                    final_size = int(round(size * entity_data['size_multiplier']))
                    final_size = max(3, final_size)
                    
                    if entity_data['is_fence']:
                        self.draw_fence_indicator_optimized(painter, entity, x, y, canvas)
                    else:
                        circles_to_draw.append({
                            'x': x,
                            'y': y,
                            'size': final_size,
                            'color': color,
                            'outline_width': outline_width,
                            'entity': entity,
                            'is_selected': is_selected,
                            'is_highlighted': is_highlighted and highlight_flash_state
                        })
                    
                    entities_drawn += 1
                    
                except Exception as e:
                    if should_log:
                        print(f"Error processing entity: {e}")
                    continue
            
            # Batch render circles
            self.draw_batch_circles(painter, circles_to_draw)
            
            # Draw labels for selected/highlighted entities
            for circle_data in circles_to_draw:
                if circle_data['is_selected'] or circle_data['is_highlighted']:
                    self._draw_entity_label_2d_optimized(
                        painter, circle_data['entity'], 
                        circle_data['x'], circle_data['y'], 
                        circle_data['size'], circle_data['is_highlighted']
                    )
        
        if should_log:
            print(f"Drew {entities_drawn} entities in 2D mode (culled: {entities_culled})")

    def draw_batch_circles(self, painter, circles_data):
        """Draw multiple circles efficiently in a batch"""
        if not circles_data:
            return
        
        # Group circles by similar properties to minimize state changes
        circles_by_style = {}
        
        for circle in circles_data:
            # Create style key
            style_key = (
                circle['color'].rgb(),
                circle['outline_width']
            )
            
            if style_key not in circles_by_style:
                circles_by_style[style_key] = []
            
            circles_by_style[style_key].append(circle)
        
        # Draw each style group in batch
        for (color_rgb, outline_width), circle_group in circles_by_style.items():
            # Set painter state once per group
            color = QColor()
            color.setRgb(color_rgb)
            
            painter.setPen(QPen(Qt.GlobalColor.black, outline_width))
            painter.setBrush(QBrush(color))
            
            # Draw all circles with this style
            for circle in circle_group:
                radius = circle['size']
                painter.drawEllipse(
                    circle['x'] - radius, 
                    circle['y'] - radius, 
                    radius * 2, 
                    radius * 2
                )

    def draw_fence_indicator_optimized(self, painter, entity, screen_x, screen_y, canvas):
        """Optimized fence drawing with simple line"""
        if not self.is_fence_object(entity):
            return False
        
        # Get cached rotation
        entity_data = self.get_or_cache_entity_data(entity)
        rotation = entity_data.get('rotation', 0)
        
        # Calculate fence line (simplified)
        fence_width_world = 24
        half_width_screen = (fence_width_world * canvas.scale_factor) / 2
        
        line_angle_rad = math.radians(rotation)
        dx = half_width_screen * math.cos(line_angle_rad)
        dy = half_width_screen * math.sin(line_angle_rad)
        
        start_x = int(screen_x - dx)
        start_y = int(screen_y - dy)
        end_x = int(screen_x + dx)
        end_y = int(screen_y + dy)
        
        # Draw simple red line (no house shape for performance)
        painter.setPen(QPen(QColor(255, 0, 0), 3))
        painter.drawLine(start_x, start_y, end_x, end_y)
        
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
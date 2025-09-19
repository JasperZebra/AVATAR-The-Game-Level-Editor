"""Main GPU-accelerated map canvas - 2D ONLY VERSION - No Terrain/Icons"""

from time import time
import math
import numpy as np
import OpenGL.GL as gl
from PyQt6.QtGui import QMatrix4x4, QVector3D
import math
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPixmap, QTransform, QFont, QPen, QVector4D
from PyQt6.QtWidgets import (
    QMessageBox, 
    QDialog, 
    QVBoxLayout, 
    QHBoxLayout,
    QLabel, 
    QTreeWidget, 
    QTreeWidgetItem,
    QPushButton
)

# Import GPU components
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    import OpenGL.GL as gl
    OPENGL_AVAILABLE = True
    print("OpenGL libraries loaded successfully")
except ImportError as e:
    from PyQt6.QtWidgets import QWidget as QOpenGLWidget  # Fallback
    OPENGL_AVAILABLE = False
    print(f"OpenGL not available ({e}) - falling back to CPU rendering")

# Import our modular components
from .grid_renderer import GridRenderer
from .entity_renderer import EntityRenderer
from .icon_renderer import IconRenderer
from .gizmo_renderer import GizmoRenderer
from .input_handler import InputHandler
from .camera_controller import CameraController
from .opengl_utils import OpenGLUtils

class MapCanvas(QOpenGLWidget):
    """Main GPU-accelerated canvas widget - 2D ONLY VERSION"""
    
    # Signals
    entitySelected = pyqtSignal(object)
    position_update = pyqtSignal(object, tuple)
    move_points = pyqtSignal(float, float, float)
    height_update = pyqtSignal(float)
    create_waypoint = pyqtSignal(float, float)
    rotate_current = pyqtSignal(object)

    def __init__(self, parent=None):
        """Initialize MapCanvas - 2D ONLY"""
        super().__init__(parent)
        self.main_window = parent
        
        # Set minimum size
        self.setMinimumSize(600, 400)

        self.mode = 0  # 0 = 2D mode
        
        # OpenGL setup
        self.opengl_initialized = False
        self.use_gpu_rendering = OPENGL_AVAILABLE
        
        # Initialize core canvas state
        self.entities = []
        self.selected_entity = None
        self.selected = []
        self.selected_positions = []
        self.selected_rotations = []
        self.scale_factor = 1.0
        
        # Canvas offset attributes (managed by camera controller)
        self.offset_x = 0
        self.offset_y = 0
        
        self.grid_config = None
        self.current_map = None
        
        # View options (2D only)
        self.show_grid = True
        self.show_entities = True
        
        # RENDERING SYSTEM
        self.entities_modified = False
        self.selection_modified = False
        
        self.last_mouse_world_pos = (0, 0)  # 2D only
        
        # SECTOR DISPLAY OPTIONS (keep for 2D)
        self.show_sector_boundaries = False
        self.sector_data = []

        # Setup all rendering modules
        self.setup_renderers()
        
        # Setup canvas properties
        self.setup_canvas()
        
        print(f"MapCanvas initialized - 2D ONLY VERSION (OpenGL: {self.use_gpu_rendering})")

    def setup_renderers(self):
        """Initialize all renderer modules - 2D ONLY"""
        try:
            # Create renderer instances
            self.grid_renderer = GridRenderer()
            self.entity_renderer = EntityRenderer()
            self.icon_renderer = IconRenderer()  # Only UI overlays now
            self.gizmo_renderer = GizmoRenderer()
            self.camera_controller = CameraController()
            self.input_handler = InputHandler(self)
            
            # Enable OpenGL in grid renderer if available
            if self.use_gpu_rendering:
                self.grid_renderer.use_opengl = True
            
            print("All renderer modules initialized (2D ONLY)")
            
        except Exception as e:
            print(f"Error setting up renderers: {e}")
            import traceback
            traceback.print_exc()

    def setup_canvas(self):
        """Setup canvas properties and timers"""
        # Setup movement timer for smooth camera movement
        self.movement_timer = QTimer(self)
        self.movement_timer.setInterval(16)  # 60 FPS for smooth camera movement
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start()
        
        # Mouse and keyboard setup
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        
        print("Canvas event handling setup complete - 2D ONLY")

    def initializeGL(self):
        """Initialize OpenGL context and resources"""
        if not self.use_gpu_rendering:
            return
            
        try:
            print("Initializing OpenGL...")
            
            # Get OpenGL version info
            version = gl.glGetString(gl.GL_VERSION).decode()
            vendor = gl.glGetString(gl.GL_VENDOR).decode()
            renderer = gl.glGetString(gl.GL_RENDERER).decode()
            
            print(f"OpenGL Version: {version}")
            print(f"GPU Vendor: {vendor}")
            print(f"GPU Renderer: {renderer}")
            
            # Set OpenGL states for 2D
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            gl.glEnable(gl.GL_LINE_SMOOTH)
            gl.glHint(gl.GL_LINE_SMOOTH_HINT, gl.GL_NICEST)
            
            # Initialize grid renderer OpenGL resources
            if hasattr(self, 'grid_renderer'):
                success = self.grid_renderer.initialize_gl()
                if success:
                    print("Grid renderer OpenGL initialized")
                else:
                    print("Grid renderer OpenGL initialization failed")
                    self.use_gpu_rendering = False
                    self.grid_renderer.use_opengl = False
            
            self.opengl_initialized = True
            print("OpenGL initialization complete - 2D ONLY")
            
        except Exception as e:
            print(f"OpenGL initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.use_gpu_rendering = False
            self.opengl_initialized = False
            if hasattr(self, 'grid_renderer'):
                self.grid_renderer.use_opengl = False
    
    def resizeGL(self, width, height):
        """Handle OpenGL viewport resize"""
        if not self.use_gpu_rendering:
            return
            
        try:
            gl.glViewport(0, 0, width, height)
            print(f"ðŸŽ§ OpenGL viewport resized: {width}x{height}")
        except Exception as e:
            print(f"Error resizing OpenGL viewport: {e}")
    
    def paintGL(self):
        """OpenGL 2D rendering ONLY"""
        if not self.use_gpu_rendering or not self.opengl_initialized:
            return
            
        try:
            # Set background color for 2D
            gl.glClearColor(0.94, 0.94, 0.94, 1.0)  # Light gray for 2D
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            self._render_2d_opengl()
                
        except Exception as e:
            print(f"Error in paintGL: {e}")
            import traceback
            traceback.print_exc()

    def _render_2d_opengl(self):
        """Render 2D scene using OpenGL"""
        # Render 2D grid
        if self.show_grid:
            self.grid_renderer.render_2d_grid(self)
        
        # For 2D entities and UI, we still need QPainter overlay
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        try:
            # Render entities in 2D
            if self.show_entities:
                entities_to_draw = self._get_visible_entities()
                if entities_to_draw:
                    self.entity_renderer.render_entities_2d(painter, self, entities_to_draw)
            
            # Render 2D UI overlays
            self.icon_renderer.render_all_overlays(painter, self)
            self.gizmo_renderer.render_rotation_gizmo_2d(painter, self)
            
            # Render sector boundaries in 2D
            if getattr(self, 'show_sector_boundaries', False):
                self.draw_sector_boundaries(painter)
                
        finally:
            painter.end()

    def paintEvent(self, event):
        """Only use OpenGL rendering - no QPainter fallback"""
        if self.use_gpu_rendering and self.opengl_initialized:
            # OpenGL rendering is handled by paintGL
            super().paintEvent(event)
        else:
            # Initialize OpenGL if not done yet
            if not self.opengl_initialized:
                self.initializeGL()
            # Force OpenGL usage
            super().paintEvent(event)

    def _get_visible_entities(self):
        """Get entities that are actually visible on screen with spatial culling"""
        if not hasattr(self, 'entities'):
            return []
        
        if not self.entities:
            return []
        
        if not self.show_entities:
            return []
        
        # Filter by current map first
        entities_to_check = self.entities
        if hasattr(self, 'current_map') and self.current_map is not None:
            entities_to_check = [e for e in entities_to_check if getattr(e, 'map_name', None) == self.current_map.name]
        
        # 2D spatial culling
        margin_pixels = 50  # Small margin for partially visible entities
        
        try:
            # Get world coordinates of screen corners
            world_left, world_bottom = self.screen_to_world(-margin_pixels, self.height() + margin_pixels)
            world_right, world_top = self.screen_to_world(self.width() + margin_pixels, -margin_pixels)
            
            # Pre-filter entities by spatial bounds
            visible_entities = []
            culled_count = 0
            
            for entity in entities_to_check:
                if hasattr(entity, 'x') and hasattr(entity, 'y'):
                    # Check if entity is within visible world bounds
                    if (world_left <= entity.x <= world_right and 
                        world_bottom <= entity.y <= world_top):
                        visible_entities.append(entity)
                    else:
                        culled_count += 1
            
            # Debug info (only log occasionally to avoid spam)
            if not hasattr(self, '_last_cull_log_time'):
                self._last_cull_log_time = 0
            
            current_time = time()
            if current_time - self._last_cull_log_time > 3.0:  # Log every 3 seconds
                total_entities = len(entities_to_check)
                visible_count = len(visible_entities)
                print(f"Spatial culling: {visible_count}/{total_entities} visible (culled {culled_count})")
                self._last_cull_log_time = current_time
            
            return visible_entities
            
        except Exception as e:
            print(f"Error in spatial culling: {e}")
            # Fallback to all entities if culling fails
            return entities_to_check

    def invalidate_entity_caches(self):
        """Invalidate all entity-related caches"""
        # Invalidate 3D entity cache
        self.entity_cache_dirty = True
        self.last_3d_camera_pos = None
        self.last_3d_camera_angles = None
        
        # Invalidate entity renderer caches
        if hasattr(self, 'entity_renderer'):
            self.entity_renderer.invalidate_all_entity_caches()
        
        # Mark entities as modified
        self.entities_modified = True
        self.selection_modified = True
        
        print("All entity caches invalidated")

    def update_entity_xml(self, entity):
        """Update entity XML coordinates and invalidate cache"""
        # Invalidate cache since entity changed
        self.entities_modified = True
        
        if not entity:
            return False
        
        source_file_path = getattr(entity, 'source_file_path', None)
        
        if source_file_path:
            # Check for WorldSector files
            if source_file_path.endswith('.data.xml') or source_file_path.endswith('.converted.xml'):
                return self._update_worldsector_xml_fcb_format(entity, source_file_path)
        else:
            # Main file entity
            return self._update_memory_xml_dunia_format(entity)
        
        return False

    def _update_worldsector_xml_fcb_format(self, entity, xml_file_path):
        """Update WorldSector XML with FCBConverter format support"""
        try:
            # Get the main window and tree
            main_window = self
            while main_window.parent():
                main_window = main_window.parent()
            
            if not hasattr(main_window, 'worldsectors_trees'):
                main_window.worldsectors_trees = {}
            
            if xml_file_path not in main_window.worldsectors_trees:
                import xml.etree.ElementTree as ET
                tree = ET.parse(xml_file_path)
                main_window.worldsectors_trees[xml_file_path] = tree
            
            tree = main_window.worldsectors_trees[xml_file_path]
            root = tree.getroot()
            
            # Find the entity in FCBConverter format
            for entity_elem in root.findall(".//object[@name='Entity']"):
                name_field = entity_elem.find("./field[@name='hidName']")
                if name_field is not None:
                    name_value = name_field.get('value-String')
                    if name_value == getattr(entity, 'name', ''):
                        # Update position fields
                        self._update_fcb_position_field(entity_elem, "hidPos", entity.x, entity.y, entity.z)
                        self._update_fcb_position_field(entity_elem, "hidPos_precise", entity.x, entity.y, entity.z)
                        
                        entity.xml_element = entity_elem
                        return True
            
            return False
            
        except Exception as e:
            print(f"Error updating FCBConverter XML coordinates: {e}")
            return False

    def _update_fcb_position_field(self, entity_elem, field_name, x, y, z):
        """Update position field in FCBConverter format"""
        pos_field = entity_elem.find(f"./field[@name='{field_name}']")
        if pos_field is not None:
            # Update the text value
            new_pos_value = f"{x:.0f},{y:.0f},{z:.0f}"
            pos_field.set('value-Vector3', new_pos_value)
            
            # Update binary hex data
            binary_hex = self._coordinates_to_binhex(x, y, z)
            pos_field.text = binary_hex

    def _coordinates_to_binhex(self, x, y, z):
        """Convert coordinates to BinHex format"""
        import struct
        binary_data = struct.pack('<fff', float(x), float(y), float(z))
        hex_string = binary_data.hex().upper()
        return hex_string

    def _update_memory_xml_dunia_format(self, entity):
        """Update main file entity coordinates with Dunia Tools format"""
        if not hasattr(entity, 'xml_element') or entity.xml_element is None:
            return False
        
        try:
            # Update hidPos with Dunia Tools format
            pos_elem = entity.xml_element.find("./value[@name='hidPos']")
            if pos_elem is not None:
                x_elem = pos_elem.find("./x")
                y_elem = pos_elem.find("./y")
                z_elem = pos_elem.find("./z")
                
                if x_elem is not None:
                    x_elem.text = f"{entity.x:.0f}"
                if y_elem is not None:
                    y_elem.text = f"{entity.y:.0f}"
                if z_elem is not None:
                    z_elem.text = f"{entity.z:.0f}"
            
            # Update hidPos_precise
            pos_precise_elem = entity.xml_element.find("./value[@name='hidPos_precise']")
            if pos_precise_elem is not None:
                x_elem = pos_precise_elem.find("./x")
                y_elem = pos_precise_elem.find("./y")
                z_elem = pos_precise_elem.find("./z")
                
                if x_elem is not None:
                    x_elem.text = f"{entity.x:.0f}"
                if y_elem is not None:
                    y_elem.text = f"{entity.y:.0f}"
                if z_elem is not None:
                    z_elem.text = f"{entity.z:.0f}"
            
            return True
            
        except Exception as e:
            print(f"Error updating Dunia Tools XML: {e}")
            return False

    def _auto_save_entity_changes(self, entity):
        """Auto-save entity changes"""
        if not entity:
            return False
        
        try:
            # Update XML first
            self.update_entity_xml(entity)
            
            # Then save the file
            source_file_path = getattr(entity, 'source_file_path', None)
            
            if source_file_path:
                # WorldSector file
                return self._auto_save_worldsector_file(source_file_path)
            else:
                # Main file
                return self._auto_save_main_file()
                
        except Exception as e:
            print(f"Error auto-saving entity {getattr(entity, 'name', 'unknown')}: {e}")
            return False

    def _auto_save_worldsector_file(self, xml_file_path):
        """Auto-save WorldSector file"""
        try:
            main_window = self
            while main_window.parent():
                main_window = main_window.parent()
            
            if (hasattr(main_window, 'worldsectors_trees') and 
                xml_file_path in main_window.worldsectors_trees):
                tree = main_window.worldsectors_trees[xml_file_path]
                tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                
                # Mark as modified
                if not hasattr(main_window, 'worldsectors_modified'):
                    main_window.worldsectors_modified = {}
                main_window.worldsectors_modified[xml_file_path] = True
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error auto-saving WorldSector file: {e}")
            return False

    def _auto_save_main_file(self):
        """Auto-save main XML file"""
        try:
            main_window = self
            while main_window.parent():
                main_window = main_window.parent()
            
            if (hasattr(main_window, 'xml_tree') and 
                hasattr(main_window, 'xml_file_path')):
                main_window.xml_tree.write(main_window.xml_file_path, encoding='utf-8', xml_declaration=True)
                main_window.xml_tree_modified = True
                if hasattr(main_window, 'entities_modified'):
                    main_window.entities_modified = True
                return True
            
            return False
            
        except Exception as e:
            print(f"Error auto-saving main file: {e}")
            return False

    def mark_entity_modified(self, entity):
        """Mark a specific entity as modified and invalidate related caches"""
        if not entity:
            return
        
        # Invalidate caches for this specific entity
        if hasattr(self, 'entity_renderer'):
            self.entity_renderer.invalidate_entity_cache(entity)
        
        # Invalidate global caches
        self.invalidate_entity_caches()
        
        print(f"Entity {getattr(entity, 'name', 'unknown')} marked as modified")

    def mark_entities_modified(self):
        """Mark entities as modified for redraw"""
        self.entities_modified = True
        if self.parent():
            if hasattr(self.parent(), 'entities_modified'):
                self.parent().entities_modified = True

    # =========================================================================
    # Event Handlers - Delegate to InputHandler (2D ONLY)
    # =========================================================================
    
    def mousePressEvent(self, event):
        """Handle mouse press for entity selection in 2D"""
        if event.button() == Qt.MouseButton.LeftButton:
            mouse_x = event.position().x()
            mouse_y = event.position().y()
            
            # Store mouse world position for paste-at-cursor functionality
            world_pos = self.screen_to_world(mouse_x, mouse_y)
            self.last_mouse_world_pos = (world_pos[0], world_pos[1])
            
            # CRITICAL: Check gizmo interaction FIRST before any entity selection
            if (hasattr(self, 'selected_entity') and self.selected_entity and 
                hasattr(self, 'gizmo_renderer')):
                if self.gizmo_renderer.rotation_gizmo.is_point_on_circle(mouse_x, mouse_y, self):
                    print("Canvas detected gizmo click - delegating to input handler")
                    # Let input handler handle gizmo interaction - don't do entity selection
                    self.input_handler.handle_mouse_press(event)
                    return  # Exit early to prevent entity selection interference
            
            # Only do entity selection if we didn't click on gizmo
            selected_entity = self.select_entity_2d(mouse_x, mouse_y)
            
            # Update selection
            if selected_entity:
                self.selected = [selected_entity]
                self.selected_entity = selected_entity
                
                # Update gizmo if it exists
                if hasattr(self, 'gizmo_renderer'):
                    self.gizmo_renderer.update_gizmo_for_entity(selected_entity)
                
                # Emit selection signal
                self.entitySelected.emit(selected_entity)
                print(f"Selected entity: {selected_entity.name}")
            else:
                # Clear selection
                self.selected = []
                self.selected_entity = None
                
                if hasattr(self, 'gizmo_renderer'):
                    self.gizmo_renderer.hide_gizmo()
            
            self.update()
        
        # Let input handler handle other mouse operations (middle mouse, right click, etc.)
        self.input_handler.handle_mouse_press(event)

    def mouseMoveEvent(self, event):
        """Throttled mouse move handling"""
        current_time = time()
        
        # Only update every 16ms (60 FPS) for smooth performance
        if not hasattr(self, '_last_mouse_update'):
            self._last_mouse_update = 0
        
        if current_time - self._last_mouse_update < 0.016:  # 16ms = 60 FPS
            return
        
        self._last_mouse_update = current_time
        self.input_handler.handle_mouse_move(event)
        
        # Always update canvas for 2D
        self.update()

    def mouseReleaseEvent(self, event):
        """Delegate mouse release to input handler"""
        try:
            self.input_handler.handle_mouse_release(event)
        except Exception as e:
            print(f"Error in mouseReleaseEvent: {e}")

    def wheelEvent(self, event):
        """Delegate wheel events to input handler"""
        try:
            self.input_handler.handle_wheel(event)
            self.update()  # Always update for zoom operations
        except Exception as e:
            print(f"Error in wheelEvent: {e}")

    def keyPressEvent(self, event):
        """Delegate key press to input handler"""
        try:
            self.input_handler.handle_key_press(event)
        except Exception as e:
            print(f"Error in keyPressEvent: {e}")

    def keyReleaseEvent(self, event):
        """Delegate key release to input handler"""
        try:
            self.input_handler.handle_key_release(event)
        except Exception as e:
            print(f"Error in keyReleaseEvent: {e}")
    
    def resizeEvent(self, event):
        """Handle canvas resize"""
        super().resizeEvent(event)
        self.update()
    
    def select_entity_2d(self, mouse_x, mouse_y):
        """Select entity in 2D mode"""
        if not self.entities:
            return None
        
        # Convert mouse coordinates to world coordinates
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)
        
        # Find closest entity
        closest_entity = None
        closest_distance = float('inf')
        selection_radius = 10.0 / self.scale_factor  # Adjust selection radius based on zoom
        
        for entity in self.entities:
            dx = entity.x - world_x
            dy = entity.y - world_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance < selection_radius and distance < closest_distance:
                closest_distance = distance
                closest_entity = entity
        
        return closest_entity

    def update_movement(self):
        """Update camera movement (called by timer) - 2D ONLY"""
        try:
            # Check if any movement is needed
            if not self.camera_controller.needs_update():
                return  # No movement, skip expensive updates
            
            # Update camera movement first
            self.camera_controller.update_movement(self)
            
            # 2D mode always updates immediately for smooth panning
            self.update()
                
        except Exception as e:
            print(f"Error in update_movement: {e}")
            # Fallback: always update to prevent getting stuck
            self.update()

    # =========================================================================
    # Public API Methods (2D ONLY)
    # =========================================================================
    
    def set_entities(self, entities):
        """Set entities and populate cache"""
        print(f"Setting {len(entities)} entities...")
        self.entities = entities
        
        # Ensure show_entities is always True when setting entities
        self.show_entities = True
        
        # Pre-populate cache for all entities
        if hasattr(self, 'entity_renderer'):
            start_time = time()
            for entity in entities:
                self.entity_renderer.get_or_cache_entity_data(entity)
            
            cache_time = time() - start_time
            print(f"Built entity cache in {cache_time:.2f}s")
        
        # Reset selection state
        self.selected_entity = None
        self.selected = []
        
        # Mark entities as available and modified
        self.entities_modified = True
        self.selection_modified = True
        
        if entities:
            self._center_view_on_entities()
        
        print(f"Entities set: count={len(entities)}, show_entities={self.show_entities}")
        self.update()

    def set_grid_config(self, grid_config):
        """Set the grid configuration"""
        self.grid_config = grid_config
        self.update()
    
    def set_current_map(self, map_info):
        """Set the current map to display"""
        self.current_map = map_info
        self.entities_modified = True  # Map change affects visible entities
        self.update()
    
    def flash_entity(self, entity):
        """Flash an entity to highlight it"""
        if self.icon_renderer:
            self.icon_renderer.flash_entity(entity)
        self.update()
    
    def zoom_to_entity(self, entity):
        """Zoom to a specific entity"""
        if not entity:
            return
        
        self.camera_controller.zoom_to_entity_2d(entity, self)
        
        # Flash the entity to highlight it
        self.flash_entity(entity)
    
    def reset_view(self):
        """Reset view to show all entities"""
        if not self.entities:
            # No entities - reset to default view
            self.camera_controller.offset_x = self.width() / 2
            self.camera_controller.offset_y = self.height() / 2
            self.offset_x = self.camera_controller.offset_x
            self.offset_y = self.camera_controller.offset_y
            self.scale_factor = 1.0
            
            self.update()
            return self.scale_factor  # Return the scale factor
        
        # Center on all entities
        self._center_view_on_entities()
        self.update()
        return self.scale_factor  # Return the scale factor after centering

    def force_enable_sector_boundaries(self):
        """Force-enable sector boundary display (even if off)"""
        self.show_sector_boundaries = True
        print("Sector boundaries forced ON")
        self.update()
    
    def create_fallback_sector_data(self):
        """Create fallback sector data when load_sector_data_from_entities is missing"""
        print("Creating fallback sector data...")
        
        if not hasattr(self, 'entities') or not self.entities:
            self.sector_data = []
            return
        
        # Group entities by 64-unit sectors
        sector_map = {}
        
        for entity in self.entities:
            if not (hasattr(entity, 'x') and hasattr(entity, 'y')):
                continue
                
            # Calculate sector coordinates
            sector_x = int(entity.x // 64)
            sector_y = int(entity.y // 64)
            sector_key = (sector_x, sector_y)
            
            if sector_key not in sector_map:
                sector_map[sector_key] = {
                    'id': len(sector_map) + 1,  # Simple sequential ID
                    'x': sector_x,
                    'y': sector_y,
                    'size': 64,
                    'entities': [],
                    'expected_ids': []
                }
            
            sector_map[sector_key]['entities'].append(entity)
            
            # Add entity ID to expected_ids
            entity_id = getattr(entity, 'id', id(entity))
            if entity_id not in sector_map[sector_key]['expected_ids']:
                sector_map[sector_key]['expected_ids'].append(entity_id)
        
        # Convert to list and store
        self.sector_data = list(sector_map.values())
        
        print(f"Created fallback sector data: {len(self.sector_data)} sectors")
        for sector in self.sector_data:
            print(f"Added sector {sector['id']} with {len(sector['entities'])} entities")

    def draw_sector_boundaries(self, painter):
        """Draw sector boundaries as colored rectangles (2D only)"""
        if not getattr(self, 'show_sector_boundaries', False):
            return

        if not hasattr(self, 'sector_data') or not self.sector_data:
            print("No sector_data, creating fallback...")
            self.create_fallback_sector_data()
            if not self.sector_data:
                return

        try:
            from PyQt6.QtGui import QPen, QBrush, QColor, QFont

            boundaries_drawn = 0

            # Save original painter state
            original_pen = painter.pen()
            original_brush = painter.brush()
            original_font = painter.font()

            for i, sector_info in enumerate(self.sector_data):
                try:
                    sector_id = sector_info.get('id', 0)
                    sector_x = sector_info.get('x', 0)
                    sector_y = sector_info.get('y', 0)
                    sector_size = sector_info.get('size', 64)

                    # World bounds
                    world_min_x = sector_x * sector_size
                    world_min_y = sector_y * sector_size
                    world_max_x = world_min_x + sector_size
                    world_max_y = world_min_y + sector_size

                    # Convert corners to screen coords
                    top_left = self.world_to_screen(world_min_x, world_max_y)
                    top_right = self.world_to_screen(world_max_x, world_max_y)
                    bottom_left = self.world_to_screen(world_min_x, world_min_y)
                    bottom_right = self.world_to_screen(world_max_x, world_min_y)

                    xs = [top_left[0], top_right[0], bottom_left[0], bottom_right[0]]
                    ys = [top_left[1], top_right[1], bottom_left[1], bottom_right[1]]

                    rect_x = min(xs)
                    rect_y = min(ys)
                    rect_w = max(xs) - rect_x
                    rect_h = max(ys) - rect_y

                    if rect_w < 2 or rect_h < 2:
                        continue

                    # Skip if completely offscreen
                    margin = 50
                    if (rect_x > self.width() + margin or
                        rect_y > self.height() + margin or
                        rect_x + rect_w < -margin or
                        rect_y + rect_h < -margin):
                        continue

                    # FIXED: Check for violations using the corrected method
                    has_violations = False
                    try:
                        if hasattr(self, "check_sector_violations"):
                            has_violations = self.check_sector_violations(sector_info)
                        else:
                            # Fallback: check entities directly
                            entities_in_sector = sector_info.get('entities', [])
                            for entity in entities_in_sector:
                                violations = self.get_entity_violations(entity)
                                if violations:
                                    has_violations = True
                                    break
                    except Exception as violation_error:
                        print(f"Error checking violations for sector {sector_id}: {violation_error}")
                        has_violations = False

                    if has_violations:
                        pen_color = QColor(255, 100, 0, 255)   # orange
                        brush_color = QColor(255, 100, 0, 40)
                        pen_width = 3
                    else:
                        pen_color = QColor(255, 0, 0, 200)     # red
                        brush_color = QColor(255, 0, 0, 30)
                        pen_width = 2

                    painter.setPen(QPen(pen_color, pen_width))
                    painter.setBrush(QBrush(brush_color))

                    # Draw sector rectangle
                    painter.drawRect(int(rect_x), int(rect_y), int(rect_w), int(rect_h))
                    boundaries_drawn += 1

                    # Draw label
                    label_text = f"Sector {sector_id}"
                    if has_violations:
                        label_text += " Warning"

                    painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
                    metrics = painter.fontMetrics()
                    text_rect = metrics.boundingRect(label_text)

                    bg_padding = 2
                    label_x = int(rect_x + 3)
                    label_y = int(rect_y + 15)

                    bg_x = label_x - bg_padding
                    bg_y = label_y - text_rect.height() - bg_padding
                    bg_w = text_rect.width() + (bg_padding * 2)
                    bg_h = text_rect.height() + (bg_padding * 2)

                    painter.fillRect(bg_x, bg_y, bg_w, bg_h, QColor(0, 0, 0, 200))
                    painter.setPen(QPen(QColor(255, 255, 255), 1))
                    painter.drawRect(bg_x, bg_y, bg_w, bg_h)

                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.drawText(label_x, label_y, label_text)

                except Exception as sector_error:
                    print(f"Error processing sector {i}: {sector_error}")
                    continue

            # Restore original state
            painter.setPen(original_pen)
            painter.setBrush(original_brush)
            painter.setFont(original_font)

            print(f"Drew {boundaries_drawn}/{len(self.sector_data)} sector boundaries")

        except Exception as e:
            print(f"Error in draw_sector_boundaries: {e}")
            import traceback
            traceback.print_exc()

    def load_sector_data_from_entities(self):
        """Extract sector data from loaded worldsector entities - IMPROVED VERSION"""
        print("Loading sector data from entities...")
        
        if not hasattr(self, 'entities') or not self.entities:
            print("No entities available")
            return
        
        # Group entities by their source files
        sector_files = {}
        worldsector_entities = []
        
        for entity in self.entities:
            source_file = getattr(entity, 'source_file_path', '')
            
            # Check if this is a worldsector entity
            if source_file and 'worldsector' in source_file.lower():
                worldsector_entities.append(entity)
                
                if source_file not in sector_files:
                    sector_files[source_file] = []
                sector_files[source_file].append(entity)
        
        print(f"Found {len(worldsector_entities)} worldsector entities in {len(sector_files)} files")
        
        # If no worldsector entities, create test sectors for demonstration
        if not sector_files:
            print("No worldsector entities found - creating test sectors for demonstration")
            self.sector_data = self.create_test_sectors_from_all_entities()
            return
        
        self.sector_data = []
        
        # Process each sector file
        for source_file, entities in sector_files.items():
            try:
                # Extract sector number from filename
                import re
                match = re.search(r'worldsector(\d+)', source_file.lower())
                if not match:
                    print(f"Could not extract sector number from: {source_file}")
                    continue
                
                sector_id = int(match.group(1))
                
                # Try to get sector metadata from the XML file
                sector_info = self.extract_sector_metadata_fixed(source_file, sector_id, entities)
                if not sector_info:
                    # Fallback: create sector info from entity positions
                    sector_info = self.create_sector_from_entities(sector_id, entities)
                
                if sector_info:
                    sector_info['entities'] = entities
                    sector_info['entity_count'] = len(entities)
                    self.sector_data.append(sector_info)
                    print(f"Added sector {sector_id} with {len(entities)} entities")
                    
            except Exception as e:
                print(f"Error processing sector file {source_file}: {e}")
        
        print(f"Loaded sector data for {len(self.sector_data)} sectors")
        
        # Sort sectors by ID for consistent display
        self.sector_data.sort(key=lambda x: x.get('id', 0))

    def create_test_sectors_from_all_entities(self):
        """Create test sectors by analyzing all entity positions"""
        print("Creating test sectors from all entity positions...")
        
        if not self.entities:
            # Create a simple test sector at origin
            return [{
                'id': 0,
                'x': 0,
                'y': 0,
                'size': 64,
                'file_path': 'test_sector',
                'is_test': True,
                'entities': [],
                'entity_count': 0
            }]
        
        # Find bounds of all entities
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for entity in self.entities:
            if hasattr(entity, 'x') and hasattr(entity, 'y'):
                min_x = min(min_x, entity.x)
                max_x = max(max_x, entity.x)
                min_y = min(min_y, entity.y)
                max_y = max(max_y, entity.y)
        
        if min_x == float('inf'):
            # No valid entities, create origin sector
            return [{
                'id': 0,
                'x': 0,
                'y': 0,
                'size': 64,
                'file_path': 'test_sector',
                'is_test': True,
                'entities': [],
                'entity_count': 0
            }]
        
        # Calculate sector grid that covers all entities
        sector_size = 64
        min_sector_x = int(min_x // sector_size)
        max_sector_x = int(max_x // sector_size)
        min_sector_y = int(min_y // sector_size)
        max_sector_y = int(max_y // sector_size)
        
        test_sectors = []
        sector_id = 0
        
        # Create sectors to cover the entity area
        for sx in range(min_sector_x, max_sector_x + 1):
            for sy in range(min_sector_y, max_sector_y + 1):
                # Find entities in this sector
                sector_entities = []
                world_min_x = sx * sector_size
                world_min_y = sy * sector_size
                world_max_x = world_min_x + sector_size
                world_max_y = world_min_y + sector_size
                
                for entity in self.entities:
                    if (hasattr(entity, 'x') and hasattr(entity, 'y') and
                        world_min_x <= entity.x < world_max_x and
                        world_min_y <= entity.y < world_max_y):
                        sector_entities.append(entity)
                
                test_sectors.append({
                    'id': sector_id,
                    'x': sx,
                    'y': sy,
                    'size': sector_size,
                    'file_path': f'test_sector_{sector_id}',
                    'is_test': True,
                    'entities': sector_entities,
                    'entity_count': len(sector_entities)
                })
                
                print(f"   Created test sector {sector_id}: grid=({sx}, {sy}) with {len(sector_entities)} entities")
                sector_id += 1
        
        print(f"Created {len(test_sectors)} test sectors covering entity area")
        return test_sectors

    def check_sector_violations(self, sector_info):
        """Check if any entities in this sector are outside its boundaries - OPTIMIZED"""
        # Use cached result if available
        if hasattr(sector_info, '_violations_checked'):
            return sector_info.get('_has_violations', False)
        
        sector_id = sector_info.get('id', 0)
        sector_x = sector_info.get('x', 0)
        sector_y = sector_info.get('y', 0)
        sector_size = sector_info.get('size', 64)
        
        # Calculate sector boundaries
        world_min_x = sector_x * sector_size
        world_min_y = sector_y * sector_size
        world_max_x = world_min_x + sector_size
        world_max_y = world_min_y + sector_size
        
        has_violations = False
        
        # Check entities that belong to this sector
        entities_to_check = sector_info.get('entities', [])
        if not entities_to_check:
            # Fallback: check all entities with matching source file
            for entity in self.entities:
                entity_source = getattr(entity, 'source_file_path', '')
                if f'worldsector{sector_id}' in entity_source:
                    entities_to_check.append(entity)
        
        for entity in entities_to_check:
            if (hasattr(entity, 'x') and hasattr(entity, 'y') and
                (entity.x < world_min_x or entity.x >= world_max_x or
                entity.y < world_min_y or entity.y >= world_max_y)):
                has_violations = True
                break
        
        # Cache the result
        sector_info['_violations_checked'] = True
        sector_info['_has_violations'] = has_violations
        
        return has_violations

    def extract_sector_metadata_fixed(self, xml_file_path, sector_id, entities):
        """Extract sector metadata from WorldSector XML file - FIXED VERSION"""
        try:
            # Get the tree from main window
            main_window = self
            while main_window.parent():
                main_window = main_window.parent()
            
            # Try to get the tree from worldsectors_trees
            tree = None
            if hasattr(main_window, 'worldsectors_trees') and xml_file_path in main_window.worldsectors_trees:
                tree = main_window.worldsectors_trees[xml_file_path]
            else:
                # Try to parse the file directly
                import os
                if os.path.exists(xml_file_path):
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(xml_file_path)
                else:
                    print(f"XML file not found: {xml_file_path}")
                    return None
            
            if not tree:
                return None
            
            root = tree.getroot()
            
            # Look for WorldSector metadata using multiple possible formats
            sector_x = None
            sector_y = None
            
            # Method 1: Look for FCBConverter format (field elements)
            x_field = root.find(".//field[@name='X']")
            if x_field is not None:
                x_value = x_field.get('value-Int32') or x_field.get('value')
                if x_value:
                    try:
                        sector_x = int(x_value)
                        print(f"Found X in FCBConverter format: {sector_x}")
                    except ValueError:
                        pass
            
            y_field = root.find(".//field[@name='Y']")
            if y_field is not None:
                y_value = y_field.get('value-Int32') or y_field.get('value')
                if y_value:
                    try:
                        sector_y = int(y_value)
                        print(f"Found Y in FCBConverter format: {sector_y}")
                    except ValueError:
                        pass
            
            # Method 2: Look for Dunia Tools format (value elements)
            if sector_x is None:
                x_value_elem = root.find(".//value[@name='X']")
                if x_value_elem is not None and x_value_elem.text:
                    try:
                        sector_x = int(x_value_elem.text)
                        print(f"Found X in Dunia format: {sector_x}")
                    except ValueError:
                        pass
            
            if sector_y is None:
                y_value_elem = root.find(".//value[@name='Y']")
                if y_value_elem is not None and y_value_elem.text:
                    try:
                        sector_y = int(y_value_elem.text)
                        print(f"Found Y in Dunia format: {sector_y}")
                    except ValueError:
                        pass
            
            if sector_x is not None and sector_y is not None:
                print(f"Extracted sector metadata: Sector {sector_id} at ({sector_x}, {sector_y})")
                return {
                    'id': sector_id,
                    'x': sector_x,
                    'y': sector_y,
                    'size': 64,  # Standard sector size
                    'file_path': xml_file_path
                }
            else:
                print(f"Could not find X/Y coordinates in {xml_file_path}")
                return None
                
        except Exception as e:
            print(f"Error extracting metadata from {xml_file_path}: {e}")
            return None

    def create_sector_from_entities(self, sector_id, entities):
        """Create sector info by analyzing entity positions - FALLBACK METHOD"""
        if not entities:
            return None
        
        try:
            # Find the bounds of all entities in this sector
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')
            
            for entity in entities:
                min_x = min(min_x, entity.x)
                min_y = min(min_y, entity.y)
                max_x = max(max_x, entity.x)
                max_y = max(max_y, entity.y)
            
            # Calculate sector coordinates (assuming 64-unit sectors)
            sector_size = 64
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            sector_x = int(center_x / sector_size)
            sector_y = int(center_y / sector_size)
            
            print(f"Created sector {sector_id} from entities: ({sector_x}, {sector_y})")
            print(f"  Entity bounds: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})")
            
            return {
                'id': sector_id,
                'x': sector_x,
                'y': sector_y,
                'size': sector_size,
                'file_path': None,
                'created_from_entities': True
            }
            
        except Exception as e:
            print(f"Error creating sector from entities: {e}")
            return None

    def get_entity_violations(self):
        """Get list of entities that are outside their sector boundaries"""
        violations = []
        
        if not hasattr(self, 'sector_data') or not self.sector_data:
            return violations
        
        try:
            for sector_info in self.sector_data:
                sector_id = sector_info.get('id', 0)
                sector_x = sector_info.get('x', 0)
                sector_y = sector_info.get('y', 0)
                sector_size = sector_info.get('size', 64)
                
                # Calculate sector boundaries
                world_min_x = sector_x * sector_size
                world_min_y = sector_y * sector_size
                world_max_x = world_min_x + sector_size
                world_max_y = world_min_y + sector_size
                
                # Check entities
                for entity in self.entities:
                    entity_source = getattr(entity, 'source_file_path', '')
                    if f'worldsector{sector_id}' not in entity_source:
                        continue
                    
                    # Check if outside boundaries
                    if (entity.x < world_min_x or entity.x >= world_max_x or
                        entity.y < world_min_y or entity.y >= world_max_y):
                        
                        violations.append({
                            'entity': entity,
                            'sector_id': sector_id,
                            'sector_bounds': (world_min_x, world_min_y, world_max_x, world_max_y),
                            'entity_pos': (entity.x, entity.y, entity.z),
                            'distance_out': max(
                                max(world_min_x - entity.x, 0),  # How far left of sector
                                max(entity.x - world_max_x, 0),  # How far right of sector
                                max(world_min_y - entity.y, 0),  # How far below sector
                                max(entity.y - world_max_y, 0)   # How far above sector
                            )
                        })
            
            return violations
            
        except Exception as e:
            print(f"Error checking entity violations: {e}")
            import traceback
            traceback.print_exc()
            return violations
    
    def zoom_in(self):
        """Zoom in"""
        self.camera_controller.zoom_in(self)

    def zoom_out(self):
        """Zoom out"""
        self.camera_controller.zoom_out(self)
    
    def set_mouse_mode(self, mode):
        """Set the mouse interaction mode"""
        # Reset any ongoing operations
        if hasattr(self.input_handler, 'dragging'):
            self.input_handler.dragging = False
        if hasattr(self.input_handler, 'panning'):
            self.input_handler.panning = False
        
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
    
    # =========================================================================
    # Coordinate Conversion (delegate to OpenGLUtils) - 2D ONLY
    # =========================================================================
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates"""
        return OpenGLUtils.world_to_screen(world_x, world_y, self)

    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates"""
        return OpenGLUtils.screen_to_world(screen_x, screen_y, self)
        
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _center_view_on_entities(self):
        """Center the view on all entities"""
        if not self.entities:
            return
        
        # Calculate bounding box
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        valid_entities = 0
        for entity in self.entities:
            if hasattr(entity, 'x') and hasattr(entity, 'y'):
                min_x = min(min_x, entity.x)
                max_x = max(max_x, entity.x)
                min_y = min(min_y, entity.y)
                max_y = max(max_y, entity.y)
                valid_entities += 1
        
        if valid_entities == 0:
            return
        
        # Calculate center
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # Calculate scale to fit all entities
        if max_x > min_x and max_y > min_y:
            width_span = max_x - min_x
            height_span = max_y - min_y
            
            # Scale to fit with padding
            scale_x = (self.width() * 0.8) / width_span if width_span > 0 else 1.0
            scale_y = (self.height() * 0.8) / height_span if height_span > 0 else 1.0
            self.scale_factor = min(scale_x, scale_y, 2.0)  # Cap at 2x zoom
        else:
            self.scale_factor = 1.0
        
        # Center the view
        new_offset_x = self.width() / 2 - center_x * self.scale_factor
        new_offset_y = self.height() / 2 - center_y * self.scale_factor
        
        # Update both camera controller and canvas offsets
        self.camera_controller.offset_x = new_offset_x
        self.camera_controller.offset_y = new_offset_y
        self.offset_x = new_offset_x
        self.offset_y = new_offset_y
        
        print(f"Centered view on {valid_entities} entities at scale {self.scale_factor:.2f}")
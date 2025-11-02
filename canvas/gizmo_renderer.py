"""Gizmo renderer for rotation tools and entity manipulation - 2D ONLY"""

import math
import time
from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QVector3D
from .opengl_utils import OpenGLUtils

class RotationGizmo:
    """Rotation gizmo for rotating entities around their Z-axis - 2D ONLY"""
    
    def __init__(self):
        self.position = QVector3D(0, 0, 0)
        self.hidden = True
        self.radius = 30
        self.thickness = 3
        self.is_dragging = False
        self.drag_start_angle = 0
        self.initial_rotation = 0
        self.current_rotation = 0
        self.drag_start_pos = (0, 0)
        
        # Performance tracking
        self._last_rotation_log_time = 0
    
    def move_to_entity(self, entity):
        """Move gizmo to entity position"""
        if entity:
            self.position = QVector3D(entity.x, entity.y, entity.z)  # Store entity coordinates
            self.hidden = False
            self.current_rotation = self.extract_entity_rotation(entity)
            self.initial_rotation = self.current_rotation
            print(f"🎯 Moved rotation gizmo to {getattr(entity, 'name', 'entity')} at ({entity.x}, {entity.y}) rotation {self.current_rotation:.1f}°")
        else:
            self.hidden = True

    def extract_entity_rotation(self, entity):
        """Extract Z rotation from entity's XML data with comprehensive caching"""
        entity_id = id(entity)
        current_time = time.time()
        
        # PRIORITY 1: Check entity renderer cache first (most reliable)
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'entity_renderer'):
            entity_data = self.canvas.entity_renderer.entity_cache.get(entity_id)
            if (entity_data and 
                current_time - entity_data.get('rotation_cache_time', 0) < 5.0):
                return entity_data['rotation']
        
        # PRIORITY 2: Check local gizmo cache
        if hasattr(entity, '_gizmo_cached_rotation') and hasattr(entity, '_gizmo_rotation_cache_time'):
            if current_time - entity._gizmo_rotation_cache_time < 5.0:
                return entity._gizmo_cached_rotation
        
        # CALCULATION NEEDED: No valid cache found
        if not hasattr(entity, 'xml_element') or entity.xml_element is None:
            # Cache the "no rotation" result in both places
            self._cache_rotation_result(entity, 0.0, current_time)
            return 0.0
        
        rotation_z = 0.0
        entity_name = getattr(entity, 'name', 'entity')
        
        # Reduce logging frequency to every 5 seconds
        should_log = current_time - getattr(self, '_last_rotation_log_time', 0) > 5.0
        
        try:
            # Method 1: FCBConverter format (field elements)
            angles_field = entity.xml_element.find("./field[@name='hidAngles']")
            if angles_field is not None:
                angles_value = angles_field.get('value-Vector3')
                if angles_value:
                    try:
                        parts = angles_value.split(',')
                        if len(parts) >= 3:
                            game_rotation = float(parts[2].strip())
                            # Convert from game coordinates to editor coordinates
                            rotation_z = (360 - game_rotation) % 360
                            
                            if should_log and rotation_z != 0:
                                print(f"🔄 FCB rotation for {entity_name}: game={game_rotation:.1f}° -> editor={rotation_z:.1f}°")
                                self._last_rotation_log_time = current_time
                            
                            # Cache result in both places
                            self._cache_rotation_result(entity, rotation_z, current_time)
                            return rotation_z
                    except (ValueError, IndexError):
                        pass
            
            # Method 2: Dunia Tools format (value elements)
            angles_elem = entity.xml_element.find("./value[@name='hidAngles']")
            if angles_elem is not None:
                z_elem = angles_elem.find("./z")
                if z_elem is not None and z_elem.text:
                    try:
                        game_rotation = float(z_elem.text.strip())
                        # Convert from game coordinates to editor coordinates
                        rotation_z = (360 - game_rotation) % 360
                        
                        if should_log and rotation_z != 0:
                            print(f"🔄 Dunia rotation for {entity_name}: game={game_rotation:.1f}° -> editor={rotation_z:.1f}°")
                            self._last_rotation_log_time = current_time
                        
                        # Cache result in both places
                        self._cache_rotation_result(entity, rotation_z, current_time)
                        return rotation_z
                    except ValueError:
                        pass
            
            # Method 3: Check for rotation field directly
            rotation_field = entity.xml_element.find("./field[@name='rotation']")
            if rotation_field is not None:
                rotation_value = rotation_field.get('value') or rotation_field.text
                if rotation_value:
                    try:
                        rotation_z = float(rotation_value)
                        
                        if should_log and rotation_z != 0:
                            print(f"🔄 Direct rotation for {entity_name}: {rotation_z:.1f}°")
                            self._last_rotation_log_time = current_time
                        
                        # Cache result in both places
                        self._cache_rotation_result(entity, rotation_z, current_time)
                        return rotation_z
                    except ValueError:
                        pass
                        
        except Exception:
            pass
        
        # No rotation found - cache the zero result
        if should_log:
            print(f"⚠️ No rotation found for {entity_name}, using 0°")
            self._last_rotation_log_time = current_time
        
        # Cache the "no rotation found" result in both places
        self._cache_rotation_result(entity, 0.0, current_time)
        return 0.0

    def _cache_rotation_result(self, entity, rotation_z, current_time):
        """Cache rotation result in both local and entity renderer caches"""
        entity_id = id(entity)
        
        # Cache in local gizmo cache
        entity._gizmo_cached_rotation = rotation_z
        entity._gizmo_rotation_cache_time = current_time
        
        # Cache in entity renderer cache if available
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'entity_renderer'):
            # Get or create entity data
            entity_data = self.canvas.entity_renderer.get_or_cache_entity_data(entity)
            entity_data['rotation'] = rotation_z
            entity_data['rotation_cache_time'] = current_time

    def get_cached_rotation(self, entity, canvas):
        """Get cached rotation with minimal recalculation - used by EntityRenderer"""
        entity_id = id(entity)
        current_time = time()
        
        # Get entity data from cache
        entity_data = self.get_or_cache_entity_data(entity)
        
        # Check if rotation cache is still valid (5 second cache)
        if (current_time - entity_data.get('rotation_cache_time', 0) < 5.0):
            return entity_data['rotation']
        
        # Only recalculate if cache expired - delegate to gizmo renderer
        if hasattr(canvas, 'gizmo_renderer') and canvas.gizmo_renderer.rotation_gizmo:
            rotation = canvas.gizmo_renderer.rotation_gizmo.extract_entity_rotation(entity)
            return rotation
        
        return 0.0
    
    def update_entity_rotation(self, entity, new_rotation):
        """Update entity rotation in XML and invalidate cache"""
        if not hasattr(entity, 'xml_element') or entity.xml_element is None:
            print(f"⚠️ Cannot update rotation for {getattr(entity, 'name', 'entity')}: No XML element")
            return False
        
        try:
            # Convert editor rotation to game rotation
            game_rotation = (360 - new_rotation) % 360
            entity_name = getattr(entity, 'name', 'entity')
            
            # Only log updates occasionally
            current_time = time.time()
            should_log = current_time - getattr(self, '_last_update_log_time', 0) > 1.0
            
            if should_log:
                print(f"🔄 Updating {entity_name}: editor={new_rotation:.1f}° -> game={game_rotation:.1f}°")
                self._last_update_log_time = current_time
            
            # Method 1: FCBConverter format
            angles_field = entity.xml_element.find("./field[@name='hidAngles']")
            if angles_field is not None:
                angles_value = angles_field.get('value-Vector3')
                if angles_value:
                    try:
                        parts = angles_value.split(',')
                        if len(parts) >= 3:
                            # Update Z rotation while preserving X and Y
                            parts[2] = f"{game_rotation:.1f}"
                            new_angles_value = ','.join(parts)
                            angles_field.set('value-Vector3', new_angles_value)
                            
                            # Update binary hex data if present
                            binary_hex = self._angles_to_binhex(float(parts[0]), float(parts[1]), game_rotation)
                            angles_field.text = binary_hex
                            
                            # Invalidate cache
                            self._invalidate_rotation_cache(entity)
                            
                            # Find canvas through direct object inspection
                            try:
                                canvas = None
                                if hasattr(self, 'canvas'):
                                    canvas = self.canvas
                                else:
                                    # Try to find the canvas from the current frame
                                    import inspect
                                    for frame_info in inspect.stack():
                                        frame_locals = frame_info.frame.f_locals
                                        if 'canvas' in frame_locals and hasattr(frame_locals['canvas'], 'mark_entity_modified'):
                                            canvas = frame_locals['canvas']
                                            break
                                        if 'self' in frame_locals and hasattr(frame_locals['self'], 'canvas'):
                                            canvas = frame_locals['self'].canvas
                                            break
                                
                                if canvas and hasattr(canvas, 'mark_entity_modified'):
                                    canvas.mark_entity_modified(entity)
                                
                            except Exception as canvas_error:
                                print(f"⚠️ Could not invalidate canvas cache: {canvas_error}")
                            
                            if should_log:
                                print(f"✅ Updated FCB rotation: {new_angles_value}")
                            return True
                    except (ValueError, IndexError):
                        pass
            
            # Method 2: Dunia Tools format
            angles_elem = entity.xml_element.find("./value[@name='hidAngles']")
            if angles_elem is not None:
                z_elem = angles_elem.find("./z")
                if z_elem is not None:
                    z_elem.text = f"{game_rotation:.1f}"
                    
                    # Invalidate cache
                    self._invalidate_rotation_cache(entity)
                    
                    if should_log:
                        print(f"✅ Updated Dunia rotation: {game_rotation:.1f}°")
                    return True
            
            # Method 3: Direct rotation field
            rotation_field = entity.xml_element.find("./field[@name='rotation']")
            if rotation_field is not None:
                rotation_field.set('value', f"{new_rotation:.1f}")
                if rotation_field.text is not None:
                    rotation_field.text = f"{new_rotation:.1f}"
                
                # Invalidate cache
                self._invalidate_rotation_cache(entity)
                
                if should_log:
                    print(f"✅ Updated direct rotation: {new_rotation:.1f}°")
                return True
            
            if should_log:
                print(f"⚠️ No rotation field found to update for {entity_name}")
            return False
            
        except Exception as e:
            print(f"⚠️ Exception updating rotation for {getattr(entity, 'name', 'entity')}: {e}")
            return False
    
    def _invalidate_rotation_cache(self, entity):
        """Invalidate cached rotation data for an entity"""
        cache_attrs = ['_gizmo_cached_rotation', '_gizmo_rotation_cache_time', 
                      '_cached_rotation', '_rotation_cache_time']
        for attr in cache_attrs:
            if hasattr(entity, attr):
                delattr(entity, attr)
    
    def _angles_to_binhex(self, x, y, z):
        """Convert angles to BinHex format for FCBConverter"""
        import struct
        
        # Pack as three 32-bit little-endian floats
        binary_data = struct.pack('<fff', float(x), float(y), float(z))
        
        # Convert to hex string (uppercase)
        hex_string = binary_data.hex().upper()
        
        return hex_string
    
    def render_2d(self, painter, canvas):
        """Render rotation gizmo in 2D mode"""
        if self.hidden:
            return
        
        # Use entity coordinates for 2D positioning
        screen_x, screen_y = OpenGLUtils.world_to_screen(self.position.x(), self.position.y(), canvas)
        
        # Check if gizmo is visible
        if (screen_x < -50 or screen_x > canvas.width() + 50 or
            screen_y < -50 or screen_y > canvas.height() + 50):
            return
        
        # Draw hollow blue circle
        if self.is_dragging:
            painter.setPen(QPen(QColor(255, 255, 0), self.thickness + 1))  # Yellow when dragging
        else:
            painter.setPen(QPen(QColor(0, 120, 255), self.thickness))  # Blue normally
        
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))  # Transparent fill
        
        painter.drawEllipse(
            int(screen_x - self.radius), 
            int(screen_y - self.radius),
            self.radius * 2, 
            self.radius * 2
        )
        
        # Draw rotation indicator line
        angle_rad = math.radians(self.current_rotation - 90)  # -90 to start from top
        indicator_x = screen_x + (self.radius - 5) * math.cos(angle_rad)
        indicator_y = screen_y + (self.radius - 5) * math.sin(angle_rad)
        
        painter.setPen(QPen(QColor(255, 255, 0), 3))
        painter.drawLine(
            int(screen_x), int(screen_y),
            int(indicator_x), int(indicator_y)
        )
        
        # Draw angle text with better positioning to avoid overlap
        game_rotation = (360 - self.current_rotation) % 360
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        
        # Position text below the gizmo to avoid entity label overlap
        text_x = int(screen_x - 30)
        text_y = int(screen_y + self.radius + 20)
        
        # Create compact single-line text
        rotation_text = f"Rot: {self.current_rotation:.1f}° (Game: {game_rotation:.1f}°)"
        
        # Measure text for background
        metrics = painter.fontMetrics()
        text_rect = metrics.boundingRect(rotation_text)
        text_width = text_rect.width()
        text_height = text_rect.height()
        
        # Keep text on screen
        canvas_width = canvas.width()
        canvas_height = canvas.height()
        
        if text_x + text_width > canvas_width - 10:
            text_x = canvas_width - text_width - 10
        if text_x < 10:
            text_x = 10
        if text_y + text_height > canvas_height - 10:
            text_y = int(screen_y - self.radius - 10)  # Above gizmo instead
        
        # Draw background for text
        bg_padding = 3
        bg_x = text_x - bg_padding
        bg_y = text_y - metrics.ascent() - bg_padding
        bg_width = text_width + bg_padding * 2
        bg_height = text_height + bg_padding * 2
        
        # Semi-transparent background
        painter.fillRect(bg_x, bg_y, bg_width, bg_height, QColor(0, 0, 0, 180))
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        painter.drawRect(bg_x, bg_y, bg_width, bg_height)
        
        # Draw text
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawText(text_x, text_y, rotation_text)

    def is_point_on_circle(self, screen_x, screen_y, canvas):
        """Check if a screen point is on the rotation circle"""
        if self.hidden:
            return False
        
        # Use entity coordinates for 2D mode
        gizmo_screen_x, gizmo_screen_y = OpenGLUtils.world_to_screen(self.position.x(), self.position.y(), canvas)
        
        dx = screen_x - gizmo_screen_x
        dy = screen_y - gizmo_screen_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        tolerance = self.thickness + 8  # More generous tolerance
        return abs(distance - self.radius) <= tolerance

    def start_rotation(self, screen_x, screen_y, canvas):
        """Start rotation interaction"""
        if not self.is_point_on_circle(screen_x, screen_y, canvas):
            return False
        
        self.is_dragging = True
        self.drag_start_pos = (screen_x, screen_y)
        
        # Calculate initial angle from gizmo center
        gizmo_screen_x, gizmo_screen_y = OpenGLUtils.world_to_screen(self.position.x(), self.position.y(), canvas)
        dx = screen_x - gizmo_screen_x
        dy = screen_y - gizmo_screen_y
        self.drag_start_angle = math.degrees(math.atan2(dy, dx))
        
        self.initial_rotation = self.current_rotation
        print(f"Started rotation: initial={self.initial_rotation:.1f}°, start_angle={self.drag_start_angle:.1f}°")
        return True

    def update_rotation(self, screen_x, screen_y, canvas, entity):
        """Update rotation during drag"""
        if not self.is_dragging:
            return
        
        # Track which entity we're rotating for cache invalidation
        self._last_rotated_entity = entity
        
        try:
            # Calculate current angle from gizmo center
            gizmo_screen_x, gizmo_screen_y = OpenGLUtils.world_to_screen(self.position.x(), self.position.y(), canvas)
            dx = screen_x - gizmo_screen_x
            dy = screen_y - gizmo_screen_y
            current_angle = math.degrees(math.atan2(dy, dx))
            
            # Calculate rotation delta
            angle_delta = current_angle - self.drag_start_angle
            
            # Update current rotation
            self.current_rotation = (self.initial_rotation + angle_delta) % 360
            
            # Update entity XML
            if self.update_entity_rotation(entity, self.current_rotation):
                # Only log occasionally during dragging
                current_time = time.time()
                if current_time - getattr(self, '_last_drag_log_time', 0) > 0.5:
                    print(f"Rotation updated: {self.current_rotation:.1f}° (delta: {angle_delta:.1f}°)")
                    self._last_drag_log_time = current_time
            
        except Exception as e:
            print(f"Error updating rotation: {e}")

    def end_rotation(self):
        """End rotation interaction"""
        if self.is_dragging:
            print(f"Rotation completed: {self.current_rotation:.1f}°")
            self.is_dragging = False
            
            # Force cache invalidation when rotation ends to ensure colors update properly
            if hasattr(self, '_last_rotated_entity'):
                entity = self._last_rotated_entity
                if hasattr(entity, '_cached_style_2d'):
                    delattr(entity, '_cached_style_2d')
                delattr(self, '_last_rotated_entity')
        else:
            self.is_dragging = False

class GizmoRenderer:
    """Handles rendering of gizmos and manipulation tools - 2D ONLY"""
    
    def __init__(self):
        self.rotation_gizmo = RotationGizmo()
        print("GizmoRenderer initialized (2D only)")
    
    def render_rotation_gizmo_2d(self, painter, canvas):
        """Render rotation gizmo in 2D mode"""
        if (hasattr(canvas, 'selected_entity') and canvas.selected_entity and 
            not self.rotation_gizmo.hidden):
            self.rotation_gizmo.render_2d(painter, canvas)
    
    def handle_gizmo_mouse_press(self, event, canvas):
        """Handle mouse press for gizmo interactions"""
        if (hasattr(canvas, 'selected_entity') and canvas.selected_entity and 
            self.rotation_gizmo.start_rotation(event.position().x(), event.position().y(), canvas)):
            print("Started gizmo rotation interaction")
            return True
        return False
    
    def handle_gizmo_mouse_move(self, event, canvas):
        """Handle mouse move for gizmo interactions"""
        if (self.rotation_gizmo.is_dragging and hasattr(canvas, 'selected_entity') and canvas.selected_entity):
            self.rotation_gizmo.update_rotation(
                event.position().x(), event.position().y(), canvas, canvas.selected_entity
            )
            return True
        return False
    
    def handle_gizmo_mouse_release(self, event, canvas):
        """Handle mouse release for gizmo interactions"""
        if self.rotation_gizmo.is_dragging:
            self.rotation_gizmo.end_rotation()
            print("Ended gizmo rotation interaction")
            return True
        return False
    
    def update_gizmo_for_entity(self, entity):
        """Update gizmo position when entity is selected"""
        self.rotation_gizmo.move_to_entity(entity)
    
    def hide_gizmo(self):
        """Hide all gizmos"""
        self.rotation_gizmo.hidden = True
    
    def is_gizmo_active(self):
        """Check if any gizmo is currently being interacted with"""
        return self.rotation_gizmo.is_dragging
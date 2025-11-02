"""2D camera controller for navigation and view management - 2D ONLY VERSION"""

import math
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QVector3D
from .opengl_utils import OpenGLUtils

class CameraController:
    """Handles 2D camera movement, zooming, and view management - 2D ONLY"""
    
    def __init__(self):
        # 2D position offsets - initialize with default centered view
        self.offset_x = 0
        self.offset_y = 0
        
        # Movement state flags for 2D
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        
        # SHIFT modifier state for speed boost
        self.shift_modifier = False
        
        # REMOVED: All 3D camera properties (camera_height, camera_pitch, camera_yaw, etc.)
        # REMOVED: 3D interaction state (rotating_camera, camera_panning, etc.)
        
        # SMOOTH MOVEMENT - 2D ONLY
        self.movement_speed = 8.0  # Base movement speed
        self.shift_speed_multiplier = 2.5  # Speed multiplier when SHIFT is held
        self.movement_acceleration = 1.3  # Acceleration
        self.max_movement_speed = 20.0  # Maximum movement speed (normal)
        self.max_movement_speed_shift = 50.0  # Maximum movement speed with SHIFT
        self.current_movement_speed = self.movement_speed
        
        # Frame rate independent movement
        self.last_update_time = 0
        self.target_fps = 60.0
        self.frame_time = 1.0 / self.target_fps
        
        print("CameraController initialized - 2D ONLY")
    
    def set_shift_modifier(self, shift_pressed):
        """Set the shift modifier state for speed boost"""
        old_shift = self.shift_modifier
        self.shift_modifier = shift_pressed
        
        # Reset movement speed when shift state changes
        if old_shift != shift_pressed:
            if shift_pressed:
                self.current_movement_speed = self.movement_speed * self.shift_speed_multiplier
                print(f"SHIFT speed boost: {self.movement_speed} -> {self.current_movement_speed}")
            else:
                self.current_movement_speed = self.movement_speed
                print(f"SHIFT speed normal: {self.current_movement_speed} -> {self.movement_speed}")
    
    def get_effective_movement_speed(self):
        """Get the effective movement speed based on shift modifier"""
        if self.shift_modifier:
            return self.movement_speed * self.shift_speed_multiplier
        return self.movement_speed
    
    def get_effective_max_speed(self):
        """Get the effective maximum speed based on shift modifier"""
        if self.shift_modifier:
            return self.max_movement_speed_shift
        return self.max_movement_speed
    
    def update_movement(self, canvas):
        """Update camera movement - 2D ONLY with SHIFT speed boost"""
        if not self.needs_update():
            self.current_movement_speed = self.get_effective_movement_speed()
            return
        
        import time
        current_time = time.time()
        if self.last_update_time == 0:
            self.last_update_time = current_time
            return
        
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time
        delta_time = min(delta_time, 0.1)  # Cap delta time
        
        # Gradually increase movement speed (with shift consideration)
        if self.needs_update():
            effective_max_speed = self.get_effective_max_speed()
            self.current_movement_speed = min(
                self.current_movement_speed * self.movement_acceleration,
                effective_max_speed
            )
        
        moved = False
        
        # 2D movement calculation with shift boost
        base_movement_per_frame = 10.0 / 60.0
        speed_multiplier = self.shift_speed_multiplier if self.shift_modifier else 1.0
        movement_distance = self.current_movement_speed * base_movement_per_frame * (delta_time * self.target_fps)
        
        if self.MOVE_UP:
            self.offset_y -= movement_distance
            canvas.offset_y = self.offset_y
            moved = True
        if self.MOVE_DOWN:
            self.offset_y += movement_distance
            canvas.offset_y = self.offset_y
            moved = True
        if self.MOVE_LEFT:
            self.offset_x += movement_distance
            canvas.offset_x = self.offset_x
            moved = True
        if self.MOVE_RIGHT:
            self.offset_x -= movement_distance
            canvas.offset_x = self.offset_x
            moved = True
        
        if moved:
            canvas.update()
            
            # Log occasionally to verify movement (include shift state)
            if not hasattr(self, '_last_movement_log'):
                self._last_movement_log = 0
            
            if current_time - self._last_movement_log > 2.0:
                shift_status = " (SHIFT)" if self.shift_modifier else ""
                print(f"2D Camera: ({self.offset_x:.1f}, {self.offset_y:.1f}) speed={self.current_movement_speed:.1f}{shift_status}")
                self._last_movement_log = current_time

    def zoom_in(self, canvas):
        """Zoom in - 2D ONLY"""
        old_scale = canvas.scale_factor
        canvas.scale_factor *= 1.2
        print(f"Zoom in: {old_scale:.2f} -> {canvas.scale_factor:.2f}")
        canvas.update()

    def zoom_out(self, canvas):
        """Zoom out - 2D ONLY"""
        old_scale = canvas.scale_factor
        canvas.scale_factor /= 1.2
        canvas.scale_factor = max(0.01, canvas.scale_factor)
        print(f"Zoom out: {old_scale:.2f} -> {canvas.scale_factor:.2f}")
        canvas.update()
    
    def zoom_to_entity_2d(self, entity, canvas):
        """Zoom to an entity in 2D mode"""
        if not entity:
            print("No entity provided for zoom")
            return
        
        print(f"Zooming to entity in 2D mode: {entity.name} at ({entity.x}, {entity.y})")
        
        # Calculate a good zoom level
        zoom_level = 3.0  # Default zoom factor
        
        # Center on entity with current scale
        self.offset_x = (canvas.width() / 2) - (entity.x * zoom_level)
        self.offset_y = (canvas.height() / 2) - (entity.y * zoom_level)
        canvas.scale_factor = zoom_level
        
        # Sync with canvas
        canvas.offset_x = self.offset_x
        canvas.offset_y = self.offset_y
        
        # Force update
        canvas.update()
        
        print(f"Zoom completed to: scale={canvas.scale_factor:.2f}, "
            f"offset=({self.offset_x:.1f}, {self.offset_y:.1f})")

    def handle_wheel_zoom_2d(self, event, canvas):
        """Handle wheel zoom in 2D mode with cursor-centered zooming"""
        from .opengl_utils import OpenGLUtils
        
        # Get the current cursor position
        cursor_x, cursor_y = event.position().x(), event.position().y()
        
        # Convert cursor position to world coordinates BEFORE zooming
        world_x, world_y = OpenGLUtils.screen_to_world(cursor_x, cursor_y, canvas)
        
        # Store old scale factor
        old_scale = canvas.scale_factor
        
        # Apply zoom
        if event.angleDelta().y() > 0:
            canvas.scale_factor *= 1.2
        else:
            canvas.scale_factor /= 1.2
        
        # Apply zoom limits
        canvas.scale_factor = max(0.01, min(100, canvas.scale_factor))
        
        # Adjust offsets to keep world point under cursor
        new_offset_x = cursor_x - (world_x * canvas.scale_factor)
        new_offset_y = cursor_y + (world_y * canvas.scale_factor) - canvas.height()
        
        # Update both camera controller and canvas offsets
        self.offset_x = new_offset_x
        self.offset_y = -new_offset_y
        canvas.offset_x = self.offset_x
        canvas.offset_y = self.offset_y
        
        canvas.update()
    
    def set_movement_flag(self, key, pressed):
        """Set movement flags based on key presses - 2D ONLY with shift consideration"""
        old_flags = (self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        
        if key == Qt.Key.Key_W:
            self.MOVE_UP = 1 if pressed else 0
        elif key == Qt.Key.Key_S:
            self.MOVE_DOWN = 1 if pressed else 0
        elif key == Qt.Key.Key_A:
            self.MOVE_LEFT = 1 if pressed else 0
        elif key == Qt.Key.Key_D:
            self.MOVE_RIGHT = 1 if pressed else 0
        
        # Reset movement speed when starting new movement (considering shift state)
        if pressed and not any(old_flags):
            self.current_movement_speed = self.get_effective_movement_speed()
        
        new_flags = (self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT)
        if old_flags != new_flags:
            key_name = {
                Qt.Key.Key_W: "W", Qt.Key.Key_S: "S", Qt.Key.Key_A: "A", 
                Qt.Key.Key_D: "D"
            }.get(key, str(key))
            action = "pressed" if pressed else "released"
            shift_status = " (SHIFT)" if self.shift_modifier else ""
            print(f"Movement key {key_name} {action}{shift_status}")
    
    def needs_update(self):
        """Check if camera movement requires view update - 2D ONLY"""
        return any([self.MOVE_UP, self.MOVE_DOWN, self.MOVE_LEFT, self.MOVE_RIGHT])
    
    def reset_view(self, canvas):
        """Reset view to default position"""
        self.offset_x = canvas.width() / 2
        self.offset_y = canvas.height() / 2
        canvas.offset_x = self.offset_x
        canvas.offset_y = self.offset_y
        canvas.scale_factor = 1.0
        canvas.update()
        print("Reset view to default position")
    
    def center_on_point(self, world_x, world_y, canvas):
        """Center the view on a specific world point"""
        self.offset_x = canvas.width() / 2 - world_x * canvas.scale_factor
        self.offset_y = canvas.height() / 2 - world_y * canvas.scale_factor
        canvas.offset_x = self.offset_x
        canvas.offset_y = self.offset_y
        canvas.update()
        print(f"Centered view on ({world_x:.1f}, {world_y:.1f})")
    
    def get_view_bounds(self, canvas):
        """Get the current view bounds in world coordinates"""
        try:
            world_left, world_bottom = OpenGLUtils.screen_to_world(0, canvas.height(), canvas)
            world_right, world_top = OpenGLUtils.screen_to_world(canvas.width(), 0, canvas)
            
            return {
                'left': world_left,
                'right': world_right,
                'top': world_top,
                'bottom': world_bottom,
                'width': world_right - world_left,
                'height': world_top - world_bottom,
                'center_x': (world_left + world_right) / 2,
                'center_y': (world_top + world_bottom) / 2
            }
        except Exception as e:
            print(f"Error calculating view bounds: {e}")
            return None
    
    def fit_entities_in_view(self, entities, canvas, padding=1.2):
        """Fit all given entities in the current view"""
        if not entities:
            return
        
        # Calculate bounding box
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        valid_entities = 0
        for entity in entities:
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
            scale_x = (canvas.width() * 0.8) / (width_span * padding) if width_span > 0 else 1.0
            scale_y = (canvas.height() * 0.8) / (height_span * padding) if height_span > 0 else 1.0
            canvas.scale_factor = min(scale_x, scale_y, 5.0)  # Cap at 5x zoom
        else:
            canvas.scale_factor = 1.0
        
        # Center the view
        self.offset_x = canvas.width() / 2 - center_x * canvas.scale_factor
        self.offset_y = canvas.height() / 2 - center_y * canvas.scale_factor
        
        # Update canvas offsets
        canvas.offset_x = self.offset_x
        canvas.offset_y = self.offset_y
        
        canvas.update()
        print(f"Fit {valid_entities} entities in view at scale {canvas.scale_factor:.2f}")
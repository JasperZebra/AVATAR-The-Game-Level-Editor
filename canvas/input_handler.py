"""Input handler for mouse and keyboard interactions - 2D ONLY VERSION"""

import math
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMenu
from .opengl_utils import OpenGLUtils
from PyQt6.QtGui import QVector3D

class InputHandler:
    """Handles mouse and keyboard input for the canvas - 2D ONLY"""
    
    def __init__(self, canvas):
        self.canvas = canvas
        
        # Mouse state
        self.dragging = False
        self.panning = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        
        # Modifier key states
        self.shift_is_pressed = False
        
        print("InputHandler initialized - 2D ONLY")

    def handle_mouse_press(self, event):
        """Handle mouse press events - 2D ONLY"""
        print(f"Mouse press: button={event.button()}, pos=({event.position().x():.1f}, {event.position().y():.1f})")
        
        try:            
            # CRITICAL: Check if we're clicking on a gizmo FIRST (highest priority)
            if hasattr(self.canvas, 'gizmo_renderer'):
                if self.canvas.gizmo_renderer.handle_gizmo_mouse_press(event, self.canvas):
                    print("Started gizmo interaction")
                    self.canvas.update()
                    return  # Gizmo interaction started, don't do other mouse handling
            
            # Handle 2D mouse press
            self.handle_mouse_press_2d(event)
            
        except Exception as e:
            print(f"Error in handle_mouse_press: {e}")
            import traceback
            traceback.print_exc()

    def handle_mouse_move(self, event):
        """Handle mouse move events - 2D ONLY"""
        try:
            # CRITICAL: Check if we're dragging a gizmo FIRST (highest priority)
            if hasattr(self.canvas, 'gizmo_renderer'):
                if self.canvas.gizmo_renderer.handle_gizmo_mouse_move(event, self.canvas):
                    # CRITICAL FIX: Invalidate caches when entity is rotated
                    if hasattr(self.canvas, 'selected_entity') and self.canvas.selected_entity:
                        self.canvas.mark_entity_modified(self.canvas.selected_entity)
                        self._auto_save_entity_changes(self.canvas.selected_entity)
                    self.canvas.update()  # Update immediately for smooth gizmo interaction
                    return  # Gizmo is being dragged, don't do other mouse handling
            
            # Handle 2D mouse move
            self.handle_mouse_move_2d(event)
            
        except Exception as e:
            print(f"Error in handle_mouse_move: {e}")

    def handle_mouse_release(self, event):
        """Handle mouse release events - 2D ONLY"""
        print(f"Mouse release: button={event.button()}")
        
        try:
            # CRITICAL: Check if we're releasing a gizmo FIRST (highest priority)
            if hasattr(self.canvas, 'gizmo_renderer'):
                if self.canvas.gizmo_renderer.handle_gizmo_mouse_release(event, self.canvas):
                    print("Ended gizmo interaction")
                    self.canvas.update()
                    return  # Gizmo interaction ended, don't do other mouse handling
            
            # Handle 2D mouse release
            self.handle_mouse_release_2d(event)
            
        except Exception as e:
            print(f"Error in handle_mouse_release: {e}")

    def handle_mouse_press_2d(self, event):
        """Handle mouse press in 2D mode with gizmo integration"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Get editor/canvas coordinates
            mouse_x = event.position().x()
            mouse_y = event.position().y()

            # Convert to level/world coordinates
            if hasattr(self.canvas, 'screen_to_world'):
                level_x, level_y = self.canvas.screen_to_world(mouse_x, mouse_y)
            else:
                # fallback to raw coordinates if screen_to_world not available
                level_x, level_y = mouse_x, mouse_y

            print(f"Mouse click at level coords: ({level_x:.1f}, {level_y:.1f})")

            # Check if an entity was clicked
            entity = self.get_entity_at_position(mouse_x, mouse_y)
            
            if entity:
                # Select entity
                self.canvas.selected_entity = entity
                self.canvas.selected = [entity]
                
                # Update gizmo position for selected entity
                if hasattr(self.canvas, 'gizmo_renderer'):
                    print(f"2D Click: Updating gizmo for {entity.name}")
                    self.canvas.gizmo_renderer.update_gizmo_for_entity(entity)
                
                # Emit selection signal to main window
                if hasattr(self.canvas, 'entitySelected'):
                    self.canvas.entitySelected.emit(entity)
                
                self.dragging = True
                print(f"Selected entity: {getattr(entity, 'name', 'unknown')}")
            else:
                # Clear selection when clicking empty space
                if not (QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier):
                    self.canvas.selected_entity = None
                    self.canvas.selected = []
                    
                    # Hide gizmo when clearing selection
                    if hasattr(self.canvas, 'gizmo_renderer'):
                        print("2D Empty click: Hiding gizmo")
                        self.canvas.gizmo_renderer.hide_gizmo()
                    
                    # Emit cleared selection signal
                    if hasattr(self.canvas, 'entitySelected'):
                        self.canvas.entitySelected.emit(None)
                    
                    print("Cleared selection - clicked empty space")
                            
            self.drag_start_x = mouse_x
            self.drag_start_y = mouse_y
            self.canvas.update()
            
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Start panning (middle mouse button only)
            self.panning = True
            self.drag_start_x = event.position().x()
            self.drag_start_y = event.position().y()
            print("Started middle-button panning")
            
        elif event.button() == Qt.MouseButton.RightButton:
            # Show context menu
            if hasattr(self.canvas, 'showContextMenu'):
                self.canvas.showContextMenu(event)
            elif hasattr(self.canvas.parent(), 'show_enhanced_context_menu'):
                self.canvas.parent().show_enhanced_context_menu(event)

    def handle_mouse_move_2d(self, event):
        """Handle mouse move in 2D mode with entity dragging and gizmo updates"""
        current_x = event.position().x()
        current_y = event.position().y()
        
        if self.dragging and hasattr(self.canvas, 'selected_entity') and self.canvas.selected_entity:
            # Move entity
            world_x, world_y = OpenGLUtils.screen_to_world(current_x, current_y, self.canvas)
            
            # Update entity position
            old_x, old_y = self.canvas.selected_entity.x, self.canvas.selected_entity.y
            self.canvas.selected_entity.x = world_x
            self.canvas.selected_entity.y = world_y
            
            print(f"Entity moved from ({old_x:.1f}, {old_y:.1f}) to ({world_x:.1f}, {world_y:.1f})")
            
            # CRITICAL: Invalidate caches when entity position changes
            self.canvas.mark_entity_modified(self.canvas.selected_entity)
            
            # CRITICAL: Update gizmo position when entity moves
            if hasattr(self.canvas, 'gizmo_renderer'):
                self.canvas.gizmo_renderer.update_gizmo_for_entity(self.canvas.selected_entity)
            
            # Update XML and auto-save
            self._update_entity_xml(self.canvas.selected_entity)
            self._auto_save_entity_changes(self.canvas.selected_entity)
            
            self.canvas.update()
            
        elif self.panning:
            # Handle panning
            dx = current_x - self.drag_start_x
            dy = current_y - self.drag_start_y
            
            self.canvas.camera_controller.offset_x += dx
            self.canvas.camera_controller.offset_y += dy
            self.canvas.offset_x = self.canvas.camera_controller.offset_x
            self.canvas.offset_y = self.canvas.camera_controller.offset_y
            
            self.drag_start_x = current_x
            self.drag_start_y = current_y
            self.canvas.update()
        else:
            # Update cursor and status for hover
            self._update_cursor_2d(current_x, current_y)
            self._update_status_bar_2d(current_x, current_y)

    def handle_mouse_release_2d(self, event):
        """Handle mouse release in 2D mode"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.dragging:
                print("Ended entity dragging")
            if self.panning:
                print("Ended left-button panning")
                
            self.dragging = False
            self.panning = False
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)
            
        elif event.button() == Qt.MouseButton.MiddleButton:
            if self.panning:
                print("Ended middle-button panning")
            self.panning = False

    def _update_cursor_2d(self, screen_x, screen_y):
        """Update cursor based on 2D hover state - includes gizmo detection"""
        # Check for gizmo hover first (highest priority)
        if (hasattr(self.canvas, 'selected_entity') and self.canvas.selected_entity and 
            hasattr(self.canvas, 'gizmo_renderer') and 
            self.canvas.gizmo_renderer.rotation_gizmo.is_point_on_circle(screen_x, screen_y, self.canvas)):
            self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
            return
        
        # Check for entity hover
        hovered_entity = self.get_entity_at_position(screen_x, screen_y)
        if hovered_entity:
            self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def handle_wheel(self, event):
        """Handle wheel events - 2D ONLY"""
        print(f"Wheel event: delta={event.angleDelta().y()}")
        
        # Always use 2D zoom
        self.canvas.camera_controller.handle_wheel_zoom_2d(event, self.canvas)
    
    def handle_key_press(self, event):
        """Handle key press events - 2D ONLY with SHIFT speed boost"""
        key_name = {
            Qt.Key.Key_W: "W", Qt.Key.Key_A: "A", Qt.Key.Key_S: "S", Qt.Key.Key_D: "D",
            Qt.Key.Key_Q: "Q", Qt.Key.Key_E: "E", Qt.Key.Key_Shift: "Shift"
        }.get(event.key(), f"Key_{event.key()}")
        
        print(f"Key pressed: {key_name}")
        
        # Set modifier flags
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_pressed = True
            # Update camera controller with shift state
            if hasattr(self.canvas, 'camera_controller'):
                self.canvas.camera_controller.set_shift_modifier(True)
                print("SHIFT speed boost activated")

        # Movement keys for camera (2D movement)
        self.canvas.camera_controller.set_movement_flag(event.key(), True)
    
    def handle_key_release(self, event):
        """Handle key release events - 2D ONLY with SHIFT speed boost"""
        key_name = {
            Qt.Key.Key_W: "W", Qt.Key.Key_A: "A", Qt.Key.Key_S: "S", Qt.Key.Key_D: "D",
            Qt.Key.Key_Q: "Q", Qt.Key.Key_E: "E", Qt.Key.Key_Shift: "Shift"
        }.get(event.key(), f"Key_{event.key()}")
        
        print(f"Key released: {key_name}")
        
        # Reset modifier flags
        if event.key() == Qt.Key.Key_Shift:
            self.shift_is_pressed = False
            # Update camera controller with shift state
            if hasattr(self.canvas, 'camera_controller'):
                self.canvas.camera_controller.set_shift_modifier(False)
                print("SHIFT speed boost deactivated")

        # Movement keys for camera
        self.canvas.camera_controller.set_movement_flag(event.key(), False)
    
    def get_entity_at_position(self, screen_x, screen_y, radius=8):
        """Get entity at the given screen position in 2D mode"""
        entities = getattr(self.canvas, 'entities', [])
        if not entities:
            return None
            
        for entity in entities:
            if (hasattr(self.canvas, 'current_map') and self.canvas.current_map is not None and 
                getattr(entity, 'map_name', None) != self.canvas.current_map.name):
                continue
                
            if not hasattr(entity, 'x') or not hasattr(entity, 'y'):
                continue
                
            x, y = OpenGLUtils.world_to_screen(entity.x, entity.y, self.canvas)
            
            entity_size = 6 if entity in getattr(self.canvas, 'selected', []) else 4
            square_size = entity_size * 2
            half_size = square_size // 2
            
            if (x - half_size <= screen_x <= x + half_size and 
                y - half_size <= screen_y <= y + half_size):
                return entity
        return None

    def center_view_here(self, event):
        """Center view at click location"""
        width = self.canvas.width()
        height = self.canvas.height()
        
        # 2D centering
        self.canvas.camera_controller.offset_x += width / 2 - event.position().x()
        self.canvas.camera_controller.offset_y += height / 2 - event.position().y()
        
        self.canvas.update()
        print(f"Centered view at click position")
    
    def zoom_to_selected_entities(self):
        """Zoom view to show all selected entities"""
        selected = getattr(self.canvas, 'selected', [])
        if not selected:
            return
        
        if len(selected) == 1:
            entity = selected[0]
            self.canvas.camera_controller.zoom_to_entity_2d(entity, self.canvas)
        else:
            # Multiple entities - zoom to fit all
            self._zoom_to_multiple_entities(selected)
    
    def toggle_grid(self):
        """Toggle grid display"""
        self.canvas.show_grid = not getattr(self.canvas, 'show_grid', True)
        print(f"Grid toggled: {self.canvas.show_grid}")
        self.canvas.update()
    
    def toggle_entities(self):
        """Toggle entity display"""
        self.canvas.show_entities = not getattr(self.canvas, 'show_entities', True)
        print(f"Entities toggled: {self.canvas.show_entities}")
        self.canvas.update()
            
    def _update_status_bar_2d(self, screen_x, screen_y):
        """Update status bar with 2D cursor info"""
        try:
            if hasattr(self.canvas.parent(), 'statusBar') and self.canvas.parent().statusBar():
                world_x, world_y = OpenGLUtils.screen_to_world(screen_x, screen_y, self.canvas)
                
                cursor_info = f"Cursor: X: {world_x:.2f}, Y: {world_y:.2f}"
                
                # Add sector information if available
                if hasattr(self.canvas, 'grid_config') and self.canvas.grid_config:
                    sector_x = int(world_x / 64)  # Assuming 64-unit sectors
                    sector_y = int(world_y / 64)
                    cursor_info += f" | Sector: ({sector_x}, {sector_y})"
                
                self.canvas.parent().statusBar().showMessage(cursor_info)
        except Exception as e:
            pass  # Ignore status bar errors

    def _zoom_to_multiple_entities(self, entities):
        """Zoom to fit multiple entities"""
        if not entities:
            return
        
        # Calculate bounding box
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for entity in entities:
            if hasattr(entity, 'x') and hasattr(entity, 'y'):
                min_x = min(min_x, entity.x)
                min_y = min(min_y, entity.y)
                max_x = max(max_x, entity.x)
                max_y = max(max_y, entity.y)
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # 2D zoom calculation
        width = max_x - min_x
        height = max_y - min_y
        padding = 1.5
        
        scale_x = self.canvas.width() / (width * padding) if width > 0 else 1.0
        scale_y = self.canvas.height() / (height * padding) if height > 0 else 1.0
        
        target_scale = min(scale_x, scale_y)
        target_scale = max(0.1, min(10.0, target_scale))
        
        self.canvas.scale_factor = target_scale
        self.canvas.camera_controller.offset_x = (self.canvas.width() / 2) - (center_x * self.canvas.scale_factor)
        self.canvas.camera_controller.offset_y = (self.canvas.height() / 2) - (center_y * self.canvas.scale_factor)
        
        self.canvas.update()
        print(f"Zoomed to {len(entities)} entities")
    
    def _auto_save_entity_changes(self, entity):
        """Auto-save entity changes"""
        if hasattr(self.canvas, '_auto_save_entity_changes'):
            self.canvas._auto_save_entity_changes(entity)
    
    def _update_entity_xml(self, entity):
        """Update entity XML"""
        if hasattr(self.canvas, 'update_entity_xml'):
            self.canvas.update_entity_xml(entity)
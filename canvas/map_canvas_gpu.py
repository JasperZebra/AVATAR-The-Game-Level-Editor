"""Main GPU-accelerated map canvas - 2D AND 3D VERSION
Integrates 3D camera view with existing 2D level editor
"""
import os
from time import time
import math
import numpy as np
import OpenGL.GL as gl
from PyQt6.QtGui import QMatrix4x4, QVector3D
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPainter, QColor, QPixmap, QTransform, QFont, QPen, QVector4D
from PyQt6.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QPushButton, QApplication

# View mode constants
MODE_TOPDOWN = 0
MODE_3D = 1

# Import GPU components
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from OpenGL.GL import *
    from OpenGL.GLU import *
    import OpenGL.GL as gl
    OPENGL_AVAILABLE = True
    print("OpenGL libraries loaded successfully")
except ImportError as e:
    from PyQt6.QtWidgets import QWidget as QOpenGLWidget
    OPENGL_AVAILABLE = False
    print(f"OpenGL not available ({e}) - falling back to CPU rendering")

# Import modular components (your existing ones)
from .terrain_renderer import TerrainRenderer
from .grid_renderer import GridRenderer
from .entity_renderer import EntityRenderer
from .icon_renderer import IconRenderer
from .gizmo_renderer import GizmoRenderer
from .input_handler import InputHandler
from .camera_controller import CameraController
from .opengl_utils import OpenGLUtils
from .model_loader import ModelLoader


"""Enhanced 3D Camera with 2D-style smooth movement"""
import numpy as np

class Camera3D:
    """3D Camera for FPS-style navigation with smooth acceleration like 2D camera"""
    
    def __init__(self):
        self.position = np.array([0.0, 200.0, 600.0], dtype=float)
        self.yaw = -90.0  # Looking along -Z
        self.pitch = -30.0  # Looking down slightly
        
        # Movement state flags (like 2D camera)
        self.MOVE_FORWARD = 0
        self.MOVE_BACKWARD = 0
        self.MOVE_LEFT = 0
        self.MOVE_RIGHT = 0
        self.MOVE_UP = 0
        self.MOVE_DOWN = 0
        
        # SHIFT modifier state for speed boost (like 2D camera)
        self.shift_modifier = False
        
        # SMOOTH MOVEMENT - matching 2D camera settings
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
        
        # Mouse sensitivity
        self.sensitivity = 0.3
        
        self.update_vectors()
        print("Camera3D initialized with 2D-style smooth movement")
    
    def update_vectors(self):
        """Update camera direction vectors"""
        rad_yaw = np.radians(self.yaw)
        rad_pitch = np.radians(self.pitch)
        
        self.forward = np.array([
            np.cos(rad_pitch) * np.cos(rad_yaw),
            np.sin(rad_pitch),
            np.cos(rad_pitch) * np.sin(rad_yaw)
        ])
        self.forward /= np.linalg.norm(self.forward)
        
        self.right = np.cross(self.forward, [0, 1, 0])
        self.right /= np.linalg.norm(self.right)
        
        self.up = np.cross(self.right, self.forward)
    
    def set_shift_modifier(self, shift_pressed):
        """Set the shift modifier state for speed boost (like 2D camera)"""
        old_shift = self.shift_modifier
        self.shift_modifier = shift_pressed
        
        # Reset movement speed when shift state changes
        if old_shift != shift_pressed:
            if shift_pressed:
                self.current_movement_speed = self.movement_speed * self.shift_speed_multiplier
                print(f"3D Camera SHIFT speed boost: {self.movement_speed} -> {self.current_movement_speed}")
            else:
                self.current_movement_speed = self.movement_speed
                print(f"3D Camera SHIFT speed normal: {self.current_movement_speed} -> {self.movement_speed}")
    
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
    
    def set_movement_flag(self, key_direction, pressed):
        """Set movement flags based on key presses (like 2D camera)"""
        old_flags = (self.MOVE_FORWARD, self.MOVE_BACKWARD, self.MOVE_LEFT, 
                     self.MOVE_RIGHT, self.MOVE_UP, self.MOVE_DOWN)
        
        if key_direction == "FORWARD":
            self.MOVE_FORWARD = 1 if pressed else 0
        elif key_direction == "BACKWARD":
            self.MOVE_BACKWARD = 1 if pressed else 0
        elif key_direction == "LEFT":
            self.MOVE_LEFT = 1 if pressed else 0
        elif key_direction == "RIGHT":
            self.MOVE_RIGHT = 1 if pressed else 0
        elif key_direction == "UP":
            self.MOVE_UP = 1 if pressed else 0
        elif key_direction == "DOWN":
            self.MOVE_DOWN = 1 if pressed else 0
        
        # Reset movement speed when starting new movement (considering shift state)
        if pressed and not any(old_flags):
            self.current_movement_speed = self.get_effective_movement_speed()
        
        new_flags = (self.MOVE_FORWARD, self.MOVE_BACKWARD, self.MOVE_LEFT, 
                     self.MOVE_RIGHT, self.MOVE_UP, self.MOVE_DOWN)
        if old_flags != new_flags:
            action = "pressed" if pressed else "released"
            shift_status = " (SHIFT)" if self.shift_modifier else ""
            print(f"3D Movement {key_direction} {action}{shift_status}")
    
    def needs_update(self):
        """Check if camera movement requires view update"""
        return any([self.MOVE_FORWARD, self.MOVE_BACKWARD, self.MOVE_LEFT, 
                   self.MOVE_RIGHT, self.MOVE_UP, self.MOVE_DOWN])
    
    def update_movement(self):
        """Update camera movement with smooth acceleration (like 2D camera)"""
        if not self.needs_update():
            self.current_movement_speed = self.get_effective_movement_speed()
            return False
        
        import time
        current_time = time.time()
        if self.last_update_time == 0:
            self.last_update_time = current_time
            return False
        
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
        
        # Calculate movement distance (matching 2D formula)
        base_movement_per_frame = 10.0 / 60.0
        movement_distance = self.current_movement_speed * base_movement_per_frame * (delta_time * self.target_fps)
        
        moved = False
        
        # Apply movement in all 6 directions
        if self.MOVE_FORWARD:
            self.position += self.forward * movement_distance
            moved = True
        if self.MOVE_BACKWARD:
            self.position -= self.forward * movement_distance
            moved = True
        if self.MOVE_LEFT:
            self.position -= self.right * movement_distance
            moved = True
        if self.MOVE_RIGHT:
            self.position += self.right * movement_distance
            moved = True
        if self.MOVE_UP:
            self.position += self.up * movement_distance
            moved = True
        if self.MOVE_DOWN:
            self.position -= self.up * movement_distance
            moved = True
        
        # Log occasionally to verify movement (like 2D camera)
        if moved:
            if not hasattr(self, '_last_movement_log'):
                self._last_movement_log = 0
            
            if current_time - self._last_movement_log > 2.0:
                shift_status = " (SHIFT)" if self.shift_modifier else ""
                print(f"3D Camera: ({self.position[0]:.1f}, {self.position[1]:.1f}, {self.position[2]:.1f}) "
                      f"speed={self.current_movement_speed:.1f}{shift_status}")
                self._last_movement_log = current_time
        
        return moved
    
    def rotate(self, dx, dy):
        """Rotate camera view"""
        self.yaw += dx * self.sensitivity
        self.pitch -= dy * self.sensitivity
        self.pitch = np.clip(self.pitch, -89, 89)
        self.update_vectors()
    
    def get_look_at(self):
        """Get the point the camera is looking at"""
        return self.position + self.forward

def draw_3d_grid(canvas, size=5120, sector_size=64):
    """Draw 3D grid for Avatar or FC2 worlds, matching the 2D grid exactly."""
    
    # --------------------
    # Detect FC2 mode
    is_fc2 = getattr(canvas, 'is_fc2_world', False) or getattr(canvas, 'game_mode', '') == 'farcry2'
    if not is_fc2 and hasattr(canvas, 'editor'):
        is_fc2 = getattr(canvas.editor, 'is_fc2_world', False) or getattr(canvas.editor, 'game_mode', '') == 'farcry2'

    # --------------------
    if is_fc2:
        # FC2 grid: 10x10 world cells, each 16x16 sectors
        sector_size = 64
        sectors_per_world = 16
        world_cell_size = sector_size * sectors_per_world  # 1024 units
        world_grid_size = 10

        # Grid limit (add extra padding)
        grid_limit = world_cell_size * (world_grid_size + 2) // 2  # Â±6144

        # Minor sector lines (gray)
        glLineWidth(1.0)
        glColor3f(0.2, 0.2, 0.2)
        glBegin(GL_LINES)
        for wx in range(-world_grid_size // 2, world_grid_size // 2):
            for wz in range(-world_grid_size // 2, world_grid_size // 2):
                cell_origin_x = wx * world_cell_size
                cell_origin_z = wz * world_cell_size
                for i in range(1, sectors_per_world):
                    x = cell_origin_x + i * sector_size
                    glVertex3f(x, 0, cell_origin_z)
                    glVertex3f(x, 0, cell_origin_z + world_cell_size)
                    z = cell_origin_z + i * sector_size
                    glVertex3f(cell_origin_x, 0, z)
                    glVertex3f(cell_origin_x + world_cell_size, 0, z)
        glEnd()

        # World cell boundaries (blue, thick)
        glLineWidth(3.0)
        glColor3f(0.0, 0.3, 0.8)
        glBegin(GL_LINES)
        for wx in range(-world_grid_size // 2, world_grid_size // 2 + 1):
            for wz in range(-world_grid_size // 2, world_grid_size // 2 + 1):
                x0 = wx * world_cell_size
                z0 = wz * world_cell_size
                x1 = x0 + world_cell_size
                z1 = z0 + world_cell_size
                # Vertical line
                glVertex3f(x0, 0, z0)
                glVertex3f(x0, 0, z1)
                # Horizontal line
                glVertex3f(x0, 0, z0)
                glVertex3f(x1, 0, z0)
        # Draw the outermost right and bottom edges explicitly
        outer = world_grid_size // 2 * world_cell_size
        glVertex3f(outer, 0, -outer)
        glVertex3f(outer, 0, outer)
        glVertex3f(-outer, 0, outer)
        glVertex3f(outer, 0, outer)
        glEnd()
    
    else:
        # Avatar grid
        major_interval = 5
        major_size = sector_size * major_interval
        grid_limit = size

        # Minor lines
        glLineWidth(1.0)
        glColor3f(0.2, 0.2, 0.2)
        glBegin(GL_LINES)
        for x in range(-grid_limit, grid_limit + 1, sector_size):
            if x % major_size != 0 and x != 0:
                glVertex3f(x, 0, -grid_limit)
                glVertex3f(x, 0, grid_limit)
                glVertex3f(-grid_limit, 0, x)
                glVertex3f(grid_limit, 0, x)
        glEnd()

        # Major lines
        glLineWidth(3.0)
        glColor3f(0.0, 0.0, 0.0)
        glBegin(GL_LINES)
        for x in range(-grid_limit, grid_limit + 1, major_size):
            if x != 0:
                glVertex3f(x, 0, -grid_limit)
                glVertex3f(x, 0, grid_limit)
                glVertex3f(-grid_limit, 0, x)
                glVertex3f(grid_limit, 0, x)
        glEnd()

    # Axes
    glLineWidth(5.0)
    glBegin(GL_LINES)
    glColor3f(1.0, 0.0, 0.0)
    glVertex3f(-grid_limit, 0, 0)
    glVertex3f(grid_limit, 0, 0)
    glColor3f(0.0, 1.0, 0.0)
    glVertex3f(0, 0, -grid_limit)
    glVertex3f(0, 0, grid_limit)
    glEnd()
    glLineWidth(1.0)

    
class MapCanvas(QOpenGLWidget):
    """Main GPU-accelerated canvas widget - 2D AND 3D VERSION"""
    
    # Signals
    entitySelected = pyqtSignal(object)
    position_update = pyqtSignal(object, tuple)
    move_points = pyqtSignal(float, float, float)
    height_update = pyqtSignal(float)
    create_waypoint = pyqtSignal(float, float)
    rotate_current = pyqtSignal(object)

    def __init__(self, parent=None):
        """Initialize MapCanvas - 2D AND 3D"""
        super().__init__(parent)
        self.main_window = parent
        
        self.setMinimumSize(600, 400)

        # View mode (0 = 2D, 1 = 3D)
        self.mode = MODE_TOPDOWN
        
        # Game mode tracking
        self.game_mode = "avatar"
        self.is_fc2_world = False
        
        # OpenGL setup
        self.opengl_initialized = False
        self.use_gpu_rendering = OPENGL_AVAILABLE
        
        # Display list for cube geometry
        self.cube_display_list = None  # ADD THIS LINE
        
        # Core canvas state
        self.entities = []
        self.selected_entity = None
        self.selected = []
        self.selected_positions = []
        self.selected_rotations = []
        self.scale_factor = 1.0
        
        # Canvas offset attributes (2D mode)
        self.offset_x = 0
        self.offset_y = 0
        
        self.grid_config = None
        self.current_map = None
        
        # View options
        self.show_grid = True
        self.show_entities = True
        
        # Rendering state
        self.entities_modified = False
        self.selection_modified = False
        self.last_mouse_world_pos = (0, 0)
        
        # Sector display
        self.show_sector_boundaries = False
        self.sector_data = []

        self.is_3d_mode = False

        # 3D Camera
        self.camera_3d = Camera3D()
        self.last_mouse_3d = None
        self.mouse_captured_3d = False
        
        # Setup all rendering modules
        self.setup_renderers()

        self.model_loader = ModelLoader()
        self.setup_3d_models()

        self.setup_canvas()
        self.setup_vehicle_icons()
        
        print(f"MapCanvas initialized - 2D AND 3D VERSION (OpenGL: {self.use_gpu_rendering})")

    def initializeGL(self):
        """Initialize OpenGL context"""
        if not self.use_gpu_rendering:
            return
            
        try:
            print("Initializing OpenGL...")
            
            version = gl.glGetString(gl.GL_VERSION).decode()
            vendor = gl.glGetString(gl.GL_VENDOR).decode()
            renderer = gl.glGetString(gl.GL_RENDERER).decode()
            
            print(f"OpenGL Version: {version}")
            print(f"GPU Vendor: {vendor}")
            print(f"GPU Renderer: {renderer}")
            
            # Enable depth testing for 3D
            gl.glEnable(gl.GL_DEPTH_TEST)
            
            # Enable blending for 2D
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            
            # Initialize grid renderer
            if hasattr(self, 'grid_renderer'):
                success = self.grid_renderer.initialize_gl()
                if success:
                    print("Grid renderer OpenGL initialized")
                else:
                    print("Grid renderer OpenGL initialization failed")
                    self.use_gpu_rendering = False
                    self.grid_renderer.use_opengl = False
            
            # CREATE CUBE DISPLAY LIST (only once!)
            self.cube_display_list = glGenLists(1)
            glNewList(self.cube_display_list, GL_COMPILE)
            self._draw_cube_geometry(1.0)
            glEndList()
            print("âœ“ Created cube display list for efficient 3D rendering")
            
            self.opengl_initialized = True
            print("OpenGL initialization complete - 2D AND 3D")
            
        except Exception as e:
            print(f"OpenGL initialization failed: {e}")
            import traceback
            traceback.print_exc()
            self.use_gpu_rendering = False
            self.opengl_initialized = False

    def _draw_cube_geometry(self, size):
        """Draw a solid cube with no outline."""
        s = size / 2

        glBegin(GL_QUADS)

        # Front face
        glNormal3f(0, 0, 1)
        glVertex3f(-s, -s, s)
        glVertex3f(s, -s, s)
        glVertex3f(s, s, s)
        glVertex3f(-s, s, s)

        # Back face
        glNormal3f(0, 0, -1)
        glVertex3f(-s, -s, -s)
        glVertex3f(-s, s, -s)
        glVertex3f(s, s, -s)
        glVertex3f(s, -s, -s)

        # Top face
        glNormal3f(0, 1, 0)
        glVertex3f(-s, s, -s)
        glVertex3f(-s, s, s)
        glVertex3f(s, s, s)
        glVertex3f(s, s, -s)

        # Bottom face
        glNormal3f(0, -1, 0)
        glVertex3f(-s, -s, -s)
        glVertex3f(s, -s, -s)
        glVertex3f(s, -s, s)
        glVertex3f(-s, -s, s)

        # Right face
        glNormal3f(1, 0, 0)
        glVertex3f(s, -s, -s)
        glVertex3f(s, s, -s)
        glVertex3f(s, s, s)
        glVertex3f(s, -s, s)

        # Left face
        glNormal3f(-1, 0, 0)
        glVertex3f(-s, -s, -s)
        glVertex3f(-s, -s, s)
        glVertex3f(-s, s, s)
        glVertex3f(-s, s, -s)

        glEnd()

    def _render_entities_3d(self):
        """Render entities in 3D mode using BATCHED instanced rendering"""
        if not self.entities or not self.cube_display_list:
            return
        
        entities_to_draw = self._get_visible_entities()
        models_rendered = 0
        cubes_rendered = 0
        textured_models = 0
        unmatched_entities = []

        if not hasattr(self, '_3d_debug_shown'):
            self._3d_debug_shown = True
            print(f"\n{'='*70}")
            print(f"{'3D BATCH RENDERING DEBUG':^70}")
            print(f"{'='*70}")
            print(f"Total entities: {len(self.entities)}")
            print(f"Entities to render: {len(entities_to_draw)}")
            if hasattr(self, 'model_loader'):
                print(f"Models directory: {self.model_loader.models_directory}")
                print(f"EntityLibrary loaded: {getattr(self.model_loader, '_entity_library_loaded', False)}")
                print(f"Materials directory: {self.model_loader.materials_directory}")
                print(f"Models cached: {len(getattr(self.model_loader, 'models_cache', []))}")
                print(f"Entity patterns: {len(getattr(self.model_loader, 'entity_patterns', []))}")

        # Prepare batches for all visible entities
        if hasattr(self, 'model_loader') and getattr(self.model_loader, '_entity_library_loaded', False):
            try:
                self.model_loader.prepare_batches(entities_to_draw, self.selected)
                
                # Render all batched models in one pass
                instances_rendered = self.model_loader.render_batched_models()
                models_rendered = instances_rendered
                
                # Count textured models
                for model in self.model_loader.models_cache.values():
                    if getattr(model, 'textures', None):
                        textured_models += 1
                
                if not hasattr(self, '_first_batch_logged'):
                    self._first_batch_logged = True
                    print(f"\n✓ First Batch Render Complete:")
                    print(f"   Instances rendered: {instances_rendered}")
                    print(f"   Unique models: {len(self.model_loader.instance_batches)}")
                    print(f"   Textured models: {textured_models}")
            
            except Exception as e:
                if not hasattr(self, '_batch_error_logged'):
                    self._batch_error_logged = True
                    print(f"⚠ Error in batch rendering: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Fallback: render cubes for entities without models OR for selection highlighting
        for entity in entities_to_draw:
            if not all(hasattr(entity, attr) for attr in ('x', 'y', 'z')):
                continue
            
            is_selected = entity in self.selected
            has_model = hasattr(entity, 'model_file') and entity.model_file
            
            # Render cube if:
            # 1. No model file, OR
            # 2. Entity is selected (for highlighting)
            if not has_model or is_selected:
                cubes_rendered += 1
                glPushMatrix()
                glTranslatef(entity.x, entity.z, -entity.y)
                color = (0.2, 0.5, 1.0) if is_selected else (0.4, 0.7, 1.0)
                glColor3f(*color)
                glCallList(self.cube_display_list)
                glPopMatrix()
                
                if not has_model:
                    entity_name = getattr(entity, 'hid_name', getattr(entity, 'name', 'unknown'))
                    if entity_name not in unmatched_entities:
                        unmatched_entities.append(entity_name)

        if not hasattr(self, '_first_render_logged'):
            self._first_render_logged = True
            print(f"\n🎮 First 3D Render Complete:")
            print(f"   Models rendered: {models_rendered}")
            print(f"   - With textures: {textured_models}")
            print(f"   Cubes rendered: {cubes_rendered}")
            if models_rendered == 0:
                if unmatched_entities:
                    print(f"   ⚠ Unmatched entities ({len(unmatched_entities)}):")
                    print(f"     {', '.join(unmatched_entities[:10])}" + ("..." if len(unmatched_entities) > 10 else ""))
                else:
                    print(f"   ⚠ ⚠ No entity models matched - check hidNames in EntityLibrary XML")

    def set_3d_mode(self, enabled: bool):
        """Enable or disable 3D rendering."""
        self.is_3d_mode = enabled
        self.mode = MODE_3D if enabled else MODE_TOPDOWN  # ADD THIS LINE
        
        if enabled:
            print("Switching to 3D mode")
            # Position 3D camera to show the scene
            if self.entities:
                # Calculate center of entities
                min_x = min_y = float('inf')
                max_x = max_y = float('-inf')
                
                for entity in self.entities:
                    if hasattr(entity, 'x') and hasattr(entity, 'y'):
                        min_x = min(min_x, entity.x)
                        max_x = max(max_x, entity.x)
                        min_y = min(min_y, entity.y)
                        max_y = max(max_y, entity.y)
                
                if min_x != float('inf'):
                    center_x = (min_x + max_x) / 2
                    center_y = (min_y + max_y) / 2
                    
                    # Position camera above and behind center
                    self.camera_3d.position = np.array([center_x, 200.0, center_y + 600.0])
                    self.camera_3d.yaw = -90.0
                    self.camera_3d.pitch = -30.0
                    self.camera_3d.update_vectors()
        else:
            print("Switching to 2D mode")
            self.mouse_captured_3d = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        
        self.update()

    def switch_to_3d_mode(self):
        """Switch to 3D view mode"""
        self.set_3d_mode(True)

    def switch_to_2d_mode(self):
        """Switch to 2D view mode"""
        self.set_3d_mode(False)

    def toggle_view_mode(self):
        """Toggle between 2D and 3D modes"""
        self.set_3d_mode(not self.is_3d_mode)
        print(f"Toggled to: {'3D' if self.is_3d_mode else '2D'} mode")

    def load_terrain(self, sdat_path):
        """Load terrain heightmap data"""
        if not hasattr(self, 'terrain_renderer'):
            print("No terrain renderer available")
            return False
        
        try:
            success = self.terrain_renderer.load_sdat_folder(sdat_path)
            if success:
                print(f"âœ“ Terrain loaded from {sdat_path}")
                self.update()
            else:
                print(f"âœ— Failed to load terrain from {sdat_path}")
            return success
        except Exception as e:
            print(f"Error loading terrain: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_terrain_visibility(self, visible):
        """Toggle terrain visibility"""
        if hasattr(self, 'terrain_renderer'):
            self.terrain_renderer.show_terrain = visible
            self.update()

    def set_terrain_opacity(self, opacity):
        """Set terrain opacity (0.0 to 1.0)"""
        if hasattr(self, 'terrain_renderer'):
            self.terrain_renderer.set_opacity(opacity)
            self.update()

    def setup_vehicle_icons(self):
        """Setup vehicle icons directory"""
        import os
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icons_path = os.path.join(current_dir, "assets", "vehicle_icons")
        
        if not os.path.exists(icons_path):
            parent_dir = os.path.dirname(current_dir)
            icons_path = os.path.join(parent_dir, "assets", "vehicle_icons")
        
        if not os.path.exists(icons_path):
            search_dir = current_dir
            for _ in range(5):
                test_path = os.path.join(search_dir, "assets", "vehicle_icons")
                if os.path.exists(test_path):
                    icons_path = test_path
                    break
                search_dir = os.path.dirname(search_dir)
        
        if os.path.exists(icons_path):
            if hasattr(self, 'entity_renderer'):
                self.entity_renderer.set_icons_directory(icons_path)
                print(f"âœ… Vehicle icons loaded from: {icons_path}")
        else:
            print(f"âš ï¸ Vehicle icons directory not found.")

    def setup_3d_models(self):
        """Setup 3D model loader with models directory, EntityLibrary, AND materials for textures"""
        import os
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        models_path = os.path.join(current_dir, "assets", "models", "graphics")
        
        print(f"\n=== 3D Models & Textures Setup ===")
        
        # Setup models directory
        if os.path.exists(models_path):
            success = self.model_loader.set_models_directory(models_path)
            if success:
                print(f"âœ“ 3D models directory indexed")
        else:
            print(f"âš ï¸  Models directory not found: {models_path}")
        
        # Setup EntityLibrary folder - TRY MULTIPLE WAYS TO FIND IT
        worlds_path = None
        
        # Method 1: Direct attribute
        if hasattr(self, 'main_window'):
            worlds_path = getattr(self.main_window, 'worlds_folder', None)
            if worlds_path:
                print(f"Found worlds_folder from main_window.worlds_folder")
        
        # Method 2: Try parent
        if not worlds_path and hasattr(self, 'parent') and self.parent():
            worlds_path = getattr(self.parent(), 'worlds_folder', None)
            if worlds_path:
                print(f"Found worlds_folder from parent")
        
        # Method 3: Search for it from loaded XML path
        if not worlds_path and hasattr(self, 'main_window'):
            if hasattr(self.main_window, 'xml_file_path'):
                xml_path = self.main_window.xml_file_path
                if xml_path:
                    # Go up from XML to worlds folder
                    # e.g., worlds/generated/worlds/level.xml -> worlds/
                    worlds_path = os.path.dirname(os.path.dirname(os.path.dirname(xml_path)))
                    print(f"Derived worlds_folder from XML path: {worlds_path}")
        
        # Method 4: Ask user to set it manually (fallback)
        if not worlds_path:
            print("âš ï¸  Could not find worlds folder automatically")
            print("   Please add this to your main window initialization:")
            print("   self.worlds_folder = r'path/to/your/Avatar/worlds'")
            print("\n   Example paths:")
            print("   - Avatar: D:\\Games\\Avatar The Game\\Data_Win32\\worlds")
            print("   - FC2: D:\\Games\\Far Cry 2\\Data_Win32\\worlds")
        
        if worlds_path and os.path.exists(worlds_path):
            success = self.model_loader.set_entity_library_folder(worlds_path)
            if success:
                print(f"âœ“ EntityLibrary configured")
        
        # Setup materials directory for textures
        if worlds_path:
            # Derive game data path from worlds folder
            game_data_path = os.path.dirname(worlds_path)  # worlds/../Data
            materials_path = os.path.join(game_data_path, "graphics", "_materials")
            
            if os.path.exists(materials_path):
                self.model_loader.set_materials_directory(materials_path)
            else:
                print(f"âš ï¸  Materials folder not found at: {materials_path}")
                print("   Models will render without textures")
        
        print("=" * 50 + "\n")

    def setup_renderers(self):
        """Initialize all renderer modules"""
        try:
            self.grid_renderer = GridRenderer()
            self.entity_renderer = EntityRenderer()
            self.icon_renderer = IconRenderer()
            self.gizmo_renderer = GizmoRenderer()
            self.terrain_renderer = TerrainRenderer()
            self.camera_controller = CameraController()
            self.input_handler = InputHandler(self)
            
            if self.use_gpu_rendering:
                self.grid_renderer.use_opengl = True
            
            print("All renderer modules initialized (2D AND 3D)")
            
        except Exception as e:
            print(f"Error setting up renderers: {e}")
            import traceback
            traceback.print_exc()

    def setup_canvas(self):
        """Setup canvas properties and timers"""
        self.movement_timer = QTimer(self)
        self.movement_timer.setInterval(16)  # 60 FPS
        self.movement_timer.timeout.connect(self.update_movement)
        self.movement_timer.start()
        
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        
        print("Canvas event handling setup complete - 2D AND 3D")
    
    def resizeGL(self, width, height):
        """Handle OpenGL viewport resize"""
        if not self.use_gpu_rendering:
            return
            
        try:
            gl.glViewport(0, 0, width, height)
            print(f"OpenGL viewport resized: {width}x{height}")
        except Exception as e:
            print(f"Error resizing OpenGL viewport: {e}")
    
    def paintGL(self):
        """Main OpenGL rendering"""
        if not self.use_gpu_rendering or not self.opengl_initialized:
            return
            
        try:
            if self.mode == MODE_TOPDOWN:
                # 2D rendering
                gl.glClearColor(0.94, 0.94, 0.94, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                self._render_2d_opengl()
            else:
                # 3D rendering
                gl.glClearColor(0.94, 0.94, 0.94, 1.0)
                gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
                self._render_3d_opengl()
                
        except Exception as e:
            print(f"Error in paintGL: {e}")
            import traceback
            traceback.print_exc()

    def _render_2d_opengl(self):
        """Render 2D scene"""
        if self.show_grid:
            self.grid_renderer.render_2d_grid(self)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        try:
            if hasattr(self, 'terrain_renderer'):
                self.terrain_renderer.render_terrain_2d(painter, self)
            
            if self.show_entities:
                entities_to_draw = self._get_visible_entities()
                if entities_to_draw:
                    self.entity_renderer.render_entities_2d(painter, self, entities_to_draw)
            
            self.icon_renderer.render_all_overlays(painter, self)
            self.gizmo_renderer.render_rotation_gizmo_2d(painter, self)
            
            if getattr(self, 'show_sector_boundaries', False):
                self.draw_sector_boundaries(painter)
                
        finally:
            painter.end()

    def _render_3d_opengl(self):
        """Render 3D scene using OpenGL with matching grid style"""
        try:
            # Set up 3D projection
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(60, self.width() / self.height(), 0.1, 10000.0)
            
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            
            # Position camera
            cam = self.camera_3d
            gluLookAt(
                cam.position[0], cam.position[1], cam.position[2],
                *cam.get_look_at(),
                0, 1, 0
            )
            
            # Enable proper depth testing for solid rendering
            glEnable(GL_DEPTH_TEST)
            glDepthFunc(GL_LESS)
            glDepthMask(GL_TRUE)
            
            # Enable face culling to only render front faces
            glEnable(GL_CULL_FACE)
            glCullFace(GL_BACK)
            glFrontFace(GL_CCW)
            
            # Disable blending for opaque rendering
            glDisable(GL_BLEND)
            
            # Enable lighting for 3D
            glEnable(GL_LIGHTING)
            glEnable(GL_LIGHT0)
            glEnable(GL_COLOR_MATERIAL)
            glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
            
            # Set up lighting
            glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 1.0, 1.0, 0.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
            
            # Draw grid with matching 2D style
            if self.show_grid:
                glDisable(GL_LIGHTING)  # Disable lighting for grid lines
                draw_3d_grid(self, 5120, 64)
                glEnable(GL_LIGHTING)  # Re-enable for entities
            
            # Draw entities as simple colored cubes
            if self.show_entities:
                self._render_entities_3d()
            
            # RESTORE OpenGL STATE for 2D rendering
            glDisable(GL_LIGHTING)
            glDisable(GL_LIGHT0)
            glDisable(GL_CULL_FACE)
            glDisable(GL_DEPTH_TEST)
            
            # Re-enable blending for 2D mode
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            
            # Draw 2D UI overlays on top
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            try:
                self._draw_3d_ui_overlays(painter)
            finally:
                painter.end()
            
        except Exception as e:
            print(f"Error in 3D rendering: {e}")
            import traceback
            traceback.print_exc()

    def _draw_3d_ui_overlays(self, painter):
        """Draw UI overlays for 3D mode"""
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        
        # Mode indicator
        margin = 10
        mode_text = "3D View"
        metrics = painter.fontMetrics()
        text_y = self.height() - margin
        
        painter.fillRect(margin - 3, text_y - metrics.ascent() - 2, 
                        metrics.boundingRect(mode_text).width() + 6, 
                        metrics.height() + 4, 
                        QColor(200, 100, 0, 150))
        painter.drawText(margin, text_y, mode_text)
        
        # Camera info
        cam = self.camera_3d
        info_text = f"Cam: ({cam.position[0]:.0f}, {cam.position[1]:.0f}, {cam.position[2]:.0f})"
        painter.drawText(margin, margin + metrics.ascent(), info_text)
        
        # Controls hint
        controls_text = "WASD+QE: Move | Mouse: Look | T: Toggle 2D/3D"
        painter.drawText(margin, self.height() - margin - metrics.height(), controls_text)

    def _get_visible_entities(self):
        """Get entities visible on screen"""
        # Your existing implementation
        if not hasattr(self, 'entities') or not self.entities:
            return []
        
        if not self.show_entities:
            return []
        
        entities_to_check = self.entities
        if hasattr(self, 'current_map') and self.current_map is not None:
            entities_to_check = [e for e in entities_to_check if getattr(e, 'map_name', None) == self.current_map.name]
        
        if self.mode == MODE_3D:
            return entities_to_check  # For 3D, simple frustum culling could be added
        
        # 2D spatial culling (your existing code)
        margin_pixels = 50
        
        try:
            world_left, world_bottom = self.screen_to_world(-margin_pixels, self.height() + margin_pixels)
            world_right, world_top = self.screen_to_world(self.width() + margin_pixels, -margin_pixels)
            
            visible_entities = []
            for entity in entities_to_check:
                if hasattr(entity, 'x') and hasattr(entity, 'y'):
                    if (world_left <= entity.x <= world_right and 
                        world_bottom <= entity.y <= world_top):
                        visible_entities.append(entity)
            
            return visible_entities
            
        except Exception as e:
            print(f"Error in spatial culling: {e}")
            return entities_to_check

    def keyPressEvent(self, event):
        """Handle key press - mode aware with smooth 3D camera"""
        k = event.key()

        # Toggle view mode
        if k == Qt.Key.Key_T:
            self.toggle_view_mode()
            return

        # Update SHIFT modifier state for both 2D and 3D
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.mode == MODE_3D:
                self.camera_3d.set_shift_modifier(True)
            else:
                self.camera_controller.set_shift_modifier(True)

        # Height adjustment for selected entity
        if k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.selected_entity is not None:
            height_delta = 1.0 if k == Qt.Key.Key_Up else -1.0
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                height_delta *= 0.1
            old_z = self.selected_entity.z
            self.selected_entity.z += height_delta
            print(f"Height adjusted: {getattr(self.selected_entity, 'name', 'entity')} "
                f"Z: {old_z:.1f} -> {self.selected_entity.z:.1f} (Δ{height_delta:+.1f})")
            self.update_entity_xml(self.selected_entity)
            self.mark_entity_modified(self.selected_entity)
            if hasattr(self, '_auto_save_entity_changes'):
                self._auto_save_entity_changes(self.selected_entity)
            if self.mode == MODE_3D and hasattr(self, 'gizmo_renderer'):
                self.gizmo_renderer.update_gizmo_for_entity(self.selected_entity)
            if hasattr(self, 'height_update'):
                self.height_update.emit(self.selected_entity.z)
            self.update()
            return

        # 3D camera controls with FLAG-BASED system (like 2D)
        if self.mode == MODE_3D:
            if k == Qt.Key.Key_W:
                self.camera_3d.set_movement_flag("FORWARD", True)
            elif k == Qt.Key.Key_S:
                self.camera_3d.set_movement_flag("BACKWARD", True)
            elif k == Qt.Key.Key_A:
                self.camera_3d.set_movement_flag("LEFT", True)
            elif k == Qt.Key.Key_D:
                self.camera_3d.set_movement_flag("RIGHT", True)
            elif k == Qt.Key.Key_E:
                self.camera_3d.set_movement_flag("UP", True)
            elif k == Qt.Key.Key_Q:
                self.camera_3d.set_movement_flag("DOWN", True)
        else:
            # 2D controls
            self.input_handler.handle_key_press(event)

    def keyReleaseEvent(self, event):
        """Handle key release - mode aware"""
        k = event.key()
        
        # Update SHIFT modifier state for both 2D and 3D
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            if self.mode == MODE_3D:
                self.camera_3d.set_shift_modifier(False)
            else:
                self.camera_controller.set_shift_modifier(False)
        
        if self.mode == MODE_3D:
            # Release 3D movement flags
            if k == Qt.Key.Key_W:
                self.camera_3d.set_movement_flag("FORWARD", False)
            elif k == Qt.Key.Key_S:
                self.camera_3d.set_movement_flag("BACKWARD", False)
            elif k == Qt.Key.Key_A:
                self.camera_3d.set_movement_flag("LEFT", False)
            elif k == Qt.Key.Key_D:
                self.camera_3d.set_movement_flag("RIGHT", False)
            elif k == Qt.Key.Key_E:
                self.camera_3d.set_movement_flag("UP", False)
            elif k == Qt.Key.Key_Q:
                self.camera_3d.set_movement_flag("DOWN", False)
        else:
            self.input_handler.handle_key_release(event)

    def update_movement(self):
        """Update camera movement for both 2D and 3D"""
        try:
            if self.mode == MODE_TOPDOWN:
                # 2D movement
                if not self.camera_controller.needs_update():
                    return
                
                self.camera_controller.update_movement(self)
                self.update()
            
            elif self.mode == MODE_3D:
                # 3D movement with smooth acceleration
                if not self.camera_3d.needs_update():
                    return
                
                moved = self.camera_3d.update_movement()
                if moved:
                    self.update()
        
        except Exception as e:
            print(f"Error in update_movement: {e}")

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
    
    def mousePressEvent(self, event):
        """Handle mouse press - mode aware"""
        if self.mode == MODE_3D:
            # ===== 3D MODE ONLY =====
            if event.button() == Qt.MouseButton.LeftButton:
                mouse_x = event.position().x()
                mouse_y = event.position().y()
                
                # Force a render to ensure matrices are up to date
                self.makeCurrent()  # Make OpenGL context current
                
                # Manually set up matrices like in render
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(60, self.width() / self.height(), 0.1, 10000.0)
                
                glMatrixMode(GL_MODELVIEW)
                glLoadIdentity()
                cam = self.camera_3d
                gluLookAt(
                    cam.position[0], cam.position[1], cam.position[2],
                    *cam.get_look_at(),
                    0, 1, 0
                )
                
                # Now do selection with correct matrices
                selected_entity = self.select_entity_3d(mouse_x, mouse_y)
                
                if selected_entity:
                    self.selected = [selected_entity]
                    self.selected_entity = selected_entity
                    
                    if hasattr(self, 'gizmo_renderer'):
                        self.gizmo_renderer.update_gizmo_for_entity(selected_entity)
                    
                    self.entitySelected.emit(selected_entity)
                    self.selection_modified = True
                    print(f"âœ“ Selected entity in 3D: {getattr(selected_entity, 'name', 'unknown')}")
                else:
                    self.selected = []
                    self.selected_entity = None
                    
                    if hasattr(self, 'gizmo_renderer'):
                        self.gizmo_renderer.hide_gizmo()
                    
                    self.entitySelected.emit(None)
                    self.selection_modified = True
                    print("âœ“ Cleared selection in 3D mode")
                
                self.update()
                return
                
            elif event.button() == Qt.MouseButton.RightButton:
                # RIGHT CLICK: Capture mouse for camera look
                self.mouse_captured_3d = True
                self.setCursor(Qt.CursorShape.BlankCursor)
                self.last_mouse_3d = event.position()
                return
        
        else:
            # ===== 2D MODE - ORIGINAL CODE UNTOUCHED =====
            self.input_handler.handle_mouse_press(event)


    def mouseReleaseEvent(self, event):
        """Handle mouse release - mode aware"""
        if self.mode == MODE_3D:
            if event.button() == Qt.MouseButton.RightButton:
                # Release camera look
                self.mouse_captured_3d = False
                self.unsetCursor()
        else:
            self.input_handler.handle_mouse_release(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move - mode aware"""
        if self.mode == MODE_3D:
            if self.mouse_captured_3d and self.last_mouse_3d is not None:
                dx = event.position().x() - self.last_mouse_3d.x()
                dy = event.position().y() - self.last_mouse_3d.y()
                self.camera_3d.rotate(dx, dy)
                self.last_mouse_3d = event.position()
                self.update()
        else:
            # 2D handling
            current_time = time()
            if not hasattr(self, '_last_mouse_update'):
                self._last_mouse_update = 0
            
            if current_time - self._last_mouse_update < 0.016:
                return
            
            self._last_mouse_update = current_time
            self.input_handler.handle_mouse_move(event)
            self.update()
    
    def wheelEvent(self, event):
        """Handle wheel - mode aware"""
        if self.mode == MODE_TOPDOWN:
            self.input_handler.handle_wheel(event)
            self.update()
        
    def select_entity_2d(self, mouse_x, mouse_y):
        """Select entity in 2D (your existing implementation)"""
        if not self.entities:
            return None
        
        world_x, world_y = self.screen_to_world(mouse_x, mouse_y)
        
        closest_entity = None
        closest_distance = float('inf')
        selection_radius = 10.0 / self.scale_factor
        
        for entity in self.entities:
            dx = entity.x - world_x
            dy = entity.y - world_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance < selection_radius and distance < closest_distance:
                closest_distance = distance
                closest_entity = entity
        
        return closest_entity
    
    def select_entity_3d(self, mouse_x, mouse_y):
        """Select entity in 3D mode using screen-space distance (simpler approach)"""
        if not self.entities:
            return None
        
        try:
            # SIMPLER APPROACH: Project entities to screen and check distance
            
            # Get matrices during paint
            viewport = glGetIntegerv(GL_VIEWPORT)
            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
            projection = glGetDoublev(GL_PROJECTION_MATRIX)
            
            closest_entity = None
            closest_distance = float('inf')
            selection_threshold = 20.0  # pixels
            
            for entity in self.entities:
                if not (hasattr(entity, 'x') and hasattr(entity, 'y') and hasattr(entity, 'z')):
                    continue
                
                # Entity position in 3D world space (match rendering)
                world_x = float(entity.x)
                world_y = float(entity.z)
                world_z = float(-entity.y)
                
                # Project entity to screen coordinates
                try:
                    screen_pos = gluProject(world_x, world_y, world_z, 
                                        modelview, projection, viewport)
                    
                    screen_x = screen_pos[0]
                    screen_y = viewport[3] - screen_pos[1]  # Flip Y
                    
                    # Calculate distance from mouse to projected entity
                    dx = screen_x - mouse_x
                    dy = screen_y - mouse_y
                    distance = np.sqrt(dx*dx + dy*dy)
                    
                    # Check if this is the closest entity within threshold
                    if distance < selection_threshold and distance < closest_distance:
                        closest_distance = distance
                        closest_entity = entity
                        print(f"Entity '{getattr(entity, 'name', 'unknown')}' at screen ({screen_x:.0f}, {screen_y:.0f}), distance: {distance:.1f}px")
                
                except Exception as e:
                    continue
            
            if closest_entity:
                print(f"âœ“ Selected: {getattr(closest_entity, 'name', 'unknown')} (distance: {closest_distance:.1f}px)")
            else:
                print(f"No entity within {selection_threshold}px of click")
            
            return closest_entity
            
        except Exception as e:
            print(f"Error in select_entity_3d: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    def set_entities(self, entities):
        """Set entities after level load and assign 3D models using local EntityLibrary"""
        print(f"Setting {len(entities)} entities.")
        self.entities = entities
        self.show_entities = True

        # FIXED: Check model_loader's attribute and call its method
        if hasattr(self, 'model_loader') and getattr(self.model_loader, '_entity_library_loaded', False):
            print("Assigning 3D models using LOCAL EntityLibrary...")
            self.model_loader.assign_models_to_entities(entities)  # <-- FIXED!
        else:
            print("âš ï¸ EntityLibrary not loaded in ModelLoader")

        if hasattr(self, 'entity_renderer'):
            from time import time
            start = time()
            for entity in entities:
                self.entity_renderer.get_or_cache_entity_data(entity)
            print(f"Built entity cache in {time() - start:.2f}s")

        self.selected_entity = None
        self.selected = []
        self.entities_modified = True
        self.selection_modified = True
        if entities:
            self._center_view_on_entities()
        print(f"âœ“ Entities set: count={len(entities)}")
        self.update()

    def setup_3d_models_for_level(self, worlds_path):
        """
        Setup 3D models specifically for a loaded level.
        FIXED: Uses local editor assets for models, game files for EntityLibrary
        
        Models: canvas/assets/models/graphics (local editor folder)
        EntityLibrary: patch/worlds/level_name/generated/ (game files)
        Materials: patch/graphics/_materials (game files)
        """
        print(f"\n=== Setting up 3D models for level ===")
        print(f"Level worlds path: {worlds_path}")
        
        if not worlds_path or not os.path.exists(worlds_path):
            print(f"âš ï¸ Invalid worlds path: {worlds_path}")
            return False
        
        # ============================================
        # 1. Setup EntityLibrary from game files
        # ============================================
        success = self.model_loader.set_entity_library_folder(worlds_path)
        if success:
            print(f"âœ… EntityLibrary configured from: {worlds_path}")
        else:
            print(f"âš ï¸ EntityLibrary setup failed")
            return False
        
        # ============================================
        # 2. Setup Models from LOCAL editor assets
        # ============================================
        # Get the editor's root directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        editor_root = os.path.dirname(current_dir)  # Go up from canvas/ to editor root
        
        models_path = os.path.join(editor_root, "canvas", "assets", "models", "graphics")
        
        if os.path.exists(models_path):
            self.model_loader.set_models_directory(models_path, scan_recursive=True)
            print(f"âœ… Models directory set (local assets): {models_path}")
        else:
            # Try alternative paths
            alt_paths = [
                os.path.join(current_dir, "assets", "models", "graphics"),  # canvas/assets/models/graphics
                os.path.join(editor_root, "assets", "models", "graphics"),   # assets/models/graphics
            ]
            
            found = False
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    self.model_loader.set_models_directory(alt_path, scan_recursive=True)
                    print(f"âœ… Models directory set (local assets): {alt_path}")
                    found = True
                    break
            
            if not found:
                print(f"âš ï¸ Models directory not found!")
                print(f"   Tried: {models_path}")
                for alt in alt_paths:
                    print(f"   Tried: {alt}")
        
        # ============================================
        # 3. Setup Materials from game patch files
        # ============================================
        # Derive patch root from worlds path
        path_parts = worlds_path.replace('\\', '/').split('/')
        
        # Find 'worlds' or 'Worlds' in path
        worlds_index = -1
        for i, part in enumerate(path_parts):
            if part.lower() == 'worlds':
                worlds_index = i
                break
        
        if worlds_index != -1:
            # Patch root is everything up to (but not including) 'worlds'
            patch_root = '/'.join(path_parts[:worlds_index])
            print(f"Derived patch root: {patch_root}")
            
            # Setup materials from game files
            materials_path = os.path.join(patch_root, "graphics", "_materials")
            if os.path.exists(materials_path):
                self.model_loader.set_materials_directory(materials_path)
                print(f"âœ… Materials directory set: {materials_path}")
            else:
                # Try without underscore
                materials_path_alt = os.path.join(patch_root, "graphics", "materials")
                if os.path.exists(materials_path_alt):
                    self.model_loader.set_materials_directory(materials_path_alt)
                    print(f"âœ… Materials directory set: {materials_path_alt}")
                else:
                    print(f"âš ï¸ Materials directory not found: {materials_path}")
                    print(f"   Models will render without textures")
        else:
            print(f"âš ï¸ Could not find 'worlds' folder in path: {worlds_path}")
            print(f"   Materials directory not set")
        
        print(f"=== 3D model setup complete ===\n")
        return True

    def _center_view_on_entities(self):
        """Center 2D view on all entities"""
        if not self.entities:
            return
        
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
        
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        if max_x > min_x and max_y > min_y:
            width_span = max_x - min_x
            height_span = max_y - min_y
            
            scale_x = (self.width() * 0.8) / width_span if width_span > 0 else 1.0
            scale_y = (self.height() * 0.8) / height_span if height_span > 0 else 1.0
            self.scale_factor = min(scale_x, scale_y, 2.0)
        else:
            self.scale_factor = 1.0
        
        new_offset_x = self.width() / 2 - center_x * self.scale_factor
        new_offset_y = self.height() / 2 - center_y * self.scale_factor
        
        self.camera_controller.offset_x = new_offset_x
        self.camera_controller.offset_y = new_offset_y
        self.offset_x = new_offset_x
        self.offset_y = new_offset_y
        
        print(f"Centered view on {valid_entities} entities at scale {self.scale_factor:.2f}")
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen (2D mode)"""
        return OpenGLUtils.world_to_screen(world_x, world_y, self)

    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world (2D mode)"""
        return OpenGLUtils.screen_to_world(screen_x, screen_y, self)
    
    def set_grid_config(self, grid_config):
        """Set grid configuration"""
        self.grid_config = grid_config
        self.update()
    
    def set_current_map(self, map_info):
        """Set current map"""
        self.current_map = map_info
        self.entities_modified = True
        self.update()
    
    def flash_entity(self, entity):
        """Flash entity to highlight"""
        if self.icon_renderer:
            self.icon_renderer.flash_entity(entity)
        self.update()
    
    def zoom_to_entity(self, entity):
        """Zoom to entity"""
        if not entity:
            return
        
        self.camera_controller.zoom_to_entity_2d(entity, self)
        self.flash_entity(entity)
    
    def reset_view(self):
        """Reset view"""
        if not self.entities:
            self.camera_controller.offset_x = self.width() / 2
            self.camera_controller.offset_y = self.height() / 2
            self.offset_x = self.camera_controller.offset_x
            self.offset_y = self.camera_controller.offset_y
            self.scale_factor = 1.0
            
            self.update()
            return self.scale_factor
        
        self._center_view_on_entities()
        self.update()
        return self.scale_factor
    
    def zoom_in(self):
        """Zoom in"""
        self.camera_controller.zoom_in(self)

    def zoom_out(self):
        """Zoom out"""
        self.camera_controller.zoom_out(self)
    
    def invalidate_entity_caches(self):
        """Invalidate all entity caches"""
        self.entity_cache_dirty = True
        self.last_3d_camera_pos = None
        self.last_3d_camera_angles = None
        
        if hasattr(self, 'entity_renderer'):
            self.entity_renderer.invalidate_all_entity_caches()
        
        self.entities_modified = True
        self.selection_modified = True
        
        print("All entity caches invalidated")
    
    def update_entity_xml(self, entity):
        """Update entity XML coordinates"""
        self.entities_modified = True
        
        if not entity:
            return False
        
        source_file_path = getattr(entity, 'source_file_path', None)
        
        if source_file_path:
            if source_file_path.endswith('.data.xml') or source_file_path.endswith('.converted.xml'):
                return self._update_worldsector_xml_fcb_format(entity, source_file_path)
        else:
            return self._update_memory_xml_dunia_format(entity)
        
        return False
    
    def _update_worldsector_xml_fcb_format(self, entity, xml_file_path):
        """Update WorldSector XML (FCB format)"""
        try:
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
            
            for entity_elem in root.findall(".//object[@name='Entity']"):
                name_field = entity_elem.find("./field[@name='hidName']")
                if name_field is not None:
                    name_value = name_field.get('value-String')
                    if name_value == getattr(entity, 'name', ''):
                        self._update_fcb_position_field(entity_elem, "hidPos", entity.x, entity.y, entity.z)
                        self._update_fcb_position_field(entity_elem, "hidPos_precise", entity.x, entity.y, entity.z)
                        
                        entity.xml_element = entity_elem
                        return True
            
            return False
            
        except Exception as e:
            print(f"Error updating FCB XML: {e}")
            return False

    def _update_fcb_position_field(self, entity_elem, field_name, x, y, z):
        """Update position field (FCB format)"""
        pos_field = entity_elem.find(f"./field[@name='{field_name}']")
        if pos_field is not None:
            new_pos_value = f"{x:.0f},{y:.0f},{z:.0f}"
            pos_field.set('value-Vector3', new_pos_value)
            
            binary_hex = self._coordinates_to_binhex(x, y, z)
            pos_field.text = binary_hex

    def _coordinates_to_binhex(self, x, y, z):
        """Convert coordinates to BinHex"""
        import struct
        binary_data = struct.pack('<fff', float(x), float(y), float(z))
        hex_string = binary_data.hex().upper()
        return hex_string

    def _update_memory_xml_dunia_format(self, entity):
        """Update main file entity (Dunia format)"""
        if not hasattr(entity, 'xml_element') or entity.xml_element is None:
            return False
        
        try:
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
            print(f"Error updating Dunia XML: {e}")
            return False
    
    def mark_entity_modified(self, entity):
        """Mark entity as modified"""
        if not entity:
            return
        
        if hasattr(self, 'entity_renderer'):
            self.entity_renderer.invalidate_entity_cache(entity)
        
        self.invalidate_entity_caches()
        
        print(f"Entity {getattr(entity, 'name', 'unknown')} marked as modified")
    
    def mark_entities_modified(self):
        """Mark entities as modified"""
        self.entities_modified = True
        if self.parent():
            if hasattr(self.parent(), 'entities_modified'):
                self.parent().entities_modified = True
    
    def draw_sector_boundaries(self, painter):
        """Draw sector boundaries for both worldsectors AND landmarks (2D only)"""
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
            landmarks_drawn = 0
            original_pen = painter.pen()
            original_brush = painter.brush()
            original_font = painter.font()

            for i, sector_info in enumerate(self.sector_data):
                try:
                    sector_id = sector_info.get('id', 0)
                    sector_x = sector_info.get('x', 0)
                    sector_y = sector_info.get('y', 0)
                    sector_size = sector_info.get('size', 64)
                    is_landmark = sector_info.get('is_landmark', False)

                    # Calculate world bounds
                    world_min_x = sector_x * sector_size
                    world_min_y = sector_y * sector_size
                    world_max_x = world_min_x + sector_size
                    world_max_y = world_min_y + sector_size

                    # Convert to screen coordinates
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

                    # Skip if too small
                    if rect_w < 2 or rect_h < 2:
                        continue

                    # Skip if off-screen (with margin)
                    margin = 50
                    if (rect_x > self.width() + margin or
                        rect_y > self.height() + margin or
                        rect_x + rect_w < -margin or
                        rect_y + rect_h < -margin):
                        continue

                    # Check for violations
                    has_violations = False
                    try:
                        if hasattr(self, "check_sector_violations"):
                            has_violations = self.check_sector_violations(sector_info)
                    except Exception as violation_error:
                        print(f"Error checking violations: {violation_error}")

                    # Choose colors based on type and violation status
                    if is_landmark:
                        # LANDMARKS: Purple/Magenta
                        if has_violations:
                            pen_color = QColor(255, 0, 255, 255)  # Bright magenta for violations
                            brush_color = QColor(255, 0, 255, 40)
                            pen_width = 3
                        else:
                            pen_color = QColor(128, 0, 255, 200)  # Purple for normal landmarks
                            brush_color = QColor(128, 0, 255, 30)
                            pen_width = 2
                        landmarks_drawn += 1
                    else:
                        # WORLDSECTORS: Red/Orange
                        if has_violations:
                            pen_color = QColor(255, 100, 0, 255)  # Orange for violations
                            brush_color = QColor(255, 100, 0, 40)
                            pen_width = 3
                        else:
                            pen_color = QColor(255, 0, 0, 200)  # Red for normal sectors
                            brush_color = QColor(255, 0, 0, 30)
                            pen_width = 2

                    # Draw the sector boundary rectangle
                    painter.setPen(QPen(pen_color, pen_width))
                    painter.setBrush(QBrush(brush_color))
                    painter.drawRect(int(rect_x), int(rect_y), int(rect_w), int(rect_h))
                    boundaries_drawn += 1

                    # Create label text
                    if is_landmark:
                        label_text = f"Landmark {sector_id}"
                    else:
                        label_text = f"Sector {sector_id}"
                    
                    if has_violations:
                        label_text += " ⚠"  # Warning symbol

                    # Draw label with background
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

                    # Draw label background (semi-transparent black)
                    painter.fillRect(bg_x, bg_y, bg_w, bg_h, QColor(0, 0, 0, 200))
                    painter.setPen(QPen(QColor(255, 255, 255), 1))
                    painter.drawRect(bg_x, bg_y, bg_w, bg_h)

                    # Draw label text (white)
                    painter.setPen(QPen(QColor(255, 255, 255), 2))
                    painter.drawText(label_x, label_y, label_text)

                    # Optional: Draw entity count badge
                    entity_count = sector_info.get('entity_count', 0)
                    if entity_count > 0:
                        count_text = f"{entity_count}"
                        count_metrics = painter.fontMetrics()
                        count_rect = count_metrics.boundingRect(count_text)
                        
                        badge_x = int(rect_x + rect_w - count_rect.width() - 8)
                        badge_y = int(rect_y + 15)
                        badge_bg_x = badge_x - bg_padding
                        badge_bg_y = badge_y - count_rect.height() - bg_padding
                        badge_bg_w = count_rect.width() + (bg_padding * 2)
                        badge_bg_h = count_rect.height() + (bg_padding * 2)
                        
                        # Draw badge background
                        badge_color = QColor(128, 0, 255) if is_landmark else QColor(255, 0, 0)
                        painter.fillRect(badge_bg_x, badge_bg_y, badge_bg_w, badge_bg_h, 
                                    QColor(badge_color.red(), badge_color.green(), badge_color.blue(), 180))
                        painter.setPen(QPen(QColor(255, 255, 255), 1))
                        painter.drawRect(badge_bg_x, badge_bg_y, badge_bg_w, badge_bg_h)
                        
                        # Draw count text
                        painter.setPen(QPen(QColor(255, 255, 255), 2))
                        painter.drawText(badge_x, badge_y, count_text)

                except Exception as sector_error:
                    print(f"Error processing sector {i}: {sector_error}")
                    continue

            # Restore original painter state
            painter.setPen(original_pen)
            painter.setBrush(original_brush)
            painter.setFont(original_font)

            # Log summary
            regular_sectors = boundaries_drawn - landmarks_drawn
            if landmarks_drawn > 0:
                print(f"Drew {boundaries_drawn} boundaries: {regular_sectors} sectors (red), {landmarks_drawn} landmarks (purple)")
            else:
                print(f"Drew {boundaries_drawn}/{len(self.sector_data)} sector boundaries")

        except Exception as e:
            print(f"Error in draw_sector_boundaries: {e}")
            import traceback
            traceback.print_exc()

    def create_fallback_sector_data(self):
        """Create fallback sector data"""
        print("Creating fallback sector data...")
        
        if not hasattr(self, 'entities') or not self.entities:
            self.sector_data = []
            return
        
        sector_map = {}
        
        for entity in self.entities:
            if not (hasattr(entity, 'x') and hasattr(entity, 'y')):
                continue
                
            sector_x = int(entity.x // 64)
            sector_y = int(entity.y // 64)
            sector_key = (sector_x, sector_y)
            
            if sector_key not in sector_map:
                sector_map[sector_key] = {
                    'id': len(sector_map) + 1,
                    'x': sector_x,
                    'y': sector_y,
                    'size': 64,
                    'entities': [],
                    'expected_ids': []
                }
            
            sector_map[sector_key]['entities'].append(entity)
            
            entity_id = getattr(entity, 'id', id(entity))
            if entity_id not in sector_map[sector_key]['expected_ids']:
                sector_map[sector_key]['expected_ids'].append(entity_id)
        
        self.sector_data = list(sector_map.values())
        
        print(f"Created fallback sector data: {len(self.sector_data)} sectors")
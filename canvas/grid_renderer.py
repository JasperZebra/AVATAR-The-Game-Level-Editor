"""Grid rendering module for 2D grids with OpenGL acceleration - 2D ONLY"""

from time import time
import math
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QVector3D
from .opengl_utils import OpenGLUtils

# Try to import OpenGL - graceful fallback if not available
try:
    from PyQt6.QtOpenGLWidgets import QOpenGLWidget
    from PyQt6.QtOpenGL import QOpenGLBuffer, QOpenGLShaderProgram, QOpenGLVertexArrayObject, QOpenGLShader
    import OpenGL.GL as gl
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    print("OpenGL not available - using QPainter for grids")

class GridRenderer:
    """Handles 2D grid rendering with optional OpenGL acceleration - 2D ONLY"""
    
    def __init__(self):
        self.initialized = False
        self.use_opengl = OPENGL_AVAILABLE  # Enable OpenGL by default if available
        
        if OPENGL_AVAILABLE and self.use_opengl:
            self.grid_2d_program = None
            self.grid_2d_vao = None
            self.grid_2d_vbo = None
            
            # Updated shader source code for better compatibility
            self.vertex_shader_2d = """
            #version 330 core
            layout (location = 0) in vec2 position;
            layout (location = 1) in vec3 color;
            
            uniform mat4 projection;
            uniform mat4 view;
            
            out vec3 vertexColor;
            
            void main() {
                gl_Position = projection * view * vec4(position, 0.0, 1.0);
                vertexColor = color;
            }
            """
            
            self.fragment_shader = """
            #version 330 core
            in vec3 vertexColor;
            out vec4 FragColor;
            
            void main() {
                FragColor = vec4(vertexColor, 1.0);
            }
            """
        
        print(f"GridRenderer initialized (2D only, OpenGL: {self.use_opengl})")
    
    def initialize_gl(self):
        """Initialize OpenGL resources for grid rendering"""
        if not self.use_opengl or self.initialized:
            return True
            
        try:
            print("Creating 2D grid shader program...")
            
            # Create 2D shader program
            self.grid_2d_program = self._create_shader_program(
                self.vertex_shader_2d, self.fragment_shader)
            if not self.grid_2d_program:
                print("Failed to create 2D shader program")
                return False
            
            # Create VAOs and VBOs
            self.grid_2d_vao = QOpenGLVertexArrayObject()
            if not self.grid_2d_vao.create():
                print("Failed to create 2D VAO")
                return False
            
            self.grid_2d_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            if not self.grid_2d_vbo.create():
                print("Failed to create 2D VBO")
                return False
            
            self.initialized = True
            print("Grid OpenGL resources initialized successfully")
            return True
            
        except Exception as e:
            print(f"Error initializing grid OpenGL: {e}")
            import traceback
            traceback.print_exc()
            self.use_opengl = False  # Fall back to QPainter
            return False
    
    def _create_shader_program(self, vertex_source, fragment_source):
        """Create and compile a shader program"""
        try:
            program = QOpenGLShaderProgram()
            
            # Add vertex shader
            if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, vertex_source):
                print(f"Vertex shader compilation failed: {program.log()}")
                return None
            
            # Add fragment shader
            if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment_source):
                print(f"Fragment shader compilation failed: {program.log()}")
                return None
            
            # Link program
            if not program.link():
                print(f"Shader program linking failed: {program.log()}")
                return None
            
            print("Shader program created successfully")
            return program
            
        except Exception as e:
            print(f"Error creating shader program: {e}")
            return None
    
    def render_2d_grid(self, canvas):
        """Render 2D grid using OpenGL or QPainter fallback"""
        if not canvas.show_grid:
            return
            
        if self.use_opengl and self.initialized:
            try:
                self._render_2d_grid_opengl(canvas)
                return
            except Exception as e:
                print(f"OpenGL 2D grid rendering failed: {e}")
                self.use_opengl = False  # Disable OpenGL on failure
        
        # Fallback to QPainter
        painter = QPainter(canvas)
        self._draw_2d_grid_qpainter(painter, canvas)
        painter.end()
    
    def render_2d_grid_qpainter(self, painter, canvas):
        """Render 2D grid using existing QPainter"""
        if not canvas.show_grid:
            return
        self._draw_2d_grid_qpainter(painter, canvas)
    
    def _render_2d_grid_opengl(self, canvas):
        """Render 2D grid using OpenGL with separate passes for different line thicknesses"""
        try:
            # Generate grid data with proper separation
            minor_data, major_data, axis_data = self._generate_2d_grid_data_separated(canvas)
            
            # Create projection matrix that matches Qt's coordinate system
            from PyQt6.QtGui import QMatrix4x4
            projection = QMatrix4x4()
            
            # Convert current view bounds to world coordinates
            world_left, world_bottom = OpenGLUtils.screen_to_world(0, canvas.height(), canvas)
            world_right, world_top = OpenGLUtils.screen_to_world(canvas.width(), 0, canvas)
            
            # Set up orthographic projection to match current view
            projection.ortho(world_left, world_right, world_bottom, world_top, -1, 1)
            
            view = QMatrix4x4()  # Identity
            
            # Use shader program
            self.grid_2d_program.bind()
            self.grid_2d_program.setUniformValue("projection", projection)
            self.grid_2d_program.setUniformValue("view", view)
            
            # Draw minor grid lines first (1px)
            if len(minor_data) > 0:
                self.grid_2d_vao.bind()
                self.grid_2d_vbo.bind()
                self.grid_2d_vbo.allocate(minor_data.tobytes(), len(minor_data) * 4)
                
                # Setup vertex attributes
                gl.glEnableVertexAttribArray(0)  # Position
                gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, None)
                
                gl.glEnableVertexAttribArray(1)  # Color
                gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, gl.ctypes.c_void_p(2 * 4))
                
                vertex_count = len(minor_data) // 5
                gl.glLineWidth(1.0)  # Thin lines for minor grid
                gl.glDrawArrays(gl.GL_LINES, 0, vertex_count)
                
                self.grid_2d_vao.release()
            
            # Draw major grid lines second (4px thick)
            if len(major_data) > 0:
                self.grid_2d_vao.bind()
                self.grid_2d_vbo.bind()
                self.grid_2d_vbo.allocate(major_data.tobytes(), len(major_data) * 4)
                
                # Setup vertex attributes
                gl.glEnableVertexAttribArray(0)  # Position
                gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, None)
                
                gl.glEnableVertexAttribArray(1)  # Color
                gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, gl.ctypes.c_void_p(2 * 4))
                
                vertex_count = len(major_data) // 5
                gl.glLineWidth(2.0)  # THICK lines for major grid
                gl.glDrawArrays(gl.GL_LINES, 0, vertex_count)
                
                self.grid_2d_vao.release()
            
            # Draw axis lines last (6px thick)
            if len(axis_data) > 0:
                self.grid_2d_vao.bind()
                self.grid_2d_vbo.bind()
                self.grid_2d_vbo.allocate(axis_data.tobytes(), len(axis_data) * 4)
                
                # Setup vertex attributes
                gl.glEnableVertexAttribArray(0)  # Position
                gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, None)
                
                gl.glEnableVertexAttribArray(1)  # Color
                gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 5 * 4, gl.ctypes.c_void_p(2 * 4))
                
                vertex_count = len(axis_data) // 5
                gl.glLineWidth(5.0)  # VERY THICK lines for red/green axes
                gl.glDrawArrays(gl.GL_LINES, 0, vertex_count)
                
                self.grid_2d_vao.release()
            
            self.grid_2d_program.release()
            
        except Exception as e:
            print(f"Error rendering 2D grid: {e}")
            raise  # Re-raise to trigger fallback

    def _generate_2d_grid_data_separated(self, canvas):
        """Generate 2D grid vertex data with proper separation for minor, major, and axis lines"""
        minor_vertices = []  # Minor grid lines (1px)
        major_vertices = []  # Major grid lines (4px)
        axis_vertices = []   # Red/Green axis lines (6px)
        
        # Calculate grid bounds based on current view
        width = canvas.width()
        height = canvas.height()
        
        # Convert screen bounds to world coordinates  
        world_left, world_bottom = OpenGLUtils.screen_to_world(0, height, canvas)
        world_right, world_top = OpenGLUtils.screen_to_world(width, 0, canvas)
        
        # Add padding
        padding = 200
        world_left -= padding
        world_right += padding
        world_bottom -= padding
        world_top += padding
        
        # Grid settings
        grid_step = 64  # 64-unit grid
        major_interval = 5  # Every 5th line is major
        
        # Snap to grid boundaries
        min_x = int(world_left / grid_step) * grid_step
        max_x = int(world_right / grid_step) * grid_step + grid_step
        min_y = int(world_bottom / grid_step) * grid_step  
        max_y = int(world_top / grid_step) * grid_step + grid_step
        
        # Limit grid size
        grid_limit = 5120
        min_x = max(min_x, -grid_limit)
        max_x = min(max_x, grid_limit)
        min_y = max(min_y, -grid_limit)
        max_y = min(max_y, grid_limit)
        
        # Generate horizontal lines
        for y in range(int(min_y), int(max_y) + 1, grid_step):
            if abs(y) > grid_limit:
                continue
                
            if y == 0:
                # RED X-axis - goes to axis_vertices for 6px rendering
                color = [1.0, 0.0, 0.0]
                axis_vertices.extend([min_x, y, color[0], color[1], color[2]])
                axis_vertices.extend([max_x, y, color[0], color[1], color[2]])
            elif y % (grid_step * major_interval) == 0:
                # Major grid lines - goes to major_vertices for 4px rendering
                color = [0.0, 0.0, 0.0]  # BLACK for major lines
                major_vertices.extend([min_x, y, color[0], color[1], color[2]])
                major_vertices.extend([max_x, y, color[0], color[1], color[2]])
            else:
                # Minor grid lines - goes to minor_vertices for 1px rendering
                color = [0.2, 0.2, 0.2]  # DARK GRAY for minor lines
                minor_vertices.extend([min_x, y, color[0], color[1], color[2]])
                minor_vertices.extend([max_x, y, color[0], color[1], color[2]])
        
        # Generate vertical lines
        for x in range(int(min_x), int(max_x) + 1, grid_step):
            if abs(x) > grid_limit:
                continue
                
            if x == 0:
                # GREEN Y-axis - goes to axis_vertices for 6px rendering
                color = [0.0, 1.0, 0.0]
                axis_vertices.extend([x, min_y, color[0], color[1], color[2]])
                axis_vertices.extend([x, max_y, color[0], color[1], color[2]])
            elif x % (grid_step * major_interval) == 0:
                # Major grid lines - goes to major_vertices for 4px rendering
                color = [0.0, 0.0, 0.0]  # BLACK for major lines
                major_vertices.extend([x, min_y, color[0], color[1], color[2]])
                major_vertices.extend([x, max_y, color[0], color[1], color[2]])
            else:
                # Minor grid lines - goes to minor_vertices for 1px rendering
                color = [0.2, 0.2, 0.2]  # DARK GRAY for minor lines
                minor_vertices.extend([x, min_y, color[0], color[1], color[2]])
                minor_vertices.extend([x, max_y, color[0], color[1], color[2]])
        
        # Return numpy arrays for each line type
        minor_array = np.array(minor_vertices, dtype=np.float32) if minor_vertices else np.array([], dtype=np.float32)
        major_array = np.array(major_vertices, dtype=np.float32) if major_vertices else np.array([], dtype=np.float32)
        axis_array = np.array(axis_vertices, dtype=np.float32) if axis_vertices else np.array([], dtype=np.float32)
        
        return minor_array, major_array, axis_array
    
    def _draw_2d_grid_qpainter(self, painter, canvas):
        """QPainter fallback for 2D grid rendering with THICKER major lines"""
        try:
            width = canvas.width()
            height = canvas.height()
            
            # Fixed 64-unit grid squares
            grid_world_size = 64
            grid_world_limit = 4000
            
            min_x = max(-grid_world_limit, OpenGLUtils.screen_to_world(0, height, canvas)[0])
            min_y = max(-grid_world_limit, OpenGLUtils.screen_to_world(0, height, canvas)[1])
            max_x = min(grid_world_limit, OpenGLUtils.screen_to_world(width, 0, canvas)[0])
            max_y = min(grid_world_limit, OpenGLUtils.screen_to_world(width, 0, canvas)[1])
            
            # Round to nearest grid size
            min_x = int(min_x / grid_world_size) * grid_world_size
            min_y = int(min_y / grid_world_size) * grid_world_size
            max_x = int(max_x / grid_world_size) * grid_world_size + grid_world_size
            max_y = int(max_y / grid_world_size) * grid_world_size + grid_world_size
            
            # Grid styling - Use integer widths for major lines
            minor_pen = QPen(QColor(50, 50, 50), 1)      # Minor lines: 1px
            major_pen = QPen(QColor(0, 0, 0), 5)         # Major lines: 2px
            major_interval = 5
            
            # Draw horizontal lines
            for y in range(int(min_y), int(max_y) + 1, grid_world_size):
                if abs(y) > grid_world_limit:
                    continue
                    
                start_x, start_y = OpenGLUtils.world_to_screen(min_x, y, canvas)
                end_x, end_y = OpenGLUtils.world_to_screen(max_x, y, canvas)
                
                if y == 0:
                    painter.setPen(QPen(QColor(255, 0, 0), 4))  # Thick red X-axis
                elif y % (grid_world_size * major_interval) == 0:
                    painter.setPen(major_pen)  # 2px thick major lines
                else:
                    painter.setPen(minor_pen)  # 1px minor lines
                
                painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
            
            # Draw vertical lines
            for x in range(int(min_x), int(max_x) + 1, grid_world_size):
                if abs(x) > grid_world_limit:
                    continue
                    
                start_x, start_y = OpenGLUtils.world_to_screen(x, min_y, canvas)
                end_x, end_y = OpenGLUtils.world_to_screen(x, max_y, canvas)
                
                if x == 0:
                    painter.setPen(QPen(QColor(0, 255, 0), 4))  # Thick green Y-axis
                elif x % (grid_world_size * major_interval) == 0:
                    painter.setPen(major_pen)  # 2px thick major lines
                else:
                    painter.setPen(minor_pen)  # 1px minor lines
                
                painter.drawLine(int(start_x), int(start_y), int(end_x), int(end_y))
            
            # Draw origin marker
            origin_x, origin_y = OpenGLUtils.world_to_screen(0, 0, canvas)
            painter.setPen(QPen(QColor(0, 0, 255), 2))
            painter.setBrush(QBrush(QColor(0, 0, 255)))
            painter.drawEllipse(int(origin_x - 3), int(origin_y - 3), 6, 6)
            
            # Draw origin label
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(int(origin_x + 5), int(origin_y - 5), "Origin (0,0)")
            
            # Draw grid info
            painter.setPen(QPen(Qt.GlobalColor.black, 1))
            painter.setFont(QFont("Arial", 9))
            grid_info = f"Grid: {grid_world_size} units per square (zoom: {canvas.scale_factor:.2f}x)"
            painter.drawText(10, canvas.height() - 20, grid_info)
            
        except Exception as e:
            print(f"Error drawing 2D grid with QPainter: {e}")
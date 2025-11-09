"""OpenGL utility functions for coordinate conversion and helpers - 2D ONLY"""

import math
from time import time
from PyQt6.QtGui import QVector3D

class OpenGLUtils:
    """Utility functions for OpenGL operations and coordinate conversions - 2D ONLY"""
    
    @staticmethod
    def world_to_screen(world_x, world_y, canvas):
        """Convert world coordinates to screen coordinates"""
        screen_x = world_x * canvas.scale_factor + canvas.offset_x
        screen_y = canvas.height() - (world_y * canvas.scale_factor + canvas.offset_y)
        return screen_x, screen_y

    @staticmethod
    def screen_to_world(screen_x, screen_y, canvas):
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x - canvas.offset_x) / canvas.scale_factor
        world_y = (canvas.height() - screen_y - canvas.offset_y) / canvas.scale_factor
        return world_x, world_y

    @staticmethod
    def create_shader_program(vertex_source, fragment_source):
        """Create and compile a shader program (for future OpenGL expansion)"""
        try:
            from PyQt6.QtOpenGL import QOpenGLShaderProgram, QOpenGLShader
            
            program = QOpenGLShaderProgram()
            
            # Add vertex shader
            if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, vertex_source):
                print(f"Vertex shader failed: {program.log()}")
                return None
            
            # Add fragment shader
            if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment_source):
                print(f"Fragment shader failed: {program.log()}")
                return None
            
            # Link program
            if not program.link():
                print(f"Shader linking failed: {program.log()}")
                return None
            
            return program
            
        except ImportError:
            print("OpenGL not available for shader creation")
            return None
        except Exception as e:
            print(f"Error creating shader program: {e}")
            return None

    @staticmethod
    def create_opengl_buffer(data, buffer_type):
        """Create an OpenGL buffer with data (for future expansion)"""
        try:
            from PyQt6.QtOpenGL import QOpenGLBuffer
            import numpy as np
            
            buffer = QOpenGLBuffer(buffer_type)
            if buffer.create():
                buffer.bind()
                if isinstance(data, np.ndarray):
                    buffer.allocate(data.tobytes(), len(data) * 4)
                else:
                    buffer.allocate(data, len(data))
                buffer.release()
                return buffer
            return None
            
        except ImportError:
            return None
        except Exception as e:
            print(f"Error creating OpenGL buffer: {e}")
            return None
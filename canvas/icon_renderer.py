"""UI overlay renderer for entity information and status displays - 2D ONLY"""

from time import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

class IconRenderer:
    """Handles rendering of UI overlays and info displays - 2D ONLY"""
    
    def __init__(self):
        # Entity highlighting system
        self.highlighted_entities_list = []
        self.flash_timer = None
        
        print("IconRenderer initialized (2D only) - UI overlays only")
    
    def render_all_overlays(self, painter, canvas):
        """Main method to render all UI overlays for 2D mode"""
        try:
            # Information overlays
            self.draw_entity_count(painter, canvas)
            self.draw_selection_info(painter, canvas)
            self.draw_mode_indicator(painter, canvas)
            self.draw_grid_info(painter, canvas)
            self.draw_performance_info(painter, canvas)
            
        except Exception as e:
            print(f"Error rendering overlays: {e}")
    
    def draw_entity_count(self, painter, canvas):
        """Draw entity count in top-left corner"""
        try:
            entities = getattr(canvas, 'entities', [])
            if not entities:
                return
            
            # Filter visible entities
            visible_count = len(entities)
            current_map = getattr(canvas, 'current_map', None)
            
            if current_map:
                visible_count = len([e for e in entities if getattr(e, 'map_name', None) == current_map.name])
            
            # Setup drawing
            margin = 10
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            
            # Create text
            if current_map and visible_count != len(entities):
                count_text = f"Entities: {visible_count}/{len(entities)} (filtered)"
            else:
                count_text = f"Entities: {len(entities)}"
            
            # Draw background
            metrics = painter.fontMetrics()
            text_width = metrics.boundingRect(count_text).width()
            painter.fillRect(margin - 3, margin - 2, 
                            text_width + 6, metrics.height() + 4, 
                            QColor(0, 0, 0, 100))
            
            # Draw text
            painter.drawText(margin, margin + metrics.ascent(), count_text)
            
        except Exception as e:
            print(f"Error drawing entity count: {e}")
    
    def draw_selection_info(self, painter, canvas):
        """Draw selection information in top-right corner"""
        try:
            selected = getattr(canvas, 'selected', [])
            if not selected:
                return
            
            margin = 10
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            
            if len(selected) == 1:
                # Single entity selected
                entity = selected[0]
                entity_name = getattr(entity, 'name', 'Unknown')
                info_text = f"Selected: {entity_name}"
                pos_text = f"Position: ({entity.x:.1f}, {entity.y:.1f})"
                
                # Calculate text dimensions
                metrics = painter.fontMetrics()
                text_width = max(metrics.boundingRect(info_text).width(), 
                               metrics.boundingRect(pos_text).width())
                
                # Draw background
                text_x = canvas.width() - text_width - margin - 5
                bg_width = text_width + 10
                bg_height = metrics.height() * 2 + 10
                
                painter.fillRect(text_x - 5, margin, bg_width, bg_height, QColor(0, 0, 0, 120))
                
                # Draw text
                painter.drawText(text_x, margin + metrics.ascent(), info_text)
                painter.drawText(text_x, margin + metrics.ascent() + metrics.height(), pos_text)
            
            else:
                # Multiple entities selected
                info_text = f"Selected: {len(selected)} entities"
                
                metrics = painter.fontMetrics()
                text_width = metrics.boundingRect(info_text).width()
                text_x = canvas.width() - text_width - margin - 5
                
                painter.fillRect(text_x - 5, margin, text_width + 10, metrics.height() + 5, QColor(0, 0, 0, 120))
                painter.drawText(text_x, margin + metrics.ascent(), info_text)
                
        except Exception as e:
            print(f"Error drawing selection info: {e}")
    
    def draw_mode_indicator(self, painter, canvas):
        """Draw current mode indicator in bottom-left"""
        try:
            mode_text = "2D View"
            
            margin = 5
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            
            # Calculate position
            metrics = painter.fontMetrics()
            text_y = canvas.height() - margin
            text_width = metrics.boundingRect(mode_text).width()
            
            # Draw background
            painter.fillRect(margin - 3, text_y - metrics.ascent() - 2, 
                            text_width + 6, metrics.height() + 4, 
                            QColor(0, 100, 200, 150))
            
            # Draw text
            painter.drawText(margin, text_y, mode_text)
            
        except Exception as e:
            print(f"Error drawing mode indicator: {e}")
    
    def draw_grid_info(self, painter, canvas):
        """Draw grid information in bottom-right"""
        try:
            if not getattr(canvas, 'show_grid', True):
                return
            
            margin = 10
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            
            # Create grid info text for 2D mode
            scale_factor = getattr(canvas, 'scale_factor', 1.0)
            grid_info = f"Grid: 64 units/square | Zoom: {scale_factor:.2f}x"
            
            # Calculate position
            metrics = painter.fontMetrics()
            text_width = metrics.boundingRect(grid_info).width()
            text_x = canvas.width() - text_width - margin
            text_y = canvas.height() - margin
            
            # Draw background
            painter.fillRect(text_x - 5, text_y - metrics.ascent() - 2, 
                            text_width + 10, metrics.height() + 4, 
                            QColor(0, 0, 0, 100))
            
            # Draw text
            painter.drawText(text_x, text_y, grid_info)
            
        except Exception as e:
            print(f"Error drawing grid info: {e}")
    
    def draw_performance_info(self, painter, canvas):
        """Draw performance information below entity count"""
        try:
            margin = 10
            painter.setFont(QFont("Arial", 8))
            painter.setPen(QPen(QColor(150, 150, 150), 1))
            
            perf_text = "Rendering: 2D QPainter"
            
            # Position below entity count
            metrics = painter.fontMetrics()
            text_y = margin + metrics.height() * 2 + 5
            
            painter.drawText(margin, text_y, perf_text)
            
        except Exception as e:
            print(f"Error drawing performance info: {e}")
    
    def flash_entity(self, entity):
        """Start flashing an entity to highlight it"""
        try:
            if not entity:
                return
            
            # Remove any existing highlight for this entity
            self.highlighted_entities_list = [
                item for item in self.highlighted_entities_list 
                if item['entity'] != entity
            ]
            
            # Add new highlight
            highlight_info = {
                'entity': entity,
                'start_time': time(),
                'duration': 1.0,  # 1 second highlight
                'flash_count': 5   # Number of flashes
            }
            self.highlighted_entities_list.append(highlight_info)
            
            # Start flash timer if not already running
            if not self.flash_timer:
                self.flash_timer = QTimer()
                self.flash_timer.timeout.connect(self.update_entity_highlights)
                self.flash_timer.start(50)  # Update every 50ms
            
            entity_name = getattr(entity, 'name', 'unknown')
            print(f"Started flashing entity: {entity_name}")
            
        except Exception as e:
            print(f"Error starting entity flash: {e}")
    
    def update_entity_highlights(self):
        """Update flashing effects for highlighted entities"""
        try:
            if not self.highlighted_entities_list:
                # No highlighted entities, stop the timer
                if self.flash_timer:
                    self.flash_timer.stop()
                    self.flash_timer = None
                return
            
            # Check each highlighted entity
            current_time = time()
            entities_to_remove = []
            
            for i, highlight_info in enumerate(self.highlighted_entities_list):
                start_time = highlight_info['start_time']
                duration = highlight_info['duration']
                
                # Check if highlight duration is over
                if current_time - start_time > duration:
                    entities_to_remove.append(i)
            
            # Remove expired highlights (in reverse order)
            for i in reversed(entities_to_remove):
                entity_name = getattr(self.highlighted_entities_list[i]['entity'], 'name', 'unknown')
                print(f"Stopped flashing entity: {entity_name}")
                del self.highlighted_entities_list[i]
            
            # Stop timer if no more highlights
            if not self.highlighted_entities_list and self.flash_timer:
                self.flash_timer.stop()
                self.flash_timer = None
                
        except Exception as e:
            print(f"Error updating entity highlights: {e}")
    
    def draw_status_message(self, painter, canvas, message):
        """Draw a status message overlay"""
        if not message:
            return
        
        try:
            margin = 10
            painter.setFont(QFont("Arial", 9))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            
            # Calculate text size
            metrics = painter.fontMetrics()
            text_rect = metrics.boundingRect(message)
            
            # Draw background
            bg_rect = text_rect.adjusted(-5, -2, 5, 2)
            bg_rect.translate(margin, margin + metrics.ascent())
            
            painter.fillRect(bg_rect, QColor(0, 0, 0, 120))
            
            # Draw text
            painter.drawText(margin, margin + metrics.ascent(), message)
            
        except Exception as e:
            print(f"Error drawing status message: {e}")
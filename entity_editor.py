"""
Consolidated Entity Editor for Avatar Map Editor
Structured sections with auto-save functionality and BinHex conversion
"""

import sys
import os
import math
import struct
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                           QLabel, QLineEdit, QPushButton, QCheckBox, QScrollArea, 
                           QWidget, QFrame, QGroupBox, QMessageBox, QApplication, 
                           QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette, QDoubleValidator, QIntValidator


class DecimalInput(QLineEdit):
    """Enhanced decimal input with mouse drag support"""
    changed = pyqtSignal()

    def __init__(self, parent, get_value, set_value, min_val=-math.inf, max_val=math.inf):
        super().__init__(parent)
        self.get_value = get_value
        self.set_value = set_value
        self.min_val = min_val
        self.max_val = max_val
        
        self.setValidator(QDoubleValidator(min_val, max_val, 6, self))
        self.textChanged.connect(self.on_text_changed)
        
        # Mouse drag support
        self.drag_start_x = None
        self.drag_start_value = None
        self.scaling_factor = 1.0
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_x = event.position().x()
            try:
                self.drag_start_value = self.get_value()
            except:
                self.drag_start_value = 0.0
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.drag_start_x is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.position().x() - self.drag_start_x
            
            # Scale factor based on modifiers
            scale = 0.01 if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            
            new_value = self.drag_start_value + delta * self.scaling_factor * scale
            new_value = max(self.min_val, min(self.max_val, new_value))
            
            self.setText(f"{new_value:.6f}")
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        self.drag_start_x = None
        self.drag_start_value = None
        super().mouseReleaseEvent(event)

    def update_value(self):
        try:
            val = self.get_value()
            self.blockSignals(True)
            if isinstance(val, (int, float)):
                if val != int(val):
                    self.setText(f"{val:.6f}".rstrip('0').rstrip('.'))
                else:
                    self.setText(str(int(val)))
            else:
                self.setText(str(val))
            self.blockSignals(False)
        except Exception as e:
            print(f"Error updating decimal input: {e}")
            self.setText("0")

    def on_text_changed(self, text):
        try:
            if text.strip():
                val = float(text)
                val = max(self.min_val, min(self.max_val, val))
                self.set_value(val)
                self.changed.emit()
        except ValueError:
            pass


class IntegerInput(QLineEdit):
    """Integer input with validation"""
    changed = pyqtSignal()

    def __init__(self, parent, get_value, set_value, min_val=None, max_val=None):
        super().__init__(parent)
        self.get_value = get_value
        self.set_value = set_value
        
        if min_val is not None and max_val is not None:
            self.setValidator(QIntValidator(min_val, max_val, self))
        
        self.textChanged.connect(self.on_text_changed)

    def update_value(self):
        try:
            val = self.get_value()
            self.blockSignals(True)
            self.setText(str(int(val)))
            self.blockSignals(False)
        except Exception as e:
            print(f"Error updating integer input: {e}")
            self.setText("0")

    def on_text_changed(self, text):
        try:
            if text.strip():
                val = int(text)
                self.set_value(val)
                self.changed.emit()
        except ValueError:
            pass


class StringInput(QLineEdit):
    """String input field"""
    changed = pyqtSignal()

    def __init__(self, parent, get_value, set_value):
        super().__init__(parent)
        self.get_value = get_value
        self.set_value = set_value
        self.textChanged.connect(self.on_text_changed)

    def update_value(self):
        try:
            val = self.get_value()
            self.blockSignals(True)
            self.setText(str(val) if val is not None else "")
            self.blockSignals(False)
        except Exception as e:
            print(f"Error updating string input: {e}")
            self.setText("")

    def on_text_changed(self, text):
        try:
            self.set_value(text)
            self.changed.emit()
        except Exception as e:
            print(f"Error setting string value: {e}")


class EntityEditorWindow(QDialog):
    """Entity editor window with structured sections"""
    
    def __init__(self, parent, canvas):
        super().__init__(parent)
        self.canvas = canvas
        self.current_entity = None
        self.auto_save_enabled = True
        self.auto_update_enabled = True
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self.auto_save)
        
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("Entity Editor")
        self.setMinimumSize(500, 700)
        self.resize(600, 900)
        
        # Keep window on top option
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Header with entity info and controls
        header_frame = QFrame(self)
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        
        # Entity name and type
        self.entity_name_label = QLabel("No entity selected", self)
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.entity_name_label.setFont(font)
        
        self.entity_type_label = QLabel("", self)
        self.entity_coords_label = QLabel("", self)
        
        header_layout.addWidget(self.entity_name_label)
        header_layout.addWidget(self.entity_type_label)
        header_layout.addWidget(self.entity_coords_label)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.auto_update_checkbox = QCheckBox("Auto-update", self)
        self.auto_update_checkbox.setChecked(self.auto_update_enabled)
        self.auto_update_checkbox.toggled.connect(self.toggle_auto_update)
        
        self.auto_save_checkbox = QCheckBox("Auto-save", self)
        self.auto_save_checkbox.setChecked(self.auto_save_enabled)
        self.auto_save_checkbox.toggled.connect(self.toggle_auto_save)
        
        self.show_all_fields_button = QPushButton("Show All Fields", self)
        self.show_all_fields_button.clicked.connect(self.show_all_available_fields)
        
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)
        
        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.manual_save)
        
        controls_layout.addWidget(self.auto_update_checkbox)
        controls_layout.addWidget(self.auto_save_checkbox)
        controls_layout.addWidget(self.show_all_fields_button)
        controls_layout.addStretch()
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.save_button)
        
        header_layout.addLayout(controls_layout)
        main_layout.addWidget(header_frame)
        
        # Scroll area for entity properties
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)
        
        # Status bar
        self.status_label = QLabel("Ready", self)
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        main_layout.addWidget(self.status_label)
        
    def setup_connections(self):
        """Setup signal connections"""
        # Connect to canvas selection changes
        if hasattr(self.canvas, 'entitySelected'):
            self.canvas.entitySelected.connect(self.on_entity_selected)
    
    def toggle_auto_update(self, enabled):
        """Toggle auto-update on entity selection"""
        self.auto_update_enabled = enabled
        
    def toggle_auto_save(self, enabled):
        """Toggle auto-save functionality"""
        self.auto_save_enabled = enabled
        
    def on_entity_selected(self, entity):
        """Handle entity selection from canvas"""
        if self.auto_update_enabled and entity != self.current_entity:
            self.set_entity(entity)
    
    def set_entity(self, entity):
        """Set the current entity and populate the editor"""
        if entity == self.current_entity:
            return
            
        # Save previous entity if auto-save is enabled
        if self.current_entity and self.auto_save_enabled:
            self.auto_save()
            
        self.current_entity = entity
        self.populate_fields()
        
    def populate_fields(self):
        """Populate the editor fields with entity data"""
        # Clear existing content
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        if not self.current_entity:
            self.entity_name_label.setText("No entity selected")
            self.entity_type_label.setText("")
            self.entity_coords_label.setText("")
            return
            
        entity = self.current_entity
        
        # Update header info
        self.entity_name_label.setText(f"Entity: {entity.name}")
        
        # Get entity type
        try:
            entity_type = self.canvas._determine_entity_type(entity.name)
            creature_type = self.canvas.extract_entity_creature_type(entity)
            
            type_text = f"Type: {entity_type}"
            if creature_type:
                type_text += f" | Creature: {creature_type}"
            self.entity_type_label.setText(type_text)
        except Exception as e:
            self.entity_type_label.setText("Type: Unknown")
            print(f"Error determining entity type: {e}")
        
        # Show coordinates
        self.entity_coords_label.setText(f"Position: ({entity.x:.2f}, {entity.y:.2f}, {entity.z:.2f})")
        
        # Create sections
        self.create_basic_properties_section()
        self.create_main_entity_section()
        self.create_components_section()
        
        self.status_label.setText(f"Loaded entity: {entity.name}")
    
    def create_basic_properties_section(self):
        """Create basic properties section"""
        entity = self.current_entity
        
        # Section frame
        section_frame = QGroupBox("Basic Properties", self)
        layout = QGridLayout(section_frame)
        row = 0
        
        # Entity name
        layout.addWidget(QLabel("Name:", self), row, 0)
        name_input = StringInput(
            self,
            lambda: entity.name,
            lambda val: setattr(entity, 'name', val)
        )
        name_input.changed.connect(self.schedule_auto_save)
        name_input.update_value()
        layout.addWidget(name_input, row, 1, 1, 2)
        row += 1
        
        # Position
        layout.addWidget(QLabel("Position:", self), row, 0)
        pos_widget = self.create_position_widget(entity)
        layout.addWidget(pos_widget, row, 1, 1, 2)
        
        self.content_layout.addWidget(section_frame)
    
    def create_position_widget(self, entity):
        """Create position input widget"""
        pos_widget = QWidget(self)
        pos_layout = QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        
        # X coordinate
        x_input = DecimalInput(
            self,
            lambda: entity.x,
            lambda val: self.set_position_component(entity, 'x', val)
        )
        x_input.changed.connect(self.on_position_changed)
        x_input.update_value()
        
        # Y coordinate
        y_input = DecimalInput(
            self,
            lambda: entity.y,
            lambda val: self.set_position_component(entity, 'y', val)
        )
        y_input.changed.connect(self.on_position_changed)
        y_input.update_value()
        
        # Z coordinate
        z_input = DecimalInput(
            self,
            lambda: entity.z,
            lambda val: self.set_position_component(entity, 'z', val)
        )
        z_input.changed.connect(self.on_position_changed)
        z_input.update_value()
        
        pos_layout.addWidget(QLabel("X:", self))
        pos_layout.addWidget(x_input)
        pos_layout.addWidget(QLabel("Y:", self))
        pos_layout.addWidget(y_input)
        pos_layout.addWidget(QLabel("Z:", self))
        pos_layout.addWidget(z_input)
        pos_layout.addStretch()
        
        return pos_widget
    
    def create_main_entity_section(self):
        """Create main entity properties section"""
        entity = self.current_entity
        
        # Section frame
        section_frame = QGroupBox("Main Entity Properties", self)
        layout = QGridLayout(section_frame)
        
        if not hasattr(entity, 'xml_element') or not entity.xml_element:
            no_xml_label = QLabel("No XML data available", self)
            no_xml_label.setStyleSheet("color: #666666; font-style: italic;")
            layout.addWidget(no_xml_label, 0, 0, 1, 3)
            self.content_layout.addWidget(section_frame)
            return
        
        # Main entity fields
        main_fields = [
            ("tplCreatureType", "Creature Type"),
            ("hidName", "Entity Name"),
            ("disEntityId", "Entity ID"),
            ("hidResourceCount", "Resource Count"),
            ("hidPos", "Position (XML)"),
            ("hidAngles", "Rotation"),
            ("hidPos_precise", "Precise Position"),
        ]
        
        row = 0
        for field_name, display_name in main_fields:
            if self.add_xml_field(layout, row, field_name, display_name):
                row += 1
            else:
                # Show placeholder
                label = QLabel(f"{display_name}:", self)
                label.setStyleSheet("color: #999999;")
                placeholder = QLabel("(not found)", self)
                placeholder.setStyleSheet("color: #999999; font-style: italic;")
                layout.addWidget(label, row, 0)
                layout.addWidget(placeholder, row, 1, 1, 2)
                row += 1
        
        self.content_layout.addWidget(section_frame)
    
    def create_components_section(self):
        """Create components section"""
        entity = self.current_entity
        
        # Section frame
        section_frame = QGroupBox("Components", self)
        layout = QVBoxLayout(section_frame)
        
        if not hasattr(entity, 'xml_element') or not entity.xml_element:
            no_xml_label = QLabel("No XML data available", self)
            no_xml_label.setStyleSheet("color: #666666; font-style: italic;")
            layout.addWidget(no_xml_label)
            self.content_layout.addWidget(section_frame)
            return
        
        # Look for Components object
        components = entity.xml_element.find(".//object[@name='Components']")
        if components is None:
            no_comp_label = QLabel("No Components found", self)
            no_comp_label.setStyleSheet("color: #666666; font-style: italic;")
            layout.addWidget(no_comp_label)
            self.content_layout.addWidget(section_frame)
            return
        
        # Create component subsections
        self.add_graphic_component(layout, components)
        self.add_vehicle_physics_component(layout, components)
        self.add_vehicle_component(layout, components)
        self.add_event_component(layout, components)
        
        self.content_layout.addWidget(section_frame)
    
    def add_graphic_component(self, layout, components):
        """Add CGraphicComponent fields"""
        graphic_comp = components.find(".//object[@name='CGraphicComponent']")
        if graphic_comp is None:
            return
        
        # Subsection
        sub_frame = QGroupBox("CGraphicComponent", self)
        sub_layout = QGridLayout(sub_frame)
        
        graphic_fields = [
            ("bAllowCullBySize", "Allow Cull By Size"),
            ("hidSkyOcclusion0", "Sky Occlusion 0"),
            ("hidSkyOcclusion2", "Sky Occlusion 2"),
            ("hidGroundColor", "Ground Color"),
            ("hidHasAmbientValues", "Has Ambient Values"),
        ]
        
        row = 0
        for field_name, display_name in graphic_fields:
            field_elem = graphic_comp.find(f".//field[@name='{field_name}']")
            if field_elem is not None:
                if self.add_component_field(sub_layout, row, field_elem, display_name):
                    row += 1
            else:
                # Placeholder
                label = QLabel(f"{display_name}:", self)
                label.setStyleSheet("color: #999999;")
                placeholder = QLabel("(not found)", self)
                placeholder.setStyleSheet("color: #999999; font-style: italic;")
                sub_layout.addWidget(label, row, 0)
                sub_layout.addWidget(placeholder, row, 1, 1, 2)
                row += 1
        
        layout.addWidget(sub_frame)
    
    def add_vehicle_physics_component(self, layout, components):
        """Add CVehicleWheeledPhysComponent fields"""
        vehicle_phys = components.find(".//object[@name='CVehicleWheeledPhysComponent']")
        if vehicle_phys is None:
            return
        
        # Subsection
        sub_frame = QGroupBox("CVehicleWheeledPhysComponent", self)
        sub_layout = QVBoxLayout(sub_frame)
        
        # Force PPU field
        wheeled_params = vehicle_phys.find(".//object[@name='WheeledParams']")
        if wheeled_params is not None:
            force_ppu_field = wheeled_params.find(".//field[@name='bForcePPU']")
            if force_ppu_field is not None:
                ppu_widget = QWidget(self)
                ppu_layout = QGridLayout(ppu_widget)
                if self.add_component_field(ppu_layout, 0, force_ppu_field, "Force PPU"):
                    sub_layout.addWidget(ppu_widget)
        
        # Wheel primitives
        wheel_primitives = vehicle_phys.findall(".//object[@name='hidPrimitive']")
        for i, primitive in enumerate(wheel_primitives):
            part = primitive.find(".//object[@name='hidPart']")
            if part is not None:
                wheel_frame = QGroupBox(f"Wheel {i+1}", self)
                wheel_layout = QGridLayout(wheel_frame)
                
                wheel_fields = [
                    ("hidRigidbodyIndex", "Rigidbody Index"),
                    ("hidGraphicIndex", "Graphic Index"),
                    ("text_hidRigidbodyName", "Rigidbody Name"),
                    ("hidRigidbodyName", "Rigidbody Name (Hash)"),
                    ("hidPartId", "Part ID"),
                ]
                
                wheel_row = 0
                for field_name, display_name in wheel_fields:
                    field_elem = part.find(f".//field[@name='{field_name}']")
                    if field_elem is not None:
                        if self.add_component_field(wheel_layout, wheel_row, field_elem, display_name):
                            wheel_row += 1
                
                sub_layout.addWidget(wheel_frame)
        
        layout.addWidget(sub_frame)
    
    def add_vehicle_component(self, layout, components):
        """Add CVehicle fields"""
        vehicle_comp = components.find(".//object[@name='CVehicle']")
        if vehicle_comp is None:
            return
        
        # Subsection
        sub_frame = QGroupBox("CVehicle", self)
        sub_layout = QGridLayout(sub_frame)
        
        row = 0
        
        # POV section
        pov = vehicle_comp.find(".//object[@name='POV']")
        if pov is not None:
            vector_q0 = pov.find(".//field[@name='vectorQ0']")
            if vector_q0 is not None:
                if self.add_component_field(sub_layout, row, vector_q0, "Vector Q0"):
                    row += 1
        
        # Leaning section
        leaning = vehicle_comp.find(".//object[@name='Leaning']")
        if leaning is not None:
            camera_rot = leaning.find(".//field[@name='fCameraRotationFactor']")
            if camera_rot is not None:
                if self.add_component_field(sub_layout, row, camera_rot, "Camera Rotation Factor"):
                    row += 1
        
        layout.addWidget(sub_frame)
    
    def add_event_component(self, layout, components):
        """Add CEventComponent"""
        event_comp = components.find(".//object[@name='CEventComponent']")
        if event_comp is not None:
            sub_frame = QGroupBox("CEventComponent", self)
            sub_layout = QVBoxLayout(sub_frame)
            
            event_label = QLabel("Event component present", self)
            event_label.setStyleSheet("color: #666666; font-style: italic;")
            sub_layout.addWidget(event_label)
            
            layout.addWidget(sub_frame)
    
    def add_xml_field(self, layout, row, field_name, display_name):
        """Add an XML field to the layout"""
        entity = self.current_entity
        if not entity.xml_element:
            return False
            
        # Look for field element
        field_elem = entity.xml_element.find(f".//field[@name='{field_name}']")
        if field_elem is None:
            return False
        
        # Create label
        label = QLabel(f"{display_name}:", self)
        layout.addWidget(label, row, 0)
        
        # Create input widget
        input_widget = self.create_field_input_widget(field_elem, field_name)
        layout.addWidget(input_widget, row, 1, 1, 2)
        
        return True
    
    def add_component_field(self, layout, row, field_elem, display_name):
        """Add a component field to the layout"""
        if field_elem is None:
            return False
        
        # Create label
        label = QLabel(f"{display_name}:", self)
        layout.addWidget(label, row, 0)
        
        # Create input widget
        field_name = field_elem.get('name', '')
        input_widget = self.create_field_input_widget(field_elem, field_name)
        layout.addWidget(input_widget, row, 1, 1, 2)
        
        return True
    
    def create_field_input_widget(self, field_elem, field_name):
        """Create appropriate input widget for a field"""
        value_attr = self.get_value_attribute(field_elem)
        
        # Determine field type based on name and attributes
        if field_name in ["hidAngles", "vectorQ0", "hidPos", "hidPos_precise"]:
            # Vector3 fields
            widget = self.create_vector3_field(field_elem, value_attr)
            if field_name in ["hidPos", "hidPos_precise"]:
                widget.setEnabled(False)  # Read-only for position fields
            return widget
        elif field_name in ["disEntityId", "hidResourceCount", "hidRigidbodyIndex", "hidGraphicIndex", "hidPartId"]:
            # Integer fields
            return self.create_integer_field(field_elem, value_attr)
        elif field_name in ["hidSkyOcclusion0", "hidSkyOcclusion2", "hidGroundColor", "hidRigidbodyName"]:
            # Hash32 fields
            return self.create_hash32_field(field_elem, value_attr)
        elif field_name in ["bAllowCullBySize", "bForcePPU", "hidHasAmbientValues"]:
            # Boolean fields
            return self.create_boolean_field(field_elem, value_attr)
        elif field_name in ["fCameraRotationFactor"]:
            # Float fields
            return self.create_float_field(field_elem, value_attr)
        else:
            # String fields (default)
            return self.create_string_field(field_elem, value_attr)
    
    def create_hash32_field(self, field_elem, value_attr):
        """Create a Hash32 input field"""
        input_field = IntegerInput(
            self,
            lambda: int(field_elem.get(value_attr) or "0"),
            lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, str(val), 'hash32')
        )
        input_field.changed.connect(self.schedule_auto_save)
        input_field.update_value()
        return input_field

    def create_boolean_field(self, field_elem, value_attr):
        """Create a boolean checkbox field"""
        checkbox = QCheckBox(self)
        
        def get_bool_value():
            val = field_elem.get(value_attr)
            if val is None:
                binhex = field_elem.text or ""
                return binhex.strip().upper() == "01"
            return val.lower() in ['true', '1', 'yes']
        
        def set_bool_value(checked):
            str_val = "True" if checked else "False"
            field_elem.set(value_attr, str_val)
            binhex_val = "01" if checked else "00"
            field_elem.text = binhex_val
            self.schedule_auto_save()
        
        checkbox.setChecked(get_bool_value())
        checkbox.toggled.connect(set_bool_value)
        
        return checkbox

    def create_integer_field(self, field_elem, value_attr):
        """Create an integer input field"""
        if value_attr == 'value-Id64':
            # 64-bit ID field - use string input for large IDs
            input_field = StringInput(
                self,
                lambda: field_elem.get(value_attr) or "0",
                lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, val, 'id64')
            )
        else:
            # Regular 32-bit integer
            input_field = IntegerInput(
                self,
                lambda: int(field_elem.get(value_attr) or "0"),
                lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, str(val), 'int32')
            )
        
        input_field.changed.connect(self.schedule_auto_save)
        input_field.update_value()
        return input_field

    def create_float_field(self, field_elem, value_attr):
        """Create a float input field"""
        input_field = DecimalInput(
            self,
            lambda: float(field_elem.get(value_attr) or "0.0"),
            lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, str(val), 'float32')
        )
        input_field.changed.connect(self.schedule_auto_save)
        input_field.update_value()
        return input_field

    def create_string_field(self, field_elem, value_attr):
        """Create a string input field"""
        input_field = StringInput(
            self,
            lambda: field_elem.get(value_attr) or "",
            lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, val, 'string')
        )
        input_field.changed.connect(self.schedule_auto_save)
        input_field.update_value()
        return input_field
    
    def create_vector3_field(self, field_elem, value_attr):
        """Create a Vector3 input field"""
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Parse current Vector3 value
        vector_str = field_elem.get(value_attr) or "0,0,0"
        try:
            x, y, z = map(float, vector_str.split(','))
        except:
            x, y, z = 0.0, 0.0, 0.0
        
        # Create individual inputs for X, Y, Z
        for i, (axis, value) in enumerate([('X', x), ('Y', y), ('Z', z)]):
            label = QLabel(f"{axis}:", self)
            label.setMinimumWidth(15)
            
            input_field = DecimalInput(
                self,
                lambda idx=i: self.get_vector_component(field_elem, value_attr, idx),
                lambda val, idx=i: self.set_vector_component(field_elem, value_attr, idx, val)
            )
            input_field.changed.connect(self.schedule_auto_save)
            input_field.update_value()
            
            layout.addWidget(label)
            layout.addWidget(input_field)
        
        layout.addStretch()
        return widget
    
    def get_value_attribute(self, field_elem):
        """Get the appropriate value attribute from a field element"""
        for attr in ['value-String', 'value-Vector3', 'value-Int32', 'value-Id64', 
                     'value-Float32', 'value-Hash32', 'value-Boolean', 'value']:
            if field_elem.get(attr) is not None:
                return attr
        return 'value-String'
    
    def get_vector_component(self, field_elem, value_attr, index):
        """Get a specific component (X, Y, Z) from a Vector3 field"""
        vector_str = field_elem.get(value_attr) or "0,0,0"
        try:
            components = list(map(float, vector_str.split(',')))
            return components[index] if index < len(components) else 0.0
        except:
            return 0.0
    
    def set_vector_component(self, field_elem, value_attr, index, value):
        """Set a specific component (X, Y, Z) in a Vector3 field"""
        vector_str = field_elem.get(value_attr) or "0,0,0"
        try:
            components = list(map(float, vector_str.split(',')))
            while len(components) <= index:
                components.append(0.0)
            components[index] = value
            new_vector_str = ",".join(map(str, components))
            self.update_xml_field_with_binhex(field_elem, value_attr, new_vector_str, 'vector3')
        except Exception as e:
            print(f"Error setting vector component: {e}")
    
    def update_xml_field_with_binhex(self, field_elem, value_attr, value, data_type):
        """Update XML field with both text and BinHex values"""
        try:
            # Update the text value
            field_elem.set(value_attr, value)
            
            # Update the BinHex value
            if data_type == 'string':
                binhex = value.encode('utf-8').hex().upper() + "00"  # Null-terminated
            elif data_type == 'int32':
                binhex = struct.pack('<I', int(value)).hex().upper()
            elif data_type == 'id64':
                binhex = struct.pack('<Q', int(value)).hex().upper()
            elif data_type == 'float32':
                binhex = struct.pack('<f', float(value)).hex().upper()
            elif data_type == 'vector3':
                components = list(map(float, value.split(',')))
                while len(components) < 3:
                    components.append(0.0)
                binhex = struct.pack('<fff', *components[:3]).hex().upper()
            elif data_type == 'hash32':
                binhex = struct.pack('<I', int(value)).hex().upper()
            elif data_type == 'boolean':
                binhex = "01" if value.lower() in ['true', '1', 'yes'] else "00"
            else:
                binhex = value.encode('utf-8').hex().upper() + "00"
            
            field_elem.text = binhex
            
        except Exception as e:
            print(f"Error updating XML field with BinHex: {e}")
    
    def set_position_component(self, entity, component, value):
        """Set position component and update entity"""
        setattr(entity, component, value)
    
    def on_position_changed(self):
        """Handle position changes"""
        if not self.current_entity:
            return
            
        try:
            # Update XML coordinates
            self.canvas.update_entity_xml(self.current_entity)
            
            # Update canvas display
            self.canvas.update()
            
            # Update coordinate display
            entity = self.current_entity
            self.entity_coords_label.setText(f"Position: ({entity.x:.2f}, {entity.y:.2f}, {entity.z:.2f})")
            
            # Schedule auto-save
            self.schedule_auto_save()
        except Exception as e:
            print(f"Error handling position change: {e}")
    
    def show_all_available_fields(self):
        """Show all available fields in the current entity for debugging"""
        if not self.current_entity or not self.current_entity.xml_element:
            QMessageBox.information(self, "Debug", "No entity selected or no XML data available.")
            return
        
        # Find all field elements
        all_fields = self.current_entity.xml_element.findall(".//field[@name]")
        
        field_info = []
        for field in all_fields:
            name = field.get('name', 'Unknown')
            field_type = field.get('type', 'Unknown')
            
            # Get value from different possible attributes
            value = None
            for attr in ['value-String', 'value-Vector3', 'value-Int32', 'value-Id64', 
                        'value-Float32', 'value-Hash32', 'value-Boolean', 'value']:
                if field.get(attr) is not None:
                    value = field.get(attr)
                    break
            
            if value is None:
                value = field.text or "No value"
            
            field_info.append(f"{name} ({field_type}): {value}")
        
        # Show in message box
        if field_info:
            msg = f"Found {len(field_info)} fields:\n\n" + "\n".join(field_info[:20])
            if len(field_info) > 20:
                msg += f"\n\n... and {len(field_info) - 20} more fields"
        else:
            msg = "No fields found in XML structure."
        
        QMessageBox.information(self, "All Available Fields", msg)

    def schedule_auto_save(self):
        """Schedule an auto-save"""
        if self.auto_save_enabled:
            self.auto_save_timer.stop()
            self.auto_save_timer.start(1000)  # Auto-save after 1 second of inactivity
            self.status_label.setText("Changes pending...")
    
    def auto_save(self):
        """Perform auto-save"""
        if not self.current_entity:
            return
            
        try:
            self.canvas._auto_save_entity_changes(self.current_entity)
            from PyQt6.QtCore import QTime
            current_time = QTime.currentTime().toString("hh:mm:ss")
            self.status_label.setText(f"Auto-saved at {current_time}")
        except Exception as e:
            self.status_label.setText(f"Auto-save failed: {str(e)}")
            print(f"Auto-save error: {e}")
    
    def manual_save(self):
        """Perform manual save"""
        if not self.current_entity:
            QMessageBox.information(self, "Save", "No entity to save.")
            return
            
        try:
            self.canvas._auto_save_entity_changes(self.current_entity)
            self.status_label.setText("Manually saved successfully")
            QMessageBox.information(self, "Save", "Entity saved successfully!")
        except Exception as e:
            error_msg = f"Save failed: {str(e)}"
            self.status_label.setText(error_msg)
            QMessageBox.critical(self, "Save Error", error_msg)
    
    def refresh_data(self):
        """Refresh the entity data"""
        if self.current_entity:
            entity = self.current_entity
            self.current_entity = None  # Force refresh
            self.set_entity(entity)
    
    def closeEvent(self, event):
        """Handle window closing"""
        if self.current_entity and self.auto_save_enabled:
            self.auto_save()
        super().closeEvent(event)
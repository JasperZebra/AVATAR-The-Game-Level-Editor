"""
Enhanced Entity Editor for Avatar Map Editor
Improved UI with comprehensive field display and better organization
"""

import sys
import os
import math
import struct
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
                           QLabel, QLineEdit, QPushButton, QCheckBox, QScrollArea, 
                           QWidget, QFrame, QGroupBox, QMessageBox, QApplication, 
                           QSpacerItem, QSizePolicy, QTabWidget, QTextEdit,
                           QSplitter, QTreeWidget, QTreeWidgetItem, QComboBox)
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
    """Enhanced Entity editor window with comprehensive field display"""
    
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
        """Setup the enhanced user interface"""
        print("=== DEBUG: Starting setup_ui ===")
        print(f"Children before setup: {[child.__class__.__name__ for child in self.children()]}")
        
        self.setWindowTitle("Enhanced Entity Editor")
        self.setMinimumSize(800, 900)
        self.resize(1200, 1000)
        
        # Keep window on top option
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        
        print(f"Children after window setup: {[child.__class__.__name__ for child in self.children()]}")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        print(f"Children after main layout: {[child.__class__.__name__ for child in self.children()]}")
        
        # Header with entity info and controls
        print("=== Creating header ===")
        self.create_header(main_layout)
        print(f"Children after header: {[child.__class__.__name__ for child in self.children()]}")
        
        # Main content with tabs
        print("=== Creating main content ===")
        self.create_main_content(main_layout)
        print(f"Children after main content: {[child.__class__.__name__ for child in self.children()]}")
        
        print("=== DEBUG: Finished setup_ui ===")
        
        # Check for any widgets that might be added to the main layout
        print(f"Main layout item count: {main_layout.count()}")
        for i in range(main_layout.count()):
            item = main_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                print(f"Layout item {i}: {widget.__class__.__name__} - {getattr(widget, 'objectName', 'no name')()}")
                # Check if it's a QLabel with text
                if isinstance(widget, QLabel):
                    print(f"  Label text: '{widget.text()}'")
                elif hasattr(widget, 'children'):
                    print(f"  Widget children: {[child.__class__.__name__ for child in widget.children()]}")

    def create_header(self, main_layout):
        """Create header section"""
        print("=== DEBUG: Creating header frame ===")
        header_frame = QFrame(self)
        header_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        
        # Entity info section
        info_layout = QHBoxLayout()
        
        # Left side - Entity details
        entity_info_layout = QVBoxLayout()
        
        print("=== Creating entity labels ===")
        self.entity_name_label = QLabel("No entity selected", self)
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.entity_name_label.setFont(font)
        
        self.entity_type_label = QLabel("", self)
        self.entity_coords_label = QLabel("", self)
        self.entity_id_label = QLabel("", self)
        
        entity_info_layout.addWidget(self.entity_name_label)
        entity_info_layout.addWidget(self.entity_type_label)
        entity_info_layout.addWidget(self.entity_coords_label)
        entity_info_layout.addWidget(self.entity_id_label)
        
        info_layout.addLayout(entity_info_layout)
        info_layout.addStretch()
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        print("=== Creating control widgets ===")
        self.auto_update_checkbox = QCheckBox("Auto-update", self)
        self.auto_update_checkbox.setChecked(self.auto_update_enabled)
        self.auto_update_checkbox.toggled.connect(self.toggle_auto_update)
        
        self.auto_save_checkbox = QCheckBox("Auto-save", self)
        self.auto_save_checkbox.setChecked(self.auto_save_enabled)
        self.auto_save_checkbox.toggled.connect(self.toggle_auto_save)
        
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_data)
        
        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.manual_save)
        
        controls_layout.addWidget(self.auto_update_checkbox)
        controls_layout.addWidget(self.auto_save_checkbox)
        controls_layout.addStretch()
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.save_button)
        
        # Add status label to the controls layout
        print("=== Creating status label ===")
        self.status_label = QLabel("Ready", self)
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        controls_layout.addWidget(self.status_label)
        
        header_layout.addLayout(info_layout)
        header_layout.addLayout(controls_layout)
        
        print("=== Adding header frame to main layout ===")
        main_layout.addWidget(header_frame)
        print(f"Header frame children: {[child.__class__.__name__ for child in header_frame.children()]}")

    def create_main_content(self, main_layout):
        """Create main content area with unified view"""
        print("=== DEBUG: Creating main content ===")
        # Scroll area for all content
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(self.scroll_area)
        print("=== Main content created ===")

    def setup_connections(self):
        """Setup signal connections"""
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
        """Set the current entity and populate all views"""
        print(f"=== DEBUG: set_entity called with {entity.name if entity else 'None'} ===")
        
        if entity == self.current_entity:
            print("Entity unchanged, returning early")
            return
            
        # Save previous entity if auto-save is enabled
        if self.current_entity and self.auto_save_enabled:
            self.auto_save()
            
        self.current_entity = entity
        print(f"Set current_entity to: {entity.name if entity else 'None'}")
        
        self.populate_all_views()

    def populate_all_views(self):
        """Populate unified view with all entity data"""
        print("=== DEBUG: populate_all_views called ===")
        
        # Clear existing content
        print(f"Content layout item count before clear: {self.content_layout.count()}")
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i).widget()
            if child:
                print(f"Removing child widget: {child.__class__.__name__}")
                child.setParent(None)
        
        if not self.current_entity:
            print("No current entity, clearing views")
            self.clear_all_views()
            return
            
        entity = self.current_entity
        print(f"Populating views for entity: {entity.name}")
        
        # Update header info
        print("=== Updating header info ===")
        self.update_header_info(entity)
        
        # Create all sections in order
        print("=== Creating basic properties section ===")
        self.create_basic_properties_section()
        print(f"Content layout item count after basic properties: {self.content_layout.count()}")
        
        if hasattr(entity, 'xml_element') and entity.xml_element:
            print("=== Creating main entity section ===")
            self.create_main_entity_section()
            print(f"Content layout item count after main entity: {self.content_layout.count()}")
            
            print("=== Creating vehicle sections ===")
            self.create_vehicle_sections()
            print(f"Content layout item count after vehicle: {self.content_layout.count()}")
            
            print("=== Creating graphics section ===")
            self.create_graphics_section()
            print(f"Content layout item count after graphics: {self.content_layout.count()}")
            
            print("=== Creating physics section ===")
            self.create_physics_section()
            print(f"Content layout item count after physics: {self.content_layout.count()}")
            
            print("=== Creating other components section ===")
            self.create_other_components_section()
            print(f"Content layout item count after other components: {self.content_layout.count()}")
            
            # Add detailed components view at the end
            print("=== Creating detailed components section ===")
            self.create_detailed_components_section()
            print(f"Content layout item count after detailed: {self.content_layout.count()}")
        
        self.status_label.setText(f"Loaded entity: {entity.name}")
        print("=== DEBUG: populate_all_views completed ===")

    def create_basic_properties_section(self):
        """Create basic properties section"""
        print("=== DEBUG: create_basic_properties_section called ===")
        entity = self.current_entity
        
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
        
        print(f"Adding basic properties section to content layout")
        self.content_layout.addWidget(section_frame)
        print(f"Basic properties section added")

    def clear_all_views(self):
        """Clear all views when no entity is selected"""
        print("=== DEBUG: clear_all_views called ===")
        
        self.entity_name_label.setText("No entity selected")
        self.entity_type_label.setText("")
        self.entity_coords_label.setText("")
        self.entity_id_label.setText("")
        
        # Clear content
        print(f"Content layout item count before clear: {self.content_layout.count()}")
        for i in reversed(range(self.content_layout.count())):
            child = self.content_layout.itemAt(i).widget()
            if child:
                print(f"Clearing child widget: {child.__class__.__name__}")
                child.setParent(None)
        print("All views cleared")        

    def update_header_info(self, entity):
        """Update header information display"""
        self.entity_name_label.setText(f"Entity: {entity.name}")
        
        # Get entity type and creature type
        try:
            entity_type = "Unknown"
            if hasattr(self.canvas, '_determine_entity_type'):
                entity_type = self.canvas._determine_entity_type(entity.name)
            elif hasattr(self.canvas, 'determine_entity_type'):
                entity_type = self.canvas.determine_entity_type(entity.name)
            
            creature_type = None
            if hasattr(self.canvas, 'extract_entity_creature_type'):
                creature_type = self.canvas.extract_entity_creature_type(entity)
            
            type_text = f"Type: {entity_type}"
            if creature_type:
                type_text += f" | Creature: {creature_type}"
            self.entity_type_label.setText(type_text)
        except Exception as e:
            self.entity_type_label.setText("Type: Unknown")
            print(f"Error determining entity type: {e}")
        
        # Show coordinates
        self.entity_coords_label.setText(f"Position: ({entity.x:.3f}, {entity.y:.3f}, {entity.z:.3f})")
        
        # Show entity ID if available
        if hasattr(entity, 'xml_element') and entity.xml_element:
            id_field = entity.xml_element.find(".//field[@name='disEntityId']")
            if id_field is not None:
                entity_id = id_field.get('value-Id64', 'Unknown')
                self.entity_id_label.setText(f"Entity ID: {entity_id}")
            else:
                self.entity_id_label.setText("Entity ID: Not found")
        else:
            self.entity_id_label.setText("Entity ID: No XML data")
            
    def create_position_widget(self, entity):
        """Create enhanced position input widget"""
        pos_widget = QWidget(self)
        pos_layout = QHBoxLayout(pos_widget)
        pos_layout.setContentsMargins(0, 0, 0, 0)
        
        # X coordinate
        pos_layout.addWidget(QLabel("X:", self))
        x_input = DecimalInput(
            self,
            lambda: entity.x,
            lambda val: self.set_position_component(entity, 'x', val)
        )
        x_input.changed.connect(self.on_position_changed)
        x_input.update_value()
        pos_layout.addWidget(x_input)
        
        # Y coordinate
        pos_layout.addWidget(QLabel("Y:", self))
        y_input = DecimalInput(
            self,
            lambda: entity.y,
            lambda val: self.set_position_component(entity, 'y', val)
        )
        y_input.changed.connect(self.on_position_changed)
        y_input.update_value()
        pos_layout.addWidget(y_input)
        
        # Z coordinate
        pos_layout.addWidget(QLabel("Z:", self))
        z_input = DecimalInput(
            self,
            lambda: entity.z,
            lambda val: self.set_position_component(entity, 'z', val)
        )
        z_input.changed.connect(self.on_position_changed)
        z_input.update_value()
        pos_layout.addWidget(z_input)
        
        pos_layout.addStretch()
        return pos_widget
    
    def create_main_entity_section(self):
        """Create main entity properties section"""
        entity = self.current_entity
        
        section_frame = QGroupBox("Main Entity Properties", self)
        layout = QGridLayout(section_frame)
        
        # Main entity fields
        main_fields = [
            ("tplCreatureType", "Creature Type", "String"),
            ("hidName", "Entity Name", "String"),
            ("disEntityId", "Entity ID", "Id64"),
            ("hidResourceCount", "Resource Count", "Int32"),
            ("hidPos", "Position (XML)", "Vector3"),
            ("hidAngles", "Rotation", "Vector3"),
            ("hidPos_precise", "Precise Position", "Vector3"),
            ("hidScale", "Scale", "Hash32"),
            ("hidConstEntity", "Constant Entity", "Boolean"),
        ]
        
        row = 0
        for field_name, display_name, field_type in main_fields:
            # Special handling for hidAngles field
            if field_name == "hidAngles":
                # Check if the field exists in XML
                if entity.xml_element and entity.xml_element.find(".//field[@name='hidAngles']") is not None:
                    # Field exists, add it normally
                    if self.add_xml_field_to_layout(layout, row, field_name, display_name, field_type):
                        row += 1
                else:
                    # Field doesn't exist, add the button instead
                    layout.addWidget(QLabel("Rotation:", self), row, 0)
                    add_rotation_button = QPushButton("Add Rotation Field", self)
                    add_rotation_button.clicked.connect(self.add_rotation_field)
                    layout.addWidget(add_rotation_button, row, 1, 1, 2)
                    row += 1
            else:
                # Normal field handling
                if self.add_xml_field_to_layout(layout, row, field_name, display_name, field_type):
                    row += 1
        
        if row > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_vehicle_sections(self):
        """Create vehicle-specific sections"""
        entity = self.current_entity
        
        # Look for vehicle components
        if not entity.xml_element:
            return
            
        components = entity.xml_element.find(".//object[@name='Components']")
        if components is None:
            return
            
        # Vehicle physics component
        self.create_vehicle_physics_section(components)
        
        # Vehicle component (CVehicle or similar)
        vehicle_comps = components.findall(".//object")
        for comp in vehicle_comps:
            comp_name = comp.get('name', '')
            if 'Vehicle' in comp_name and comp_name != 'CVehicleWheeledPhysComponent':
                self.create_vehicle_component_section(comp, comp_name)
    
    def create_vehicle_physics_section(self, components):
        """Create vehicle physics component section"""
        vehicle_phys = components.find(".//object[@name='CVehicleWheeledPhysComponent']")
        if vehicle_phys is None:
            return
        
        section_frame = QGroupBox("Vehicle Physics Component", self)
        section_layout = QVBoxLayout(section_frame)
        
        # Force PPU field
        wheeled_params = vehicle_phys.find(".//object[@name='WheeledParams']")
        if wheeled_params is not None:
            force_ppu_field = wheeled_params.find(".//field[@name='bForcePPU']")
            if force_ppu_field is not None:
                ppu_widget = QWidget(self)
                ppu_layout = QGridLayout(ppu_widget)
                if self.add_component_field_to_layout(ppu_layout, 0, force_ppu_field, "Force PPU"):
                    section_layout.addWidget(ppu_widget)
        
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
                        if self.add_component_field_to_layout(wheel_layout, wheel_row, field_elem, display_name):
                            wheel_row += 1
                
                if wheel_row > 0:
                    section_layout.addWidget(wheel_frame)
        
        if section_layout.count() > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_vehicle_component_section(self, component, component_name):
        """Create section for vehicle component"""
        section_frame = QGroupBox(f"{component_name}", self)
        section_layout = QVBoxLayout(section_frame)
        
        # POV section
        pov = component.find(".//object[@name='POV']")
        if pov is not None:
            pov_frame = QGroupBox("POV Settings", self)
            pov_layout = QGridLayout(pov_frame)
            pov_row = 0
            
            pov_fields = pov.findall(".//field[@name]")
            for field in pov_fields:
                field_name = field.get('name', '')
                display_name = field_name.replace('vector', 'Vector ').replace('Q', ' Q')
                if self.add_component_field_to_layout(pov_layout, pov_row, field, display_name):
                    pov_row += 1
            
            if pov_row > 0:
                section_layout.addWidget(pov_frame)
        
        # Leaning section
        leaning = component.find(".//object[@name='Leaning']")
        if leaning is not None:
            leaning_frame = QGroupBox("Leaning Settings", self)
            leaning_layout = QGridLayout(leaning_frame)
            leaning_row = 0
            
            leaning_fields = leaning.findall(".//field[@name]")
            for field in leaning_fields:
                field_name = field.get('name', '')
                display_name = field_name.replace('f', '').replace('Camera', 'Camera ').replace('Rotation', ' Rotation').replace('Factor', ' Factor')
                if self.add_component_field_to_layout(leaning_layout, leaning_row, field, display_name):
                    leaning_row += 1
            
            if leaning_row > 0:
                section_layout.addWidget(leaning_frame)
        
        # Other subsections
        for obj in component.findall(".//object[@name]"):
            obj_name = obj.get('name', '')
            if obj_name not in ['POV', 'Leaning', 'hidLinks']:
                self.create_generic_object_section(section_layout, obj, obj_name)
        
        if section_layout.count() > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_graphics_section(self):
        """Create graphics component section"""
        entity = self.current_entity
        components = entity.xml_element.find(".//object[@name='Components']")
        if components is None:
            return
            
        graphic_comp = components.find(".//object[@name='CGraphicComponent']")
        if graphic_comp is None:
            return
        
        section_frame = QGroupBox("Graphics Component", self)
        section_layout = QVBoxLayout(section_frame)
        
        # Main graphics fields
        main_graphics_frame = QGroupBox("Main Graphics Settings", self)
        main_graphics_layout = QGridLayout(main_graphics_frame)
        
        graphics_fields = [
            ("hidComponentClassName", "Component Class Name"),
            ("bCastShadow", "Cast Shadow"),
            ("bReceiveShadow", "Receive Shadow"),
            ("bCastAmbientShadow", "Cast Ambient Shadow"),
            ("bAllowCullBySize", "Allow Cull By Size"),
            ("olgLightGroup", "Light Group"),
            ("bShowInReflection", "Show In Reflection"),
            ("bAlwaysShowInReflection", "Always Show In Reflection"),
            ("agAmbientGroup", "Ambient Group"),
            ("bBehaveLikeAPickup", "Behave Like Pickup"),
            ("hidIndex", "Index"),
            ("text_objModel", "Object Model Path"),
            ("objModel", "Object Model Hash"),
            ("hidMeshName", "Mesh Name"),
        ]
        
        row = 0
        for field_name, display_name in graphics_fields:
            field_elem = graphic_comp.find(f".//field[@name='{field_name}']")
            if field_elem is not None:
                if self.add_component_field_to_layout(main_graphics_layout, row, field_elem, display_name):
                    row += 1
        
        if row > 0:
            section_layout.addWidget(main_graphics_frame)
        
        # Sky occlusion fields
        occlusion_frame = QGroupBox("Sky Occlusion", self)
        occlusion_layout = QGridLayout(occlusion_frame)
        
        occlusion_fields = [
            ("hidSkyOcclusion0", "Sky Occlusion 0"),
            ("hidSkyOcclusion1", "Sky Occlusion 1"),
            ("hidSkyOcclusion2", "Sky Occlusion 2"),
            ("hidSkyOcclusion3", "Sky Occlusion 3"),
            ("hidGroundColor", "Ground Color"),
            ("hidHasAmbientValues", "Has Ambient Values"),
        ]
        
        occlusion_row = 0
        for field_name, display_name in occlusion_fields:
            field_elem = graphic_comp.find(f".//field[@name='{field_name}']")
            if field_elem is not None:
                if self.add_component_field_to_layout(occlusion_layout, occlusion_row, field_elem, display_name):
                    occlusion_row += 1
        
        if occlusion_row > 0:
            section_layout.addWidget(occlusion_frame)
        
        if section_layout.count() > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_physics_section(self):
        """Create physics component section"""
        entity = self.current_entity
        components = entity.xml_element.find(".//object[@name='Components']")
        if components is None:
            return
            
        # Look for physics components
        physics_components = [
            ("CStaticPhysComponent", "Static Physics Component"),
            ("CPhysComponent", "Physics Component"),
            ("CRigidBodyComponent", "Rigid Body Component"),
        ]
        
        for comp_name, display_name in physics_components:
            phys_comp = components.find(f".//object[@name='{comp_name}']")
            if phys_comp is not None:
                self.create_physics_component_section(phys_comp, display_name)
    
    def create_physics_component_section(self, component, component_name):
        """Create section for physics component"""
        section_frame = QGroupBox(component_name, self)
        section_layout = QVBoxLayout(section_frame)
        
        # Main physics fields
        main_frame = QGroupBox("Physics Settings", self)
        main_layout = QGridLayout(main_frame)
        
        physics_fields = [
            ("text_hidResourceId", "Resource Path"),
            ("hidResourceId", "Resource Hash"),
            ("bUseMaxTerrainSlope", "Use Max Terrain Slope"),
            ("bIgnoreInExplosions", "Ignore In Explosions"),
            ("bAnimateable", "Animateable"),
            ("bLargeEntity", "Large Entity"),
            ("hidResourceIndex", "Resource Index"),
        ]
        
        row = 0
        for field_name, display_name in physics_fields:
            field_elem = component.find(f".//field[@name='{field_name}']")
            if field_elem is not None:
                if self.add_component_field_to_layout(main_layout, row, field_elem, display_name):
                    row += 1
        
        if row > 0:
            section_layout.addWidget(main_frame)
        
        # Static params
        static_params = component.find(".//object[@name='StaticParams']")
        if static_params is not None:
            params_frame = QGroupBox("Static Parameters", self)
            params_layout = QGridLayout(params_frame)
            params_row = 0
            
            for field in static_params.findall(".//field[@name]"):
                field_name = field.get('name', '')
                display_name = field_name.replace('b', '').replace('Need', ' Need').replace('Explosion', ' Explosion').replace('Info', ' Info')
                if self.add_component_field_to_layout(params_layout, params_row, field, display_name):
                    params_row += 1
            
            if params_row > 0:
                section_layout.addWidget(params_frame)
        
        if section_layout.count() > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_other_components_section(self):
        """Create section for other components"""
        entity = self.current_entity
        components = entity.xml_element.find(".//object[@name='Components']")
        if components is None:
            return
        
        # Known components that are handled elsewhere
        handled_components = [
            'CGraphicComponent', 'CVehicleWheeledPhysComponent', 'CStaticPhysComponent',
            'CPhysComponent', 'CRigidBodyComponent'
        ]
        
        # Find other components
        other_components = []
        for comp in components.findall(".//object[@name]"):
            comp_name = comp.get('name', '')
            if comp_name not in handled_components and comp_name != 'Components':
                other_components.append((comp, comp_name))
        
        if not other_components:
            return
        
        section_frame = QGroupBox("Other Components", self)
        section_layout = QVBoxLayout(section_frame)
        
        for comp, comp_name in other_components:
            self.create_generic_object_section(section_layout, comp, comp_name)
        
        if section_layout.count() > 0:
            self.content_layout.addWidget(section_frame)
    
    def create_generic_object_section(self, parent_layout, obj, obj_name):
        """Create a generic section for any object"""
        obj_frame = QGroupBox(obj_name, self)
        obj_layout = QVBoxLayout(obj_frame)
        
        # Direct fields
        fields = obj.findall("field[@name]")
        if fields:
            fields_frame = QGroupBox("Fields", self)
            fields_layout = QGridLayout(fields_frame)
            fields_row = 0
            
            for field in fields:
                field_name = field.get('name', '')
                display_name = self.format_field_name(field_name)
                if self.add_component_field_to_layout(fields_layout, fields_row, field, display_name):
                    fields_row += 1
            
            if fields_row > 0:
                obj_layout.addWidget(fields_frame)
        
        # Child objects
        child_objects = obj.findall("object[@name]")
        for child in child_objects:
            child_name = child.get('name', '')
            if child_name != 'hidLinks':  # Skip empty link containers
                self.create_generic_object_section(obj_layout, child, child_name)
        
        if obj_layout.count() > 0:
            parent_layout.addWidget(obj_frame)
    
    def create_detailed_components_section(self):
        """Create detailed components section (former components detail tab)"""
        if not self.current_entity or not hasattr(self.current_entity, 'xml_element') or not self.current_entity.xml_element:
            return
        
        entity = self.current_entity
        components = entity.xml_element.find(".//object[@name='Components']")
        
        if components is None:
            return
        
        # Create main detailed components section
        detailed_frame = QGroupBox("🔍 Detailed Component View", self)
        detailed_layout = QVBoxLayout(detailed_frame)
        
        # Info label
        info_label = QLabel("Complete field-by-field view of all components with BinHex data", self)
        info_label.setStyleSheet("color: gray; font-style: italic; margin-bottom: 10px;")
        detailed_layout.addWidget(info_label)
        
        # Create detailed view for all components
        for comp in components.findall(".//object[@name]"):
            comp_name = comp.get('name', '')
            if comp_name != 'Components':
                self.create_detailed_component_view_unified(detailed_layout, comp, comp_name)
        
        self.content_layout.addWidget(detailed_frame)
    
    def create_detailed_component_view_unified(self, parent_layout, component, component_name):
        """Create detailed view for a single component in unified layout"""
        comp_frame = QGroupBox(f"{component_name}", self)
        comp_layout = QVBoxLayout(comp_frame)
        
        # Component hash info
        comp_hash = component.get('hash', 'No hash')
        hash_label = QLabel(f"Hash: {comp_hash}", self)
        hash_label.setStyleSheet("color: gray; font-size: 10px;")
        comp_layout.addWidget(hash_label)
        
        # All fields in this component
        all_fields = self.get_all_fields_recursive(component)
        
        if all_fields:
            fields_frame = QGroupBox("All Fields", self)
            fields_layout = QGridLayout(fields_frame)
            fields_layout.setColumnStretch(2, 1)  # Make value column expandable
            
            for i, (field_path, field_elem) in enumerate(all_fields):
                # Field name with path
                path_label = QLabel(field_path, self)
                path_label.setStyleSheet("font-weight: bold;")
                fields_layout.addWidget(path_label, i, 0)
                
                # Field type
                field_type = field_elem.get('type', 'Unknown')
                type_label = QLabel(field_type, self)
                type_label.setStyleSheet("color: gray; font-size: 9px;")
                fields_layout.addWidget(type_label, i, 1)
                
                # Field value (editable)
                field_name = field_elem.get('name', '')
                input_widget = self.create_field_input_widget(field_elem, field_name)
                fields_layout.addWidget(input_widget, i, 2)
                
                # BinHex value (read-only)
                binhex_value = field_elem.text or ""
                if len(binhex_value) > 30:
                    binhex_display = binhex_value[:30] + "..."
                else:
                    binhex_display = binhex_value
                
                binhex_label = QLabel(binhex_display, self)
                binhex_label.setStyleSheet("color: gray; font-family: monospace; font-size: 9px;")
                binhex_label.setToolTip(f"Full BinHex: {binhex_value}")
                fields_layout.addWidget(binhex_label, i, 3)
            
            comp_layout.addWidget(fields_frame)
        else:
            no_fields_label = QLabel("No fields found", self)
            no_fields_label.setStyleSheet("color: gray; font-style: italic;")
            comp_layout.addWidget(no_fields_label)
        
        parent_layout.addWidget(comp_frame)
    
    def get_all_fields_recursive(self, element, prefix=""):
        """Get all fields recursively with their full paths"""
        fields = []
        
        # Direct fields
        for field in element.findall("field[@name]"):
            field_name = field.get('name', 'Unknown')
            full_path = f"{prefix}.{field_name}" if prefix else field_name
            fields.append((full_path, field))
        
        # Fields in child objects
        for obj in element.findall("object[@name]"):
            obj_name = obj.get('name', 'Unknown')
            child_prefix = f"{prefix}.{obj_name}" if prefix else obj_name
            child_fields = self.get_all_fields_recursive(obj, child_prefix)
            fields.extend(child_fields)
        
        return fields
    
    def format_field_name(self, field_name):
        """Format field name for display"""
        # Remove common prefixes
        name = field_name.replace('hid', '').replace('text_', '').replace('dis', '').replace('tpl', '')
        
        # Add spaces before capitals
        formatted = ''
        for i, char in enumerate(name):
            if i > 0 and char.isupper() and name[i-1].islower():
                formatted += ' '
            formatted += char
        
        # Capitalize first letter
        return formatted.strip().title() if formatted.strip() else field_name
    
    def add_xml_field_to_layout(self, layout, row, field_name, display_name, expected_type=None):
        """Add an XML field to the layout with enhanced styling"""
        entity = self.current_entity
        if not entity.xml_element:
            return False
            
        field_elem = entity.xml_element.find(f".//field[@name='{field_name}']")
        if field_elem is None:
            return False
        
        # Create styled label
        label = QLabel(f"{display_name}:", self)
        layout.addWidget(label, row, 0)
        
        # Create input widget
        input_widget = self.create_field_input_widget(field_elem, field_name)
        layout.addWidget(input_widget, row, 1, 1, 2)
        
        return True
    
    def add_component_field_to_layout(self, layout, row, field_elem, display_name):
        """Add a component field to the layout with enhanced styling"""
        if field_elem is None:
            return False
        
        # Create styled label
        label = QLabel(f"{display_name}:", self)
        layout.addWidget(label, row, 0)
        
        # Create input widget
        field_name = field_elem.get('name', '')
        input_widget = self.create_field_input_widget(field_elem, field_name)
        layout.addWidget(input_widget, row, 1, 1, 2)
        
        return True
    
    def create_field_input_widget(self, field_elem, field_name):
        """Create appropriate input widget for a field with enhanced functionality"""
        value_attr = self.get_value_attribute(field_elem)
        
        # Determine field type based on name and attributes
        if field_name in ["hidAngles", "vectorQ0", "vectorQ2", "vectorQ5", "vectorNeutral", "hidPos", "hidPos_precise", "vInitialPos"]:
            # Vector3 fields
            widget = self.create_vector3_field(field_elem, value_attr)
            if field_name in ["hidPos", "hidPos_precise"]:
                widget.setEnabled(False)  # Read-only for position fields
            return widget
        elif value_attr in ["value-Id64"] or field_name in ["disEntityId"]:
            # 64-bit ID fields
            return self.create_id64_field(field_elem, value_attr)
        elif value_attr in ["value-Int32"] or field_name in ["hidResourceCount", "hidRigidbodyIndex", "hidGraphicIndex", "hidPartId", "olgLightGroup", "agAmbientGroup", "hidIndex", "nVehicleColor"]:
            # Integer fields
            return self.create_integer_field(field_elem, value_attr)
        elif value_attr in ["value-Hash32"] or field_name in ["hidSkyOcclusion0", "hidSkyOcclusion1", "hidSkyOcclusion2", "hidSkyOcclusion3", "hidGroundColor", "hidRigidbodyName", "objModel", "hidResourceId", "hidScale"]:
            # Hash32 fields
            return self.create_hash32_field(field_elem, value_attr)
        elif value_attr in ["value-Boolean"] or field_name in ["bAllowCullBySize", "bForcePPU", "hidHasAmbientValues", "bCastShadow", "bReceiveShadow", "bCastAmbientShadow", "bShowInReflection", "bAlwaysShowInReflection", "bBehaveLikeAPickup", "bUseMaxTerrainSlope", "bIgnoreInExplosions", "bAnimateable", "bLargeEntity", "bNeedExplosionInfo"]:
            # Boolean fields
            return self.create_boolean_field(field_elem, value_attr)
        elif value_attr in ["value-Float32"] or field_name in ["fCameraRotationFactor", "fDustFactor", "fDirtFactor", "fMaxRollAngle"]:
            # Float fields
            return self.create_float_field(field_elem, value_attr)
        else:
            # String fields (default)
            return self.create_string_field(field_elem, value_attr)
    
    def create_id64_field(self, field_elem, value_attr):
        """Create a 64-bit ID input field"""
        input_field = StringInput(
            self,
            lambda: field_elem.get(value_attr) or "0",
            lambda val: self.update_xml_field_with_binhex(field_elem, value_attr, val, 'id64')
        )
        input_field.changed.connect(self.schedule_auto_save)
        input_field.update_value()
        return input_field
    
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
        """Create a Vector3 input field with enhanced styling"""
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
        for i, (axis, value) in enumerate(zip(['X', 'Y', 'Z'], [x, y, z])):
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
            self.entity_coords_label.setText(f"Position: ({entity.x:.3f}, {entity.y:.3f}, {entity.z:.3f})")
            
            # Schedule auto-save
            self.schedule_auto_save()
        except Exception as e:
            print(f"Error handling position change: {e}")
    
    def add_rotation_field(self):
        """Add hidAngles field to entity if it doesn't exist"""
        if not self.current_entity:
            QMessageBox.information(self, "Add Rotation", "No entity selected.")
            return
            
        if not hasattr(self.current_entity, 'xml_element') or not self.current_entity.xml_element:
            QMessageBox.warning(self, "Add Rotation", "Entity has no XML data.")
            return
        
        # Check if hidAngles already exists
        existing_angles = self.current_entity.xml_element.find(".//field[@name='hidAngles']")
        if existing_angles is not None:
            QMessageBox.information(self, "Add Rotation", "Entity already has rotation data (hidAngles field).")
            return
        
        try:
            # Find the hidPos field to insert after
            pos_field = self.current_entity.xml_element.find(".//field[@name='hidPos']")
            if pos_field is None:
                QMessageBox.warning(self, "Add Rotation", "Could not find hidPos field to insert rotation after.")
                return
            
            # Create the new hidAngles field element
            from xml.etree import ElementTree as ET
            
            angles_field = ET.Element("field")
            angles_field.set("hash", "6553B60B")
            angles_field.set("name", "hidAngles") 
            angles_field.set("value-Vector3", "0,-0,0")
            angles_field.set("type", "BinHex")
            angles_field.text = "000000000000008000000000"  # BinHex for (0, -0, 0)
            
            # Find the parent of hidPos field
            parent = None
            for element in self.current_entity.xml_element.iter():
                for child in element:
                    if child == pos_field:
                        parent = element
                        break
                if parent is not None:
                    break
            
            if parent is None:
                QMessageBox.warning(self, "Add Rotation", "Could not find parent element for insertion.")
                return
            
            # Find the index of hidPos field and insert hidAngles after it
            pos_index = list(parent).index(pos_field)
            parent.insert(pos_index + 1, angles_field)
            
            # Refresh the view to show the new field
            self.populate_all_views()
            
            # Schedule auto-save
            self.schedule_auto_save()
            
            QMessageBox.information(self, "Add Rotation", 
                                  "Rotation field (hidAngles) added successfully!\n\n"
                                  "The field has been inserted between hidPos and hidPos_precise "
                                  "with default values (0, -0, 0).")
            
        except Exception as e:
            error_msg = f"Failed to add rotation field: {str(e)}"
            QMessageBox.critical(self, "Add Rotation Error", error_msg)
            print(f"Add rotation error: {e}")
    
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


# Additional utility functions for better entity handling

def create_enhanced_entity_editor(parent, canvas):
    """Factory function to create the enhanced entity editor"""
    return EntityEditorWindow(parent, canvas)


def get_entity_type_info(entity):
    """Get comprehensive entity type information"""
    info = {
        'name': entity.name,
        'type': 'Unknown',
        'creature_type': None,
        'is_vehicle': False,
        'is_static': False,
        'components': []
    }
    
    if not hasattr(entity, 'xml_element') or not entity.xml_element:
        return info
    
    # Get creature type
    creature_field = entity.xml_element.find(".//field[@name='tplCreatureType']")
    if creature_field is not None:
        creature_type = creature_field.get('value-String', '')
        info['creature_type'] = creature_type
        info['is_vehicle'] = 'vehicle' in creature_type.lower()
    
    # Get entity class
    class_field = entity.xml_element.find(".//field[@name='text_hidEntityClass']")
    if class_field is not None:
        entity_class = class_field.get('value-String', '')
        info['type'] = entity_class
        info['is_static'] = entity_class == 'CEntity'
    
    # Get components
    components = entity.xml_element.find(".//object[@name='Components']")
    if components is not None:
        for comp in components.findall(".//object[@name]"):
            comp_name = comp.get('name', '')
            if comp_name != 'Components':
                info['components'].append(comp_name)
    
    return info


def format_entity_summary(entity):
    """Create a formatted summary of entity information"""
    info = get_entity_type_info(entity)
    
    summary = f"Entity: {info['name']}\n"
    summary += f"Type: {info['type']}\n"
    
    if info['creature_type']:
        summary += f"Creature Type: {info['creature_type']}\n"
    
    if info['is_vehicle']:
        summary += "Category: Vehicle\n"
    elif info['is_static']:
        summary += "Category: Static Object\n"
    
    summary += f"Position: ({entity.x:.3f}, {entity.y:.3f}, {entity.z:.3f})\n"
    
    if info['components']:
        summary += f"Components: {', '.join(info['components'][:5])}"
        if len(info['components']) > 5:
            summary += f" (and {len(info['components']) - 5} more)"
        summary += "\n"
    
    return summary


# Enhanced field type detection
FIELD_TYPE_MAPPINGS = {
    # Vector3 fields
    'vector_fields': [
        'hidAngles', 'vectorQ0', 'vectorQ2', 'vectorQ5', 'vectorNeutral', 
        'hidPos', 'hidPos_precise', 'vInitialPos'
    ],
    
    # Integer fields
    'integer_fields': [
        'hidResourceCount', 'hidRigidbodyIndex', 'hidGraphicIndex', 'hidPartId', 
        'olgLightGroup', 'agAmbientGroup', 'hidIndex', 'nVehicleColor', 
        'hidResourceIndex', 'CustomValue'
    ],
    
    # Hash32 fields  
    'hash_fields': [
        'hidSkyOcclusion0', 'hidSkyOcclusion1', 'hidSkyOcclusion2', 'hidSkyOcclusion3',
        'hidGroundColor', 'hidRigidbodyName', 'objModel', 'hidResourceId', 'hidScale',
        'fileName', 'hidMissionLayerPath', 'hidCategory', 'hidEntityClass'
    ],
    
    # Boolean fields
    'boolean_fields': [
        'bAllowCullBySize', 'bForcePPU', 'hidHasAmbientValues', 'bCastShadow',
        'bReceiveShadow', 'bCastAmbientShadow', 'bShowInReflection', 
        'bAlwaysShowInReflection', 'bBehaveLikeAPickup', 'bUseMaxTerrainSlope',
        'bIgnoreInExplosions', 'bAnimateable', 'bLargeEntity', 'bNeedExplosionInfo',
        'hidConstEntity', 'ForceMerge', 'bCanBePickedUp'
    ],
    
    # Float fields
    'float_fields': [
        'fCameraRotationFactor', 'fDustFactor', 'fDirtFactor', 'fMaxRollAngle'
    ],
    
    # ID64 fields
    'id64_fields': [
        'disEntityId'
    ],
    
    # String fields (default for others)
    'string_fields': [
        'tplCreatureType', 'hidName', 'text_hidEntityClass', 'text_fileName',
        'text_objModel', 'text_hidResourceId', 'text_hidRigidbodyName',
        'text_hidMissionLayerPath', 'text_hidCategory', 'Value'
    ]
}


def get_field_category(field_name, value_attr):
    """Determine the category of a field for proper widget creation"""
    # Check value attribute first
    if value_attr == 'value-Vector3':
        return 'vector'
    elif value_attr == 'value-Int32':
        return 'integer'
    elif value_attr == 'value-Id64':
        return 'id64'
    elif value_attr == 'value-Float32':
        return 'float'
    elif value_attr == 'value-Hash32':
        return 'hash'
    elif value_attr == 'value-Boolean':
        return 'boolean'
    elif value_attr in ['value-String', 'value']:
        return 'string'
    
    # Check field name patterns
    for category, fields in FIELD_TYPE_MAPPINGS.items():
        if field_name in fields:
            return category.replace('_fields', '')
    
    # Default to string
    return 'string'


# Enhanced component descriptions
COMPONENT_DESCRIPTIONS = {
    'CGraphicComponent': 'Handles visual rendering, shadows, and graphics properties',
    'CStaticPhysComponent': 'Static physics collision and physical properties',
    'CVehicleWheeledPhysComponent': 'Wheeled vehicle physics simulation',
    'CVehicle': 'Vehicle-specific behavior and controls',
    'CEventComponent': 'Event system links and triggers',
    'CMissionComponent': 'Mission system integration',
    'CFileDescriptorComponent': 'File resource management',
    'CVehicleMaterialComponent': 'Vehicle material and visual effects',
    'CMapIntelligence': 'AI pathfinding and navigation data'
}


def get_component_description(component_name):
    """Get a user-friendly description for a component"""
    return COMPONENT_DESCRIPTIONS.get(component_name, f"Component: {component_name}")
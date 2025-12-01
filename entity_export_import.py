# entity_export_import.py - Entity Export/Import System for Level Editor

import os
import json
import xml.etree.ElementTree as ET
import shutil
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QLineEdit, QFileDialog, QMessageBox, 
                             QComboBox, QTextEdit, QGroupBox, QCheckBox,
                             QListWidget, QListWidgetItem, QSplitter,
                             QProgressDialog, QApplication)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap, QIcon
from data_models import Entity
import time


class XMLHelper:
    """Helper class for XML manipulation shared between export and import"""
    
    @staticmethod
    def update_entity_position(xml_element, x, y, z):
        """Update position fields in entity XML - works for both formats"""
        try:
            # FCBConverter format (has field elements)
            pos_field = xml_element.find(".//field[@name='hidPos']")
            if pos_field is not None:
                pos_field.set('value-Vector3', f"{x},{y},{z}")
                binary_hex = XMLHelper.coordinates_to_binhex(x, y, z)
                pos_field.text = binary_hex
                
                # Also update hidPos_precise
                pos_precise = xml_element.find(".//field[@name='hidPos_precise']")
                if pos_precise is not None:
                    pos_precise.set('value-Vector3', f"{x},{y},{z}")
                    pos_precise.text = binary_hex
                return True
            
            # Dunia Tools format (has value elements)
            pos_elem = xml_element.find(".//value[@name='hidPos']")
            if pos_elem is not None:
                for axis, value in [('x', x), ('y', y), ('z', z)]:
                    axis_elem = pos_elem.find(f"./{axis}")
                    if axis_elem is not None:
                        axis_elem.text = str(int(value))
                
                # Also update hidPos_precise
                pos_precise = xml_element.find(".//value[@name='hidPos_precise']")
                if pos_precise is not None:
                    for axis, value in [('x', x), ('y', y), ('z', z)]:
                        axis_elem = pos_precise.find(f"./{axis}")
                        if axis_elem is not None:
                            axis_elem.text = str(int(value))
                return True
                
            return False
        except Exception as e:
            print(f"Error updating position: {e}")
            return False
    
    @staticmethod
    def coordinates_to_binhex(x, y, z):
        """Convert coordinates to BinHex format (IEEE 754 32-bit floats)"""
        import struct
        try:
            binary_data = struct.pack('<fff', float(x), float(y), float(z))
            return binary_data.hex().upper()
        except Exception as e:
            print(f"Error converting to BinHex: {e}")
            return "000000000000000000000000"
    
    @staticmethod
    def int64_to_binhex(value):
        """Convert 64-bit integer to BinHex format"""
        import struct
        try:
            binary_data = struct.pack('<Q', int(value))
            return binary_data.hex().upper()
        except:
            return "0000000000000000"
    
    @staticmethod
    def update_entity_id(xml_element, new_id):
        """Update entity ID in XML"""
        try:
            # FCBConverter format
            id_field = xml_element.find(".//field[@name='disEntityId']")
            if id_field is not None:
                id_field.set('value-Id64', str(new_id))
                binary_hex = XMLHelper.int64_to_binhex(new_id)
                id_field.text = binary_hex
                return True
            
            # Dunia Tools format
            id_elem = xml_element.find(".//value[@name='disEntityId']")
            if id_elem is not None:
                id_elem.text = str(new_id)
                return True
                
            return False
        except Exception as e:
            print(f"Error updating entity ID: {e}")
            return False
    
    @staticmethod
    def extract_position_from_xml(xml_element):
        """Extract position from XML element"""
        try:
            # FCBConverter format
            pos_field = xml_element.find(".//field[@name='hidPos']")
            if pos_field is not None:
                pos_vector = pos_field.get('value-Vector3', '0,0,0')
                x, y, z = map(float, pos_vector.split(','))
                return x, y, z
            
            # Dunia Tools format
            pos_elem = xml_element.find(".//value[@name='hidPos']")
            if pos_elem is not None:
                x = float(pos_elem.find('./x').text or 0)
                y = float(pos_elem.find('./y').text or 0)
                z = float(pos_elem.find('./z').text or 0)
                return x, y, z
        except:
            pass
        
        return 0.0, 0.0, 0.0
    
    @staticmethod
    def extract_entity_name(xml_element):
        """Extract entity name from XML"""
        try:
            # FCBConverter format
            name_field = xml_element.find(".//field[@name='hidName']")
            if name_field is not None:
                return name_field.get('value-String', 'Unknown')
            
            # Dunia Tools format
            name_elem = xml_element.find(".//value[@name='hidName']")
            if name_elem is not None:
                return name_elem.text or 'Unknown'
        except:
            pass
        
        return 'Unknown'
    
    @staticmethod
    def extract_entity_id(xml_element):
        """Extract entity ID from XML"""
        try:
            # FCBConverter format
            id_field = xml_element.find(".//field[@name='disEntityId']")
            if id_field is not None:
                return id_field.get('value-Id64', 'Unknown')
            
            # Dunia Tools format
            id_elem = xml_element.find(".//value[@name='disEntityId']")
            if id_elem is not None:
                return id_elem.text or 'Unknown'
        except:
            pass
        
        return 'Unknown'


class EntityExportDialog(QDialog):
    """Dialog for exporting selected entities to XML files"""
    
    def __init__(self, parent, selected_entities):
        super().__init__(parent)
        self.parent_editor = parent
        self.selected_entities = selected_entities
        self.objects_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "objects")
        
        self.setWindowTitle("Export Entities")
        self.setModal(True)
        self.resize(500, 400)
        
        self.setup_ui()
        self.load_existing_collections()
        
    def setup_ui(self):
        """Setup the export dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel(f"Export {len(self.selected_entities)} Selected Entities")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Entity list preview
        preview_group = QGroupBox("Entities to Export")
        preview_layout = QVBoxLayout(preview_group)
        
        self.entity_list = QListWidget()
        for entity in self.selected_entities:
            item_text = f"{entity.name} - ({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})"
            source = getattr(entity, 'source_file', 'unknown')
            item_text += f" [{source}]"
            
            item = QListWidgetItem(item_text)
            self.entity_list.addItem(item)
        
        preview_layout.addWidget(self.entity_list)
        layout.addWidget(preview_group)
        
        # Collection naming
        naming_group = QGroupBox("Export Settings")
        naming_layout = QVBoxLayout(naming_group)
        
        # Collection name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Collection Name:"))
        
        self.collection_name_edit = QLineEdit()
        self.collection_name_edit.setPlaceholderText("Enter collection name (e.g., 'vehicles', 'buildings')")
        name_layout.addWidget(self.collection_name_edit)
        
        naming_layout.addLayout(name_layout)
        
        # Export options
        self.preserve_positions_check = QCheckBox("Preserve original positions")
        self.preserve_positions_check.setChecked(True)
        self.preserve_positions_check.setToolTip("Keep original world coordinates when exporting")
        naming_layout.addWidget(self.preserve_positions_check)
        
        self.include_metadata_check = QCheckBox("Include metadata (source, map info)")
        self.include_metadata_check.setChecked(True)
        naming_layout.addWidget(self.include_metadata_check)
        
        layout.addWidget(naming_group)
        
        # Existing collections (if any)
        if os.path.exists(self.objects_folder):
            existing_group = QGroupBox("Existing Collections")
            existing_layout = QVBoxLayout(existing_group)
            
            self.existing_combo = QComboBox()
            self.existing_combo.addItem("-- Create New Collection --")
            existing_layout.addWidget(QLabel("Or add to existing collection:"))
            existing_layout.addWidget(self.existing_combo)
            
            # When existing collection is selected, update name field
            self.existing_combo.currentTextChanged.connect(self.on_existing_selected)
            
            layout.addWidget(existing_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Export Entities")
        self.export_button.clicked.connect(self.export_entities)
        button_layout.addWidget(self.export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        
    def load_existing_collections(self):
        """Load existing entity collections"""
        if not hasattr(self, 'existing_combo'):
            return
            
        if os.path.exists(self.objects_folder):
            for item in os.listdir(self.objects_folder):
                item_path = os.path.join(self.objects_folder, item)
                if os.path.isdir(item_path):
                    # Check if it contains entity XML files
                    has_entities = any(f.endswith('.xml') for f in os.listdir(item_path))
                    if has_entities:
                        self.existing_combo.addItem(item)
    
    def on_existing_selected(self, collection_name):
        """Handle selection of existing collection"""
        if collection_name != "-- Create New Collection --":
            self.collection_name_edit.setText(collection_name)
        else:
            self.collection_name_edit.clear()
    
    def export_entities(self):
        """Export the selected entities to XML files"""
        collection_name = self.collection_name_edit.text().strip()
        
        if not collection_name:
            QMessageBox.warning(self, "No Collection Name", 
                              "Please enter a collection name.")
            return
        
        # Validate collection name
        if not self.is_valid_folder_name(collection_name):
            QMessageBox.warning(self, "Invalid Name", 
                              "Collection name contains invalid characters.\n"
                              "Please use only letters, numbers, spaces, and basic punctuation.")
            return
        
        try:
            # Create objects folder if it doesn't exist
            if not os.path.exists(self.objects_folder):
                os.makedirs(self.objects_folder)
            
            # Create collection folder
            collection_folder = os.path.join(self.objects_folder, collection_name)
            if not os.path.exists(collection_folder):
                os.makedirs(collection_folder)
            
            # Export each entity
            exported_files = []
            metadata = {
                'collection_name': collection_name,
                'export_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'entity_count': len(self.selected_entities),
                'preserve_positions': self.preserve_positions_check.isChecked(),
                'include_metadata': self.include_metadata_check.isChecked(),
                'entities': []
            }
            
            for i, entity in enumerate(self.selected_entities):
                # Create safe filename
                safe_name = self.create_safe_filename(entity.name)
                xml_filename = f"{safe_name}_{i+1:03d}.xml"
                xml_path = os.path.join(collection_folder, xml_filename)
                
                # Export entity to XML
                success = self.export_entity_to_xml(entity, xml_path)
                
                if success:
                    exported_files.append(xml_filename)
                    
                    # Add to metadata
                    entity_metadata = {
                        'name': entity.name,
                        'id': entity.id,
                        'filename': xml_filename,
                        'original_position': {
                            'x': entity.x,
                            'y': entity.y,
                            'z': entity.z
                        }
                    }
                    
                    if self.include_metadata_check.isChecked():
                        entity_metadata.update({
                            'source_file': getattr(entity, 'source_file', None),
                            'source_file_path': getattr(entity, 'source_file_path', None),
                            'map_name': getattr(entity, 'map_name', None)
                        })
                    
                    metadata['entities'].append(entity_metadata)
            
            # Save collection metadata
            metadata_path = os.path.join(collection_folder, "collection_info.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            # Create a readme file
            readme_path = os.path.join(collection_folder, "README.txt")
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(f"Entity Collection: {collection_name}\n")
                f.write(f"Exported: {metadata['export_date']}\n")
                f.write(f"Entity Count: {len(exported_files)}\n\n")
                f.write("Exported Entities:\n")
                for entity_info in metadata['entities']:
                    f.write(f"- {entity_info['name']} ({entity_info['filename']})\n")
                f.write(f"\nTo import these entities, use the Entity Import function in the level editor.")
            
            # Show success message
            QMessageBox.information(
                self, 
                "Export Successful", 
                f"Successfully exported {len(exported_files)} entities to:\n"
                f"{collection_folder}\n\n"
                f"Files created:\n"
                f"• {len(exported_files)} entity XML files\n"
                f"• collection_info.json (metadata)\n"
                f"• README.txt (documentation)"
            )
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", 
                               f"Failed to export entities: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def export_entity_to_xml(self, entity, xml_path):
        """Export a single entity to an XML file"""
        try:
            # Create a clean copy of the entity's XML element
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                # Make a deep copy of the XML element
                import copy
                xml_copy = copy.deepcopy(entity.xml_element)
                
                # Update the position fields to current entity position if preserve_positions is checked
                if self.preserve_positions_check.isChecked():
                    XMLHelper.update_entity_position(xml_copy, entity.x, entity.y, entity.z)
                
                # Export the clean entity XML directly (no wrapper)
                self.write_xml_with_custom_formatting(xml_copy, xml_path)
                
                print(f"✓ Exported {entity.name} to {os.path.basename(xml_path)}")
                return True
            else:
                print(f"✗ Entity {entity.name} has no XML element")
                return False
                
        except Exception as e:
            print(f"✗ Error exporting {entity.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
                            
    def write_xml_with_custom_formatting(self, element, xml_path):
        """Write XML with custom formatting - no declaration, 2-space indentation"""
        try:
            # Convert element to string with proper formatting
            import xml.dom.minidom
            
            # First convert to string using ElementTree
            rough_string = ET.tostring(element, encoding='unicode')
            
            # Parse with minidom for pretty printing
            dom = xml.dom.minidom.parseString(rough_string)
            
            # Get the pretty printed string with 2-space indentation
            pretty_xml = dom.documentElement.toprettyxml(indent="  ")
            
            # Remove the extra XML declaration that minidom adds
            lines = pretty_xml.split('\n')
            if lines[0].startswith('<?xml'):
                lines = lines[1:]
            
            # Remove empty lines and rejoin
            clean_lines = [line for line in lines if line.strip()]
            
            # Write to file with clean formatting
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(clean_lines))
            
        except Exception as e:
            print(f"Error in custom XML formatting: {e}")
            # Fallback to standard method
            tree = ET.ElementTree(element)
            tree.write(xml_path, encoding='utf-8', xml_declaration=False)
                        
    def is_valid_folder_name(self, name):
        """Check if the folder name is valid"""
        invalid_chars = '<>:"/\\|?*'
        return not any(char in name for char in invalid_chars) and len(name) > 0
    
    def create_safe_filename(self, entity_name):
        """Create a safe filename from entity name"""
        # Remove or replace invalid filename characters
        safe_name = entity_name
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')
        
        # Remove multiple underscores and clean up
        while '__' in safe_name:
            safe_name = safe_name.replace('__', '_')
        
        safe_name = safe_name.strip('_')
        
        # Ensure it's not empty
        if not safe_name:
            safe_name = "entity"
        
        return safe_name


class EntityImportDialog(QDialog):
    """Dialog for importing entities from XML files"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_editor = parent
        self.objects_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "objects")
        self.selected_collection = None
        self.collection_metadata = None
        self.entities_to_import = []
        
        self.setWindowTitle("Import Entities")
        self.setModal(True)
        self.resize(700, 500)
        
        self.setup_ui()
        self.load_collections()
    
    def setup_ui(self):
        """Setup the import dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Import Entities from Collection")
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Collection selection
        left_widget = QGroupBox("Collections")
        left_layout = QVBoxLayout(left_widget)
        
        self.collections_list = QListWidget()
        self.collections_list.currentItemChanged.connect(self.on_collection_selected)
        left_layout.addWidget(self.collections_list)
        
        browse_button = QPushButton("Browse for Collection...")
        browse_button.clicked.connect(self.browse_for_collection)
        left_layout.addWidget(browse_button)
        
        splitter.addWidget(left_widget)
        
        # Right side - Entity preview and options
        right_widget = QGroupBox("Import Settings")
        right_layout = QVBoxLayout(right_widget)
        
        # Collection info
        self.collection_info_label = QLabel("Select a collection to see details")
        right_layout.addWidget(self.collection_info_label)
        
        # Entity list
        entities_label = QLabel("Entities to Import:")
        right_layout.addWidget(entities_label)
        
        self.entities_list = QListWidget()
        self.entities_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        right_layout.addWidget(self.entities_list)
        
        # Import position options
        position_group = QGroupBox("Position Settings")
        position_layout = QVBoxLayout(position_group)
        
        self.preserve_positions_radio = QCheckBox("Use original positions")
        self.preserve_positions_radio.setChecked(True)
        position_layout.addWidget(self.preserve_positions_radio)
        
        self.cursor_position_radio = QCheckBox("Place at cursor position")
        position_layout.addWidget(self.cursor_position_radio)
        
        right_layout.addWidget(position_group)
        
        # Sector selection
        sector_group = QGroupBox("Target Sector")
        sector_layout = QVBoxLayout(sector_group)
        
        sector_label = QLabel("Import entities to sector:")
        sector_layout.addWidget(sector_label)
        
        self.sector_combo = QComboBox()
        self.load_available_sectors()
        sector_layout.addWidget(self.sector_combo)
        
        right_layout.addWidget(sector_group)
        
        splitter.addWidget(right_widget)
        layout.addWidget(splitter)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.import_button = QPushButton("Import Selected Entities")
        self.import_button.clicked.connect(self.import_entities)
        self.import_button.setEnabled(False)
        button_layout.addWidget(self.import_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
    
    def load_entities_from_collection(self, collection_path):
        """Load entities from the collection folder"""
        self.entities_list.clear()
        
        # Find all XML files
        xml_files = [f for f in os.listdir(collection_path) 
                     if f.endswith('.xml') and f != 'collection_info.json']
        
        for xml_file in xml_files:
            xml_path = os.path.join(collection_path, xml_file)
            
            try:
                # Parse the exported XML (clean format)
                tree = ET.parse(xml_path)
                root = tree.getroot()
                
                # Extract entity information using XMLHelper
                entity_name = XMLHelper.extract_entity_name(root)
                entity_id = XMLHelper.extract_entity_id(root)
                x, y, z = XMLHelper.extract_position_from_xml(root)
                
                position_text = f"({x:.1f}, {y:.1f}, {z:.1f})"
                item_text = f"{entity_name} - {position_text}"
                
                list_item = QListWidgetItem(item_text)
                list_item.setData(Qt.ItemDataRole.UserRole, {
                    'xml_path': xml_path,
                    'name': entity_name,
                    'id': entity_id,
                    'position': position_text,
                    'xml_element': root
                })
                list_item.setSelected(True)
                self.entities_list.addItem(list_item)
                    
            except Exception as e:
                print(f"Error loading entity from {xml_file}: {e}")
                list_item = QListWidgetItem(f"{xml_file} (Error loading)")
                list_item.setData(Qt.ItemDataRole.UserRole, {
                    'xml_path': xml_path,
                    'name': xml_file,
                    'id': 'unknown',
                    'error': str(e)
                })
                self.entities_list.addItem(list_item)

    def import_single_entity(self, item, sector_file_path):
        """Import a single entity by copying its XML directly into the sector file"""
        try:
            entity_data = item.data(Qt.ItemDataRole.UserRole)
            xml_path = entity_data['xml_path']
            
            # Read the exported XML file directly
            tree = ET.parse(xml_path)
            entity_xml = tree.getroot()
            
            # Make a deep copy to avoid modifying the original
            import copy
            entity_xml = copy.deepcopy(entity_xml)
            
            # Generate new unique ID
            new_id = self.generate_unique_entity_id()
            
            # Update the entity ID in the XML
            if not XMLHelper.update_entity_id(entity_xml, new_id):
                print("Warning: Could not update entity ID")
            
            # Update position if using cursor position
            if self.cursor_position_radio.isChecked():
                # Get cursor position
                if hasattr(self.parent_editor.canvas, 'last_mouse_world_pos'):
                    cursor_pos = self.parent_editor.canvas.last_mouse_world_pos
                    x, y, z = cursor_pos[0], cursor_pos[1], cursor_pos[2]
                else:
                    x = y = z = 0.0
                
                XMLHelper.update_entity_position(entity_xml, x, y, z)
            
            # Add the entity XML directly to the sector file
            success = self.add_entity_xml_to_sector(entity_xml, sector_file_path)
            if not success:
                return False, None
            
            # Create Entity object for the editor
            entity_name = entity_data['name']
            
            # Get final position from the XML
            x, y, z = XMLHelper.extract_position_from_xml(entity_xml)
            
            entity = Entity(
                id=str(new_id),
                name=entity_name,
                x=x, y=y, z=z,
                xml_element=entity_xml
            )
            
            # Set source file information
            entity.source_file = "worldsectors"
            entity.source_file_path = sector_file_path
            
            print(f"✓ Successfully imported {entity_name} to {os.path.basename(sector_file_path)}")
            return True, entity
            
        except Exception as e:
            print(f"Error importing entity: {e}")
            import traceback
            traceback.print_exc()
            return False, None

    def generate_unique_entity_id(self):
        """Generate a unique entity ID"""
        # Try to use parent editor's method if available
        if hasattr(self.parent_editor, 'generate_new_entity_id'):
            return self.parent_editor.generate_new_entity_id()
        
        # Fallback: generate based on existing entities
        existing_ids = set()
        if hasattr(self.parent_editor, 'entities'):
            for entity in self.parent_editor.entities:
                try:
                    existing_ids.add(int(entity.id))
                except:
                    pass
        
        # Start from a high number to avoid conflicts
        new_id = 900000
        while new_id in existing_ids:
            new_id += 1
        
        return new_id

    def add_entity_xml_to_sector(self, entity_xml, sector_file_path):
        """Add entity XML to MissionLayer - prefers 'outside_entity', falls back to 'main'"""
        try:
            # Load the target file if not already loaded
            if not hasattr(self.parent_editor, 'worldsectors_trees'):
                self.parent_editor.worldsectors_trees = {}
            
            if sector_file_path not in self.parent_editor.worldsectors_trees:
                if os.path.exists(sector_file_path):
                    tree = ET.parse(sector_file_path)
                    self.parent_editor.worldsectors_trees[sector_file_path] = tree
                else:
                    print(f"Sector file does not exist: {sector_file_path}")
                    return False
            
            tree = self.parent_editor.worldsectors_trees[sector_file_path]
            root = tree.getroot()
            
            # Find ALL MissionLayers
            mission_layers = root.findall(".//object[@name='MissionLayer']")
            if not mission_layers:
                print(f"No MissionLayer found in {sector_file_path}")
                return False
            
            print(f"Found {len(mission_layers)} MissionLayer(s) in file")
            
            # Search for MissionLayers - try "outside_entity" first, then "main"
            target_mission_layer = None
            target_path_id = None
            
            for preferred_id in ["outside_entity", "main"]:
                for mission_layer in mission_layers:
                    # Check text_PathId field (FCBConverter format)
                    path_id_field = mission_layer.find("field[@name='text_PathId']")
                    if path_id_field is not None:
                        path_id_value = path_id_field.get('value-String', '')
                        if path_id_value == preferred_id:
                            target_mission_layer = mission_layer
                            target_path_id = preferred_id
                            print(f"✅ Found target MissionLayer: {preferred_id}")
                            break
                    
                    # Also check Dunia Tools format (value element)
                    path_id_elem = mission_layer.find("value[@name='text_PathId']")
                    if path_id_elem is not None:
                        path_id_value = path_id_elem.text or ''
                        if path_id_value == preferred_id:
                            target_mission_layer = mission_layer
                            target_path_id = preferred_id
                            print(f"✅ Found target MissionLayer: {preferred_id}")
                            break
                
                # If we found a layer, stop searching
                if target_mission_layer is not None:
                    break
            
            if target_mission_layer is None:
                print(f"❌ No MissionLayer with PathId='outside_entity' or 'main' found in {sector_file_path}")
                print(f"Available MissionLayers:")
                for ml in mission_layers:
                    path_field = ml.find("field[@name='text_PathId']")
                    if path_field is not None:
                        print(f"  - {path_field.get('value-String', 'unknown')}")
                    else:
                        path_elem = ml.find("value[@name='text_PathId']")
                        if path_elem is not None:
                            print(f"  - {path_elem.text or 'unknown'}")
                return False
            
            # Count existing entities BEFORE adding
            existing_entities = target_mission_layer.findall("object[@name='Entity']")
            print(f"MissionLayer '{target_path_id}' currently has {len(existing_entities)} entities")
            
            # CRITICAL FIX: Create truly independent copy by converting to string and parsing back
            print(f"🔧 Creating independent copy of entity XML...")
            xml_string = ET.tostring(entity_xml, encoding='unicode')
            entity_copy = ET.fromstring(xml_string)
            
            # IMPORTANT: Insert the entity at the END of the MissionLayer's children
            # Find the last Entity index to insert after all other entities
            last_entity_index = -1
            for i, child in enumerate(target_mission_layer):
                if child.tag == 'object' and child.get('name') == 'Entity':
                    last_entity_index = i
            
            if last_entity_index >= 0:
                # Insert after the last entity
                insert_position = last_entity_index + 1
                print(f"🔧 Inserting entity at position {insert_position} (after last entity)")
                target_mission_layer.insert(insert_position, entity_copy)
            else:
                # No entities yet, append at end
                print(f"🔧 Appending entity (first entity in layer)")
                target_mission_layer.append(entity_copy)
            
            # Verify the entity was added correctly
            new_entities = target_mission_layer.findall("object[@name='Entity']")
            print(f"MissionLayer '{target_path_id}' now has {len(new_entities)} entities")
            
            if len(new_entities) <= len(existing_entities):
                print(f"❌ Entity was not added correctly!")
                print(f"Expected: {len(existing_entities) + 1}, Got: {len(new_entities)}")
                
                # Debug: Check what's in the MissionLayer
                print(f"🔍 Debug - MissionLayer children:")
                for i, child in enumerate(target_mission_layer):
                    print(f"  {i}: {child.tag}, name={child.get('name', 'N/A')}")
                
                return False
            
            print(f"✅ Successfully added entity to '{target_path_id}' MissionLayer")
            
            # CRITICAL: Use indent() to properly format the XML before saving
            print(f"🔧 Formatting XML with proper indentation...")
            try:
                # Python 3.9+ has indent() built-in
                ET.indent(tree, space="  ")
            except AttributeError:
                # Fallback for older Python versions - manual indentation
                self._indent_xml_tree(root)
            
            # Save the file immediately
            print(f"💾 Writing to file: {sector_file_path}")
            tree.write(sector_file_path, encoding='utf-8', xml_declaration=True)
            print(f"💾 Saved {os.path.basename(sector_file_path)}")
            
            # Mark as modified
            if not hasattr(self.parent_editor, 'worldsectors_modified'):
                self.parent_editor.worldsectors_modified = {}
            self.parent_editor.worldsectors_modified[sector_file_path] = True
            
            return True
            
        except Exception as e:
            print(f"❌ Error adding entity to sector: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _indent_xml_tree(self, elem, level=0):
        """Fallback XML indentation for Python < 3.9"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                self._indent_xml_tree(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def load_collections(self):
        """Load available entity collections"""
        self.collections_list.clear()
        
        if not os.path.exists(self.objects_folder):
            self.status_label.setText("No objects folder found. Export some entities first.")
            return
        
        collections_found = 0
        
        for item in os.listdir(self.objects_folder):
            item_path = os.path.join(self.objects_folder, item)
            if os.path.isdir(item_path):
                # Check if it's a valid collection
                metadata_path = os.path.join(item_path, "collection_info.json")
                xml_files = [f for f in os.listdir(item_path) if f.endswith('.xml')]
                
                if os.path.exists(metadata_path) or xml_files:
                    collections_found += 1
                    
                    # Create list item with collection info
                    if os.path.exists(metadata_path):
                        try:
                            with open(metadata_path, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            
                            item_text = f"{item} ({metadata.get('entity_count', len(xml_files))} entities)"
                            export_date = metadata.get('export_date', 'Unknown date')
                            item_text += f" - {export_date}"
                        except:
                            item_text = f"{item} ({len(xml_files)} entities)"
                    else:
                        item_text = f"{item} ({len(xml_files)} entities)"
                    
                    list_item = QListWidgetItem(item_text)
                    list_item.setData(Qt.ItemDataRole.UserRole, item_path)
                    self.collections_list.addItem(list_item)
        
        if collections_found == 0:
            self.status_label.setText("No entity collections found in objects folder.")
        else:
            self.status_label.setText(f"Found {collections_found} entity collections.")
    
    def load_available_sectors(self):
        """Load available worldsector files for target selection"""
        self.sector_combo.clear()
        self.sector_combo.addItem("-- Select Target Sector --")
        
        sectors_added = 0
        existing_paths = set()
        
        # Method 1: Check worldsectors_trees (loaded XML files)
        if hasattr(self.parent_editor, 'worldsectors_trees') and self.parent_editor.worldsectors_trees:
            print(f"Found {len(self.parent_editor.worldsectors_trees)} loaded worldsector trees")
            for file_path in self.parent_editor.worldsectors_trees.keys():
                filename = os.path.basename(file_path)
                if 'worldsector' in filename:
                    # Extract sector number
                    import re
                    match = re.search(r'worldsector(\d+)', filename)
                    if match:
                        sector_num = match.group(1)
                        display_name = f"Sector {sector_num} ({filename})"
                        self.sector_combo.addItem(display_name, file_path)
                        existing_paths.add(file_path)
                        sectors_added += 1
                        print(f"Added sector from trees: {display_name}")
        
        # Method 2: Check entities for their source files
        sectors_from_entities = set()
        if hasattr(self.parent_editor, 'entities'):
            for entity in self.parent_editor.entities:
                source_file = getattr(entity, 'source_file_path', None)
                if source_file and 'worldsector' in source_file and os.path.exists(source_file):
                    sectors_from_entities.add(source_file)
        
        # Add any sectors we found from entities that aren't already loaded
        for sector_file in sectors_from_entities:
            if sector_file not in existing_paths:
                filename = os.path.basename(sector_file)
                import re
                match = re.search(r'worldsector(\d+)', filename)
                if match:
                    sector_num = match.group(1)
                    display_name = f"Sector {sector_num} ({filename}) [From entities]"
                    self.sector_combo.addItem(display_name, sector_file)
                    existing_paths.add(sector_file)
                    sectors_added += 1
                    print(f"Added sector from entities: {display_name}")
        
        # Method 3: Check worldsectors_path for .converted.xml files
        if hasattr(self.parent_editor, 'worldsectors_path') and self.parent_editor.worldsectors_path:
            worldsectors_path = self.parent_editor.worldsectors_path
            if os.path.exists(worldsectors_path):
                for file in os.listdir(worldsectors_path):
                    if file.endswith('.converted.xml') and 'worldsector' in file:
                        file_path = os.path.join(worldsectors_path, file)
                        if file_path not in existing_paths:
                            import re
                            match = re.search(r'worldsector(\d+)', file)
                            if match:
                                sector_num = match.group(1)
                                display_name = f"Sector {sector_num} ({file}) [Available]"
                                self.sector_combo.addItem(display_name, file_path)
                                existing_paths.add(file_path)
                                sectors_added += 1
                                print(f"Added sector from worldsectors_path: {display_name}")
        
        print(f"Total sectors added to combo: {sectors_added}")
        
        if sectors_added == 0:
            self.sector_combo.addItem("No sectors available - load worldsectors first", None)
            print("No worldsectors found - added warning message")
    
    def browse_for_collection(self):
        """Browse for a collection folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Entity Collection Folder",
            self.objects_folder if os.path.exists(self.objects_folder) else ""
        )
        
        if folder_path:
            # Check if it's a valid collection
            xml_files = [f for f in os.listdir(folder_path) if f.endswith('.xml')]
            if xml_files:
                self.load_collection_from_path(folder_path)
            else:
                QMessageBox.warning(self, "Invalid Collection", 
                                  "The selected folder does not contain any XML entity files.")
    
    def on_collection_selected(self, current, previous):
        """Handle collection selection"""
        if current:
            collection_path = current.data(Qt.ItemDataRole.UserRole)
            self.load_collection_from_path(collection_path)
    
    def load_collection_from_path(self, collection_path):
        """Load collection details from the given path"""
        self.selected_collection = collection_path
        self.entities_to_import = []
        
        # Load metadata if available
        metadata_path = os.path.join(collection_path, "collection_info.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.collection_metadata = json.load(f)
            except:
                self.collection_metadata = None
        else:
            self.collection_metadata = None
        
        # Update collection info
        collection_name = os.path.basename(collection_path)
        info_text = f"Collection: {collection_name}\n"
        
        if self.collection_metadata:
            info_text += f"Exported: {self.collection_metadata.get('export_date', 'Unknown')}\n"
            info_text += f"Entity Count: {self.collection_metadata.get('entity_count', 'Unknown')}\n"
        
        self.collection_info_label.setText(info_text)
        
        # Load entities list
        self.load_entities_from_collection(collection_path)
        
        # Enable import button
        self.import_button.setEnabled(True)
    
    def import_entities(self):
        """Import the selected entities"""
        # Get selected entities
        selected_items = [self.entities_list.item(i) for i in range(self.entities_list.count()) 
                         if self.entities_list.item(i).isSelected()]
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select entities to import.")
            return
        
        # Get target sector
        sector_data = self.sector_combo.currentData()
        if not sector_data:
            QMessageBox.warning(self, "No Sector", "Please select a target sector.")
            return
        
        # Confirm import
        reply = QMessageBox.question(
            self,
            "Confirm Import",
            f"Import {len(selected_items)} entities to {os.path.basename(sector_data)}?\n\n"
            f"This will add the entities to the selected worldsector file.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Create progress dialog
            progress = QProgressDialog("Importing entities...", "Cancel", 0, len(selected_items), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            
            imported_entities = []
            failed_imports = []
            
            for i, item in enumerate(selected_items):
                progress.setValue(i)
                entity_name = item.data(Qt.ItemDataRole.UserRole)['name']
                progress.setLabelText(f"Importing {entity_name}...")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                
                # Import the entity
                success, entity = self.import_single_entity(item, sector_data)
                if success:
                    imported_entities.append(entity)
                else:
                    failed_imports.append(entity_name)
            
            progress.close()
            
            # Update the editor
            if imported_entities:
                # Add to main entities list
                self.parent_editor.entities.extend(imported_entities)
                
                # Update canvas
                self.parent_editor.canvas.set_entities(self.parent_editor.entities)
                
                # Update entity tree
                if hasattr(self.parent_editor, 'update_entity_tree'):
                    self.parent_editor.update_entity_tree()
                
                # Update statistics
                if hasattr(self.parent_editor, 'update_entity_statistics'):
                    self.parent_editor.update_entity_statistics()
                
                # Update canvas
                self.parent_editor.canvas.update()
                
                # Reset view to show imported entities
                if hasattr(self.parent_editor, 'reset_view'):
                    self.parent_editor.reset_view()
            
            # Show results
            success_msg = f"Successfully imported {len(imported_entities)} entities"
            if failed_imports:
                success_msg += f"\n\nFailed to import {len(failed_imports)} entities:\n"
                success_msg += "\n".join(failed_imports[:5])
                if len(failed_imports) > 5:
                    success_msg += f"\n... and {len(failed_imports) - 5} more"
                
                QMessageBox.warning(self, "Import Completed with Errors", success_msg)
            else:
                QMessageBox.information(self, "Import Successful", success_msg)
            
            if imported_entities:
                self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import entities: {str(e)}")
            import traceback
            traceback.print_exc()


def show_entity_export_dialog(editor):
    """Show the entity export dialog"""
    # Check if entities are selected
    selected_entities = []
    
    if hasattr(editor, 'canvas') and hasattr(editor.canvas, 'selected'):
        selected_entities = editor.canvas.selected
    elif hasattr(editor, 'selected_entity') and editor.selected_entity:
        selected_entities = [editor.selected_entity]
    
    if not selected_entities:
        QMessageBox.warning(
            editor,
            "No Selection",
            "Please select one or more entities to export.\n\n"
            "Click on entities in the canvas or use the entity browser to select them."
        )
        return
    
    # Show export dialog
    dialog = EntityExportDialog(editor, selected_entities)
    dialog.exec()


def show_entity_import_dialog(editor):
    """Show the entity import dialog"""
    # Enhanced worldsector detection
    worldsectors_available = False
    
    # Check multiple sources for worldsectors
    if hasattr(editor, 'worldsectors_trees') and editor.worldsectors_trees:
        worldsectors_available = True
        print(f"Found {len(editor.worldsectors_trees)} loaded worldsector trees")
    
    if not worldsectors_available and hasattr(editor, 'entities'):
        # Check if any entities have worldsector source files
        for entity in editor.entities:
            source_file = getattr(entity, 'source_file_path', None)
            if source_file and 'worldsector' in source_file and os.path.exists(source_file):
                worldsectors_available = True
                print(f"Found worldsector from entity: {source_file}")
                break
    
    if not worldsectors_available and hasattr(editor, 'worldsectors_path'):
        # Check if worldsectors_path exists and has .converted.xml files
        if editor.worldsectors_path and os.path.exists(editor.worldsectors_path):
            for file in os.listdir(editor.worldsectors_path):
                if file.endswith('.converted.xml') and 'worldsector' in file:
                    worldsectors_available = True
                    print(f"Found worldsector file: {file}")
                    break
    
    if not worldsectors_available:
        reply = QMessageBox.question(
            editor,
            "No Worldsectors Available",
            "No worldsector files are currently available for import.\n\n"
            "Entities need to be imported into worldsectors. Would you like to load worldsectors first?\n\n"
            "Available options:\n"
            "• Load Level Objects (recommended)\n"
            "• Load individual worldsector files",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Trigger load worldsectors
            if hasattr(editor, 'load_level_objects'):
                editor.load_level_objects()
                return
        else:
            return
    
    # Show import dialog
    dialog = EntityImportDialog(editor)
    dialog.exec()

def setup_entity_export_import_system(editor):
    """Setup the complete entity export/import system"""
    
    # Ensure objects folder exists
    objects_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "objects")
    if not os.path.exists(objects_folder):
        os.makedirs(objects_folder)
        print(f"Created objects folder: {objects_folder}")
    
    # Add generate_new_entity_id method to editor if it doesn't exist
    if not hasattr(editor, 'generate_new_entity_id'):
        def generate_new_entity_id(self):
            """Generate a new unique entity ID"""
            existing_ids = set()
            for entity in self.entities:
                try:
                    existing_ids.add(int(entity.id))
                except:
                    pass
            
            # Start from a high number to avoid conflicts
            new_id = 900000
            while new_id in existing_ids:
                new_id += 1
            
            return new_id
        
        # Bind the method to the editor instance
        import types
        editor.generate_new_entity_id = types.MethodType(generate_new_entity_id, editor)
            
    print("✅ Entity Export/Import system setup complete")


# Utility function to validate exported entities
def validate_exported_entity(xml_path):
    """Validate an exported entity XML file"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Check basic structure
        if root.tag != "object":
            return False, "Root element is not 'object'"
        
        # Check for essential fields
        essential_fields = ['hidName', 'disEntityId', 'hidPos']
        for field_name in essential_fields:
            # Check both formats
            fcb_field = root.find(f".//field[@name='{field_name}']")
            dunia_field = root.find(f".//value[@name='{field_name}']")
            
            if fcb_field is None and dunia_field is None:
                return False, f"Missing essential field: {field_name}"
        
        return True, "Valid entity XML"
        
    except Exception as e:
        return False, f"Parse error: {str(e)}"


# Utility function to batch export entities
def batch_export_entities(editor, entity_list, collection_name, output_folder=None):
    """Batch export multiple entities programmatically"""
    try:
        if output_folder is None:
            output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "objects")
        
        collection_folder = os.path.join(output_folder, collection_name)
        if not os.path.exists(collection_folder):
            os.makedirs(collection_folder)
        
        exported_count = 0
        for i, entity in enumerate(entity_list):
            # Create filename
            safe_name = entity.name.replace('/', '_').replace('\\', '_')
            xml_filename = f"{safe_name}_{i+1:03d}.xml"
            xml_path = os.path.join(collection_folder, xml_filename)
            
            # Export entity
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                import copy
                xml_copy = copy.deepcopy(entity.xml_element)
                
                # Update position
                XMLHelper.update_entity_position(xml_copy, entity.x, entity.y, entity.z)
                
                # Write to file
                tree = ET.ElementTree(xml_copy)
                tree.write(xml_path, encoding='utf-8', xml_declaration=True)
                
                exported_count += 1
        
        print(f"✓ Batch exported {exported_count} entities to {collection_folder}")
        return True, exported_count
        
    except Exception as e:
        print(f"✗ Batch export failed: {e}")
        return False, 0
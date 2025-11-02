# all_in_one_copy_paste.py
# Enhanced copy/paste system that works like export/import for all entity types

import json
import xml.etree.ElementTree as ET
import copy
import os
import time
import random
import struct
import types
from PyQt6.QtWidgets import QApplication, QMessageBox, QMenu
from PyQt6.QtCore import QMimeData
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from data_models import Entity

class EntityClipboard:
    """Handles copy/paste operations for entities using export/import methodology"""
    
    def __init__(self):
        self.clipboard_data = None
        
    def copy_entities(self, entities):
        """Copy entities to clipboard using export methodology"""
        if not entities:
            return False
            
        try:
            serialized_entities = []
            
            for entity in entities:
                print(f"Copying entity: {entity.name}")
                
                # Use the same approach as entity export - work with the complete XML element
                if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                    # Make a complete deep copy of the XML element
                    xml_copy = copy.deepcopy(entity.xml_element)
                    
                    # Remove any existing export-specific attributes that might be there
                    export_attrs = ['type', 'exported_name', 'exported_id', 'export_version', 'exported_position']
                    for attr in export_attrs:
                        if attr in xml_copy.attrib:
                            del xml_copy.attrib[attr]
                    
                    # Convert to string for storage (same as export system)
                    xml_string = ET.tostring(xml_copy, encoding='unicode')
                    
                    entity_data = {
                        'id': entity.id,
                        'name': entity.name,
                        'x': entity.x,
                        'y': entity.y,
                        'z': entity.z,
                        'xml': xml_string,
                        'source_file': getattr(entity, 'source_file', 'unknown'),
                        'source_file_path': getattr(entity, 'source_file_path', None),
                        'map_name': getattr(entity, 'map_name', None),
                        'entity_type': getattr(entity, 'entity_type', None),
                        'has_xml_element': True
                    }
                else:
                    print(f"Warning: Entity {entity.name} has no XML element")
                    # Fallback for entities without XML elements
                    entity_data = {
                        'id': entity.id,
                        'name': entity.name,
                        'x': entity.x,
                        'y': entity.y,
                        'z': entity.z,
                        'xml': None,
                        'source_file': getattr(entity, 'source_file', 'unknown'),
                        'source_file_path': getattr(entity, 'source_file_path', None),
                        'map_name': getattr(entity, 'map_name', None),
                        'entity_type': getattr(entity, 'entity_type', None),
                        'has_xml_element': False
                    }
                
                serialized_entities.append(entity_data)
            
            clipboard_data = {
                'type': 'avatar_entities_fcb',
                'version': '2.0',
                'format': 'FCBConverter',
                'count': len(serialized_entities),
                'copy_date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'entities': serialized_entities
            }
            
            json_string = json.dumps(clipboard_data, indent=2)
            
            clipboard = QApplication.clipboard()
            mime_data = QMimeData()
            mime_data.setText(json_string)
            mime_data.setData("application/x-avatar-entities-fcb", json_string.encode())
            clipboard.setMimeData(mime_data)
            
            self.clipboard_data = clipboard_data
            
            print(f"✅ Successfully copied {len(entities)} entities")
            return True
            
        except Exception as e:
            print(f"❌ Error copying entities: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def paste_entities(self, target_position=None, id_generator=None, name_generator=None):
        """Paste entities from clipboard using import methodology"""
        try:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            
            clipboard_data = None
            
            # Try to get clipboard data
            if mime_data.hasFormat("application/x-avatar-entities-fcb"):
                json_string = mime_data.data("application/x-avatar-entities-fcb").data().decode()
                clipboard_data = json.loads(json_string)
            elif mime_data.hasText():
                try:
                    json_string = mime_data.text()
                    clipboard_data = json.loads(json_string)
                    if not (clipboard_data.get('type') in ['avatar_entities', 'avatar_entities_fcb'] and 'entities' in clipboard_data):
                        clipboard_data = None
                except json.JSONDecodeError:
                    clipboard_data = None
            
            if clipboard_data is None:
                clipboard_data = self.clipboard_data
                
            if clipboard_data is None:
                print("No entity data found in clipboard")
                return []
            
            entities_data = clipboard_data.get('entities', [])
            if not entities_data:
                print("No entities found in clipboard data")
                return []
            
            print(f"Pasting {len(entities_data)} entities using import methodology...")
            
            # Calculate offset if target position is specified
            offset_x = offset_y = offset_z = 0
            if target_position and entities_data:
                first_entity = entities_data[0]
                offset_x = target_position[0] - first_entity['x']
                offset_y = target_position[1] - first_entity['y']
                offset_z = target_position[2] - first_entity['z']
                print(f"Applying offset: ({offset_x:.1f}, {offset_y:.1f}, {offset_z:.1f})")
            
            # Get all existing entity IDs and names to ensure uniqueness
            existing_ids = self._get_all_existing_entity_ids()
            existing_names = self._get_all_existing_entity_names()
            print(f"Found {len(existing_ids)} existing entity IDs and {len(existing_names)} existing names")
            
            # Process entities using import methodology
            new_entities = []
            
            for i, entity_data in enumerate(entities_data):
                try:
                    print(f"\nProcessing entity {i+1}: {entity_data['name']}")
                    
                    if entity_data.get('has_xml_element', True) and entity_data.get('xml'):
                        # Parse the complete XML structure (same as import system)
                        xml_element = ET.fromstring(entity_data['xml'])
                        
                        # Generate new unique entity ID
                        new_id = self._generate_unique_entity_id(existing_ids, id_generator)
                        existing_ids.add(new_id)
                        
                        # Generate new unique entity name
                        new_name = self._generate_unique_entity_name(entity_data['name'], existing_names, name_generator)
                        existing_names.add(new_name)
                        
                        print(f"  Generated unique ID: {new_id}")
                        print(f"  Generated unique name: {new_name}")
                        
                        # Update the entity XML with new values (same as import system)
                        self._update_entity_id_in_xml(xml_element, new_id)
                        self._update_entity_name_in_xml(xml_element, new_name)
                        
                        # Calculate new position
                        new_x = entity_data['x'] + offset_x
                        new_y = entity_data['y'] + offset_y
                        new_z = entity_data['z'] + offset_z
                        
                        print(f"  New position: ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
                        
                        # Update position in XML (same as import system)
                        self._update_entity_position_in_xml(xml_element, new_x, new_y, new_z)
                        
                        # Create new Entity object
                        entity = Entity(
                            id=str(new_id),
                            name=new_name,
                            x=new_x,
                            y=new_y,
                            z=new_z,
                            xml_element=xml_element
                        )
                        
                    else:
                        # Fallback for entities without XML elements
                        print(f"  Entity has no XML element, creating basic entity")
                        
                        new_id = self._generate_unique_entity_id(existing_ids, id_generator)
                        existing_ids.add(new_id)
                        
                        new_name = self._generate_unique_entity_name(entity_data['name'], existing_names, name_generator)
                        existing_names.add(new_name)
                        
                        new_x = entity_data['x'] + offset_x
                        new_y = entity_data['y'] + offset_y
                        new_z = entity_data['z'] + offset_z
                        
                        entity = Entity(
                            id=str(new_id),
                            name=new_name,
                            x=new_x,
                            y=new_y,
                            z=new_z
                        )
                    
                    # Set additional attributes from original entity
                    entity.source_file = entity_data.get('source_file', 'worldsectors')
                    entity.source_file_path = entity_data.get('source_file_path', None)
                    entity.map_name = entity_data.get('map_name', None)
                    entity.entity_type = entity_data.get('entity_type', None)
                    
                    new_entities.append(entity)
                    print(f"  ✅ Successfully created entity: {entity.name}")
                    
                except Exception as e:
                    print(f"  ❌ Error processing entity {i+1}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"✅ Successfully pasted {len(new_entities)} entities")
            return new_entities
            
        except Exception as e:
            print(f"❌ Error pasting entities: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _update_entity_position_in_xml(self, xml_element, new_x, new_y, new_z):
        """Update entity position in XML using the same method as import system"""
        try:
            # Check if this is FCBConverter format (has field elements)
            pos_field = xml_element.find(".//field[@name='hidPos']")
            if pos_field is not None:
                # FCBConverter format
                pos_field.set('value-Vector3', f"{new_x:.0f},{new_y:.0f},{new_z:.0f}")
                # Update binary hex data
                binary_hex = self._coordinates_to_binhex(new_x, new_y, new_z)
                pos_field.text = binary_hex
                print(f"    Updated hidPos (FCB format): ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
            else:
                # Dunia Tools format (has value elements)
                pos_elem = xml_element.find(".//value[@name='hidPos']")
                if pos_elem is not None:
                    x_elem = pos_elem.find("./x")
                    y_elem = pos_elem.find("./y")
                    z_elem = pos_elem.find("./z")
                    
                    if x_elem is not None:
                        x_elem.text = f"{new_x:.0f}"
                    if y_elem is not None:
                        y_elem.text = f"{new_y:.0f}"
                    if z_elem is not None:
                        z_elem.text = f"{new_z:.0f}"
                    print(f"    Updated hidPos (Dunia format): ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
                else:
                    print(f"    Warning: hidPos field not found in entity XML")
            
            # Also update hidPos_precise if it exists
            pos_precise_field = xml_element.find(".//field[@name='hidPos_precise']")
            if pos_precise_field is not None:
                # FCBConverter format
                pos_precise_field.set('value-Vector3', f"{new_x:.0f},{new_y:.0f},{new_z:.0f}")
                # Update binary hex data
                binary_hex = self._coordinates_to_binhex(new_x, new_y, new_z)
                pos_precise_field.text = binary_hex
                print(f"    Updated hidPos_precise (FCB format): ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
            else:
                # Dunia Tools format
                pos_precise_elem = xml_element.find(".//value[@name='hidPos_precise']")
                if pos_precise_elem is not None:
                    x_elem = pos_precise_elem.find("./x")
                    y_elem = pos_precise_elem.find("./y")
                    z_elem = pos_precise_elem.find("./z")
                    
                    if x_elem is not None:
                        x_elem.text = f"{new_x:.0f}"
                    if y_elem is not None:
                        y_elem.text = f"{new_y:.0f}"
                    if z_elem is not None:
                        z_elem.text = f"{new_z:.0f}"
                    print(f"    Updated hidPos_precise (Dunia format): ({new_x:.1f}, {new_y:.1f}, {new_z:.1f})")
            
        except Exception as e:
            print(f"    Error updating entity position: {e}")

    def _coordinates_to_binhex(self, x, y, z):
        """Convert coordinates to BinHex format (same as import system)"""
        try:
            import struct
            binary_data = struct.pack('<fff', float(x), float(y), float(z))
            hex_string = binary_data.hex().upper()
            return hex_string
        except Exception as e:
            print(f"Error converting coordinates to BinHex: {e}")
            return "000000000000000000000000"  # Return zeros on error
    
    def _update_entity_id_in_xml(self, xml_element, new_id):
        """Update entity ID in XML using the same method as import system"""
        try:
            # Check if this is FCBConverter format (has field elements)
            id_field = xml_element.find(".//field[@name='disEntityId']")
            if id_field is not None:
                # FCBConverter format
                id_field.set('value-Id64', str(new_id))
                # Update binary hex data
                binary_hex = self._int64_to_binhex(new_id)
                id_field.text = binary_hex
                print(f"    Updated disEntityId (FCB format): {new_id}")
            else:
                # Dunia Tools format (has value elements)
                id_elem = xml_element.find(".//value[@name='disEntityId']")
                if id_elem is not None:
                    id_elem.text = str(new_id)
                    print(f"    Updated disEntityId (Dunia format): {new_id}")
                else:
                    print(f"    Warning: disEntityId field not found in entity XML")
        except Exception as e:
            print(f"    Error updating entity ID: {e}")

    def _update_entity_name_in_xml(self, xml_element, new_name):
        """Update entity name in XML using the same method as import system"""
        try:
            # Check if this is FCBConverter format (has field elements)
            name_field = xml_element.find(".//field[@name='hidName']")
            if name_field is not None:
                # FCBConverter format
                name_field.set('value-String', new_name)
                # Update binary hex data
                binary_hex = self._string_to_binhex(new_name)
                name_field.text = binary_hex
                print(f"    Updated hidName (FCB format): {new_name}")
            else:
                # Dunia Tools format (has value elements)
                name_elem = xml_element.find(".//value[@name='hidName']")
                if name_elem is not None:
                    name_elem.text = new_name
                    print(f"    Updated hidName (Dunia format): {new_name}")
                else:
                    print(f"    Warning: hidName field not found in entity XML")
        except Exception as e:
            print(f"    Error updating entity name: {e}")

    def _int64_to_binhex(self, value):
        """Convert 64-bit integer to BinHex format (same as import system)"""
        try:
            binary_data = struct.pack('<Q', int(value))
            return binary_data.hex().upper()
        except:
            return "0000000000000000"

    def _string_to_binhex(self, text):
        """Convert string to BinHex format (same as import system)"""
        try:
            # Encode string as UTF-8 and add null terminator
            binary_data = text.encode('utf-8') + b'\x00'
            hex_string = binary_data.hex().upper()
            return hex_string
        except Exception as e:
            print(f"Error converting string '{text}' to BinHex: {e}")
            return "00"  # Return just null terminator on error

    def _get_all_existing_entity_ids(self):
        """Get all existing entity IDs to ensure uniqueness"""
        existing_ids = set()
        # This method needs access to the editor's data
        # It will be called with proper context from the bound methods
        return existing_ids

    def _get_all_existing_entity_names(self):
        """Get all existing entity names to ensure uniqueness"""
        existing_names = set()
        # This method needs access to the editor's data
        # It will be called with proper context from the bound methods
        return existing_names

    def _generate_unique_entity_id(self, existing_ids, id_generator=None):
        """Generate a unique entity ID"""
        # Try the provided generator first
        if id_generator:
            for _ in range(100):
                try:
                    new_id = int(id_generator())
                    if new_id not in existing_ids:
                        return new_id
                except:
                    continue
        
        # Fallback: generate based on timestamp and random component
        base_id = int(time.time() * 1000000)
        
        for attempt in range(1000):
            new_id = base_id + random.randint(1000, 999999) + attempt
            
            # Ensure it's in valid range for 64-bit signed integer
            if new_id > 9223372036854775807:
                new_id = random.randint(1000000000000000000, 9000000000000000000)
            
            if new_id not in existing_ids:
                return new_id
        
        # Last resort: simple incremental
        max_id = max(existing_ids) if existing_ids else 1000000000000000000
        return max_id + 1

    def _generate_unique_entity_name(self, original_name, existing_names, name_generator=None):
        """Generate a unique entity name"""
        if name_generator:
            try:
                new_name = name_generator(original_name)
                if new_name not in existing_names:
                    return new_name
            except Exception as e:
                print(f"Name generator error: {e}")
        
        # Default naming strategy: append _Copy_N
        base_name = original_name
        
        # Remove existing _Copy_N suffix if present
        import re
        match = re.match(r'^(.+)_Copy_(\d+)$', original_name)
        if match:
            base_name = match.group(1)
        
        # Try _Copy first
        copy_name = f"{base_name}_Copy"
        if copy_name not in existing_names:
            return copy_name
        
        # Try _Copy_N
        for i in range(1, 1000):
            candidate_name = f"{base_name}_Copy_{i}"
            if candidate_name not in existing_names:
                return candidate_name
        
        # Last resort: add timestamp
        timestamp = int(time.time()) % 100000
        return f"{base_name}_Copy_{timestamp}"
    
    def has_clipboard_data(self):
        """Check if clipboard contains entity data"""
        try:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            
            if mime_data.hasFormat("application/x-avatar-entities-fcb"):
                return True
            
            if mime_data.hasText():
                try:
                    json_string = mime_data.text()
                    clipboard_data = json.loads(json_string)
                    return clipboard_data.get('type') in ['avatar_entities', 'avatar_entities_fcb']
                except json.JSONDecodeError:
                    pass
            
            return self.clipboard_data is not None
            
        except Exception:
            return False
    
    def get_clipboard_info(self):
        """Get information about clipboard contents"""
        try:
            clipboard = QApplication.clipboard()
            mime_data = clipboard.mimeData()
            
            clipboard_data = None
            
            if mime_data.hasFormat("application/x-avatar-entities-fcb"):
                json_string = mime_data.data("application/x-avatar-entities-fcb").data().decode()
                clipboard_data = json.loads(json_string)
            elif mime_data.hasText():
                try:
                    json_string = mime_data.text()
                    clipboard_data = json.loads(json_string)
                    if clipboard_data.get('type') not in ['avatar_entities', 'avatar_entities_fcb']:
                        clipboard_data = None
                except json.JSONDecodeError:
                    clipboard_data = None
            
            if clipboard_data is None:
                clipboard_data = self.clipboard_data
            
            if clipboard_data is None:
                return None
            
            return {
                'count': clipboard_data.get('count', 0),
                'version': clipboard_data.get('version', 'unknown'),
                'copy_date': clipboard_data.get('copy_date', 'unknown'),
                'entities': [entity['name'] for entity in clipboard_data.get('entities', [])]
            }
            
        except Exception:
            return None


def setup_complete_smart_system(editor):
    """Setup copy/paste system using export/import methodology"""
    print("Setting up enhanced copy/paste system using export/import methodology...")
    
    # Initialize clipboard system
    editor.entity_clipboard = EntityClipboard()
    editor.next_entity_id = 3000000000000000000
    editor._remove_entity_from_worldsector_fixed = types.MethodType(_remove_entity_from_worldsector_fixed, editor)
    editor.test_entity_deletion = types.MethodType(test_entity_deletion, editor)
    
    def generate_new_entity_id(self):
        self.next_entity_id += 1
        return str(self.next_entity_id)
    
    def generate_unique_entity_name(self, original_name):
        """Generate a unique entity name with smart naming"""
        # Remove common prefixes that indicate copies
        import re
        
        # Pattern to match existing copy naming
        copy_pattern = r'^(.+?)(?:_Copy(?:_\d+)?)?$'
        match = re.match(copy_pattern, original_name)
        base_name = match.group(1) if match else original_name
        
        # Add timestamp for uniqueness
        timestamp = int(time.time()) % 10000
        return f"{base_name}_Copy_{timestamp}"
    
    def get_all_existing_entity_ids(self):
        """Get all existing entity IDs from editor data"""
        existing_ids = set()
        
        # Check main entities list
        if hasattr(self, 'entities'):
            for entity in self.entities:
                try:
                    entity_id = int(entity.id)
                    existing_ids.add(entity_id)
                except (ValueError, AttributeError):
                    pass
        
        # Check worldsector XML trees for entity IDs
        if hasattr(self, 'worldsectors_trees'):
            for file_path, tree in self.worldsectors_trees.items():
                try:
                    root = tree.getroot()
                    for id_field in root.findall(".//field[@name='disEntityId']"):
                        id_value = id_field.get('value-Id64')
                        if id_value:
                            try:
                                entity_id = int(id_value)
                                existing_ids.add(entity_id)
                            except ValueError:
                                pass
                except Exception as e:
                    print(f"Error scanning {file_path} for entity IDs: {e}")
        
        return existing_ids
    
    def get_all_existing_entity_names(self):
        """Get all existing entity names from editor data"""
        existing_names = set()
        
        # Check main entities list
        if hasattr(self, 'entities'):
            for entity in self.entities:
                if hasattr(entity, 'name') and entity.name:
                    existing_names.add(entity.name)
        
        # Check worldsector XML trees for entity names
        if hasattr(self, 'worldsectors_trees'):
            for file_path, tree in self.worldsectors_trees.items():
                try:
                    root = tree.getroot()
                    for name_field in root.findall(".//field[@name='hidName']"):
                        name_value = name_field.get('value-String')
                        if name_value:
                            existing_names.add(name_value)
                except Exception as e:
                    print(f"Error scanning {file_path} for entity names: {e}")
        
        return existing_names
    
    def copy_selected_entities(self):
        if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'selected'):
            return False
            
        selected_entities = getattr(self.canvas, 'selected', [])
        if not selected_entities:
            self.status_bar.showMessage("No entities selected to copy")
            return False
        
        success = self.entity_clipboard.copy_entities(selected_entities)
        if success:
            self.status_bar.showMessage(f"Copied {len(selected_entities)} entities to clipboard")
        else:
            self.status_bar.showMessage("Failed to copy entities")
        
        return success
    
    def paste_entities(self, target_position=None, at_cursor=False):
        """Paste entities using import methodology with automatic +20 X/Y offset or cursor position"""
        # Calculate target position if pasting at cursor
        if at_cursor and hasattr(self, 'canvas') and hasattr(self.canvas, 'last_mouse_world_pos'):
            target_position = self.canvas.last_mouse_world_pos
        
        # Bind the helper methods to the clipboard so it can access editor data
        self.entity_clipboard._get_all_existing_entity_ids = lambda: self.get_all_existing_entity_ids()
        self.entity_clipboard._get_all_existing_entity_names = lambda: self.get_all_existing_entity_names()
        
        # If no target position specified, apply automatic +20 X/Y offset
        if target_position is None:
            # Get clipboard data to calculate offset from first entity
            clipboard_data = None
            try:
                clipboard = QApplication.clipboard()
                mime_data = clipboard.mimeData()
                
                if mime_data.hasFormat("application/x-avatar-entities-fcb"):
                    json_string = mime_data.data("application/x-avatar-entities-fcb").data().decode()
                    clipboard_data = json.loads(json_string)
                elif mime_data.hasText():
                    try:
                        json_string = mime_data.text()
                        clipboard_data = json.loads(json_string)
                        if not (clipboard_data.get('type') in ['avatar_entities', 'avatar_entities_fcb'] and 'entities' in clipboard_data):
                            clipboard_data = None
                    except json.JSONDecodeError:
                        clipboard_data = None
                
                if clipboard_data is None:
                    clipboard_data = self.entity_clipboard.clipboard_data
                
                # Calculate automatic offset position
                if clipboard_data and clipboard_data.get('entities'):
                    first_entity = clipboard_data['entities'][0]
                    target_position = (
                        first_entity['x'] + 20,  # +20 on X axis
                        first_entity['y'] + 20,  # +20 on Y axis  
                        first_entity['z']        # Keep Z the same
                    )
                    print(f"Auto-offsetting paste by +20 X/Y: {target_position}")
            except Exception as e:
                print(f"Error calculating auto-offset: {e}")
                target_position = None
        
        # Use import-style pasting
        new_entities = self.entity_clipboard.paste_entities(
            target_position=target_position,
            id_generator=self.generate_new_entity_id,
            name_generator=self.generate_unique_entity_name
        )
        
        if not new_entities:
            self.status_bar.showMessage("No entities to paste")
            return []
        
        print(f"\n=== PASTING {len(new_entities)} ENTITIES USING IMPORT METHODOLOGY ===")
        
        # Process each entity using import-style approach
        successfully_added = []
        for i, entity in enumerate(new_entities):
            print(f"\nProcessing entity {i+1}: {entity.name}")
            print(f"  Entity ID: {entity.id}")
            print(f"  Position: ({entity.x}, {entity.y}, {entity.z})")
            print(f"  Has XML element: {hasattr(entity, 'xml_element') and entity.xml_element is not None}")
            
            # Add to main entities list
            self.entities.append(entity)
            
            # Add to worldsector XML using import methodology
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                # Find target worldsector file (same logic as import system)
                target_sector_file = self._find_best_worldsector_for_entity(entity)
                
                if target_sector_file:
                    print(f"  Adding to worldsector: {os.path.basename(target_sector_file)}")
                    
                    # Use the same method as import system
                    success = self._add_entity_xml_to_sector(entity.xml_element, target_sector_file)
                    if success:
                        entity.source_file_path = target_sector_file
                        entity.source_file = "worldsectors"
                        successfully_added.append(entity)
                        print(f"  ✅ Successfully added to worldsector")
                    else:
                        print(f"  ⚠️ Failed to add to worldsector, but entity added to main list")
                        successfully_added.append(entity)
                else:
                    print(f"  ⚠️ No suitable worldsector found, adding to main list only")
                    successfully_added.append(entity)
            else:
                print(f"  Entity has no XML element, adding to main list only")
                successfully_added.append(entity)
        
        # Update UI
        self.canvas.set_entities(self.entities)
        if hasattr(self, 'update_entity_tree'):
            self.update_entity_tree()
        
        # Select the pasted entities
        self.canvas.selected = new_entities
        self.canvas.selected_entity = new_entities[0] if new_entities else None
        self.selected_entity = self.canvas.selected_entity
        
        self.canvas.update()
        if hasattr(self, 'update_ui_for_selected_entity'):
            self.update_ui_for_selected_entity(self.selected_entity)
        
        self.status_bar.showMessage(f"Pasted {len(successfully_added)} entities")
        print(f"=== PASTE COMPLETE: {len(successfully_added)} entities ===\n")
        return new_entities

    def _find_best_worldsector_for_entity(self, entity):
        """Find the best worldsector file for an entity (same logic as import system)"""
        x, y = entity.x, entity.y
        print(f"🎯 Finding target worldsector for {entity.name} at ({x}, {y})")
        
        # Initialize worldsectors_trees if needed
        if not hasattr(self, 'worldsectors_trees'):
            self.worldsectors_trees = {}
        
        # Get all available worldsector files
        available_files = list(self.worldsectors_trees.keys()) if self.worldsectors_trees else []
        print(f"🗂️  Available worldsector files: {len(available_files)}")
        
        if not available_files:
            print("❌ No worldsector files loaded")
            return None
        
        # Use the first available file as fallback (same as import system)
        fallback_file = available_files[0]
        print(f"📁 Using worldsector file: {fallback_file}")
        return fallback_file

    def _add_entity_xml_to_sector(self, entity_xml, sector_file_path):
        """Add entity XML directly to the target worldsector file (same as import system)"""
        try:
            # Load the target file if not already loaded
            if not hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees = {}
            
            if sector_file_path not in self.worldsectors_trees:
                if os.path.exists(sector_file_path):
                    tree = ET.parse(sector_file_path)
                    self.worldsectors_trees[sector_file_path] = tree
                else:
                    print(f"Sector file does not exist: {sector_file_path}")
                    return False
            
            tree = self.worldsectors_trees[sector_file_path]
            root = tree.getroot()
            
            # Find MissionLayer
            mission_layer = root.find(".//object[@name='MissionLayer']")
            if mission_layer is None:
                print(f"No MissionLayer found in {sector_file_path}")
                return False
            
            # Add entity XML directly to MissionLayer
            mission_layer.append(entity_xml)
            
            # Save the file
            tree.write(sector_file_path, encoding='utf-8', xml_declaration=True)
            
            # Mark as modified
            if not hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified = {}
            self.worldsectors_modified[sector_file_path] = True
            
            return True
            
        except Exception as e:
            print(f"Error adding entity to sector: {e}")
            return False
    
    def duplicate_selected_entities(self):
        """Duplicate selected entities with +20 X/Y offset and unique names"""
        if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'selected'):
            return False
            
        selected_entities = getattr(self.canvas, 'selected', [])
        if not selected_entities:
            self.status_bar.showMessage("No entities selected to duplicate")
            return False
        
        # Copy to clipboard
        success = self.entity_clipboard.copy_entities(selected_entities)
        if not success:
            return False
        
        # Calculate offset position (+20 X/Y from first selected entity)
        if selected_entities:
            first_entity = selected_entities[0]
            offset_position = (
                first_entity.x + 20,  # +20 on X axis
                first_entity.y + 20,  # +20 on Y axis
                first_entity.z        # Keep Z the same
            )
            print(f"Duplicating with +20 X/Y offset: {offset_position}")
        else:
            offset_position = None
        
        # Paste with offset
        new_entities = self.paste_entities(target_position=offset_position)
        
        if new_entities:
            self.status_bar.showMessage(f"Duplicated {len(new_entities)} entities with +20 X/Y offset")
            return True
        else:
            self.status_bar.showMessage("Failed to duplicate entities")
            return False
        
    def delete_selected_entities(self):
        """Delete selected entities from both memory and XML"""
        if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'selected'):
            return False
            
        selected_entities = getattr(self.canvas, 'selected', [])
        if not selected_entities:
            self.status_bar.showMessage("No entities selected to delete")
            return False
        
        reply = QMessageBox.question(
            self,
            "Delete Entities",
            f"Are you sure you want to delete {len(selected_entities)} entities?\n\n"
            f"This will remove them from both the display and the XML files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return False
        
        print(f"\n🗑️ DELETING {len(selected_entities)} entities...")
        
        deleted_count = 0
        
        # Remove entities from worldsector XML trees and main entities list
        for entity in selected_entities:
            print(f"\n🗑️ Processing deletion of: {entity.name}")
            
            # Remove from worldsector XML if applicable
            if hasattr(entity, 'source_file_path') and entity.source_file_path:
                if hasattr(self, 'worldsectors_trees') and entity.source_file_path in self.worldsectors_trees:
                    print(f"  Removing from worldsector XML: {os.path.basename(entity.source_file_path)}")
                    
                    try:
                        success = self._remove_entity_from_worldsector_fixed(entity)
                        if success:
                            print(f"  ✅ Successfully removed from XML")
                        else:
                            print(f"  ⚠️ Failed to remove from XML, but continuing...")
                            
                    except Exception as e:
                        print(f"  ❌ Error removing from XML: {e}")
                else:
                    print(f"  ⚠️ WorldSector file not loaded: {entity.source_file_path}")
            else:
                print(f"  📋 Entity is from main file, not worldsector")
            
            # Remove from main entities list
            if entity in self.entities:
                self.entities.remove(entity)
                deleted_count += 1
                print(f"  ✅ Removed from main entities list")
            else:
                print(f"  ⚠️ Entity not found in main entities list")
        
        # Clear selection
        self.canvas.selected = []
        self.canvas.selected_entity = None
        self.selected_entity = None
        
        # Update UI
        self.canvas.set_entities(self.entities)
        if hasattr(self, 'update_entity_tree'):
            self.update_entity_tree()
        
        self.canvas.update()
        self.status_bar.showMessage(f"Deleted {deleted_count} entities from display and XML")
        
        print(f"🗑️ DELETION COMPLETE: {deleted_count} entities removed")
        return True

    def select_all_entities(self):
        """Select all visible entities"""
        if not hasattr(self, 'canvas'):
            return False
        
        visible_entities = []
        for entity in self.entities:
            if hasattr(self, 'current_map') and self.current_map is not None and hasattr(entity, 'map_name') and entity.map_name != self.current_map.name:
                continue
            visible_entities.append(entity)
        
        if not visible_entities:
            self.status_bar.showMessage("No entities to select")
            return False
        
        self.canvas.selected = visible_entities
        self.canvas.selected_entity = visible_entities[0] if visible_entities else None
        self.selected_entity = self.canvas.selected_entity
        
        if hasattr(self, 'update_ui_for_selected_entity'):
            self.update_ui_for_selected_entity(self.selected_entity)
        
        self.canvas.update()
        self.status_bar.showMessage(f"Selected {len(visible_entities)} entities")
        return True
    
    def show_clipboard_info(self):
        """Show clipboard information"""
        info = self.entity_clipboard.get_clipboard_info()
        if info is None:
            self.status_bar.showMessage("No entity data in clipboard")
            return
        
        entity_names = info['entities'][:5]
        if len(info['entities']) > 5:
            entity_names.append(f"... and {len(info['entities']) - 5} more")
        
        QMessageBox.information(
            self,
            "Clipboard Contents",
            f"Entity count: {info['count']}\n"
            f"Version: {info['version']}\n"
            f"Copied: {info.get('copy_date', 'unknown')}\n\n"
            f"Entities:\n" + "\n".join([f"• {name}" for name in entity_names])
        )
    
    # Bind methods to editor
    editor.generate_new_entity_id = types.MethodType(generate_new_entity_id, editor)
    editor.generate_unique_entity_name = types.MethodType(generate_unique_entity_name, editor)
    editor.get_all_existing_entity_ids = types.MethodType(get_all_existing_entity_ids, editor)
    editor.get_all_existing_entity_names = types.MethodType(get_all_existing_entity_names, editor)
    editor.copy_selected_entities = types.MethodType(copy_selected_entities, editor)
    editor.paste_entities = types.MethodType(paste_entities, editor)
    editor.duplicate_selected_entities = types.MethodType(duplicate_selected_entities, editor)
    editor.delete_selected_entities = types.MethodType(delete_selected_entities, editor)
    editor.select_all_entities = types.MethodType(select_all_entities, editor)
    editor.show_clipboard_info = types.MethodType(show_clipboard_info, editor)
    editor._find_best_worldsector_for_entity = types.MethodType(_find_best_worldsector_for_entity, editor)
    editor._add_entity_xml_to_sector = types.MethodType(_add_entity_xml_to_sector, editor)
    
    # Setup UI
    setup_ui_integration(editor)
    setup_keyboard_shortcuts(editor)
    
    print("✅ Enhanced copy/paste system setup complete using export/import methodology!")


def _remove_entity_from_worldsector_fixed(self, entity):
    """Remove entity from its worldsector XML file - FIXED for FCBConverter format and multiple MissionLayers"""
    try:
        source_file = entity.source_file_path
        print(f"\n🔧 Removing {entity.name} from {os.path.basename(source_file)}")
        
        # Auto-load source file if not already loaded
        if not hasattr(self, 'worldsectors_trees'):
            self.worldsectors_trees = {}
        
        if source_file not in self.worldsectors_trees:
            if os.path.exists(source_file):
                try:
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(source_file)
                    self.worldsectors_trees[source_file] = tree
                    print(f"🔧 Auto-loaded source file: {os.path.basename(source_file)}")
                except Exception as e:
                    print(f"❌ Error loading source file {source_file}: {e}")
                    return False
            else:
                print(f"❌ Source file does not exist: {source_file}")
                return False
        
        tree = self.worldsectors_trees[source_file]
        root = tree.getroot()
        
        # Find ALL MissionLayers - there can be multiple in worldsector files
        mission_layers = root.findall(".//object[@name='MissionLayer']")
        if not mission_layers:
            print(f"❌ No MissionLayer found in {source_file}")
            return False
        
        print(f"📋 Found {len(mission_layers)} MissionLayer(s) in file")
        
        entity_to_remove = None
        source_mission_layer = None
        
        # Search through ALL MissionLayers
        for layer_idx, mission_layer in enumerate(mission_layers):
            print(f"\n🔍 Checking MissionLayer {layer_idx + 1}/{len(mission_layers)}")
            print(f"📋 This MissionLayer has {len(mission_layer)} children")
            
            # Look for entities directly under this MissionLayer
            entities_in_layer = mission_layer.findall("object[@name='Entity']")
            print(f"🔍 Found {len(entities_in_layer)} Entity objects in this MissionLayer")
            
            # Search through entities in FCBConverter format
            for i, entity_elem in enumerate(entities_in_layer):
                print(f"🔍 Checking entity {i+1}/{len(entities_in_layer)}")
                
                # Look for hidName field (FCBConverter format)
                name_field = entity_elem.find("field[@name='hidName']")
                if name_field is not None:
                    stored_name = name_field.get('value-String')
                    print(f"   Name in XML: '{stored_name}'")
                    print(f"   Looking for: '{entity.name}'")
                    
                    if stored_name == entity.name:
                        print(f"✅ FOUND MATCH: {entity.name} in MissionLayer {layer_idx + 1}")
                        entity_to_remove = entity_elem
                        source_mission_layer = mission_layer
                        break
                    else:
                        print(f"❌ No match")
                else:
                    print(f"   No hidName field found")
            
            # If found, break out of layer loop
            if entity_to_remove is not None:
                break
            
            # If not found in FCBConverter format in this layer, try Dunia Tools format as fallback
            print(f"🔍 Trying Dunia Tools format in MissionLayer {layer_idx + 1}...")
            for entity_elem in entities_in_layer:
                name_elem = entity_elem.find("./value[@name='hidName']")
                if name_elem is not None and name_elem.text == entity.name:
                    print(f"✅ Found {entity.name} in Dunia Tools format in MissionLayer {layer_idx + 1}")
                    entity_to_remove = entity_elem
                    source_mission_layer = mission_layer
                    break
            
            # If found, break out of layer loop
            if entity_to_remove is not None:
                break
        
        if entity_to_remove is None:
            print(f"❌ Entity {entity.name} not found in any MissionLayer")
            return False
        
        # Remove the entity from the correct MissionLayer
        print(f"🗑️ Removing entity from MissionLayer")
        source_mission_layer.remove(entity_to_remove)
        
        # Verify removal
        all_entities_after = []
        for ml in mission_layers:
            all_entities_after.extend(ml.findall("object[@name='Entity']"))
        print(f"✅ Entity removed. All MissionLayers now have {len(all_entities_after)} total entities")
        
        # Save immediately
        tree.write(source_file, encoding='utf-8', xml_declaration=True)
        print(f"💾 Saved {os.path.basename(source_file)}")
        
        # Mark file as modified
        if not hasattr(self, 'worldsectors_modified'):
            self.worldsectors_modified = {}
        self.worldsectors_modified[source_file] = True
        
        return True
        
    except Exception as e:
        print(f"❌ Error removing entity: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_entity_deletion(self, entity_name):
    """Test method to debug entity deletion"""
    print(f"\n🧪 TESTING DELETION for {entity_name}")
    
    # Find the entity
    target_entity = None
    for entity in self.entities:
        if entity.name == entity_name:
            target_entity = entity
            break
    
    if not target_entity:
        print(f"❌ Entity {entity_name} not found in entities list")
        return False
    
    print(f"✅ Found entity in entities list")
    print(f"   Position: ({target_entity.x}, {target_entity.y}, {target_entity.z})")
    print(f"   Source file: {getattr(target_entity, 'source_file_path', 'None')}")
    
    # Check if entity exists in XML
    if hasattr(target_entity, 'source_file_path') and target_entity.source_file_path:
        source_file = target_entity.source_file_path
        
        if hasattr(self, 'worldsectors_trees') and source_file in self.worldsectors_trees:
            tree = self.worldsectors_trees[source_file]
            root = tree.getroot()
            
            # Count entities before deletion
            all_entities_before = root.findall(".//object[@name='Entity']")
            print(f"📊 Total entities in XML before deletion: {len(all_entities_before)}")
            
            # Find our specific entity
            found_in_xml = False
            for mission_layer in root.findall(".//object[@name='MissionLayer']"):
                for entity_elem in mission_layer.findall("object[@name='Entity']"):
                    name_field = entity_elem.find("field[@name='hidName']")
                    if name_field is not None:
                        stored_name = name_field.get('value-String')
                        if stored_name == entity_name:
                            found_in_xml = True
                            print(f"✅ Found entity in XML file")
                            break
                if found_in_xml:
                    break
            
            if not found_in_xml:
                print(f"❌ Entity not found in XML file")
                return False
        else:
            print(f"❌ Worldsector tree not loaded for {source_file}")
            return False
    else:
        print(f"⚠️ Entity has no source_file_path")
        return False
    
    # Perform the deletion test
    print(f"\n🗑️ Performing deletion...")
    success = self._remove_entity_from_worldsector_fixed(target_entity)
    
    if success:
        # Verify deletion
        all_entities_after = root.findall(".//object[@name='Entity']")
        print(f"📊 Total entities in XML after deletion: {len(all_entities_after)}")
        print(f"📊 Entities removed: {len(all_entities_before) - len(all_entities_after)}")
        
        # Check if our entity is still there
        still_found = False
        for mission_layer in root.findall(".//object[@name='MissionLayer']"):
            for entity_elem in mission_layer.findall("object[@name='Entity']"):
                name_field = entity_elem.find("field[@name='hidName']")
                if name_field is not None:
                    stored_name = name_field.get('value-String')
                    if stored_name == entity_name:
                        still_found = True
                        break
            if still_found:
                break
        
        if still_found:
            print(f"❌ Entity still found in XML after deletion!")
            return False
        else:
            print(f"✅ Entity successfully removed from XML")
            return True
    else:
        print(f"❌ Deletion failed")
        return False


def setup_ui_integration(editor):
    """Setup UI integration with enhanced features"""
    # Create Edit menu if it doesn't exist
    if not hasattr(editor, 'edit_menu'):
        editor.edit_menu = editor.menuBar().addMenu("Edit")
    
    # Add actions
    editor.edit_menu.addSeparator()
    
    copy_action = QAction("Copy Entities", editor)
    copy_action.setShortcut(QKeySequence.StandardKey.Copy)
    copy_action.triggered.connect(editor.copy_selected_entities)
    editor.edit_menu.addAction(copy_action)
    
    paste_action = QAction("Paste Entities", editor)
    paste_action.setShortcut(QKeySequence.StandardKey.Paste)
    paste_action.triggered.connect(lambda: editor.paste_entities(at_cursor=True))
    editor.edit_menu.addAction(paste_action)
    
    duplicate_action = QAction("Duplicate Entities", editor)
    duplicate_action.setShortcut("Ctrl+D")
    duplicate_action.triggered.connect(editor.duplicate_selected_entities)
    editor.edit_menu.addAction(duplicate_action)
    
    editor.edit_menu.addSeparator()
    
    select_all_action = QAction("Select All Entities", editor)
    select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
    select_all_action.triggered.connect(editor.select_all_entities)
    editor.edit_menu.addAction(select_all_action)
    
    clipboard_info_action = QAction("Show Clipboard Info", editor)
    clipboard_info_action.triggered.connect(editor.show_clipboard_info)
    editor.edit_menu.addAction(clipboard_info_action)
    
    # Setup context menu
    setup_context_menu(editor)


def setup_context_menu(self):
    """Setup enhanced context menu with all copy/paste features"""
    if hasattr(self.canvas, 'showContextMenu'):
        self.canvas._original_showContextMenu = self.canvas.showContextMenu
    
    def enhanced_showContextMenu(event):
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu(self.canvas)
        
        selected_entities = getattr(self.canvas, 'selected', [])
        has_selection = len(selected_entities) > 0
        has_clipboard = hasattr(self, 'entity_clipboard') and self.entity_clipboard.has_clipboard_data()
        
        if has_selection:
            menu.addAction(f"Selected: {len(selected_entities)} entities").setEnabled(False)
            menu.addSeparator()
            
            copy_action = menu.addAction("Copy Entities")
            copy_action.triggered.connect(self.copy_selected_entities)
            
            duplicate_action = menu.addAction("Duplicate Entities")
            duplicate_action.triggered.connect(self.duplicate_selected_entities)
            
            # CRITICAL FIX: Make sure delete is properly connected
            delete_action = menu.addAction("Delete Entities")
            delete_action.triggered.connect(self.delete_selected_entities)
            
            menu.addSeparator()
        
        if has_clipboard:
            clipboard_info = self.entity_clipboard.get_clipboard_info()
            if clipboard_info:
                paste_label = f"Paste {clipboard_info['count']} Entities"
                
                paste_action = menu.addAction(paste_label)
                paste_action.triggered.connect(lambda: self.paste_entities(at_cursor=True))
                
                paste_original_action = menu.addAction("Paste at Original Position")
                paste_original_action.triggered.connect(lambda: self.paste_entities(at_cursor=False))
                
                menu.addSeparator()
                
                clipboard_info_action = menu.addAction("Show Clipboard Info")
                clipboard_info_action.triggered.connect(self.show_clipboard_info)
                
                menu.addSeparator()
        
        # Selection actions
        if not has_selection:
            select_all_action = menu.addAction("Select All Entities")
            select_all_action.triggered.connect(self.select_all_entities)
            menu.addSeparator()
        
        # View actions
        world_x, world_y = self.canvas.screen_to_world(event.position().x(), event.position().y())
        
        center_action = menu.addAction("Center View Here")
        center_action.triggered.connect(lambda: center_view_at(self, world_x, world_y))
        
        # Add zoom actions if available
        if hasattr(self.canvas, 'zoom_in'):
            menu.addSeparator()
            zoom_in_action = menu.addAction("Zoom In")
            zoom_in_action.triggered.connect(self.canvas.zoom_in)
            
            zoom_out_action = menu.addAction("Zoom Out")
            zoom_out_action.triggered.connect(self.canvas.zoom_out)
            
            reset_view_action = menu.addAction("Reset View")
            reset_view_action.triggered.connect(self.reset_view)
        
        menu.exec(event.globalPosition().toPoint())
    
    self.canvas.showContextMenu = enhanced_showContextMenu

def center_view_at(editor, world_x, world_y):
    """Center view at coordinates"""
    if editor.canvas.mode == 0:  # 2D mode
        editor.canvas.offset_x = (editor.canvas.width() / 2) - (world_x * editor.canvas.scale_factor)
        editor.canvas.offset_y = (editor.canvas.height() / 2) - (world_y * editor.canvas.scale_factor)
    else:  # 3D mode
        editor.canvas.offset_x = -world_x
        editor.canvas.offset_z = world_y
    
    editor.canvas.update()


def setup_keyboard_shortcuts(self):
    """Setup comprehensive keyboard shortcuts"""
    from PyQt6.QtGui import QShortcut, QKeySequence
    
    # Copy (Ctrl+C)
    copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
    copy_shortcut.activated.connect(self.copy_selected_entities)
    
    # Paste (Ctrl+V)  
    paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
    paste_shortcut.activated.connect(lambda: self.paste_entities(at_cursor=True))
    
    # Duplicate (Ctrl+D)
    duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
    duplicate_shortcut.activated.connect(self.duplicate_selected_entities)
    
    # CRITICAL FIX: Delete (Delete key) - make sure this is connected
    delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, self)
    delete_shortcut.activated.connect(self.delete_selected_entities)
    
    # Select All (Ctrl+A)
    select_all_shortcut = QShortcut(QKeySequence.StandardKey.SelectAll, self)
    select_all_shortcut.activated.connect(self.select_all_entities)
    
    # Show clipboard info (Ctrl+I)
    clipboard_info_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
    clipboard_info_shortcut.activated.connect(self.show_clipboard_info)
    
    print("✅ Keyboard shortcuts setup complete including delete key")
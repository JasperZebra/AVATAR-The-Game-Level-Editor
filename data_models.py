# enhanced_data_models.py
# Enhanced data models for the Simplified Map Editor application

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import xml.etree.ElementTree as ET
from PyQt6.QtGui import QImage
import os

@dataclass
class MapInfo:
    """Map information from the grid configuration"""
    name: str
    offset_x: int
    offset_y: int
    sector_offset_x: int
    sector_offset_y: int
    count_x: int
    count_y: int
    granularity: int
    minimap_path: Optional[str] = None
    minimap_image: Optional[QImage] = None
    minimap_scale_x: float = 1.0  # Scaling factor for the X dimension
    minimap_scale_y: float = 1.0  # Scaling factor for the Y dimension
    minimap_offset_x: float = 0.0  # X offset for the minimap
    minimap_offset_y: float = 0.0  # Y offset for the minimap


@dataclass
class GridConfig:
    """Grid configuration containing sector and map information"""
    sector_count_x: int
    sector_count_y: int
    sector_granularity: int
    maps: List[MapInfo]


@dataclass
class Entity:
    """Entity representation with position and XML data"""
    id: str  # The entity ID
    name: str  # The hidName value
    x: float  # X coordinate
    y: float  # Y coordinate
    z: float  # Z coordinate
    xml_element: ET.Element  # Reference to the original XML element
    map_name: Optional[str] = None  # The map this entity belongs to
    source_file: Optional[str] = None  # Source file type (mapsdata, managers, etc.)
    entity_type: Optional[str] = None  # Type of entity (Entity, Object, etc.)


@dataclass
class ObjectEntity:
    """Object entity from .data.fcb files with enhanced properties"""
    id: str  # The object ID
    name: str  # The object name
    x: float  # X coordinate
    y: float  # Y coordinate
    z: float  # Z coordinate
    xml_element: ET.Element  # Reference to the original XML element
    map_name: Optional[str] = None  # The map this object belongs to
    source_file: Optional[str] = None  # Source .data.fcb file path
    sector_path: Optional[str] = None  # Path to the sector folder
    object_type: Optional[str] = None  # Type of object (StaticObject, DynamicObject, etc.)
    class_name: Optional[str] = None  # Object class name
    model_path: Optional[str] = None  # Path to the 3D model
    properties: Dict[str, Any] = None  # Additional object properties
    
    def __post_init__(self):
        """Initialize properties dict if None"""
        if self.properties is None:
            self.properties = {}


@dataclass
class WorldSectorInfo:
    """Information about a world sector containing objects"""
    sector_x: int  # Sector X coordinate
    sector_y: int  # Sector Y coordinate
    folder_path: str  # Path to the sector folder
    data_fcb_files: List[str] = None  # List of .data.fcb files in this sector
    data_xml_files: List[str] = None  # List of .data.xml files in this sector
    object_count: int = 0  # Number of objects in this sector
    
    def __post_init__(self):
        """Initialize file lists if None"""
        if self.data_fcb_files is None:
            self.data_fcb_files = []
        if self.data_xml_files is None:
            self.data_xml_files = []


@dataclass
class ObjectLoadResult:
    """Result of loading objects from worldsectors"""
    total_objects: int = 0
    loaded_objects: int = 0
    failed_objects: int = 0
    sectors_processed: int = 0
    conversion_errors: List[str] = None
    loaded_sectors: List[WorldSectorInfo] = None
    
    def __post_init__(self):
        """Initialize lists if None"""
        if self.conversion_errors is None:
            self.conversion_errors = []
        if self.loaded_sectors is None:
            self.loaded_sectors = []

class ObjectParser:
    """Parser for object data from .data.xml files with entity type detection"""
        
    @staticmethod
    def _extract_vehicle_class(xml_element, obj_name):
        """Extract vehicle class information"""
        # Check for class hash
        class_hash_elem = xml_element.find("./value[@hash='346AAB33']")
        if class_hash_elem is not None and class_hash_elem.get("type") == "BinHex":
            # Try to decode the hex to get class name
            try:
                hex_data = class_hash_elem.text
                if hex_data:
                    # Convert hex to string (this is a simplified approach)
                    decoded = bytes.fromhex(hex_data).decode('utf-8', errors='ignore')
                    if decoded.strip():
                        return decoded.strip('\x00')
            except:
                pass
        
        # Fallback based on name
        if "Avatar." in obj_name:
            return f"vehicle.{obj_name}"
        return "Vehicle.Unknown"
    
    @staticmethod
    def _extract_static_class(xml_element, obj_name):
        """Extract static object class information"""
        # Check for file descriptor component
        file_desc_elem = xml_element.find(".//object[@type='CFileDescriptorComponent']")
        if file_desc_elem is not None:
            # Try to find the file name
            file_name_elem = file_desc_elem.find("./value[@hash='2A7BCA49']")
            if file_name_elem is not None and file_name_elem.text:
                file_path = file_name_elem.text
                # Extract class from file path
                if '\\' in file_path:
                    parts = file_path.split('\\')
                    if len(parts) >= 2:
                        return f"StaticObject.{parts[-2]}.{parts[-1].replace('.xml', '')}"
        
        # Fallback
        return f"StaticObject.{obj_name}"
    
    @staticmethod
    def _extract_character_class(xml_element, obj_name):
        """Extract character class information"""
        if "Avatar." in obj_name:
            return f"Character.{obj_name}"
        return "Character.Unknown"
    
    @staticmethod
    def _extract_generic_class(xml_element, obj_name):
        """Extract generic entity class information"""
        return f"Entity.{obj_name}"
    
    @staticmethod
    def _detect_type_by_name(obj_name):
        """Fallback type detection based on name patterns"""
        name_lower = obj_name.lower()
        
        if any(vehicle_keyword in name_lower for vehicle_keyword in 
               ["buggy", "atv", "quad", "dirtbike", "motorbike", "motorcycle", "vehicle", "car", "truck"]):
            return "Vehicle", f"Vehicle.{obj_name}"
        
        elif any(static_keyword in name_lower for static_keyword in 
                 ["staticobject", "building", "structure", "debris", "concrete", "block"]):
            return "StaticObject", f"StaticObject.{obj_name}"
        
        elif any(character_keyword in name_lower for character_keyword in 
                 ["character", "npc", "avatar", "marine", "soldier"]):
            return "Character", f"Character.{obj_name}"
        
        else:
            return "Entity", f"Entity.{obj_name}"
            
    @staticmethod
    def update_object_xml_position_fcb_format(obj):
        """Update object position in FCBConverter format"""
        if not hasattr(obj, 'xml_element') or obj.xml_element is None:
            return False
        
        obj_name = getattr(obj, 'name', 'unknown')
        print(f"Updating {obj_name} position (FCBConverter format)")
        
        # Format coordinates as comma-separated string
        pos_value = f"{obj.x},{obj.y},{obj.z}"
        
        updated = False
        
        # Update hidPos field
        pos_field = obj.xml_element.find("./field[@name='hidPos']")
        if pos_field is not None:
            pos_field.set('value-Vector3', pos_value)
            updated = True
            print(f"Updated hidPos to: {pos_value}")
        
        # Update hidPos_precise field
        pos_precise_field = obj.xml_element.find("./field[@name='hidPos_precise']")
        if pos_precise_field is not None:
            pos_precise_field.set('value-Vector3', pos_value)
            updated = True
            print(f"Updated hidPos_precise to: {pos_value}")
        
        return updated

    @staticmethod
    def update_object_xml_position(obj):
        """
        Update XML element with current object position - supports both formats
        
        Args:
            obj (ObjectEntity): Object to update
            
        Returns:
            bool: True if position was updated successfully
        """
        if not hasattr(obj, 'xml_element') or obj.xml_element is None:
            print(f"DEBUG: No xml_element for object {getattr(obj, 'name', 'unknown')}")
            return False
        
        # Check if this is FCBConverter format (has field elements)
        if obj.xml_element.find("./field[@name='hidPos']") is not None:
            return ObjectParser.update_object_xml_position_fcb_format(obj)
        else:
            # Original format with separate x, y, z elements
            return ObjectParser.update_object_xml_position_original_format(obj)
    
    @staticmethod
    def update_object_xml_position_original_format(obj):
        """Update object position in original XML format (separate x, y, z elements)"""
        if not hasattr(obj, 'xml_element') or obj.xml_element is None:
            return False
        
        obj_name = getattr(obj, 'name', 'unknown')
        print(f"Updating {obj_name} position (original format)")
        
        updated = False
        
        # Update hidPos with separate x, y, z elements
        pos_elem = obj.xml_element.find("./value[@name='hidPos']")
        if pos_elem is not None:
            x_elem = pos_elem.find("./x")
            y_elem = pos_elem.find("./y")
            z_elem = pos_elem.find("./z")
            
            if x_elem is not None and y_elem is not None and z_elem is not None:
                x_elem.text = str(obj.x)
                y_elem.text = str(obj.y)
                z_elem.text = str(obj.z)
                updated = True
                print(f"Updated hidPos elements to: ({obj.x}, {obj.y}, {obj.z})")
        
        # Update hidPos_precise with separate x, y, z elements
        pos_precise_elem = obj.xml_element.find("./value[@name='hidPos_precise']")
        if pos_precise_elem is not None:
            x_elem = pos_precise_elem.find("./x")
            y_elem = pos_precise_elem.find("./y")
            z_elem = pos_precise_elem.find("./z")
            
            if x_elem is not None and y_elem is not None and z_elem is not None:
                x_elem.text = str(obj.x)
                y_elem.text = str(obj.y)
                z_elem.text = str(obj.z)
                updated = True
                print(f"Updated hidPos_precise elements to: ({obj.x}, {obj.y}, {obj.z})")
        
        return updated

    @staticmethod
    def _update_vehicle_specific_positions(obj):
        """Update vehicle-specific position data if needed"""
        # Vehicles might have additional position data in their components
        # This is a placeholder for vehicle-specific position updates
        # You can expand this based on what vehicle data needs updating
        return False
    
    @staticmethod
    def extract_objects_from_data_xml(xml_file_path, sector_path=None):
        """
        Extract all Entity objects from a .data.xml file
        UPDATED: Handle FCBConverter XML format with <object> and <field> tags
        """
        objects = []
        
        try:
            print(f"\n=== Processing {os.path.basename(xml_file_path)} ===")
            
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            print(f"Root element: <{root.tag}> name='{root.get('name')}' hash='{root.get('hash')}'")
            
            # Handle FCBConverter format - look for root with name="WorldSector"
            is_worldsector = False
            
            if root.get("name") == "WorldSector":
                print("Processing as WorldSector file (FCBConverter format)")
                is_worldsector = True
                
                # Extract WorldSector information from <field> elements
                sector_id = None
                sector_x = None
                sector_y = None
                
                id_field = root.find("./field[@name='Id']")
                if id_field is not None:
                    try:
                        # FCBConverter format stores as value-Int32 attribute
                        id_value = id_field.get('value-Int32')
                        if id_value:
                            sector_id = int(id_value)
                    except (ValueError, TypeError):
                        pass
                
                x_field = root.find("./field[@name='X']")
                if x_field is not None:
                    try:
                        x_value = x_field.get('value-Int32')
                        if x_value:
                            sector_x = int(x_value)
                    except (ValueError, TypeError):
                        pass
                
                y_field = root.find("./field[@name='Y']")
                if y_field is not None:
                    try:
                        y_value = y_field.get('value-Int32')
                        if y_value:
                            sector_y = int(y_value)
                    except (ValueError, TypeError):
                        pass
                
                print(f"WorldSector {sector_id} at ({sector_x}, {sector_y})")
            
            # Find all Entity objects - FCBConverter format uses <object name="Entity">
            entity_elements = root.findall(".//object[@name='Entity']")
            
            print(f"Found {len(entity_elements)} Entity objects")
            
            # Parse each Entity using the EXISTING method name
            for i, entity_elem in enumerate(entity_elements):
                print(f"\n--- Processing Entity {i+1}/{len(entity_elements)} ---")
                
                obj_entity = ObjectParser.parse_object_from_xml_fcb_format(
                    entity_elem, 
                    source_file=xml_file_path,
                    sector_path=sector_path
                )
                
                if obj_entity is not None:
                    objects.append(obj_entity)
                    print(f"Added {obj_entity.name} to objects list")
                else:
                    print("Failed to parse entity")
            
            print(f"\n=== Successfully parsed {len(objects)} objects from {os.path.basename(xml_file_path)} ===")
            
        except Exception as e:
            print(f"Error extracting objects from {xml_file_path}: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return objects

    @staticmethod
    def parse_object_from_xml_fcb_format(xml_element, source_file=None, sector_path=None):
        """
        Parse an object (Entity) from FCBConverter XML format
        
        Args:
            xml_element (ET.Element): XML element containing Entity data (FCBConverter format)
            source_file (str): Path to the source .data file
            sector_path (str): Path to the sector folder
            
        Returns:
            ObjectEntity: Parsed object entity or None if parsing fails
        """
        try:
            # This should be an Entity element with name="Entity"
            if xml_element.get("name") != "Entity":
                print(f"WARNING: Expected Entity element, got {xml_element.get('name')}")
                return None
            
            print(f"Parsing FCBConverter Entity element with hash='{xml_element.get('hash')}'")
            
            # Extract entity ID from <field name="disEntityId">
            obj_id = "Unknown"
            id_field = xml_element.find("./field[@name='disEntityId']")
            if id_field is not None:
                # Try value-Id64 first, then value-String
                id_value = id_field.get('value-Id64') or id_field.get('value-String')
                if id_value:
                    obj_id = id_value.strip()
                    print(f"Found entity ID: {obj_id}")
            
            # Extract entity name from <field name="hidName">
            obj_name = "Unnamed Object"
            name_field = xml_element.find("./field[@name='hidName']")
            if name_field is not None:
                name_value = name_field.get('value-String')
                if name_value:
                    obj_name = name_value.strip()
                    print(f"Found entity name: {obj_name}")
            
            # Extract position from <field name="hidPos"> or <field name="hidPos_precise">
            x = y = z = 0.0
            position_found = False
            
            # Try hidPos first
            pos_field = xml_element.find("./field[@name='hidPos']")
            if pos_field is not None:
                pos_value = pos_field.get('value-Vector3')
                if pos_value:
                    try:
                        # Parse "450.988,366.305,7.62474E-06" format
                        coords = pos_value.split(',')
                        if len(coords) == 3:
                            x = float(coords[0])
                            y = float(coords[1])
                            z = float(coords[2])
                            position_found = True
                            print(f"Found position: ({x}, {y}, {z})")
                    except (ValueError, IndexError):
                        print(f"Error parsing position: {pos_value}")
            
            # Try hidPos_precise as fallback
            if not position_found:
                pos_precise_field = xml_element.find("./field[@name='hidPos_precise']")
                if pos_precise_field is not None:
                    pos_value = pos_precise_field.get('value-Vector3')
                    if pos_value:
                        try:
                            coords = pos_value.split(',')
                            if len(coords) == 3:
                                x = float(coords[0])
                                y = float(coords[1])
                                z = float(coords[2])
                                position_found = True
                                print(f"Found precise position: ({x}, {y}, {z})")
                        except (ValueError, IndexError):
                            print(f"Error parsing precise position: {pos_value}")
            
            if not position_found:
                print(f"WARNING: No position found for {obj_name}")
            
            # Extract creature type for entity type detection
            creature_type = None
            type_field = xml_element.find("./field[@name='tplCreatureType']")
            if type_field is not None:
                creature_type = type_field.get('value-String')
                if creature_type:
                    print(f"Found creature type: {creature_type}")
            
            # DETECT: Detect entity type based on creature type and components
            entity_type, class_name = ObjectParser._detect_entity_type_fcb_format(xml_element, obj_name, creature_type)
            
            # Extract additional properties
            properties = ObjectParser._extract_entity_properties_fcb_format(xml_element, entity_type)
            
            # Extract resource count
            resource_field = xml_element.find("./field[@name='hidResourceCount']")
            if resource_field is not None:
                try:
                    resource_count = resource_field.get('value-Int32')
                    if resource_count:
                        properties['resource_count'] = int(resource_count)
                except (ValueError, TypeError):
                    pass
            
            # Create ObjectEntity
            obj_entity = ObjectEntity(
                id=obj_id,
                name=obj_name,
                x=x,
                y=y,
                z=z,
                xml_element=xml_element,
                source_file=source_file,
                sector_path=sector_path,
                object_type=entity_type,
                class_name=class_name,
                model_path=None,
                properties=properties
            )
            
            print(f"Created {entity_type} entity: {obj_name} at ({x}, {y}, {z})")
            return obj_entity
            
        except Exception as e:
            print(f"Error parsing FCBConverter object from XML: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def _detect_entity_type_fcb_format(xml_element, obj_name, creature_type=None):
        """
        Detect entity type from FCBConverter format XML
        
        Returns:
            tuple: (entity_type, class_name)
        """
        # Use creature type if available
        if creature_type:
            if creature_type.startswith("vehicle."):
                return "Vehicle", creature_type
            elif "character" in creature_type.lower():
                return "Character", creature_type
            elif "weapon" in creature_type.lower():
                return "Weapon", creature_type
        
        # Check components - look for <object name="Components">
        components_elem = xml_element.find("./object[@name='Components']")
        if components_elem is not None:
            component_types = []
            for component in components_elem:
                comp_name = component.get("name")
                if comp_name:
                    component_types.append(comp_name)
            
            print(f"Found components: {component_types}")
            
            # Detect based on component combinations
            if "CVehicleWheeledPhysComponent" in component_types or "CVehicle" in component_types:
                return "Vehicle", creature_type or f"Vehicle.{obj_name}"
            
            elif "CStaticPhysComponent" in component_types and "CGraphicComponent" in component_types:
                return "StaticObject", creature_type or f"StaticObject.{obj_name}"
            
            elif "CGraphicComponent" in component_types:
                if "CCharacterPhysComponent" in component_types:
                    return "Character", creature_type or f"Character.{obj_name}"
                elif "CProjectileComponent" in component_types:
                    return "Projectile", creature_type or f"Projectile.{obj_name}"
                else:
                    return "Entity", creature_type or f"Entity.{obj_name}"
        
        # Fallback to name-based detection
        return ObjectParser._detect_type_by_name(obj_name)


    @staticmethod
    def _extract_entity_properties_fcb_format(xml_element, entity_type):
        """Extract entity-specific properties from FCBConverter format"""
        properties = {}
        
        # Extract angles if available
        angles_field = xml_element.find("./field[@name='hidAngles']")
        if angles_field is not None:
            angles_value = angles_field.get('value-Vector3')
            if angles_value:
                try:
                    coords = angles_value.split(',')
                    if len(coords) == 3:
                        properties['angles'] = {
                            'x': float(coords[0]),
                            'y': float(coords[1]),
                            'z': float(coords[2])
                        }
                except (ValueError, IndexError):
                    pass
        
        # Extract creature type
        creature_field = xml_element.find("./field[@name='tplCreatureType']")
        if creature_field is not None:
            creature_type = creature_field.get('value-String')
            if creature_type:
                properties['creature_type'] = creature_type
        
        return properties

class WorldSectorManager:
    """Manager for handling world sector operations"""
    
    @staticmethod
    def scan_worldsectors_folder(worldsectors_path, log_callback=None):
        """
        Scan worldsectors folder and return information about sectors
        UPDATED: Use .converted.xml files directly without creating .data.xml copies
        
        Args:
            worldsectors_path: Path to the worldsectors folder
            log_callback: Optional callback function for logging messages
        """
        # Helper for logging to both console and callback
        def log(message):
            print(message)
            if log_callback:
                try:
                    log_callback(message)
                except:
                    pass
        
        sectors = []
        
        try:
            if not os.path.exists(worldsectors_path):
                log(f"Worldsectors path does not exist: {worldsectors_path}")
                return sectors
            
            log(f"Scanning worldsectors folder: {worldsectors_path}")
            
            # Find all .data files directly in the worldsectors folder
            data_fcb_files = []
            data_xml_files = []
            
            # Scan all files in the directory
            all_files = os.listdir(worldsectors_path)
            log(f"Found {len(all_files)} total files in directory")
            
            for file in all_files:
                file_path = os.path.join(worldsectors_path, file)
                if os.path.isfile(file_path):
                    if file.endswith(".data.fcb"):
                        data_fcb_files.append(file_path)
                        log(f"  Found FCB: {file}")
                    elif file.endswith(".data.fcb.converted.xml"):
                        # Use .converted.xml files directly - NO COPYING
                        data_xml_files.append(file_path)
                        log(f"  Found converted XML: {file}")
            
            log(f"Total: {len(data_fcb_files)} .data.fcb files and {len(data_xml_files)} .converted.xml files")
            
            # Create a single "sector" representing the entire worldsectors folder
            if data_fcb_files or data_xml_files:
                sector_info = WorldSectorInfo(
                    sector_x=0,
                    sector_y=0,
                    folder_path=worldsectors_path,
                    data_fcb_files=data_fcb_files,
                    data_xml_files=data_xml_files,  # These are now .converted.xml files
                    object_count=0
                )
                
                sectors.append(sector_info)
                log(f"Created sector info with {len(data_fcb_files)} FCB and {len(data_xml_files)} converted XML files")
            
        except Exception as e:
            log(f"Error scanning worldsectors folder: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return sectors
    
    @staticmethod
    def get_sector_statistics(sectors):
        """
        Get statistics about the sectors
        
        Args:
            sectors (List[WorldSectorInfo]): List of sector information
            
        Returns:
            dict: Statistics about the sectors
        """
        stats = {
            'total_sectors': len(sectors),
            'total_fcb_files': 0,
            'total_xml_files': 0,
            'sectors_with_data': 0,
            'sectors_needing_conversion': 0
        }
        
        for sector in sectors:
            stats['total_fcb_files'] += len(sector.data_fcb_files)
            stats['total_xml_files'] += len(sector.data_xml_files)
            
            if sector.data_fcb_files or sector.data_xml_files:
                stats['sectors_with_data'] += 1
            
            # Check if sector needs conversion (has FCB but no corresponding XML)
            needs_conversion = False
            for fcb_file in sector.data_fcb_files:
                xml_file = fcb_file.replace('.data.fcb', '.data.xml')
                if not os.path.exists(xml_file):
                    needs_conversion = True
                    break
            
            if needs_conversion:
                stats['sectors_needing_conversion'] += 1
        
        return stats
# hash_parser.py
import xml.etree.ElementTree as ET
import os

class HashParser:
    """Parser for binary class definitions to convert hash values to readable names"""
    
    def __init__(self, binary_classes_path=None):
        """
        Initialize the hash parser with binary class definitions
        
        Args:
            binary_classes_path (str, optional): Path to the binary_classes.xml file
        """
        self.class_hash_map = {}  # Maps class hashes to class names
        self.member_hash_map = {}  # Maps member hashes to member names
        
        # Default path for binary_classes.xml (in the FCCU_FC2 project folder)
        if not binary_classes_path:
            tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
            binary_classes_path = os.path.join(tools_path, "projects", "FCCU_FC2", "binary_classes.xml")
        
        self.load_binary_classes(binary_classes_path)
    
    def load_binary_classes(self, file_path):
        """
        Load binary class definitions from XML
        
        Args:
            file_path (str): Path to the binary_classes.xml file
        """
        try:
            if not os.path.exists(file_path):
                print(f"Warning: binary_classes.xml not found at {file_path}")
                return
            
            print(f"Loading binary class definitions from {file_path}")
            
            # Try to read the content of the file directly for debugging
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"File size: {len(content)} bytes")
                print(f"First 500 characters:\n{content[:500]}...")
            
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            print(f"XML root tag: {root.tag}")
            print(f"Number of direct child elements: {len(list(root))}")
            
            # Count classes and members
            class_count = len(root.findall(".//class"))
            member_count = len(root.findall(".//member"))
            print(f"Total classes found: {class_count}")
            print(f"Total members found: {member_count}")
            
            # Count classes with hash attributes
            classes_with_hash = len(root.findall(".//class[@hash]"))
            members_with_hash = len(root.findall(".//member[@hash]"))
            print(f"Classes with hash attribute: {classes_with_hash}")
            print(f"Members with hash attribute: {members_with_hash}")
            
            # Process all class definitions
            for class_elem in root.findall(".//class"):
                # Get class hash and name
                class_hash = class_elem.get("hash")
                class_name = class_elem.get("name")
                
                if class_hash:
                    # Store class hash mapping if hash is available
                    name_to_use = class_name if class_name else f"Class_{class_hash}"
                    self.class_hash_map[class_hash] = name_to_use
                    print(f"Added class mapping: {class_hash} -> {name_to_use}")
                
                # Process all member definitions within this class
                for member_elem in class_elem.findall("./member"):
                    member_hash = member_elem.get("hash")
                    member_name = member_elem.get("name")
                    
                    if member_hash and member_name:
                        # Store member hash mapping if hash and name are available
                        self.member_hash_map[member_hash] = member_name
                        print(f"Added member mapping: {member_hash} -> {member_name}")
            
            print(f"Loaded {len(self.class_hash_map)} class hash mappings and {len(self.member_hash_map)} member hash mappings")
            
        except Exception as e:
            print(f"Error loading binary class definitions: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def get_class_name(self, hash_value):
        """
        Get class name from hash value
        
        Args:
            hash_value (str): Hash value as a string
            
        Returns:
            str: Class name if found, otherwise the original hash value
        """
        return self.class_hash_map.get(hash_value, hash_value)
    
    def get_member_name(self, hash_value):
        """
        Get member name from hash value
        
        Args:
            hash_value (str): Hash value as a string
            
        Returns:
            str: Member name if found, otherwise the original hash value
        """
        return self.member_hash_map.get(hash_value, hash_value)
    
    def parse_xml_element(self, elem):
        """
        Parse an XML element and update hash values with names if available
        
        Args:
            elem (Element): XML element to parse
            
        Returns:
            Element: Updated XML element
        """
        # Check if this element has a hash attribute
        if "hash" in elem.attrib:
            hash_value = elem.attrib["hash"]
            
            # If it's an object element, try to map the class hash
            if elem.tag == "object":
                class_name = self.get_class_name(hash_value)
                
                # If we found a class name, replace the hash attribute with type
                if class_name != hash_value:
                    elem.attrib.pop("hash")
                    elem.attrib["type"] = class_name
            elif elem.tag == "value":
                # For value elements with hash attributes, try to map the member hash
                member_name = self.get_member_name(hash_value)
                
                # If we found a member name, replace the hash attribute with name
                if member_name != hash_value:
                    elem.attrib.pop("hash")
                    elem.attrib["name"] = member_name
        
        # Recursively process all child elements
        for child in elem:
            self.parse_xml_element(child)
        
        return elem
    
    def parse_xml_file(self, input_path, output_path=None):
        """
        Parse an XML file and update hash values with names
        
        Args:
            input_path (str): Path to input XML file
            output_path (str, optional): Path to output XML file. If not provided, will overwrite input file.
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse the XML file
            tree = ET.parse(input_path)
            root = tree.getroot()
            
            # Process the root element and all its children
            self.parse_xml_element(root)
            
            # Determine output path
            if not output_path:
                output_path = input_path
            
            # Write the updated XML to file
            tree.write(output_path, encoding="utf-8", xml_declaration=True)
            
            print(f"Successfully parsed {input_path} and wrote to {output_path}")
            return True
            
        except Exception as e:
            print(f"Error parsing XML file {input_path}: {str(e)}")
            return False
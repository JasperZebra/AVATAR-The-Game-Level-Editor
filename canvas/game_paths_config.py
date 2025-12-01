"""
Game-Specific Path Configuration for Avatar and Far Cry 2
Handles all asset paths based on game mode
"""

import os

class GamePathConfig:
    """Configuration for game-specific asset paths"""
    
    def __init__(self, game_mode, editor_root):
        """
        Initialize path configuration
        
        Args:
            game_mode: "avatar" or "farcry2"
            editor_root: Root directory of the editor
        """
        self.game_mode = game_mode
        self.editor_root = editor_root
        
        # Determine game folder name
        self.game_folder = "avatar" if game_mode == "avatar" else "fc2"
    
    def get_local_models_paths(self):
        """Get local editor models directory paths (returns list to try in order)"""
        return [
            os.path.join(self.editor_root, "canvas", "assets", self.game_folder, "models", "graphics"),
            os.path.join(self.editor_root, "assets", self.game_folder, "models", "graphics"),
        ]
    
    def get_local_entitylibrary_path(self):
        """Get local editor EntityLibrary XML path"""
        return os.path.join(
            self.editor_root, 
            "canvas", 
            "assets", 
            self.game_folder, 
            "entitylibrary", 
            "entitylibrary_full.fcb.converted.xml"
        )
    
    def get_local_materials_paths(self):
        """Get local materials directory paths (returns list to try in order)"""
        return [
            os.path.join(self.editor_root, "canvas", "assets", self.game_folder, "models", "graphics", "_materials"),
            os.path.join(self.editor_root, "assets", self.game_folder, "models", "graphics", "_materials"),
        ]
    
    def find_first_existing_path(self, path_list):
        """Find first existing path from a list of paths"""
        for path in path_list:
            if os.path.exists(path):
                return path
        return None
    
    def get_models_path(self):
        """Get the first existing models path"""
        return self.find_first_existing_path(self.get_local_models_paths())
    
    def get_materials_path(self):
        """Get the first existing materials path"""
        return self.find_first_existing_path(self.get_local_materials_paths())
    
    def print_paths_summary(self):
        """Print summary of all configured paths"""
        print(f"\n{'='*70}")
        print(f"GAME-SPECIFIC PATHS ({self.game_mode.upper()})")
        print(f"{'='*70}")
        
        # Models
        models_paths = self.get_local_models_paths()
        models_path = self.get_models_path()
        print(f"\nModels Directory:")
        for i, path in enumerate(models_paths):
            status = "✓ FOUND" if path == models_path else "✗ Not found"
            print(f"  [{i+1}] {path}")
            print(f"      {status}")
        
        # EntityLibrary
        entitylib_path = self.get_local_entitylibrary_path()
        entitylib_exists = os.path.exists(entitylib_path)
        print(f"\nEntityLibrary:")
        print(f"  {entitylib_path}")
        print(f"  {'✓ FOUND' if entitylib_exists else '✗ Not found'}")
        
        # Materials
        materials_paths = self.get_local_materials_paths()
        materials_path = self.get_materials_path()
        print(f"\nMaterials Directory:")
        for i, path in enumerate(materials_paths):
            status = "✓ FOUND" if path == materials_path else "✗ Not found"
            print(f"  [{i+1}] {path}")
            print(f"      {status}")
        
        print(f"{'='*70}\n")


# =============================================================================
# INTEGRATION FUNCTIONS
# =============================================================================

def setup_game_paths(main_window):
    """
    Setup game-specific paths for the editor
    Call this in SimplifiedMapEditor.__init__() BEFORE setup_ui()
    
    Args:
        main_window: SimplifiedMapEditor instance
    """
    # Get editor root directory
    current_file = os.path.abspath(__file__)
    editor_root = os.path.dirname(os.path.dirname(current_file))  # Go up from canvas/ to editor root
    
    # Create path config
    main_window.game_path_config = GamePathConfig(main_window.game_mode, editor_root)
    main_window.game_path_config.print_paths_summary()
    
    # Store paths as attributes for easy access
    main_window.local_models_path = main_window.game_path_config.get_models_path()
    main_window.local_entitylibrary_path = main_window.game_path_config.get_local_entitylibrary_path()
    main_window.local_materials_path = main_window.game_path_config.get_materials_path()
    
    # Warn if paths not found
    if not main_window.local_models_path:
        print(f"⚠️  WARNING: No models directory found for {main_window.game_mode}")
        print(f"   Please create one of these directories:")
        for path in main_window.game_path_config.get_local_models_paths():
            print(f"   - {path}")
    
    if not os.path.exists(main_window.local_entitylibrary_path):
        print(f"⚠️  WARNING: EntityLibrary not found for {main_window.game_mode}")
        print(f"   Expected at: {main_window.local_entitylibrary_path}")
    
    if not main_window.local_materials_path:
        print(f"⚠️  WARNING: No materials directory found for {main_window.game_mode}")
        print(f"   Please create one of these directories:")
        for path in main_window.game_path_config.get_local_materials_paths():
            print(f"   - {path}")


def update_model_loader_for_game(model_loader, game_path_config):
    """
    Update ModelLoader to use game-specific paths
    Call this AFTER creating ModelLoader instance
    
    Args:
        model_loader: ModelLoader instance
        game_path_config: GamePathConfig instance
    """
    print(f"\n{'='*70}")
    print(f"CONFIGURING MODEL LOADER FOR {game_path_config.game_mode.upper()}")
    print(f"{'='*70}")
    
    # 1. Setup models directory
    models_path = game_path_config.get_models_path()
    if models_path:
        success = model_loader.set_models_directory(models_path, scan_recursive=True)
        if success:
            print(f"✓ Models directory set: {models_path}")
        else:
            print(f"✗ Failed to set models directory: {models_path}")
    else:
        print(f"✗ No models directory found")
    
    # 2. Setup EntityLibrary (override the local loading)
    entitylib_path = game_path_config.get_local_entitylibrary_path()
    if os.path.exists(entitylib_path):
        # Directly load the EntityLibrary XML
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(entitylib_path)
            root = tree.getroot()
            model_loader.entity_patterns = {}
            
            # Parse EntityLibrary (same logic as _load_local_entity_library)
            for proto_obj in root.findall(".//object[@name='EntityPrototype']"):
                name_field = proto_obj.find(".//field[@name='Name']")
                if name_field is None:
                    continue
                
                proto_name = name_field.get('value-String')
                if not proto_name:
                    continue
                
                entity_obj = proto_obj.find(".//object[@name='Entity']")
                if entity_obj is None:
                    continue
                
                hid_field = entity_obj.find(".//field[@name='hidName']")
                hid_name = hid_field.get('value-String') if hid_field is not None else None
                
                descriptor_component = entity_obj.find(".//object[@name='CFileDescriptorComponent']")
                if descriptor_component is not None:
                    hid_descriptor = descriptor_component.find(".//field[@name='hidDescriptor']")
                    if hid_descriptor is not None:
                        graphic_component = hid_descriptor.find(".//component[@class='GraphicComponent']")
                        if graphic_component is not None:
                            resource = graphic_component.find(".//resource")
                            if resource is not None:
                                model_file = resource.get('fileName')
                                if model_file:
                                    model_loader.entity_patterns[proto_name] = model_file
                                    if hid_name:
                                        model_loader.entity_patterns[hid_name] = model_file
                        
                        kit_component = hid_descriptor.find(".//component[@class='GraphicKitComponent']")
                        if kit_component is not None:
                            resource = kit_component.find(".//resource")
                            if resource is not None:
                                model_file = resource.get('fileName')
                                if model_file:
                                    model_loader.entity_patterns[proto_name] = model_file
                                    if hid_name:
                                        model_loader.entity_patterns[hid_name] = model_file
            
            model_loader._entity_library_loaded = True
            print(f"✓ EntityLibrary loaded: {entitylib_path}")
            print(f"  Loaded {len(model_loader.entity_patterns)} entity patterns")
            
        except Exception as e:
            print(f"✗ Failed to load EntityLibrary: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"✗ EntityLibrary not found: {entitylib_path}")
    
    # 3. Setup materials directory
    materials_path = game_path_config.get_materials_path()
    if materials_path:
        model_loader.set_materials_directory(materials_path)
        print(f"✓ Materials directory set: {materials_path}")
    else:
        print(f"⚠️  Materials directory not found - models will render without textures")
    
    print(f"{'='*70}\n")


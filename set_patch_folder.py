"""
Patch Folder Management and Visual Level Selection System
Handles patch folder configuration and provides visual level selection interface
"""

import os
import json
import glob
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QScrollArea, QWidget,
    QMessageBox, QFileDialog, QGroupBox,
    QLineEdit, QProgressDialog, QFrame, QComboBox,
    QApplication
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QPainter, QFont, QColor, QAction

# Configuration file for storing patch folder path
PATCH_CONFIG_FILE = "patch_config.json"

@dataclass
class LevelInfo:
    """Data class for storing level information"""
    name: str
    worlds_path: str
    levels_path: str
    thumbnail_path: Optional[str] = None
    display_name: Optional[str] = None
    has_terrain: bool = False
    has_objects: bool = False
    file_counts: Dict[str, int] = field(default_factory=dict)

class PatchFolderScanner(QThread):
    """Background thread for scanning patch folder structure"""
    
    progress_updated = pyqtSignal(int, str)  # progress percentage, status message
    scan_complete = pyqtSignal(dict)  # Dictionary of found levels
    error_occurred = pyqtSignal(str)  # Error message
    
    def __init__(self, patch_folder: str, file_converter=None):
        super().__init__()
        self.patch_folder = patch_folder
        self.file_converter = file_converter
        self.should_stop = False
        
    def run(self):
        """Scan the patch folder for levels and their components"""
        try:
            levels_data = {}
            
            # Check for required directories - be more flexible
            worlds_dir = os.path.join(self.patch_folder, "worlds")
            levels_dir = os.path.join(self.patch_folder, "levels")
            
            # Also check for alternative naming
            if not os.path.exists(worlds_dir):
                # Try "Worlds" with capital W
                worlds_dir_alt = os.path.join(self.patch_folder, "Worlds")
                if os.path.exists(worlds_dir_alt):
                    worlds_dir = worlds_dir_alt
                    print(f"Using alternative worlds directory: {worlds_dir}")
            
            if not os.path.exists(levels_dir):
                # Try "Levels" with capital L
                levels_dir_alt = os.path.join(self.patch_folder, "Levels")
                if os.path.exists(levels_dir_alt):
                    levels_dir = levels_dir_alt
                    print(f"Using alternative levels directory: {levels_dir}")
            
            # Check if at least one directory exists
            has_worlds = os.path.exists(worlds_dir)
            has_levels = os.path.exists(levels_dir)
            
            if not has_worlds and not has_levels:
                # Try to detect if this IS a worlds or levels folder directly
                if self._check_world_data(self.patch_folder):
                    print("Detected patch folder as direct worlds folder")
                    worlds_dir = self.patch_folder
                    has_worlds = True
                    levels_dir = None
                    has_levels = False
                elif self._check_level_data(self.patch_folder):
                    print("Detected patch folder as direct levels folder")
                    levels_dir = self.patch_folder
                    has_levels = True
                    worlds_dir = None
                    has_worlds = False
                else:
                    self.error_occurred.emit(
                        f"Could not find 'worlds' or 'levels' subdirectories in:\n{self.patch_folder}\n\n"
                        f"Please ensure your patch folder contains these directories,\n"
                        f"or select the worlds/levels folder directly."
                    )
                    return
            
            print(f"Scanning with worlds_dir={worlds_dir}, levels_dir={levels_dir}")
            
            self.progress_updated.emit(10, "Scanning worlds folder...")
            
            # Get all world folders
            world_folders = {}
            if has_worlds and worlds_dir:
                print(f"Scanning worlds directory: {worlds_dir}")
                try:
                    items = os.listdir(worlds_dir)
                    print(f"Found {len(items)} items in worlds directory")
                    
                    for item in items:
                        if self.should_stop:
                            return
                            
                        item_path = os.path.join(worlds_dir, item)
                        if os.path.isdir(item_path):
                            # First try to convert FCB files if file converter is available
                            if self.file_converter:
                                try:
                                    print(f"  Attempting to convert FCB files in {item}...")
                                    success_count, error_count, errors = self.file_converter.convert_folder(
                                        item_path, 
                                        progress_callback=None
                                    )
                                    if success_count > 0:
                                        print(f"    Converted {success_count} FCB files to XML")
                                except Exception as e:
                                    print(f"    Conversion error: {e}")
                            
                            # Now check if it contains required XML/FCB files
                            has_world_data = self._check_world_data(item_path)
                            if has_world_data:
                                world_folders[item] = item_path
                                print(f"  ✓ Valid world folder: {item}")
                            else:
                                print(f"  ✗ Not a valid world folder: {item}")
                except Exception as e:
                    print(f"Error scanning worlds: {e}")
            
            # Debug output for world folders
            print(f"\nWorld folders found:")
            for name, path in world_folders.items():
                print(f"  {name}: {path}")
            
            self.progress_updated.emit(30, f"Found {len(world_folders)} world folders")
            
            # Get all level folders
            level_folders = {}
            if has_levels and levels_dir:
                print(f"Scanning levels directory: {levels_dir}")
                try:
                    items = os.listdir(levels_dir)
                    print(f"Found {len(items)} items in levels directory")
                    
                    for item in items:
                        if self.should_stop:
                            return
                            
                        item_path = os.path.join(levels_dir, item)
                        if os.path.isdir(item_path):
                            # Check for worldsectors folder
                            has_level_data = self._check_level_data(item_path)
                            if has_level_data:
                                level_folders[item] = item_path
                                print(f"  ✓ Valid level folder: {item}")
                            else:
                                print(f"  ✗ Not a valid level folder: {item}")
                except Exception as e:
                    print(f"Error scanning levels: {e}")
            
            # Debug output for level folders
            print(f"\nLevel folders found:")
            for name, path in level_folders.items():
                print(f"  {name}: {path}")
            
            self.progress_updated.emit(50, f"Found {len(level_folders)} level folders")
            
            # Continue even if we only have one type of folder
            print(f"Proceeding with {len(world_folders)} worlds and {len(level_folders)} levels")
            
            # Match world and level folders
            self.progress_updated.emit(60, "Matching world and level folders...")
            
            # Debug output for matching
            print(f"\nMatching results:")
            for world_name in world_folders:
                matches = self._find_matching_level(world_name, level_folders)
                print(f"  {world_name} -> {matches}")
            
            for folder_name in world_folders:
                if self.should_stop:
                    return
                    
                # Try to find matching level folder
                matching_levels = self._find_matching_level(folder_name, level_folders)
                
                if matching_levels:
                    # Handle multiple level folders for a single world (like sp_drifting_sierra_fm_01)
                    for idx, level_folder in enumerate(matching_levels):
                        level_suffix = f"_part{idx+1}" if len(matching_levels) > 1 else ""
                        level_key = f"{folder_name}{level_suffix}"
                        
                        # Create level info
                        level_info = LevelInfo(
                            name=folder_name,
                            worlds_path=world_folders[folder_name],
                            levels_path=level_folders[level_folder]
                        )
                        
                        # Check for thumbnail
                        thumbnail_path = self._find_thumbnail(folder_name)
                        if thumbnail_path:
                            level_info.thumbnail_path = thumbnail_path
                        
                        # Get file counts for additional info
                        level_info.file_counts = self._count_files(
                            world_folders[folder_name], 
                            level_folders[level_folder]
                        )
                        
                        # Check for terrain and objects
                        level_info.has_terrain = self._check_for_terrain(level_folders[level_folder])
                        level_info.has_objects = level_info.file_counts.get('objects', 0) > 0
                        
                        # Set display name (can be customized)
                        if len(matching_levels) > 1:
                            level_info.display_name = f"{self._format_display_name(folder_name)} (Part {idx+1})"
                        else:
                            level_info.display_name = self._format_display_name(folder_name)
                        
                        levels_data[level_key] = level_info
            
            self.progress_updated.emit(90, f"Matched {len(levels_data)} complete levels")
            
            # Also add level-only entries for unmatched level folders
            for level_name, level_path in level_folders.items():
                # Check if this level has been matched already
                already_matched = False
                for data in levels_data.values():
                    if data.levels_path == level_path:
                        already_matched = True
                        break
                
                if not already_matched:
                    # Try to find a matching world folder name (without _l suffix)
                    potential_world_name = level_name.replace('_l', '').replace('_l1', '').replace('_l2', '')
                    
                    # Create a level-only entry
                    level_info = LevelInfo(
                        name=potential_world_name,
                        worlds_path=None,  # No world data found
                        levels_path=level_path
                    )
                    
                    # Check for thumbnail
                    thumbnail_path = self._find_thumbnail(potential_world_name)
                    if thumbnail_path:
                        level_info.thumbnail_path = thumbnail_path
                    
                    # Get file counts
                    level_info.file_counts = self._count_files(None, level_path)
                    
                    # Check for terrain and objects
                    level_info.has_terrain = self._check_for_terrain(level_path)
                    level_info.has_objects = level_info.file_counts.get('objects', 0) > 0
                    
                    # Set display name
                    level_info.display_name = f"{self._format_display_name(potential_world_name)} (Objects Only)"
                    
                    levels_data[f"{potential_world_name}_objects_only"] = level_info
                    print(f"Added objects-only level: {potential_world_name}")
            
            # Also add unmatched world folders (world-only levels)
            for folder_name in world_folders:
                if folder_name not in levels_data:
                    level_info = LevelInfo(
                        name=folder_name,
                        worlds_path=world_folders[folder_name],
                        levels_path=None
                    )
                    
                    thumbnail_path = self._find_thumbnail(folder_name)
                    if thumbnail_path:
                        level_info.thumbnail_path = thumbnail_path
                    
                    level_info.display_name = f"{self._format_display_name(folder_name)} (World Only)"
                    levels_data[f"{folder_name}_world_only"] = level_info
            
            self.progress_updated.emit(100, "Scan complete!")
            
            # Log summary
            print(f"\nScan Summary:")
            print(f"  World folders found: {len(world_folders)}")
            print(f"  Level folders found: {len(level_folders)}")
            print(f"  Total entries created: {len(levels_data)}")
            
            # If we have any levels (even without worlds), that's success
            if levels_data:
                self.scan_complete.emit(levels_data)
            elif level_folders:
                # We have level folders but couldn't create entries - create basic entries
                print("Warning: Have level folders but no entries created, creating basic entries...")
                for level_name, level_path in level_folders.items():
                    level_info = LevelInfo(
                        name=level_name,
                        worlds_path=None,
                        levels_path=level_path,
                        display_name=f"{self._format_display_name(level_name)} (Level Only)"
                    )
                    levels_data[f"{level_name}_level_only"] = level_info
                self.scan_complete.emit(levels_data)
            else:
                # No data at all
                self.error_occurred.emit(
                    f"No valid level data found in the selected folder.\n\n"
                    f"Found:\n"
                    f"• {len(world_folders)} world folders\n"
                    f"• {len(level_folders)} level folders\n\n"
                    f"Please ensure your patch folder has the correct structure."
                )
            
        except Exception as e:
            self.error_occurred.emit(f"Error scanning patch folder: {str(e)}")

    def _check_world_data(self, folder_path: str) -> bool:
        """Check if folder contains valid world data files (looks in 'generated' subfolder for Avatar)"""
        required_files = ['mapsdata', 'managers', 'omnis', 'sectorsdep', 'entitylibrary_full']  # added entitylibrary_full
        found_files = set()
        
        generated_path = os.path.join(folder_path, 'generated')
        search_path = generated_path if os.path.exists(generated_path) else folder_path
        print(f"    Checking {os.path.basename(search_path)}...")

        try:
            if os.path.isdir(search_path):
                files = os.listdir(search_path)
                for file in files:
                    file_lower = file.lower()
                    for req in required_files:
                        if req in file_lower and (file_lower.endswith('.fcb') or file_lower.endswith('.xml')):
                            found_files.add(req)
                            print(f"      Found: {file}")
                            break
                if len(found_files) >= 2:
                    print(f"    ✓ {os.path.basename(folder_path)}: Found {len(found_files)} required files")
                    return True

            # Fallback: also search subdirectories (depth <=2)
            if len(found_files) < 2:
                for root, dirs, files in os.walk(folder_path):
                    depth = root[len(folder_path):].count(os.sep)
                    if depth > 2:
                        dirs.clear()
                        continue
                    for file in files:
                        file_lower = file.lower()
                        for req in required_files:
                            if req in file_lower and (file_lower.endswith('.fcb') or file_lower.endswith('.xml')):
                                found_files.add(req)
                                if len(found_files) >= 2:
                                    print(f"    ✓ {os.path.basename(folder_path)}: Found files in subdirectories")
                                    return True
        except Exception as e:
            print(f"    Error checking {folder_path}: {e}")
            return False

        if found_files:
            print(f"    Partial: {os.path.basename(folder_path)} has {len(found_files)} files: {', '.join(found_files)}")

        return len(found_files) >= 2
    
    def _find_matching_level(self, world_folder: str, level_folders: dict) -> list:
        """
        Find matching level folder(s) for a world folder.
        Handles Avatar: The Game specific naming patterns.
        
        Returns a list since some worlds have multiple level folders (e.g., sp_drifting_sierra_fm_01_l1 and _l2)
        """
        matches = []
        
        # Pattern 1: Exact match (rare but check first)
        if world_folder in level_folders:
            matches.append(world_folder)
            return matches
        
        # Pattern 2: World name + "_l" suffix (most common)
        if f"{world_folder}_l" in level_folders:
            matches.append(f"{world_folder}_l")
        
        # Pattern 3: World name + "_l1", "_l2" etc. (for multi-part levels)
        for i in range(1, 5):  # Check up to _l4
            level_name = f"{world_folder}_l{i}"
            if level_name in level_folders:
                matches.append(level_name)
        
        # Pattern 4: Some levels don't follow the _l pattern exactly
        # Check for levels that start with the world name
        for level_name in level_folders:
            if level_name.startswith(world_folder):
                # Avoid duplicates
                if level_name not in matches:
                    # Special case: sp_pascal_rf03_l vs sp_pascal_rf04 world
                    if world_folder == "sp_pascal_rf04" and level_name == "sp_pascal_rf03_l":
                        matches.append(level_name)
                    # For other cases, match if it's the world name plus suffix
                    elif level_name.startswith(f"{world_folder}_") or level_name == world_folder:
                        if level_name not in matches:
                            matches.append(level_name)
        
        # Special handling for known mismatches
        special_cases = {
            "sp_pascal_rf04": ["sp_pascal_rf03_l"],  # sp_pascal_rf04 world uses sp_pascal_rf03_l level
            "sp_jeannormand_df_01": ["sp_jeannormand_df_01"],  # No _l suffix
            "mp_hellsgate_02": ["mp_hellsgate_02"],  # No _l suffix
            "mp_jeannormand_of_01": ["mp_jeannormand_of_01"],  # No _l suffix
            "mp_jeannormand_rf_02": ["mp_jeannormand_rf_02"],  # No _l suffix
            "sp_philippe_rf_rb_01": ["sp_philippe_rf_rb_01"],  # No _l suffix
            "z_anim_creatures": ["z_anim_creatures"],  # No _l suffix
        }
        
        if world_folder in special_cases and not matches:
            for special_level in special_cases[world_folder]:
                if special_level in level_folders:
                    matches.append(special_level)
        
        # If still no matches, try partial matching
        if not matches:
            for level_name in level_folders:
                # Check if world name is contained in level name
                if world_folder.lower() in level_name.lower() or level_name.lower() in world_folder.lower():
                    if level_name not in matches:
                        matches.append(level_name)
                        print(f"  Partial match: {world_folder} -> {level_name}")
        
        return matches
    
    def _check_level_data(self, folder_path: str) -> bool:
        """Check if folder contains valid level data (searches recursively for worldsectors)"""
        # Search up to 3 levels deep for worldsectors folder
        for root, dirs, files in os.walk(folder_path):
            # Limit search depth
            depth = root[len(folder_path):].count(os.sep)
            if depth > 3:
                dirs.clear()  # Don't go deeper
                continue
            
            # Check if current directory is named worldsectors (case-insensitive)
            current_dir = os.path.basename(root).lower()
            if current_dir == 'worldsectors' or current_dir == 'worldsector':
                # Check for .data.fcb or .data.xml files
                data_files = [f for f in files if '.data.fcb' in f.lower() or '.data.xml' in f.lower()]
                if data_files:
                    print(f"    Found worldsectors in {os.path.basename(folder_path)} with {len(data_files)} data files")
                    return True
            
            # Also check if any subdirectory is worldsectors
            for dir_name in dirs:
                if dir_name.lower() in ['worldsectors', 'worldsector']:
                    ws_path = os.path.join(root, dir_name)
                    try:
                        ws_files = os.listdir(ws_path)
                        data_files = [f for f in ws_files if '.data.fcb' in f.lower() or '.data.xml' in f.lower()]
                        if data_files:
                            print(f"    Found worldsectors in {os.path.basename(folder_path)}/{dir_name} with {len(data_files)} data files")
                            return True
                    except:
                        continue
        
        return False
    
    def _check_for_terrain(self, level_path: str) -> bool:
        """Check if level has terrain data (searches recursively for sdat folder)"""
        if not level_path:
            return False
        
        # Search up to 3 levels deep for sdat folder
        for root, dirs, files in os.walk(level_path):
            # Limit search depth
            depth = root[len(level_path):].count(os.sep)
            if depth > 3:
                dirs.clear()  # Don't go deeper
                continue
            
            # Check if current directory is named sdat (case-insensitive)
            current_dir = os.path.basename(root).lower()
            if current_dir == 'sdat':
                # Check for terrain files
                terrain_files = [f for f in files if '.csdat' in f.lower() or '.dat' in f.lower()]
                if terrain_files:
                    return True
            
            # Also check subdirectories
            for dir_name in dirs:
                if dir_name.lower() == 'sdat':
                    return True
        
        return False
    
    def _find_thumbnail(self, level_name: str) -> Optional[str]:
        """Find thumbnail image for the level"""
        # Look in various possible locations
        thumbnail_dirs = [
            os.path.join(self.patch_folder, "thumbnails"),
            os.path.join(self.patch_folder, "images"),
            os.path.join(self.patch_folder, "worlds", level_name),
            os.path.join(self.patch_folder, "levels", level_name)
        ]
        
        # Common thumbnail patterns
        patterns = [
            f"{level_name}.png",
            f"{level_name}_thumb.png",
            f"{level_name}_thumbnail.png",
            "thumbnail.png",
            "thumb.png",
            "preview.png"
        ]
        
        for thumb_dir in thumbnail_dirs:
            if os.path.exists(thumb_dir):
                for pattern in patterns:
                    thumb_path = os.path.join(thumb_dir, pattern)
                    if os.path.exists(thumb_path):
                        return thumb_path
        
        return None
    
    def _count_files(self, worlds_path: str, levels_path: str) -> Dict[str, int]:
        """Count various file types in the level (searches recursively)"""
        counts = {
            'xml_files': 0,
            'fcb_files': 0,
            'objects': 0,
            'terrain_files': 0
        }
        
        # Count world files recursively
        if worlds_path and os.path.exists(worlds_path):
            for root, dirs, files in os.walk(worlds_path):
                # Limit search depth
                depth = root[len(worlds_path):].count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                
                counts['xml_files'] += len([f for f in files if f.lower().endswith('.xml')])
                counts['fcb_files'] += len([f for f in files if f.lower().endswith('.fcb')])
        
        # Count level objects recursively
        if levels_path and os.path.exists(levels_path):
            for root, dirs, files in os.walk(levels_path):
                # Limit search depth
                depth = root[len(levels_path):].count(os.sep)
                if depth > 3:
                    dirs.clear()
                    continue
                
                # Check if in worldsectors directory
                if 'worldsectors' in root.lower() or 'worldsector' in root.lower():
                    counts['objects'] += len([f for f in files if '.data.fcb' in f.lower() or '.data.xml' in f.lower()])
                
                # Check if in sdat directory
                if 'sdat' in root.lower():
                    counts['terrain_files'] += len([f for f in files if '.csdat' in f.lower() or '.dat' in f.lower()])
        
        return counts
    
    def _format_display_name(self, folder_name: str) -> str:
        """Format folder name for display - Avatar: The Game specific formatting"""
        name = folder_name
        
        # Handle prefixes
        prefix_map = {
            "sp_": "SP: ",  # Single Player
            "mp_": "MP: ",  # Multiplayer  
            "coop_": "Co-op: ",
            "z_": "[Dev] "  # Development/Test levels
        }
        
        for prefix, replacement in prefix_map.items():
            if name.startswith(prefix):
                name = replacement + name[len(prefix):]
                break
        
        # Remove the prefix for further processing if it was replaced
        if ": " in name:
            prefix, name_part = name.split(": ", 1)
            name = name_part
        else:
            prefix = ""
            name_part = name
        
        # Handle known level names (Avatar specific)
        known_names = {
            # Single Player levels
            "hellsgate": "Hell's Gate",
            "hometree": "Hometree",
            "bonusmap": "Bonus Map",
            "coualthighlands": "Coualthighlands",
            "drifting_sierra": "Drifting Sierra",
            "dustbowl": "Dustbowl",
            "gravesbog": "Graves Bog",
            "needlehills": "Needle Hills",
            "plainsofgoliath": "Plains of Goliath",
            "vaderashallow": "Vaderas Hollow",
            "vaderashollow": "Vaderas Hollow",  # Alternative spelling
            
            # Multiplayer levels
            "ancientgrounds": "Ancient Grounds",
            "bluelagoon": "Blue Lagoon",
            "brokencage": "Broken Cage",
            "fogswamp": "Fog Swamp",
            "forsakencaldera": "Forsaken Caldera",
            "kowecave": "Kowe Cave",
            "kowevillage": "Kowe Village",
            "mridge": "Mountain Ridge",
            "verdantpinnacle": "Verdant Pinnacle",
            "ps3map": "PS3 Map",
            
            # Developer names (level designers)
            "pascal": "Pascal",
            "jeannormand": "Jean Normand",
            "nancy": "Nancy",
            "philippe": "Philippe",
            "sebastien": "Sebastien",
            "orouleau": "O'Rouleau",
            
            # Other
            "menu": "Main Menu",
            "mpgamemodes": "MP Game Modes",
            "anim_creatures": "Animation Creatures"
        }
        
        # Process the name
        parts = name_part.split("_")
        formatted_parts = []
        
        for part in parts:
            # Skip faction/type codes (rf, rb, fm, df, hg, of)
            if part.lower() in ["rf", "rb", "fm", "df", "hg", "of", "l", "l1", "l2"]:
                continue
            # Skip version numbers
            if part.isdigit() or (len(part) == 2 and part[0] == "0" and part[1].isdigit()):
                continue
            
            # Check if this part is a known name
            part_lower = part.lower()
            if part_lower in known_names:
                formatted_parts.append(known_names[part_lower])
            else:
                # Title case for unknown parts
                formatted_parts.append(part.title())
        
        # Combine the parts
        if formatted_parts:
            formatted_name = " ".join(formatted_parts)
        else:
            # Fallback if all parts were filtered
            formatted_name = name_part.replace("_", " ").title()
        
        # Add the prefix back
        if prefix:
            formatted_name = prefix + formatted_name
        
        return formatted_name
    
    def stop(self):
        """Stop the scanning thread"""
        self.should_stop = True


class LevelButton(QPushButton):
    """Custom button widget for level selection with thumbnail"""

    level_selected = pyqtSignal(LevelInfo)

    THUMBNAILS_DIR = "thumbnails"  # central folder for all PNGs

    def __init__(self, level_info: LevelInfo, default_thumbnail: str = "thumbnails/default.png", annotation=None):
        super().__init__()
        self.level_info = level_info
        self.default_thumbnail = default_thumbnail
        self.annotation = annotation or []

        self.setFixedSize(200, 250)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setup_ui()

        # *** NEW: Update model loader with game-specific paths ***
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'model_loader'):
            from canvas.game_paths_config import update_model_loader_for_game
            update_model_loader_for_game(
                self.canvas.model_loader, 
                self.game_path_config
            )

        self.clicked.connect(lambda: self.level_selected.emit(self.level_info))

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- Thumbnail ---
        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(190, 140)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail_label.setStyleSheet("""
            QLabel {
                border: 1px solid #555;
                border-radius: 5px;
                background-color: #2b2b2b;
            }
        """)

        # Auto-find the PNG based on level name
        level_png = os.path.join(self.THUMBNAILS_DIR, f"{self.level_info.name}.png")
        pixmap = None
        if os.path.exists(level_png):
            pixmap = QPixmap(level_png)
        elif self.default_thumbnail and os.path.exists(self.default_thumbnail):
            pixmap = QPixmap(self.default_thumbnail)

        if pixmap:
            scaled_pixmap = pixmap.scaled(
                190, 140,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            thumbnail_label.setPixmap(scaled_pixmap)
        else:
            thumbnail_label.setText("No Preview")
            thumbnail_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #555;
                    border-radius: 5px;
                    background-color: #1e1e1e;
                    color: #888;
                    font-size: 14px;
                }
            """)

        layout.addWidget(thumbnail_label)

        # --- Level Name ---
        name_label = QLabel(self.level_info.display_name or self.level_info.name)
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        layout.addWidget(name_label)

        # --- Info / Annotations ---
        info_text = self.annotation.copy()
        if getattr(self.level_info, 'has_terrain', False):
            info_text.append("Terrain")
        if getattr(self.level_info, 'has_objects', False):
            obj_count = self.level_info.file_counts.get('objects', 0)
            info_text.append(f"{obj_count} Objects")

        if info_text:
            info_label = QLabel(" | ".join(info_text))
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 10px;
                }
            """)
            layout.addWidget(info_label)

        # --- Button Styling ---
        self.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #353535;
                border: 2px solid #0d7377;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
                border: 2px solid #14ffec;
            }
        """)

    def on_click(self):
        print(f"[DEBUG] LevelButton clicked: {self.level_info.name}")
        self.level_selected.emit(self.level_info)


class LevelSelectorDialog(QDialog):
    """Dialog for visual level selection"""
    level_selected = pyqtSignal(dict)  # Emits level_info dict for loading
    patch_folder_change_requested = pyqtSignal()  # Emits when user wants to change patch folder

    def __init__(self, levels_data: Dict[str, LevelInfo], parent=None, game_mode="avatar", patch_manager=None):
        super().__init__(parent)
        self.levels_data = levels_data
        self.game_mode = game_mode
        self.selected_level = None
        self.patch_manager = patch_manager

        self.setWindowTitle("Select Level")
        self.setModal(True)
        self.resize(1000, 700)

        print(f"[DEBUG] LevelSelectorDialog initialized with {len(self.levels_data)} levels")

        self.setup_ui()

    def setup_ui(self):
        """Setup the complete user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Determine theme colors based on parent's theme
        is_dark = False
        if self.parent() and hasattr(self.parent(), 'force_dark_theme'):
            is_dark = self.parent().force_dark_theme
        
        # Define theme colors
        if is_dark:
            colors = {
                'bg': '#2b2b2b',
                'bg_alt': '#1e1e1e',
                'button': '#404040',
                'button_hover': '#4a4a4a',
                'button_pressed': '#353535',
                'input': '#353535',
                'border': '#555555',
                'text': '#ffffff',
                'text_secondary': '#888888',
                'accent': '#0d7377',
            }
        else:
            colors = {
                'bg': '#f0f0f0',
                'bg_alt': '#ffffff',
                'button': '#e0e0e0',
                'button_hover': '#d0d0d0',
                'button_pressed': '#c0c0c0',
                'input': '#ffffff',
                'border': '#b0b0b0',
                'text': '#000000',
                'text_secondary': '#666666',
                'accent': '#0078d7',
            }

        # Header with patch folder info
        header_layout = QVBoxLayout()
        header_label = QLabel("Select a Level to Load")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet(f"""
            QLabel {{
                font-size: 16px; 
                font-weight: bold; 
                padding: 10px;
                color: {colors['text']};
            }}
        """)
        header_layout.addWidget(header_label)
        
        # Patch folder info and button
        patch_info_layout = QHBoxLayout()
        patch_info_layout.addStretch()
        
        if self.patch_manager:
            patch_folder = self.patch_manager.get_patch_folder()
            if patch_folder:
                # Truncate long paths for display
                display_path = patch_folder
                if len(display_path) > 60:
                    display_path = "..." + display_path[-57:]
                folder_label = QLabel(f"Patch Folder: {display_path}")
                folder_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px;")
                folder_label.setToolTip(patch_folder)  # Show full path on hover
                patch_info_layout.addWidget(folder_label)
        
        change_folder_btn = QPushButton("Change Patch Folder...")
        change_folder_btn.setMaximumWidth(180)
        change_folder_btn.clicked.connect(self.on_change_patch_folder)
        change_folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['button']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 5px 10px;
                color: {colors['text']};
            }}
            QPushButton:hover {{
                background-color: {colors['button_hover']};
                border: 1px solid {colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {colors['button_pressed']};
            }}
        """)
        patch_info_layout.addWidget(change_folder_btn)
        patch_info_layout.addStretch()
        header_layout.addLayout(patch_info_layout)
        
        layout.addLayout(header_layout)

        # Separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"background-color: {colors['border']};")
        layout.addWidget(separator)

        # Filter and search controls
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # Filter dropdown
        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet(f"color: {colors['text']}; font-weight: bold;")
        filter_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "All Levels", 
            "Complete Levels", 
            "World Only", 
            "Has Terrain", 
            "Has Objects"
        ])
        self.filter_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {colors['input']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 5px;
                color: {colors['text']};
                min-width: 150px;
            }}
            QComboBox:hover {{
                border: 1px solid {colors['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {colors['text']};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['input']};
                border: 1px solid {colors['border']};
                selection-background-color: {colors['accent']};
                color: {colors['text']};
            }}
        """)
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.filter_combo)

        filter_layout.addSpacing(20)

        # Search box
        search_label = QLabel("Search:")
        search_label.setStyleSheet(f"color: {colors['text']}; font-weight: bold;")
        filter_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search levels...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {colors['input']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 5px;
                color: {colors['text']};
            }}
            QLineEdit:focus {{
                border: 1px solid {colors['accent']};
            }}
        """)
        self.search_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.search_input, 1)  # Stretch factor of 1

        layout.addLayout(filter_layout)

        # Level count label
        self.count_label = QLabel()
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setStyleSheet(f"color: {colors['text_secondary']}; font-size: 11px; padding: 5px;")
        layout.addWidget(self.count_label)

        # Scroll area for level buttons
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {colors['border']};
                background-color: {colors['bg_alt']};
            }}
            QScrollBar:vertical {{
                background-color: {colors['button']};
                width: 12px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {colors['border']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {colors['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        scroll_area.setWidget(container)
        layout.addWidget(scroll_area, 1)  # Stretch factor of 1

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumWidth(100)
        cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors['button']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 8px 16px;
                color: {colors['text']};
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {colors['button_hover']};
                border: 1px solid {colors['accent']};
            }}
            QPushButton:pressed {{
                background-color: {colors['button_pressed']};
            }}
        """)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)

        # Populate levels
        self.populate_levels()

    def populate_levels(self, filter_text="", filter_type="All Levels"):
        """Populate the grid with level buttons"""
        # Clear existing buttons
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get default thumbnail based on game mode
        default_thumb = "avatar_default_level.png" if self.game_mode != "farcry2" else "fc2_default_level.png"

        # Filter levels
        filtered_levels = []
        for name, level_info in self.levels_data.items():
            has_world = bool(level_info.worlds_path)
            has_level = bool(level_info.levels_path)

            # Apply text filter
            if filter_text:
                filter_lower = filter_text.lower()
                name_match = filter_lower in name.lower()
                display_match = level_info.display_name and filter_lower in level_info.display_name.lower()
                if not (name_match or display_match):
                    continue

            # Apply type filter
            if filter_type == "Complete Levels" and not (has_world and has_level):
                continue
            elif filter_type == "World Only" and not has_world:
                continue
            elif filter_type == "Has Terrain" and not level_info.has_terrain:
                continue
            elif filter_type == "Has Objects" and not level_info.has_objects:
                continue

            # Determine annotation for display
            annotation = []
            if has_world and not has_level:
                annotation.append("World Only")
            elif has_level and not has_world:
                annotation.append("Level Only")
            elif has_world and has_level:
                annotation.append("World + Level")

            filtered_levels.append((name, level_info, annotation))

        # Sort levels alphabetically by display name
        filtered_levels.sort(key=lambda x: x[1].display_name or x[0])

        # Update count label
        total_levels = len(self.levels_data)
        filtered_count = len(filtered_levels)
        if filtered_count == total_levels:
            self.count_label.setText(f"Showing {total_levels} level{'s' if total_levels != 1 else ''}")
        else:
            self.count_label.setText(f"Showing {filtered_count} of {total_levels} level{'s' if total_levels != 1 else ''}")

        # Add buttons to grid
        row, col = 0, 0
        max_cols = 4
        
        if not filtered_levels:
            # Show "no results" message
            no_results = QLabel("No levels match your search criteria")
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 14px;
                    padding: 40px;
                }
            """)
            self.grid_layout.addWidget(no_results, 0, 0, 1, max_cols)
        else:
            for name, level_info, annotation in filtered_levels:
                button = LevelButton(level_info, default_thumb, annotation)
                button.level_selected.connect(self.on_level_selected)
                self.grid_layout.addWidget(button, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            # Add empty space filler at the end
            spacer = QWidget()
            spacer.setSizePolicy(
                spacer.sizePolicy().horizontalPolicy(),
                spacer.sizePolicy().verticalPolicy()
            )
            self.grid_layout.addWidget(spacer, row + 1, 0, 1, max_cols)

    def apply_filter(self):
        """Apply current filter and search criteria"""
        filter_text = self.search_input.text()
        filter_type = self.filter_combo.currentText()
        self.populate_levels(filter_text, filter_type)

    def on_level_selected(self, level_info: LevelInfo):
        """Handle level selection"""
        print(f"[DEBUG] Level selected: {level_info.name}")
        level_dict = {
            'name': level_info.name,
            'worlds_path': getattr(level_info, 'worlds_path', None),
            'levels_path': getattr(level_info, 'levels_path', None),
            'base_folder': os.path.dirname(getattr(level_info, 'worlds_path', None) or getattr(level_info, 'levels_path', None))
        }
        self.selected_level = level_dict
        self.level_selected.emit(level_dict)
        print(f"[DEBUG] LevelSelectorDialog accepted with: {self.selected_level}")
        self.accept()
    
    def on_change_patch_folder(self):
        """Handle patch folder change request"""
        print("[DEBUG] Change patch folder requested")
        if self.patch_manager:
            print("[DEBUG] Calling set_patch_folder...")
            # Call set_patch_folder directly - this opens the folder browser
            if self.patch_manager.set_patch_folder():
                # Folder changed successfully, close and signal to rescan
                print("[DEBUG] Patch folder changed successfully, closing dialog")
                self.patch_folder_change_requested.emit()
                self.accept()  # Close with success
            else:
                print("[DEBUG] Patch folder selection cancelled, keeping dialog open")
                # If set_patch_folder returns False (cancelled), do nothing - keep dialog open
        else:
            print("[DEBUG ERROR] patch_manager is None!")
            QMessageBox.information(
                self,
                "Change Patch Folder",
                "Patch folder manager not available."
            )

class PatchFolderManager:
    """Main manager class for patch folder operations"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.patch_folder: Optional[str] = None
        self.levels_data: dict = {}
        self.scanner_thread: Optional[PatchFolderScanner] = None
        
        # Load saved patch folder configuration
        self.load_config()
    
    def load_config(self):
        """Load saved patch folder configuration"""
        if os.path.exists(PATCH_CONFIG_FILE):
            try:
                with open(PATCH_CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    folder = config.get('patch_folder')
                    if folder and os.path.exists(folder):
                        self.patch_folder = folder
                        print(f"Loaded patch folder from config: {self.patch_folder}")
                    else:
                        print(f"Saved patch folder not found: {folder}")
            except Exception as e:
                print(f"Error loading patch config: {e}")
    
    def save_config(self):
        """Save patch folder configuration"""
        try:
            config = {'patch_folder': self.patch_folder}
            with open(PATCH_CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"Saved patch folder to config: {self.patch_folder}")
        except Exception as e:
            print(f"Error saving patch config: {e}")
    
    def set_patch_folder(self):
        """Let user select and set the patch folder"""
        folder = QFileDialog.getExistingDirectory(
            self.parent,
            "Select Patch Folder (containing 'worlds' and 'levels' subdirectories)",
            self.patch_folder or ""
        )
        
        if not folder:
            return False
        
        # Validate folder structure
        worlds_dir = os.path.join(folder, "worlds")
        levels_dir = os.path.join(folder, "levels")
        
        if not os.path.exists(worlds_dir) and not os.path.exists(levels_dir):
            reply = QMessageBox.warning(
                self.parent,
                "Invalid Patch Folder",
                f"The selected folder doesn't contain 'worlds' or 'levels' subdirectories.\n\n"
                f"Selected: {folder}\n\n"
                "Please select a valid patch folder or create the required structure.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return False
        
        self.patch_folder = folder
        self.save_config()
        self.scan_patch_folder()
        return True
    
    def scan_patch_folder(self, show_progress=True):
        """
        Scan the patch folder for available levels with EnhancedProgressDialog.
        Populates self.levels_data and emits signals for completion or error.
        """
        if not self.patch_folder or not os.path.exists(self.patch_folder):
            QMessageBox.warning(
                self.parent,
                "Patch Folder Not Found",
                f"The configured patch folder is invalid or missing:\n{self.patch_folder}"
            )
            self.patch_folder = None
            self.levels_data = {}
            return False

        # Stop existing thread if running
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self.scanner_thread.wait(2000)

        # Get game mode from parent if available
        game_mode = "avatar"
        if self.parent and hasattr(self.parent, 'game_mode'):
            game_mode = self.parent.game_mode

        # Create EnhancedProgressDialog instead of QProgressDialog
        from simplified_map_editor import EnhancedProgressDialog  # Import at the top of file
        
        progress_dialog = None
        if show_progress:
            progress_dialog = EnhancedProgressDialog(
                "Scanning Patch Folder", 
                self.parent, 
                game_mode=game_mode
            )
            progress_dialog.append_log(f"Scanning folder: {os.path.basename(self.patch_folder)}")
            progress_dialog.show()
            QApplication.processEvents()

        # Get file_converter from parent if available
        file_converter = None
        if self.parent and hasattr(self.parent, 'file_converter'):
            file_converter = self.parent.file_converter

        self.scanner_thread = PatchFolderScanner(self.patch_folder, file_converter)

        def on_complete(levels_data):
            self.levels_data = levels_data or {}
            if progress_dialog:
                progress_dialog.set_progress(100)
                progress_dialog.mark_complete()
                progress_dialog.stop_icon()
                progress_dialog.close()
            print(f"Scan complete: Found {len(self.levels_data)} levels")
            if self.parent:
                QMessageBox.information(
                    self.parent,
                    "Scan Complete",
                    f"Found {len(self.levels_data)} levels in patch folder."
                )

        def on_error(msg):
            self.levels_data = {}
            if progress_dialog:
                progress_dialog.append_log(f"ERROR: {msg}")
                progress_dialog.mark_complete()
                progress_dialog.stop_icon()
                progress_dialog.close()
            print(f"Scan error: {msg}")
            if self.parent:
                QMessageBox.critical(self.parent, "Scan Error", msg)

        def on_progress(percent, message):
            if progress_dialog:
                progress_dialog.set_progress(percent)
                progress_dialog.set_status(message)
                progress_dialog.append_log(message)
                QApplication.processEvents()

        self.scanner_thread.scan_complete.connect(on_complete)
        self.scanner_thread.error_occurred.connect(on_error)
        self.scanner_thread.progress_updated.connect(on_progress)
        
        if progress_dialog:
            progress_dialog.cancelled.connect(self.scanner_thread.stop)

        self.scanner_thread.finished.connect(self.on_scan_thread_finished)
        self.scanner_thread.start()
        return True
    
    def on_scan_thread_finished(self):
        """Clean up when scan thread finishes"""
        if self.scanner_thread:
            self.scanner_thread.deleteLater()
            self.scanner_thread = None
        print("Scanner thread finished")
    
    def on_scan_complete(self, levels_data: dict, progress_dialog=None):
        """Handle scan completion"""
        self.levels_data = levels_data
        if progress_dialog:
            progress_dialog.close()
        print(f"Scan complete: Found {len(levels_data)} levels")
        if self.parent:
            QMessageBox.information(
                self.parent,
                "Scan Complete",
                f"Found {len(levels_data)} levels in patch folder."
            )
    
    def on_scan_error(self, error_msg: str, progress_dialog=None):
        """Handle scan error"""
        if progress_dialog:
            progress_dialog.close()
        print(f"Scan error: {error_msg}")
        if self.parent:
            QMessageBox.critical(self.parent, "Scan Error", error_msg)
    
    def match_worlds_to_levels(self):
        """
        Match world folders to their corresponding level folders.
        If a world has no matching level, create a 'world-only' entry.
        """
        self.levels_data = {}  # Reset levels data

        for world_name, world_path in self.worlds.items():
            matched_levels = []

            # Try to find levels that match this world
            for level_name, level_path in self.levels.items():
                if level_name.startswith(world_name):
                    matched_levels.append(level_name)

            # If no levels, create a 'world-only' entry
            if not matched_levels:
                matched_levels.append(f"{world_name}_world_only")

            # Save in levels_data
            self.levels_data[world_name] = matched_levels
    
    def get_level_info(self, level_name: str) -> Optional[dict]:
        """Get info for a specific level"""
        if level_name in self.levels_data:
            level_info = self.levels_data[level_name]
            return dict(
                name=level_info.name,
                worlds_path=level_info.worlds_path,
                levels_path=level_info.levels_path,
                base_folder=os.path.dirname(level_info.worlds_path)
            )
        return None
    
    def get_patch_folder(self) -> Optional[str]:
        return self.patch_folder
    
    def is_configured(self) -> bool:
        return self.patch_folder is not None and os.path.exists(self.patch_folder)
    
    def cleanup(self):
        """Clean up resources"""
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            if not self.scanner_thread.wait(2000):
                print("Warning: scanner thread did not stop, terminating...")
                self.scanner_thread.terminate()
                self.scanner_thread.wait(1000)
        if self.scanner_thread:
            self.scanner_thread.deleteLater()
            self.scanner_thread = None
        print("PatchFolderManager cleanup complete")

def integrate_patch_manager(main_window):
    print("\n[DEBUG] integrate_patch_manager() CALLED")

    # Create PatchFolderManager instance
    print("[DEBUG] Creating PatchFolderManager instance...")
    main_window.patch_manager = PatchFolderManager(main_window)
    patch_manager = main_window.patch_manager
    
    # *** SET WORLDS_FOLDER FROM PATCH_MANAGER ***
    if patch_manager.is_configured():
        worlds_dir = os.path.join(patch_manager.patch_folder, "worlds")
        if os.path.exists(worlds_dir):
            main_window.worlds_folder = worlds_dir
            print(f"✅ Set worlds_folder from patch config: {main_window.worlds_folder}")
        else:
            # Try alternative naming (capital W)
            worlds_dir_alt = os.path.join(patch_manager.patch_folder, "Worlds")
            if os.path.exists(worlds_dir_alt):
                main_window.worlds_folder = worlds_dir_alt
                print(f"✅ Set worlds_folder (alt case): {main_window.worlds_folder}")
            else:
                print(f"⚠️  Could not find worlds subdirectory in patch folder: {patch_manager.patch_folder}")
    else:
        print("⚠️  Patch folder not configured, worlds_folder not set")

    # Add menu option for setting patch folder
    if hasattr(main_window, "menuBar"):
        file_menu = None
        for act in main_window.menuBar().actions():
            if act.text() == "File":
                file_menu = act.menu()
                break

        if file_menu:
            action = QAction("Set Patch Folder...", main_window)
            action.triggered.connect(lambda: on_patch_folder_changed(patch_manager, main_window))
            file_menu.addAction(action)
            file_menu.addSeparator()

    # -------------------------------------------------------------------------
    # NEW FIXED select_level METHOD - REPLACES ORIGINAL
    # -------------------------------------------------------------------------
    def new_select_level(self):
        # PREVENT RE-ENTRY - Critical to avoid infinite loops
        if hasattr(main_window, '_selecting_level') and main_window._selecting_level:
            print("⚠️ Already selecting level, ignoring duplicate call")
            return
        
        main_window._selecting_level = True
        
        try:
            print("\n=== STARTING LEVEL SELECTION (ENHANCED) ===")

            # PARTIAL RESET - Don't trigger game selector
            if hasattr(main_window, 'reset_editor_state_no_game_change'):
                main_window.reset_editor_state_no_game_change()
            else:
                # Fallback: manual partial reset
                print("⚠️ Using fallback partial reset")
                main_window.entities = []
                main_window.objects = []
                main_window.selected_entity = None
                if hasattr(main_window, 'canvas'):
                    main_window.canvas.entities = []
                    main_window.canvas.selected = []
                    main_window.canvas.selected_entity = None

            if not patch_manager.is_configured():
                print("[DEBUG] Patch folder not configured, prompting user...")
                reply = QMessageBox.question(
                    main_window,
                    "Patch Folder Not Set",
                    "No patch folder is configured. Would you like to set one now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if not patch_manager.set_patch_folder():
                        print("[DEBUG] User cancelled folder selection")
                        return
                    else:
                        # Update worlds_folder after setting patch folder
                        update_worlds_folder(patch_manager, main_window)
                else:
                    print("[DEBUG] User declined to set patch folder")
                    return

            # Scan patch folder if levels_data is empty
            if not patch_manager.levels_data:
                print("[DEBUG] No levels_data, scanning patch folder...")
                
                # Import EnhancedProgressDialog
                from simplified_map_editor import EnhancedProgressDialog
                
                # Create enhanced progress dialog
                progress_dialog = EnhancedProgressDialog(
                    "Scanning Patch Folder", 
                    main_window, 
                    game_mode=main_window.game_mode
                )
                progress_dialog.append_log(f"Scanning: {os.path.basename(patch_manager.patch_folder)}")
                progress_dialog.show()
                QApplication.processEvents()

                # Get file_converter from main_window
                file_converter = main_window.file_converter if hasattr(main_window, 'file_converter') else None
                
                scanner_thread = PatchFolderScanner(patch_manager.patch_folder, file_converter)
                patch_manager.scanner_thread = scanner_thread

                scan_completed = [False]
                
                def on_complete(levels_data):
                    patch_manager.levels_data = levels_data or {}
                    progress_dialog.set_progress(100)
                    progress_dialog.append_log(f"✓ Scan complete: {len(patch_manager.levels_data)} levels found")
                    progress_dialog.mark_complete()
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    scan_completed[0] = True
                    print(f"[DEBUG] Scan complete: Found {len(patch_manager.levels_data)} levels")

                def on_error(msg):
                    patch_manager.levels_data = {}
                    progress_dialog.append_log(f"✗ Error: {msg}")
                    progress_dialog.mark_complete()
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    scan_completed[0] = True
                    print(f"[DEBUG] Scan error: {msg}")
                    QMessageBox.critical(main_window, "Scan Error", msg)

                def on_progress(percent, message):
                    if progress_dialog.was_cancelled:
                        return
                    progress_dialog.set_progress(percent)
                    progress_dialog.set_status(message)
                    progress_dialog.append_log(message)
                    QApplication.processEvents()

                scanner_thread.scan_complete.connect(on_complete)
                scanner_thread.error_occurred.connect(on_error)
                scanner_thread.progress_updated.connect(on_progress)
                progress_dialog.cancelled.connect(scanner_thread.stop)
                scanner_thread.start()

                # Wait for scan to complete
                while not scan_completed[0]:
                    QApplication.processEvents()
                
                print("[DEBUG] Scan finished.")

            # Check again after scan
            if not patch_manager.levels_data:
                print("[DEBUG ERROR] No levels found after scan")
                QMessageBox.warning(
                    main_window,
                    "No Levels Found",
                    "Patch scan returned 0 usable levels."
                )
                return

            # Now show the level selector dialog with the scanned data
            print("[DEBUG] Showing level selector dialog...")
            print(f"[DEBUG] Creating dialog with {len(patch_manager.levels_data)} levels")
            
            dialog = LevelSelectorDialog(
                patch_manager.levels_data, 
                main_window, 
                main_window.game_mode, 
                patch_manager
            )
            print(f"[DEBUG] Dialog created with patch_manager: {dialog.patch_manager is not None}")
            
            def on_level_selected(lvl):
                print(f"[DEBUG] Level selected signal received: {lvl}")

            def on_patch_folder_change():
                print("[DEBUG] Patch folder change completed, clearing data and restarting")
                update_worlds_folder(patch_manager, main_window)
                patch_manager.levels_data = {}
                dialog.close()
                QTimer.singleShot(100, new_select_level)

            dialog.level_selected.connect(on_level_selected)
            dialog.patch_folder_change_requested.connect(on_patch_folder_change)

            result = dialog.exec()
            print(f"[DEBUG] Level selector exec result: {result}")
            
            if result == QDialog.DialogCode.Accepted and hasattr(dialog, 'selected_level') and dialog.selected_level:
                level_dict = dialog.selected_level
                print("[DEBUG] level_dict returned:")
                for k, v in level_dict.items():
                    print(f"    {k} = {v}")

                wp = level_dict.get("worlds_path")
                lp = level_dict.get("levels_path")

                # Validate paths - be more lenient
                worlds_valid = main_window.validate_worlds_folder(wp) if wp else True
                levels_valid = main_window.validate_levels_folder(lp) if lp else True

                print(f"[DEBUG] Validation results: worlds_valid={worlds_valid}, levels_valid={levels_valid}")

                # Only proceed if we have at least one valid path
                if (wp and worlds_valid) or (lp and levels_valid):
                    print("[DEBUG] Calling load_complete_level() with selected level")
                    main_window.load_complete_level(level_dict)
                else:
                    print("[DEBUG ERROR] Neither worlds nor levels paths are valid")
                    QMessageBox.warning(
                        main_window,
                        "Invalid Level",
                        "The selected level has no valid world or level data."
                    )
            else:
                print("[DEBUG] User cancelled level selection")
        
        finally:
            # Always release the lock
            main_window._selecting_level = False

    # REPLACE the original select_level method (don't layer on top!)
    import types
    main_window.select_level = types.MethodType(new_select_level, main_window)
    print("[DEBUG] ✓ Patched select_level method (replaced original)")
    
    # Also update the action if it exists
    if hasattr(main_window, 'select_level_action'):
        # Reconnect action to use new method
        try:
            main_window.select_level_action.triggered.disconnect()
        except:
            pass
        main_window.select_level_action.triggered.connect(main_window.select_level)
        print("[DEBUG] ✓ Reconnected select_level_action")

def update_worlds_folder(patch_manager, main_window):
    """Helper function to update worlds_folder when patch folder changes"""
    if patch_manager.is_configured():
        worlds_dir = os.path.join(patch_manager.patch_folder, "worlds")
        if os.path.exists(worlds_dir):
            main_window.worlds_folder = worlds_dir
            print(f"✅ Updated worlds_folder: {main_window.worlds_folder}")
        else:
            # Try alternative naming (capital W)
            worlds_dir_alt = os.path.join(patch_manager.patch_folder, "Worlds")
            if os.path.exists(worlds_dir_alt):
                main_window.worlds_folder = worlds_dir_alt
                print(f"✅ Updated worlds_folder (alt case): {main_window.worlds_folder}")
            else:
                print(f"⚠️  Could not find worlds subdirectory in patch folder: {patch_manager.patch_folder}")
                main_window.worlds_folder = None
    else:
        print("⚠️  Patch folder not configured, worlds_folder cleared")
        main_window.worlds_folder = None

def on_patch_folder_changed(patch_manager, main_window):
    """Handler for when user manually sets patch folder from menu"""
    if patch_manager.set_patch_folder():
        update_worlds_folder(patch_manager, main_window)
        QMessageBox.information(
            main_window,
            "Patch Folder Updated",
            f"Patch folder has been set to:\n{patch_manager.patch_folder}\n\n"
            f"Worlds folder: {main_window.worlds_folder if hasattr(main_window, 'worlds_folder') else 'Not found'}"
        )
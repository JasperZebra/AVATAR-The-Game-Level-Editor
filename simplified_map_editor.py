# PyQt6 UI Components
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QApplication, QFileDialog, 
    QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QGroupBox, QDockWidget,
    QStatusBar, QMessageBox, QToolBar, QComboBox, 
    QProgressDialog, QProgressBar, QDialog,
    QTreeWidget, QTreeWidgetItem, 
    QLineEdit, QInputDialog, QListWidgetItem,
    QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation
from PyQt6.QtGui import (
    QAction, QColor, QVector3D, QShortcut, 
    QActionGroup, QFont, QPixmap, QPainter, QTransform
)

# Application modules
from data_models import (
    Entity, GridConfig, MapInfo, ObjectEntity, 
    WorldSectorManager, ObjectParser, ObjectLoadResult
)

from entity_export_import import (
    show_entity_export_dialog, 
    show_entity_import_dialog,
    setup_entity_export_import_system
)

from set_patch_folder import LevelSelectorDialog, integrate_patch_manager
from cache_manager import get_cache_manager, shutdown_cache_manager
from canvas.terrain_renderer import TerrainRenderer
from canvas.map_canvas_gpu import MapCanvas
from file_converter import FileConverter
from all_in_one_copy_paste import setup_complete_smart_system
from entity_export_import import setup_entity_export_import_system

# Standard library
import time
import glob
import math
import sys
import os
import xml.etree.ElementTree as ET
import shutil
import subprocess
import platform
from pathlib import Path

class SimplifiedMapEditor(QMainWindow):
    """Simplified main application window for XML Entity Coordinate Editor"""
    
    def __init__(self, game_mode="avatar"):
        """Fixed initialization method with game mode support and patch folder integration
            
        Args:
            game_mode (str): Either "avatar" or "farcry2"
        """
        super().__init__()
            
        # Store game mode FIRST
        self.game_mode = game_mode

        # Create startup progress dialog
        from simplified_map_editor import EnhancedProgressDialog
        startup_dialog = EnhancedProgressDialog(
            "Initializing Editor", 
            None,  # No parent yet since we're in __init__
            game_mode=game_mode
        )
        startup_dialog.show()
        QApplication.processEvents()
        
        def log(msg):
            """Helper to log to both console and dialog"""
            print(msg)
            startup_dialog.append_log(msg)
            QApplication.processEvents()

        # *** NEW: Setup game-specific paths ***
        startup_dialog.set_status("Setting up game paths...")
        startup_dialog.set_progress(5)
        log(f"Initializing editor for: {game_mode}")
        
        from canvas.game_paths_config import setup_game_paths
        setup_game_paths(self)

        self.current_mode = "2D"

        # ================================================================
        #   WORLDS FOLDER AUTO-DETECTION  (REQUIRED FOR 3D MODELS)
        # ================================================================
        startup_dialog.set_status("Detecting game folders...")
        startup_dialog.set_progress(10)
        
        self.worlds_folder = None
        self.game_data_path = None

        window_title_prefix = "Avatar: The Game" if game_mode == "avatar" else "Far Cry 2"

        # ================================================================
        #   CACHE MANAGER
        # ================================================================
        startup_dialog.set_status("Initializing cache manager...")
        startup_dialog.set_progress(15)
        self.cache = get_cache_manager()
        log("✓ Cache manager initialized")
            
        # ================================================================
        #   BASIC PROPERTIES
        # ================================================================
        startup_dialog.set_status("Setting up data structures...")
        startup_dialog.set_progress(20)
        self.entities = []
        self.selected_entity = None
        self.xml_tree = None
        self.xml_file_path = None
            
        # ================================================================
        #   GRID CONFIG
        # ================================================================
        if game_mode == "farcry2":
            self.grid_config = GridConfig(
                sector_count_x=16,
                sector_count_y=16,
                sector_granularity=64,
                maps=[]
            )
            self.is_fc2_world = True
            self.world_grid_size = 5
            self.current_fc2_world = "world1"
            self.current_fc2_region = None
        else:
            self.grid_config = GridConfig(
                sector_count_x=16,
                sector_count_y=16,
                sector_granularity=64,
                maps=[]
            )
            self.is_fc2_world = False
            
        self.current_map = None

        # Entity editor
        self.entity_editor = None        

        # Modification tracking
        self.entities_modified = False
        self.xml_tree_modified = False
        self.omnis_tree_modified = False
        self.managers_tree_modified = False
        self.sectordep_tree_modified = False

        # WorldSectors
        self.objects = []
        self.worldsectors_path = None
        self.objects_modified = False
        self.show_objects = True
        self.worldsectors_trees = {}
        self.worldsectors_modified = {}

        # SDAT support
        self.sdat_path = None
        self.terrain_viewer = None
        self.terrain_dock = None

        # Additional trees
        self.omnis_tree = None
        self.managers_tree = None
        self.sectordep_tree = None

        # Caches & config
        self.tree_entity_type_cache = {}
        self._last_selection_log_time = 0
        self.file_config = LevelFileConfig()

        # User preferences
        self.force_dark_theme = False
        self.invert_mouse_pan = False

        # UI setup
        startup_dialog.set_status("Setting up menus...")
        startup_dialog.set_progress(25)
        self.setup_cache_menu() 
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.setup_mode_indicator()

        # Conversion tools
        startup_dialog.set_status("Initializing file converter...")
        startup_dialog.set_progress(30)
        try:
            self.setup_conversion_tools()
            log("✓ File converter initialized")
        except Exception as e:
            log(f"⚠ Could not setup conversion tools: {e}")
            self.file_converter = None

        # ================================================================
        # CRITICAL: Setup copy/paste system BEFORE creating UI
        # This binds all the methods that the UI components need
        # ================================================================
        startup_dialog.set_status("Setting up copy/paste system...")
        startup_dialog.set_progress(35)
        try:
            setup_complete_smart_system(self)
            # Note: setup_complete_smart_system binds all necessary methods including:
            # - copy_selected_entities
            # - paste_entities  
            # - duplicate_selected_entities
            # - delete_selected_entities
            # - select_all_entities (needed by entity browser!)
            # - get_all_existing_entity_ids
            # - get_all_existing_entity_names
            # - generate_new_entity_id
            # - generate_unique_entity_name
            # - _find_best_worldsector_for_entity
            # - _add_entity_xml_to_sector
            log("✓ Copy/paste system ready")
        except Exception as e:
            log(f"⚠ Could not setup copy/paste: {e}")

        # Main UI (creates canvas and entity browser)
        # NOW the UI can safely reference methods like select_all_entities
        startup_dialog.set_status("Creating main interface...")
        startup_dialog.set_progress(40)
        try:
            self.setup_ui()
            log("✓ Main UI created")
        except Exception as e:
            log(f"✗ Error setting up UI: {e}")
            raise

        # *** CRITICAL FIX: Setup enhanced context menu AFTER canvas is created ***
        startup_dialog.set_status("Setting up context menu...")
        startup_dialog.set_progress(45)
        try:
            self.add_sector_move_to_context_menu()
            log("✓ Enhanced context menu ready")
        except Exception as e:
            log(f"⚠ Could not setup context menu: {e}")

        # *** NEW: Update model loader with game-specific paths ***
        startup_dialog.set_status("Configuring 3D model loader...")
        startup_dialog.set_progress(50)
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'model_loader'):
            from canvas.game_paths_config import update_model_loader_for_game
            update_model_loader_for_game(
                self.canvas.model_loader, 
                self.game_path_config
            )
            log("✓ Model loader configured")

        # ================================================================
        #   LINK CANVAS (NO MODEL INITIALIZATION HERE ANYMORE!)
        # ================================================================
        startup_dialog.set_status("Linking canvas...")
        startup_dialog.set_progress(60)
        if hasattr(self, 'canvas'):
            self.canvas.editor = self
            self.canvas.is_fc2_world = self.is_fc2_world
            self.canvas.game_mode = self.game_mode
                
            if self.worlds_folder:
                self.canvas.main_window = self
                log("✓ Canvas linked for 3D models")

        # ================================================================
        #   Sector boundaries UI
        # ================================================================
        startup_dialog.set_status("Setting up sector boundaries...")
        startup_dialog.set_progress(65)
        try:
            self.setup_sector_boundary_ui()
            log("✓ Sector boundaries configured")
        except Exception as e:
            log(f"⚠ Could not setup sector boundaries: {e}")

        # Window title
        self.setWindowTitle(f"{window_title_prefix} Level Editor | Version 1.8 | Made By: Jasper Zebra")

        # Connect entity selection
        startup_dialog.set_status("Connecting signals...")
        startup_dialog.set_progress(70)
        try:
            self.canvas.entitySelected.connect(self.on_entity_selected)
            log("✓ Entity selection connected")
        except Exception as e:
            log(f"⚠ Could not connect entity selection: {e}")

        # Window size
        self.resize(1800, 1100)

        # Theme
        startup_dialog.set_status("Applying theme...")
        startup_dialog.set_progress(75)
        try:
            self.apply_theme()
            if hasattr(self, 'theme_toggle_action'):
                self.theme_toggle_action.setChecked(self.force_dark_theme)
                self.theme_toggle_action.setText("Light Mode" if self.force_dark_theme else "Dark Mode")
            log("✓ Theme applied")
        except Exception as e:
            log(f"⚠ Could not apply theme: {e}")

        # Entity import/export
        startup_dialog.set_status("Setting up entity export/import...")
        startup_dialog.set_progress(85)
        try:
            setup_entity_export_import_system(self)
            log("✓ Entity export/import ready")
        except Exception as e:
            log(f"⚠ Could not setup entity export/import: {e}")

        # Patch folder integration
        startup_dialog.set_status("Integrating patch manager...")
        startup_dialog.set_progress(90)
        try:
            from set_patch_folder import integrate_patch_manager
            integrate_patch_manager(self)
            log("✓ Patch manager integrated")
                
            if hasattr(self, 'patch_manager') and not self.patch_manager.is_configured():
                QTimer.singleShot(1000, lambda: self.status_bar.showMessage(
                    "Tip: Set your patch folder via File → Set Patch Folder", 5000))
        except Exception as e:
            log(f"⚠ Could not integrate patch manager: {e}")

        startup_dialog.set_status("Finalizing initialization...")
        startup_dialog.set_progress(95)
        log(f"✓ Editor initialization complete for {game_mode}")

        # Close startup dialog
        startup_dialog.set_progress(100)
        startup_dialog.mark_complete()
        startup_dialog.stop_icon()
        startup_dialog.close()

        # Welcome screen
        try:
            QTimer.singleShot(100, self.show_welcome_message_conditionally)
        except Exception as e:
            print(f"Warning: Could not show welcome message: {e}")

    def capture_canvas_logs(self, startup_dialog):
        """Capture and display canvas initialization logs"""
        import sys
        from io import StringIO
        
        # Create a custom stdout that captures prints
        class TeeOutput:
            def __init__(self, dialog):
                self.terminal = sys.stdout
                self.dialog = dialog
                
            def write(self, message):
                self.terminal.write(message)
                if message.strip():  # Only log non-empty lines
                    self.dialog.append_log(message.strip())
                    QApplication.processEvents()
                    
            def flush(self):
                self.terminal.flush()
        
        # Replace stdout temporarily
        old_stdout = sys.stdout
        sys.stdout = TeeOutput(startup_dialog)
        
        return old_stdout

    def setup_ui(self):
        """Initialize the UI components - UPDATED with game mode support"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menus()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create canvas for editing
        print("Initializing canvas...")
        self.canvas = MapCanvas(self)
        
        # Set invert mouse pan preference if canvas supports it
        if hasattr(self.canvas, 'invert_mouse_pan'):
            self.canvas.invert_mouse_pan = self.invert_mouse_pan
        
        # Pass game mode to canvas and editor references
        if hasattr(self.canvas, 'game_mode'):
            self.canvas.game_mode = self.game_mode
        self.canvas.editor = self
        self.canvas.is_fc2_world = (self.game_mode == "farcry2")
        
        main_layout.addWidget(self.canvas)
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Set status bar message based on game mode
        if self.game_mode == "farcry2":
            self.status_bar.showMessage("Far Cry 2 Mode - Ready to load world")
        else:
            self.status_bar.showMessage("Avatar Mode - Ready to load level")
        
        # CRITICAL: Make sure these are called
        self.create_side_panel()      # â† This should be here
        self.create_entity_browser()  # â† And this
                        
        # Connect entity selection signal from canvas to handler
        try:
            self.canvas.entitySelected.connect(self.on_entity_selected)
        except Exception as e:
            print(f"Warning: Could not connect entity selection signal: {e}")

    def show_main_context_menu(self, event):
        """Main context menu that delegates to the enhanced context menu"""
        # Get the enhanced context menu function that was set up in add_sector_move_to_context_menu
        if hasattr(self.canvas, 'showContextMenu'):
            self.canvas.showContextMenu(event)
        else:
            # Fallback: create a basic context menu
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self.canvas)
            menu.addAction("No enhanced menu available")
            menu.exec(event.globalPosition().toPoint())

    def show_welcome_message_updated(self):
        """Show welcome message and open visual level selector when Start Modding is pressed"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PyQt6.QtGui import QIcon

        # Create custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome to Simplified Map Editor")
        dialog.setMinimumSize(600, 500)
        dialog.resize(600, 500)

        # Set window icon depending on game
        if hasattr(self, "game_mode") and self.game_mode == "farcry2":
            dialog.setWindowIcon(QIcon("icon/fc2_icon.ico"))
        else:
            dialog.setWindowIcon(QIcon("icon/avatar_icon.ico"))

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)

        # Title
        title_label = QLabel("Simplified Map Editor")
        title_label.setStyleSheet(
            "font-size: 24px; font-weight: bold; color: #2196F3; margin-bottom: 10px;"
        )
        layout.addWidget(title_label)

        # Avatar content (full original text)
        avatar_text = """
    <b>Welcome to the Avatar: The Game Level Editor!</b><br><br>

    <b>Quick Start:</b><br>

    1. Click the green <b>"Select Level"</b> button to load a complete level<br>
    2. First: Select your <b>"WORLDS"</b> folder <b>(contains XML files)</b><br>
    3. Second: Select your <b>"LEVELS"</b> folder <b>(contains worldsectors)</b><br>
    4. Start editing entities with full copy/paste support!<br><br>

    <b>Key Features:</b><br>

    <b>Two-step loading:</b> Load both world data and level objects<br>
    <b>Smart entity placement:</b> Automatically places entities in correct files<br>
    <b>Copy/Paste system:</b> Duplicate entities with unique IDs and names<br>
    <b>Sector management:</b> Move entities between different sectors<br>
    <b>Visual editing:</b> 2D mode with gizmo controls<br>
    <b>Entity browser:</b> Color-coded entity browser with type grouping<br><br>

    <b>Keyboard Shortcuts:</b><br>

    <b>Ctrl+O:</b> Select Level (two-step loading)<br>
    <b>Delete:</b> Delete selected entities<br>

    <b>Right-click menu:</b><br>

    Move entities to different sectors<br>
    Copy, paste, and duplicate operations<br>
    View and selection controls<br><br>

    <b>Ready to get started? Click the green "Start Modding!" button!</b><br>
    """

        # Far Cry 2 content (full original text)
        fc2_text = """
    <b>Welcome to the Far Cry 2 World Editor Mode!</b><br><br>

    <b>Quick Start:</b><br>

    1. Click the green <b>"Select World"</b> button to load the main world grid<br>
    2. Choose your <b>"FC2 Worlds"</b> directory containing region XML files<br>
    3. Select one of the <b>25 world regions</b> (5×5 grid) to begin editing<br>
    4. Start editing entities, props, and terrain links!<br><br>

    <b>Key Features:</b><br>

    <b>World Grid System:</b> Edit up to 25 world sectors, each 16×16 regions<br>
    <b>Smart linking:</b> Automatically manages entities across region borders<br>
    <b>Entity Editor:</b> Modify positions, rotations, and properties<br>
    <b>Copy/Paste system:</b> Duplicate entities across world regions<br>
    <b>Visual Editor:</b> Zoom, pan, and select with gizmo support<br><br>

    <b>Keyboard Shortcuts:</b><br>

    <b>Ctrl+O:</b> Load World Grid<br>
    <b>Delete:</b> Delete selected entities<br>
    <b>Ctrl+C / Ctrl+V:</b> Copy and paste between world sectors<br><br>

    <b>Right-click menu:</b><br>

    Move entities between regions<br>
    Duplicate or edit linked props<br>
    Access debug and view controls<br><br>

    <b>Ready to explore the open world? Click the green "Start Modding!" button!</b><br>
    """

        # Choose which content to show
        if hasattr(self, "game_mode") and self.game_mode == "farcry2":
            content_text = fc2_text
            title_label.setStyleSheet(
                "font-size: 24px; font-weight: bold; color: #FF5722; margin-bottom: 10px;"
            )
        else:
            content_text = avatar_text

        # Main content label
        content_label = QLabel(content_text)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 13px; line-height: 1.4;")
        layout.addWidget(content_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        start_button = QPushButton("Start Modding!")
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # Open LevelSelectorDialog when pressed
        def open_level_selector():
            dialog.accept()  # close welcome dialog first
            self.select_level() 

        start_button.clicked.connect(open_level_selector)
        button_layout.addWidget(start_button)

        layout.addLayout(button_layout)

        dialog.exec()

    def show_welcome_message_conditionally(self):
        """Show welcome message only if not disabled by user preference"""
        try:
            import json
            config_file = "editor_config.json"
            
            # Check if user has disabled welcome screen
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if not config.get('show_welcome', True):
                        print("Welcome screen disabled by user preference")
                        
                        # Auto-open level selector if patch folder is configured
                        if hasattr(self, 'patch_manager') and self.patch_manager.is_configured():
                            from PyQt6.QtCore import QTimer
                            QTimer.singleShot(500, lambda: self.select_level())
                        return
            except:
                pass  # File doesn't exist or error reading - show welcome
            
            # Show the welcome message
            self.show_welcome_message_updated()
            
        except Exception as e:
            print(f"Error showing welcome message: {e}")

    def show_about(self):
        """Show about dialog with custom size"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        
        # Create custom dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("About Simplified Map Editor")
        dialog.setMinimumSize(500, 400)  # Set custom size
        dialog.resize(600, 500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Simplified Map Editor")
        title_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #2196F3; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Version info
        version_label = QLabel("Version 2.0 - Enhanced Edition")
        version_label.setStyleSheet("font-size: 14px; color: #666; font-style: italic; margin-bottom: 15px;")
        layout.addWidget(version_label)
        
        # Main content
        about_text = """
    <b>A powerful tool for editing Dunia engine level files.</b><br><br>

    <b>Important:</b><br>

    <b>Always backup your level files before editing!</b><br>
    <b>Close the game completely before saving changes.</b><br><br>
        
    <b>Ã°Å¸Å’Å¸ Core Features:</b><br>

    Load and edit Avatar: The Game level XML files<br>
    Visual entity editing with 2D view mode<br>
    Smart copy/paste system with automatic ID generation<br>
    Entity browser with <b>color-coded</b> type grouping<br>
    Sector boundary visualization and violation detection<br>
    Move entities between different sectors<br>
    Automatic file format conversion <b>(FCB Ã¢â€ â€ XML)</b><br>
    Grid configuration support<br><br>

    <b>Ã°Å¸Å½Â¯ Designed for:</b><br>

    Avatar: The Game community<br><br>
    
    """
        
        content_label = QLabel(about_text)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 13px; line-height: 1.4;")
        layout.addWidget(content_label)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        close_button.clicked.connect(dialog.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        dialog.exec()

    def create_menus(self):
        """Create the application menu bars - SIMPLIFIED without terrain"""
        # Create file menu
        file_menu = self.menuBar().addMenu("File")
        
        # Main unified load action
        select_level_action = QAction("Select Level... (loads both world and level data)", self)
        select_level_action.triggered.connect(self.select_level)
        select_level_action.setShortcut("Ctrl+O")
        file_menu.addAction(select_level_action)
        
        file_menu.addSeparator()
        
        # Keep individual load actions as advanced options
        advanced_menu = file_menu.addMenu("Advanced Loading")
        
        load_level_action = QAction("Load World Data Only... (searches subfolders)", self)
        load_level_action.triggered.connect(self.load_level_folder)
        advanced_menu.addAction(load_level_action)

        load_objects_action = QAction("Load Level Objects Only... (searches for worldsectors)", self)
        load_objects_action.triggered.connect(self.load_level_objects)
        load_objects_action.setShortcut("Ctrl+Shift+O")
        advanced_menu.addAction(load_objects_action)           
        
        file_menu.addSeparator()
                    
        # Save Level action (converts to FCB)
        save_level_action = QAction("Save Level (Convert to FCB)", self)
        save_level_action.triggered.connect(self.save_level)
        save_level_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_level_action)
        
        file_menu.addSeparator()
        
        # Add exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        exit_action.setShortcut("Alt+F4")
        file_menu.addAction(exit_action)

        # Create edit menu
        edit_menu = self.menuBar().addMenu("Edit")
        
        # Entity Editor action
        self.entity_editor_action = QAction("Entity Editor...", self)
        self.entity_editor_action.triggered.connect(self.open_entity_editor)
        self.entity_editor_action.setShortcut("Ctrl+E")
        self.entity_editor_action.setToolTip("Open Entity Properties Editor (Ctrl+E)")
        edit_menu.addAction(self.entity_editor_action)
        
        edit_menu.addSeparator()
        
        # Export/Import actions
        export_entities_action = QAction("Export Entities...", self)
        export_entities_action.triggered.connect(self.show_entity_export_dialog)
        export_entities_action.setShortcut("Ctrl+Shift+E")
        export_entities_action.setToolTip("Export selected entities to file")
        edit_menu.addAction(export_entities_action)
        
        import_entities_action = QAction("Import Entities...", self)
        import_entities_action.triggered.connect(self.show_entity_import_dialog)
        import_entities_action.setShortcut("Ctrl+Shift+I")
        import_entities_action.setToolTip("Import entities from file")
        edit_menu.addAction(import_entities_action)
        
        edit_menu.addSeparator()

        # Create view menu
        view_menu = self.menuBar().addMenu("View")
        
        # Reset view action
        reset_view_action = QAction("Reset View", self)
        reset_view_action.triggered.connect(self.reset_view)
        reset_view_action.setShortcut("R")
        view_menu.addAction(reset_view_action)
        
        view_menu.addSeparator()

        # Toggle visibility actions
        toggle_entities_action = QAction("Toggle Entities", self)
        toggle_entities_action.triggered.connect(self.toggle_entities)
        toggle_entities_action.setShortcut("E")
        toggle_entities_action.setCheckable(True)
        toggle_entities_action.setChecked(True)
        view_menu.addAction(toggle_entities_action)
        
        view_menu.addSeparator()
        
        # Invert mouse pan action
        invert_mouse_action = QAction("Invert Mouse Pan", self)
        invert_mouse_action.triggered.connect(self.toggle_invert_mouse)
        invert_mouse_action.setCheckable(True)
        invert_mouse_action.setChecked(False)
        invert_mouse_action.setToolTip("Invert middle mouse button camera panning direction")
        view_menu.addAction(invert_mouse_action)
        self.invert_mouse_action = invert_mouse_action
            
        # Add to Tools menu or create one
        tools_menu = self.menuBar().addMenu("Tools")
        
        create_sector_action = QAction("Create New Sector...", self)
        create_sector_action.triggered.connect(self.show_create_sector_dialog)
        create_sector_action.setToolTip("Create a new WorldSector file")
        tools_menu.addAction(create_sector_action)        
                                
        # Create help menu
        help_menu = self.menuBar().addMenu("Help")
        
        # About action
        about_action = QAction("About...", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Create the application toolbar - SIMPLIFIED without terrain"""
        # Create the toolbar instance and store as self.toolbar
        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)
        
        # --- toolbar actions ---
        select_level_action = QAction("Select Level", self)
        select_level_action.triggered.connect(self.select_level)
        select_level_action.setToolTip("Load complete level (world data + level objects)")
        self.toolbar.addAction(select_level_action)
        
        self.toolbar.addSeparator()
        
        load_world_action = QAction("Load World", self)
        load_world_action.triggered.connect(self.load_level_folder)
        load_world_action.setToolTip("Load world data only (XML files)")
        self.toolbar.addAction(load_world_action)

        load_objects_action = QAction("Load Objects", self)
        load_objects_action.triggered.connect(self.load_level_objects)
        load_objects_action.setToolTip("Load level objects only (worldsectors)")
        self.toolbar.addAction(load_objects_action)
        
        self.toolbar.addSeparator()

        entity_editor_toolbar_action = QAction("Entity Editor", self)
        entity_editor_toolbar_action.triggered.connect(self.open_entity_editor)
        entity_editor_toolbar_action.setToolTip("Open Entity Properties Editor (Ctrl+E)")
        self.toolbar.addAction(entity_editor_toolbar_action)
        
        export_toolbar_action = QAction("Export", self)
        export_toolbar_action.triggered.connect(self.show_entity_export_dialog)
        export_toolbar_action.setToolTip("Export selected entities to file")
        self.toolbar.addAction(export_toolbar_action)
        
        import_toolbar_action = QAction("Import", self)
        import_toolbar_action.triggered.connect(self.show_entity_import_dialog)
        import_toolbar_action.setToolTip("Import entities from file")
        self.toolbar.addAction(import_toolbar_action)
        
        toggle_mode_action = QAction("Toggle 2D/3D", self)
        toggle_mode_action.triggered.connect(self.toggle_mode)
        toggle_mode_action.setToolTip("Switch between 2D and 3D view")
        self.toolbar.addAction(toggle_mode_action)

        self.toolbar.addSeparator()
        
        reset_view_action = QAction("Reset View", self)
        reset_view_action.triggered.connect(self.reset_view)
        self.toolbar.addAction(reset_view_action)
        
        self.toolbar.addSeparator()
        
        toggle_entities_action = QAction("Toggle Entities", self)
        toggle_entities_action.triggered.connect(self.toggle_entities)
        toggle_entities_action.setCheckable(True)
        toggle_entities_action.setChecked(True)
        toggle_entities_action.setToolTip("Show/hide entities (E)")
        self.toolbar.addAction(toggle_entities_action)
        
        self.theme_toggle_action = QAction("Dark Mode", self)
        self.theme_toggle_action.triggered.connect(self.toggle_theme)
        self.theme_toggle_action.setCheckable(True)
        self.theme_toggle_action.setChecked(False)
        self.theme_toggle_action.setToolTip("Toggle between Light and Dark theme")
        self.toolbar.addAction(self.theme_toggle_action)
                            
        self.toolbar.addSeparator()
        
        create_sector_action = QAction("New Sector", self)
        create_sector_action.triggered.connect(self.show_create_sector_dialog)
        create_sector_action.setToolTip("Create a new WorldSector file")
        self.toolbar.addAction(create_sector_action)

        self.toolbar.addSeparator()
                    
        sector_action = QAction("Show Sectors", self)
        sector_action.setCheckable(True)
        sector_action.setChecked(False)
        sector_action.triggered.connect(self.toggle_sector_boundaries)
        sector_action.setToolTip("Show/hide sector boundaries")
        self.toolbar.addAction(sector_action)
                    
        check_violations_action = QAction("Check Violations", self)
        check_violations_action.triggered.connect(self.check_all_violations)
        check_violations_action.setToolTip("Check for entities outside sector boundaries")
        self.toolbar.addAction(check_violations_action)

        self.toolbar.addSeparator()
                    
        save_level_action = QAction("Save Level", self)
        save_level_action.triggered.connect(self.save_level)
        self.toolbar.addAction(save_level_action)

    def setup_mode_indicator(self):
        """Setup mode indicator in status bar"""
        try:
            # Create mode indicator label
            self.mode_label = QLabel("🔲 2D Mode")
            self.mode_label.setStyleSheet("padding: 2px 10px; font-weight: bold; color: #2196F3;")
            
            # Add to status bar as permanent widget (stays on right side)
            self.status_bar.addPermanentWidget(self.mode_label)
            
            print("Mode indicator added to status bar")
        except Exception as e:
            print(f"Error setting up mode indicator: {e}")

    def create_side_panel(self):
        """Create a dock widget for the side panel controls - 2D Editor"""
        # Create dock widget
        dock = QDockWidget("Level Editor Controls", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea)
        
        # Create widget to hold controls
        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        
        # Create unified level loading group
        level_group = QGroupBox("Level Loading")
        level_layout = QVBoxLayout(level_group)
        
        # Main unified level loading button - make it prominent
        select_level_button = QPushButton("Select Level")
        select_level_button.clicked.connect(self.select_level)
        select_level_button.setToolTip("Load complete level (world data + level objects)\nTwo-step process: select worlds folder, then levels folder")
        select_level_button.setMinimumHeight(45)
        select_level_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 24px;
                background-color: #228B22;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1F7A1F;
            }
            QPushButton:pressed {
                background-color: #1A5E1A;
            }
        """)
        level_layout.addWidget(select_level_button)

        # Level info label
        self.level_info_label = QLabel("No level loaded")
        self.level_info_label.setWordWrap(True)
        self.level_info_label.setStyleSheet("font-style: italic; margin: 5px;")
        level_layout.addWidget(self.level_info_label)
        
        dock_layout.addWidget(level_group)
                
        # Create entity editing group
        entity_group = QGroupBox("Entity Editing")
        entity_layout = QVBoxLayout(entity_group)
        
        # Entity Editor button
        entity_editor_button = QPushButton("Entity Properties Editor")
        entity_editor_button.clicked.connect(self.open_entity_editor)
        entity_editor_button.setMinimumHeight(35)
        entity_editor_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 20px;
                background-color: #1976D2;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        entity_layout.addWidget(entity_editor_button)
        
        # Export/Import buttons
        export_button = QPushButton("Export Entities")
        export_button.clicked.connect(self.show_entity_export_dialog)
        export_button.setMinimumHeight(30)
        export_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 18px;
                background-color: #F57C00;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #EF6C00;
            }
        """)
        entity_layout.addWidget(export_button)
        
        import_button = QPushButton("Import Entities")
        import_button.clicked.connect(self.show_entity_import_dialog)
        import_button.setMinimumHeight(30)
        import_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 18px;
                background-color: #388E3C;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2E7D32;
            }
        """)
        entity_layout.addWidget(import_button)
        
        dock_layout.addWidget(entity_group)
        
        # Create entity type color legend group
        entity_types_group = QGroupBox("Entity Colors")
        entity_types_group.setToolTip("Color coding for entity types")
        entity_types_layout = QVBoxLayout(entity_types_group)

        # Add header explaining the color system
        header_label = QLabel("Entity type color coding:")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_label.setStyleSheet("margin-bottom: 8px; padding: 2px;")
        entity_types_layout.addWidget(header_label)
        self.entity_colors_header = header_label  # Store reference for theme updates

        # Add color samples with labels
        self.color_legend_labels = []  # Store references for theme updates
        self.create_color_legend_item(entity_types_layout, QColor(52, 152, 255), "Vehicles")
        self.create_color_legend_item(entity_types_layout, QColor(46, 255, 113), "NPCs/Characters")
        self.create_color_legend_item(entity_types_layout, QColor(255, 76, 60), "Weapons/Combat")
        self.create_color_legend_item(entity_types_layout, QColor(255, 156, 18), "Spawn Points")
        self.create_color_legend_item(entity_types_layout, QColor(185, 89, 255), "Mission Objects")
        self.create_color_legend_item(entity_types_layout, QColor(255, 230, 15), "Triggers/Zones")
        self.create_color_legend_item(entity_types_layout, QColor(170, 180, 190), "Props/Structures")
        self.create_color_legend_item(entity_types_layout, QColor(255, 255, 160), "Lights")
        self.create_color_legend_item(entity_types_layout, QColor(0, 255, 200), "Effects/Audio")
        self.create_color_legend_item(entity_types_layout, QColor(255, 100, 100), "Special Objects")
        self.create_color_legend_item(entity_types_layout, QColor(130, 130, 130), "Unknown")

        dock_layout.addWidget(entity_types_group)

        # Create info group
        info_group = QGroupBox("Statistics")
        info_layout = QVBoxLayout(info_group)
        
        self.entity_count_label = QLabel("Entities: 0")
        self.entity_count_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.entity_count_label)
        
        self.selected_entity_label = QLabel("No entity selected")
        self.selected_entity_label.setWordWrap(True)
        self.selected_entity_label.setStyleSheet("margin-top: 5px;")
        info_layout.addWidget(self.selected_entity_label)
        
        dock_layout.addWidget(info_group)
                    
        # Add stretch to push everything to the top
        dock_layout.addStretch()
        
        # Set the dock widget and add to main window
        dock.setWidget(dock_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        
        # Store reference to the dock for later access
        self.controls_dock = dock
        
        # Make sure the dock is visible
        dock.setVisible(True)
        dock.show()
        
        # Update legend label colors for the current theme immediately
        if hasattr(self, "apply_theme"):
            if getattr(self, "force_dark_theme", False):
                self.entity_colors_header.setStyleSheet("color: white; margin-bottom: 8px; padding: 2px;")
                for label in self.color_legend_labels:
                    label.setStyleSheet("color: white;")
            else:
                self.entity_colors_header.setStyleSheet("color: black; margin-bottom: 8px; padding: 2px;")
                for label in self.color_legend_labels:
                    label.setStyleSheet("color: black;")

        print("Side panel created for 2D level editor")

    def update_mode_indicator(self):
        """Update the mode indicator in the status bar"""
        if not hasattr(self, 'canvas'):
            return
        
        if not hasattr(self, 'mode_label'):
            return
        
        try:
            if self.canvas.mode == 0:  # 2D mode
                self.mode_label.setText("🔲 2D Mode")
                self.mode_label.setStyleSheet("padding: 2px 10px; font-weight: bold; color: #2196F3;")
            else:  # 3D mode
                self.mode_label.setText("🎮 3D Mode")
                self.mode_label.setStyleSheet("padding: 2px 10px; font-weight: bold; color: #FF9800;")
        except Exception as e:
            print(f"Error updating mode indicator: {e}")

    def setup_cache_menu(self):
        """Setup cache management menu"""
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtGui import QAction
        
        cache_menu = self.menuBar().addMenu("Cache")
        
        # View cache statistics
        stats_action = QAction("View Cache Statistics", self)
        stats_action.triggered.connect(self.show_cache_statistics)
        stats_action.setShortcut("Ctrl+Shift+C")
        cache_menu.addAction(stats_action)
        
        cache_menu.addSeparator()
        
        # Clear all caches
        clear_all_action = QAction("Clear All Caches", self)
        clear_all_action.triggered.connect(self.clear_all_caches)
        cache_menu.addAction(clear_all_action)
        
        # Clear specific cache types
        clear_fcb_action = QAction("Clear FCB Conversion Cache", self)
        clear_fcb_action.triggered.connect(lambda: self.cache.clear_cache_type('fcb_conversion'))
        cache_menu.addAction(clear_fcb_action)
        
        clear_xml_action = QAction("Clear XML Parsing Cache", self)
        clear_xml_action.triggered.connect(lambda: self.cache.clear_cache_type('xml_parsing'))
        cache_menu.addAction(clear_xml_action)
        
        clear_disk_action = QAction("Clear Disk Cache", self)
        clear_disk_action.triggered.connect(self.clear_disk_cache)
        cache_menu.addAction(clear_disk_action)
        
        cache_menu.addSeparator()
        
        # Toggle caching
        self.cache_enabled_action = QAction("Enable Caching", self)
        self.cache_enabled_action.setCheckable(True)
        self.cache_enabled_action.setChecked(self.cache.enabled)
        self.cache_enabled_action.triggered.connect(self.toggle_caching)
        cache_menu.addAction(self.cache_enabled_action)

    def toggle_mode(self):
        """Switch between 2D and 3D modes."""
        if self.current_mode == "2D":
            self.current_mode = "3D"
            self.canvas.set_3d_mode(True)  # tell the canvas to switch to 3D rendering
        else:
            self.current_mode = "2D"
            self.canvas.set_3d_mode(False)  # back to 2D rendering

        # Update the mode indicator label
        self.setup_mode_indicator()

    def show_cache_statistics(self):
        """Show cache statistics dialog"""
        stats = self.cache.get_cache_stats()
        
        msg = f"""Cache Statistics
    ================

    Status: {'ENABLED' if stats['enabled'] else 'DISABLED'}
    Memory Usage: {stats['memory_usage_mb']:.1f} / {stats['max_memory_mb']:.1f} MB

    Cache Sizes:
    FCB Conversions: {stats['cache_sizes']['fcb_conversion']} entries
    XML Parsing: {stats['cache_sizes']['xml_parsing']} entries
    Object Parsing: {stats['cache_sizes']['object_parsing']} entries
    Terrain: {stats['cache_sizes']['terrain']} entries

    Hit Rates:
    FCB: {stats['hit_rates']['fcb']['rate']:.1f}% ({stats['hit_rates']['fcb']['hits']} hits, {stats['hit_rates']['fcb']['misses']} misses)
    XML: {stats['hit_rates']['xml']['rate']:.1f}% ({stats['hit_rates']['xml']['hits']} hits, {stats['hit_rates']['xml']['misses']} misses)
    Objects: {stats['hit_rates']['object']['rate']:.1f}% ({stats['hit_rates']['object']['hits']} hits, {stats['hit_rates']['object']['misses']} misses)
    Terrain: {stats['hit_rates']['terrain']['rate']:.1f}% ({stats['hit_rates']['terrain']['hits']} hits, {stats['hit_rates']['terrain']['misses']} misses)

    Overall Hit Rate: {stats['overall_hit_rate']:.1f}%

    Total Requests: {stats['total_hits'] + stats['total_misses']}
    Total Cache Hits: {stats['total_hits']}
    Total Cache Misses: {stats['total_misses']}
    """
        
        QMessageBox.information(self, "Cache Statistics", msg)

    def clear_all_caches(self):
        """Clear all caches with confirmation"""
        reply = QMessageBox.question(
            self,
            "Clear All Caches",
            "This will clear all cached data. Cache will be rebuilt on next load.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.cache.clear_all_caches()
            QMessageBox.information(self, "Success", "All caches cleared!")

    def clear_disk_cache(self):
        """Clear disk cache with confirmation"""
        reply = QMessageBox.question(
            self,
            "Clear Disk Cache",
            "This will clear all cached terrain images and temp files.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.cache.clear_disk_cache()
            QMessageBox.information(self, "Success", "Disk cache cleared!")

    def toggle_caching(self):
        """Toggle caching on/off"""
        if self.cache_enabled_action.isChecked():
            self.cache.enable_caching()
        else:
            self.cache.disable_caching()

    def create_color_legend_item(self, layout, color, text):
        """Create a color sample with label for the legend - ENHANCED"""
        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(5, 2, 5, 2)  # Tighter margins
        
        # Create color sample with improved styling
        color_sample = QWidget()
        color_sample.setFixedSize(14, 14)  # Slightly smaller for better fit
        color_sample.setAutoFillBackground(True)
        
        # Set color with subtle border
        palette = color_sample.palette()
        palette.setColor(color_sample.backgroundRole(), color)
        color_sample.setPalette(palette)
        
        # Add subtle border for better definition
        color_sample.setStyleSheet(f"""
            QWidget {{
                background-color: {color.name()};
                border: 1px solid rgba(0, 0, 0, 0.2);
                border-radius: 2px;
            }}
        """)
        
        # Create label with improved styling (color will be set by theme)
        label = QLabel(text)
        label.setFont(QFont("Arial", 10))
        label.setStyleSheet("margin-left: 8px;")
        
        # Store reference for theme updates
        if hasattr(self, 'color_legend_labels'):
            self.color_legend_labels.append(label)
        
        # Add to layout with label
        item_layout.addWidget(color_sample)
        item_layout.addWidget(label)
        item_layout.addStretch()  # Push everything to the left
        
        layout.addLayout(item_layout)

    def single_folder_fallback(self, selected_folder):
        """
        Fallback to single folder loading when user chooses not to do manual selection
        """
        print(f"\n=== SINGLE FOLDER FALLBACK ===")
        
        # Try to determine what type of folder this is
        worlds_valid = self.validate_worlds_folder(selected_folder)
        levels_valid = self.validate_levels_folder(selected_folder)
        
        if worlds_valid and levels_valid:
            # Folder contains both types
            level_info = {
                'name': os.path.basename(selected_folder),
                'worlds_path': selected_folder,
                'levels_path': selected_folder,
                'base_folder': os.path.dirname(selected_folder)
            }
            print(f"Folder contains both world and level data")
            self.load_complete_level(level_info)
            
        elif worlds_valid:
            # Only worlds data
            level_info = {
                'name': os.path.basename(selected_folder),
                'worlds_path': selected_folder,
                'levels_path': None,
                'base_folder': os.path.dirname(selected_folder)
            }
            print(f"Folder contains world data only")
            
            QMessageBox.information(
                self,
                "Worlds Data Only",
                f"Loading world data (entities) only from:\n{os.path.basename(selected_folder)}\n\n"
                f"No level objects (worldsectors) will be loaded."
            )
            self.load_complete_level(level_info)
            
        elif levels_valid:
            # Only levels data
            level_info = {
                'name': os.path.basename(selected_folder),
                'worlds_path': None,
                'levels_path': selected_folder,
                'base_folder': os.path.dirname(selected_folder)
            }
            print(f"Folder contains level data only")
            
            QMessageBox.information(
                self,
                "Level Objects Only",
                f"Loading level objects (worldsectors) only from:\n{os.path.basename(selected_folder)}\n\n"
                f"No world entities will be loaded."
            )
            self.load_complete_level(level_info)
            
        else:
            # No valid data found
            QMessageBox.warning(
                self,
                "No Valid Data Found",
                f"The selected folder doesn't contain valid level data:\n{selected_folder}\n\n"
                f"Please select a folder containing:\n"
                f"World data: XML files (mapsdata.xml, etc.)\n"
                f"Level data: worldsectors folder with .data.fcb files"
            )

    def validate_worlds_folder(self, folder_path):
        """Check if folder contains world data (XML files) - FIXED"""
        if not os.path.exists(folder_path):
            return False
        
        # Use the correct method name from your original code
        world_files = self.find_xml_files_enhanced(folder_path)  # Changed from find_xml_files_enhanced
        return len(world_files) > 0

    def validate_levels_folder(self, folder_path):
        """Check if folder contains level data (worldsectors) - FIXED"""
        if not os.path.exists(folder_path):
            return False
        
        # Use the correct method name from your original code
        worldsectors_info = self.find_worldsectors_folder_enhanced(folder_path)
        return worldsectors_info is not None

    def load_omnis_data(self, file_path):
        """Load omnis data from XML file"""
        try:
            print(f"Loading omnis data from: {os.path.basename(file_path)}")
            
            # Parse the XML file
            tree = ET.parse(file_path)
            self.omnis_tree = tree
            root = tree.getroot()
            
            # Track entities loaded from this file
            entities_loaded = 0
            
            # Find all Entity objects in the omnis file
            for entity_elem in root.findall(".//object[@type='Entity']"):
                try:
                    # Extract entity ID
                    entity_id = "Unknown"
                    for value_elem in entity_elem.findall("./value[@name='disEntityId']"):
                        entity_id = value_elem.text.strip() if value_elem.text else "Unknown"
                    
                    # Extract entity name
                    entity_name = "Unnamed"
                    for value_elem in entity_elem.findall("./value[@name='hidName']"):
                        entity_name = value_elem.text.strip() if value_elem.text else "Unnamed"
                    
                    # Extract position
                    pos_elem = entity_elem.find("./value[@name='hidPos']")
                    if pos_elem is None:
                        # Try finding hidPos_precise if hidPos doesn't exist
                        pos_elem = entity_elem.find("./value[@name='hidPos_precise']")
                    
                    if pos_elem is not None:
                        x_elem = pos_elem.find("./x")
                        y_elem = pos_elem.find("./y")
                        z_elem = pos_elem.find("./z")
                        
                        if x_elem is not None and y_elem is not None and z_elem is not None:
                            x = float(x_elem.text) if x_elem.text else 0.0
                            y = float(y_elem.text) if y_elem.text else 0.0
                            z = float(z_elem.text) if z_elem.text else 0.0
                            
                            # Create Entity object
                            entity = Entity(entity_id, entity_name, x, y, z, entity_elem)
                            
                            # Set source file information
                            entity.source_file = "omnis"
                            entity.source_file_path = file_path
                            
                            # Determine which map this entity belongs to
                            if self.grid_config and self.grid_config.maps:
                                entity.map_name = self.determine_entity_map(entity)
                            
                            self.entities.append(entity)
                            entities_loaded += 1
                            
                except Exception as e:
                    print(f"Error parsing omnis entity: {str(e)}")
            
            print(f"Loaded {entities_loaded} entities from omnis file")
            return True
            
        except Exception as e:
            print(f"Error loading omnis data from {file_path}: {str(e)}")
            return False

    def load_managers_data(self, file_path):
        """Load managers data from XML file"""
        try:
            print(f"Loading managers data from: {os.path.basename(file_path)}")
            
            # Parse the XML file
            tree = ET.parse(file_path)
            self.managers_tree = tree
            root = tree.getroot()
            
            # Track entities loaded from this file
            entities_loaded = 0
            
            # Find all Entity objects in the managers file
            for entity_elem in root.findall(".//object[@type='Entity']"):
                try:
                    # Extract entity ID
                    entity_id = "Unknown"
                    for value_elem in entity_elem.findall("./value[@name='disEntityId']"):
                        entity_id = value_elem.text.strip() if value_elem.text else "Unknown"
                    
                    # Extract entity name
                    entity_name = "Unnamed"
                    for value_elem in entity_elem.findall("./value[@name='hidName']"):
                        entity_name = value_elem.text.strip() if value_elem.text else "Unnamed"
                    
                    # Extract position
                    pos_elem = entity_elem.find("./value[@name='hidPos']")
                    if pos_elem is None:
                        # Try finding hidPos_precise if hidPos doesn't exist
                        pos_elem = entity_elem.find("./value[@name='hidPos_precise']")
                    
                    if pos_elem is not None:
                        x_elem = pos_elem.find("./x")
                        y_elem = pos_elem.find("./y")
                        z_elem = pos_elem.find("./z")
                        
                        if x_elem is not None and y_elem is not None and z_elem is not None:
                            x = float(x_elem.text) if x_elem.text else 0.0
                            y = float(y_elem.text) if y_elem.text else 0.0
                            z = float(z_elem.text) if z_elem.text else 0.0
                            
                            # Create Entity object
                            entity = Entity(entity_id, entity_name, x, y, z, entity_elem)
                            
                            # Set source file information
                            entity.source_file = "managers"
                            entity.source_file_path = file_path
                            
                            # Determine which map this entity belongs to
                            if self.grid_config and self.grid_config.maps:
                                entity.map_name = self.determine_entity_map(entity)
                            
                            self.entities.append(entity)
                            entities_loaded += 1
                            
                except Exception as e:
                    print(f"Error parsing managers entity: {str(e)}")
            
            print(f"Loaded {entities_loaded} entities from managers file")
            return True
            
        except Exception as e:
            print(f"Error loading managers data from {file_path}: {str(e)}")
            return False

    def load_sectordep_data(self, file_path):
        """Load sector dependencies data from XML file"""
        try:
            print(f"Loading sectordep data from: {os.path.basename(file_path)}")
            
            # Parse the XML file
            tree = ET.parse(file_path)
            self.sectordep_tree = tree
            root = tree.getroot()
            
            # Track entities loaded from this file
            entities_loaded = 0
            
            # Find all Entity objects in the sectordep file
            for entity_elem in root.findall(".//object[@type='Entity']"):
                try:
                    # Extract entity ID
                    entity_id = "Unknown"
                    for value_elem in entity_elem.findall("./value[@name='disEntityId']"):
                        entity_id = value_elem.text.strip() if value_elem.text else "Unknown"
                    
                    # Extract entity name
                    entity_name = "Unnamed"
                    for value_elem in entity_elem.findall("./value[@name='hidName']"):
                        entity_name = value_elem.text.strip() if value_elem.text else "Unnamed"
                    
                    # Extract position
                    pos_elem = entity_elem.find("./value[@name='hidPos']")
                    if pos_elem is None:
                        # Try finding hidPos_precise if hidPos doesn't exist
                        pos_elem = entity_elem.find("./value[@name='hidPos_precise']")
                    
                    if pos_elem is not None:
                        x_elem = pos_elem.find("./x")
                        y_elem = pos_elem.find("./y")
                        z_elem = pos_elem.find("./z")
                        
                        if x_elem is not None and y_elem is not None and z_elem is not None:
                            x = float(x_elem.text) if x_elem.text else 0.0
                            y = float(y_elem.text) if y_elem.text else 0.0
                            z = float(z_elem.text) if z_elem.text else 0.0
                            
                            # Create Entity object
                            entity = Entity(entity_id, entity_name, x, y, z, entity_elem)
                            
                            # Set source file information
                            entity.source_file = "sectorsdep"
                            entity.source_file_path = file_path
                            
                            # Determine which map this entity belongs to
                            if self.grid_config and self.grid_config.maps:
                                entity.map_name = self.determine_entity_map(entity)
                            
                            self.entities.append(entity)
                            entities_loaded += 1
                            
                except Exception as e:
                    print(f"Error parsing sectordep entity: {str(e)}")
            
            print(f"Loaded {entities_loaded} entities from sectordep file")
            return True
            
        except Exception as e:
            print(f"Error loading sectordep data from {file_path}: {str(e)}")
            return False
    
    def analyze_level_structure(self, base_folder):
        """
        Enhanced level structure analysis with better detection and debugging
        """
        level_data = []
        
        print(f"Analyzing level structure in: {base_folder}")
        
        # Pattern 1: Patch folder with worlds/levels subfolders
        worlds_folder = os.path.join(base_folder, "worlds")
        levels_folder = os.path.join(base_folder, "levels")
        
        if os.path.exists(worlds_folder) and os.path.exists(levels_folder):
            print("Found patch folder structure")
            
            # Find matching level names in both folders
            worlds_levels = set()
            levels_levels = set()
            
            try:
                if os.path.isdir(worlds_folder):
                    worlds_levels = {item for item in os.listdir(worlds_folder) 
                                if os.path.isdir(os.path.join(worlds_folder, item))}
                    print(f"   Worlds subfolders: {sorted(worlds_levels)}")
                
                if os.path.isdir(levels_folder):
                    levels_levels = {item for item in os.listdir(levels_folder) 
                                if os.path.isdir(os.path.join(levels_folder, item))}
                    print(f"   Levels subfolders: {sorted(levels_levels)}")
                    
            except Exception as e:
                print(f"Error scanning patch folders: {e}")
            
            # Find levels that exist in both folders
            common_levels = worlds_levels.intersection(levels_levels)
            all_levels = worlds_levels.union(levels_levels)
            
            print(f"Ã°Å¸â€œÅ  Found {len(worlds_levels)} worlds, {len(levels_levels)} levels, {len(common_levels)} complete")
            
            for level_name in sorted(all_levels):
                worlds_path = os.path.join(worlds_folder, level_name) if level_name in worlds_levels else None
                levels_path = os.path.join(levels_folder, level_name) if level_name in levels_levels else None
                
                # Validate paths with detailed feedback
                worlds_valid = False
                levels_valid = False
                
                if worlds_path:
                    worlds_valid = self.validate_worlds_folder(worlds_path)
                    if worlds_valid:
                        print(f"   {level_name} worlds folder valid")
                    else:
                        print(f"   {level_name} worlds folder invalid (no XML files)")
                
                if levels_path:
                    levels_valid = self.validate_levels_folder(levels_path)
                    if levels_valid:
                        print(f"   {level_name} levels folder valid")
                    else:
                        print(f"   {level_name} levels folder invalid (no worldsectors)")
                
                if worlds_valid or levels_valid:
                    level_info = {
                        'name': level_name,
                        'worlds_path': worlds_path if worlds_valid else None,
                        'levels_path': levels_path if levels_valid else None,
                        'base_folder': base_folder,
                        'complete': worlds_valid and levels_valid
                    }
                    level_data.append(level_info)
                    
                    status = "complete" if worlds_valid and levels_valid else "partial"
                    print(f"   Ã¢Å¾â€¢ Added {level_name} ({status})")
                else:
                    print(f"   Skipped {level_name} (no valid data)")
        
        # Pattern 2: Direct level folder
        else:
            print("Checking direct level folder")
            worlds_valid = self.validate_worlds_folder(base_folder)
            levels_valid = self.validate_levels_folder(base_folder)
            
            print(f"   Worlds data valid: {worlds_valid}")
            print(f"   Levels data valid: {levels_valid}")
            
            if worlds_valid or levels_valid:
                level_name = os.path.basename(base_folder)
                level_info = {
                    'name': level_name,
                    'worlds_path': base_folder if worlds_valid else None,
                    'levels_path': base_folder if levels_valid else None,
                    'base_folder': os.path.dirname(base_folder),
                    'complete': worlds_valid and levels_valid
                }
                level_data.append(level_info)
                
                status = "complete" if worlds_valid and levels_valid else "partial"
                print(f"   Ã¢Å¾â€¢ Added {level_name} ({status})")
            else:
                print(f"   No valid level data found in direct folder")
        
        print(f"Ã°Å¸Å½Â¯ Analysis complete: {len(level_data)} levels found")
        
        # DEBUG: Show what was found
        if level_data:
            print(f"\nDetected levels:")
            for i, level in enumerate(level_data, 1):
                worlds_status = "Ã¢Å“â€œ" if level['worlds_path'] else "Ã¢ÂÅ’"
                levels_status = "Ã¢Å“â€œ" if level['levels_path'] else "Ã¢ÂÅ’"
                complete_status = "COMPLETE" if level['complete'] else "PARTIAL"
                print(f"   {i}. {level['name']} - Worlds:{worlds_status} Levels:{levels_status} {complete_status}")
        
        return level_data

    def show_level_selection_dialog(self, level_data, prefer_complete=True):
        """Show dialog for user to select which level to load - ENHANCED"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QPushButton, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Level to Load ({len(level_data)} found)")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Info label
        complete_count = len([l for l in level_data if l['complete']])
        partial_count = len(level_data) - complete_count
        
        info_text = f"Found {len(level_data)} levels: {complete_count} complete, {partial_count} partial"
        if prefer_complete and complete_count > 0:
            info_text += "\n(Complete levels are recommended - they have both world and level data)"
        
        info_label = QLabel(info_text)
        layout.addWidget(info_label)
        
        # Level list
        level_list = QListWidget()
        
        # Sort levels: complete first if preferred, then alphabetically
        if prefer_complete:
            sorted_levels = sorted(level_data, key=lambda x: (not x['complete'], x['name']))
        else:
            sorted_levels = sorted(level_data, key=lambda x: x['name'])
        
        for level_info in sorted_levels:
            # Build item text with detailed status
            item_text = f"{level_info['name']}"
            
            status_parts = []
            if level_info['worlds_path']:
                status_parts.append("World Data Ã¢Å“â€œ")
            else:
                status_parts.append("World Data Ã¢ÂÅ’")
                
            if level_info['levels_path']:
                status_parts.append("Level Objects Ã¢Å“â€œ")
            else:
                status_parts.append("Level Objects Ã¢ÂÅ’")
            
            if level_info['complete']:
                item_text += " [COMPLETE]"
            else:
                item_text += " [PARTIAL]"
                
            item_text += f"\n    {' | '.join(status_parts)}"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, level_info)
            
            # Color coding
            if level_info['complete']:
                item.setBackground(QColor(200, 255, 200))  # Light green for complete
            else:
                item.setBackground(QColor(255, 255, 200))  # Light yellow for partial
            
            level_list.addItem(item)
        
        layout.addWidget(level_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        load_button = QPushButton("Load Selected Level")
        load_button.clicked.connect(
            lambda: self.load_selected_level_from_dialog(dialog, level_list)
        )
        button_layout.addWidget(load_button)
        
        manual_button = QPushButton("Manual Selection Instead...")
        manual_button.clicked.connect(
            lambda: self.switch_to_manual_selection_from_dialog(dialog)
        )
        button_layout.addWidget(manual_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        dialog.exec()

    def reset_maps_and_ui(self):
        """Reset map configuration, canvas, and terrain renderer when loading a new level"""
        print("Resetting maps, UI, and terrain, please wait.")

        try:
            # ---------------- 1. Reset current map ----------------
            self.current_map = None

            # ---------------- 2. Reset grid configuration ----------------
            self.grid_config = GridConfig(
                sector_count_x=16,
                sector_count_y=16,
                sector_granularity=64,
                maps=[]  # Clear all maps
            )

            # ---------------- 3. Reset canvas state ----------------
            if hasattr(self, 'canvas'):
                self.canvas.current_map = None
                self.canvas.grid_config = self.grid_config

                # Clear terrain/minimap data
                for attr in ['minimap', 'terrain_data', 'heightmap', 'terrain_texture']:
                    if hasattr(self.canvas, attr):
                        setattr(self.canvas, attr, None)

                # Reset sector boundary data
                if hasattr(self.canvas, 'sector_data'):
                    self.canvas.sector_data = []
                if hasattr(self.canvas, 'show_sector_boundaries'):
                    self.canvas.show_sector_boundaries = False

            # ---------------- 4. Reset map combo box ----------------
            if hasattr(self, 'map_combo'):
                self.map_combo.clear()
                self.map_combo.addItem("No maps loaded")

            # ---------------- 5. Reset terrain renderer ----------------
            if hasattr(self, 'terrain_viewer') and self.terrain_viewer:
                # Recreate or reset terrain renderer
                self.terrain_viewer.setParent(None)  # Remove old widget
                self.terrain_viewer.deleteLater()
                self.terrain_viewer = TerrainRenderer(parent=self)
                if hasattr(self, 'terrain_dock') and self.terrain_dock:
                    self.terrain_dock.setWidget(self.terrain_viewer)

            print("Maps, UI, and terrain reset complete")

        except Exception as e:
            print(f"Error during maps, UI, or terrain reset: {e}")
            import traceback
            traceback.print_exc()

    def parse_xml_file(self, file_path):
        """Parse the XML file to extract entities - WITH CACHING"""
        
        # ============ CACHE INTEGRATION HERE ============
        # Try to get cached parsed data first
        cached_entities = self.cache.get_parsed_xml(file_path)
        if cached_entities is not None:
            print(f"âœ“ Using cached parse for {os.path.basename(file_path)} ({len(cached_entities)} entities)")
            
            # Use cached data
            self.entities = cached_entities
            
            # Still need to set xml_tree for saving later
            tree = ET.parse(file_path)
            self.xml_tree = tree
            
            # Reset maps if needed
            base_filename = os.path.basename(file_path)
            if ".mapsdata.xml" in base_filename or "mapsdata.xml" == base_filename:
                print("Main mapsdata file detected - performing full map reset")
                self.reset_maps_and_ui()
            
            # Update UI
            if hasattr(self, 'update_entity_statistics'):
                self.update_entity_statistics()
            if hasattr(self, 'entity_tree'):
                self.update_entity_tree()
            if hasattr(self, 'canvas'):
                self.canvas.set_entities(self.entities)
            
            return  # Done - used cache!
        # ============ END CACHE CHECK ============
        
        # Cache miss - parse normally
        print(f"Parsing {os.path.basename(file_path)}...")
        
        # Reset maps when parsing a new main XML file
        base_filename = os.path.basename(file_path)
        if ".mapsdata.xml" in base_filename or "mapsdata.xml" == base_filename:
            print("Main mapsdata file detected - performing full map reset")
            self.reset_maps_and_ui()
        
        # Reset current data
        self.entities = []
        self.selected_entity = None
        
        # Parse XML
        tree = ET.parse(file_path)
        self.xml_tree = tree
        root = tree.getroot()
        
        # Determine the source file type based on filename
        source_type = "unknown"
        if ".mapsdata.xml" in base_filename:
            source_type = "mapsdata"
        elif ".managers.xml" in base_filename:
            source_type = "managers"
        elif ".omnis.xml" in base_filename:
            source_type = "omnis"
        elif ".sectorsdep.xml" in base_filename:
            source_type = "sectorsdep"
        
        # Find all Entity objects
        for entity_elem in root.findall(".//object[@type='Entity']"):
            try:
                # Extract entity ID
                entity_id = "Unknown"
                for value_elem in entity_elem.findall("./value[@name='disEntityId']"):
                    entity_id = value_elem.text.strip() if value_elem.text else "Unknown"
                
                # Extract entity name
                entity_name = "Unnamed"
                for value_elem in entity_elem.findall("./value[@name='hidName']"):
                    entity_name = value_elem.text.strip() if value_elem.text else "Unnamed"
                
                # Extract position
                pos_elem = entity_elem.find("./value[@name='hidPos']")
                if pos_elem is None:
                    # Try finding hidPos_precise if hidPos doesn't exist
                    pos_elem = entity_elem.find("./value[@name='hidPos_precise']")
                
                if pos_elem is not None:
                    x_elem = pos_elem.find("./x")
                    y_elem = pos_elem.find("./y")
                    z_elem = pos_elem.find("./z")
                    
                    if x_elem is not None and y_elem is not None and z_elem is not None:
                        x = float(x_elem.text) if x_elem.text else 0.0
                        y = float(y_elem.text) if y_elem.text else 0.0
                        z = float(z_elem.text) if z_elem.text else 0.0
                        
                        # Create Entity object without source_file parameter
                        entity = Entity(entity_id, entity_name, x, y, z, entity_elem)
                        
                        # Set source_file attribute after creation
                        entity.source_file = source_type
                        
                        # Determine which map this entity belongs to
                        if self.grid_config and self.grid_config.maps:
                            entity.map_name = self.determine_entity_map(entity)
                        
                        self.entities.append(entity)
            except Exception as e:
                print(f"Error parsing entity: {str(e)}")
        
        # Print summary
        print(f"Parsed {len(self.entities)} entities from {file_path}")
        
        # ============ CACHE INTEGRATION HERE ============
        # Cache the parsed entities for next time
        self.cache.cache_parsed_xml(file_path, self.entities)
        # ============ END CACHE INTEGRATION ============
        
        # Update entity statistics if the method exists
        if hasattr(self, 'update_entity_statistics'):
            self.update_entity_statistics()
        
        # Update the entity browser tree if it exists
        if hasattr(self, 'entity_tree'):
            self.update_entity_tree()
        
        # Update canvas with new entities
        if hasattr(self, 'canvas'):
            self.canvas.set_entities(self.entities)
                                        
    def reset_entire_editor_state(self):
        """Comprehensive reset of the entire editor state when loading a new level"""
        print("COMPREHENSIVE EDITOR RESET - Clearing all previous level data, Please wait.")
        
        try:
            # 1. CLEAR ALL ENTITY DATA
            print("   Clearing entity data, Please wait.")
            self.entities = []
            self.objects = []
            self.selected_entity = None
            
            # Clear canvas entities and selection
            if hasattr(self, 'canvas'):
                self.canvas.entities = []
                self.canvas.selected = []
                self.canvas.selected_entity = None
                self.canvas.selected_positions = []
                self.canvas.selected_rotations = []
                
                # Invalidate entity cache
                if hasattr(self.canvas, 'invalidate_entity_cache'):
                    self.canvas.invalidate_entity_cache()
            
            # 2. CLEAR ALL XML TREES AND FILE REFERENCES
            print("   Clearing XML file data, Please wait.")
            self.xml_tree = None
            self.xml_file_path = None
            self.omnis_tree = None
            self.managers_tree = None
            self.sectordep_tree = None
            
            # Clear worldsectors data
            if hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees.clear()
            else:
                self.worldsectors_trees = {}
            
            if hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified.clear()
            else:
                self.worldsectors_modified = {}
            
            self.worldsectors_path = None
            
            # 3. RESET MAP AND GRID CONFIGURATION
            print("   Resetting map configuration, Please wait.")
            self.current_map = None
            self.grid_config = GridConfig(
                sector_count_x=16,
                sector_count_y=16,
                sector_granularity=64,
                maps=[]  # Clear all maps
            )
            
            # Reset canvas map state
            if hasattr(self.canvas, 'current_map'):
                self.canvas.current_map = None
            if hasattr(self.canvas, 'grid_config'):
                self.canvas.grid_config = self.grid_config
            
            # 4. RESET MAP COMBO BOX
            print("   Resetting UI elements, Please wait.")
            if hasattr(self, 'map_combo'):
                self.map_combo.clear()
                self.map_combo.addItem("No maps loaded")
            
            # 5. CLEAR TERRAIN AND MINIMAP DATA
            print("   Clearing terrain data, Please wait.")
            if hasattr(self.canvas, 'minimap'):
                self.canvas.minimap = None
            if hasattr(self.canvas, 'terrain_data'):
                self.canvas.terrain_data = None
            if hasattr(self.canvas, 'heightmap'):
                self.canvas.heightmap = None
            if hasattr(self.canvas, 'terrain_texture'):
                self.canvas.terrain_texture = None
            
            
            # Reset terrain renderer to clear all loaded terrain data
            if hasattr(self.canvas, 'terrain_renderer'):
                try:
                    # Create a fresh terrain renderer instance
                    self.canvas.terrain_renderer = TerrainRenderer()
                    print("   Canvas terrain renderer reset")
                except Exception as e:
                    print(f"   Warning: Could not reset terrain renderer: {e}")
            
            # Reset editor-level terrain properties
            self.sdat_path = None
            
            # Close and clear terrain viewer widget
            if hasattr(self, 'terrain_viewer') and self.terrain_viewer is not None:
                try:
                    self.terrain_viewer.close()
                    self.terrain_viewer = None
                    print("   Terrain viewer closed")
                except Exception as e:
                    print(f"   Warning: Could not close terrain viewer: {e}")
            
            # Clear terrain dock widget
            if hasattr(self, 'terrain_dock') and self.terrain_dock is not None:
                try:
                    self.terrain_dock.setWidget(None)
                    print("   Terrain dock cleared")
                except Exception as e:
                    print(f"   Warning: Could not clear terrain dock: {e}")
            
            # 6. RESET SECTOR BOUNDARY DATA
            if hasattr(self.canvas, 'sector_data'):
                self.canvas.sector_data = []
            if hasattr(self.canvas, 'show_sector_boundaries'):
                self.canvas.show_sector_boundaries = False
            
            # 7. RESET MODIFICATION FLAGS
            print("   Resetting modification flags, Please wait.")
            self.entities_modified = False
            self.xml_tree_modified = False
            self.omnis_tree_modified = False
            self.managers_tree_modified = False
            self.sectordep_tree_modified = False
            self.objects_modified = False
            
            # 8. CLEAR ENTITY BROWSER/TREE
            if hasattr(self, 'entity_tree'):
                self.entity_tree.clear()
            
            # 9. RESET UI LABELS AND STATUS
            print("   Updating UI labels, Please wait.")
            if hasattr(self, 'level_info_label'):
                self.level_info_label.setText("No level loaded")
            elif hasattr(self, 'xml_file_label'):
                self.xml_file_label.setText("No level loaded")
            
            if hasattr(self, 'entity_count_label'):
                self.entity_count_label.setText("Entities: 0")
            
            if hasattr(self, 'selected_entity_label'):
                self.selected_entity_label.setText("No entity selected")
            
            # 10. RESET ENTITY EDITOR IF OPEN
            if hasattr(self, 'entity_editor') and self.entity_editor is not None:
                try:
                    self.entity_editor.close()
                    self.entity_editor = None
                except:
                    pass
            
            # 11. RESET COPY/PASTE CLIPBOARD
            if hasattr(self, 'entity_clipboard'):
                try:
                    # Clear clipboard data
                    if hasattr(self.entity_clipboard, 'clipboard_data'):
                        self.entity_clipboard.clipboard_data = None
                    if hasattr(self.entity_clipboard, 'clear_clipboard'):
                        self.entity_clipboard.clear_clipboard()
                except:
                    pass
            
            # 12. CLEAR ANY CACHED RENDER DATA
            if hasattr(self.canvas, 'entity_cache_3d'):
                self.canvas.entity_cache_3d = None
            if hasattr(self.canvas, 'entity_cache_dirty'):
                self.canvas.entity_cache_dirty = True
            if hasattr(self.canvas, 'entities_modified'):
                self.canvas.entities_modified = True
            if hasattr(self.canvas, 'selection_modified'):
                self.canvas.selection_modified = True
            
            # 13. RESET VIEW TO DEFAULT
            print("   Resetting view, Please wait.")
            if hasattr(self.canvas, 'reset_view'):
                self.canvas.reset_view()
            
            # 14. UPDATE STATUS BAR
            self.status_bar.showMessage("Editor reset - ready to load new level")
            
            # 15. FORCE CANVAS UPDATE
            if hasattr(self, 'canvas'):
                self.canvas.update()
            
            print("COMPREHENSIVE EDITOR RESET COMPLETE")
            
        except Exception as e:
            print(f"Error during comprehensive reset: {e}")
            import traceback
            traceback.print_exc()

    def select_level(self):
            """
            Visual level selection using patch folder - ENHANCED VERSION
            """
            print(f"\n=== STARTING VISUAL LEVEL SELECTION ===")
            
            # COMPREHENSIVE RESET FIRST
            self.reset_entire_editor_state()
            
            # Check if patch manager is configured
            if not hasattr(self, 'patch_manager') or not self.patch_manager.is_configured():
                print("Patch folder not configured, prompting user...")
                reply = QMessageBox.question(
                    self,
                    "Patch Folder Not Set",
                    "No patch folder is configured. Would you like to set one now?\n\n"
                    "The patch folder should contain 'worlds' and 'levels' subdirectories.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    if not self.patch_manager.set_patch_folder():
                        print("User cancelled patch folder selection")
                        return
                    else:
                        # Update worlds_folder after setting patch folder
                        from set_patch_folder import update_worlds_folder
                        update_worlds_folder(self.patch_manager, self)
                else:
                    print("User declined to set patch folder")
                    return
            
            # Scan patch folder if levels_data is empty
            if not self.patch_manager.levels_data:
                print("No levels_data, scanning patch folder...")
                
                # Create enhanced progress dialog
                from simplified_map_editor import EnhancedProgressDialog
                
                progress_dialog = EnhancedProgressDialog(
                    "Scanning Patch Folder", 
                    self, 
                    game_mode=self.game_mode
                )
                progress_dialog.append_log(f"Scanning: {os.path.basename(self.patch_manager.patch_folder)}")
                progress_dialog.show()
                QApplication.processEvents()
                
                # Get file_converter
                file_converter = self.file_converter if hasattr(self, 'file_converter') else None
                
                # Create scanner thread
                from set_patch_folder import PatchFolderScanner
                scanner_thread = PatchFolderScanner(self.patch_manager.patch_folder, file_converter)
                self.patch_manager.scanner_thread = scanner_thread
                
                scan_completed = [False]
                
                def on_complete(levels_data):
                    self.patch_manager.levels_data = levels_data or {}
                    progress_dialog.set_progress(100)
                    progress_dialog.append_log(f"âœ“ Scan complete: {len(self.patch_manager.levels_data)} levels found")
                    progress_dialog.mark_complete()
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    scan_completed[0] = True
                    print(f"Scan complete: Found {len(self.patch_manager.levels_data)} levels")
                
                def on_error(msg):
                    self.patch_manager.levels_data = {}
                    progress_dialog.append_log(f"âœ— Error: {msg}")
                    progress_dialog.mark_complete()
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    scan_completed[0] = True
                    print(f"Scan error: {msg}")
                    QMessageBox.critical(self, "Scan Error", msg)
                
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
                
                print("Scan finished.")
            
            # Check if we have any levels after scan
            if not self.patch_manager.levels_data:
                print("ERROR: No levels found after scan")
                QMessageBox.warning(
                    self,
                    "No Levels Found",
                    "No valid levels were found in the patch folder.\n\n"
                    f"Patch folder: {self.patch_manager.patch_folder}\n\n"
                    "Please ensure your patch folder contains 'worlds' and/or 'levels' subdirectories."
                )
                return
            
            # Show the visual level selector dialog
            print(f"Showing level selector dialog with {len(self.patch_manager.levels_data)} levels...")
            
            from set_patch_folder import LevelSelectorDialog
            dialog = LevelSelectorDialog(
                self.patch_manager.levels_data, 
                self, 
                self.game_mode, 
                self.patch_manager
            )
            
            def on_level_selected(level_dict):
                print(f"Level selected: {level_dict.get('name')}")
            
            def on_patch_folder_change():
                print("Patch folder change requested, restarting selection...")
                from set_patch_folder import update_worlds_folder
                update_worlds_folder(self.patch_manager, self)
                self.patch_manager.levels_data = {}
                dialog.close()
                # Restart selection after a brief delay
                QTimer.singleShot(100, self.select_level)
            
            dialog.level_selected.connect(on_level_selected)
            dialog.patch_folder_change_requested.connect(on_patch_folder_change)
            
            # Execute dialog
            result = dialog.exec()
            print(f"Level selector result: {result}")
            
            if result == QDialog.DialogCode.Accepted and hasattr(dialog, 'selected_level') and dialog.selected_level:
                level_dict = dialog.selected_level
                print(f"Loading selected level: {level_dict.get('name')}")
                
                worlds_path = level_dict.get("worlds_path")
                levels_path = level_dict.get("levels_path")
                
                # Validate paths - be lenient, allow partial data
                worlds_valid = self.validate_worlds_folder(worlds_path) if worlds_path else True
                levels_valid = self.validate_levels_folder(levels_path) if levels_path else True
                
                print(f"Validation: worlds={worlds_valid}, levels={levels_valid}")
                
                # Proceed if we have at least one valid path
                if (worlds_path and worlds_valid) or (levels_path and levels_valid):
                    print("Calling load_complete_level()...")
                    self.load_complete_level(level_dict)  # â† FIXED: Removed '_with_progress'
                else:
                    print("ERROR: No valid paths in selected level")
                    QMessageBox.warning(
                        self,
                        "Invalid Level",
                        "The selected level has no valid world or level data.\n\n"
                        f"Worlds path valid: {worlds_valid}\n"
                        f"Levels path valid: {levels_valid}"
                    )
            else:
                print("Level selection cancelled by user")

    def load_complete_level(self, level_info):
        """
        Load both world and level data for a complete level with enhanced progress dialog.
        All progress is consolidated into ONE dialog - no popup spam.
        """
        print(f"\n=== LOADING COMPLETE LEVEL: {level_info['name']} ===")

        try:
            # Create enhanced progress dialog - THE ONLY ONE
            progress_dialog = EnhancedProgressDialog("Loading Complete Level", self, game_mode=self.game_mode)
            
            # Connect cancel signal
            progress_dialog.cancelled.connect(
                lambda: self.cancel_level_loading(progress_dialog)
            )
            
            progress_dialog.show()
            QApplication.processEvents()
            
            # Helper function for logging
            def log(msg):
                print(msg)
                progress_dialog.append_log(msg)
                QApplication.processEvents()
            
            # RESET
            progress_dialog.set_status("Initializing level loading...")
            progress_dialog.set_progress(5)
            log(f"Loading level: {level_info['name']}")
            QApplication.processEvents()
            
            self.entities = []
            self.objects = []
            self.selected_entity = None
            
            total_entities = 0
            loaded_components = []
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # Set worlds folder for 3D models
            if level_info['worlds_path']:
                self.worlds_folder = level_info['worlds_path']
                log(f"Set worlds_folder for 3D models")
                print(f"✅ Set worlds_folder for 3D models: {self.worlds_folder}")
            
            # Setup canvas for 3D
            if level_info['worlds_path']:
                if hasattr(self, 'canvas') and hasattr(self.canvas, 'setup_3d_models_for_level'):
                    log("Setting up 3D models for level...")
                    print(f"📦 Setting up 3D models for level...")
                    self.canvas.setup_3d_models_for_level(level_info['worlds_path'])
                elif hasattr(self, 'canvas'):
                    print(f"⚠️ Canvas missing setup_3d_models_for_level method")
                    self.canvas.main_window = self
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # 1️⃣ Load World Data
            if level_info['worlds_path']:
                progress_dialog.set_status("Loading world data (XML files)...")
                progress_dialog.set_progress(10)
                log(f"Worlds folder: {os.path.basename(level_info['worlds_path'])}")
                QApplication.processEvents()
                
                print(f"Loading world data from: {level_info['worlds_path']}")
                
                # Enhanced search for files
                found_files = self.find_xml_files_enhanced(level_info['worlds_path'])
                log(f"Found {len(found_files)} file types in worlds folder")
                
                if progress_dialog.was_cancelled:
                    progress_dialog.close()
                    return
                
                # Convert files if needed
                progress_dialog.set_status("Converting FCB files to XML...")
                progress_dialog.set_progress(20)
                
                def update_conversion_progress(progress, message=None):
                    if progress_dialog.was_cancelled:
                        return
                    percent = int(20 + progress * 15)
                    progress_dialog.set_progress(percent)
                    if message:
                        log(message)
                    QApplication.processEvents()
                
                try:
                    success_count, error_count, errors = self.file_converter.convert_folder(
                        level_info['worlds_path'], 
                        progress_callback=update_conversion_progress
                    )
                    log(f"Conversion: {success_count} successful, {error_count} failed")
                    
                    if error_count > 0:
                        for error in errors[:2]:
                            log(f"  Error: {error}")
                            
                except Exception as e:
                    log(f"Conversion error: {str(e)}")
                    print(f"Error during conversion: {str(e)}. Continuing...")
                
                if progress_dialog.was_cancelled:
                    progress_dialog.close()
                    return
                
                # Load XML files
                progress_dialog.set_status("Loading XML files...")
                progress_dialog.set_progress(35)
                log("Processing XML files...")
                QApplication.processEvents()
                
                loaded_files = []
                
                # Load mapsdata first
                if "mapsdata" in found_files:
                    self.xml_file_path = found_files["mapsdata"]["path"]
                    self.parse_xml_file(self.xml_file_path)
                    loaded_files.append(f"mapsdata ({len(self.entities)} entities)")
                    log(f"Loaded mapsdata: {len(self.entities)} entities")
                    total_entities += len(self.entities)
                
                if progress_dialog.was_cancelled:
                    progress_dialog.close()
                    return
                
                # Load other files
                file_loaders = {
                    "omnis": self.load_omnis_data,
                    "managers": self.load_managers_data, 
                    "sectorsdep": self.load_sectordep_data
                }
                
                for file_key, loader_func in file_loaders.items():
                    if progress_dialog.was_cancelled:
                        progress_dialog.close()
                        return
                    
                    if file_key in found_files:
                        entity_count_before = len(self.entities)
                        loader_func(found_files[file_key]["path"])
                        entity_count_after = len(self.entities)
                        new_entities = entity_count_after - entity_count_before
                        loaded_files.append(f"{file_key} ({new_entities} entities)")
                        log(f"Loaded {file_key}: {new_entities} entities")
                
                if loaded_files:
                    loaded_components.append(f"World Data ({len(self.entities)} entities)")
                    print(f"✓ Loaded {len(self.entities)} entities from world data")
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # 2️⃣ Load Level Objects
            if level_info['levels_path']:
                progress_dialog.set_status("Loading level objects (worldsectors)...")
                progress_dialog.set_progress(50)
                log(f"Levels folder: {os.path.basename(level_info['levels_path'])}")
                QApplication.processEvents()
                
                print(f"Loading level objects from: {level_info['levels_path']}")
                
                # Search for worldsectors
                worldsectors_info = self.find_worldsectors_folder_enhanced(level_info['levels_path'])
                
                if worldsectors_info:
                    log(f"Found worldsectors: {worldsectors_info['fcb_files']} FCB files")
                    self.worldsectors_path = worldsectors_info["path"]
                    
                    # Look for sdat folder
                    parent_dir = os.path.dirname(worldsectors_info["path"])
                    sdat_candidate = os.path.join(parent_dir, "sdat")
                    if os.path.isdir(sdat_candidate):
                        self.sdat_path = sdat_candidate
                        log("Found sdat folder for terrain data")
                        print(f"Found sdat folder at: {self.sdat_path}")
                    else:
                        self.sdat_path = None
                        log("No sdat folder found")
                    
                    if progress_dialog.was_cancelled:
                        progress_dialog.close()
                        return
                    
                    # Load objects with progress
                    progress_dialog.set_status("Loading worldsector objects...")
                    log("Processing worldsector files...")
                    
                    def on_progress(progress):
                        if progress_dialog.was_cancelled:
                            return
                        percent = int(50 + progress * 20)
                        progress_dialog.set_progress(percent)
                        QApplication.processEvents()
                    
                    objects_success = self.load_level_objects_internal(
                        level_info['levels_path'], 
                        progress_dialog,
                        on_progress
                    )
                    
                    if objects_success:
                        loaded_components.append(f"Level Objects ({len(self.objects)} objects)")
                        total_entities += len(self.objects)
                        log(f"Loaded {len(self.objects)} objects from worldsectors")
                        print(f"✓ Loaded {len(self.objects)} objects from level data")
                    else:
                        log("No objects loaded from worldsectors")
                        print("⚠ Failed to load level objects")
                else:
                    log("No worldsectors found in levels folder")
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # 3️⃣ Setup 3D Models
            progress_dialog.set_status("Configuring 3D model loader...")
            progress_dialog.set_progress(70)
            QApplication.processEvents()
            
            if hasattr(self, 'canvas') and hasattr(self.canvas, 'model_loader'):
                log("Configuring 3D model loader...")
                from canvas.game_paths_config import update_model_loader_for_game
                update_model_loader_for_game(
                    self.canvas.model_loader, 
                    self.game_path_config
                )
                log("✓ Model loader configured")
                
                # Assign models with progress dialog
                if hasattr(self, 'entities') and self.entities:
                    progress_dialog.set_status("Assigning 3D models to entities...")
                    progress_dialog.set_progress(72)
                    log("Assigning 3D models to entities...")
                    QApplication.processEvents()
                    
                    try:
                        self.canvas.model_loader.assign_models_to_entities(
                            self.entities,
                            progress_dialog=progress_dialog,
                            parent=self,
                            game_mode=self.game_mode
                        )
                        log("✓ 3D models assigned")
                    except Exception as e:
                        log(f"⚠ Model assignment error: {str(e)}")
                        print(f"Model assignment error: {e}")
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # 4️⃣ Load Terrain
            progress_dialog.set_status("Loading terrain data...")
            progress_dialog.set_progress(80)
            QApplication.processEvents()
            
            terrain_loaded = False
            if hasattr(self, 'sdat_path') and self.sdat_path and hasattr(self.canvas, 'load_terrain'):
                log(f"Loading terrain from sdat folder...")
                print(f"Loading terrain from: {self.sdat_path}")
                try:
                    if self.canvas.load_terrain(self.sdat_path):
                        terrain_loaded = True
                        loaded_components.append("Terrain Data (Heightmap)")
                        log("✓ Terrain loaded successfully")
                        print("✓ Terrain loaded successfully")
                    else:
                        log("⚠ Terrain loading failed")
                        print("⚠ Terrain loading failed")
                except Exception as terrain_error:
                    log(f"⚠ Error loading terrain: {str(terrain_error)}")
                    print(f"⚠ Error loading terrain: {terrain_error}")
            
            if progress_dialog.was_cancelled:
                progress_dialog.close()
                return
            
            # 5️⃣ UI Finalization
            progress_dialog.set_status("Updating display...")
            progress_dialog.set_progress(90)
            log("Finalizing UI...")
            QApplication.processEvents()
            
            if hasattr(self, 'update_entity_statistics'):
                self.update_entity_statistics()
            self.canvas.set_entities(self.entities)
            if hasattr(self, 'entity_tree'):
                self.update_entity_tree()
            self.reset_view()
            
            level_name = level_info['name']
            if hasattr(self, 'level_info_label'):
                self.level_info_label.setText(f"Loaded complete level: {level_name}")
            elif hasattr(self, 'xml_file_label'):
                self.xml_file_label.setText(f"Loaded complete level: {level_name}")
            
            self.status_bar.showMessage(f"Loaded {level_name}: {total_entities} total entities/objects")
            
            # Store level info
            self.current_level_info = level_info
            
            # Complete
            progress_dialog.set_progress(100)
            log(f"✓ Level loading complete!")
            progress_dialog.mark_complete()
            progress_dialog.close()  # SPINNER AUTO-STOPS ON CLOSE
            
            # Summary popup
            if loaded_components:
                success_message = f"Successfully loaded level '{level_name}':\n\n"
                success_message += "\n".join([f"• {c}" for c in loaded_components])
                success_message += f"\n\nTotal entities/objects: {total_entities}"
                QMessageBox.information(self, "Level Loaded Successfully", success_message)
            else:
                QMessageBox.warning(self, "No Data Loaded", f"No valid data found for level '{level_name}'")
            
            # Reset all modification flags
            self.xml_tree_modified = False
            self.omnis_tree_modified = False
            self.managers_tree_modified = False
            self.sectordep_tree_modified = False
            self.entities_modified = False
            if hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified.clear()
            
            print(f"=== COMPLETE LEVEL LOADING FINISHED ===\n")
        
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.mark_complete()
                progress_dialog.close()
            QMessageBox.critical(self, "Error Loading Level", f"Failed to load level: {str(e)}")
            print(f"✗ Error loading complete level: {e}")
            import traceback
            traceback.print_exc()
        
    def load_level_objects_internal(self, levels_path, progress_dialog=None, progress_callback=None):
        """Internal method to load level objects without UI dialogs"""
        try:
            # Enhanced search for worldsectors
            worldsectors_info = self.find_worldsectors_folder_enhanced(levels_path)
            
            if not worldsectors_info:
                print(f"No worldsectors found in {levels_path}")
                return False
            
            worldsectors_path = worldsectors_info["path"]
            print(f"Found worldsectors at: {worldsectors_path}")
            
            # Store worldsectors path
            self.worldsectors_path = worldsectors_path
            
            # Create and start loading thread
            self.object_loading_thread = ObjectLoadingThread(
                worldsectors_path, 
                self.file_converter, 
                self.grid_config
            )
            
            # Connect signals
            objects_loaded = []
            
            def on_objects_loaded(objects):
                objects_loaded.extend(objects)
            
            def on_progress(progress):
                if progress_callback:
                    progress_callback(progress)
            
            def on_log_message(message):
                if progress_dialog:
                    progress_dialog.append_log(message)
            
            self.object_loading_thread.objects_loaded.connect(on_objects_loaded)
            self.object_loading_thread.progress_updated.connect(on_progress)
            
            if hasattr(self.object_loading_thread, 'log_message'):
                self.object_loading_thread.log_message.connect(on_log_message)
            
            # Run synchronously for this internal method
            self.object_loading_thread.run()  # Use run() instead of start() for synchronous execution
            
            # Process loaded objects
            if objects_loaded:
                self.on_objects_loaded(objects_loaded)
                print(f"Loaded {len(objects_loaded)} objects from level data")
                return True
            else:
                print("No objects were loaded from level data")
                return False
            
        except Exception as e:
            print(f"Error loading level objects: {e}")
            return False

    def load_level_folder(self):
        """Load a level folder with enhanced subfolder search - WITH COMPREHENSIVE RESET"""
        # COMPREHENSIVE RESET FIRST
        self.reset_entire_editor_state()
        
        # Open folder selection dialog
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Worlds Folder (will search subfolders automatically)",
            ""
        )
        
        if not folder_path:
            return
        
        try:
            print(f"Loading level from: {folder_path}")
            
            # DEBUG: Check game mode before creating dialog
            print(f"DEBUG: self.game_mode = '{self.game_mode}'")
            
            # Create enhanced progress dialog
            progress_dialog = EnhancedProgressDialog("Loading Level", self, game_mode=self.game_mode)
            
            # Connect cancel signal
            progress_dialog.cancelled.connect(
                lambda: self.cancel_loading(self.object_loading_thread if hasattr(self, 'object_loading_thread') else None, progress_dialog)
            )
            
            progress_dialog.show()
            QApplication.processEvents()
            
            # Enhanced search for files
            progress_dialog.set_status("Searching for level files, Please wait.")
            progress_dialog.set_progress(10)
            progress_dialog.append_log("Searching for XML files...")
            QApplication.processEvents()
            
            found_files = self.find_xml_files_enhanced(folder_path)
            progress_dialog.append_log(f"Found {len(found_files)} file types")
            
            # Setup EntityLibrary folder for 3D model lookups
            if hasattr(self, 'canvas') and hasattr(self.canvas, 'model_loader'):
                print(f"\n=== Setting up EntityLibrary for 3D models ===")
                if self.canvas.model_loader.set_entity_library_folder(folder_path):
                    print(f"✓ EntityLibrary configured for model lookups")
                    progress_dialog.append_log("✓ EntityLibrary found for 3D models")
                else:
                    print(f"⚠ EntityLibrary not found (3D models will use fallback)")
                    progress_dialog.append_log("⚠ No EntityLibrary (3D models disabled)")
            
            # Also search for worldsectors
            worldsectors_info = self.find_worldsectors_folder_enhanced(folder_path)
            if worldsectors_info:
                progress_dialog.append_log(f"Found worldsectors: {worldsectors_info['fcb_files']} FCB files")
            
            # Progress callback for conversion
            def update_progress(progress, message=None):
                if progress_dialog.was_cancelled:
                    return  # Just return, don't raise exception
                percent = int(10 + progress * 40)
                progress_dialog.set_progress(percent)
                if message:
                    progress_dialog.append_log(message)
                else:
                    progress_dialog.set_status(f"Converting files, Please Wait. {percent}%")
                QApplication.processEvents()
            
            # Convert files if needed
            try:
                success_count, error_count, errors = self.file_converter.convert_folder(
                    folder_path, 
                    progress_callback=update_progress
                )
                progress_dialog.append_log(f"Conversion: {success_count} successful, {error_count} failed")
                
                if error_count > 0:
                    for error in errors[:3]:
                        progress_dialog.append_log(f"  Error: {error}")
                
                # Check if cancelled during conversion
                if progress_dialog.was_cancelled:
                    progress_dialog.append_log("Operation cancelled by user")
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    return
                                
            except Exception as e:
                progress_dialog.append_log(f"Conversion error: {str(e)}")
                print(f"Error during conversion: {str(e)}. Continuing with existing XML files, Please wait.")
            
            # Check if cancelled
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            # Check if we found the essential files
            if not found_files:
                progress_dialog.stop_icon()
                progress_dialog.close()
                
                search_info = "Searched in:\nMain folder\nAll subfolders (up to 3 levels deep)\n\n"
                search_info += "Looking for:\nmapsdata.xml/.fcb\n.managers.xml/.fcb\n.omnis.xml/.fcb\nsectorsdep.xml/.fcb"
                
                if worldsectors_info:
                    search_info += f"\n\nFound worldsectors folder:\n{worldsectors_info['relative_path']} ({worldsectors_info['fcb_files']} .fcb files)"
                
                QMessageBox.warning(
                    self,
                    "Main Files Not Found",
                    f"Could not find the main level files in the selected folder or subfolders.\n\n{search_info}\n\n"
                    f"Please ensure the conversion tools are available or that XML versions exist."
                )
                return
            
            # Update progress for file loading
            progress_dialog.set_status("Loading XML files, Please wait.")
            progress_dialog.set_progress(60)
            progress_dialog.append_log("Processing XML files...")
            QApplication.processEvents()
            
            # Load the found files
            loaded_files = []
            
            progress_dialog.set_progress(70)
            progress_dialog.set_status("Processing entities, Please wait.")
            QApplication.processEvents()
            
            # Load mapsdata first
            if "mapsdata" in found_files:
                self.xml_file_path = found_files["mapsdata"]["path"]
                self.parse_xml_file(self.xml_file_path)
                
                location = found_files["mapsdata"]["location"]
                location_text = f" (found in {location})" if location != "." else ""
                loaded_files.append(f"{os.path.basename(self.xml_file_path)} ({len(self.entities)} entities){location_text}")
                progress_dialog.append_log(f"Loaded mapsdata: {len(self.entities)} entities")
            
            # Check if cancelled
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            progress_dialog.set_progress(80)
            QApplication.processEvents()
            
            # Load other files
            file_loaders = {
                "omnis": self.load_omnis_data,
                "managers": self.load_managers_data, 
                "sectorsdep": self.load_sectordep_data
            }
            
            for file_key, loader_func in file_loaders.items():
                if progress_dialog.was_cancelled:
                    progress_dialog.stop_icon()
                    progress_dialog.close()
                    return
                
                if file_key in found_files:
                    entity_count_before = len(self.entities)
                    loader_func(found_files[file_key]["path"])
                    entity_count_after = len(self.entities)
                    new_entities = entity_count_after - entity_count_before
                    
                    location = found_files[file_key]["location"]
                    location_text = f" (found in {location})" if location != "." else ""
                    loaded_files.append(f"{os.path.basename(found_files[file_key]['path'])} ({new_entities} entities){location_text}")
                    progress_dialog.append_log(f"Loaded {file_key}: {new_entities} entities")
            
            # Check if cancelled
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            progress_dialog.set_progress(95)
            progress_dialog.set_status("Updating display, Please wait.")
            QApplication.processEvents()
            
            # Update UI
            folder_name = os.path.basename(folder_path)
            if hasattr(self, 'xml_file_label'):
                self.xml_file_label.setText(f"Loaded {len(loaded_files)} main files from:\n{folder_name}")
            elif hasattr(self, 'level_info_label'):
                self.level_info_label.setText(f"Loaded {len(loaded_files)} main files from:\n{folder_name}")
            
            self.status_bar.showMessage(f"Loaded level: {len(self.entities)} total entities")
            
            # Update displays
            if hasattr(self, 'update_entity_statistics'):
                self.update_entity_statistics()
            
            self.canvas.set_entities(self.entities)
            
            if hasattr(self, 'entity_tree'):
                self.update_entity_tree()
            
            self.reset_view()
            
            # Mark complete and close progress dialog BEFORE showing success message
            progress_dialog.set_progress(100)
            progress_dialog.mark_complete()
            progress_dialog.stop_icon()
            progress_dialog.close()
            
            # Build success message
            success_message = f"Successfully loaded the main level files:\n\n" + "\n".join(loaded_files)
            
            if worldsectors_info:
                success_message += f"\n\nAlso found worldsectors folder:\n{worldsectors_info['relative_path']}"
                success_message += f"\n  ({worldsectors_info['fcb_files']} .fcb, {worldsectors_info['xml_files']} .xml files)"
                success_message += f"\n\nUse 'Load Objects' to load worldsector entities."
            
            success_message += f"\n\nTotal entities: {len(self.entities)}"
            
            # Show success message AFTER closing dialog
            QMessageBox.information(
                self,
                "Level Loaded Successfully",
                success_message
            )
            
            # Reset all modification flags
            self.xml_tree_modified = False
            self.omnis_tree_modified = False
            self.managers_tree_modified = False
            self.sectordep_tree_modified = False
            self.entities_modified = False

        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.mark_complete()
                progress_dialog.stop_icon()
                progress_dialog.close()
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to load level: {str(e)}"
            )

    def handle_load_cancel(self, dialog):
        """Handle cancellation of load operation"""
        dialog.append_log("Stopping load operation...")
        # The dialog will close naturally when the method returns

    def load_level_objects(self):
        """Load objects from worldsectors folder with enhanced search - WITH ANIMATED LOADING ICON AND LOG"""
        print("=== Starting enhanced load_level_objects ===")
        
        # COMPREHENSIVE RESET FIRST
        self.reset_entire_editor_state()
        
        # Select folder
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Level Folder (containing worldsectors)",
            ""
        )
        
        if not selected_folder:
            print("No folder selected")
            return
        
        print(f"Selected folder: {selected_folder}")
        
        # Enhanced search for worldsectors
        worldsectors_info = self.find_worldsectors_folder_enhanced(selected_folder)
        
        if not worldsectors_info:
            QMessageBox.warning(
                self,
                "No Worldsectors Found",
                f"No worldsectors folder found in:\n{selected_folder}"
            )
            return
        
        worldsectors_path = worldsectors_info["path"]
        print(f"Found worldsectors at: {worldsectors_path}")
        
        # *** NEW: Look for sdat folder in the same parent directory ***
        parent_dir = os.path.dirname(worldsectors_path)
        sdat_candidate = os.path.join(parent_dir, "sdat")
        if os.path.isdir(sdat_candidate):
            self.sdat_path = sdat_candidate
            print(f"Found sdat folder at: {self.sdat_path}")
        else:
            self.sdat_path = None
            print("No sdat folder found (terrain data will not be available)")
        
        # Check file counts
        total_files = worldsectors_info["fcb_files"] + worldsectors_info["xml_files"] + worldsectors_info["data_xml_files"]
        
        if total_files == 0:
            QMessageBox.warning(
                self,
                "No Object Files Found",
                f"No .data.fcb or .data.xml files found in:\n{worldsectors_info['relative_path']}"
            )
            return
        
        # Show confirmation dialog
        location_text = f"in {worldsectors_info['relative_path']}" if worldsectors_info['relative_path'] != "." else "in selected folder"
        
        message = (
            f"Found worldsectors {location_text}:\n\n"
            f"{worldsectors_info['fcb_files']} .data.fcb files\n"
            f"{worldsectors_info['xml_files']} .converted.xml files\n"
            f"{worldsectors_info['data_xml_files']} .data.xml files\n\n"
            f"Continue?"
        )
        
        reply = QMessageBox.question(
            self,
            "Load Level Objects",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Store worldsectors path
        self.worldsectors_path = worldsectors_path
        
        # Create enhanced progress dialog
        progress_dialog = EnhancedProgressDialog("Loading Level Objects", self, game_mode=self.game_mode)
        progress_dialog.show()
        QApplication.processEvents()
        
        print("Creating ObjectLoadingThread, Please wait.")
        
        try:
            # Create and start loading thread
            self.object_loading_thread = ObjectLoadingThread(
                worldsectors_path, 
                self.file_converter, 
                self.grid_config
            )
            
            # Connect thread signals
            self.object_loading_thread.progress_updated.connect(
                lambda p: progress_dialog.set_progress(int(p * 100))
            )
            self.object_loading_thread.status_updated.connect(
                lambda s: progress_dialog.set_status(s)
            )
            
            # Connect log messages signal
            self.object_loading_thread.log_message.connect(
                lambda msg: progress_dialog.append_log(msg)
            )
            
            self.object_loading_thread.objects_loaded.connect(self.on_objects_loaded)
            self.object_loading_thread.finished_loading.connect(
                lambda result: self.on_object_loading_finished(result, progress_dialog)
            )
                        
            # Handle cancel button AND X button via the cancelled signal
            progress_dialog.cancelled.connect(
                lambda: self.cancel_loading(self.object_loading_thread, progress_dialog)
            )

            print("Starting object loading thread, Please wait.")
            
            # Start loading
            self.object_loading_thread.start()
            
        except Exception as e:
            progress_dialog.stop_icon()
            progress_dialog.close()
            QMessageBox.critical(
                self,
                "Loading Error",
                f"Failed to start object loading:\n{str(e)}"
            )
            print(f"Error starting object loading: {e}")
            import traceback
            traceback.print_exc()

    def append_log_message(self, log_box, message):
        """Append a message to the log box and auto-scroll"""
        log_box.append(message)
        # Auto-scroll to bottom
        scrollbar = log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def cancel_loading(self, thread, dialog):
        """Cancel the loading operation - close dialog after stopping thread"""
        thread.stop()
        dialog.stop_icon()
        # Close the dialog immediately after cancelling
        dialog.close()

    def on_object_loading_finished(self, result, progress_dialog):
        """
        Handle when object loading is complete and automatically load terrain if available.
        """
        progress_dialog.mark_complete()
        progress_dialog.stop_icon()
        progress_dialog.close()

        if not progress_dialog.was_cancelled:
            # Show conversion errors if any
            if result.conversion_errors:
                error_msg = "\n".join(result.conversion_errors[:5])
                if len(result.conversion_errors) > 5:
                    error_msg += f"\n... and {len(result.conversion_errors) - 5} more errors"
                QMessageBox.warning(
                    self,
                    "Loading Completed with Errors",
                    f"Loaded {result.loaded_objects} objects from {result.sectors_processed} sectors.\n\n"
                    f"Errors encountered:\n{error_msg}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Objects Loaded Successfully",
                    f"Successfully loaded {result.loaded_objects} objects from {result.sectors_processed} sectors!"
                )

            # Update status bar
            self.status_bar.showMessage(
                f"Loaded {len(self.entities)} entities and {len(self.objects)} objects"
            )

            # Reset view
            self.reset_view()

            # Auto-load terrain
            if self.sdat_path:
                try:
                    print(f"Attempting to load terrain from: {self.sdat_path}")
                    if not hasattr(self.canvas, 'terrain_renderer') or self.canvas.terrain_renderer is None:
                        from canvas.terrain_renderer import TerrainRenderer
                        self.canvas.terrain_renderer = TerrainRenderer()
                        print(f"Initialized TerrainRenderer for game mode: {self.game_mode}")

                    success = self.canvas.load_terrain(self.sdat_path)

                    if success:
                        print("Terrain loaded successfully into canvas!")

                        if self.game_mode.lower() == "farcry2":
                            tr = self.canvas.terrain_renderer
                            center_x = (tr.terrain_world_min_x + tr.terrain_world_max_x) / 2
                            center_y = (tr.terrain_world_min_y + tr.terrain_world_max_y) / 2

                            if hasattr(self.canvas, "center_on_world"):
                                self.canvas.center_on_world(center_x, center_y)
                            else:
                                self.canvas.viewport_offset_x = center_x
                                self.canvas.viewport_offset_y = center_y

                            print(f"[FC2] View centered on terrain at ({center_x}, {center_y})")
                    else:
                        print("Failed to load terrain data")

                except Exception as e:
                    print(f"Error loading terrain: {e}")
                    import traceback
                    traceback.print_exc()
                    QMessageBox.warning(
                        self,
                        "Terrain Loading Error",
                        f"Could not load terrain:\n{str(e)}"
                    )


    def load_terrain_viewer(self):
        """Load terrain data directly into the canvas"""
        if not self.sdat_path:
            print("No sdat path available, cannot load terrain")
            return False

        try:
            print(f"Loading terrain data from: {self.sdat_path}")
            success = self.canvas.load_terrain(self.sdat_path)

            if success:
                print("Terrain loaded successfully into canvas!")
            else:
                print("Failed to load terrain data")
            return success

        except Exception as e:
            print(f"Error loading terrain: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self,
                "Terrain Loading Error",
                f"Could not load terrain:\n{str(e)}"
            )
            return False

    def auto_load_terrain_if_available(self, base_path):
        """Automatically search for and load terrain data from a base path"""
        if not base_path or not os.path.isdir(base_path):
            return False

        print(f"Searching for terrain data in: {base_path}")

        sdat_candidates = [
            os.path.join(base_path, "sdat"),
            os.path.join(os.path.dirname(base_path), "sdat"),
            os.path.join(base_path, "levels", "sdat"),
        ]

        found_sdat = None
        for candidate in sdat_candidates:
            if os.path.isdir(candidate):
                csdat_files = glob.glob(os.path.join(candidate, "*.csdat"))
                sdat_files = glob.glob(os.path.join(candidate, "*.sdat"))
                is_fc2 = self.game_mode.lower() == "farcry2"
                if (is_fc2 and sdat_files) or (not is_fc2 and csdat_files):
                    found_sdat = candidate
                    print(f"Found terrain folder at: {found_sdat}")
                    break

        if not found_sdat:
            print("No terrain folder with .csdat or .sdat files found")
            return False

        self.sdat_path = found_sdat
        return self.load_terrain_viewer()

    def load_world_data_internal(self, worlds_path, progress_dialog=None):
        """Load world data WITHOUT EntityLibrary FCB conversion"""
        try:
            # 1️⃣ Find XML files in worlds_path
            found_files = self.find_xml_files_enhanced(worlds_path)
            if not found_files:
                print(f"No world XML files found in {worlds_path}")
                return False

            # ⚠️ EntityLibrary conversion removed entirely
            print("Skipping EntityLibrary FCB conversion")

            # 4️⃣ Setup EntityLibrary for 3D model lookups (folder/XML only)
            if hasattr(self, 'canvas') and hasattr(self.canvas, 'model_loader'):
                print(f"\n=== Setting up EntityLibrary for 3D models ===")

                entity_library_fcb = os.path.join(worlds_path, "entitylibrary_full.fcb")
                entity_lib_folder = entity_library_fcb + ".converted"
                entity_lib_xml = entity_library_fcb + ".converted.xml"

                success = False
                if os.path.exists(entity_lib_folder) and os.path.isdir(entity_lib_folder):
                    success = self.canvas.model_loader.set_entity_library_folder(worlds_path)
                    print(f"✓ EntityLibrary folder used: {entity_lib_folder}")
                elif os.path.exists(entity_lib_xml):
                    success = self.canvas.model_loader.set_entity_library_xml(entity_lib_xml)
                    print(f"✓ EntityLibrary merged XML used: {entity_lib_xml}")
                else:
                    print("⚠️ EntityLibrary not found (3D models disabled)")

                if success:
                    game_data_path = os.path.dirname(os.path.dirname(worlds_path))
                    possible_model_paths = [
                        os.path.join(game_data_path, "graphics", "_models"),
                        os.path.join(game_data_path, "worlds", "graphics", "_models"),
                        os.path.join(os.path.dirname(game_data_path), "graphics", "_models"),
                    ]
                    for models_path in possible_model_paths:
                        if os.path.exists(models_path):
                            gltf_count = len(list(Path(models_path).rglob('*.gltf')))
                            self.canvas.model_loader.set_models_directory(models_path)
                            print(f"✓ Models directory set: {models_path} ({gltf_count} GLTF files)")
                            break

                    possible_material_paths = [
                        os.path.join(game_data_path, "graphics", "_materials"),
                        os.path.join(game_data_path, "worlds", "graphics", "_materials"),
                        os.path.join(os.path.dirname(game_data_path), "graphics", "_materials"),
                    ]
                    for materials_path in possible_material_paths:
                        if os.path.exists(materials_path):
                            self.canvas.model_loader.set_materials_directory(materials_path)
                            print(f"✓ Materials directory set: {materials_path}")
                            break

                print(f"\n🔧 Re-assigning models to {len(self.entities)} entities...")
                self.canvas.model_loader.assign_models_to_entities(self.entities)

            else:
                print("✗ Canvas or model_loader not available")

            # 5️⃣ Load XML files into entities
            loaded_files = []
            entity_count_before = len(self.entities)

            if "mapsdata" in found_files:
                self.xml_file_path = found_files["mapsdata"]["path"]
                self.parse_xml_file(self.xml_file_path)
                loaded_files.append(f"mapsdata ({len(self.entities) - entity_count_before} entities)")

            file_loaders = {
                "omnis": self.load_omnis_data,
                "managers": self.load_managers_data,
                "sectorsdep": self.load_sectordep_data
            }
            for key, loader_func in file_loaders.items():
                if key in found_files:
                    entity_count_before = len(self.entities)
                    loader_func(found_files[key]["path"])
                    loaded_files.append(f"{key} ({len(self.entities) - entity_count_before} entities)")

            print(f"Loaded world files: {loaded_files}")
            return True

        except Exception as e:
            print(f"Error loading world data: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_and_convert_worldsectors(self):
        """Save and convert WorldSectors files using the improved separated approach"""
        if not hasattr(self, 'worldsectors_trees') or not self.worldsectors_trees:
            return 0
        
        print(f"\nÃ°Å¸â€™Â¾ Starting improved WorldSectors save and conversion, Please wait.")
        
        # Step 1: Save all XML files first
        print(f"Ã°Å¸â€œÂ Step 1: Saving modified XML files, Please wait.")
        saved_xml_files = []
        
        for xml_file_path, tree in self.worldsectors_trees.items():
            if xml_file_path.endswith('.converted.xml'):
                try:
                    # Save the XML with current entity positions
                    tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                    saved_xml_files.append(xml_file_path)
                    print(f"   Saved: {os.path.basename(xml_file_path)}")
                except Exception as e:
                    print(f"   Failed to save {os.path.basename(xml_file_path)}: {e}")
        
        if not saved_xml_files:
            print(f"No XML files were saved")
            return 0
        
        print(f"Ã°Å¸â€œÅ  Saved {len(saved_xml_files)} XML files")
        
        # Step 2: Use the improved conversion method
        print(f"\nStep 2: Converting files using improved method, Please wait.")
        
        if hasattr(self, 'worldsectors_path') and self.worldsectors_path:
            success = self.file_converter.convert_all_worldsector_files_improved(self.worldsectors_path)
        else:
            # Fallback: get path from first XML file
            if saved_xml_files:
                worldsectors_path = os.path.dirname(saved_xml_files[0])
                success = self.file_converter.convert_all_worldsector_files_improved(worldsectors_path)
            else:
                print(f"No worldsectors path available")
                return 0
        
        if success:
            # Step 3: Clean up worldsectors_trees for successfully converted files
            print(f"\nÃ°Å¸Â§Â¹ Step 3: Cleaning up memory, Please wait.")
            
            # Remove converted XML files from tracking
            xml_files_to_remove = []
            for xml_file_path in self.worldsectors_trees.keys():
                if xml_file_path.endswith('.converted.xml') and not os.path.exists(xml_file_path):
                    xml_files_to_remove.append(xml_file_path)
            
            for xml_file_path in xml_files_to_remove:
                del self.worldsectors_trees[xml_file_path]
                print(f"   Ã°Å¸â€”â€˜ Removed from tracking: {os.path.basename(xml_file_path)}")
            
            # Clear modification flags
            if hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified.clear()
            
            print(f"WorldSectors conversion completed successfully!")
            return len(saved_xml_files)
        else:
            print(f"WorldSectors conversion failed or was incomplete")
            return 0

    def save_level(self):
        """FIXED save_level method with proper FCB conversion"""
        reply = QMessageBox.question(
            self, 
            "Save Level",
            "This will save all changes and convert files back to FCB format:\n"
            "1. Save XML files with current entity positions\n"
            "2. Convert main XML files to FCB\n"
            "3. Convert WorldSector XML files to FCB\n"
            "4. Clean up temporary files\n\n"
            "Make sure the game is completely closed before proceeding!\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.No:
            return
        
        try:
            # Create enhanced progress dialog
            progress_dialog = EnhancedProgressDialog("Saving Level", self, game_mode=self.game_mode)
            progress_dialog.cancelled.connect(lambda: self.handle_save_cancel(progress_dialog))
            progress_dialog.show()
            QApplication.processEvents()
            
            # Helper for logging
            def log(message):
                progress_dialog.append_log(message)
            
            # Step 1: Save all XML files first
            progress_dialog.set_status("Saving XML files with current positions, Please wait.")
            progress_dialog.set_progress(10)
            log("Saving XML files...")
            QApplication.processEvents()
            
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            self.save_all_xml_files_before_conversion()
            log("XML files saved")
            
            # Step 2: Convert main XML files to FCB
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            progress_dialog.set_status("Converting main files to FCB, Please wait.")
            progress_dialog.set_progress(30)
            log("Converting main XML -> FCB...")
            QApplication.processEvents()
            
            main_files_converted = self._convert_main_xml_to_fcb(log_callback=log)
            log(f"Main files: {main_files_converted} converted")
            
            # Step 3: Convert WorldSector files
            if progress_dialog.was_cancelled:
                progress_dialog.stop_icon()
                progress_dialog.close()
                return
            
            progress_dialog.set_status("Converting WorldSector files to FCB, Please wait.")
            progress_dialog.set_progress(60)
            log("Converting WorldSector XML -> FCB...")
            QApplication.processEvents()
            
            worldsector_files_converted = self._convert_worldsector_files_fixed(log_callback=log)
            log(f"WorldSector files: {worldsector_files_converted} converted")
            
            # Mark complete and close progress dialog BEFORE showing results
            progress_dialog.set_progress(100)
            progress_dialog.mark_complete()
            progress_dialog.stop_icon()
            progress_dialog.close()
            
            # Show results only if not cancelled
            if not progress_dialog.was_cancelled:
                if worldsector_files_converted > 0 or main_files_converted > 0:
                    QMessageBox.information(
                        self, 
                        "Level Saved Successfully", 
                        f"Successfully saved level!\n\n"
                        f"Main files converted: {main_files_converted}\n"
                        f"WorldSector files converted: {worldsector_files_converted}\n\n"
                        f"Your changes should now appear in the game!\n\n"
                        f"Make sure to launch the game to test your changes."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Save Issues",
                        f"Save completed but some conversions may have failed.\n"
                        f"Check the console output for details."
                    )
            
            # Reset modification flags
            self.entities_modified = False
            self.xml_tree_modified = False
            if hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified.clear()
                    
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.mark_complete()
                progress_dialog.stop_icon()
                progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Save failed: {str(e)}")

    def handle_save_cancel(self, dialog):
        """Handle cancellation of save operation"""
        dialog.append_log("Stopping save operation...")
        dialog.stop_icon()
        dialog.close()

    def save_all_xml_files_before_conversion(self):
        """Save all XML files before converting to FCB - CRITICAL STEP"""
        print(f"\nÃ°Å¸â€™Â¾ STEP 1: Saving all XML files with current entity positions, Please wait.")
        
        # 1. Save main XML files
        if hasattr(self, 'xml_tree') and self.xml_tree and hasattr(self, 'xml_file_path'):
            try:
                self.xml_tree.write(self.xml_file_path, encoding='utf-8', xml_declaration=True)
                print(f"   Saved main XML: {os.path.basename(self.xml_file_path)}")
            except Exception as e:
                print(f"   Failed to save main XML: {e}")
        
        # 2. Save other main XML files
        main_files = {
            'omnis_tree': 'omnis',
            'managers_tree': 'managers', 
            'sectordep_tree': 'sectorsdep'
        }
        
        for tree_attr, file_type in main_files.items():
            if hasattr(self, tree_attr):
                tree = getattr(self, tree_attr)
                if tree is not None:
                    file_path = self._find_tree_file_path(file_type)
                    if file_path:
                        try:
                            tree.write(file_path, encoding='utf-8', xml_declaration=True)
                            print(f"   Saved {file_type} XML: {os.path.basename(file_path)}")
                        except Exception as e:
                            print(f"   Failed to save {file_type} XML: {e}")
        
        # 3. CRITICAL: Save WorldSector .converted.xml files
        if hasattr(self, 'worldsectors_trees'):
            # First, update all entity XML elements with current positions
            print(f"   Updating entity positions in XML...")
            updated_count = 0
            for entity in self.entities:
                if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                    # Check if this entity is from a WorldSector file
                    source_file = getattr(entity, 'source_file', None)
                    source_file_path = getattr(entity, 'source_file_path', None)
                    is_worldsector = (source_file == 'worldsectors' or 
                                    (source_file_path and 'worldsector' in source_file_path.lower()))
                    
                    if is_worldsector:
                        # This is a WorldSector entity - update its XML
                        if self._update_object_xml_position(entity):
                            updated_count += 1
            
            if updated_count > 0:
                print(f"   Updated {updated_count} entity positions in XML")
            else:
                print(f"   Warning: No entity XML positions were updated!")
            
            # Now save the WorldSector XML files
            for xml_file_path, tree in self.worldsectors_trees.items():
                if xml_file_path.endswith('.converted.xml'):
                    try:
                        # Get file info before save
                        old_size = os.path.getsize(xml_file_path) if os.path.exists(xml_file_path) else 0
                        old_mtime = os.path.getmtime(xml_file_path) if os.path.exists(xml_file_path) else 0
                        
                        # Save the tree with current entity positions
                        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                        
                        # Verify save
                        new_size = os.path.getsize(xml_file_path) if os.path.exists(xml_file_path) else 0
                        new_mtime = os.path.getmtime(xml_file_path) if os.path.exists(xml_file_path) else 0
                        
                        if new_mtime != old_mtime:
                            print(f"   Saved WorldSector XML: {os.path.basename(xml_file_path)} ({new_size} bytes)")
                        else:
                            print(f"   WorldSector XML may not have saved: {os.path.basename(xml_file_path)}")
                            
                    except Exception as e:
                        print(f"   Failed to save WorldSector XML {os.path.basename(xml_file_path)}: {e}")
        
        print(f"Ã°Å¸â€™Â¾ XML save phase complete")

    def _convert_worldsector_files_fixed(self, log_callback=None):
        """Convert WorldSector .converted.xml files back to .data.fcb - FIXED VERSION with logging"""
        
        def log(message):
            print(message)
            if log_callback:
                try:
                    log_callback(message)
                except:
                    pass
        
        log("\nSTEP 2: Converting WorldSector XML files to FCB, Please wait.")
        
        if not hasattr(self, 'worldsectors_trees') or not self.worldsectors_trees:
            log("No WorldSector trees loaded")
            return 0
        
        # Find all .converted.xml files
        converted_xml_files = []
        for file_path in self.worldsectors_trees.keys():
            if file_path.endswith('.converted.xml') and os.path.exists(file_path):
                converted_xml_files.append(file_path)
        
        if not converted_xml_files:
            log("No .converted.xml files found to convert")
            return 0
        
        log(f"Found {len(converted_xml_files)} .converted.xml files to convert")
        
        converted_count = 0
        failed_files = []
        
        for xml_file in converted_xml_files:
            try:
                # Get the target FCB file path
                # worldsector33.data.fcb.converted.xml -> worldsector33.data.fcb
                if xml_file.endswith('.data.fcb.converted.xml'):
                    target_fcb = xml_file.replace('.data.fcb.converted.xml', '.data.fcb')
                else:
                    log(f"Unexpected file format: {xml_file}")
                    failed_files.append(xml_file)
                    continue
                
                log(f"\nConverting: {os.path.basename(xml_file)} -> {os.path.basename(target_fcb)}")
                
                # Verify XML file exists and has content
                if not os.path.exists(xml_file):
                    log(f"   XML file missing: {xml_file}")
                    failed_files.append(xml_file)
                    continue
                
                xml_size = os.path.getsize(xml_file)
                if xml_size == 0:
                    log("   XML file is empty")
                    failed_files.append(xml_file)
                    continue
                
                log(f"   XML file size: {xml_size} bytes")
                
                # Method 1: Try using the file converter
                result_path = self.file_converter.convert_converted_xml_back_to_fcb(target_fcb)
                
                if result_path and os.path.exists(result_path):
                    fcb_size = os.path.getsize(result_path)
                    log(f"   Conversion successful: {os.path.basename(result_path)} ({fcb_size} bytes)")
                    
                    # If the result is a _new.fcb file, we need to rename it
                    if result_path.endswith('_new.fcb'):
                        log("   Renaming _new.fcb file to replace original, Please wait.")
                        
                        # Remove original FCB if it exists
                        if os.path.exists(target_fcb):
                            try:
                                os.remove(target_fcb)
                                log("   Removed original FCB")
                            except Exception as e:
                                log(f"   Could not remove original FCB: {e}")
                        
                        # Rename _new.fcb to target name
                        try:
                            os.rename(result_path, target_fcb)
                            log(f"   Renamed to: {os.path.basename(target_fcb)}")
                        except Exception as e:
                            log(f"   Rename failed: {e}")
                            failed_files.append(xml_file)
                            continue
                    
                    converted_count += 1
                    
                    # Clean up the .converted.xml file after successful conversion
                    try:
                        os.remove(xml_file)
                        log(f"   Removed XML file: {os.path.basename(xml_file)}")
                        
                        # Remove from worldsectors_trees
                        if xml_file in self.worldsectors_trees:
                            del self.worldsectors_trees[xml_file]
                            log("   Removed from tracking")
                            
                    except Exception as cleanup_error:
                        log(f"   Cleanup warning: {cleanup_error}")
                    
                else:
                    log("   Conversion failed - no output file created")
                    failed_files.append(xml_file)
                    
            except Exception as e:
                log(f"   Error converting {xml_file}: {e}")
                failed_files.append(xml_file)
        
        # Summary
        log("\nWorldSector conversion summary:")
        log(f"   Successfully converted: {converted_count}/{len(converted_xml_files)} files")
        
        if failed_files:
            log(f"   Failed conversions: {len(failed_files)} files")
            for failed_file in failed_files[:5]:  # Show first 5
                log(f"     - {os.path.basename(failed_file)}")
            if len(failed_files) > 5:
                log(f"     ... and {len(failed_files) - 5} more")
        
        return converted_count

    def debug_verify_entity_in_files(self, entity_name):
        """Debug method to trace an entity through the entire save process"""
        print(f"\nTRACING ENTITY: {entity_name}")
        
        # Find the entity
        target_entity = None
        for entity in self.entities:
            if entity.name == entity_name:
                target_entity = entity
                break
        
        if not target_entity:
            print(f"Entity {entity_name} not found")
            return
        
        print(f"Ã°Å¸â€œÂ Entity position: ({target_entity.x:.1f}, {target_entity.y:.1f}, {target_entity.z:.1f})")
        print(f"Source file: {getattr(target_entity, 'source_file_path', 'None')}")
        
        # Check if source file exists and contains the entity
        source_file = getattr(target_entity, 'source_file_path', None)
        if source_file and os.path.exists(source_file):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(source_file)
                root = tree.getroot()
                
                # Look for the entity in the XML
                found_in_xml = False
                for entity_elem in root.findall(".//object[@type='Entity']"):
                    name_elem = entity_elem.find("./value[@name='hidName']")
                    if name_elem is not None and name_elem.text == entity_name:
                        found_in_xml = True
                        
                        # Check coordinates in XML
                        pos_elem = entity_elem.find("./value[@name='hidPos']")
                        if pos_elem is not None:
                            x_elem = pos_elem.find("./x")
                            y_elem = pos_elem.find("./y")
                            z_elem = pos_elem.find("./z")
                            
                            if all([x_elem is not None, y_elem is not None, z_elem is not None]):
                                xml_pos = (float(x_elem.text), float(y_elem.text), float(z_elem.text))
                                print(f"Found in XML: ({xml_pos[0]:.1f}, {xml_pos[1]:.1f}, {xml_pos[2]:.1f})")
                                
                                # Check if positions match
                                if (abs(xml_pos[0] - target_entity.x) < 0.1 and 
                                    abs(xml_pos[1] - target_entity.y) < 0.1 and 
                                    abs(xml_pos[2] - target_entity.z) < 0.1):
                                    print(f"XML coordinates match entity coordinates")
                                else:
                                    print(f"XML coordinates don't match entity coordinates!")
                        break
                
                if not found_in_xml:
                    print(f"Entity not found in XML file")
                    
            except Exception as e:
                print(f"Error reading XML file: {e}")
        
        # Check corresponding FCB file
        if source_file and source_file.endswith('.converted.xml'):
            fcb_file = source_file.replace('.converted.xml', '')
            if os.path.exists(fcb_file):
                fcb_size = os.path.getsize(fcb_file)
                fcb_mtime = os.path.getmtime(fcb_file)
                print(f"Corresponding FCB: {os.path.basename(fcb_file)} ({fcb_size} bytes)")
                print(f"Ã°Å¸â€œâ€¦ FCB last modified: {fcb_mtime}")
            else:
                print(f"No corresponding FCB file found: {fcb_file}")

    def emergency_restore_worldsectors(self):
        """Emergency method to restore WorldSector files from backups"""
        if not hasattr(self, 'worldsectors_path') or not self.worldsectors_path:
            QMessageBox.warning(self, "No WorldSectors Path", "No worldsectors path is set.")
            return
        
        # Find backup files
        import glob
        backup_pattern = os.path.join(self.worldsectors_path, "*.pre_delete_backup")
        backup_files = glob.glob(backup_pattern)
        
        if not backup_files:
            QMessageBox.information(self, "No Backups Found", "No backup files found to restore.")
            return
        
        reply = QMessageBox.question(
            self,
            "Restore from Backups",
            f"Found {len(backup_files)} backup files.\n\n"
            f"This will restore the original FCB files and may overwrite any changes.\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            restored_count = self.file_converter.restore_from_backups(backup_files)
            QMessageBox.information(
                self,
                "Restore Complete",
                f"Restored {restored_count} files from backups."
            )

    def _convert_worldsector_xml_to_fcb(self):
        """Convert WorldSector .converted.xml files back to .data.fcb format - HANDLES _new.fcb RENAMING"""
        print(f"\nStarting WorldSector XML to FCB conversion, Please wait.")
        
        if not hasattr(self, 'file_converter'):
            print(f"No file converter available")
            return 0
        
        # Find all WorldSector .converted.xml files from entities
        converted_xml_files = set()
        for entity in self.entities:
            if hasattr(entity, 'source_file_path') and entity.source_file_path:
                if entity.source_file_path.endswith('.converted.xml'):
                    converted_xml_files.add(entity.source_file_path)
        
        # Also check worldsectors_trees for any loaded .converted.xml files
        if hasattr(self, 'worldsectors_trees'):
            for file_path in self.worldsectors_trees.keys():
                if file_path.endswith('.converted.xml'):
                    converted_xml_files.add(file_path)
        
        if not converted_xml_files:
            print(f"No WorldSector .converted.xml files found")
            return 0
        
        print(f"Found {len(converted_xml_files)} .converted.xml files to convert to FCB")
        
        converted_count = 0
        failed_files = []
        cleanup_files = []  # Files to clean up after successful conversion
        
        # Convert each .converted.xml file back to .data.fcb
        for xml_file in converted_xml_files:
            try:
                # Determine the original FCB file path
                # worldsector83.data.fcb.converted.xml -> worldsector83.data.fcb
                if xml_file.endswith('.data.fcb.converted.xml'):
                    fcb_file = xml_file.replace('.converted.xml', '')
                else:
                    print(f"Unexpected file format: {xml_file}")
                    failed_files.append(xml_file)
                    continue
                
                print(f"\nConverting: {os.path.basename(xml_file)} Ã¢â€ â€™ {os.path.basename(fcb_file)}")
                
                # Check if XML file exists and has content
                if not os.path.exists(xml_file):
                    print(f"XML file not found: {xml_file}")
                    failed_files.append(xml_file)
                    continue
                    
                xml_size = os.path.getsize(xml_file)
                print(f"  Ã°Å¸â€œÅ  XML file size: {xml_size} bytes")
                
                if xml_size == 0:
                    print(f"XML file is empty")
                    failed_files.append(xml_file)
                    continue
                
                # Remove existing FCB file if it exists
                if os.path.exists(fcb_file):
                    old_fcb_size = os.path.getsize(fcb_file)
                    print(f"  Ã°Å¸â€”â€˜Ã¯Â¸Â Removing old FCB file ({old_fcb_size} bytes)")
                    os.remove(fcb_file)
                
                # Convert using the file converter's method for .converted.xml files
                print(f"  Running conversion, Please wait.")
                success = self.file_converter.convert_converted_xml_back_to_fcb(fcb_file)
                
                # Check conversion result
                if success:
                    if os.path.exists(fcb_file):
                        fcb_size = os.path.getsize(fcb_file)
                        print(f"  Conversion successful!")
                        print(f"  Ã°Å¸â€œÅ  FCB file size: {fcb_size} bytes")
                        converted_count += 1
                        
                        # Mark XML file for cleanup after all conversions are done
                        cleanup_files.append(xml_file)
                        
                        # Update entity source_file_path to point to FCB
                        updated_entities = 0
                        for entity in self.entities:
                            if hasattr(entity, 'source_file_path') and entity.source_file_path == xml_file:
                                entity.source_file_path = fcb_file
                                updated_entities += 1
                        
                        if updated_entities > 0:
                            print(f"  Ã°Å¸â€â€” Updated {updated_entities} entity references")
                            
                    else:
                        print(f"  Conversion reported success but FCB file not created")
                        failed_files.append(xml_file)
                else:
                    print(f"  Conversion failed for: {os.path.basename(xml_file)}")
                    failed_files.append(xml_file)
                    
            except Exception as e:
                print(f"  Error converting {xml_file}: {e}")
                failed_files.append(xml_file)
        
        # Clean up successfully converted XML files
        if cleanup_files:
            print(f"\nÃ°Å¸Â§Â¹ Cleaning up {len(cleanup_files)} successfully converted XML files, Please wait.")
            for xml_file in cleanup_files:
                try:
                    os.remove(xml_file)
                    print(f"  Ã°Å¸â€”â€˜Ã¯Â¸Â Removed: {os.path.basename(xml_file)}")
                except Exception as cleanup_error:
                    print(f"  Could not remove {os.path.basename(xml_file)}: {cleanup_error}")
        
        # Also clean up any leftover _new.fcb files
        worldsectors_path = None
        if cleanup_files:
            worldsectors_path = os.path.dirname(cleanup_files[0])
        elif hasattr(self, 'worldsectors_path'):
            worldsectors_path = self.worldsectors_path
        
        if worldsectors_path:
            print(f"\nÃ°Å¸Â§Â¹ Checking for leftover _new.fcb files, Please wait.")
            try:
                for file in os.listdir(worldsectors_path):
                    if file.endswith('_new.fcb'):
                        leftover_path = os.path.join(worldsectors_path, file)
                        try:
                            os.remove(leftover_path)
                            print(f"  Ã°Å¸â€”â€˜Ã¯Â¸Â Removed leftover: {file}")
                        except Exception as e:
                            print(f"  Could not remove leftover {file}: {e}")
            except Exception as e:
                print(f"  Error checking for leftover files: {e}")
        
        # Clear worldsectors_trees for successfully converted files
        if hasattr(self, 'worldsectors_trees') and cleanup_files:
            trees_to_remove = []
            for file_path in self.worldsectors_trees.keys():
                if file_path in cleanup_files:
                    trees_to_remove.append(file_path)
            
            for file_path in trees_to_remove:
                del self.worldsectors_trees[file_path]
            
            if trees_to_remove:
                print(f"  Ã°Å¸Â§Â¹ Cleared {len(trees_to_remove)} XML trees from memory")
        
        # Summary
        print(f"\nÃ°Å¸â€œÅ  WorldSector conversion summary:")
        print(f"  Successfully converted: {converted_count}/{len(converted_xml_files)} files")
        print(f"  Ã°Å¸Â§Â¹ Cleaned up: {len(cleanup_files)} XML files")
        
        if failed_files:
            print(f"  Failed conversions: {len(failed_files)} files")
            for failed_file in failed_files:
                print(f"    - {os.path.basename(failed_file)}")
        
        return converted_count
    
    def save_worldsectors_changes(self):
        """Save WorldSectors changes and convert back to FCB format"""
        if not hasattr(self, 'worldsectors_trees') or not self.worldsectors_trees:
            QMessageBox.information(self, "No Changes", "No WorldSectors files are loaded.")
            return
        
        try:
            # Step 1: Save all modified .converted.xml files
            print("Step 1: Saving modified .converted.xml files, Please wait.")
            
            modified_files = []
            for xml_file_path, tree in self.worldsectors_trees.items():
                if xml_file_path.endswith('.converted.xml'):
                    try:
                        # Save the XML with current entity positions
                        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                        modified_files.append(xml_file_path)
                        print(f"Saved: {os.path.basename(xml_file_path)}")
                    except Exception as e:
                        print(f"Ã¢Å“â€” Failed to save {xml_file_path}: {e}")
            
            if not modified_files:
                QMessageBox.information(self, "No Changes", "No modified WorldSectors files to save.")
                return
            
            # Step 2: Convert .converted.xml back to .data.fcb
            progress_dialog = QProgressDialog("Converting XML to FCB, Please Wait.", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Saving WorldSectors")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            
            print("Step 2: Converting .converted.xml files back to .data.fcb, Please wait.")
            
            converted_count = 0
            failed_files = []
            
            for i, xml_file in enumerate(modified_files):
                if progress_dialog.wasCanceled():
                    break
                    
                # Get the original FCB path
                # worldsector83.data.fcb.converted.xml -> worldsector83.data.fcb
                if xml_file.endswith('.data.fcb.converted.xml'):
                    fcb_file = xml_file.replace('.converted.xml', '')
                    
                    progress_dialog.setLabelText(f"Converting {os.path.basename(fcb_file)}, Please Wait.")
                    progress_dialog.setValue(int((i / len(modified_files)) * 100))
                    QApplication.processEvents()
                    
                    print(f"Converting: {os.path.basename(xml_file)} -> {os.path.basename(fcb_file)}, Please Wait.")
                    
                    # Use the file converter to convert back to FCB
                    success = self.file_converter.convert_converted_xml_back_to_fcb(fcb_file)
                    
                    if success:
                        converted_count += 1
                        print(f"Converted: {os.path.basename(fcb_file)}")
                        
                        # Update entity source_file_path to point back to FCB
                        for entity in self.entities:
                            if hasattr(entity, 'source_file_path') and entity.source_file_path == xml_file:
                                entity.source_file_path = fcb_file
                                
                    else:
                        failed_files.append(xml_file)
                        print(f"Ã¢Å“â€” Failed to convert: {os.path.basename(xml_file)}")
            
            progress_dialog.setValue(100)
            progress_dialog.close()
            
            # Step 3: Clean up .converted.xml files after successful conversion
            if converted_count > 0:
                print("Step 3: Cleaning up .converted.xml files, Please wait.")
                
                cleanup_files = []
                for xml_file in modified_files:
                    if xml_file not in failed_files:
                        try:
                            os.remove(xml_file)
                            cleanup_files.append(xml_file)
                            print(f"Removed: {os.path.basename(xml_file)}")
                        except Exception as e:
                            print(f"Ã¢Å¡  Could not remove {xml_file}: {e}")
                
                # Clear worldsectors_trees for cleaned up files
                for xml_file in cleanup_files:
                    if xml_file in self.worldsectors_trees:
                        del self.worldsectors_trees[xml_file]
            
            # Step 4: Show results
            if failed_files:
                QMessageBox.warning(
                    self,
                    "Conversion Completed with Errors",
                    f"Successfully converted {converted_count} files to FCB format.\n\n"
                    f"Failed to convert {len(failed_files)} files:\n" +
                    "\n".join([os.path.basename(f) for f in failed_files[:5]]) +
                    (f"\n... and {len(failed_files) - 5} more" if len(failed_files) > 5 else "")
                )
            else:
                QMessageBox.information(
                    self,
                    "WorldSectors Saved Successfully",
                    f"Successfully saved and converted {converted_count} WorldSectors files!\n\n"
                    f"Your changes are now saved in FCB format and will appear in the game."
                )
            
            # Reset modification flags
            if hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified.clear()
            
            self.status_bar.showMessage(f"Saved {converted_count} WorldSectors files to FCB format")
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Failed to save WorldSectors: {str(e)}")

    def _convert_main_xml_to_fcb(self, log_callback=None):
        """Convert main XML files back to FCB format - CORRECTED VERSION with logging"""
        
        def log(message):
            print(message)
            if log_callback:
                try:
                    log_callback(message)
                except:
                    pass
        
        log("\nStarting XML to FCB conversion, Please wait.")
        
        if not hasattr(self, 'file_converter'):
            log("No file converter available")
            return 0
        
        converted_count = 0
        
        # List of main XML files to convert
        main_xml_files = []
        
        # Add main XML file
        if hasattr(self, 'xml_file_path') and self.xml_file_path and os.path.exists(self.xml_file_path):
            main_xml_files.append({
                'xml_path': self.xml_file_path,
                'type': 'mapsdata'
            })
            log(f"  Found main XML: {os.path.basename(self.xml_file_path)}")
        
        # Add other main XML files
        for file_type in ['omnis', 'managers', 'sectorsdep']:
            file_path = self._find_tree_file_path(file_type)
            if file_path and os.path.exists(file_path):
                main_xml_files.append({
                    'xml_path': file_path,
                    'type': file_type
                })
                log(f"  Found {file_type} XML: {os.path.basename(file_path)}")
        
        if not main_xml_files:
            log("No main XML files found to convert")
            return 0
        
        log(f"Found {len(main_xml_files)} XML files to convert to FCB")
        
        # Convert each XML file back to FCB
        for file_info in main_xml_files:
            xml_file = file_info['xml_path']
            file_type = file_info['type']
            
            try:
                fcb_file = xml_file.replace('.xml', '.fcb')
                
                log(f"\nConverting: {os.path.basename(xml_file)} -> {os.path.basename(fcb_file)}")
                
                # Check if XML file exists and has content
                if not os.path.exists(xml_file):
                    log(f"XML file not found: {xml_file}")
                    continue
                    
                xml_size = os.path.getsize(xml_file)
                log(f"  XML file size: {xml_size} bytes")
                
                if xml_size == 0:
                    log("XML file is empty")
                    continue
                
                # Remove existing FCB file if it exists
                if os.path.exists(fcb_file):
                    old_fcb_size = os.path.getsize(fcb_file)
                    log(f"  Removing old FCB file ({old_fcb_size} bytes)")
                    os.remove(fcb_file)
                
                # Use the correct method name from your FileConverter
                log("  Running conversion, Please wait.")
                success = self.file_converter.convert_xml_to_fcb(xml_file)
                
                # Check conversion result
                if success:
                    if os.path.exists(fcb_file):
                        fcb_size = os.path.getsize(fcb_file)
                        log("  Conversion successful!")
                        log(f"  FCB file size: {fcb_size} bytes")
                        converted_count += 1
                        
                        # Remove the temporary XML file after successful conversion
                        try:
                            os.remove(xml_file)
                            log(f"  Cleaned up XML file: {os.path.basename(xml_file)}")
                        except Exception as cleanup_error:
                            log(f"  Could not remove XML file: {cleanup_error}")
                    else:
                        log("  Conversion reported success but FCB file not created")
                else:
                    log(f"  Conversion failed for: {os.path.basename(xml_file)}")
                    
            except Exception as e:
                log(f"  Error converting {xml_file}: {e}")
                import traceback
                traceback.print_exc()
        
        log(f"\nConversion summary: {converted_count}/{len(main_xml_files)} files converted to FCB")
        return converted_count

    def save_worldsector_xml_with_precision_preservation(self, tree, file_path):
        """Save worldsector XML while preserving original formatting and precision"""
        try:
            # Create backup first
            backup_path = file_path + ".precision_backup"
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_path)
            
            # CRITICAL: Don't add XML declaration to match original format
            tree.write(
                file_path, 
                encoding='utf-8', 
                xml_declaration=True  # Changed from True to False
            )
            
            print(f"Saved worldsector XML with precision preservation: {os.path.basename(file_path)}")
            
        except Exception as e:
            print(f"Error saving worldsector XML with precision preservation: {e}")
            raise

    def _convert_all_data_files_to_fcb(self):
        """Convert all data XML files to FCB with verification"""
        import glob
        
        # Find all .data.xml files
        pattern = os.path.join(self.worldsectors_path, "*.data.xml")
        xml_files = glob.glob(pattern)
        
        success_count = 0
        error_count = 0
        
        print(f"Converting {len(xml_files)} data XML files to FCB, Please Wait.")
        
        for xml_file in xml_files:
            try:
                # Get the FCB path
                fcb_file = xml_file.replace('.data.xml', '.data.fcb')
                
                print(f"Converting: {os.path.basename(xml_file)} -> {os.path.basename(fcb_file)}, Please Wait.")
                
                # Check XML file size before conversion
                xml_size = os.path.getsize(xml_file)
                print(f"  XML size: {xml_size} bytes")
                
                # Perform conversion
                if self.file_converter.convert_data_xml_to_fcb(xml_file):
                    # Check if FCB was created
                    if os.path.exists(fcb_file):
                        fcb_size = os.path.getsize(fcb_file)
                        print(f"  FCB size: {fcb_size} bytes")
                        
                        # Remove XML after successful conversion
                        os.remove(xml_file)
                        success_count += 1
                        print(f"Converted and cleaned up: {os.path.basename(xml_file)}")
                    else:
                        error_count += 1
                        print(f"Ã¢Å“â€” FCB file not created: {os.path.basename(fcb_file)}")
                else:
                    error_count += 1
                    print(f"Ã¢Å“â€” Conversion failed: {os.path.basename(xml_file)}")
                    
            except Exception as e:
                error_count += 1
                print(f"Error converting {xml_file}: {e}")
        
        print(f"Data file conversion: {success_count} successful, {error_count} failed")

    def _save_all_main_xml_files(self):
        """Save all main XML files that have been modified"""
        # Save primary XML file
        if hasattr(self, 'xml_tree') and hasattr(self, 'xml_file_path'):
            self.xml_tree.write(self.xml_file_path, encoding='utf-8', xml_declaration=True)
            print(f"Saved main XML: {os.path.basename(self.xml_file_path)}")
        
        # Save other XML files
        file_mappings = {
            'omnis_tree': 'omnis',
            'managers_tree': 'managers', 
            'sectordep_tree': 'sectorsdep'
        }
        
        for tree_attr, file_type in file_mappings.items():
            if hasattr(self, tree_attr):
                tree = getattr(self, tree_attr)
                if tree is not None:
                    file_path = self._find_tree_file_path(file_type)
                    if file_path:
                        tree.write(file_path, encoding='utf-8', xml_declaration=True)
                        print(f"Saved {file_type} XML: {os.path.basename(file_path)}")

    def _convert_main_files_to_fcb(self):
        """Convert main XML files back to FCB format"""
        files_to_convert = []
        
        # Add primary XML file
        if hasattr(self, 'xml_file_path') and self.xml_file_path:
            files_to_convert.append(self.xml_file_path)
        
        # Add other XML files
        for file_type in ['omnis', 'managers', 'sectorsdep']:
            file_path = self._find_tree_file_path(file_type)
            if file_path and os.path.exists(file_path):
                files_to_convert.append(file_path)
        
        # Convert each file
        success_count = 0
        error_count = 0
        
        for xml_file in files_to_convert:
            try:
                fcb_file = xml_file.replace('.xml', '.fcb')
                
                # Remove existing FCB file
                if os.path.exists(fcb_file):
                    os.remove(fcb_file)
                
                # Convert XML to FCB
                if self.file_converter.convert_xml_to_fcb(xml_file):
                    success_count += 1
                    print(f"Converted to FCB: {os.path.basename(fcb_file)}")
                else:
                    error_count += 1
                    print(f"Ã¢Å“â€” Failed to convert: {os.path.basename(xml_file)}")
                    
            except Exception as e:
                error_count += 1
                print(f"Error converting {xml_file}: {e}")
        
        print(f"Main file conversion: {success_count} successful, {error_count} failed")

    def _cleanup_temp_xml_files(self):
        """Remove temporary XML files after successful FCB conversion"""
        files_to_remove = []
        
        # Add main XML files
        if hasattr(self, 'xml_file_path') and self.xml_file_path:
            files_to_remove.append(self.xml_file_path)
        
        for file_type in ['omnis', 'managers', 'sectorsdep']:
            file_path = self._find_tree_file_path(file_type)
            if file_path and os.path.exists(file_path):
                files_to_remove.append(file_path)
        
        # Add modified data XML files
        if hasattr(self, 'worldsectors_modified'):
            for file_path, is_modified in self.worldsectors_modified.items():
                if is_modified:
                    files_to_remove.append(file_path)
        
        # Remove the files
        removed_count = 0
        for xml_file in files_to_remove:
            try:
                if os.path.exists(xml_file):
                    os.remove(xml_file)
                    print(f"Removed temp XML: {os.path.basename(xml_file)}")
                    removed_count += 1
            except Exception as e:
                print(f"Warning: Could not remove {xml_file}: {e}")
        
        print(f"Cleaned up {removed_count} temporary XML files")

    def show_sector_violations_dialog(self, violations):
        """Show dialog with entities that are outside their sector boundaries"""
        if not violations:
            return
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sector Boundary Violations ({len(violations)} found)")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        # Warning message
        warning_label = QLabel("The following entities are outside their sector boundaries.\n"
                            "This may cause crashes or unexpected behavior in the game!")
        warning_label.setStyleSheet("color: orange; font-weight: bold; padding: 10px;")
        layout.addWidget(warning_label)
        
        # List of violations
        violation_list = QListWidget()
        
        for violation in violations:
            entity = violation['entity']
            sector_id = violation['sector_id']
            bounds = violation['sector_bounds']
            pos = violation['entity_pos']
            distance = violation['distance_out']
            
            item_text = (f"{entity.name} (Sector {sector_id})\n"
                        f"Position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})\n"
                        f"Sector bounds: ({bounds[0]}-{bounds[2]}, {bounds[1]}-{bounds[3]})\n"
                        f"Distance outside: {distance:.1f} units")
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, entity)  # Store entity reference
            
            # Color code by severity
            if distance > 50:
                item.setBackground(QColor(255, 200, 200))  # Light red for far outside
            else:
                item.setBackground(QColor(255, 255, 200))  # Light yellow for slightly outside
            
            violation_list.addItem(item)
        
        layout.addWidget(violation_list)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        # Move to entity button
        move_to_button = QPushButton("Zoom to Selected Entity")
        move_to_button.clicked.connect(lambda: self.zoom_to_violation_entity(violation_list))
        button_layout.addWidget(move_to_button)
        
        # Fix entity button (move it back to sector)
        fix_button = QPushButton("Move Entity to Sector Center")
        fix_button.clicked.connect(lambda: self.fix_violation_entity(violation_list, violations))
        button_layout.addWidget(fix_button)
        
        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Show dialog
        dialog.exec()

    def zoom_to_violation_entity(self, violation_list):
        """Zoom to the selected entity in the violations list"""
        current_item = violation_list.currentItem()
        if current_item:
            entity = current_item.data(Qt.ItemDataRole.UserRole)
            if entity:
                # Use existing zoom to entity method
                if hasattr(self, 'zoom_to_entity'):
                    self.zoom_to_entity(entity)
                else:
                    # Fallback zoom
                    self.canvas.selected_entity = entity
                    self.canvas.selected = [entity]
                    if self.canvas.mode == 0:  # 2D mode
                        self.canvas.offset_x = (self.canvas.width() / 2) - (entity.x * self.canvas.scale_factor)
                        self.canvas.offset_y = (self.canvas.height() / 2) - (entity.y * self.canvas.scale_factor)
                    self.canvas.update()

    def fix_violation_entity(self, violation_list, violations):
        """Move the selected entity back to its sector center"""
        current_item = violation_list.currentItem()
        if not current_item:
            return
        
        entity = current_item.data(Qt.ItemDataRole.UserRole)
        if not entity:
            return
        
        # Find the violation info for this entity
        violation_info = None
        for violation in violations:
            if violation['entity'] == entity:
                violation_info = violation
                break
        
        if not violation_info:
            return
        
        # Calculate sector center
        bounds = violation_info['sector_bounds']
        center_x = (bounds[0] + bounds[2]) / 2
        center_y = (bounds[1] + bounds[3]) / 2
        
        # Ask user for confirmation
        reply = QMessageBox.question(
            self,
            "Move Entity",
            f"Move {entity.name} from ({entity.x:.1f}, {entity.y:.1f}) to sector center ({center_x:.1f}, {center_y:.1f})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Move entity
            entity.x = center_x
            entity.y = center_y
            
            # Update XML
            self.canvas.update_entity_xml(entity)
            
            # Update UI
            self.canvas.update()
            self.status_bar.showMessage(f"Moved {entity.name} to sector center")
            
            # Mark as modified
            self.entities_modified = True

    def get_sector_statistics(self):
        """Get statistics about sector usage and violations"""
        if not hasattr(self.canvas, 'sector_data') or not self.canvas.sector_data:
            return None
        
        stats = {
            'total_sectors': len(self.canvas.sector_data),
            'sectors_with_violations': 0,
            'total_violations': 0,
            'violations_by_sector': {}
        }
        
        for sector_info in self.canvas.sector_data:
            sector_id = sector_info['id']
            has_violations = self.canvas.check_sector_violations(sector_info)
            
            if has_violations:
                stats['sectors_with_violations'] += 1
            
            # Count violations in this sector
            sector_violations = 0
            for entity in self.entities:
                entity_source = getattr(entity, 'source_file_path', '')
                if f'worldsector{sector_id}' in entity_source:
                    sector_x = sector_info['x']
                    sector_y = sector_info['y'] 
                    sector_size = sector_info['size']
                    
                    world_min_x = sector_x * sector_size
                    world_min_y = sector_y * sector_size
                    world_max_x = world_min_x + sector_size
                    world_max_y = world_min_y + sector_size
                    
                    if (entity.x < world_min_x or entity.x >= world_max_x or
                        entity.y < world_min_y or entity.y >= world_max_y):
                        sector_violations += 1
            
            if sector_violations > 0:
                stats['violations_by_sector'][sector_id] = sector_violations
                stats['total_violations'] += sector_violations
        
        return stats

    def move_entity_to_sector_manually(self, entity):
        """Move entity to a different sector chosen by user"""
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        
        if not entity:
            QMessageBox.warning(self, "No Entity", "No entity selected to move.")
            return False
        
        # Get current sector info
        current_file = getattr(entity, 'source_file_path', 'Unknown')
        current_sector = "Unknown"
        if current_file:
            import re
            match = re.search(r'worldsector(\d+)', current_file)
            if match:
                current_sector = match.group(1)
        
        print(f"Moving entity: {entity.name}")
        print(f"Current sector: {current_sector}")
        print(f"Current file: {current_file}")
        
        # Get list of available sectors - check multiple sources
        available_sectors = []
        
        # Method 1: Check worldsectors_trees
        if hasattr(self, 'worldsectors_trees') and self.worldsectors_trees:
            for file_path in self.worldsectors_trees.keys():
                import re
                match = re.search(r'worldsector(\d+)', file_path)
                if match:
                    sector_num = match.group(1)
                    available_sectors.append(sector_num)
        
        # Method 2: Check entities for their source files (fallback)
        if not available_sectors and hasattr(self, 'entities'):
            seen_sectors = set()
            for entity in self.entities:
                source_file = getattr(entity, 'source_file_path', None)
                if source_file and 'worldsector' in source_file:
                    import re
                    match = re.search(r'worldsector(\d+)', source_file)
                    if match:
                        sector_num = match.group(1)
                        seen_sectors.add(sector_num)
            available_sectors = list(seen_sectors)
        
        # Method 3: If entity has a source file, try to find other sectors in same directory
        if not available_sectors and current_file and current_file != "Unknown":
            import os
            import glob
            directory = os.path.dirname(current_file)
            if os.path.exists(directory):
                pattern = os.path.join(directory, "worldsector*.converted.xml")
                found_files = glob.glob(pattern)
                for file_path in found_files:
                    import re
                    match = re.search(r'worldsector(\d+)', file_path)
                    if match:
                        sector_num = match.group(1)
                        available_sectors.append(sector_num)
        
        if not available_sectors:
            QMessageBox.warning(
                self, 
                "No Sectors Available", 
                f"No worldsector files found.\n\n"
                f"Current entity file: {current_file}\n"
                f"Worldsectors_trees loaded: {len(self.worldsectors_trees) if hasattr(self, 'worldsectors_trees') else 0}\n"
                f"Please load worldsectors first or check file paths."
            )
            return False
        
        available_sectors.sort(key=int)  # Sort numerically
        
        # Ask user which sector to move to
        sector_choice, ok = QInputDialog.getItem(
            self,
            "Move to Sector",
            f"Move {entity.name} from sector {current_sector} to which sector?",
            available_sectors,
            0,  # Default selection
            False  # Not editable
        )
        
        if not ok:
            return False  # User cancelled
        
        # Find the target file - check multiple sources
        target_file = None
        
        # Method 1: Check in worldsectors_trees
        if hasattr(self, 'worldsectors_trees'):
            for file_path in self.worldsectors_trees.keys():
                if f'worldsector{sector_choice}' in file_path:
                    target_file = file_path
                    break
        
        # Method 2: Construct path based on current entity's file location
        if not target_file and current_file and current_file != "Unknown":
            import os
            directory = os.path.dirname(current_file)
            # Try different naming patterns
            possible_names = [
                f"worldsector{sector_choice}.data.fcb.converted.xml",
                f"worldsector{sector_choice}.converted.xml",
                f"worldsector{sector_choice}.data.xml"
            ]
            
            for name in possible_names:
                potential_path = os.path.join(directory, name)
                if os.path.exists(potential_path):
                    target_file = potential_path
                    
                    # Load it into worldsectors_trees if not already loaded
                    if not hasattr(self, 'worldsectors_trees'):
                        self.worldsectors_trees = {}
                    
                    if target_file not in self.worldsectors_trees:
                        try:
                            import xml.etree.ElementTree as ET
                            tree = ET.parse(target_file)
                            self.worldsectors_trees[target_file] = tree
                            print(f"Loaded {target_file} for sector move")
                        except Exception as e:
                            print(f"Error loading {target_file}: {e}")
                            continue
                    break
        
        if not target_file:
            QMessageBox.critical(
                self,
                "Sector Not Found", 
                f"Could not find worldsector{sector_choice} file.\n\n"
                f"Looked for file in directory: {os.path.dirname(current_file) if current_file != 'Unknown' else 'Unknown'}"
            )
            return False
        
        if target_file == current_file:
            QMessageBox.information(
                self,
                "Same Sector",
                f"Entity {entity.name} is already in sector {sector_choice}."
            )
            return False
        
        # Confirm the move
        reply = QMessageBox.question(
            self,
            "Confirm Move",
            f"Move {entity.name} from sector {current_sector} to sector {sector_choice}?\n\n"
            f"This will remove it from:\n{current_file}\n\n"
            f"And add it to:\n{target_file}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return False
        
        # Perform the move
        return self.execute_sector_move(entity, current_file, target_file, sector_choice)

    def show_entity_export_dialog(self):
        """Show the entity export dialog"""
        try:
            from entity_export_import import show_entity_export_dialog
            show_entity_export_dialog(self)
        except Exception as e:
            print(f"Error showing entity export dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to open entity export dialog:\n{str(e)}")

    def show_entity_import_dialog(self):
        """Show the entity import dialog"""
        try:
            from entity_export_import import show_entity_import_dialog
            show_entity_import_dialog(self)
        except Exception as e:
            print(f"Error showing entity import dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to open entity import dialog:\n{str(e)}")

    def debug_export_import_system(self):
        """Debug the export/import system setup"""
        print("\n=== EXPORT/IMPORT SYSTEM DEBUG ===")
        
        # Check if system is setup
        has_clipboard = hasattr(self, 'entity_clipboard')
        print(f"Has entity_clipboard: {has_clipboard}")
        
        if has_clipboard:
            print(f"Clipboard has data: {self.entity_clipboard.has_clipboard_data()}")
        
        # Check objects folder
        objects_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "objects")
        print(f"Objects folder: {objects_folder}")
        print(f"Objects folder exists: {os.path.exists(objects_folder)}")
        
        if os.path.exists(objects_folder):
            collections = [d for d in os.listdir(objects_folder) 
                        if os.path.isdir(os.path.join(objects_folder, d))]
            print(f"Collections found: {len(collections)}")
            for collection in collections[:5]:
                collection_path = os.path.join(objects_folder, collection)
                xml_files = [f for f in os.listdir(collection_path) if f.endswith('.xml')]
                print(f"  - {collection} ({len(xml_files)} XML files)")
        
        # Check worldsectors
        has_worldsectors = hasattr(self, 'worldsectors_trees') and self.worldsectors_trees
        print(f"Has worldsectors loaded: {has_worldsectors}")
        
        if has_worldsectors:
            print(f"Worldsector files: {len(self.worldsectors_trees)}")
            for i, path in enumerate(list(self.worldsectors_trees.keys())[:5]):
                tree = self.worldsectors_trees[path]
                root = tree.getroot()
                entities = root.findall(".//object[@name='Entity']")
                print(f"  {i+1}. {os.path.basename(path)} ({len(entities)} entities)")
        
        # Check selected entities
        selected_count = 0
        if hasattr(self, 'canvas') and hasattr(self.canvas, 'selected'):
            selected_count = len(self.canvas.selected)
        print(f"Selected entities: {selected_count}")
        
        # Check total entities
        total_entities = len(self.entities) if hasattr(self, 'entities') else 0
        print(f"Total entities loaded: {total_entities}")
        
        print("=== END DEBUG ===\n")

    def _add_entity_to_worldsector(self, entity):
        """Add entity to worldsector XML with smart sector assignment"""
        print(f"Smart worldsector assignment for: {entity.name}")
        
        # Find the best target worldsector file
        target_file = self._find_target_worldsector_file(entity)
        
        if not target_file:
            print("No suitable worldsector file found")
            return False
        
        # Update entity's source file path to the target sector
        old_source = getattr(entity, 'source_file_path', 'none')
        entity.source_file_path = target_file
        
        if old_source != target_file:
            print(f"Reassigned entity from {old_source} Ã¢â€ â€™ {target_file}")
        
        # Load XML file on-demand if not already loaded
        if target_file not in self.worldsectors_trees:
            print(f"Loading target XML file: {target_file}")
            try:
                import xml.etree.ElementTree as ET
                import os
                
                if not os.path.exists(target_file):
                    print(f"Target XML file does not exist: {target_file}")
                    return False
                
                # Load the XML tree
                tree = ET.parse(target_file)
                self.worldsectors_trees[target_file] = tree
                print(f"Loaded XML tree for {target_file}")
                
            except Exception as e:
                print(f"Error loading XML file {target_file}: {e}")
                return False
        
        try:
            print(f"Adding entity to target sector: {target_file}")
            tree = self.worldsectors_trees[target_file]
            root = tree.getroot()
            
            # Find ALL MissionLayers - use the first one for adding
            mission_layers = root.findall(".//object[@name='MissionLayer']")
            if not mission_layers:
                print("No MissionLayer found in target XML")
                return False
            
            # Use the first MissionLayer for adding
            mission_layer = mission_layers[0]
            print(f"Using MissionLayer 1 (of {len(mission_layers)}) for adding")
                
            # Count existing entities
            existing_entities = mission_layer.findall("object[@name='Entity']")
            print(f"Target sector has {len(existing_entities)} existing entities")
            
            # Create a clean copy of the entity XML
            import xml.etree.ElementTree as ET
            xml_string = ET.tostring(entity.xml_element, encoding='unicode')
            fresh_element = ET.fromstring(xml_string)
            
            # Add to MissionLayer
            mission_layer.append(fresh_element)
            
            # Verify addition
            new_entity_count = len(mission_layer.findall("object[@name='Entity']"))
            if new_entity_count > len(existing_entities):
                print(f"Successfully added {entity.name} to {target_file}")
                
                # Update entity reference
                entity.xml_element = fresh_element
                
                # Save the XML file immediately
                tree.write(target_file, encoding='utf-8', xml_declaration=True)
                print(f"Ã°Å¸â€™Â¾ Saved XML file with new entity")
                
                # Mark file as modified
                if not hasattr(self, 'worldsectors_modified'):
                    self.worldsectors_modified = {}
                self.worldsectors_modified[target_file] = True
                
                return True
            else:
                print(f"Entity addition verification failed")
                return False
                
        except Exception as e:
            print(f"Exception in smart worldsector assignment: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_target_worldsector_file(self, entity):
        """Find the best worldsector file for an entity using smart assignment"""
        x, y = entity.x, entity.y
        print(f"Ã°Å¸Å½Â¯ Finding target worldsector for {entity.name} at ({x}, {y})")
        
        # Initialize worldsectors_trees if needed
        if not hasattr(self, 'worldsectors_trees'):
            self.worldsectors_trees = {}
        
        # Get all available worldsector files
        available_files = list(self.worldsectors_trees.keys()) if self.worldsectors_trees else []
        print(f"Ã°Å¸â€”â€šÃ¯Â¸Â  Available worldsector files: {len(available_files)}")
        
        if not available_files:
            print("No worldsector files loaded - cannot assign sector")
            return None
        
        # Strategy: Use the first available file for now (you can enhance this logic later)
        fallback_file = available_files[0]
        print(f" Using fallback sector: {fallback_file}")
        return fallback_file

    def _calculate_worldsector_from_position(self, x, y):
        """Calculate which worldsector an entity should belong to based on position"""
        try:
            # Check if we have grid configuration
            if hasattr(self, 'grid_config') and self.grid_config:
                # Use existing grid configuration if available
                sector_size = getattr(self.grid_config, 'sector_size', 512)
                offset_x = getattr(self.grid_config, 'offset_x', 0)
                offset_y = getattr(self.grid_config, 'offset_y', 0)
            else:
                # Default grid configuration (common Avatar game values)
                sector_size = 512  # Each sector is typically 512x512 units
                offset_x = 0
                offset_y = 0
            
            # Calculate sector coordinates
            sector_x = int((x - offset_x) // sector_size)
            sector_y = int((y - offset_y) // sector_size)
            
            # Calculate sector ID (this may need adjustment based on your game's numbering)
            # Common patterns: sector_id = sector_y * max_sectors_x + sector_x
            # For now, using a simple formula - may need refinement
            sector_id = sector_y * 10 + sector_x  # Assuming 10x10 grid max
            
            # Ensure sector_id is positive and reasonable
            if sector_id < 0:
                sector_id = 0
            if sector_id > 99:  # Reasonable upper limit
                sector_id = 99
                
            print(f"Ã°Å¸Â§Â® Position ({x}, {y}) Ã¢â€ â€™ Sector X:{sector_x}, Y:{sector_y} Ã¢â€ â€™ ID:{sector_id}")
            return sector_id
            
        except Exception as e:
            print(f"Error calculating sector from position: {e}")
            return None

    def toggle_sector_boundaries(self):
        """Toggle sector boundary visibility - FIXED VERSION"""
        try:
            # Ensure canvas has the required attributes
            if not hasattr(self.canvas, 'show_sector_boundaries'):
                self.canvas.show_sector_boundaries = False
            
            if not hasattr(self.canvas, 'sector_data'):
                self.canvas.sector_data = []
            
            # Toggle the visibility
            self.canvas.show_sector_boundaries = not self.canvas.show_sector_boundaries
            
            print(f"Toggling sector boundaries: {self.canvas.show_sector_boundaries}")
            
            # Load sector data if needed and showing
            if self.canvas.show_sector_boundaries:
                if not self.canvas.sector_data:
                    print("Loading sector data, Please wait.")
                    success = self.load_sector_data_for_canvas()
                    if not success:
                        print("Failed to load sector data")
                        self.canvas.show_sector_boundaries = False
                        return
                
                # Force sector boundary display
                print("Sector boundaries enabled")
                self.canvas.force_enable_sector_boundaries()
            else:
                print("Sector boundaries disabled")
            
            # Update canvas
            self.canvas.update()
            
            # Update status
            visibility = "visible" if self.canvas.show_sector_boundaries else "hidden"
            self.status_bar.showMessage(f"Sector boundaries: {visibility}")
            
            # Check for violations if showing
            if self.canvas.show_sector_boundaries:
                try:
                    violations = self.canvas.get_entity_violations()
                    if violations:
                        print(f"Found {len(violations)} sector violations")
                        self.show_sector_violations_dialog(violations)
                except Exception as e:
                    print(f"Warning: Could not check violations: {e}")
            
        except Exception as e:
            print(f"Error toggling sector boundaries: {e}")
            import traceback
            traceback.print_exc()

    def load_sector_data_for_canvas(self):
        """Load sector data for the canvas from entities - ENHANCED to include landmarks"""
        try:
            print("Loading sector data from entities and landmarks...")
            
            if not hasattr(self, 'entities') or not self.entities:
                print("No entities available for sector data")
                return False
            
            # Check if canvas has the method
            if hasattr(self.canvas, 'load_sector_data_from_entities'):
                self.canvas.load_sector_data_from_entities()
                
                # ENHANCEMENT: Also add landmark sectors
                self._add_landmark_sectors_to_data()
                
                return len(self.canvas.sector_data) > 0
            else:
                # Fallback: create basic sector data from worldsector entities
                print("Canvas missing load_sector_data_from_entities, using enhanced fallback")
                return self.create_enhanced_sector_data()
                
        except Exception as e:
            print(f"Error loading sector data: {e}")
            return False

    def _add_landmark_sectors_to_data(self):
        """Add landmark file sectors to sector_data"""
        try:
            if not hasattr(self, 'worldsectors_path') or not self.worldsectors_path:
                return
            
            import glob
            import re
            
            # Find all landmark files
            landmark_pattern = os.path.join(self.worldsectors_path, "landmarkfar*.data.fcb.converted.xml")
            landmark_files = glob.glob(landmark_pattern)
            
            if not landmark_files:
                print("No landmark files found")
                return
            
            print(f"Found {len(landmark_files)} landmark files")
            
            for landmark_file in landmark_files:
                try:
                    # Extract landmark ID from filename
                    # Example: landmarkfar10.data.fcb.converted.xml -> 10
                    match = re.search(r'landmarkfar(\d+)', os.path.basename(landmark_file))
                    if not match:
                        continue
                    
                    landmark_id = int(match.group(1))
                    
                    # Load the landmark XML to get sector position
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(landmark_file)
                    root = tree.getroot()
                    
                    # Find WorldSector element
                    sector_x = None
                    sector_y = None
                    
                    x_elem = root.find(".//field[@name='X']")
                    if x_elem is not None:
                        sector_x = int(x_elem.get('value-Int32', 0))
                    
                    y_elem = root.find(".//field[@name='Y']")
                    if y_elem is not None:
                        sector_y = int(y_elem.get('value-Int32', 0))
                    
                    if sector_x is None or sector_y is None:
                        print(f"Could not get sector position from {os.path.basename(landmark_file)}")
                        continue
                    
                    # Count entities in this landmark
                    entities_in_landmark = []
                    for entity in self.entities:
                        source_file = getattr(entity, 'source_file_path', '')
                        if f'landmarkfar{landmark_id}' in source_file:
                            entities_in_landmark.append(entity)
                    
                    # Create sector info for this landmark
                    sector_info = {
                        'id': f"LM{landmark_id}",  # Mark as landmark
                        'x': sector_x,
                        'y': sector_y,
                        'size': 64,
                        'file_path': landmark_file,
                        'entities': entities_in_landmark,
                        'entity_count': len(entities_in_landmark),
                        'is_landmark': True
                    }
                    
                    # Add to sector_data if not already present
                    if hasattr(self.canvas, 'sector_data'):
                        # Check if this sector position already exists
                        exists = False
                        for existing_sector in self.canvas.sector_data:
                            if (existing_sector.get('x') == sector_x and 
                                existing_sector.get('y') == sector_y):
                                exists = True
                                # Merge entities
                                existing_sector['entities'].extend(entities_in_landmark)
                                existing_sector['entity_count'] += len(entities_in_landmark)
                                print(f"Merged landmark {landmark_id} into existing sector at ({sector_x}, {sector_y})")
                                break
                        
                        if not exists:
                            self.canvas.sector_data.append(sector_info)
                            print(f"Added landmark {landmark_id} as sector at ({sector_x}, {sector_y}) with {len(entities_in_landmark)} entities")
                    
                except Exception as e:
                    print(f"Error processing landmark file {os.path.basename(landmark_file)}: {e}")
            
            print(f"Total sectors after adding landmarks: {len(self.canvas.sector_data)}")
            
        except Exception as e:
            print(f"Error adding landmark sectors: {e}")
            import traceback
            traceback.print_exc()

    def create_enhanced_sector_data(self):
        """Create enhanced sector data including landmarks"""
        try:
            sector_files = {}
            
            # Group entities by worldsector AND landmark files
            for entity in self.entities:
                source_file = getattr(entity, 'source_file_path', '')
                if source_file and ('worldsector' in source_file.lower() or 'landmarkfar' in source_file.lower()):
                    if source_file not in sector_files:
                        sector_files[source_file] = []
                    sector_files[source_file].append(entity)
            
            if not sector_files:
                print("No worldsector or landmark entities found")
                return False
            
            # Create sector data
            self.canvas.sector_data = []
            for source_file, entities in sector_files.items():
                # Extract sector number or landmark ID
                import re
                
                # Check if it's a landmark file
                is_landmark = 'landmarkfar' in source_file.lower()
                
                if is_landmark:
                    match = re.search(r'landmarkfar(\d+)', source_file.lower())
                    sector_id = f"LM{match.group(1)}" if match else "LM?"
                else:
                    match = re.search(r'worldsector(\d+)', source_file.lower())
                    sector_id = int(match.group(1)) if match else 0
                
                # Calculate sector bounds from entities
                if entities:
                    min_x = min(e.x for e in entities)
                    max_x = max(e.x for e in entities)
                    min_y = min(e.y for e in entities)
                    max_y = max(e.y for e in entities)
                    
                    # Estimate sector grid position (64-unit sectors)
                    center_x = (min_x + max_x) / 2
                    center_y = (min_y + max_y) / 2
                    sector_x = int(center_x // 64)
                    sector_y = int(center_y // 64)
                    
                    sector_info = {
                        'id': sector_id,
                        'x': sector_x,
                        'y': sector_y,
                        'size': 64,
                        'file_path': source_file,
                        'entities': entities,
                        'entity_count': len(entities),
                        'is_landmark': is_landmark
                    }
                    
                    self.canvas.sector_data.append(sector_info)
                    print(f"Added {'landmark' if is_landmark else 'sector'} {sector_id} with {len(entities)} entities")
            
            print(f"Created enhanced sector data: {len(self.canvas.sector_data)} sectors (including landmarks)")
            return len(self.canvas.sector_data) > 0
            
        except Exception as e:
            print(f"Error creating enhanced sector data: {e}")
            return False

    def create_fallback_sector_data(self):
        """Create basic sector data as fallback"""
        try:
            sector_files = {}
            
            # Group entities by worldsector file
            for entity in self.entities:
                source_file = getattr(entity, 'source_file_path', '')
                if source_file and 'worldsector' in source_file.lower():
                    if source_file not in sector_files:
                        sector_files[source_file] = []
                    sector_files[source_file].append(entity)
            
            if not sector_files:
                print("No worldsector entities found")
                return False
            
            # Create sector data
            self.canvas.sector_data = []
            for source_file, entities in sector_files.items():
                # Extract sector number
                import re
                match = re.search(r'worldsector(\d+)', source_file.lower())
                if match:
                    sector_id = int(match.group(1))
                    
                    # Calculate sector bounds from entities
                    if entities:
                        min_x = min(e.x for e in entities)
                        max_x = max(e.x for e in entities)
                        min_y = min(e.y for e in entities)
                        max_y = max(e.y for e in entities)
                        
                        # Estimate sector grid position (64-unit sectors)
                        center_x = (min_x + max_x) / 2
                        center_y = (min_y + max_y) / 2
                        sector_x = int(center_x // 64)
                        sector_y = int(center_y // 64)
                        
                        sector_info = {
                            'id': sector_id,
                            'x': sector_x,
                            'y': sector_y,
                            'size': 64,
                            'file_path': source_file,
                            'entities': entities,
                            'entity_count': len(entities)
                        }
                        
                        self.canvas.sector_data.append(sector_info)
                        print(f"Added sector {sector_id} with {len(entities)} entities")
            
            print(f"Created fallback sector data: {len(self.canvas.sector_data)} sectors")
            return len(self.canvas.sector_data) > 0
            
        except Exception as e:
            print(f"Error creating fallback sector data: {e}")
            return False

    def setup_sector_boundary_ui(self):
        """Add sector boundary controls to the existing UI - ENHANCED"""
        try:
            # Initialize canvas properties
            if not hasattr(self.canvas, 'show_sector_boundaries'):
                self.canvas.show_sector_boundaries = False
            if not hasattr(self.canvas, 'sector_data'):
                self.canvas.sector_data = []
            
            # Add toggle button to view menu
            self.toggle_sector_boundaries_action = QAction("Show Sector Boundaries", self)
            self.toggle_sector_boundaries_action.setCheckable(True)
            self.toggle_sector_boundaries_action.setChecked(False)
            self.toggle_sector_boundaries_action.triggered.connect(self.toggle_sector_boundaries)
            
            # Add to view menu (if it exists)
            if hasattr(self, 'menuBar'):
                for action in self.menuBar().actions():
                    if action.text() == "View":
                        view_menu = action.menu()
                        if view_menu:
                            view_menu.addSeparator()
                            view_menu.addAction(self.toggle_sector_boundaries_action)
                        break
            
            print("Sector boundary UI setup complete")
            
        except Exception as e:
            print(f"Error setting up sector boundary UI: {e}")

    def check_all_violations(self):
        """Check for sector violations and show results"""
        try:
            # Ensure sector data is loaded
            if not hasattr(self.canvas, 'sector_data') or not self.canvas.sector_data:
                print("Loading sector data for violation check, Please wait.")
                success = self.load_sector_data_for_canvas()
                if not success:
                    QMessageBox.warning(
                        self,
                        "No Sector Data",
                        "Could not load sector data to check for violations.\n\n"
                        "Make sure worldsector entities are loaded."
                    )
                    return
            
            # Get violations
            if hasattr(self.canvas, 'get_entity_violations'):
                violations = self.canvas.get_entity_violations()
            else:
                violations = self.get_entity_violations_fallback()
            
            if violations:
                self.show_sector_violations_dialog(violations)
            else:
                QMessageBox.information(
                    self,
                    "No Violations Found",
                    "All entities are within their sector boundaries! Ã¢Å“â€¦"
                )
                
        except Exception as e:
            print(f"Error checking violations: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Error checking sector violations:\n{str(e)}"
            )

    def get_entity_violations_fallback(self):
        """Fallback method to check entity violations"""
        violations = []
        
        try:
            if not hasattr(self.canvas, 'sector_data') or not self.canvas.sector_data:
                return violations
            
            for sector_info in self.canvas.sector_data:
                sector_id = sector_info.get('id', 0)
                sector_x = sector_info.get('x', 0)
                sector_y = sector_info.get('y', 0)
                sector_size = sector_info.get('size', 64)
                
                # Calculate sector boundaries
                world_min_x = sector_x * sector_size
                world_min_y = sector_y * sector_size
                world_max_x = world_min_x + sector_size
                world_max_y = world_min_y + sector_size
                
                # Check entities from this sector
                for entity in self.entities:
                    entity_source = getattr(entity, 'source_file_path', '')
                    if f'worldsector{sector_id}' not in entity_source:
                        continue
                    
                    # Check if outside boundaries
                    if (entity.x < world_min_x or entity.x >= world_max_x or
                        entity.y < world_min_y or entity.y >= world_max_y):
                        
                        distance_out = max(
                            max(world_min_x - entity.x, 0),
                            max(entity.x - world_max_x, 0),
                            max(world_min_y - entity.y, 0),
                            max(entity.y - world_max_y, 0)
                        )
                        
                        violations.append({
                            'entity': entity,
                            'sector_id': sector_id,
                            'sector_bounds': (world_min_x, world_min_y, world_max_x, world_max_y),
                            'entity_pos': (entity.x, entity.y, entity.z),
                            'distance_out': distance_out
                        })
            
        except Exception as e:
            print(f"Error in fallback violation check: {e}")
        
        return violations

    # Test method you can call from a menu or button
    def test_sector_boundaries(self):
        """Test method to debug sector boundary display"""
        print("\nTESTING SECTOR BOUNDARIES")
        
        # Step 1: Check canvas attributes
        print(f"Canvas has show_sector_boundaries: {hasattr(self.canvas, 'show_sector_boundaries')}")
        print(f"Canvas has sector_data: {hasattr(self.canvas, 'sector_data')}")
        
        # Step 2: Initialize if needed
        if not hasattr(self.canvas, 'show_sector_boundaries'):
            self.canvas.show_sector_boundaries = False
            print("Initialized show_sector_boundaries")
        
        if not hasattr(self.canvas, 'sector_data'):
            self.canvas.sector_data = []
            print("Initialized sector_data")
        
        # Step 3: Load sector data
        print("Loading sector data, Please wait.")
        success = self.load_sector_data_for_canvas()
        print(f"Sector data loaded: {success}")
        
        if hasattr(self.canvas, 'sector_data'):
            print(f"Sector data count: {len(self.canvas.sector_data)}")
            for i, sector in enumerate(self.canvas.sector_data[:3]):  # Show first 3
                print(f"  Sector {i}: {sector}")
        
        # Step 4: Enable and test
        print("Enabling sector boundaries, Please wait.")
        self.canvas.show_sector_boundaries = True
        
        # Step 5: Force update
        print("Forcing canvas update, Please wait.")
        self.canvas.update()
        
        print("Test complete!")

    def _remove_entity_from_worldsector_fixed(self, entity):
        """Remove entity from its worldsector XML file - FIXED for FCBConverter format and multiple MissionLayers"""
        try:
            source_file = entity.source_file_path
            print(f"\nRemoving {entity.name} from {os.path.basename(source_file)}")
            
            # Auto-load source file if not already loaded
            if not hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees = {}
            
            if source_file not in self.worldsectors_trees:
                if os.path.exists(source_file):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(source_file)
                        self.worldsectors_trees[source_file] = tree
                        print(f"Auto-loaded source file: {os.path.basename(source_file)}")
                    except Exception as e:
                        print(f"Error loading source file {source_file}: {e}")
                        return False
                else:
                    print(f"Source file does not exist: {source_file}")
                    return False
            
            tree = self.worldsectors_trees[source_file]
            root = tree.getroot()
            
            # Find ALL MissionLayers - there can be multiple in worldsector files
            mission_layers = root.findall(".//object[@name='MissionLayer']")
            if not mission_layers:
                print(f"No MissionLayer found in {source_file}")
                return False
            
            print(f"Found {len(mission_layers)} MissionLayer(s) in file")
            
            entity_to_remove = None
            source_mission_layer = None
            
            # Search through ALL MissionLayers
            for layer_idx, mission_layer in enumerate(mission_layers):
                print(f"\nChecking MissionLayer {layer_idx + 1}/{len(mission_layers)}")
                
                # Look for entities directly under this MissionLayer
                entities_in_layer = mission_layer.findall("object[@name='Entity']")
                print(f"Found {len(entities_in_layer)} Entity objects in this MissionLayer")
                
                # Search through entities in FCBConverter format
                for i, entity_elem in enumerate(entities_in_layer):
                    # Look for hidName field (FCBConverter format)
                    name_field = entity_elem.find("field[@name='hidName']")
                    if name_field is not None:
                        stored_name = name_field.get('value-String')
                        print(f"   Checking: '{stored_name}' vs '{entity.name}'")
                        
                        if stored_name == entity.name:
                            print(f"FOUND MATCH: {entity.name} in MissionLayer {layer_idx + 1}")
                            entity_to_remove = entity_elem
                            source_mission_layer = mission_layer
                            break
                
                # If found, break out of layer loop
                if entity_to_remove is not None:
                    break
                
                # If not found in FCBConverter format, try Dunia Tools format
                for entity_elem in entities_in_layer:
                    name_elem = entity_elem.find("./value[@name='hidName']")
                    if name_elem is not None and name_elem.text == entity.name:
                        print(f"Found {entity.name} in Dunia Tools format in MissionLayer {layer_idx + 1}")
                        entity_to_remove = entity_elem
                        source_mission_layer = mission_layer
                        break
                
                # If found, break out of layer loop
                if entity_to_remove is not None:
                    break
            
            if entity_to_remove is None:
                print(f"Entity {entity.name} not found in any MissionLayer")
                return False
            
            # Remove the entity from the correct MissionLayer
            print(f"Ã°Å¸â€”â€˜Ã¯Â¸Â Removing entity from MissionLayer")
            source_mission_layer.remove(entity_to_remove)
            
            # Verify removal
            all_entities_after = []
            for ml in mission_layers:
                all_entities_after.extend(ml.findall("object[@name='Entity']"))
            print(f"Entity removed. All MissionLayers now have {len(all_entities_after)} total entities")
            
            # Save immediately
            tree.write(source_file, encoding='utf-8', xml_declaration=True)
            print(f"Ã°Å¸â€™Â¾ Saved {os.path.basename(source_file)}")
            
            # Mark file as modified
            if not hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified = {}
            self.worldsectors_modified[source_file] = True
            
            return True
            
        except Exception as e:
            print(f"Error removing entity: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def remove_entity_from_sector(self, entity, source_file):
        """Remove entity from its current sector XML file - FIXED for FCBConverter format"""
        try:
            print(f"\nRemoving {entity.name} from {os.path.basename(source_file)}")
            
            # Auto-load source file if not already loaded
            if not hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees = {}
            
            if source_file not in self.worldsectors_trees:
                if os.path.exists(source_file):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(source_file)
                        self.worldsectors_trees[source_file] = tree
                        print(f"Auto-loaded source file: {os.path.basename(source_file)}")
                    except Exception as e:
                        print(f"Error loading source file {source_file}: {e}")
                        return False
                else:
                    print(f"Source file does not exist: {source_file}")
                    return False
            
            tree = self.worldsectors_trees[source_file]
            root = tree.getroot()
            
            # Find ALL MissionLayers - there can be multiple in worldsector files
            mission_layers = root.findall(".//object[@name='MissionLayer']")
            if not mission_layers:
                print(f"No MissionLayer found in {source_file}")
                return False
            
            print(f"Found {len(mission_layers)} MissionLayer(s) in file")
            
            entity_to_remove = None
            source_mission_layer = None
            
            # Search through ALL MissionLayers
            for layer_idx, mission_layer in enumerate(mission_layers):
                print(f"\nChecking MissionLayer {layer_idx + 1}/{len(mission_layers)}")
                print(f"This MissionLayer has {len(mission_layer)} children")
                
                # Look for entities directly under this MissionLayer
                entities_in_layer = mission_layer.findall("object[@name='Entity']")
                print(f"Found {len(entities_in_layer)} Entity objects in this MissionLayer")
                
                # Search through entities in FCBConverter format
                for i, entity_elem in enumerate(entities_in_layer):
                    print(f"Checking entity {i+1}/{len(entities_in_layer)}")
                    
                    # Look for hidName field (FCBConverter format)
                    name_field = entity_elem.find("field[@name='hidName']")
                    if name_field is not None:
                        stored_name = name_field.get('value-String')
                        print(f"   Name in XML: '{stored_name}'")
                        print(f"   Looking for: '{entity.name}'")
                        
                        if stored_name == entity.name:
                            print(f"FOUND MATCH: {entity.name} in MissionLayer {layer_idx + 1}")
                            entity_to_remove = entity_elem
                            source_mission_layer = mission_layer
                            break
                        else:
                            print(f"No match")
                    else:
                        print(f"   No hidName field found")
                
                # If found, break out of layer loop
                if entity_to_remove is not None:
                    break
                
                # If not found in FCBConverter format in this layer, try Dunia Tools format as fallback
                print(f"Trying Dunia Tools format in MissionLayer {layer_idx + 1}, Please wait.")
                for entity_elem in entities_in_layer:
                    name_elem = entity_elem.find("./value[@name='hidName']")
                    if name_elem is not None and name_elem.text == entity.name:
                        print(f"Found {entity.name} in Dunia Tools format in MissionLayer {layer_idx + 1}")
                        entity_to_remove = entity_elem
                        source_mission_layer = mission_layer
                        break
                
                # If found, break out of layer loop
                if entity_to_remove is not None:
                    break
                
                # Debug: Show all entity names in this layer
                if entities_in_layer:
                    print(f"All entities in MissionLayer {layer_idx + 1}:")
                    for i, entity_elem in enumerate(entities_in_layer):
                        name_field = entity_elem.find("field[@name='hidName']")
                        if name_field is not None:
                            stored_name = name_field.get('value-String')
                            print(f"   {i+1}: {stored_name}")
                        else:
                            name_elem = entity_elem.find("./value[@name='hidName']")
                            if name_elem is not None:
                                print(f"   {i+1}: {name_elem.text} (Dunia format)")
                            else:
                                print(f"   {i+1}: [No name field]")
            
            if entity_to_remove is None:
                print(f"Entity {entity.name} not found in any MissionLayer")
                return False
            
            # Remove the entity from the correct MissionLayer
            print(f"Ã°Å¸â€”â€˜Ã¯Â¸Â Removing entity from MissionLayer")
            source_mission_layer.remove(entity_to_remove)
            
            # Verify removal
            all_entities_after = []
            for ml in mission_layers:
                all_entities_after.extend(ml.findall("object[@name='Entity']"))
            print(f"Entity removed. All MissionLayers now have {len(all_entities_after)} total entities")
            
            # Save immediately
            tree.write(source_file, encoding='utf-8', xml_declaration=True)
            print(f"Ã°Å¸â€™Â¾ Saved {os.path.basename(source_file)}")
            
            return True
            
        except Exception as e:
            print(f"Error removing entity: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_entity_to_sector(self, entity, target_file):
        """Add entity to target sector XML file - FIXED for FCBConverter format"""
        try:
            print(f"\nAdding {entity.name} to {os.path.basename(target_file)}")
            
            # Auto-load target file if not already loaded
            if not hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees = {}
            
            if target_file not in self.worldsectors_trees:
                if os.path.exists(target_file):
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(target_file)
                        self.worldsectors_trees[target_file] = tree
                        print(f"Auto-loaded target file: {os.path.basename(target_file)}")
                    except Exception as e:
                        print(f"Error loading target file {target_file}: {e}")
                        return False
                else:
                    print(f"Target file does not exist: {target_file}")
                    return False
            
            tree = self.worldsectors_trees[target_file]
            root = tree.getroot()
            
            # Find ALL MissionLayers - there can be multiple in worldsector files
            mission_layers = root.findall(".//object[@name='MissionLayer']")
            if not mission_layers:
                print(f"No MissionLayer found in {target_file}")
                return False
            
            print(f"Found {len(mission_layers)} MissionLayer(s) in target file")
            
            # For adding, we'll use the first MissionLayer (most common case)
            # In the future, you could add logic to let the user choose which layer
            mission_layer = mission_layers[0]
            print(f"Using MissionLayer 1 for adding entity")
            
            # Count existing entities in the target MissionLayer
            existing_entities = mission_layer.findall("object[@name='Entity']")
            print(f"Target MissionLayer has {len(existing_entities)} existing entities")
            
            # Create a completely fresh copy of the entity XML element
            import xml.etree.ElementTree as ET
            
            if hasattr(entity, 'xml_element') and entity.xml_element is not None:
                # Create a deep copy of the existing XML element
                xml_string = ET.tostring(entity.xml_element, encoding='unicode')
                fresh_element = ET.fromstring(xml_string)
                print(f"Created fresh XML element from existing element")
            else:
                print(f"Entity has no xml_element - cannot proceed")
                return False
            
            # Add to MissionLayer
            mission_layer.append(fresh_element)
            
            # Verify addition
            new_entities = mission_layer.findall("object[@name='Entity']")
            if len(new_entities) > len(existing_entities):
                print(f"Successfully added {entity.name} to {os.path.basename(target_file)}")
                print(f"Ã°Å¸â€œÅ  MissionLayer now has {len(new_entities)} entities")
                
                # Update entity's XML reference
                entity.xml_element = fresh_element
                
                # Save immediately
                tree.write(target_file, encoding='utf-8', xml_declaration=True)
                print(f"Ã°Å¸â€™Â¾ Saved {os.path.basename(target_file)}")
                
                # Mark file as modified
                if not hasattr(self, 'worldsectors_modified'):
                    self.worldsectors_modified = {}
                self.worldsectors_modified[target_file] = True
                
                return True
            else:
                print(f"Entity addition verification failed")
                return False
                
        except Exception as e:
            print(f"Error adding entity: {e}")
            import traceback
            traceback.print_exc()
            return False

    def execute_sector_move(self, entity, current_file, target_file, target_sector):
        """Execute the actual sector move operation - FIXED for FCBConverter format"""
        try:
            print(f"\nÃ°Å¸Å¡Å¡ Executing sector move for {entity.name}")
            print(f"From: {current_file}")
            print(f"To: {target_file}")
            
            # Step 1: Remove from current sector
            if current_file and current_file != "Unknown":
                success = self.remove_entity_from_sector(entity, current_file)
                if not success:
                    QMessageBox.critical(
                        self,
                        "Remove Failed",
                        f"Failed to remove {entity.name} from current sector.\n\n"
                        f"The entity '{entity.name}' was not found in the source file.\n"
                        f"This might happen if:\n"
                        f"The entity was already moved\n"
                        f"The XML file structure is different than expected\n"
                        f"The entity name contains special characters\n\n"
                        f"Check the console output for detailed debugging information."
                    )
                    return False
                print(f"Successfully removed from {os.path.basename(current_file)}")
            
            # Step 2: Update entity's file reference
            entity.source_file_path = target_file
            
            # Step 3: Add to target sector
            success = self.add_entity_to_sector(entity, target_file)
            if not success:
                QMessageBox.critical(
                    self,
                    "Add Failed", 
                    f"Failed to add {entity.name} to target sector.\n"
                    f"Entity may have been removed from original sector!"
                )
                return False
            
            print(f"Successfully added to {os.path.basename(target_file)}")
            
            # Step 4: Update UI
            if hasattr(self, 'update_entity_tree'):
                self.update_entity_tree()
            
            if hasattr(self, 'canvas'):
                self.canvas.update()
            
            # Step 5: Mark as modified
            self.entities_modified = True
            
            QMessageBox.information(
                self,
                "Move Successful",
                f"Successfully moved {entity.name} to sector {target_sector}!"
            )
            
            return True
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Move Error",
                f"Error moving entity: {str(e)}"
            )
            print(f"Error in execute_sector_move: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_sector_move_to_context_menu(self):
        """Add sector move option to existing context menu"""
        
        # Store the original context menu function if it exists
        if hasattr(self.canvas, 'showContextMenu'):
            original_context_menu = self.canvas.showContextMenu
        else:
            original_context_menu = None
        
        def enhanced_showContextMenu(event):
            """Enhanced context menu with sector move option"""
            from PyQt6.QtWidgets import QMenu
            from PyQt6.QtCore import Qt
            
            menu = QMenu(self.canvas)
            
            # Check if we have a selected entity
            selected_entity = None
            if hasattr(self.canvas, 'selected') and self.canvas.selected:
                selected_entity = self.canvas.selected[0]
            elif hasattr(self, 'selected_entity') and self.selected_entity:
                selected_entity = self.selected_entity
            
            # Add sector move option if entity is selected
            if selected_entity:
                menu.addAction(f"Selected: {selected_entity.name}").setEnabled(False)
                menu.addSeparator()
                
                # Check if entity is from worldsectors
                source_file = getattr(selected_entity, 'source_file_path', None)
                if source_file and 'worldsector' in source_file:
                    move_sector_action = menu.addAction("Move to Different Sector...")
                    move_sector_action.triggered.connect(
                        lambda: self.move_entity_to_sector_manually(selected_entity)
                    )
                    menu.addSeparator()
                else:
                    menu.addAction("(Not a worldsector entity)").setEnabled(False)
                    menu.addSeparator()
            
            # Add original context menu items from your existing copy/paste system
            selected_entities = getattr(self.canvas, 'selected', [])
            has_selection = len(selected_entities) > 0
            has_clipboard = hasattr(self, 'entity_clipboard') and self.entity_clipboard.has_clipboard_data()
            
            if has_selection:
                copy_action = menu.addAction("Copy Entities")
                copy_action.triggered.connect(self.copy_selected_entities)
                
                duplicate_action = menu.addAction("Duplicate Entities")
                duplicate_action.triggered.connect(self.duplicate_selected_entities)
                
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
            
            # Selection actions
            if not has_selection:
                select_all_action = menu.addAction("Select All Entities")
                select_all_action.triggered.connect(self.select_all_entities)
                menu.addSeparator()
            
            # View actions
            center_action = menu.addAction("Center View Here")
            center_action.triggered.connect(lambda: self.center_view_here(event))
            
            reset_action = menu.addAction("Reset View")
            reset_action.triggered.connect(self.reset_view)
            
            # Toggle options
            menu.addSeparator()
            toggle_grid_action = menu.addAction("Toggle Grid")
            toggle_grid_action.setCheckable(True)
            toggle_grid_action.setChecked(self.canvas.show_grid)
            toggle_grid_action.triggered.connect(self.toggle_grid)
            
            toggle_entities_action = menu.addAction("Toggle Entities")
            toggle_entities_action.setCheckable(True)
            toggle_entities_action.setChecked(self.canvas.show_entities)
            toggle_entities_action.triggered.connect(self.toggle_entities)
            
            # Add sector boundaries toggle if available
            if hasattr(self.canvas, 'show_sector_boundaries'):
                toggle_sectors_action = menu.addAction("Toggle Sector Boundaries")
                toggle_sectors_action.setCheckable(True)
                toggle_sectors_action.setChecked(self.canvas.show_sector_boundaries)
                toggle_sectors_action.triggered.connect(self.toggle_sector_boundaries)
            
            # Show the menu
            menu.exec(event.globalPosition().toPoint())
        
        # Replace the context menu
        self.canvas.showContextMenu = enhanced_showContextMenu
        print("Added 'Move to Different Sector' to enhanced right-click menu")

    def center_view_here(self, event):
        """Center view at click location"""
        width = self.canvas.width()
        height = self.canvas.height()
        self.canvas.offset_x += width / 2 - event.position().x()
        self.canvas.offset_y += height / 2 - event.position().y()
        self.canvas.update()

    def _find_tree_file_path(self, tree_type):
        """Find the file path for a specific tree type"""
        if not hasattr(self, 'xml_file_path') or not self.xml_file_path:
            return None
        
        folder_path = os.path.dirname(self.xml_file_path)
        
        # Define patterns to look for each tree type
        patterns = {
            'omnis': ['.omnis.xml', 'omnis.xml'],
            'managers': ['.managers.xml', 'managers.xml'],
            'sectordep': ['sectorsdep.xml', 'sectordep.xml', '.sectorsdep.xml']
        }
        
        if tree_type not in patterns:
            return None
        
        # Try to find existing file
        for pattern in patterns[tree_type]:
            file_path = os.path.join(folder_path, pattern)
            if os.path.exists(file_path):
                return file_path
            
            # Also try with level name prefix
            if hasattr(self, 'xml_file_path') and self.xml_file_path:
                level_name = os.path.splitext(os.path.basename(self.xml_file_path))[0]
                prefixed_pattern = f"{level_name}{pattern}"
                file_path = os.path.join(folder_path, prefixed_pattern)
                if os.path.exists(file_path):
                    return file_path
        
        # If not found, return None (don't create new files)
        return None
        
    def determine_entity_map(self, entity):
        """Determine which map an entity belongs to based on its coordinates"""
        if not self.grid_config or not self.grid_config.maps:
            return None
            
        # Convert entity coordinates to sector coordinates
        sector_x = int(entity.x / self.grid_config.sector_granularity)
        sector_y = int(entity.z / self.grid_config.sector_granularity)  # Note: using Z for Y-axis
        
        # Check each map to see if entity belongs to it
        for map_info in self.grid_config.maps:
            min_sector_x = map_info.sector_offset_x
            min_sector_y = map_info.sector_offset_y
            max_sector_x = min_sector_x + map_info.count_x
            max_sector_y = min_sector_y + map_info.count_y
            
            if (min_sector_x <= sector_x < max_sector_x and 
                min_sector_y <= sector_y < max_sector_y):
                return map_info.name
        
        return None

    def create_entity_browser(self):
        """Create a dock widget for browsing and organizing entities"""
        # Create dock widget
        entity_dock = QDockWidget("Entity Browser", self)
        entity_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        entity_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | 
                            QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        
        # Create main widget
        dock_widget = QWidget()
        dock_layout = QVBoxLayout(dock_widget)
        
        # Add search/filter control
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.entity_filter = QLineEdit()
        self.entity_filter.setPlaceholderText("Search entities...")
        self.entity_filter.textChanged.connect(self.filter_entities)
        filter_layout.addWidget(self.entity_filter)
        
        dock_layout.addLayout(filter_layout)
        
        # Add grouping options
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group by:"))
        
        self.group_combo = QComboBox()
        self.group_combo.addItems(["No Grouping", "By Map", "By Source", "By Type"])
        self.group_combo.currentIndexChanged.connect(self.update_entity_tree)
        group_layout.addWidget(self.group_combo)
        
        dock_layout.addLayout(group_layout)
        
        # Create tree widget
        self.entity_tree = QTreeWidget()
        self.entity_tree.setHeaderLabels(["Name", "ID", "Position"])
        self.entity_tree.setColumnWidth(0, 180)
        self.entity_tree.setColumnWidth(1, 80)
        self.entity_tree.setAlternatingRowColors(False)
        self.entity_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.entity_tree.itemSelectionChanged.connect(self.on_entity_tree_selection_changed)
        dock_layout.addWidget(self.entity_tree)
        
        # Add buttons at bottom
        button_layout = QHBoxLayout()
        
        # Add "Select All" button
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self.select_all_entities)
        button_layout.addWidget(select_all_button)
        
        # Add "Select None" button
        select_none_button = QPushButton("Select None")
        select_none_button.clicked.connect(self.clear_entity_selection)
        button_layout.addWidget(select_none_button)
        
        # Add "Refresh" button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.update_entity_tree)
        button_layout.addWidget(refresh_button)
        
        dock_layout.addLayout(button_layout)
        
        # Set the dock widget
        entity_dock.setWidget(dock_widget)
        
        # Set a fixed width for the dock widget
        entity_dock.setMinimumWidth(400)  # Set minimum width
        entity_dock.setMaximumWidth(500)  # Set maximum width (optional)
        
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, entity_dock)
        
        # Keep a reference to the dock
        self.entity_browser_dock = entity_dock
        
        self.entity_tree.itemDoubleClicked.connect(self.on_entity_tree_double_clicked)

        # Initialize the tree
        self.update_entity_tree()
        
        return entity_dock
    
    def debug_entity_update(self):
        """Debug the currently selected entity"""
        if self.selected_entity:
            print(f"\nDEBUG: Starting debug for {self.selected_entity.name}")
            self.canvas.debug_entity_xml_update(self.selected_entity.name)
        else:
            print("No entity selected for debugging")
            print("Please select an entity first, then click Debug Entity")

    def setup_entity_browser_connections(self):
        """Setup additional connections for the entity browser"""
        # Double-click handler for zooming to entity location
        self.entity_tree.itemDoubleClicked.connect(self.on_entity_tree_double_clicked)

    def on_entity_tree_selection_changed(self):
        """Handle selection change in the entity tree - FIXED to fully select entity like grid selection"""
        # Get selected items
        selected_items = self.entity_tree.selectedItems()
        
        # Filter out group items (which don't have entity data)
        selected_entities = []
        for item in selected_items:
            entity = item.data(0, Qt.ItemDataRole.UserRole)
            if entity:
                selected_entities.append(entity)
        
        # Skip if no entities selected
        if not selected_entities:
            # Clear selection and hide gizmo
            if hasattr(self.canvas, 'selected'):
                self.canvas.selected = []
            self.selected_entity = None
            if hasattr(self.canvas, 'selected_entity'):
                self.canvas.selected_entity = None
            
            # Hide gizmo when nothing is selected
            if hasattr(self.canvas, 'gizmo_renderer'):
                self.canvas.gizmo_renderer.hide_gizmo()
            
            # Update UI
            self.update_ui_for_selected_entity(None)
            self.canvas.update()
            return
        
        # CRITICAL FIX: Use the same handler as grid selection to ensure full selection
        # This ensures the entity is fully selected for the entity editor (Ctrl+E)
        primary_entity = selected_entities[0]
        
        # Print which entity was selected from the browser
        print(f"Entity Browser: Selected '{primary_entity.name}' (ID: {primary_entity.id})")
        
        # Set canvas selection for multiple selection support
        if hasattr(self.canvas, 'selected'):
            self.canvas.selected = selected_entities
        
        # Call the same handler as grid selection to ensure consistent behavior
        # This ensures the entity is fully recognized by entity editor and all systems
        self.on_entity_selected(primary_entity)
        
        # If multiple selection, also update canvas.selected list
        if len(selected_entities) > 1:
            if hasattr(self.canvas, 'selected'):
                self.canvas.selected = selected_entities
            print(f"Multiple entities selected ({len(selected_entities)}), primary: {primary_entity.name}")
            
    def on_entity_tree_double_clicked(self, item, column):
        """Enhanced double-click handler that shows gizmo and centers view"""
        # Get the entity
        entity = item.data(0, Qt.ItemDataRole.UserRole)
        if not entity:
            return
        
        print(f"Ã°Å¸Å½Â¯ Double-clicked entity: {entity.name}")
        
        # Select the entity
        self.selected_entity = entity
        self.canvas.selected_entity = entity
        self.canvas.selected = [entity]
        
        # CRITICAL: Update gizmo for double-clicked entity
        if hasattr(self.canvas, 'gizmo_renderer'):
            print(f"Ã°Å¸Å½Â¯ Double-click: Updating gizmo for {entity.name}")
            self.canvas.gizmo_renderer.update_gizmo_for_entity(entity)
        
        # Update UI
        self.update_ui_for_selected_entity(entity)
        
        # Center view on entity
        if self.canvas.mode == 0:  # 2D mode
            # Set position but keep current scale
            self.canvas.offset_x = (self.canvas.width() / 2) - (entity.x * self.canvas.scale_factor)
            self.canvas.offset_y = (self.canvas.height() / 2) - (entity.y * self.canvas.scale_factor)
        else:
            # 3D mode - set camera position
            self.canvas.offset_x = -entity.x
            self.canvas.offset_z = entity.z + 100
            self.canvas.camera_height = entity.y + 50
            if hasattr(self.canvas.camera_controller, 'update_camera_direction'):
                self.canvas.camera_controller.update_camera_direction()
        
        # Update canvas
        self.canvas.update()
        
        print(f"Double-click complete: Entity {entity.name} selected with gizmo visible")

    def zoom_to_entity(self, entity):
        """Zoom and center view on the specified entity - WORKS IN 2D AND 3D"""
        print(f"zoom_to_entity called for: {entity.name if entity else 'None'}")
        
        if not entity:
            print("No entity provided!")
            return
            
        print(f"Zooming to entity: {entity.name}")
        print(f"Entity position: ({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})")
        print(f"Entity map: {entity.map_name}")
        print(f"Current map: {self.current_map.name if self.current_map else 'None'}")
        print(f"Current mode: {'2D' if self.canvas.mode == 0 else '3D'}")
            
        # Check if entity is in current map
        if self.current_map is not None and entity.map_name != self.current_map.name:
            print(f"Entity is in a different map, switching to {entity.map_name}")
            # First switch to the correct map
            for i in range(self.map_combo.count()):
                map_info = self.map_combo.itemData(i)
                if map_info and map_info.name == entity.map_name:
                    print(f"Found matching map at index {i}")
                    self.map_combo.setCurrentIndex(i)
                    break
            else:
                print("Could not find matching map in combo box")
        
        # Zoom based on current mode
        if self.canvas.mode == 0:  # 2D mode
            print("Using 2D zoom...")
            
            # Use canvas zoom method if available
            if hasattr(self.canvas, 'zoom_to_entity'):
                self.canvas.zoom_to_entity(entity)
            else:
                # Fallback: manual 2D positioning
                print("Using fallback 2D zoom")
                self.canvas.selected_entity = entity
                self.canvas.selected = [entity]
                
                # Center on entity
                self.canvas.offset_x = (self.canvas.width() / 2) - (entity.x * self.canvas.scale_factor)
                self.canvas.offset_y = (self.canvas.height() / 2) - (entity.y * self.canvas.scale_factor)
                
                # Set a reasonable zoom level
                self.canvas.scale_factor = max(self.canvas.scale_factor, 1.0)
                
                self.canvas.update()
                
            print(f"2D zoom complete: offset=({self.canvas.offset_x:.1f}, {self.canvas.offset_y:.1f}), "
                f"scale={self.canvas.scale_factor:.2f}")
            
        else:  # 3D mode
            print("Using 3D camera positioning...")
            
            import numpy as np
            
            # Calculate camera position relative to entity
            # Position camera behind and above the entity for a good view
            camera_offset_distance = 100.0  # Distance from entity
            camera_height_offset = 50.0     # Height above entity
            
            # Position camera behind entity (negative X direction)
            camera_x = entity.x - camera_offset_distance
            camera_y = entity.z + camera_height_offset  # Z is height in game coordinates
            camera_z = entity.y  # Y maps to Z in OpenGL
            
            self.canvas.camera_3d.position = np.array([camera_x, camera_y, camera_z], dtype=float)
            
            # Calculate yaw to look at entity
            dx = entity.x - camera_x
            dy = entity.y - camera_z
            self.canvas.camera_3d.yaw = np.degrees(np.arctan2(dy, dx))
            
            # Set pitch to look slightly down at entity
            dz = entity.z - camera_y
            horizontal_dist = np.sqrt(dx*dx + dy*dy)
            if horizontal_dist > 0:
                self.canvas.camera_3d.pitch = np.degrees(np.arctan2(-dz, horizontal_dist))
            else:
                self.canvas.camera_3d.pitch = -20.0
            
            # Clamp pitch
            self.canvas.camera_3d.pitch = np.clip(self.canvas.camera_3d.pitch, -89, 89)
            
            # Update camera vectors
            self.canvas.camera_3d.update_vectors()
            
            # Update canvas
            self.canvas.update()
            
            print(f"3D camera positioned at ({camera_x:.0f}, {camera_y:.0f}, {camera_z:.0f})")
            print(f"Looking at entity: yaw={self.canvas.camera_3d.yaw:.1f}°, "
                f"pitch={self.canvas.camera_3d.pitch:.1f}°")
            
            # Update status bar
            self.status_bar.showMessage(f"3D camera focused on {entity.name}")

    def _set_item_color_by_source(self, item, entity):
        """Set item text color based on entity source and type - SILENT VERSION"""
        # Define colors that EXACTLY match your legend
        legend_colors = {
            "Vehicle": QColor(52, 152, 255),     # Blue - Vehicles
            "NPC": QColor(46, 255, 113),         # Green - NPCs/Characters
            "Weapon": QColor(255, 76, 60),       # Red - Weapons/Explosives
            "Spawn": QColor(255, 156, 18),       # Orange - Spawn Locations
            "Mission": QColor(185, 89, 255),     # Purple - Mission Objects
            "Trigger": QColor(255, 230, 15),     # Yellow - Triggers/Zones
            "Prop": QColor(170, 180, 190),       # Gray - Props/Static Objects
            "Light": QColor(255, 255, 160),      # Light Yellow - Lights
            "Effect": QColor(0, 255, 200),       # Teal - Effects/Particles
            "WorldSectors": QColor(255, 100, 100), # Red - WorldSectors Objects
            "Unknown": QColor(130, 130, 130)     # Dark Gray - Unknown Type
        }
        
        # Determine entity type using the SAME logic as your canvas entity renderer
        entity_type = self._determine_entity_type_for_browser(entity)
        
        # Only use "WorldSectors" color as absolute fallback for truly unknown entities from worldsectors
        source_file_path = getattr(entity, 'source_file_path', None)
        source_file = getattr(entity, 'source_file', None)
        
        is_from_worldsectors = (source_file == 'worldsectors' or 
                            (source_file_path and 'worldsector' in source_file_path.lower()))
        
        # Only override to WorldSectors color if the entity type is Unknown AND it's from worldsectors
        if is_from_worldsectors and entity_type == "Unknown":
            entity_type = "WorldSectors"
        
        # Get the color for this entity type
        entity_color = legend_colors.get(entity_type, legend_colors["Unknown"])
        
        # Check if entity is selected
        is_selected = (entity == self.selected_entity or 
                    (hasattr(self.canvas, 'selected') and entity in self.canvas.selected))
        
        if is_selected:
            # SELECTED ENTITY STYLING
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
            
            selected_bg = QColor(52, 152, 255, 120)  # Blue with opacity
            item.setBackground(0, selected_bg)
            item.setForeground(0, QColor(255, 255, 255))  # White text for selected
            
            # REMOVE/REDUCE: Only log occasionally
            if not hasattr(self, '_last_selection_log_time'):
                self._last_selection_log_time = 0
            
            current_time = time.time()
            if current_time - self._last_selection_log_time > 2.0:  # Only every 2 seconds
                print(f"Ã°Å¸Å½Â¯ Selected entity styling applied: {getattr(entity, 'name', 'unknown')}")
                self._last_selection_log_time = current_time
        else:
            # NON-SELECTED ENTITY STYLING
            font = item.font(0)
            font.setBold(False)
            item.setFont(0, font)
            
            item.setBackground(0, QColor(0, 0, 0, 0))  # Transparent background
            item.setForeground(0, entity_color)
        
    def _determine_entity_type_for_browser(self, entity):
        """Cached version to avoid repeated analysis"""
        entity_id = id(entity)
        
        # Check cache first
        if entity_id in self.tree_entity_type_cache:
            return self.tree_entity_type_cache[entity_id]
        
        # Calculate once and cache
        entity_type = self._calculate_entity_type(entity)
        self.tree_entity_type_cache[entity_id] = entity_type
        
        return entity_type

    def _calculate_entity_type(self, entity):
        """The actual calculation logic - SILENT VERSION"""
        entity_name = getattr(entity, 'name', '').lower()
        
        # Vehicle patterns (check first as they're most specific)
        vehicle_patterns = ['vehicle', 'car', 'truck', 'boat', 'ship', 'plane', 'helicopter', 
                        'bike', 'motorcycle', 'aircraft', 'transport', 'scorpion', 'samson']
        for pattern in vehicle_patterns:
            if pattern in entity_name:
                return "Vehicle"
        
        # NPC/Character patterns  
        npc_patterns = ['npc', 'character', 'ai_', 'enemy', 'friend', 'ally', 'neutral', 
                    'soldier', 'civilian', 'avatar', 'human', 'person']
        for pattern in npc_patterns:
            if pattern in entity_name:
                return "NPC"
        
        # Weapon patterns
        weapon_patterns = ['weapon', 'gun', 'rifle', 'pistol', 'sword', 'bomb', 'explosive', 
                        'grenade', 'missile', 'rocket', 'ammo', 'ammunition']
        for pattern in weapon_patterns:
            if pattern in entity_name:
                return "Weapon"
        
        # Spawn patterns
        spawn_patterns = ['spawn', 'start', 'respawn', 'checkpoint', 'playerstart', 
                        'spawnpoint', 'birth', 'entry']
        for pattern in spawn_patterns:
            if pattern in entity_name:
                return "Spawn"
        
        # Mission patterns
        mission_patterns = ['mission', 'objective', 'goal', 'target', 'quest', 'task', 
                        'pickup', 'collectible', 'artifact']
        for pattern in mission_patterns:
            if pattern in entity_name:
                return "Mission"
        
        # Trigger patterns
        trigger_patterns = ['trigger', 'zone', 'area', 'region', 'volume', 'detector', 
                        'sensor', 'activator', 'switch']
        for pattern in trigger_patterns:
            if pattern in entity_name:
                return "Trigger"
        
        # Light patterns
        light_patterns = ['light', 'lamp', 'torch', 'spotlight', 'illumination', 'glow', 
                        'bulb', 'lantern', 'beacon']
        for pattern in light_patterns:
            if pattern in entity_name:
                return "Light"
        
        # Effect patterns
        effect_patterns = ['fx_', 'effect', 'particle', 'vfx', 'smoke', 'fire', 'explosion',
                        'steam', 'dust', 'spark', 'emitter']
        for pattern in effect_patterns:
            if pattern in entity_name:
                return "Effect"
        
        # Prop patterns (check last as it's most generic)
        prop_patterns = ['prop_', 'object_', 'static_', 'decoration', 'furniture', 'building',
                        'structure', 'rock', 'tree', 'plant', 'debris']
        for pattern in prop_patterns:
            if pattern in entity_name:
                return "Prop"
        
        # Default to Unknown
        return "Unknown"

    def debug_entity_colors(self):
        """Debug method to check why entities are showing as red"""
        print(f"\nDEBUG: Entity Browser Colors")
        print(f"Total entities: {len(self.entities) if hasattr(self, 'entities') else 0}")
        
        if hasattr(self, 'entities') and self.entities:
            # Check first 5 entities
            for i, entity in enumerate(self.entities[:5]):
                entity_name = getattr(entity, 'name', 'unknown')
                source_file = getattr(entity, 'source_file', 'none')
                source_file_path = getattr(entity, 'source_file_path', 'none')
                
                print(f"\nEntity {i+1}: {entity_name}")
                print(f"  source_file: {source_file}")
                print(f"  source_file_path: {source_file_path}")
                
                # Test type detection
                entity_type = self._determine_entity_type_for_browser(entity)
                print(f"  detected_type: {entity_type}")
                
                # Check if it's being classified as WorldSectors
                is_worldsector = (source_file == 'worldsectors' or 
                                (source_file_path and 'worldsector' in source_file_path.lower()))
                print(f"  is_worldsector: {is_worldsector}")
                
                # Final type
                final_type = "WorldSectors" if is_worldsector else entity_type
                print(f"  final_type: {final_type}")

    def fix_red_entities_in_browser(self):
        """Quick fix method to refresh entity browser colors"""
        try:
            print("Fixing red entity highlighting in browser...")
            
            # Debug current state
            self.debug_entity_colors()
            
            # Force refresh the entity tree
            if hasattr(self, 'update_entity_tree'):
                self.update_entity_tree()
            
            print("Entity browser colors refreshed")
            
        except Exception as e:
            print(f"Error fixing entity colors: {e}")

    def update_entity_tree(self):
        """Update the entity tree with current entities and grouping, theme-aware"""
        self.entity_tree.clear()
        
        if not self.entities:
            return
        
        grouping = self.group_combo.currentText()
        filter_text = self.entity_filter.text().lower()
        
        if grouping == "No Grouping":
            self._populate_tree_no_grouping(filter_text)
        elif grouping == "By Map":
            self._populate_tree_by_map(filter_text)
        elif grouping == "By Source":
            self._populate_tree_by_source(filter_text)
        elif grouping == "By Type":
            self._populate_tree_by_type_enhanced(filter_text)
        
        # Expand top-level items
        for i in range(self.entity_tree.topLevelItemCount()):
            self.entity_tree.topLevelItem(i).setExpanded(True)

    def _populate_tree_by_type_enhanced(self, filter_text=""):
        type_groups = {}
        group_colors = {
            "Vehicle": QColor(52, 152, 255),
            "NPC": QColor(46, 255, 113),
            "Weapon": QColor(255, 76, 60),
            "Spawn": QColor(255, 156, 18),
            "Mission": QColor(185, 89, 255),
            "Trigger": QColor(255, 230, 15),
            "Prop": QColor(170, 180, 190),
            "Light": QColor(255, 255, 160),
            "Effect": QColor(0, 255, 200),
            "WorldSectors": QColor(255, 100, 100),
            "Unknown": QColor(130, 130, 130)
        }

        for entity in self.entities:
            if filter_text and filter_text not in entity.name.lower() and filter_text not in entity.id.lower():
                continue

            entity_type = self._determine_entity_type_for_browser(entity)
            source_file_path = getattr(entity, 'source_file_path', None)
            source_file = getattr(entity, 'source_file', None)
            if source_file == 'worldsectors' or (source_file_path and 'worldsector' in source_file_path.lower()):
                entity_type = "WorldSectors"

            # Create group header if it doesn't exist
            if entity_type not in type_groups:
                type_group = QTreeWidgetItem()
                type_group.setText(0, f"{entity_type} (0)")
                # Keep background color
                group_color = group_colors.get(entity_type, group_colors["Unknown"])
                bg_color = QColor(group_color)
                bg_color.setAlpha(80)
                type_group.setBackground(0, bg_color)

                # Use theme-aware text for header
                self._set_item_theme_color(type_group)

                # Bold font for group headers
                font = type_group.font(0)
                font.setBold(True)
                type_group.setFont(0, font)

                self.entity_tree.addTopLevelItem(type_group)
                type_groups[entity_type] = {'group': type_group, 'count': 0}

            # Add entity to group
            item = QTreeWidgetItem(type_groups[entity_type]['group'])
            item.setText(0, entity.name)
            item.setText(1, entity.id)
            item.setText(2, f"({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})")
            item.setData(0, Qt.ItemDataRole.UserRole, entity)

            # Theme-aware text color
            self._set_item_theme_color(item)

            type_groups[entity_type]['count'] += 1

        # Update group counts
        for entity_type, group_data in type_groups.items():
            count = group_data['count']
            group_data['group'].setText(0, f"{entity_type} ({count})")
            # Apply theme-aware color again after updating text
            self._set_item_theme_color(group_data['group'])

    def _set_item_theme_color(self, item):
        """Set QTreeWidgetItem text color based on current theme"""
        color = QColor(255, 255, 255) if self.force_dark_theme else QColor(0, 0, 0)
        for col in range(item.columnCount()):
            item.setForeground(col, color)

    def create_color_legend_group(self):
        """Enhanced color legend with better organization"""
        legend_group = QGroupBox("Entity Type Color Legend")
        legend_layout = QVBoxLayout(legend_group)
        
        # Add header
        header_label = QLabel("Colors match entity browser and canvas:")
        header_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        legend_layout.addWidget(header_label)
        
        # Create color samples with labels (matching your existing legend)
        self.create_color_legend_item(legend_layout, QColor(52, 152, 255), "Blue - Vehicles")        
        self.create_color_legend_item(legend_layout, QColor(46, 255, 113), "Green - NPCs/Characters") 
        self.create_color_legend_item(legend_layout, QColor(255, 76, 60), "Red - Weapons/Explosives") 
        self.create_color_legend_item(legend_layout, QColor(255, 156, 18), "Orange - Spawn Locations") 
        self.create_color_legend_item(legend_layout, QColor(185, 89, 255), "Purple - Mission Objects") 
        self.create_color_legend_item(legend_layout, QColor(255, 230, 15), "Yellow - Triggers/Zones") 
        self.create_color_legend_item(legend_layout, QColor(170, 180, 190), "Gray - Props/Static Objects") 
        self.create_color_legend_item(legend_layout, QColor(255, 255, 160), "Light Yellow - Lights") 
        self.create_color_legend_item(legend_layout, QColor(0, 255, 200), "Teal - Effects/Particles") 
        self.create_color_legend_item(legend_layout, QColor(255, 100, 100), "Red - WorldSectors Objects") 
        self.create_color_legend_item(legend_layout, QColor(130, 130, 130), "Dark Gray - Unknown Type") 
        
    def _populate_tree_no_grouping(self, filter_text=""):
        for entity in self.entities:
            if filter_text and filter_text not in entity.name.lower() and filter_text not in entity.id.lower():
                continue
            
            item = QTreeWidgetItem()
            item.setText(0, entity.name)
            item.setText(1, entity.id)
            item.setText(2, f"({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})")
            item.setData(0, Qt.ItemDataRole.UserRole, entity)
            
            # Set theme-aware text color
            self._set_item_theme_color(item)
            
            self.entity_tree.addTopLevelItem(item)

    def _populate_tree_by_map(self, filter_text=""):
        map_groups = {}
        
        no_map_group = QTreeWidgetItem()
        no_map_group.setText(0, "No Map")
        no_map_group.setBackground(0, QColor(200, 200, 200, 100))
        self.entity_tree.addTopLevelItem(no_map_group)
        
        for entity in self.entities:
            if filter_text and filter_text not in entity.name.lower() and filter_text not in entity.id.lower():
                continue
            
            map_name = entity.map_name
            if not map_name:
                item = QTreeWidgetItem(no_map_group)
            else:
                if map_name not in map_groups:
                    map_group = QTreeWidgetItem()
                    map_group.setText(0, os.path.basename(map_name))
                    map_group.setBackground(0, QColor(220, 240, 255, 100))
                    self.entity_tree.addTopLevelItem(map_group)
                    map_groups[map_name] = map_group
                item = QTreeWidgetItem(map_groups[map_name])
            
            item.setText(0, entity.name)
            item.setText(1, entity.id)
            item.setText(2, f"({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})")
            item.setData(0, Qt.ItemDataRole.UserRole, entity)
            self._set_item_theme_color(item)
        
        if no_map_group.childCount() == 0:
            index = self.entity_tree.indexOfTopLevelItem(no_map_group)
            self.entity_tree.takeTopLevelItem(index)

    def _populate_tree_by_source(self, filter_text=""):
        source_groups = {}
        
        unknown_group = QTreeWidgetItem()
        unknown_group.setText(0, "Unknown Source")
        unknown_group.setBackground(0, QColor(200, 200, 200, 100))
        self.entity_tree.addTopLevelItem(unknown_group)
        
        for entity in self.entities:
            if filter_text and filter_text not in entity.name.lower() and filter_text not in entity.id.lower():
                continue
            
            source = getattr(entity, 'source_file', 'unknown')
            if not source:
                source = "unknown"
            
            if source not in source_groups:
                source_group = QTreeWidgetItem()
                source_group.setText(0, source)
                source_group.setBackground(0, QColor(220, 220, 220, 100))
                self.entity_tree.addTopLevelItem(source_group)
                source_groups[source] = source_group
            
            item = QTreeWidgetItem(source_groups[source])
            item.setText(0, entity.name)
            item.setText(1, entity.id)
            item.setText(2, f"({entity.x:.1f}, {entity.y:.1f}, {entity.z:.1f})")
            item.setData(0, Qt.ItemDataRole.UserRole, entity)
            self._set_item_theme_color(item)

    def _update_tree_selection(self):
        """Update tree selection to match canvas, without overriding theme colors"""
        if not hasattr(self, 'entity_tree'):
            return
        
        self.entity_tree.blockSignals(True)
        try:
            selected_entities = getattr(self.canvas, 'selected', [])
            self.entity_tree.clearSelection()
            self._refresh_all_item_colors()
            
            for i in range(self.entity_tree.topLevelItemCount()):
                top_item = self.entity_tree.topLevelItem(i)
                if top_item.childCount() > 0:
                    for j in range(top_item.childCount()):
                        child = top_item.child(j)
                        entity = child.data(0, Qt.ItemDataRole.UserRole)
                        if entity in selected_entities:
                            child.setSelected(True)
                else:
                    entity = top_item.data(0, Qt.ItemDataRole.UserRole)
                    if entity in selected_entities:
                        top_item.setSelected(True)
        finally:
            self.entity_tree.blockSignals(False)

    def _refresh_all_item_colors(self):
        """Refresh all tree items to theme colors only"""
        for i in range(self.entity_tree.topLevelItemCount()):
            top_item = self.entity_tree.topLevelItem(i)
            
            # If it's a group with children
            if top_item.childCount() > 0:
                for j in range(top_item.childCount()):
                    child = top_item.child(j)
                    self._set_item_theme_color(child)
            else:
                self._set_item_theme_color(top_item)

        # Force repaint so colors update immediately
        self.entity_tree.viewport().update()

    def on_entity_selected(self, entity):
        """Handle when an entity is selected - WORKS IN BOTH MODES"""
        self.selected_entity = entity
        
        # Log selection
        if entity:
            print(f"Entity selected: {entity.name} (ID: {entity.id}) in {'2D' if self.canvas.mode == 0 else '3D'} mode")
        else:
            print(f"Entity deselected in {'2D' if self.canvas.mode == 0 else '3D'} mode")
        
        # Update gizmo (2D mode only)
        if self.canvas.mode == 0:  # 2D mode
            if hasattr(self.canvas, 'gizmo_renderer') and entity:
                print(f"2D mode: Updating gizmo for {entity.name}")
                self.canvas.gizmo_renderer.update_gizmo_for_entity(entity)
            elif hasattr(self.canvas, 'gizmo_renderer'):
                # Hide gizmo when nothing is selected
                self.canvas.gizmo_renderer.hide_gizmo()
        else:  # 3D mode
            # Gizmo not shown in 3D mode
            if hasattr(self.canvas, 'gizmo_renderer'):
                self.canvas.gizmo_renderer.hide_gizmo()
        
        # Update UI (works in both modes)
        self.update_ui_for_selected_entity(entity)
        
        # Update selection in entity tree
        self._update_tree_selection()
        
        # Force canvas update
        self.canvas.update()

    def update_entity_tree_colors_only(self):
        """Update only the colors in the entity tree without rebuilding it"""
        try:
            if not hasattr(self, 'entity_tree'):
                return
                
            print("Updating entity tree colors, Please wait.")
            
            # Refresh all item colors
            self._refresh_all_item_colors()
            
            print("Entity tree colors updated")
            
        except Exception as e:
            print(f"Error updating entity tree colors: {e}")

    def force_refresh_entity_tree_colors(self):
        """Force refresh of all entity tree colors - useful after selection changes"""
        try:
            # This method can be called from external systems when selection changes
            self.update_entity_tree_colors_only()
            
            # Also update the tree selection highlighting
            self._update_tree_selection()
            
        except Exception as e:
            print(f"Error force refreshing entity tree colors: {e}")

    def filter_entities(self):
        """Filter entities in the tree based on search text"""
        self.update_entity_tree()

    def fix_xml_element_references(self):
        """Fix xml_element references to point to the actual tree elements"""
        print(f"\nFIXING: XML element references")
        
        if not hasattr(self, 'worldsectors_trees'):
            print(f"No worldsectors_trees found")
            return
        
        fixed_count = 0
        
        for entity in self.entities:
            if hasattr(entity, 'source_file_path') and entity.source_file_path:
                source_file = entity.source_file_path
                
                if source_file in self.worldsectors_trees:
                    tree = self.worldsectors_trees[source_file]
                    root = tree.getroot()
                    
                    # Find the entity in the tree
                    for entity_elem in root.findall(".//object[@type='Entity']"):
                        name_elem = entity_elem.find("./value[@name='hidName']")
                        if name_elem is not None and name_elem.text == entity.name:
                            # Update the reference
                            entity.xml_element = entity_elem
                            fixed_count += 1
                            print(f"   Fixed reference for {entity.name}")
                            break
        
        print(f"Fixed {fixed_count} XML element references")

    def test_xml_save_after_fix(self, entity_name="Avatar.Scorpion_Pilotable_0"):
        """Test XML save after fixing references"""
        print(f"\nTEST: XML save after fixing references")
        
        # Step 1: Fix references
        self.fix_xml_element_references()
        
        # Step 2: Find entity
        target_entity = None
        for entity in self.entities:
            if entity.name == entity_name:
                target_entity = entity
                break
        
        if not target_entity:
            print(f"Entity not found")
            return
        
        # Step 3: Move entity
        original_y = target_entity.y
        test_y = 777.54321
        target_entity.y = test_y
        
        print(f"Ã°Å¸â€œÂ Moved entity Y: {original_y} -> {test_y}")
        
        # Step 4: Update XML using normal method
        xml_updated = self.canvas.update_entity_xml(target_entity)
        if xml_updated:
            self.canvas._auto_save_entity_changes(target_entity)
            print(f"Ã°Å¸â€™Â¾ Updated and saved XML")
        
        # Step 5: Verify save
        self._verify_position_sync_in_file(target_entity.source_file_path, entity_name)
        
        # Step 6: Restore
        target_entity.y = original_y
        self.canvas.update_entity_xml(target_entity)
        self.canvas._auto_save_entity_changes(target_entity)
        
        print(f"Restored position")
        print(f"Test complete")

    def clear_entity_selection(self):
        """Clear entity selection in the tree"""
        self.entity_tree.clearSelection()
        
        # Also clear canvas selection
        if hasattr(self.canvas, 'selected'):
            self.canvas.selected = []
        if hasattr(self.canvas, 'selected_entity'):
            self.canvas.selected_entity = None
        
        # Update canvas
        self.canvas.update()
        
        # Update UI
        self.update_ui_for_selected_entity(None)
        
    def on_objects_loaded(self, objects):
        """Handle when objects are loaded from the thread - SIMPLIFIED"""
        print(f"Received {len(objects)} objects from loading thread")
        
        # Store objects
        self.objects = objects
        
        # Convert ObjectEntity objects to Entity objects for display compatibility
        converted_entities = []
        for obj in objects:
            try:
                # Create Entity object from ObjectEntity
                entity = Entity(
                    id=obj.id,
                    name=obj.name,
                    x=obj.x,
                    y=obj.y,
                    z=obj.z,
                    xml_element=obj.xml_element
                )
                
                # Set the source file path for XML updates
                entity.source_file_path = obj.source_file
                
                # Set source file type
                source_filename = os.path.basename(obj.source_file) if obj.source_file else ""
                if source_filename.startswith('worldsector') and source_filename.endswith('.data.xml'):
                    entity.source_file = "worldsectors"
                
                entity.map_name = obj.map_name
                converted_entities.append(entity)
                
            except Exception as e:
                print(f"Error converting object {obj.name}: {e}")
        
        # Add converted entities to the main entities list
        self.entities.extend(converted_entities)
        print(f"Added {len(converted_entities)} converted entities. Total entities: {len(self.entities)}")
        
        # Update canvas with combined entities
        self.canvas.set_entities(self.entities)
        
        # Update entity browser
        if hasattr(self, 'update_entity_tree'):
            self.update_entity_tree()
        
        # Update statistics
        if hasattr(self, 'update_entity_statistics'):
            self.update_entity_statistics()
        
        # Force canvas update
        self.canvas.update()
        print("Canvas updated with worldsectors objects")

    def save_xml_files(self):
        """Save all XML files without converting to FCB - UPDATED VERSION"""
        try:
            # Find all XML files that need saving
            files_to_save = []
            
            # 1. Main XML files (if loaded)
            if hasattr(self, 'xml_tree') and self.xml_tree and hasattr(self, 'xml_file_path'):
                files_to_save.append({
                    'type': 'main',
                    'path': self.xml_file_path,
                    'tree': self.xml_tree,
                    'name': os.path.basename(self.xml_file_path)
                })
            
            # 2. Other main XML files
            main_files = {
                'omnis_tree': 'omnis',
                'managers_tree': 'managers', 
                'sectordep_tree': 'sectorsdep'
            }
            
            for tree_attr, file_type in main_files.items():
                if hasattr(self, tree_attr):
                    tree = getattr(self, tree_attr)
                    if tree is not None:
                        file_path = self._find_tree_file_path(file_type)
                        if file_path:
                            files_to_save.append({
                                'type': file_type,
                                'path': file_path,
                                'tree': tree,
                                'name': os.path.basename(file_path)
                            })
            
            # 3. WorldSector XML files (from the loaded trees)
            if hasattr(self, 'worldsectors_trees'):
                for xml_file_path, tree in self.worldsectors_trees.items():
                    if os.path.exists(xml_file_path):
                        files_to_save.append({
                            'type': 'worldsector',
                            'path': xml_file_path,
                            'tree': tree,
                            'name': os.path.basename(xml_file_path)
                        })
            
            if not files_to_save:
                QMessageBox.information(self, "No Files to Save", "No XML files are currently loaded.")
                return
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Saving XML files, Please Wait.", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Saving XML Files")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            
            saved_files = []
            total_files = len(files_to_save)
            
            for i, file_info in enumerate(files_to_save):
                if progress_dialog.wasCanceled():
                    break
                    
                progress_dialog.setLabelText(f"Saving {file_info['name']}, Please Wait.")
                progress_dialog.setValue(int((i / total_files) * 100))
                QApplication.processEvents()
                
                try:
                    if file_info['type'] == 'worldsector':
                        # Use precision preservation for worldsector files
                        self.save_worldsector_xml_with_precision_preservation(file_info['tree'], file_info['path'])
                        saved_files.append(f"{file_info['name']} (precision preserved)")
                    else:
                        # Use precision preservation for main files too
                        self.save_xml_with_precision_preservation(file_info['tree'], file_info['path'])
                        saved_files.append(f"{file_info['name']}")
                    
                    print(f"Saved: {file_info['name']}")
                            
                except Exception as e:
                    saved_files.append(f"Ã¢Å“â€” {file_info['name']} - Error: {str(e)}")
                    print(f"Ã¢Å“â€” Failed to save {file_info['name']}: {e}")
            
            # Close progress dialog
            progress_dialog.setValue(100)
            progress_dialog.close()
            
            # Show results
            success_count = len([f for f in saved_files if f.startswith('Ã¢Å“â€œ')])
            error_count = len([f for f in saved_files if f.startswith('Ã¢Å“â€”')])
            
            if error_count == 0:
                QMessageBox.information(
                    self,
                    "XML Files Saved",
                    f"Successfully saved {success_count} XML files with precision preservation!\n\n" + 
                    "\n".join(saved_files)
                )
            else:
                QMessageBox.warning(
                    self,
                    "XML Save Complete with Errors", 
                    f"Saved {success_count} files successfully, {error_count} files had errors:\n\n" + 
                    "\n".join(saved_files)
                )
            
            # Update status
            self.status_bar.showMessage(f"Saved {success_count} XML files with precision preservation")
            
        except Exception as e:
            if 'progress_dialog' in locals():
                progress_dialog.close()
            QMessageBox.critical(self, "Error", f"Failed to save XML files: {str(e)}")

    def check_loaded_files(self):
        """Debug method to check what files are currently loaded"""
        print(f"\nLOADED FILES CHECK:")
        
        # Check main XML files
        print(f"Main XML files:")
        if hasattr(self, 'xml_tree') and self.xml_tree and hasattr(self, 'xml_file_path'):
            print(f"  Main: {os.path.basename(self.xml_file_path)}")
        else:
            print(f"  Main: Not loaded")
        
        # Check other main files
        main_files = ['omnis_tree', 'managers_tree', 'sectordep_tree']
        for tree_attr in main_files:
            if hasattr(self, tree_attr) and getattr(self, tree_attr) is not None:
                print(f"  {tree_attr}: Loaded")
            else:
                print(f"  {tree_attr}: Not loaded")
        
        # Check WorldSector files
        worldsector_files = set()
        for entity in self.entities:
            if hasattr(entity, 'source_file_path') and entity.source_file_path:
                if entity.source_file_path.endswith('.data.xml'):
                    worldsector_files.add(entity.source_file_path)
        
        print(f"WorldSector XML files:")
        if worldsector_files:
            for xml_file in worldsector_files:
                exists = "Ã¢Å“â€œ" if os.path.exists(xml_file) else "Ã¢ÂÅ’"
                print(f"  {exists} {os.path.basename(xml_file)}")
        else:
            print(f"  No WorldSector files found")
        
        print(f"Total entities: {len(self.entities)}")
        print(f"Total objects: {len(getattr(self, 'objects', []))}")

    def verify_worldsector_save(self, entity_name):
        """Verify that the entity coordinates were actually saved to the file"""
        print(f"\nVERIFY: Checking if {entity_name} coordinates were saved")
        
        # Find the entity
        target_entity = None
        for entity in self.entities:
            if entity.name == entity_name:
                target_entity = entity
                break
        
        if not target_entity:
            print(f"   Entity {entity_name} not found")
            return
        
        if not hasattr(target_entity, 'source_file_path'):
            print(f"   Entity has no source_file_path")
            return
        
        source_file = target_entity.source_file_path
        print(f"   Source file: {os.path.basename(source_file)}")
        print(f"   Current entity position: ({target_entity.x:.3f}, {target_entity.y:.3f}, {target_entity.z:.3f})")
        
        # Read the file fresh from disk
        try:
            import xml.etree.ElementTree as ET
            fresh_tree = ET.parse(source_file)
            root = fresh_tree.getroot()
            
            # Find the entity in the file
            for entity_elem in root.findall(".//object[@type='Entity']"):
                name_elem = entity_elem.find("./value[@name='hidName']")
                if name_elem is not None and name_elem.text == entity_name:
                    print(f"   Found entity in saved file")
                    
                    # Check hidPos
                    pos_elem = entity_elem.find("./value[@name='hidPos']")
                    if pos_elem is not None:
                        x_elem = pos_elem.find("./x")
                        y_elem = pos_elem.find("./y")
                        z_elem = pos_elem.find("./z")
                        
                        if all([x_elem is not None, y_elem is not None, z_elem is not None]):
                            file_pos = (float(x_elem.text), float(y_elem.text), float(z_elem.text))
                            entity_pos = (target_entity.x, target_entity.y, target_entity.z)
                            
                            print(f"   hidPos in file: ({file_pos[0]:.3f}, {file_pos[1]:.3f}, {file_pos[2]:.3f})")
                            print(f"   Entity position: ({entity_pos[0]:.3f}, {entity_pos[1]:.3f}, {entity_pos[2]:.3f})")
                            
                            # Check if they match (within small tolerance)
                            tolerance = 0.001
                            matches = (abs(file_pos[0] - entity_pos[0]) < tolerance and
                                    abs(file_pos[1] - entity_pos[1]) < tolerance and
                                    abs(file_pos[2] - entity_pos[2]) < tolerance)
                            
                            if matches:
                                print(f"   Coordinates match! Save was successful.")
                            else:
                                print(f"   Coordinates don't match! Save failed.")
                                
                    break
            else:
                print(f"   Entity not found in saved file")
                
        except Exception as e:
            print(f"   Error reading saved file: {e}")

    def save_objects(self):
        """Save objects back to FCB format"""
        if not self.objects or not self.worldsectors_path:
            QMessageBox.warning(self, "No Objects", "No objects loaded to save.")
            return
        
        reply = QMessageBox.question(
            self,
            "Save Objects",
            f"Convert {len(self.objects)} objects back to FCB format?\n\n"
            f"This will:\n"
            f"Save XML files with current object positions\n"
            f"Convert XML files back to FCB format\n"
            f"Remove temporary XML files\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # First, save any modified XML files
            self._save_modified_object_xml_files()
            
            # Create progress dialog
            progress_dialog = QProgressDialog("Saving objects, Please Wait.", "Cancel", 0, 100, self)
            progress_dialog.setWindowTitle("Saving Objects")
            progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)
            
            # Convert XML back to FCB
            def progress_callback(progress):
                progress_dialog.setValue(int(progress * 100))
                QApplication.processEvents()
            
            success_count, error_count, errors = self.file_converter.convert_worldsectors_back_to_fcb(
                self.worldsectors_path,
                progress_callback=progress_callback
            )
            
            progress_dialog.close()
            
            if error_count > 0:
                error_msg = "\n".join(errors[:5])
                if len(errors) > 5:
                    error_msg += f"\n... and {len(errors) - 5} more errors"
                
                QMessageBox.warning(
                    self,
                    "Save Completed with Errors",
                    f"Saved {success_count} files successfully.\n"
                    f"{error_count} files had errors:\n\n{error_msg}"
                )
            else:
                QMessageBox.information(
                    self,
                    "Objects Saved Successfully",
                    f"Successfully saved {success_count} object files!"
                )
            
            # Reset modification flag
            self.objects_modified = False
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save objects: {str(e)}")

    def _save_modified_object_xml_files(self):
        """Save modified object XML files before conversion"""
        modified_files = set()
        
        # Update XML elements with current object positions
        for obj in self.objects:
            if hasattr(obj, 'xml_element') and obj.xml_element is not None:
                # Update position in XML
                self._update_object_xml_position(obj)
                
                # Track which file this object belongs to
                if obj.source_file:
                    modified_files.add(obj.source_file)
        
        # Save each modified XML file
        for xml_file_path in modified_files:
            try:
                # Find the tree for this file
                tree = None
                for obj in self.objects:
                    if obj.source_file == xml_file_path and hasattr(obj, 'xml_element'):
                        # Create tree from the root element
                        root = obj.xml_element
                        while root.getparent() is not None:
                            root = root.getparent()
                        tree = ET.ElementTree(root)
                        break
                
                if tree:
                    tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
                    print(f"Saved modified object XML: {xml_file_path}")
                    
            except Exception as e:
                print(f"Error saving object XML {xml_file_path}: {str(e)}")

    def toggle_objects(self):
        """Toggle object visibility - ENHANCED VERSION"""
        if not hasattr(self, 'show_objects'):
            self.show_objects = True
        
        self.show_objects = not self.show_objects
        
        # Update the entities list shown in canvas
        if self.show_objects:
            # Show both entities and converted objects
            all_items = self.entities.copy()  # This should already include converted worldsectors objects
        else:
            # Show only non-worldsectors entities
            all_items = [entity for entity in self.entities if getattr(entity, 'source_file', None) != 'worldsectors']
        
        self.canvas.set_entities(all_items)
        self.canvas.update()
        
        visibility = "visible" if self.show_objects else "hidden"
        self.status_bar.showMessage(f"WorldSectors objects visibility: {visibility}")
        print(f"Objects visibility toggled: {visibility}, showing {len(all_items)} entities")
    
    def _update_object_xml_position(self, obj):
        """Update the XML element with the current object position"""
        if not hasattr(obj, 'xml_element') or obj.xml_element is None:
            return False
        
        try:
            import struct
            
            # Find hidPos field
            pos_field = obj.xml_element.find(".//field[@name='hidPos']")
            if pos_field is not None:
                # Update the value-Vector3 attribute
                pos_field.set('value-Vector3', f"{obj.x},{obj.y},{obj.z}")
                
                # Update the BinHex data
                pos_bytes = struct.pack('<fff', obj.x, obj.y, obj.z)
                pos_field.set('type', 'BinHex')
                pos_field.text = pos_bytes.hex().upper()
            
            # Also update hidPos_precise if it exists
            pos_precise_field = obj.xml_element.find(".//field[@name='hidPos_precise']")
            if pos_precise_field is not None:
                # Update the value-Vector3 attribute
                pos_precise_field.set('value-Vector3', f"{obj.x},{obj.y},{obj.z}")
                
                # Update the BinHex data
                pos_bytes = struct.pack('<fff', obj.x, obj.y, obj.z)
                pos_precise_field.set('type', 'BinHex')
                pos_precise_field.text = pos_bytes.hex().upper()
            
            return True
            
        except Exception as e:
            print(f"Error updating object XML position: {e}")
            return False
    
    def setup_conversion_tools(self):
        """Setup the file conversion tools (internal use only)"""
        import sys
        
        # Get correct tools directory for exe vs script
        if getattr(sys, 'frozen', False):
            # Running as exe - use executable directory
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script - use script directory  
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        tools_dir = os.path.join(base_dir, "tools")
        
        if not os.path.exists(tools_dir):
            os.makedirs(tools_dir)
        
        # Check for conversion tools
        xml_converter_path = os.path.join(tools_dir, "Gibbed.Dunia.ConvertXml.exe")
        binary_converter_path = os.path.join(tools_dir, "Gibbed.Dunia.ConvertBinary.exe")
        
        missing_tools = []
        if not os.path.exists(xml_converter_path):
            missing_tools.append("Gibbed.Dunia.ConvertXml.exe")
        if not os.path.exists(binary_converter_path):
            missing_tools.append("Gibbed.Dunia.ConvertBinary.exe")
        
        # Just log the missing tools, don't display to user
        if missing_tools:
            print(f"WARNING: Missing conversion tools: {', '.join(missing_tools)}")
            print(f"Some file conversions may not be available.")
        
        # Initialize the file converter with error handling
        try:
            print(f"Initializing FileConverter with tools_dir: {tools_dir}")
            self.file_converter = FileConverter(tools_dir)
            print("File converter initialized successfully")
        except Exception as e:
            print(f"Error initializing FileConverter: {e}")
            import traceback
            traceback.print_exc()
            self.file_converter = None
            raise  # Re-raise to trigger the fallback in __init__
        
        return len(missing_tools) == 0

    def find_worldsectors_folder_enhanced(self, base_folder):
        """
        Enhanced search for worldsectors folder and files
        
        Args:
            base_folder: Base folder to search in
            
        Returns:
            Dict with worldsectors path and file counts
        """
        print(f"Searching for worldsectors in: {base_folder}")
        
        # Common worldsectors folder names
        worldsectors_folder_names = [
            "worldsectors",
            "Worldsectors", 
            "WorldSectors",
            "worldsector",
            "sectors"
        ]
        
        # Search for worldsectors folders
        worldsectors_paths = []
        
        # 1. Check direct subfolders
        for folder_name in worldsectors_folder_names:
            potential_path = os.path.join(base_folder, folder_name)
            if os.path.exists(potential_path) and os.path.isdir(potential_path):
                worldsectors_paths.append(potential_path)
                print(f"  Found worldsectors folder: {folder_name}")
        
        # 2. Search in subfolders (up to 2 levels deep)
        for root, dirs, files in os.walk(base_folder):
            # Limit depth
            depth = len(os.path.relpath(root, base_folder).split(os.sep))
            if depth > 2:
                continue
            
            for dir_name in dirs:
                if dir_name.lower() in [name.lower() for name in worldsectors_folder_names]:
                    potential_path = os.path.join(root, dir_name)
                    if potential_path not in worldsectors_paths:
                        worldsectors_paths.append(potential_path)
                        relative_path = os.path.relpath(potential_path, base_folder)
                        print(f"  Found worldsectors folder: {relative_path}")
        
        # 3. If no worldsectors folder found, check if base folder contains .data.fcb files
        if not worldsectors_paths:
            fcb_files = glob.glob(os.path.join(base_folder, "*.data.fcb"))
            converted_files = glob.glob(os.path.join(base_folder, "*.converted.xml"))
            
            if fcb_files or converted_files:
                worldsectors_paths.append(base_folder)
                print(f"  Base folder contains worldsector files ({len(fcb_files)} .fcb, {len(converted_files)} .converted.xml)")
        
        if not worldsectors_paths:
            return None
        
        # Choose the best worldsectors folder (prefer one with most files)
        best_path = None
        best_score = 0
        
        for ws_path in worldsectors_paths:
            fcb_count = len(glob.glob(os.path.join(ws_path, "*.data.fcb")))
            xml_count = len(glob.glob(os.path.join(ws_path, "*.converted.xml")))
            data_xml_count = len(glob.glob(os.path.join(ws_path, "*.data.xml")))
            
            score = fcb_count * 2 + xml_count + data_xml_count  # Prefer FCB files
            
            print(f"  {os.path.relpath(ws_path, base_folder)}: {fcb_count} .fcb, {xml_count} .converted.xml, {data_xml_count} .data.xml (score: {score})")
            
            if score > best_score:
                best_score = score
                best_path = ws_path
        
        if best_path:
            return {
                "path": best_path,
                "fcb_files": len(glob.glob(os.path.join(best_path, "*.data.fcb"))),
                "xml_files": len(glob.glob(os.path.join(best_path, "*.converted.xml"))),
                "data_xml_files": len(glob.glob(os.path.join(best_path, "*.data.xml"))),
                "relative_path": os.path.relpath(best_path, base_folder)
            }
        
        return None

    def find_files_in_subfolders(self, base_folder, patterns, max_depth=3):
        """
        Search for files matching patterns in base folder and subfolders
        
        Args:
            base_folder: Root folder to search
            patterns: List of file patterns to match (e.g., ['*.xml', '*.fcb'])
            max_depth: Maximum depth to search (default 3)
        
        Returns:
            Dict of {pattern: [matching_files]}
        """
        found_files = {pattern: [] for pattern in patterns}
        
        def search_folder(folder_path, current_depth):
            if current_depth > max_depth:
                return
            
            try:
                # Search current folder
                for pattern in patterns:
                    matches = glob.glob(os.path.join(folder_path, pattern))
                    found_files[pattern].extend(matches)
                
                # Search subfolders
                if current_depth < max_depth:
                    for item in os.listdir(folder_path):
                        item_path = os.path.join(folder_path, item)
                        if os.path.isdir(item_path):
                            search_folder(item_path, current_depth + 1)
            except PermissionError:
                # Skip folders we can't access
                pass
            except Exception as e:
                print(f"Error searching {folder_path}: {e}")
        
        search_folder(base_folder, 0)
        return found_files
        
    def find_xml_files_enhanced(self, folder_path):
        """Enhanced XML file finder that searches subfolders - FIXED VERSION"""
        print(f"Enhanced search in: {folder_path}")
        
        # Search patterns for main files
        main_patterns = [
            "*.mapsdata.fcb", "*.mapsdata.xml",
            "*.managers.fcb", "*.managers.xml", 
            "*.omnis.fcb", "*.omnis.xml",
            "*.sectorsdep.fcb", "*.sectorsdep.xml",
            "mapsdata.fcb", "mapsdata.xml",
            "managers.fcb", "managers.xml",
            "omnis.fcb", "omnis.xml", 
            "sectorsdep.fcb", "sectorsdep.xml"
        ]

        # Search for files
        search_results = self.find_files_in_subfolders(folder_path, main_patterns)
        
        # Organize results by file type
        found_files = {}
        
        # Find mapsdata file first to get level name
        level_name = None
        mapsdata_files = []
        
        for pattern in ["*.mapsdata.fcb", "*.mapsdata.xml", "mapsdata.fcb", "mapsdata.xml"]:
            mapsdata_files.extend(search_results[pattern])
        
        if mapsdata_files:
            main_file = mapsdata_files[0]
            filename = os.path.basename(main_file)
            if '.mapsdata.' in filename:
                level_name = filename.split('.mapsdata.')[0]
            print(f"Level name detected: {level_name}")
            
            # Convert FCB to XML if needed
            if main_file.endswith('.fcb'):
                xml_file = main_file.replace('.fcb', '.xml')
                try:
                    success = self.file_converter.convert_fcb_to_xml(main_file)
                    if success and os.path.exists(xml_file):
                        found_files["mapsdata"] = {
                            "path": xml_file,
                            "description": "Map Data",
                            "original_fcb": main_file,
                            "location": os.path.relpath(os.path.dirname(xml_file), folder_path)
                        }
                except Exception as e:
                    print(f"Error converting {main_file}: {e}")
            else:
                found_files["mapsdata"] = {
                    "path": main_file,
                    "description": "Map Data", 
                    "original_fcb": None,
                    "location": os.path.relpath(os.path.dirname(main_file), folder_path)
                }
        
        # Find other files using the same logic
        file_types = {
            "omnis": {
                "patterns": [f"{level_name}.omnis.fcb", f"{level_name}.omnis.xml", ".omnis.fcb", ".omnis.xml"] if level_name else [".omnis.fcb", ".omnis.xml"],
                "description": "Omnis Data"
            },
            "managers": {
                "patterns": [f"{level_name}.managers.fcb", f"{level_name}.managers.xml", ".managers.fcb", ".managers.xml"] if level_name else [".managers.fcb", ".managers.xml"],
                "description": "Managers Data"
            },
            "sectorsdep": {
                "patterns": [f"{level_name}.sectorsdep.fcb", f"{level_name}.sectorsdep.xml", "sectorsdep.fcb", "sectorsdep.xml"] if level_name else ["sectorsdep.fcb", "sectorsdep.xml"],
                "description": "Sector Dependencies"
            }
        }

        for file_type, info in file_types.items():
            for pattern in info["patterns"]:
                # Look for exact matches first
                matching_files = []
                for search_pattern in main_patterns:
                    if pattern in search_results.get(search_pattern, []):
                        matching_files.extend([f for f in search_results[search_pattern] if os.path.basename(f) == pattern])
                
                if matching_files:
                    file_path = matching_files[0]
                    
                    # Standard handling for all files using Gibbed tools
                    if file_path.endswith('.fcb'):
                        xml_file = file_path.replace('.fcb', '.xml')
                        try:
                            success = self.file_converter.convert_fcb_to_xml(file_path)
                            if success and os.path.exists(xml_file):
                                found_files[file_type] = {
                                    "path": xml_file,
                                    "description": info["description"],
                                    "original_fcb": file_path,
                                    "location": os.path.relpath(os.path.dirname(xml_file), folder_path)
                                }
                            break
                        except Exception as e:
                            print(f"Error converting {file_path}: {e}")
                            continue
                    else:
                        # Already XML - use directly
                        found_files[file_type] = {
                            "path": file_path,
                            "description": info["description"],
                            "original_fcb": None,
                            "location": os.path.relpath(os.path.dirname(file_path), folder_path)
                        }
                    break

        return found_files

    def open_entity_editor(self):
            """Open or show the entity editor window - FIXED IMPORT"""
            
            # Try multiple import methods
            EntityEditorWindow = None
            
            # Method 1: Try direct import
            try:
                from entity_editor import EntityEditorWindow
                print("Successfully imported EntityEditorWindow from entity_editor.py")
            except ImportError as e1:
                print(f"Failed direct import: {e1}")
                
                # Method 2: Try importing from current directory
                try:
                    import sys
                    import os
                    current_dir = os.path.dirname(__file__)
                    if current_dir not in sys.path:
                        sys.path.insert(0, current_dir)
                    from entity_editor import EntityEditorWindow
                    print("Successfully imported EntityEditorWindow from current directory")
                except ImportError as e2:
                    print(f"Failed current directory import: {e2}")
                    
                    # Method 3: Try to find the file and give helpful error
                    try:
                        import os
                        current_dir = os.path.dirname(__file__) if hasattr(self, '__file__') else os.getcwd()
                        entity_editor_path = os.path.join(current_dir, "entity_editor.py")
                        
                        if os.path.exists(entity_editor_path):
                            error_msg = f"Entity editor file exists at {entity_editor_path} but import failed.\nError: {e2}"
                        else:
                            # Look for the file in nearby directories
                            found_files = []
                            for root, dirs, files in os.walk(current_dir):
                                if "entity_editor.py" in files:
                                    found_files.append(os.path.join(root, "entity_editor.py"))
                            
                            if found_files:
                                error_msg = f"Entity editor file found at:\n" + "\n".join(found_files[:3])
                                error_msg += f"\n\nMove one of these files to: {current_dir}"
                            else:
                                error_msg = f"Entity editor file not found!\n\nCurrent directory: {current_dir}\nExpected file: {entity_editor_path}\n\nPlease create entity_editor.py in the same directory as your main application."
                        
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.critical(self, "Entity Editor Import Error", error_msg)
                        return
                        
                    except Exception as e3:
                        from PyQt6.QtWidgets import QMessageBox
                        QMessageBox.critical(self, "Entity Editor Error", 
                                        f"Could not import Entity Editor:\n{e1}\n\nAlso failed to diagnose the problem:\n{e3}")
                        return
            
            # If we get here, import was successful
            if EntityEditorWindow is None:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", "EntityEditorWindow class not found after import!")
                return
            
            # Create editor if it doesn't exist
            if not hasattr(self, 'entity_editor') or self.entity_editor is None:
                try:
                    print("=== Creating new Entity Editor window ===")
                    self.entity_editor = EntityEditorWindow(self, self.canvas)
                    print("Successfully created EntityEditorWindow instance")
                    
                    # Set current entity if one is selected
                    if hasattr(self.canvas, 'selected') and self.canvas.selected:
                        entity = self.canvas.selected[0]
                        print(f"ðŸ“ Entity Editor: Opening with entity '{entity.name}' (ID: {entity.id})")
                        self.entity_editor.set_entity(entity)
                    elif hasattr(self.canvas, 'selected_entity') and self.canvas.selected_entity:
                        entity = self.canvas.selected_entity
                        print(f"ðŸ“ Entity Editor: Opening with entity '{entity.name}' (ID: {entity.id})")
                        self.entity_editor.set_entity(entity)
                    else:
                        print("âš ï¸ Entity Editor: No entity currently selected")
                        
                except Exception as e:
                    from PyQt6.QtWidgets import QMessageBox
                    import traceback
                    error_details = traceback.format_exc()
                    QMessageBox.critical(self, "Entity Editor Creation Error", 
                                    f"Failed to create Entity Editor:\n{str(e)}\n\nDetails:\n{error_details}")
                    print(f"Entity Editor creation failed: {e}")
                    print(f"Full traceback:\n{error_details}")
                    return
            else:
                # Editor already exists, just update the entity
                print("=== Entity Editor window already exists ===")
                if hasattr(self.canvas, 'selected') and self.canvas.selected:
                    entity = self.canvas.selected[0]
                    print(f"ðŸ“ Entity Editor: Updating to entity '{entity.name}' (ID: {entity.id})")
                    self.entity_editor.set_entity(entity)
                elif hasattr(self.canvas, 'selected_entity') and self.canvas.selected_entity:
                    entity = self.canvas.selected_entity
                    print(f"ðŸ“ Entity Editor: Updating to entity '{entity.name}' (ID: {entity.id})")
                    self.entity_editor.set_entity(entity)
                else:
                    print("âš ï¸ Entity Editor: No entity currently selected to update")
            
            # Show and raise the window
            try:
                self.entity_editor.show()
                self.entity_editor.raise_()
                self.entity_editor.activateWindow()
                if hasattr(self, 'current_entity') or (hasattr(self.canvas, 'selected') and self.canvas.selected):
                    entity_name = self.canvas.selected[0].name if (hasattr(self.canvas, 'selected') and self.canvas.selected) else "Unknown"
                    print(f"âœ… Entity Editor window opened successfully with '{entity_name}'")
                else:
                    print("âœ… Entity Editor window opened successfully (no entity loaded)")
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", f"Failed to show Entity Editor window:\n{str(e)}")
                print(f"Failed to show Entity Editor: {e}")

    def toggle_grid(self):
        """Toggle grid visibility"""
        self.canvas.show_grid = not self.canvas.show_grid
        self.canvas.update()
        
        visibility = "visible" if self.canvas.show_grid else "hidden"
        self.status_bar.showMessage(f"Grid visibility: {visibility}")
    
    def toggle_entities(self):
        """Toggle entities visibility"""
        self.canvas.show_entities = not self.canvas.show_entities
        self.canvas.update()
        
        visibility = "visible" if self.canvas.show_entities else "hidden"
        self.status_bar.showMessage(f"Entities visibility: {visibility}")
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.force_dark_theme = not self.force_dark_theme
        self.apply_theme()
        
        # Update button text
        if self.force_dark_theme:
            self.theme_toggle_action.setText("Light Mode")
            self.status_bar.showMessage("Dark theme enabled")
        else:
            self.theme_toggle_action.setText("Dark Mode")
            self.status_bar.showMessage("Light theme enabled")
        
        # Force the entity tree to update colors immediately
        if hasattr(self, 'entity_tree'):
            self.force_refresh_entity_tree_colors()
    
    def toggle_invert_mouse(self):
        """Toggle mouse pan inversion"""
        self.invert_mouse_pan = not self.invert_mouse_pan
        if hasattr(self.canvas, 'invert_mouse_pan'):
            self.canvas.invert_mouse_pan = self.invert_mouse_pan
        status = "enabled" if self.invert_mouse_pan else "disabled"
        self.status_bar.showMessage(f"Inverted mouse pan {status}")
    
    def apply_theme(self):
        """Apply the selected theme to the application"""
        if self.force_dark_theme:
            # Dark theme stylesheet
            dark_style = """
                QWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QGroupBox {
                    background-color: #353535;
                    border: 1px solid #555555;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: #ffffff;
                }
                QGroupBox::title {
                    color: #ffffff;
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 5px;
                }
                QPushButton {
                    background-color: #404040;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #4a4a4a;
                }
                QPushButton:pressed {
                    background-color: #353535;
                }
                QPushButton:checked {
                    background-color: #0078d7;       /* Same blue as light mode */
                    border: 1px solid #005a9e;
                    color: #ffffff;
                }
                QPushButton:checked:hover {
                    background-color: #1e88e5;
                }
                QLabel {
                    color: #ffffff;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: #353535;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 2px;
                }
                QComboBox {
                    background-color: #353535;
                    color: #ffffff;
                    border: 1px solid #555555;
                    border-radius: 3px;
                    padding: 2px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #ffffff;
                }
                QComboBox QAbstractItemView {
                    background-color: #353535;
                    color: #ffffff;
                    selection-background-color: #404040;
                }
                QTreeWidget {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QTreeWidget::item:selected {
                    background-color: #404040;
                    color: #ffffff;
                }
                QTextEdit {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QScrollBar:vertical {
                    background-color: #2b2b2b;
                    width: 12px;
                }
                QScrollBar::handle:vertical {
                    background-color: #555555;
                    border-radius: 6px;
                }
                QScrollBar:horizontal {
                    background-color: #2b2b2b;
                    height: 12px;
                }
                QScrollBar::handle:horizontal {
                    background-color: #555555;
                    border-radius: 6px;
                }
                QMenuBar {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QMenuBar::item:selected {
                    background-color: #404040;
                }
                QMenu {
                    background-color: #2b2b2b;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QMenu::item:selected {
                    background-color: #404040;
                }
                QStatusBar {
                    background-color: #2b2b2b;
                    color: #ffffff;
                }
                QDockWidget {
                    color: #ffffff;
                }
                QDockWidget::title {
                    background-color: #353535;
                    color: #ffffff;
                    padding: 4px;
                }
                QToolBar {
                    background-color: #2b2b2b;
                    border: 1px solid #555555;
                }
                QToolBar QToolButton {
                    color: #ffffff;
                    background-color: transparent;
                }
                QToolBar QToolButton:hover {
                    background-color: #404040;
                }
                QToolBar QToolButton:checked {
                    background-color: #0078d7;       /* Match light mode */
                    border: 1px solid #005a9e;
                    color: #ffffff;
                }
                QToolBar QToolButton:checked:hover {
                    background-color: #1e88e5;
                }
                QToolBar::separator {
                    background-color: #555555;
                    width: 1px;
                }
                QHeaderView::section {
                    background-color: #353535;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QTabWidget::pane {
                    border: 1px solid #555555;
                    background-color: #2b2b2b;
                }
                QTabBar::tab {
                    background-color: #353535;
                    color: #ffffff;
                    border: 1px solid #555555;
                    padding: 5px;
                }
                QTabBar::tab:selected {
                    background-color: #404040;
                }
            """
            self.setStyleSheet(dark_style)
        else:
            # Light theme stylesheet
            light_style = """
                QWidget {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #c0c0c0;
                    border-radius: 5px;
                    margin-top: 10px;
                    padding-top: 10px;
                    color: #000000;
                }
                QGroupBox::title {
                    color: #000000;
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 2px 5px;
                }
                QPushButton {
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                    border-radius: 3px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #d0d0d0;
                }
                QPushButton:pressed {
                    background-color: #c0c0c0;
                }
                QPushButton:checked {
                    background-color: #0078d7;
                    color: #ffffff;
                    border: 1px solid #005a9e;
                }
                QPushButton:checked:hover {
                    background-color: #1e88e5;
                }
                QLabel {
                    color: #000000;
                    background-color: transparent;
                }
                QLineEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QComboBox {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #000000;
                }
                QTreeWidget {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QTreeWidget::item:selected {
                    background-color: #0078d7;
                    color: #ffffff;
                }
                QTextEdit {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QMenuBar {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QMenuBar::item:selected {
                    background-color: #e0e0e0;
                }
                QMenu {
                    background-color: #ffffff;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QMenu::item:selected {
                    background-color: #0078d7;
                    color: #ffffff;
                }
                QStatusBar {
                    background-color: #f0f0f0;
                    color: #000000;
                }
                QDockWidget {
                    color: #000000;
                }
                QDockWidget::title {
                    background-color: #e0e0e0;
                    color: #000000;
                    padding: 4px;
                }
                QToolBar {
                    background-color: #f0f0f0;
                    border: 1px solid #c0c0c0;
                }
                QToolBar QToolButton {
                    color: #000000;
                    background-color: transparent;
                }
                QToolBar QToolButton:hover {
                    background-color: #e0e0e0;
                }
                QToolBar QToolButton:checked {
                    background-color: #0078d7;
                    border: 1px solid #005a9e;
                    color: #ffffff;
                }
                QToolBar QToolButton:checked:hover {
                    background-color: #1e88e5;
                }
                QHeaderView::section {
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                }
                QTabWidget::pane {
                    border: 1px solid #b0b0b0;
                    background-color: #ffffff;
                }
                QTabBar::tab {
                    background-color: #e0e0e0;
                    color: #000000;
                    border: 1px solid #b0b0b0;
                    padding: 5px;
                }
                QTabBar::tab:selected {
                    background-color: #ffffff;
                }
            """
            self.setStyleSheet(light_style)

        # ðŸ”„ Update entity color legend text colors dynamically
        if hasattr(self, "entity_colors_header"):
            if self.force_dark_theme:
                self.entity_colors_header.setStyleSheet("color: white; margin-bottom: 8px; padding: 2px;")
                for label in getattr(self, "color_legend_labels", []):
                    label.setStyleSheet("color: white;")
            else:
                self.entity_colors_header.setStyleSheet("color: black; margin-bottom: 8px; padding: 2px;")
                for label in getattr(self, "color_legend_labels", []):
                    label.setStyleSheet("color: black;")
    
    def force_canvas_update(self):
        """Force the canvas to update and redraw entities"""
        if hasattr(self, 'canvas'):
            print("Forcing canvas update, Please wait.")
            
            # Ensure entities are set
            if hasattr(self, 'entities') and self.entities:
                print(f"Re-applying {len(self.entities)} entities to canvas")
                self.canvas.set_entities(self.entities)
            
            # Reset the view if needed
            self.reset_view()
            
            # Force a redraw
            self.canvas.update()
            
            # Force the application to process events
            QApplication.processEvents()

    
    def save_xml_with_precision_preservation(self, tree, file_path):
        """Save XML while preserving original floating-point precision"""
        try:
            # Create backup first
            backup_path = file_path + ".precision_backup"
            if os.path.exists(file_path):
                shutil.copy2(file_path, backup_path)
            
            # Save with minimal changes to preserve precision
            root = tree.getroot()
            
            # Don't use pretty printing - it can change precision
            # Write directly as-is
            tree.write(file_path, encoding='utf-8', xml_declaration=False)
            
            print(f"Saved with precision preservation: {file_path}")
            
        except Exception as e:
            print(f"Error saving XML with precision preservation: {e}")
            raise

    def _find_tree_file_path(self, tree_type):
        """Find the file path for a specific tree type using proper naming"""
        if not hasattr(self, 'xml_file_path') or not self.xml_file_path:
            return None
        
        folder_path = os.path.dirname(self.xml_file_path)
        
        # Get the level name from the main XML file
        # For example: "z_anim_creatures.mapsdata.xml" -> "z_anim_creatures"
        main_filename = os.path.basename(self.xml_file_path)
        if '.mapsdata.' in main_filename:
            level_name = main_filename.split('.mapsdata.')[0]
        else:
            # Fallback if naming doesn't match expected pattern
            level_name = os.path.splitext(main_filename)[0]
        
        print(f"Looking for {tree_type} file with level name: {level_name}")
        
        # Define the correct naming patterns for each file type
        file_patterns = {
            'omnis': [
                f"{level_name}.omnis.xml",     # z_anim_creatures.omnis.xml
                f"{level_name}.omnis.fcb",     # z_anim_creatures.omnis.fcb (original)
                ".omnis.xml",                  # fallback
                ".omnis.fcb"                   # fallback
            ],
            'managers': [
                f"{level_name}.managers.xml",   # z_anim_creatures.managers.xml
                f"{level_name}.managers.fcb",   # z_anim_creatures.managers.fcb (original)
                ".managers.xml",                # fallback
                ".managers.fcb"                 # fallback
            ],
            'sectorsdep': [
                f"{level_name}.sectorsdep.xml", # z_anim_creatures.sectorsdep.xml
                f"{level_name}.sectorsdep.fcb", # z_anim_creatures.sectorsdep.fcb (original)
                "sectorsdep.xml",               # fallback
                "sectorsdep.fcb",               # fallback
                "sectordep.xml",                # alternative naming
                "sectordep.fcb"                 # alternative naming
            ]
        }
        
        if tree_type not in file_patterns:
            return None
        
        # Try to find existing file (prefer XML, then FCB)
        for pattern in file_patterns[tree_type]:
            file_path = os.path.join(folder_path, pattern)
            if os.path.exists(file_path):
                print(f"Found existing file: {pattern}")
                
                # If it's an FCB file, we need to return the XML equivalent
                if file_path.endswith('.fcb'):
                    xml_path = file_path.replace('.fcb', '.xml')
                    print(f"FCB file found, XML equivalent would be: {os.path.basename(xml_path)}")
                    return xml_path
                else:
                    return file_path
        
        # If no existing file found, return the preferred XML path (with level name)
        preferred_path = os.path.join(folder_path, f"{level_name}.{tree_type}.xml")
        print(f"No existing file found, using preferred path: {os.path.basename(preferred_path)}")
        return preferred_path

    def update_ui_for_selected_entity(self, entity):
        """Update UI when an entity is selected - MODE AWARE"""
        if entity:
            # Get source_file attribute safely
            source_file = getattr(entity, 'source_file', None)
            source_text = f"Source: {source_file}" if source_file else "Source: unknown"
            
            # Get current mode
            mode_text = "2D Mode" if self.canvas.mode == 0 else "3D Mode"
            
            # Build selection info text
            selection_text = (
                f"Selected: {entity.name}\n"
                f"Position: ({entity.x:.2f}, {entity.y:.2f}, {entity.z:.2f})\n"
                f"{source_text}\n"
                f"View: {mode_text}"
            )
            
            self.selected_entity_label.setText(selection_text)
            
            # Update status bar
            self.status_bar.showMessage(
                f"Selected: {entity.name} at ({entity.x:.0f}, {entity.y:.0f}, {entity.z:.0f}) | {mode_text}"
            )
        else:
            mode_text = "2D Mode" if self.canvas.mode == 0 else "3D Mode"
            self.selected_entity_label.setText(f"No entity selected\nView: {mode_text}")
            self.status_bar.showMessage(f"No selection | {mode_text}")

    def update_entity_statistics(self):
        """Update entity and object statistics by source file and type - ENHANCED VERSION"""
        try:
            # Count entities from each source
            entity_stats = {
                "mapsdata": 0,
                "managers": 0,
                "omnis": 0,
                "sectorsdep": 0,
                "worldsectors": 0,  # Add worldsectors category
                "preload": 0,
                "particles": 0,
                "unknown": 0
            }
            
            # Count entities by source
            for entity in self.entities:
                source = getattr(entity, 'source_file', None)
                if not source:
                    source = "unknown"
                    entity_stats["unknown"] += 1
                elif source.startswith("particles_"):
                    entity_stats["particles"] += 1
                elif source in entity_stats:
                    entity_stats[source] += 1
                else:
                    entity_stats["unknown"] += 1
            
            # Count objects separately
            object_stats_by_type = {}
            object_stats_by_sector = {}
            
            for obj in self.objects:
                # Count by object type
                obj_type = getattr(obj, 'object_type', 'Unknown')
                if obj_type not in object_stats_by_type:
                    object_stats_by_type[obj_type] = 0
                object_stats_by_type[obj_type] += 1
                
                # Count by sector
                sector_path = getattr(obj, 'sector_path', None)
                if sector_path:
                    sector_name = os.path.basename(sector_path)
                    if sector_name not in object_stats_by_sector:
                        object_stats_by_sector[sector_name] = 0
                    object_stats_by_sector[sector_name] += 1
            
            # Build statistics text
            total_entities = len(self.entities)
            total_objects = len(self.objects)
            
            stats_text = f"Total: {total_entities} entities"
            if total_objects > 0:
                stats_text += f" + {total_objects} objects"
            
            # Add entity breakdown
            if total_entities > 0:
                entity_breakdown = []
                for source, count in entity_stats.items():
                    if count > 0:
                        entity_breakdown.append(f"{count} {source}")
                
                if entity_breakdown:
                    stats_text += f"\nEntities: " + ", ".join(entity_breakdown)
            
            # Add object breakdown if we have objects
            if total_objects > 0:
                sorted_obj_types = sorted(object_stats_by_type.items(), key=lambda x: x[1], reverse=True)
                top_obj_types = sorted_obj_types[:3]
                
                obj_breakdown = []
                for obj_type, count in top_obj_types:
                    obj_breakdown.append(f"{count} {obj_type}")
                
                if len(sorted_obj_types) > 3:
                    others_count = sum(count for _, count in sorted_obj_types[3:])
                    obj_breakdown.append(f"{others_count} others")
                
                if obj_breakdown:
                    stats_text += f"\nObjects: " + ", ".join(obj_breakdown)
                
                if object_stats_by_sector:
                    sector_count = len(object_stats_by_sector)
                    stats_text += f"\nFrom {sector_count} sectors"
            
            # Update UI
            self.entity_count_label.setText(stats_text)
            
            # Status bar message
            if total_objects > 0:
                status_message = f"Loaded {total_entities} entities and {total_objects} objects"
            else:
                status_message = f"Loaded {total_entities} entities"
            
            self.status_bar.showMessage(status_message)
            
            print(f"Statistics: {total_entities} entities, {total_objects} objects")
            print(f"Entity breakdown: {entity_stats}")
            
        except Exception as e:
            print(f"Error updating statistics: {str(e)}")
            # Fallback
            try:
                total_entities = len(self.entities) if hasattr(self, 'entities') else 0
                total_objects = len(self.objects) if hasattr(self, 'objects') else 0
                self.entity_count_label.setText(f"Entities: {total_entities}, Objects: {total_objects}")
            except:
                self.entity_count_label.setText("Statistics unavailable")

    def change_to_topdownview(self):
        """Simplified - no mode switching needed"""
        # Since we only have 2D mode now, this just ensures we're in the right state
        self.statusBar().showMessage("2D top-down view active")

    def update_side_panel_for_2d(self):
        """Update side panel UI elements for 2D mode - SIMPLIFIED"""
        # Since we only have 2D mode, this can be simplified or removed
        # Update the entity info panel if needed
        self.update_ui_for_selected_entity(self.selected_entity)

    def keyPressEvent(self, event):
        """Handle key press events - WITH 2D/3D MODE SUPPORT"""
        
        # TAB KEY - Toggle between 2D and 3D
        if event.key() == Qt.Key.Key_Tab:
            if hasattr(self.canvas, 'toggle_view_mode'):
                old_mode = self.canvas.mode
                self.canvas.toggle_view_mode()
                new_mode = self.canvas.mode
                
                print(f"Mode toggled from {old_mode} to {new_mode}")
                
                # Update status bar with mode-specific tips
                if self.canvas.mode == 0:  # 2D mode
                    mode_name = "2D Top-Down View"
                    tips = "WASD: Pan | Wheel: Zoom | Left-Click: Select | Tab: Switch to 3D"
                    print("Switched to 2D mode")
                else:  # 3D mode
                    mode_name = "3D Perspective View"
                    tips = "WASD: Move | QE: Up/Down | Mouse: Look Around | Tab: Switch to 2D"
                    print("Switched to 3D mode")
                
                self.statusBar().showMessage(f"Mode: {mode_name} | {tips}", 5000)
                
                # Update mode indicator if it exists
                if hasattr(self, 'update_mode_indicator'):
                    self.update_mode_indicator()
                    
            event.accept()
            return
        
        # F1 - Help (mode-aware)
        if event.key() == Qt.Key.Key_F1:
            self.show_help_dialog_with_3d()
            event.accept()
            return
        
        # G - Toggle grid (works in both modes)
        if event.key() == Qt.Key.Key_G:
            self.toggle_grid()
            event.accept()
            return
        
        # E - Toggle entities (works in both modes)
        if event.key() == Qt.Key.Key_E:
            self.toggle_entities()
            event.accept()
            return
        
        # R - Reset view (mode-aware)
        if event.key() == Qt.Key.Key_R:
            self.reset_view()
            event.accept()
            return
        
        # Delete - Delete selected entities (works in both modes)
        if event.key() == Qt.Key.Key_Delete:
            if hasattr(self, 'delete_selected_entities'):
                self.delete_selected_entities()
                event.accept()
                return
        
        # Ctrl+C - Copy (works in both modes)
        if event.key() == Qt.Key.Key_C and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if hasattr(self, 'copy_selected_entities'):
                self.copy_selected_entities()
                event.accept()
                return
        
        # Ctrl+V - Paste (works in both modes)
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if hasattr(self, 'paste_entities'):
                self.paste_entities()
                event.accept()
                return
        
        # Ctrl+D - Duplicate (works in both modes)
        if event.key() == Qt.Key.Key_D and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if hasattr(self, 'duplicate_selected_entities'):
                self.duplicate_selected_entities()
                event.accept()
                return
        
        # Ctrl+E - Entity Editor (works in both modes)
        if event.key() == Qt.Key.Key_E and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if hasattr(self, 'open_entity_editor'):
                self.open_entity_editor()
                event.accept()
                return
        
        # Pass other keys to canvas (handles WASD differently per mode)
        if hasattr(self, 'canvas'):
            self.canvas.keyPressEvent(event)
        
        # Call parent handler for any unhandled keys
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """Handle key release events from the main window"""
        # Pass the key event to the canvas for camera movement
        if hasattr(self.canvas, 'keyReleaseEvent'):
            self.canvas.keyReleaseEvent(event)


    def show_help_dialog_with_3d(self):
        """Show help dialog with keyboard and mouse controls - INCLUDING 3D MODE"""
        help_text = (
            "Keyboard Controls:\n"
            "  General:\n"
            "    Tab        - Toggle between 2D and 3D view modes\n"
            "    F1         - Show this help dialog\n"
            "    Delete     - Delete selected entity/entities\n"
            "    Ctrl+C     - Copy selected entity/entities\n"
            "    Ctrl+V     - Paste entity/entities\n"
            "    Ctrl+Z     - Undo (if available)\n"
            "\n"
            "  2D Mode Navigation:\n"
            "    W/A/S/D    - Pan camera (Up/Left/Down/Right)\n"
            "    Shift      - Speed boost for panning\n"
            "    Mouse Wheel - Zoom in/out\n"
            "\n"
            "  3D Mode Navigation:\n"
            "    W/S        - Move forward/backward\n"
            "    A/D        - Move left/right (strafe)\n"
            "    Q/E        - Move up/down (vertical)\n"
            "    Shift      - Speed boost for movement\n"
            "\n"
            "Mouse Controls:\n"
            "  2D Mode:\n"
            "    Left Click      - Select entity\n"
            "    Ctrl+Left Click - Multi-select entities\n"
            "    Left Drag       - Move selected entity\n"
            "    Mouse Wheel     - Zoom in/out\n"
            "    Right Click     - Context menu\n"
            "\n"
            "  3D Mode:\n"
            "    Left Click           - Select entity\n"
            "    Right Click + Drag   - Rotate camera (look around)\n"
            "    Middle Click + Drag  - Pan camera\n"
            "    Mouse Wheel          - Move forward/backward\n"
            "    Right Click          - Context menu\n"
            "\n"
            "View Options:\n"
            "  G          - Toggle grid visibility\n"
            "  E          - Toggle entity visibility\n"
            "  T          - Toggle terrain visibility (if loaded)\n"
            "  B          - Toggle sector boundaries (2D mode)\n"
            "\n"
            "Gizmo Controls (Both Modes):\n"
            "  Click and drag the colored arrows to move entities\n"
            "  Red arrow    - X axis\n"
            "  Green arrow  - Y axis (Z in 3D)\n"
            "  Blue arrow   - Z axis (Y in 3D)\n"
            "\n"
            "Tips:\n"
            "  â€¢ Hold Shift while moving for faster camera movement\n"
            "  â€¢ Double-click an entity in the tree to focus on it\n"
            "  â€¢ Right-click entities for quick actions\n"
            "  â€¢ Use Tab to switch between top-down editing and 3D preview\n"
        )
        
        # Create and show help dialog
        from PyQt6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Level Editor Controls - 2D & 3D Modes")
        msg_box.setText(help_text)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.exec()
    
    def reset_view(self):
        """Reset the view to show all content - UPDATED for 2D and 3D"""
        if not self.entities:
            print("No entities to display")
            self.status_bar.showMessage("No entities to display")
            return
            
        print(f"Resetting view for {len(self.entities)} entities in mode {self.canvas.mode}")
        
        if self.canvas.mode == 0:  # 2D mode
            # Get current scale factor before reset
            old_scale = self.canvas.scale_factor
            
            # Call the canvas reset_view method
            new_scale = self.canvas.reset_view()
            
            # Debug output
            print(f"2D view reset: scale changed from {old_scale:.2f} to {new_scale:.2f}")
            
            # Update status bar
            self.status_bar.showMessage(f"2D view reset (scale: {new_scale:.2f})")
            
            # Return the new scale
            return new_scale
            
        else:  # 3D mode
            # Calculate center of all entities
            min_x = min_y = min_z = float('inf')
            max_x = max_y = max_z = float('-inf')
            
            valid_entities = 0
            for entity in self.entities:
                if hasattr(entity, 'x') and hasattr(entity, 'y') and hasattr(entity, 'z'):
                    min_x = min(min_x, entity.x)
                    max_x = max(max_x, entity.x)
                    min_y = min(min_y, entity.y)
                    max_y = max(max_y, entity.y)
                    min_z = min(min_z, entity.z)
                    max_z = max(max_z, entity.z)
                    valid_entities += 1
            
            if valid_entities == 0:
                print("No valid entities with 3D coordinates")
                return 1.0
            
            # Calculate center point
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            center_z = (min_z + max_z) / 2
            
            # Calculate span to determine camera distance
            span_x = max_x - min_x
            span_y = max_y - min_y
            span_z = max_z - min_z
            max_span = max(span_x, span_y, span_z, 100)  # Minimum span of 100
            
            # Position camera to view all entities
            camera_distance = max_span * 2  # Distance based on span
            
            # Position camera behind and above the center
            import numpy as np
            self.canvas.camera_3d.position = np.array([
                center_x - camera_distance * 0.5,  # Behind on X
                center_z + camera_distance * 0.7,  # Above (Z is height)
                center_y + camera_distance * 0.5   # Back on Y
            ], dtype=float)
            
            # Calculate yaw to look at center
            dx = center_x - self.canvas.camera_3d.position[0]
            dy = center_y - self.canvas.camera_3d.position[2]
            self.canvas.camera_3d.yaw = np.degrees(np.arctan2(dy, dx))
            
            # Set pitch to look down at scene
            self.canvas.camera_3d.pitch = -30.0
            
            # Update camera vectors
            self.canvas.camera_3d.update_vectors()
            
            print(f"3D camera positioned at ({self.canvas.camera_3d.position[0]:.0f}, "
                f"{self.canvas.camera_3d.position[1]:.0f}, {self.canvas.camera_3d.position[2]:.0f})")
            print(f"Looking at center: ({center_x:.0f}, {center_y:.0f}, {center_z:.0f})")
            
            # Update canvas
            self.canvas.update()
            
            # Update status bar
            self.status_bar.showMessage(f"3D view reset - viewing {valid_entities} entities")
            
            return 1.0  # No scale factor in 3D
    
    def action_ground_objects(self):
        """Ground selected objects to the terrain - SIMPLIFIED for 2D only"""
        # Simplified implementation for 2D mode only
        for pos in self.canvas.selected_positions:
            if self.canvas.collision is None:
                return None
            height = self.canvas.collision.collide_ray_closest(pos.x, pos.z, pos.y)

            if height is not None:
                pos.y = height

        self.pik_control.update_info()
        self.canvas.gizmo.move_to_average(self.canvas.selected, None, None, False)
        self.set_has_unsaved_changes(True)
        self.canvas.update()

    def action_move_objects(self, deltax, deltay, deltaz):
        """Handle moving objects - SIMPLIFIED for 2D only"""
        # Proceed with the move implementation (no mode check needed)
        for pos in self.canvas.selected_positions:
            pos.add_position(deltax, deltay, deltaz)

        # Update the view
        self.canvas.update()
        self.pik_control.update_info()
        self.set_has_unsaved_changes(True)

    def action_rotate_object(self, deltarotation):
        """Handle rotating objects in both 2D and 3D modes"""
        # Pass through to the canvas's rotation implementation
        self.canvas.action_rotate_object(deltarotation)
        
        # Update UI
        self.canvas.update()
        self.pik_control.update_info()
        self.set_has_unsaved_changes(True)
    
    def action_update_info(self):
        """Update information panel based on selection"""
        if self.level_file is not None:
            selected = self.canvas.selected
            if len(selected) == 1:
                currentobj = selected[0]
                self.pik_control.set_info(currentobj, self.reset_view)
                self.pik_control.update_info()
            else:
                self.pik_control.reset_info("{0} objects selected".format(len(self.canvas.selected)))
                self.pik_control.set_objectlist(selected)    

    def toggle_display_mode(self):
        """Remove this method entirely or make it a no-op"""
        # Since we only have 2D mode, this method is no longer needed
        self.statusBar().showMessage("Only 2D mode available")

    def create_new_sector(self, sector_id, sector_x, sector_y):
        """Create a new worldsector file with proper FCBConverter format"""
        try:
            import xml.etree.ElementTree as ET
            import os
            
            print(f"Ã°Å¸Ââ€”Ã¯Â¸Â Creating new sector {sector_id} at grid position ({sector_x}, {sector_y})")
            
            # Generate the sector file path
            if not hasattr(self, 'worldsectors_path') or not self.worldsectors_path:
                QMessageBox.warning(self, "No Worldsectors Path", 
                                "No worldsectors folder is set. Please load a level first.")
                return None
            
            sector_filename = f"worldsector{sector_id}.data.fcb.converted.xml"
            sector_file_path = os.path.join(self.worldsectors_path, sector_filename)
            
            # Check if sector already exists
            if os.path.exists(sector_file_path):
                reply = QMessageBox.question(self, "Sector Exists", 
                                        f"Sector {sector_id} already exists. Overwrite?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply != QMessageBox.StandardButton.Yes:
                    return None
            
            # Create the XML structure
            root = self._create_sector_xml_structure(sector_id, sector_x, sector_y)
            
            # Create and save the tree
            tree = ET.ElementTree(root)
            self._indent_xml_elements(root)
            tree.write(sector_file_path, encoding='utf-8', xml_declaration=True)
            
            # Add to worldsectors_trees
            if not hasattr(self, 'worldsectors_trees'):
                self.worldsectors_trees = {}
            self.worldsectors_trees[sector_file_path] = tree
            
            # Mark as modified
            if not hasattr(self, 'worldsectors_modified'):
                self.worldsectors_modified = {}
            self.worldsectors_modified[sector_file_path] = True
            
            print(f"Created new sector file: {sector_filename}")
            
            # Update sector data for boundary display
            if hasattr(self, 'sector_data'):
                new_sector_info = {
                    'id': sector_id,
                    'x': sector_x,
                    'y': sector_y,
                    'size': 64,
                    'file_path': sector_file_path,
                    'entities': [],
                    'entity_count': 0,
                    'is_new': True
                }
                self.sector_data.append(new_sector_info)
                print(f"Added sector {sector_id} to sector boundary data")
            
            return sector_file_path
            
        except Exception as e:
            print(f"Error creating new sector: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to create new sector: {str(e)}")
            return None

    def _indent_xml_elements(self, elem, level=0):
        """Recursively add proper indentation to XML elements"""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml_elements(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def _indent_xml(self, elem, level=0):
        """Add proper indentation to XML elements"""
        indent = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
            for child in elem:
                self._indent_xml(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent

    def _create_sector_xml_structure(self, sector_id, sector_x, sector_y):
        """Create the XML structure for a new WorldSector with proper FCBConverter format"""
        import xml.etree.ElementTree as ET
        
        # Root WorldSector object
        root = ET.Element("object")
        root.set("hash", "C1CB6D9A")
        root.set("name", "WorldSector")
        
        # Id field
        id_field = ET.SubElement(root, "field")
        id_field.set("hash", "2ABD43F2")
        id_field.set("name", "Id")
        id_field.set("value-Int32", str(sector_id))
        id_field.set("type", "BinHex")
        id_field.text = self._int32_to_binhex(sector_id)
        
        # X field
        x_field = ET.SubElement(root, "field")
        x_field.set("hash", "B7B2364B")
        x_field.set("name", "X")
        x_field.set("value-Int32", str(sector_x))
        x_field.set("type", "BinHex")
        x_field.text = self._int32_to_binhex(sector_x)
        
        # Y field
        y_field = ET.SubElement(root, "field")
        y_field.set("hash", "C0B506DD")
        y_field.set("name", "Y")
        y_field.set("value-Int32", str(sector_y))
        y_field.set("type", "BinHex")
        y_field.text = self._int32_to_binhex(sector_y)
        
        # MissionLayer object
        mission_layer = ET.SubElement(root, "object")
        mission_layer.set("hash", "494C09F2")
        mission_layer.set("name", "MissionLayer")
        
        # PathId fields for MissionLayer
        text_path_field = ET.SubElement(mission_layer, "field")
        text_path_field.set("hash", "C56F9204")
        text_path_field.set("name", "text_PathId")
        text_path_field.set("value-String", "main")
        text_path_field.set("type", "BinHex")
        text_path_field.text = self._string_to_binhex("main")
        
        path_id_field = ET.SubElement(mission_layer, "field")
        path_id_field.set("hash", "D0E30BF7")
        path_id_field.set("name", "PathId")
        path_id_field.set("value-ComputeHash32", "main")
        path_id_field.set("type", "BinHex")
        path_id_field.text = "64CD28BF"  # Hash of "main"
        
        return root

    def _int32_to_binhex(self, value):
        """Convert 32-bit integer to BinHex format"""
        try:
            import struct
            binary_data = struct.pack('<I', int(value))  # Little-endian unsigned int
            return binary_data.hex().upper()
        except:
            return "00000000"

    def _string_to_binhex(self, text):
        """Convert string to BinHex format with null terminator"""
        try:
            binary_data = text.encode('utf-8') + b'\x00'
            return binary_data.hex().upper()
        except:
            return "00"

    def show_create_sector_dialog(self):
        """Show dialog to create a new sector"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                    QSpinBox, QPushButton, QFormLayout, QMessageBox)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New WorldSector")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # Info label
        info_label = QLabel("Create a new WorldSector file:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Sector ID
        self.sector_id_spin = QSpinBox()
        self.sector_id_spin.setRange(0, 9999)
        self.sector_id_spin.setValue(self._get_next_available_sector_id())
        form_layout.addRow("Sector ID:", self.sector_id_spin)
        
        # Sector X coordinate
        self.sector_x_spin = QSpinBox()
        self.sector_x_spin.setRange(-100, 100)
        self.sector_x_spin.setValue(0)
        form_layout.addRow("Grid X:", self.sector_x_spin)
        
        # Sector Y coordinate
        self.sector_y_spin = QSpinBox()
        self.sector_y_spin.setRange(-100, 100)
        self.sector_y_spin.setValue(0)
        form_layout.addRow("Grid Y:", self.sector_y_spin)
        
        layout.addLayout(form_layout)
        
        # Preview info
        preview_label = QLabel()
        preview_label.setStyleSheet("color: gray; font-style: italic; margin: 10px 0;")
        self._update_sector_preview(preview_label)
        layout.addWidget(preview_label)
        
        # Update preview when values change
        self.sector_id_spin.valueChanged.connect(lambda: self._update_sector_preview(preview_label))
        self.sector_x_spin.valueChanged.connect(lambda: self._update_sector_preview(preview_label))
        self.sector_y_spin.valueChanged.connect(lambda: self._update_sector_preview(preview_label))
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_button = QPushButton("Create Sector")
        create_button.clicked.connect(lambda: self._create_sector_from_dialog(dialog))
        create_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(create_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        dialog.exec()

    def _update_sector_preview(self, label):
        """Update the preview information in the create sector dialog"""
        sector_id = self.sector_id_spin.value()
        sector_x = self.sector_x_spin.value()
        sector_y = self.sector_y_spin.value()
        
        # Calculate world coordinates
        world_min_x = sector_x * 64
        world_min_y = sector_y * 64
        world_max_x = world_min_x + 64
        world_max_y = world_min_y + 64
        
        filename = f"worldsector{sector_id}.data.fcb.converted.xml"
        
        preview_text = (f"File: {filename}\n"
                    f"World bounds: ({world_min_x}, {world_min_y}) to ({world_max_x}, {world_max_y})")
        
        # Check if sector already exists
        if hasattr(self, 'worldsectors_path') and self.worldsectors_path:
            full_path = os.path.join(self.worldsectors_path, filename)
            if os.path.exists(full_path):
                preview_text += "\nThis sector already exists and will be overwritten!"
                label.setStyleSheet("color: orange; font-style: italic; margin: 10px 0;")
            else:
                label.setStyleSheet("color: gray; font-style: italic; margin: 10px 0;")
        
        label.setText(preview_text)

    def _get_next_available_sector_id(self):
        """Get the next available sector ID"""
        if not hasattr(self, 'worldsectors_path') or not self.worldsectors_path:
            return 0
        
        try:
            import glob
            import os
            import re
            
            # Find all existing sector files
            pattern = os.path.join(self.worldsectors_path, "worldsector*.data.fcb.converted.xml")
            existing_files = glob.glob(pattern)
            
            # Also check for .data.fcb files
            fcb_pattern = os.path.join(self.worldsectors_path, "worldsector*.data.fcb")
            existing_fcb_files = glob.glob(fcb_pattern)
            
            used_ids = set()
            
            # Extract IDs from .converted.xml files
            for file_path in existing_files:
                filename = os.path.basename(file_path)
                match = re.match(r'worldsector(\d+)\.data\.fcb\.converted\.xml', filename)
                if match:
                    used_ids.add(int(match.group(1)))
            
            # Extract IDs from .data.fcb files
            for file_path in existing_fcb_files:
                filename = os.path.basename(file_path)
                match = re.match(r'worldsector(\d+)\.data\.fcb', filename)
                if match:
                    used_ids.add(int(match.group(1)))
            
            # Find next available ID
            next_id = 0
            while next_id in used_ids:
                next_id += 1
            
            return next_id
            
        except Exception as e:
            print(f"Error finding next sector ID: {e}")
            return 0

    def closeEvent(self, event):
        """Handle application close event - cleanup resources"""
        print("Application closing - cleaning up resources...")
        
        # Clean up patch manager if it exists
        if hasattr(self, 'patch_manager'):
            try:
                self.patch_manager.cleanup()
            except Exception as e:
                print(f"Error cleaning up patch manager: {e}")
        
        # Clean up cache manager
        if hasattr(self, 'cache'):
            try:
                from cache_manager import shutdown_cache_manager
                shutdown_cache_manager()
                print("Cache manager shutdown complete")
            except Exception as e:
                print(f"Error shutting down cache manager: {e}")
        
        # Close entity editor if open
        if hasattr(self, 'entity_editor') and self.entity_editor:
            try:
                self.entity_editor.close()
            except:
                pass
        
        # Clean up any running threads
        if hasattr(self, 'object_loading_thread') and self.object_loading_thread:
            try:
                if self.object_loading_thread.isRunning():
                    self.object_loading_thread.stop()
                    self.object_loading_thread.wait(2000)
            except:
                pass
        
        # Accept the close event
        event.accept()
        print("Application cleanup complete")

    def _create_sector_from_dialog(self, dialog):
        """Create sector from dialog values"""
        sector_id = self.sector_id_spin.value()
        sector_x = self.sector_x_spin.value()
        sector_y = self.sector_y_spin.value()
        
        # Create the sector
        sector_file_path = self.create_new_sector(sector_id, sector_x, sector_y)
        
        if sector_file_path:
            dialog.accept()
            
            # Show success message
            QMessageBox.information(self, "Sector Created", 
                                f"Successfully created sector {sector_id}!\n\n"
                                f"File: {os.path.basename(sector_file_path)}\n"
                                f"Grid position: ({sector_x}, {sector_y})")
            
            # Refresh sector boundaries if they're visible
            if hasattr(self, 'show_sector_boundaries') and self.show_sector_boundaries:
                self.load_sector_data_from_entities()
                self.canvas.update()
        else:
            QMessageBox.warning(self, "Creation Failed", "Failed to create the sector file.")

class ObjectLoadingThread(QThread):
    """Thread for loading objects from worldsectors in the background"""
    
    progress_updated = pyqtSignal(float)  # Progress from 0.0 to 1.0
    status_updated = pyqtSignal(str)      # Status message
    log_message = pyqtSignal(str)         # NEW: Log messages for the log box
    objects_loaded = pyqtSignal(list)     # List of loaded objects
    finished_loading = pyqtSignal(object) # ObjectLoadResult
    
    def __init__(self, worldsectors_path, file_converter, grid_config=None):
        super().__init__()
        self.worldsectors_path = worldsectors_path
        self.file_converter = file_converter
        self.grid_config = grid_config
        self.should_stop = False
    
    def stop(self):
        """Stop the loading process"""
        self.should_stop = True
        print("Stop requested for object loading thread")

    def run(self):
        """Run the object loading process with cleanup - UPDATED with cancellation check"""
        try:
            from data_models import ObjectLoadResult, WorldSectorManager, ObjectParser
            
            result = ObjectLoadResult()
            
            # Progress weights
            CLEANUP_WEIGHT = 0.02
            SCAN_WEIGHT = 0.03
            CONVERT_WEIGHT = 0.70
            RESCAN_WEIGHT = 0.05
            LOAD_WEIGHT = 0.20
            
            current_progress = 0.0
            
            # Helper for logging
            def log(message):
                print(message)
                self.log_message.emit(message)
            
            # Step 1: Cleanup
            self.status_updated.emit("Cleaning up duplicate files, Please wait.")
            self.progress_updated.emit(0.0)
            self.cleanup_duplicate_xml_files(self.worldsectors_path)
            current_progress = CLEANUP_WEIGHT
            self.progress_updated.emit(current_progress)
            
            if self.should_stop:
                return
            
            # Step 2: Initial scan
            self.status_updated.emit("Scanning for converted XML files, Please wait.")
            sectors = WorldSectorManager.scan_worldsectors_folder(self.worldsectors_path, log_callback=log)
            log(f"Found {len(sectors)} sectors")
            current_progress += SCAN_WEIGHT
            self.progress_updated.emit(current_progress)
            
            if self.should_stop:
                return
            
            # Step 3: Convert FCB files
            self.status_updated.emit("Converting .data.fcb files to XML, Please wait.")

            # Create callback that checks for cancellation and handles logging
            def conversion_progress_with_logging(progress, message=None):
                # Check if cancelled
                if self.should_stop:
                    raise InterruptedError("Conversion cancelled by user")
                
                # If message is provided, always send it to log
                if message:
                    self.log_message.emit(message)
                
                # Update progress bar only if progress is a valid number
                if progress is not None:
                    overall = current_progress + (progress * CONVERT_WEIGHT)
                    self.progress_updated.emit(overall)

            try:
                success_count, error_count, converted_files = self.file_converter.convert_data_fcb_files(
                    self.worldsectors_path,
                    progress_callback=conversion_progress_with_logging
                )
            except InterruptedError:
                print("Conversion interrupted by user")
                return

            log(f"Conversion results: {success_count} successful, {error_count} failed")
            current_progress += CONVERT_WEIGHT
            self.progress_updated.emit(current_progress)
            
            if self.should_stop:
                return
            
            # Step 4: Re-scan
            self.status_updated.emit("Re-scanning for XML files, Please wait.")
            sectors = WorldSectorManager.scan_worldsectors_folder(self.worldsectors_path, log_callback=log)
            result.sectors_processed = len(sectors)
            result.loaded_sectors = sectors
            log(f"After conversion, found {len(sectors)} sectors")
            current_progress += RESCAN_WEIGHT
            self.progress_updated.emit(current_progress)
            
            if self.should_stop:
                return
            
            # Step 5: Load objects
            self.status_updated.emit("Loading objects from converted XML files, Please wait.")
            all_objects = []
            
            total_xml_files = sum(len(sector.data_xml_files) for sector in sectors)
            files_processed = 0
            
            for i, sector in enumerate(sectors):
                if self.should_stop:
                    break
                
                log(f"Processing sector {i+1}/{len(sectors)} with {len(sector.data_xml_files)} XML files")
                sector_objects = []
                
                for xml_file in sector.data_xml_files:
                    if self.should_stop:
                        break
                    
                    try:
                        if xml_file.endswith('.converted.xml'):
                            log(f"Loading objects from: {xml_file}")
                            objects = ObjectParser.extract_objects_from_data_xml(
                                xml_file, 
                                sector_path=sector.folder_path
                            )
                            
                            log(f"Extracted {len(objects)} objects from {os.path.basename(xml_file)}")
                            
                            for obj in objects:
                                if self.grid_config and self.grid_config.maps:
                                    obj.map_name = self._determine_object_map(obj)
                            
                            sector_objects.extend(objects)
                        else:
                            log(f"Skipping non-converted XML file: {xml_file}")
                            
                    except Exception as e:
                        error_msg = f"Error loading {xml_file}: {str(e)}"
                        log(error_msg)
                        result.conversion_errors.append(error_msg)
                        result.failed_objects += 1
                    
                    files_processed += 1
                    if total_xml_files > 0:
                        file_progress = files_processed / total_xml_files
                        overall = current_progress + (file_progress * LOAD_WEIGHT)
                        self.progress_updated.emit(overall)
                        self.status_updated.emit(f"Loading objects: {files_processed}/{total_xml_files} files")
                
                sector.object_count = len(sector_objects)
                all_objects.extend(sector_objects)
                log(f"Sector {i+1} loaded {len(sector_objects)} objects (total: {len(all_objects)})")
            
            # Check if cancelled before emitting results
            if self.should_stop:
                print("Loading cancelled by user")
                return
            
            # Final results
            result.total_objects = len(all_objects)
            result.loaded_objects = len(all_objects)
            
            log(f"Loading complete: {len(all_objects)} total objects loaded")
            self.status_updated.emit(f"Complete: {len(all_objects)} objects loaded")
            self.progress_updated.emit(1.0)
            
            # Emit results
            self.objects_loaded.emit(all_objects)
            self.finished_loading.emit(result)
            
        except Exception as e:
            error_msg = f"Error during loading: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            
            self.status_updated.emit(error_msg)
            result = ObjectLoadResult()
            result.conversion_errors.append(str(e))
            self.finished_loading.emit(result)

    def cleanup_duplicate_xml_files(self, worldsectors_path):
        """Remove duplicate .data.xml files, keep only .converted.xml"""
        try:
            duplicate_files = []
            
            for file in os.listdir(worldsectors_path):
                if file.endswith(".data.xml") and not file.endswith(".converted.xml"):
                    # Check if corresponding .converted.xml exists
                    base_name = file.replace(".data.xml", "")
                    converted_file = base_name + ".data.fcb.converted.xml"
                    converted_path = os.path.join(worldsectors_path, converted_file)
                    
                    if os.path.exists(converted_path):
                        # Remove the duplicate .data.xml file
                        duplicate_path = os.path.join(worldsectors_path, file)
                        duplicate_files.append(duplicate_path)
            
            # Remove duplicate files
            for duplicate_file in duplicate_files:
                try:
                    os.remove(duplicate_file)
                    print(f"Removed duplicate file: {os.path.basename(duplicate_file)}")
                except Exception as e:
                    print(f"Error removing {duplicate_file}: {e}")
            
            if duplicate_files:
                print(f"Cleaned up {len(duplicate_files)} duplicate .data.xml files")
            else:
                print("No duplicate files found")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def _determine_object_map(self, obj):
        """Determine which map an object belongs to based on its coordinates - ENHANCED"""
        if not self.grid_config or not self.grid_config.maps:
            print(f"No grid config available for object {obj.name}")
            return None
            
        # Convert object coordinates to sector coordinates
        sector_x = int(obj.x / self.grid_config.sector_granularity)
        sector_y = int(obj.z / self.grid_config.sector_granularity)  # Note: using Z for Y-axis
        
        print(f"Object {obj.name} at ({obj.x:.1f}, {obj.y:.1f}, {obj.z:.1f}) -> sector ({sector_x}, {sector_y})")
        
        # Check each map to see if object belongs to it
        for map_info in self.grid_config.maps:
            min_sector_x = map_info.sector_offset_x
            min_sector_y = map_info.sector_offset_y
            max_sector_x = min_sector_x + map_info.count_x
            max_sector_y = min_sector_y + map_info.count_y
            
            if (min_sector_x <= sector_x < max_sector_x and 
                min_sector_y <= sector_y < max_sector_y):
                print(f"Object {obj.name} belongs to map {map_info.name}")
                return map_info.name
        
        print(f"Object {obj.name} does not belong to any map")
        return None

    @staticmethod
    def extract_objects_from_data_xml(xml_file_path, sector_path=None):
        """
        Extract all Entity objects from a .data.xml file
        
        Args:
            xml_file_path (str): Path to the .data.xml file
            sector_path (str): Path to the sector folder
            
        Returns:
            List[ObjectEntity]: List of parsed objects
        """
        objects = []
        
        try:
            print(f"\n=== Processing {os.path.basename(xml_file_path)} ===")
            
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            
            print(f"Root element type: {root.get('type')}")
            
            # Handle different file types
            if root.get("type") == "WorldSector":
                print("Processing as WorldSector file")
                
                # Extract WorldSector information
                sector_id = None
                sector_x = None
                sector_y = None
                
                id_elem = root.find("./value[@name='Id']")
                if id_elem is not None and id_elem.text:
                    try:
                        sector_id = int(id_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                x_elem = root.find("./value[@name='X']")
                if x_elem is not None and x_elem.text:
                    try:
                        sector_x = int(x_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                y_elem = root.find("./value[@name='Y']")
                if y_elem is not None and y_elem.text:
                    try:
                        sector_y = int(y_elem.text)
                    except (ValueError, TypeError):
                        pass
                
                print(f"WorldSector {sector_id} at ({sector_x}, {sector_y})")
            
            elif "landmark" in os.path.basename(xml_file_path).lower():
                print("Processing as Landmark file")
            
            else:
                print(f"Processing as {root.get('type', 'unknown')} file")
            
            # Find all Entity objects anywhere in the file
            entity_elements = root.findall(".//object[@type='Entity']")
            
            print(f"Found {len(entity_elements)} Entity objects")
            
            # Parse each Entity
            for i, entity_elem in enumerate(entity_elements):
                print(f"\n--- Processing Entity {i+1}/{len(entity_elements)} ---")
                
                obj_entity = ObjectParser.parse_object_from_xml(
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
        
    def debug_check_xml_coordinates(self, entity_name):
        """Debug method to check if coordinates are actually in the XML files"""
        if not hasattr(self, 'worldsectors_trees'):
            print("No worldsectors_trees available")
            return
        
        for file_path, tree in self.worldsectors_trees.items():
            root = tree.getroot()
            
            # Find entities with the given name
            for entity_elem in root.findall(".//object[@type='Entity']"):
                name_elem = entity_elem.find("./value[@name='hidName']")
                if name_elem is not None and name_elem.text == entity_name:
                    print(f"DEBUG: Found {entity_name} in {os.path.basename(file_path)}")
                    
                    # Check hidPos
                    pos_elem = entity_elem.find("./value[@name='hidPos']")
                    if pos_elem is not None:
                        x_elem = pos_elem.find("./x")
                        y_elem = pos_elem.find("./y")
                        z_elem = pos_elem.find("./z")
                        
                        if x_elem is not None and y_elem is not None and z_elem is not None:
                            print(f"  hidPos in XML: ({x_elem.text}, {y_elem.text}, {z_elem.text})")
                    
                    # Check hidPos_precise
                    pos_precise_elem = entity_elem.find("./value[@name='hidPos_precise']")
                    if pos_precise_elem is not None:
                        x_elem = pos_precise_elem.find("./x")
                        y_elem = pos_precise_elem.find("./y")
                        z_elem = pos_precise_elem.find("./z")
                        
                        if x_elem is not None and y_elem is not None and z_elem is not None:
                            print(f"  hidPos_precise in XML: ({x_elem.text}, {y_elem.text}, {z_elem.text})")

class LevelFileConfig:
    """Configuration for which level files to load and convert"""
    
    def __init__(self):
        # Main files that are always loaded
        self.main_files = {
            "mapsdata": {
                "enabled": True,
                "required": True,  # Cannot be disabled
                "patterns": ["mapsdata.fcb", "mapsdata.xml", "*.mapsdata.xml", "*.mapsdata.fcb"],
                "description": "Map Data (Main entities)"
            },
            "entitylibrary_full": {
                "enabled": True,
                "required": False,
                "patterns": ["entitylibrary_full.fcb", "entitylibrary_full.xml"],
                "description": "Entity Library (Entity definitions)"
            },
            "managers": {
                "enabled": True,
                "required": False,
                "patterns": [".managers.fcb", ".managers.xml", "managers.fcb", "managers.xml", "*.managers.fcb", "*.managers.xml"],
                "description": "Managers (Game systems)"
            },
            "omnis": {
                "enabled": True,
                "required": False,
                "patterns": [".omnis.fcb", ".omnis.xml", "omnis.fcb", "omnis.xml", "*.omnis.fcb", "*.omnis.xml"],
                "description": "Omnis (Universal objects)"
            },
            "sectorsdep": {
                "enabled": True,
                "required": False,
                "patterns": ["sectorsdep.fcb", "sectorsdep.xml", "sectordep.fcb", "sectordep.xml"],
                "description": "Sector Dependencies"
            }
        }
        
        # Optional files that are now disabled by default
        self.optional_files = {
            "preload": {
                "enabled": False,  # Disabled by default
                "patterns": [".preload.xml", "preload.xml"],
                "description": "Preload Data"
            },
            "particles": {
                "enabled": False,  # Disabled by default
                "patterns": ["_deploadnewparticles_*.xml"],
                "description": "Particle Data"
            },
            "game": {
                "enabled": False,  # Disabled by default
                "patterns": ["*.game.xml"],
                "description": "Game Configuration"
            }
        }
    
    def get_enabled_files(self):
        """Get list of enabled file types"""
        enabled = {}
        
        # Add enabled main files
        for file_type, config in self.main_files.items():
            if config["enabled"]:
                enabled[file_type] = config
        
        # Add enabled optional files
        for file_type, config in self.optional_files.items():
            if config["enabled"]:
                enabled[file_type] = config
        
        return enabled
    
    def is_file_enabled(self, file_type):
        """Check if a specific file type is enabled"""
        if file_type in self.main_files:
            return self.main_files[file_type]["enabled"]
        elif file_type in self.optional_files:
            return self.optional_files[file_type]["enabled"]
        return False
    
    def set_file_enabled(self, file_type, enabled):
        """Enable or disable a file type"""
        if file_type in self.main_files:
            # Cannot disable required files
            if self.main_files[file_type].get("required", False) and not enabled:
                print(f"Cannot disable required file type: {file_type}")
                return False
            self.main_files[file_type]["enabled"] = enabled
            return True
        elif file_type in self.optional_files:
            self.optional_files[file_type]["enabled"] = enabled
            return True
        return False
        
class RotatingLoadingIcon(QLabel):
    """Custom rotating loading icon widget"""
    
    def __init__(self, background_path, rotating_path, parent=None):
        super().__init__(parent)
        
        # Load images
        self.background = QPixmap(background_path)
        self.rotating = QPixmap(rotating_path)
        
        # Check if images loaded
        if self.background.isNull():
            print(f"Failed to load background: {background_path}")
            self.background = QPixmap(64, 64)
            self.background.fill(Qt.GlobalColor.lightGray)
        
        if self.rotating.isNull():
            print(f"Failed to load rotating image: {rotating_path}")
            self.rotating = QPixmap(64, 64)
            self.rotating.fill(Qt.GlobalColor.blue)
        
        # Set widget size to match images
        size = max(self.background.width(), self.background.height())
        self.setFixedSize(size, size)
        
        # Rotation angle
        self.rotation_angle = 0
        
        # Setup rotation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(100)  # Update every 50ms (20 FPS)
    
    def rotate(self):
        """Rotate the icon by 30 degrees (one clock position)"""
        self.rotation_angle = (self.rotation_angle + 30) % 360  # 30 degrees = 1/12 of circle
        self.update()
    
    def paintEvent(self, event):
        """Paint the rotating loading icon - works in both 2D and 3D modes"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw background centered
        if hasattr(self, 'background') and self.background is not None:
            bg_x = (self.width() - self.background.width()) // 2
            bg_y = (self.height() - self.background.height()) // 2
            painter.drawPixmap(bg_x, bg_y, self.background)

        # Draw rotated foreground
        if hasattr(self, 'rotating') and self.rotating is not None:
            painter.save()
            painter.translate(self.width() / 2, self.height() / 2)
            painter.rotate(self.rotation_angle)
            painter.translate(-self.rotating.width() / 2, -self.rotating.height() / 2)
            painter.drawPixmap(0, 0, self.rotating)
            painter.restore()

        painter.end()

    def stop(self):
        """Stop the rotation"""
        self.timer.stop()

class EnhancedProgressDialog(QDialog):
    """Enhanced progress dialog with rotating loading icon and log - auto-selects icon based on game mode"""
    
    cancelled = pyqtSignal()  # Signal for cancellation
    
    def __init__(self, title, parent=None, game_mode="avatar"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(800, 400)
        
        # DEBUG: Print received game mode
        print(f"EnhancedProgressDialog: Received game_mode = '{game_mode}'")
        
        layout = QVBoxLayout(self)
        
        # Add rotating icons at the top
        icon_layout = QHBoxLayout()
        icon_layout.addStretch()
        
        # Select icon paths based on game mode
        if game_mode == "farcry2":
            # FC2: Use same image for background and rotating (single icon that rotates)
            background_path = "loading_logo2.png"
            rotating_path = "loading_logo3.png"
            print(f"EnhancedProgressDialog: Using FC2 icons: {background_path}")
        else:  # avatar
            # Avatar: Use default icons
            background_path = "default_i3.png"
            rotating_path = "default_i5.png"
            print(f"EnhancedProgressDialog: Using Avatar icons: {background_path}, {rotating_path}")
        
        # Rotating icons
        self.loading_icon = RotatingLoadingIcon(background_path, rotating_path)
        icon_layout.addWidget(self.loading_icon)
        icon_layout.addStretch()
        
        layout.addLayout(icon_layout)
        
        # Status label
        self.status_label = QLabel("Initializing, please wait...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Log box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(200)
        self.log_box.setStyleSheet("""
            QTextEdit {
                background-color: #333333;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 16px;
                border: 1px solid #3e3e3e;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.log_box)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        layout.addWidget(self.cancel_button)
        
        self.was_cancelled = False
        self.is_complete = False  # Track if operation completed
        self.cancel_button.clicked.connect(self.on_cancel)

    def closeEvent(self, event):
        shutdown_cache_manager()
        if not self.was_cancelled and not self.is_complete:
            self.on_cancel()
            event.ignore()
        else:
            event.accept()

    def on_cancel(self):
        if not self.was_cancelled:
            self.was_cancelled = True
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Cancelling...")
            self.append_log("Cancellation requested...")
            self.cancelled.emit()

    def set_status(self, text):
        self.status_label.setText(text)

    def set_progress(self, value):
        self.progress_bar.setValue(int(value))

    def append_log(self, message):
        if not message or not message.strip():
            return
        self.log_box.append(message)
        scrollbar = self.log_box.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def stop_icon(self):
        """Stop both rotating icons"""
        if hasattr(self, "loading_icon"):
            self.loading_icon.stop()

    def mark_complete(self):
        """Mark operation as complete - allows dialog to close"""
        self.is_complete = True
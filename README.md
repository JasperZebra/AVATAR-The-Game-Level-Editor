![GitHub release (latest by date)](https://img.shields.io/github/v/release/JasperZebra/AVATAR-The-Game-Level-Editor?style=for-the-badge&logo=github&color=00ffff&logoColor=white&labelColor=1a4d66)
![Total Downloads](https://img.shields.io/github/downloads/JasperZebra/AVATAR-The-Game-Level-Editor/total?style=for-the-badge&logo=github&color=00ffff&logoColor=white&labelColor=1a4d66) 
![Platform](https://img.shields.io/badge/platform-windows-00ffff?style=for-the-badge&logo=windows&logoColor=00ffff&labelColor=1a4d66)
![Made for](https://img.shields.io/badge/made%20for-2009_AVATAR:_The_Game-00ffff?style=for-the-badge&logo=gamepad&logoColor=00ffff&labelColor=1a4d66) 
![Tool Type](https://img.shields.io/badge/type-level%20editor-00ffff?style=for-the-badge&logo=edit&logoColor=00ffff&labelColor=1a4d66)

# Avatar: The Game Level Editor

A comprehensive level editor for modifying **Avatar: The Game** level files with full FCB to XML conversion support and real-time visual editing capabilities.

## Features

- **Dual-Format Support**: Seamlessly works with both FCB and XML file formats with automatic conversion
- **Visual Entity Management**: Drag-and-drop positioning, rotation gizmos, and real-time property editing
- **Smart Entity Operations**: Copy/paste, duplication with auto-generated IDs, and batch operations
- **Interactive Canvas**: Color-coded entity visualization with adaptive grid system
- **Sector Management**: Visual boundary display with violation detection

## Quick Start

### Game Selection
1. Select you game you want to start modding

| **New Game selection** |
|---|
| <img width="600" height="500" alt="Screenshot 2025-12-01 161755" src="https://github.com/user-attachments/assets/b5a75f8d-18e9-4a16-b099-4fd6be77b5c2" /> |

### Loading a Level
1. Set your `ptach` folder for the game type you're currently modding
2. Level folders and files will be automatically read, loaded and converted as needed.
3. Select the level you want to load into the editor from the UI screen

| **AVATAR** | **FARCRY 2** |
|---|---|
| <img width="1329" height="1096" alt="Screenshot 2025-12-01 161837" src="https://github.com/user-attachments/assets/0cd89cef-c05c-4341-ad62-7aef36d47eb4" /> | <img width="1600" height="1300" alt="Screenshot 2025-12-01 161923" src="https://github.com/user-attachments/assets/8c837629-b9b9-4c09-a856-eefbde5e8a31" /> |

## View Modes

### 2D Mode:
| **AVATAR** | **FARCRY 2** | 
|---|---|
| <img width="1808" height="1133" alt="Screenshot 2025-12-01 163403" src="https://github.com/user-attachments/assets/e69512a0-83c8-48e5-a2ec-b46e2506c165" /> | <img width="1807" height="1131" alt="Screenshot 2025-12-01 163745" src="https://github.com/user-attachments/assets/d2aa097d-7065-4440-8263-589983715e4d" /> |

### 3D Mode:
| **AVATAR** | **FARCRY 2** | 
|---|---|
| <img width="1801" height="1134" alt="Screenshot 2025-12-01 163508" src="https://github.com/user-attachments/assets/49fc5790-9758-4286-969c-474379842edb" /> | <img width="1803" height="1131" alt="Screenshot 2025-12-01 164020" src="https://github.com/user-attachments/assets/e310a42d-be1f-4485-9eef-4474f5669040" /> | 



### Basic Controls
- **Select**: Left-click (Ctrl+click for multi-select)
- **Move**: Drag entities or use Entity Editor
- **Rotate**: Use the blue rotation gizmo
- **Edit**: Open Entity Editor (Ctrl+E) for detailed properties
- **Save**: Use "Save Level" to convert back to FCB format

## Keyboard Shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| **File Operations** |
| Open Level | ``Ctrl+O`` | Two-step level loading |
| Save Level | ``Ctrl+S`` | Save changes to FCB format |
| **Editing** |
| Entity Editor | ``Ctrl+E`` | Open property editor |
| Copy | ``Ctrl+C`` | Copy selected entities |
| Paste | ``Ctrl+V`` | Paste entities |
| Duplicate | ``Ctrl+D`` | Duplicate with +20 X/Y offset |
| Delete | ``Delete`` | Remove selected entities |
| **View Controls** |
| Reset View | ``R`` | Center and reset camera |
| Toggle Entities | ``E`` | Show/hide entity visibility |
| Toggle Grid | ``G`` | Show/hide grid lines |
| Camera Movement | ``WASD`` | Move camera (Shift for speed boost) |
| Zoom | ``Mouse Wheel`` | Cursor-centered zooming |

## Entity Types & Visualization

Entities are automatically color-coded by type with size-based scaling:

- **Blue**: Vehicles (cars, boats, aircraft)
- **Green**: NPCs/Characters  
- **Red**: Weapons/Combat items
- **Orange**: Spawn points
- **Purple**: Mission objects
- **Yellow**: Triggers/Zones
- **Light Yellow**: Lights
- **Teal**: Effects/Particles
- **Gray**: Props/Static objects
- **Dark Gray**: Unknown types

## Supported Files

### Primary Files
- ``mapsdata.xml/.fcb`` - Main map data and entities
- ``managers.xml/.fcb`` - Game system managers
- ``omnis.xml/.fcb`` - Universal objects
- ``sectorsdep.xml/.fcb`` - Sector dependencies
- ``worldsector*.data.fcb`` - Individual sector data

Both FCB (native game format) and XML (human-readable) formats are supported with automatic conversion.

## Editor Components

### Entity Editor
- Real-time property editing with live preview
- Component system support (vehicle physics, graphics, missions)
- Direct XML field manipulation with type detection
- Optional auto-save functionality

### Visual Tools
- **Rotation Gizmo**: Interactive rotation with real-time angle display
- **Grid System**: Multi-level grids that adapt to zoom level
- **Sector Boundaries**: Visual boundaries with violation detection
- **Entity Browser**: Searchable, filterable entity management

## Safety & Best Practices

⚠️ **Important**: Always backup your level files before editing

## Contributing
Found a bug or want to contribute? Please create an issue or submit a pull request.

## Support
For issues and support, please create a GitHub issue with:
- Level file version
- Error message/logs
- Steps to reproduce the problem

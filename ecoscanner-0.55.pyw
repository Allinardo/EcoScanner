# eco_recipe_gui_with_notes.pyw – v5.4 Standard Window - Enhanced Room Tier Display - FIXED NAVIGATION
import os, re, json, threading, tkinter as tk
from tkinter import filedialog, messagebox, ttk
import shutil
import platform
import sys
from pathlib import Path
from datetime import datetime
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

def setup_window_icon_and_title(root):
    """Setup window icon and title for taskbar display with enhanced icon handling"""
    try:
        # Set window title
        root.title("EcoScanner 0.55")
        
        # Set window icon with multiple fallback options
        script_dir = Path(__file__).parent
        icon_paths = [
            script_dir / 'EcoScanner.ico',           # Primary icon
            script_dir / 'AppIcons' / 'EcoScanner.ico',  # Alternative location
            script_dir / 'EcoScanner.png',           # PNG fallback
        ]
        
        icon_set = False
        for icon_path in icon_paths:
            if icon_path.exists():
                try:
                    if icon_path.suffix.lower() == '.ico':
                        # Use iconbitmap for .ico files (preferred for Windows taskbar)
                        root.iconbitmap(str(icon_path))
                        log(f"✓ Set .ico window icon: {icon_path}")
                        icon_set = True
                        break
                    elif icon_path.suffix.lower() == '.png' and Image:
                        # Convert PNG to PhotoImage as fallback
                        img = Image.open(icon_path)
                        # Resize to common icon size if needed
                        img = img.resize((32, 32), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        root.iconphoto(True, photo)
                        # Keep reference to prevent garbage collection
                        root._icon_photo_ref = photo
                        log(f"✓ Set .png window icon: {icon_path}")
                        icon_set = True
                        break
                except Exception as icon_error:
                    log(f"Failed to set icon {icon_path}: {icon_error}")
                    continue
        
        if not icon_set:
            log("⚠ No valid icon file found. Checked paths:")
            for path in icon_paths:
                log(f"  - {path} (exists: {path.exists()})")
            
    except Exception as e:
        log(f"Error in icon setup function: {e}")

# Multi-platform default paths
def get_default_eco_paths():
    """Get platform-specific default Eco game paths"""
    system = platform.system().lower()
    home = Path.home()
    
    paths = []
    
    if system == "windows":
        # Steam paths on Windows
        steam_paths = [
            Path("C:/Program Files (x86)/Steam/steamapps/common/Eco"),
            Path("C:/Program Files/Steam/steamapps/common/Eco"),
            home / "AppData/Local/Steam/steamapps/common/Eco",
        ]
        # Epic Games paths
        epic_paths = [
            Path("C:/Program Files/Epic Games/Eco"),
            Path("C:/Program Files (x86)/Epic Games/Eco"),
        ]
        # Custom installation paths
        for drive in ["C:", "D:", "E:", "F:"]:
            paths.append(Path(f"{drive}/Games/Eco"))
            paths.append(Path(f"{drive}/Eco"))
        
        paths.extend(steam_paths + epic_paths)
        
    elif system == "darwin":  # macOS
        paths = [
            home / "Library/Application Support/Steam/steamapps/common/Eco",
            Path("/Applications/Eco.app"),
            home / "Applications/Eco.app",
            home / "Games/Eco",
        ]
        
    elif system == "linux":
        paths = [
            home / ".steam/steam/steamapps/common/Eco",
            home / ".local/share/Steam/steamapps/common/Eco",
            home / "Games/Eco",
            Path("/opt/Eco"),
            Path("/usr/local/games/Eco"),
        ]
    
    # Check which paths actually exist
    existing_paths = [p for p in paths if p.exists() and p.is_dir()]
    return existing_paths[0] if existing_paths else Path.cwd()

DEFAULT_ECO_PATH = str(get_default_eco_paths())
LOG = "eco_parser.log"

def log(msg):
    """Thread-safe logging function"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{timestamp}  {msg}\n")
        print(f"[{timestamp}] {msg}")  # Also print to console for debugging
    except Exception as e:
        print(f"Logging error: {e}")

def safe_read_file(path, encoding="utf-8"):
    """Safely read file with fallback encodings"""
    encodings = [encoding, "utf-8", "utf-8-sig", "cp1252", "latin1"]
    
    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                content = f.read()
            return content
        except (UnicodeDecodeError, UnicodeError) as e:
            continue
        except Exception as e:
            log(f"Error reading file {path}: {e}")
            break
    
    log(f"Failed to read file {path} with any encoding")
    return None

# Regex patterns for parsing recipes
PAT_RES      = re.compile(r"new\s+CraftingElement<\s*([A-Za-z0-9\s]+?)Item", re.I)
PAT_RES_ALT  = re.compile(r'products:\s*new\s+List<.*?>\s*{\s*new\s+CraftingElement<\s*([A-Za-z0-9\s]+?)Item', re.S | re.I)
PAT_RES_NAME = re.compile(r'name:\s*"(\w+)"', re.I)  # Fallback to recipe name
PAT_ING_STR  = re.compile(r'IngredientElement\s*\(\s*"([A-Za-z0-9\s]+?)"\s*,\s*(\d+)', re.I)
PAT_ING_TYPE = re.compile(r'IngredientElement\s*\(\s*typeof\(([A-Za-z0-9\s]+?)Item\)\s*,\s*(\d+)', re.I)
PAT_ING_GEN  = re.compile(r'IngredientElement<\s*([A-Za-z0-9\s]+?)Item\s*>\s*\(\s*(\d+)', re.I)
# Additional ingredient patterns for different recipe formats
PAT_ING_TAG  = re.compile(r'TagIngredient\s*\(\s*"([A-Za-z0-9\s]+?)"\s*,\s*(\d+)', re.I)
PAT_ING_NEW  = re.compile(r'new\s+IngredientElement\s*\(\s*typeof\s*\(\s*([A-Za-z0-9\s]+?)Item\s*\)\s*,\s*(\d+)', re.I)
# Pattern for items/tags as ingredients (e.g., Gold for adorned items)
PAT_ING_ITEM = re.compile(r'Items\.Get<\s*([A-Za-z0-9\s]+?)Item\s*>\s*\(\s*\)\s*,\s*(\d+)', re.I)
# Additional patterns for different ingredient formats
PAT_ING_DIRECT = re.compile(r'{\s*typeof\s*\(\s*([A-Za-z0-9\s]+?)Item\s*\)\s*,\s*(\d+)', re.I)
PAT_ING_CREATE = re.compile(r'Create<\s*([A-Za-z0-9\s]+?)Item\s*>\s*\(\s*\)\s*,\s*(\d+)', re.I)
PAT_DESC     = re.compile(r'\[LocDescription\("(.+?)"\)\]', re.S)
PAT_REQSK    = re.compile(r'\[RequiresSkill\(\s*typeof\(([A-Za-z0-9\s]+?)Skill\)\s*,\s*(\d+)', re.I)
PAT_SK       = re.compile(r"RequiredSkillType\s*=\s*typeof\(([A-Za-z0-9\s]+)", re.I)
PAT_LVL      = re.compile(r"RequiredSkillLevel\s*=\s*(\d+)", re.I)
PAT_NUTRIENTS = re.compile(r"Nutrients\s*=\s*new\s+List<.*?>\s*\{([^}]+)\}", re.S | re.I)
PAT_WEIGHT   = re.compile(r'\[Weight\((\d+)\)\]', re.I)  # Matches [Weight(6500)] format
# Housing/Furnishing patterns
PAT_BASE_VALUE = re.compile(r'BaseValue\s*=\s*(\d+\.?\d*)f?', re.I)
PAT_ROOM_CATEGORY = re.compile(r'Category\s*=\s*HousingConfig\.GetRoomCategory\("(\w+)"\)', re.I)
PAT_TYPE_FOR_ROOM_LIMIT = re.compile(r'TypeForRoomLimit\s*=\s*Localizer\.DoStr\("([^"]+)"\)', re.I)
PAT_DIMINISHING_RETURN = re.compile(r'DiminishingReturnMultiplier\s*=\s*(\d+\.?\d*)f?', re.I)

# Room requirement patterns
PAT_REQUIRE_ROOM_CONTAINMENT = re.compile(r'\[RequireRoomContainment\]', re.I)
PAT_REQUIRE_ROOM_VOLUME = re.compile(r'\[RequireRoomVolume\((\d+)\)\]', re.I)
PAT_REQUIRE_ROOM_MATERIAL_TIER = re.compile(r'\[RequireRoomMaterialTier\((\d+\.?\d*)f?', re.I)
PAT_TAB      = [
    re.compile(r"CraftingTable\s*=\s*typeof\(([A-Za-z0-9\s]+?)Object\)", re.I),
    re.compile(r"AddRecipe<\s*(\w+?)Object", re.I),
    re.compile(r"AddRecipe\s*\([^,]+,\s*typeof\((\w+?)Object\)", re.I),
    re.compile(r"Initialize\([^)]*typeof\((\w+?)Object\)", re.I),
    re.compile(r"AddRecipe\([^)]*tableType\s*:\s*typeof\((\w+?)Object\)", re.I),
    re.compile(r"CraftingComponent\.AddRecipe\([^)]*tableType\s*:\s*typeof\((\w+?)Object\)", re.I),
    re.compile(r"CraftingComponent\.AddTagProduct\s*\(\s*typeof\s*\(\s*(\w+?)Object\s*\)", re.I),  # Pattern for adorned items
]
# Patterns for upgrade recipes and variant recipes
PAT_UPGRADE  = re.compile(r"UpgradeRecipe.*?Product\s*=\s*typeof\s*\(\s*([A-Za-z0-9\s]+?)Item\s*\)", re.S | re.I)
PAT_VARIANT  = re.compile(r"RecipeVariant.*?Product\s*=\s*typeof\s*\(\s*([A-Za-z0-9\s]+?)Item\s*\)", re.S | re.I)
# Pattern for items defined in recipe lists or variants
PAT_RECIPE_ITEM = re.compile(r'(?:RecipeItem|Item\.Get|Items\.Get|CreateItem|Product)\s*[<(]\s*([A-Za-z0-9\s]+?)Item\s*[>)]', re.I)

# For uncraftable items and better item detection
PAT_ITEM_CLASS = re.compile(r"class\s+([A-Za-z0-9\s]+?)Item\b")
PAT_ITEM_DESC  = re.compile(r'\[LocDescription\("(.+?)"\)\]', re.S)

# New patterns for nutrition parsing
PAT_CALORIES = re.compile(r"Calories\s*=\s*(-?\d+)", re.I)
PAT_CARBS = re.compile(r"Carbs\s*=\s*(-?\d+)", re.I)
PAT_PROTEIN = re.compile(r"Protein\s*=\s*(-?\d+)", re.I)
PAT_FAT = re.compile(r"Fat\s*=\s*(-?\d+)", re.I)
PAT_VITAMINS = re.compile(r"Vitamins\s*=\s*(-?\d+)", re.I)

# Eco nutrient colors
NUTRIENT_COLORS = {
    'calories': {'fg': '#666666', 'bg': '#E0E0E0'},  # Grey
    'carbs': {'fg': '#FFFFFF', 'bg': '#CC0000'},     # Red with white text
    'protein': {'fg': '#FFFFFF', 'bg': '#FF6600'},   # Orange with white text
    'fat': {'fg': '#000000', 'bg': '#FFCC00'},       # Yellow with black text
    'vitamins': {'fg': '#FFFFFF', 'bg': '#00AA00'}   # Green with white text
}

def unescape_csharp_string(text):
    if not text:
        return text
    
    # Handle common C# escape sequences
    replacements = {
        '\\n': '\n',
        '\\r': '\r',
        '\\t': '\t',
        '\\"': '"',
        "\\'": "'",
        '\\\\': '\\',
    }
    
    result = text
    for escaped, unescaped in replacements.items():
        result = result.replace(escaped, unescaped)
    
    # Handle Unicode escape sequences like \u0025 (for %)
    def replace_unicode_escape(match):
        try:
            unicode_value = int(match.group(1), 16)
            return chr(unicode_value)
        except (ValueError, OverflowError):
            return match.group(0)  # Return original if conversion fails
    
    # Replace \uXXXX patterns
    result = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode_escape, result)
    
    # Handle \xXX patterns as well
    def replace_hex_escape(match):
        try:
            hex_value = int(match.group(1), 16)
            return chr(hex_value)
        except (ValueError, OverflowError):
            return match.group(0)
    
    result = re.sub(r'\\x([0-9a-fA-F]{2})', replace_hex_escape, result)
    
    return result

def parse_weight(txt: str):
    weight_match = PAT_WEIGHT.search(txt)
    if weight_match:
        try:
            raw_weight = int(weight_match.group(1))
            weight_kg = round(raw_weight / 4000, 2)
            return weight_kg
        except ValueError:
            return None
    return None

def parse_housing_info(txt: str):
    housing_info = {}
    
    if base_value_match := PAT_BASE_VALUE.search(txt):
        try:
            housing_info['base_value'] = float(base_value_match.group(1))
        except ValueError:
            pass
    
    if category_match := PAT_ROOM_CATEGORY.search(txt):
        housing_info['room_category'] = category_match.group(1)
    
    if type_match := PAT_TYPE_FOR_ROOM_LIMIT.search(txt):
        furniture_type = type_match.group(1)
        if furniture_type:
            housing_info['furniture_type'] = furniture_type
        else:
            housing_info['furniture_type'] = "General"
    
    if diminishing_match := PAT_DIMINISHING_RETURN.search(txt):
        try:
            multiplier = float(diminishing_match.group(1))
            percentage = int(multiplier * 100)
            housing_info['diminishing_return'] = percentage
        except ValueError:
            pass
    
    return housing_info if housing_info else None

def parse_room_requirements(txt: str):
    room_reqs = {}
    
    if PAT_REQUIRE_ROOM_CONTAINMENT.search(txt):
        room_reqs['requires_containment'] = True
    
    if volume_match := PAT_REQUIRE_ROOM_VOLUME.search(txt):
        try:
            room_reqs['required_volume'] = int(volume_match.group(1))
        except ValueError:
            pass
    
    if tier_match := PAT_REQUIRE_ROOM_MATERIAL_TIER.search(txt):
        try:
            room_reqs['required_tier'] = float(tier_match.group(1))
        except ValueError:
            pass
    
    return room_reqs if room_reqs else None

def parse_nutrition(txt: str):
    nutrition = {}
    
    if cal := PAT_CALORIES.search(txt):
        nutrition['calories'] = int(cal.group(1))
    if carbs := PAT_CARBS.search(txt):
        nutrition['carbs'] = int(carbs.group(1))
    if protein := PAT_PROTEIN.search(txt):
        nutrition['protein'] = int(protein.group(1))
    if fat := PAT_FAT.search(txt):
        nutrition['fat'] = int(fat.group(1))
    if vitamins := PAT_VITAMINS.search(txt):
        nutrition['vitamins'] = int(vitamins.group(1))
    
    if nutrients := PAT_NUTRIENTS.search(txt):
        nutrient_text = nutrients.group(1)
        if "Nutrient.Calories" in nutrient_text or "Calories" in nutrient_text:
            cal_match = re.search(r"(?:Nutrient\.)?Calories\s*,\s*(\d+)", nutrient_text)
            if cal_match:
                nutrition['calories'] = int(cal_match.group(1))
        if "Nutrient.Carbohydrates" in nutrient_text or "Carbs" in nutrient_text:
            carb_match = re.search(r"(?:Nutrient\.)?(?:Carbohydrates|Carbs)\s*,\s*(\d+)", nutrient_text)
            if carb_match:
                nutrition['carbs'] = int(carb_match.group(1))
        if "Nutrient.Protein" in nutrient_text or "Protein" in nutrient_text:
            prot_match = re.search(r"(?:Nutrient\.)?Protein\s*,\s*(\d+)", nutrient_text)
            if prot_match:
                nutrition['protein'] = int(prot_match.group(1))
        if "Nutrient.Fat" in nutrient_text or "Fat" in nutrient_text:
            fat_match = re.search(r"(?:Nutrient\.)?Fat\s*,\s*(\d+)", nutrient_text)
            if fat_match:
                nutrition['fat'] = int(fat_match.group(1))
        if "Nutrient.Vitamins" in nutrient_text or "Vitamins" in nutrient_text:
            vit_match = re.search(r"(?:Nutrient\.)?Vitamins\s*,\s*(\d+)", nutrient_text)
            if vit_match:
                nutrition['vitamins'] = int(vit_match.group(1))
    
    if nutrition:
        log(f"Found nutrition data: {nutrition}")
    
    return nutrition if nutrition else None

def camel_case_to_spaced(name):
    """Convert CamelCase to spaced text"""
    import re
    # Insert space before uppercase letters that follow lowercase letters or numbers
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', name)
    return spaced

def spaced_to_camel_case(spaced_name):
    """Convert spaced text back to CamelCase"""
    return ''.join(word.capitalize() for word in spaced_name.split())

def parse_cs(path: str):
    try:
        txt = safe_read_file(path)
        if txt is None:
            return None
    except Exception as e:
        log(f"read fail {path}: {e}")
        return None
    
    recipe_result = None
    
    recipe_class_match = re.search(r'public\s+(?:partial\s+)?class\s+(\w+?)Recipe\s*:', txt, re.I)
    if recipe_class_match:
        recipe_name = recipe_class_match.group(1)
        if "new Recipe" in txt or "new RecipeFamily" in txt or "UpgradeRecipe" in txt or "RecipeVariant" in txt or "this.Init" in txt:
            m = PAT_RES.search(txt)
            if not m:
                m = PAT_RES_ALT.search(txt)
            if not m:
                m = PAT_UPGRADE.search(txt)
            if not m:
                m = PAT_VARIANT.search(txt)
            if not m and recipe_class_match:
                class FakeMatch:
                    def group(self, n):
                        return recipe_name
                m = FakeMatch()
                
            if m:
                rec = {"result_item": m.group(1), "type": "recipe"}
                rec["result_item"] = camel_case_to_spaced(rec["result_item"])
                
                if d := PAT_DESC.search(txt):
                    raw_description = d.group(1).strip()
                    rec["description"] = unescape_csharp_string(raw_description)
                
                weight = parse_weight(txt)
                if weight:
                    rec["weight"] = weight
                
                housing_info = parse_housing_info(txt)
                if housing_info:
                    rec["housing_info"] = housing_info

                room_reqs = parse_room_requirements(txt)
                if room_reqs:
                    rec["room_requirements"] = room_reqs
                
                ingredients_dict = {}
                for pat in (PAT_ING_STR, PAT_ING_TYPE, PAT_ING_GEN, PAT_ING_TAG, PAT_ING_NEW, PAT_ING_ITEM, PAT_ING_DIRECT, PAT_ING_CREATE):
                    for i, q in pat.findall(txt):
                        ingredient_name = i.replace("Item", "")
                        ingredient_name = camel_case_to_spaced(ingredient_name)  # FIX: Convert to spaced
                        if ingredient_name in ingredients_dict:
                            ingredients_dict[ingredient_name] = max(ingredients_dict[ingredient_name], int(q))
                        else:
                            ingredients_dict[ingredient_name] = int(q)
                
                rec["ingredients"] = [[name, qty] for name, qty in ingredients_dict.items()]
                
                if "Adorned" in rec["result_item"] and not rec["ingredients"]:
                    if "Basalt" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Basalt", 1], ["Gold", 1]]
                    elif "Granite" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Granite", 1], ["Gold", 1]]
                    elif "Limestone" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Limestone", 1], ["Gold", 1]]
                    elif "Sandstone" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Sandstone", 1], ["Gold", 1]]
                    elif "Shale" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Shale", 1], ["Gold", 1]]
                    elif "Gneiss" in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Gneiss", 1], ["Gold", 1]]
                    elif "Stone" in rec["result_item"] and "Sandstone" not in rec["result_item"] and "Limestone" not in rec["result_item"]:
                        rec["ingredients"] = [["Ashlar Stone", 1], ["Gold", 1]]
                
                if sk := PAT_REQSK.search(txt):
                    rec.update(skill=sk.group(1), level=int(sk.group(2)))
                else:
                    sk2, lv2 = PAT_SK.search(txt), PAT_LVL.search(txt)
                    if sk2 and lv2:
                        rec.update(skill=sk2.group(1).replace("Skill",""), level=int(lv2.group(1)))
                
                tb = next((p.search(txt) for p in PAT_TAB if p.search(txt)), None)
                if tb:
                    rec["crafting_table"] = camel_case_to_spaced(tb.group(1))  # FIX: Convert to spaced
                
                nutrition = parse_nutrition(txt)
                if nutrition:
                    rec["nutrition"] = nutrition
                
                recipe_result = rec
            else:
                recipe_result = {
                    "result_item": recipe_name,
                    "type": "item",
                    "description": "",
                    "ingredients": [],
                }
    else:
        if "new Recipe" in txt or "new RecipeFamily" in txt or "UpgradeRecipe" in txt or "RecipeVariant" in txt:
            m = PAT_RES.search(txt)
            if not m:
                m = PAT_RES_ALT.search(txt)
            if not m:
                m = PAT_UPGRADE.search(txt)
            if not m:
                m = PAT_VARIANT.search(txt)
                
            if m:
                rec = {"result_item": m.group(1), "type": "recipe"}
                rec["result_item"] = camel_case_to_spaced(rec["result_item"])  # FIX: Convert to spaced
                
                if d := PAT_DESC.search(txt):
                    raw_description = d.group(1).strip()
                    rec["description"] = unescape_csharp_string(raw_description)
                
                weight = parse_weight(txt)
                if weight:
                    rec["weight"] = weight
                
                ingredients_dict = {}
                for pat in (PAT_ING_STR, PAT_ING_TYPE, PAT_ING_GEN, PAT_ING_TAG, PAT_ING_NEW, PAT_ING_ITEM, PAT_ING_DIRECT, PAT_ING_CREATE):
                    for i, q in pat.findall(txt):
                        ingredient_name = i.replace("Item", "")
                        ingredient_name = camel_case_to_spaced(ingredient_name)  # FIX: Convert to spaced
                        if ingredient_name in ingredients_dict:
                            ingredients_dict[ingredient_name] = max(ingredients_dict[ingredient_name], int(q))
                        else:
                            ingredients_dict[ingredient_name] = int(q)
                
                rec["ingredients"] = [[name, qty] for name, qty in ingredients_dict.items()]
                
                if sk := PAT_REQSK.search(txt):
                    rec.update(skill=sk.group(1), level=int(sk.group(2)))
                else:
                    sk2, lv2 = PAT_SK.search(txt), PAT_LVL.search(txt)
                    if sk2 and lv2:
                        rec.update(skill=sk2.group(1).replace("Skill",""), level=int(lv2.group(1)))
                
                tb = next((p.search(txt) for p in PAT_TAB if p.search(txt)), None)
                if tb:
                    rec["crafting_table"] = camel_case_to_spaced(tb.group(1))  # FIX: Convert to spaced
                
                nutrition = parse_nutrition(txt)
                if nutrition:
                    rec["nutrition"] = nutrition
                
                recipe_result = rec
    
    item_results = []
    for m in PAT_ITEM_CLASS.finditer(txt):
        name = m.group(1)
        if recipe_result and recipe_result["result_item"] == name:
            continue
        
        desc_search_start = max(0, m.start() - 500)
        desc_search_end = min(len(txt), m.end() + 500)
        desc_text = txt[desc_search_start:desc_search_end]
        
        d = PAT_ITEM_DESC.search(desc_text)
        item_data = {
            "result_item": camel_case_to_spaced(name),
            "type": "item", 
            "description": "",
            "ingredients": [],
        }
        
        if d:
            raw_description = d.group(1).strip()
            item_data["description"] = unescape_csharp_string(raw_description)
        
        weight = parse_weight(desc_text)
        if weight:
            item_data["weight"] = weight
            
        housing_info = parse_housing_info(txt)
        if housing_info:
            item_data["housing_info"] = housing_info
        
        room_reqs = parse_room_requirements(txt)
        if room_reqs:
            item_data["room_requirements"] = room_reqs
        
        nutrition = parse_nutrition(txt)
        if nutrition:
            item_data["nutrition"] = nutrition
        
        item_results.append(item_data)
    
    if recipe_result:
        if item_results and item_results[0]['result_item'] == recipe_result['result_item']:
            if item_results[0].get('weight') and not recipe_result.get('weight'):
                recipe_result['weight'] = item_results[0]['weight']
            if item_results[0].get('nutrition') and not recipe_result.get('nutrition'):
                recipe_result['nutrition'] = item_results[0]['nutrition']
        return recipe_result
    elif item_results:
        return item_results[0]
    
    return None
    
class ThreadSafeGUI:
    """Thread-safe GUI update helper"""
    def __init__(self, root):
        self.root = root
        self.update_queue = []
    
    def schedule_update(self, func, *args, **kwargs):
        """Schedule a GUI update to run on the main thread"""
        self.root.after_idle(lambda: func(*args, **kwargs))

class GUI:
    def __init__(s, root):
        s.r = root
        s.r.geometry("1600x1200")  # Set initial window size
        
        # Setup window icon and title
        setup_window_icon_and_title(root)
        
        # Center the window on screen
        s._center_window(1600, 1200)
        
        # Initialize thread safety
        s.thread_helper = ThreadSafeGUI(root)
        s.parsing_active = False
        
        # Setup keyboard shortcuts for recipe navigation
        root.bind('<Tab>', lambda e: s.next_recipe() if s.current_item_recipes and len(s.current_item_recipes) > 1 else None)
        root.bind('<Shift-Tab>', lambda e: s.prev_recipe() if s.current_item_recipes and len(s.current_item_recipes) > 1 else None)
        root.bind('<Left>', lambda e: s.prev_recipe() if s.current_item_recipes and len(s.current_item_recipes) > 1 else None)
        root.bind('<Right>', lambda e: s.next_recipe() if s.current_item_recipes and len(s.current_item_recipes) > 1 else None)
        
        # Initialize data storage files with proper error handling
        s._init_data_files()
        
        # Initialize variables
        s.folder = tk.StringVar(value=DEFAULT_ECO_PATH)
        s.q = tk.StringVar()
        s.data = []
        s.filtered_data = []
        s.icons = {}
        s.small_icons = {}
        s.large_icons = {}
        s.selected_item = None
        s.current_recipe_index = 0
        s.current_item_recipes = []
        s.edit_mode = False

        # Cross-platform font handling
        s._setup_fonts()
        
        # Build UI
        s._create_ui()
        
        # Handle window close properly
        root.protocol('WM_DELETE_WINDOW', s._on_close)
    
    def _center_window(s, width, height):
        """Center the window on screen"""
        screen_width = s.r.winfo_screenwidth()
        screen_height = s.r.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        s.r.geometry(f"{width}x{height}+{x}+{y}")
    
    def _init_data_files(s):
        """Initialize data storage files with proper error handling"""
        script_dir = Path(__file__).parent
        
        # Notes file
        s.notes_file = script_dir / 'notes.json'
        try:
            if s.notes_file.exists():
                with open(s.notes_file, 'r', encoding='utf-8') as f:
                    s._notes = json.load(f)
            else:
                s._notes = {}
        except Exception as e:
            log(f"Failed to load notes.json: {e}")
            s._notes = {}
        
        # Tags file
        s.tags_file = script_dir / 'tags.json'
        try:
            if s.tags_file.exists():
                with open(s.tags_file, 'r', encoding='utf-8') as f:
                    preview = f.read(1024)
                    log(f"tags.json preview start: {preview!r}")
                    f.seek(0)
                    s._tags = json.load(f)
            else:
                s._tags = {}
        except json.JSONDecodeError as e:
            s._tags = {}
            log(f"JSON syntax error loading tags.json from {s.tags_file}: {e}")
            try:
                messagebox.showerror("Failed to load tags.json", f"JSON syntax error: {e}")
            except Exception:
                pass
        except Exception as e:
            s._tags = {}
            log(f"Unexpected error loading tags.json from {s.tags_file}: {e!r}")
            try:
                messagebox.showerror("Failed to load tags.json", f"Unexpected error: {e}")
            except Exception:
                pass
        
        # Hidden items file
        s.hidden_items_file = script_dir / 'hidden_items.json'
        try:
            if s.hidden_items_file.exists():
                with open(s.hidden_items_file, 'r', encoding='utf-8') as f:
                    s._hidden_items = set(json.load(f))
            else:
                s._hidden_items = set()
        except Exception as e:
            log(f"Failed to load hidden_items.json: {e}")
            s._hidden_items = set()
        
        # Custom edits file
        s.custom_edits_file = script_dir / 'custom_item_data.json'
        try:
            if s.custom_edits_file.exists():
                with open(s.custom_edits_file, 'r', encoding='utf-8') as f:
                    s._custom_edits = json.load(f)
            else:
                s._custom_edits = {}
        except Exception as e:
            log(f"Failed to load custom_item_data.json: {e}")
            s._custom_edits = {}
        
        # Dev items file
        s.dev_items_file = script_dir / 'dev_items.json'
        try:
            if s.dev_items_file.exists():
                with open(s.dev_items_file, 'r', encoding='utf-8') as f:
                    s._dev_items = set(json.load(f))
            else:
                s._dev_items = set()
        except Exception as e:
            log(f"Failed to load dev_items.json: {e}")
            s._dev_items = set()
    
    def _setup_fonts(s):
        """Set up fonts with cross-platform fallbacks"""
        script_dir = Path(__file__).parent
        fonts_dir = script_dir / 'Fonts'
        
        # Default system fonts
        s.tree_font = ('Arial', 18)
        s.main_text_font = ('Arial', 11, 'italic')
        s.nutrition_font = ('Arial', 10)
        s.nutrition_font_bold = ('Arial', 10, 'bold')
        s.ui_font = ('Arial', 10)
        s.ui_font_bold = ('Arial', 12, 'bold')
        s.description_font = ('Georgia', 14, 'italic')
        # Add room tier font for prominence
        s.room_tier_font = ('Arial', 14, 'bold')
        
        # Try to load custom fonts if available
        if fonts_dir.exists():
            try:
                raleway_path = fonts_dir / 'Raleway-Medium.ttf'
                if raleway_path.exists():
                    s.r.tk.call('font', 'create', 'Raleway', '-family', str(raleway_path), '-size', 18)
                    s.tree_font = ('Raleway', 16)
            except Exception as e:
                log(f"Failed to load Raleway font: {e}")
            
            try:
                dm_serif_path = fonts_dir / 'DMSerifText-Italic.ttf'
                if dm_serif_path.exists():
                    s.r.tk.call('font', 'create', 'DMSerifText', '-family', str(dm_serif_path), '-size', 11, '-slant', 'italic')
                    s.main_text_font = ('DMSerifText', 11, 'italic')
            except Exception as e:
                log(f"Failed to load DMSerifText font: {e}")
            
            try:
                arimo_path = fonts_dir / 'Arimo-VariableFont_wght.ttf'
                if arimo_path.exists():
                    s.r.tk.call('font', 'create', 'Arimo', '-family', str(arimo_path), '-size', 10)
                    s.nutrition_font = ('Arimo', 10)
                    s.nutrition_font_bold = ('Arimo', 10, 'bold')
            except Exception as e:
                log(f"Failed to load Arimo font: {e}")
            
            try:
                alice_path = fonts_dir / 'Alice-Regular.ttf'
                if alice_path.exists():
                    s.r.tk.call('font', 'create', 'Alice', '-family', str(alice_path), '-size', 10)
                    s.ui_font = ('Alice', 10)
                    s.ui_font_bold = ('Alice', 12, 'bold')
            except Exception as e:
                log(f"Failed to load Alice font: {e}")
            
            try:
                merriweather_path = fonts_dir / 'Merriweather-Italic.ttf'
                if merriweather_path.exists():
                    s.r.tk.call('font', 'create', 'MerriweatherItalic', '-family', str(merriweather_path), '-size', 14, '-slant', 'italic')
                    s.description_font = ('MerriweatherItalic', 14, 'italic')
                    log(f"Successfully loaded Merriweather font for descriptions")
            except Exception as e:
                log(f"Failed to load Merriweather font: {e}")
    
    def _create_ui(s):
        """Create the user interface"""
        # Use standard Tkinter Frame as main container instead of custom 9-patch content frame
        s.main_frame = s.r
        
        # Top section - control bar with parsing and folder selection
        top = tk.Frame(s.main_frame)
        top.pack(fill="x", padx=6, pady=6)
        
        # Parse button with enhanced styling
        parse_btn = tk.Button(top, text="PARSE ▶", command=s.run, 
                             font=s.ui_font_bold, 
                             bg='#4CAF50', fg='white',
                             padx=20, pady=10)
        parse_btn.pack(side="left", padx=(0, 15))
        
        # Visual separator
        tk.Label(top, text="|", font=('Arial', 14), fg='gray').pack(side="left", padx=10)
        
        # Path controls
        tk.Entry(top, textvariable=s.folder, width=50, font=s.ui_font).pack(side="left", padx=4)
        tk.Button(top, text="Eco Game Folder...", command=s.pick, font=s.ui_font).pack(side="left")
        tk.Button(top, text="Auto-Detect", command=s.auto_detect_eco, bg="lightgreen", font=s.ui_font).pack(side="left", padx=6)
        tk.Button(top, text="Refresh Images", command=s.refresh_images, bg="lightblue", font=s.ui_font).pack(side="left", padx=6)
        tk.Button(top, text="Hidden Items", command=s.show_hidden_items, bg="lightyellow", font=s.ui_font).pack(side="left", padx=2)
        
        # Status display
        s.st = tk.Label(top, fg="blue", font=s.ui_font)
        s.st.pack(side="left", padx=8)
        s.pb = ttk.Progressbar(top, mode="indeterminate", length=140)
        s.pb.pack(side="left", padx=4)

        # Search section
        sr = tk.Frame(s.main_frame)
        sr.pack(fill="x", padx=6, pady=(0,6))
        tk.Label(sr, text="Search:", font=s.ui_font).pack(side="left")
        e = tk.Entry(sr, textvariable=s.q, width=30, font=s.ui_font)
        e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", s.filter)
        
        # Filter buttons
        s.tags_filter_btn = tk.Button(sr, text="Tags", font=s.ui_font, width=10)
        s.tags_filter_btn.pack(side="left", padx=(20, 5))
        
        s.food_items_btn = tk.Button(sr, text="Food Items", font=s.ui_font, width=10)
        s.food_items_btn.pack(side="left", padx=(0, 5))
        
        s.current_filter_label = tk.Label(sr, text="", font=s.ui_font, fg="blue")
        s.current_filter_label.pack(side="left", padx=5)
        
        # Admin Tools Toggle - moved to right side for visibility
        s.admin_tools_btn = tk.Button(sr, text="Admin Tools", font=s.ui_font, bg="lightgray")
        s.admin_tools_btn.pack(side="right", padx=(5, 0))
        
        s.filter_tag = None
        
        # Nutrition sort controls (initially hidden)
        s.nutrition_sort_frame = tk.Frame(sr)
        tk.Label(s.nutrition_sort_frame, text="Sort by:", font=s.ui_font).pack(side="left", padx=(10, 5))
        
        s.sort_var = tk.StringVar(value="Name (A-Z)")
        s.sort_options = [
            "Name (A-Z)",
            "Name (Z-A)",
            "Calories ↑",
            "Calories ↓",
            "🔴 Carbohydrates ↑",
            "🔴 Carbohydrates ↓",
            "🟠 Protein ↑",
            "🟠 Protein ↓",
            "🟡 Fat ↑",
            "🟡 Fat ↓",
            "🟢 Vitamins ↑",
            "🟢 Vitamins ↓"
        ]
        
        s.sort_dropdown = ttk.Combobox(s.nutrition_sort_frame, textvariable=s.sort_var, 
                                      values=s.sort_options, state="readonly", width=18, font=s.ui_font)
        s.sort_dropdown.pack(side="left")
        s.sort_dropdown.bind("<<ComboboxSelected>>", lambda e: s.filter())

        # Main paned window with horizontal split
        pane = ttk.PanedWindow(s.main_frame, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=6)
        
        # Tree view on left (item list)
        tree_frame = tk.Frame(pane)
        
        # Enhanced scrollbar styling
        style = ttk.Style()
        style.configure("Custom.Vertical.TScrollbar",
                        width=20,
                        arrowsize=16,
                        borderwidth=2,
                        relief="raised")
        
        style.map("Custom.Vertical.TScrollbar",
                  background=[('active', '#4a90e2'), ('!active', '#6b9bd1')],
                  troughcolor=[('active', '#e0e0e0'), ('!active', '#f0f0f0')],
                  bordercolor=[('active', '#333333'), ('!active', '#666666')],
                  arrowcolor=[('active', '#ffffff'), ('!active', '#000000')],
                  darkcolor=[('active', '#4a90e2'), ('!active', '#6b9bd1')],
                  lightcolor=[('active', '#6b9bd1'), ('!active', '#8fb0d4')])
        
        s.tree = ttk.Treeview(tree_frame, show="tree")
        s.tree.column("#0", width=350)  # Set tree column width
        s.tree.bind("<<TreeviewSelect>>", s.show)
        s.tree.bind("<Button-1>", s._on_tree_click)
        s.tree.bind("<KeyPress>", s._on_tree_key_press)
        
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=s.tree.yview, style="Custom.Vertical.TScrollbar")
        s.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")
        s.tree.pack(side="left", fill="both", expand=True)
        
        # Tree styling
        tree_style = ttk.Style()
        tree_style.configure("Treeview", font=s.tree_font, rowheight=36)
        
        # Enhanced mouse wheel support for tree
        def on_mousewheel(event):
            s.tree.yview_scroll(int(-6*(event.delta/120)), "units")
            return "break"
        
        s.tree.bind("<MouseWheel>", on_mousewheel)
        s.tree.bind("<Button-4>", lambda e: s.tree.yview_scroll(-6, "units"))
        s.tree.bind("<Button-5>", lambda e: s.tree.yview_scroll(6, "units"))
        
        # Add tree frame to paned window
        pane.add(tree_frame, weight=1)

        # Main content paned window (vertical split for content and admin tools)
        content_pane = ttk.PanedWindow(pane, orient="vertical")
        
        # Main content area
        content_frame = tk.Frame(content_pane)
        
        # Top section with icon, room tier alert, and tag management
        top_section = tk.Frame(content_frame)
        top_section.pack(fill='x', pady=(0,4))
        
        # Left frame for room tier alert and tags (viewing only - public)
        left_frame = tk.Frame(top_section)
        left_frame.pack(side='left', anchor='nw', padx=(0,10), fill='x', expand=True)
        
        # ROOM TIER ALERT - This is the key enhancement!
        # Create a prominent frame for room tier requirements
        s.room_tier_alert_frame = tk.Frame(left_frame, relief='solid', borderwidth=2, bg='#8B0000')  # Dark red background
        # Note: This frame will only be packed when there's a room tier requirement to display
        
        s.room_tier_label = tk.Label(s.room_tier_alert_frame, text="", 
                                    font=s.room_tier_font, 
                                    fg='white', bg='#8B0000',  # White text on dark red
                                    padx=10, pady=5)
        s.room_tier_label.pack()
        
        # Tags section (below room tier alert)
        tk.Label(left_frame, text='Item Tags', font=s.ui_font_bold).pack(anchor='w', pady=(10,0))
        s.tags_display_frame = tk.Frame(left_frame)
        s.tags_display_frame.pack(anchor='w', pady=(0,6))
        
        # Icon display (centered but smaller allocation)
        s.ic = tk.Label(top_section)
        s.ic.pack(side='right', padx=(10,0))
        
        # Admin tools container - initially hidden
        s.admin_tools_container = tk.Frame(top_section)
        # Don't pack this initially - it will be packed when admin tools are shown
        
        # Admin tools frame (initially hidden)
        s.admin_tools_frame = tk.Frame(s.admin_tools_container, relief="ridge", borderwidth=2, bg='#ffe6e6')
        
        # Tag Management section (moved to admin tools)
        tag_mgmt_label = tk.Label(s.admin_tools_frame, text="Tag Management", font=s.ui_font_bold, fg='red', bg='#ffe6e6')
        tag_mgmt_label.pack(anchor='w', padx=2, pady=(2,0))
        
        # Initialize variables first
        s.current_suggestions = []
        s.tag_var = tk.StringVar()
        
        # Tag entry section (admin-only)
        tag_entry_frame = tk.Frame(s.admin_tools_frame, bg='#ffe6e6')
        tag_entry_frame.pack(anchor='w', pady=(0,5), padx=2)
        
        tk.Label(tag_entry_frame, text="Add Tag:", font=s.ui_font, bg='#ffe6e6').pack(side='left', padx=(0,5))
        s.fill_tag_entry = tk.Entry(tag_entry_frame, width=15, font=s.ui_font)
        s.fill_tag_entry.pack(side='left', padx=(0,10))
        s.fill_tag_entry.insert(0, "Fill Tag")
        s.fill_tag_entry.bind('<FocusIn>', s._clear_fill_tag_placeholder)
        s.fill_tag_entry.bind('<FocusOut>', s._restore_fill_tag_placeholder)
        s.fill_tag_entry.bind('<KeyRelease>', s._on_tag_entry_change)
        s.fill_tag_entry.bind('<Tab>', s._autocomplete_tag)
        s.fill_tag_entry.bind('<Down>', s._next_suggestion)
        s.fill_tag_entry.bind('<Up>', s._prev_suggestion)
        s.fill_tag_entry.bind('<Return>', lambda e: s._add_tag())
        s.fill_tag_entry.config(fg='gray')
        
        tk.Button(tag_entry_frame, text='Add Tag', command=s._add_tag, font=s.ui_font).pack(side='left')
        
        # Autocomplete frame (admin-only)
        s.autocomplete_frame = tk.Frame(s.admin_tools_frame, bg='#ffe6e6')
        s.autocomplete_listbox = tk.Listbox(s.autocomplete_frame, height=5, font=s.ui_font)
        s.autocomplete_listbox.bind('<<ListboxSelect>>', s._on_suggestion_select)
        s.autocomplete_scrollbar = tk.Scrollbar(s.autocomplete_frame, orient="vertical")
        s.autocomplete_listbox.config(yscrollcommand=s.autocomplete_scrollbar.set)
        s.autocomplete_scrollbar.config(command=s.autocomplete_listbox.yview)
        
        # Tag list (admin-only)
        tag_list_frame = tk.Frame(s.admin_tools_frame, relief="ridge", borderwidth=1, bg='white')
        tag_list_frame.pack(fill="x", pady=(5,5), padx=2)
        
        tk.Label(tag_list_frame, text="All Tags (double-click to add):", font=s.ui_font, bg='white').pack(anchor='w', padx=2, pady=2)
        
        tag_list_inner = tk.Frame(tag_list_frame, bg='white')
        tag_list_inner.pack(fill="x", padx=2, pady=2)
        
        tag_scrollbar = tk.Scrollbar(tag_list_inner, orient="vertical")
        s.all_tags_listbox = tk.Listbox(tag_list_inner, 
                                      yscrollcommand=tag_scrollbar.set,
                                      height=6,
                                      font=s.ui_font,
                                      selectmode="single",
                                      activestyle="dotbox",
                                      selectbackground="#4a90e2",
                                      selectforeground="white")
        tag_scrollbar.config(command=s.all_tags_listbox.yview)
        
        tag_scrollbar.pack(side="right", fill="y")
        s.all_tags_listbox.pack(side="left", fill="both", expand=True)
        
        all_tags = sorted({t for tags in s._tags.values() for t in tags})
        for tag in all_tags:
            s.all_tags_listbox.insert(tk.END, tag)
        
        def on_admin_tag_double_click(event):
            selection = s.all_tags_listbox.curselection()
            if selection:
                selected_tag = s.all_tags_listbox.get(selection[0])
                if s.selected_item:
                    if s.selected_item not in s._tags:
                        s._tags[s.selected_item] = []
                    if selected_tag not in s._tags[s.selected_item]:
                        s._tags[s.selected_item].append(selected_tag)
                        s._save_current()
                        s._update_tags_display(s.selected_item)
        
        def on_admin_tag_select(event):
            selection = s.all_tags_listbox.curselection()
            if selection:
                selected_tag = s.all_tags_listbox.get(selection[0])
        
        s.all_tags_listbox.bind('<Double-Button-1>', on_admin_tag_double_click)
        s.all_tags_listbox.bind('<<ListboxSelect>>', on_admin_tag_select)
        s.all_tags_listbox.bind('<KeyPress>', s._on_tag_key_press)
        
        # Image Operations section
        image_ops_label = tk.Label(s.admin_tools_frame, text="Image Operations", font=s.ui_font_bold, fg='red', bg='#ffe6e6')
        image_ops_label.pack(anchor='w', padx=2, pady=(10,2))
        
        # Single image replacement
        single_img_label = tk.Label(s.admin_tools_frame, text="Single Image Replace:", font=s.ui_font_bold, bg='#ffe6e6')
        single_img_label.pack(anchor='w', padx=2)
        
        s.image_path = tk.Entry(s.admin_tools_frame, width=25, font=s.ui_font)
        s.image_path.pack(fill="x", pady=1, padx=2)
        tk.Button(s.admin_tools_frame, text="Browse & Link", command=s._browse_image, font=s.ui_font).pack(fill="x", pady=1, padx=2)
        tk.Button(s.admin_tools_frame, text="AutoScan", command=s._auto_scan_image, font=s.ui_font, bg='#2196F3', fg='white').pack(fill="x", pady=1, padx=2)
        tk.Button(s.admin_tools_frame, text="Scan All Missing", command=s._scan_all_missing_images, font=s.ui_font, bg='#4CAF50', fg='white').pack(fill="x", pady=1, padx=2)
        
        # Foreground selection
        fg_frame = tk.Frame(s.admin_tools_frame, bg='#ffe6e6')
        fg_frame.pack(fill="x", pady=(16, 2), padx=2)
        tk.Label(fg_frame, text="Foreground:", font=s.ui_font, width=10, anchor="w", bg='#ffe6e6').pack(anchor="w")
        s.foreground_path = tk.Entry(fg_frame, width=25, font=s.ui_font)
        s.foreground_path.pack(fill="x", pady=1)
        s.foreground_path.bind("<KeyRelease>", s._check_combine_valid)
        tk.Button(fg_frame, text="Browse...", command=s._browse_foreground, font=s.ui_font).pack(fill="x", pady=1)
        
        # Background selection
        bg_frame = tk.Frame(s.admin_tools_frame, bg='#ffe6e6')
        bg_frame.pack(fill="x", pady=2, padx=2)
        tk.Label(bg_frame, text="Background:", font=s.ui_font, width=10, anchor="w", bg='#ffe6e6').pack(anchor="w")
        s.background_path = tk.Entry(bg_frame, width=25, font=s.ui_font)
        s.background_path.pack(fill="x", pady=1)
        s.background_path.bind("<KeyRelease>", s._check_combine_valid)
        tk.Button(bg_frame, text="Browse...", command=s._browse_background, font=s.ui_font).pack(fill="x", pady=1)
        
        # Combine button
        s.combine_btn = tk.Button(s.admin_tools_frame, text="Combine New Image", command=s._combine_images, 
                                 font=s.ui_font_bold, bg='#FF9800', fg='white', state='disabled')
        s.combine_btn.pack(fill="x", pady=(5, 10), padx=2)
        
        # DevItem checkbox
        s.dev_item_var = tk.BooleanVar()
        s.dev_item_check = tk.Checkbutton(s.admin_tools_frame, text="DevItem", variable=s.dev_item_var,
                                         font=s.ui_font, command=s._toggle_dev_item, bg='#ffe6e6')
        s.dev_item_check.pack(pady=(10, 0))
        
        # Initialize admin tools as hidden
        s.admin_tools_visible = False
        s.tag_remove_enabled = False
        
        # Create a container for description and recipe sections with proper proportions
        sections_container = tk.Frame(content_frame)
        sections_container.pack(fill="both", expand=True, pady=(0, 4))
        
        # Description frame with controlled height
        desc_frame = tk.Frame(sections_container, relief="solid", borderwidth=1)
        desc_frame.pack(fill="both", expand=False, pady=(0, 2))
        
        desc_header = tk.Frame(desc_frame)
        desc_header.pack(fill="x", padx=4, pady=2)
        
        tk.Label(desc_header, text="Item Description", font=s.ui_font_bold).pack(side="left")
        
        # Load pencil icon for edit functionality
        s.pencil_icon = None
        s.pencil_photo = None
        pencil_path = Path(__file__).parent / 'AppIcons' / 'Pencil.png'
        if pencil_path.exists() and Image:
            try:
                s.pencil_icon = Image.open(pencil_path).resize((20, 20), Image.LANCZOS)
                s.pencil_photo = ImageTk.PhotoImage(s.pencil_icon)
            except:
                pass
        
        edit_button_frame = tk.Frame(desc_header)
        edit_button_frame.pack(side="right", padx=5, pady=2)
        
        # Admin-only editing controls (initially hidden)
        s.edit_controls_frame = tk.Frame(edit_button_frame)
        
        # Admin-only formatting controls (initially hidden)
        s.formatting_frame = tk.Frame(s.edit_controls_frame)
        
        # Text size controls
        size_frame = tk.Frame(s.formatting_frame)
        size_frame.pack(side="left", padx=(0, 5))
        tk.Label(size_frame, text="Size:", font=(s.ui_font[0], 9)).pack(side="top")
        size_buttons_frame = tk.Frame(size_frame)
        size_buttons_frame.pack(side="top")
        
        tk.Button(size_buttons_frame, text="A-", command=lambda: s._change_text_size(-2), 
                 font=(s.ui_font[0], 8), width=3).pack(side="left")
        tk.Button(size_buttons_frame, text="A+", command=lambda: s._change_text_size(2), 
                 font=(s.ui_font[0], 8), width=3).pack(side="left")
        
        # Style controls
        style_frame = tk.Frame(s.formatting_frame)
        style_frame.pack(side="left", padx=(5, 5))
        tk.Label(style_frame, text="Style:", font=(s.ui_font[0], 9)).pack(side="top")
        style_buttons_frame = tk.Frame(style_frame)
        style_buttons_frame.pack(side="top")
        
        tk.Button(style_buttons_frame, text="B", command=lambda: s._toggle_bold(), 
                 font=(s.ui_font[0], 10, 'bold'), width=2).pack(side="left")
        tk.Button(style_buttons_frame, text="I", command=lambda: s._toggle_italic(), 
                 font=(s.ui_font[0], 10, 'italic'), width=2).pack(side="left")
        
        if s.pencil_photo:
            s.pencil_label = tk.Label(s.edit_controls_frame, image=s.pencil_photo, cursor='hand2')
            s.pencil_label.pack(side="left", padx=(5, 5))
            s.pencil_label.bind('<Button-1>', lambda e: s.toggle_edit_mode())
        
        desc_text_frame = tk.Frame(desc_frame)
        desc_text_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        
        desc_scroll = tk.Scrollbar(desc_text_frame)
        desc_scroll.pack(side="right", fill="y")
        
        # Description text widget - read-only by default
        s.desc_txt = tk.Text(desc_text_frame, wrap="word", font=s.main_text_font, 
                            height=8, yscrollcommand=desc_scroll.set, state="disabled")
        s.desc_txt.pack(side="left", fill="both", expand=True)
        desc_scroll.config(command=s.desc_txt.yview)
        
        # Recipe frame - compact with reduced height
        recipe_frame = tk.Frame(sections_container, relief="solid", borderwidth=1)
        recipe_frame.pack(fill="both", expand=False, pady=(2, 2))
        
        recipe_header = tk.Frame(recipe_frame)
        recipe_header.pack(fill="x", padx=4, pady=2)
        
        tk.Label(recipe_header, text="Recipe Information", font=s.ui_font_bold).pack(side="left")
        
        recipe_nav_frame = tk.Frame(recipe_header)
        recipe_nav_frame.pack(side="right")
        
        s.recipe_info_label = tk.Label(recipe_nav_frame, text="", font=s.ui_font, fg="blue")
        s.recipe_info_label.pack(side="left", padx=(0, 10))
        
        s.prev_recipe_btn = tk.Button(recipe_nav_frame, text="◀", 
                                     command=s.prev_recipe, font=s.ui_font, width=3, state="disabled")
        s.prev_recipe_btn.pack(side="left", padx=(0, 2))
        
        s.next_recipe_btn = tk.Button(recipe_nav_frame, text="▶", 
                                     command=s.next_recipe, font=s.ui_font, width=3, state="disabled")
        s.next_recipe_btn.pack(side="left")
        
        recipe_text_frame = tk.Frame(recipe_frame)
        recipe_text_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        
        recipe_scroll = tk.Scrollbar(recipe_text_frame)
        recipe_scroll.pack(side="right", fill="y")
        
        # Recipe section - reduced height so Notes section is visible
        s.recipe_txt = tk.Text(recipe_text_frame, wrap="word", font=s.main_text_font, 
                              height=6, yscrollcommand=recipe_scroll.set, state="disabled")
        s.recipe_txt.pack(side="left", fill="both", expand=True)
        recipe_scroll.config(command=s.recipe_txt.yview)
        
        # Separate "Used In" section with fixed height
        used_in_frame = tk.Frame(sections_container, relief="solid", borderwidth=1)
        used_in_frame.pack(fill="x", expand=False, pady=(2, 2))
        
        used_in_header = tk.Frame(used_in_frame)
        used_in_header.pack(fill="x", padx=4, pady=2)
        
        tk.Label(used_in_header, text="Used In", font=s.ui_font_bold).pack(side="left")
        
        used_in_text_frame = tk.Frame(used_in_frame)
        used_in_text_frame.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        
        used_in_scroll = tk.Scrollbar(used_in_text_frame)
        used_in_scroll.pack(side="right", fill="y")
        
        # Separate text widget for "Used In" section
        s.used_in_txt = tk.Text(used_in_text_frame, wrap="word", font=s.main_text_font, 
                               height=11, yscrollcommand=used_in_scroll.set, state="disabled")
        s.used_in_txt.pack(side="left", fill="both", expand=True)
        used_in_scroll.config(command=s.used_in_txt.yview)
        
        s.save_indicator = tk.Label(content_frame, text='', fg='green', font=s.ui_font)
        s.save_indicator.pack(anchor='e', padx=4)
        
        # Notes section (restored and now visible)
        # Admin-only notes formatting controls (initially hidden)
        s.notes_formatting_frame = tk.Frame(content_frame)
        
        # Font selection
        font_frame = tk.Frame(s.notes_formatting_frame)
        font_frame.pack(side="left", padx=(0, 10))
        tk.Label(font_frame, text="Font:", font=(s.ui_font[0], 9)).pack(side="top")
        
        import tkinter.font as tkFont
        s.available_fonts = sorted(tkFont.families())
        s.font_var = tk.StringVar(value="Arial")
        s.font_dropdown = ttk.Combobox(font_frame, textvariable=s.font_var, 
                                      values=s.available_fonts, state="readonly", width=12)
        s.font_dropdown.pack(side="top")
        s.font_dropdown.bind("<<ComboboxSelected>>", s._apply_font_change)
        
        # Size controls
        size_frame = tk.Frame(s.notes_formatting_frame)
        size_frame.pack(side="left", padx=(0, 10))
        tk.Label(size_frame, text="Size:", font=(s.ui_font[0], 9)).pack(side="top")
        size_buttons_frame = tk.Frame(size_frame)
        size_buttons_frame.pack(side="top")
        
        tk.Button(size_buttons_frame, text="A-", command=lambda: s._change_notes_size(-2), 
                 font=(s.ui_font[0], 8), width=3).pack(side="left")
        tk.Button(size_buttons_frame, text="A+", command=lambda: s._change_notes_size(2), 
                 font=(s.ui_font[0], 8), width=3).pack(side="left")
        
        # Style controls
        style_frame = tk.Frame(s.notes_formatting_frame)
        style_frame.pack(side="left", padx=(0, 10))
        tk.Label(style_frame, text="Style:", font=(s.ui_font[0], 9)).pack(side="top")
        style_buttons_frame = tk.Frame(style_frame)
        style_buttons_frame.pack(side="top")
        
        tk.Button(style_buttons_frame, text="B", command=s._toggle_notes_bold, 
                 font=(s.ui_font[0], 10, 'bold'), width=2).pack(side="left")
        tk.Button(style_buttons_frame, text="I", command=s._toggle_notes_italic, 
                 font=(s.ui_font[0], 10, 'italic'), width=2).pack(side="left")
        
        # Color controls
        color_frame = tk.Frame(s.notes_formatting_frame)
        color_frame.pack(side="left", padx=(0, 10))
        tk.Label(color_frame, text="Color:", font=(s.ui_font[0], 9)).pack(side="top")
        color_buttons_frame = tk.Frame(color_frame)
        color_buttons_frame.pack(side="top")
        
        # Text color
        s.text_color_btn = tk.Button(color_buttons_frame, text="Text", command=s._choose_text_color, 
                                    font=(s.ui_font[0], 8), width=4, bg="black", fg="white")
        s.text_color_btn.pack(side="left", padx=(0, 2))
        
        # Highlight color
        s.highlight_color_btn = tk.Button(color_buttons_frame, text="High", command=s._choose_highlight_color, 
                                         font=(s.ui_font[0], 8), width=4, bg="yellow", fg="black")
        s.highlight_color_btn.pack(side="left")
        
        notes_label = tk.Label(content_frame, text='Notes:', font=s.ui_font)
        notes_label.pack(anchor='w', padx=4, pady=(4,0))
        
        notes_frame = tk.Frame(content_frame)
        notes_frame.pack(fill='both', expand=True, padx=4, pady=(0,6))
        
        notes_scroll = tk.Scrollbar(notes_frame, orient="vertical")
        notes_scroll.pack(side="right", fill="y")
        
        # Notes section now expands to fill remaining space
        s.notes = tk.Text(notes_frame, wrap='word', font=s.ui_font, yscrollcommand=notes_scroll.set)
        s.notes.pack(side="left", fill='both', expand=True)
        notes_scroll.config(command=s.notes.yview)
        
        # Bind notes to save when modified
        s.notes.bind('<KeyRelease>', lambda e: s._save_current())
        s.notes.bind('<FocusOut>', lambda e: s._save_current())
        
        content_pane.add(content_frame, weight=1)
        
        # Add content pane to main paned window
        pane.add(content_pane, weight=2)
        
        # Configure text widget tags for all text widgets
        for txt_widget in [s.desc_txt, s.recipe_txt, s.used_in_txt]:
            txt_widget.tag_config('item_name', font=(s.main_text_font[0], 14, 'bold'))
            txt_widget.tag_config('dev_marker', font=(s.main_text_font[0], 11, 'bold'), foreground='red')
            txt_widget.tag_config('nutrition_header', font=(s.main_text_font[0], 12, 'bold'))
            txt_widget.tag_config('section_header', font=(s.main_text_font[0], 12, 'bold'))
            txt_widget.tag_config('building_info', font=s.main_text_font, foreground='#006400')
            txt_widget.tag_config('calorie_count', font=(s.main_text_font[0], 10, 'italic'), foreground='#444444')
            txt_widget.tag_config('calorie_count_display', font=s.nutrition_font_bold, 
                            foreground='black', background='#E0E0E0')
            txt_widget.tag_config('weight_info', font=(s.main_text_font[0], 11, 'bold'), foreground='#8B4513')
            txt_widget.tag_config('furnishing_value', font=(s.main_text_font[0], 11, 'bold'), foreground='#006400')
            txt_widget.tag_config('room_category', font=(s.main_text_font[0], 11, 'bold'), foreground='#FF8C00')
            txt_widget.tag_config('furniture_type', font=(s.main_text_font[0], 11, 'bold'), foreground='#006400')
            txt_widget.tag_config('diminishing_return', font=s.main_text_font, foreground='#000000')
            # Reduced emphasis on room requirements in description since they're now prominent at top
            txt_widget.tag_config('room_requirement', font=(s.main_text_font[0], 10), foreground='#666666')
            
            txt_widget.tag_config('description', font=s.description_font, foreground='#2F4F4F')
            
            for nutrient, colors in NUTRIENT_COLORS.items():
                txt_widget.tag_config(f'nutrient_{nutrient}', 
                                foreground=colors['fg'], 
                                background=colors['bg'],
                                font=s.nutrition_font_bold)
        
        # Connect button event handlers
        s.tags_filter_btn.config(command=s.toggle_tags_filter)
        s.food_items_btn.config(command=s.toggle_food_filter)
        s.admin_tools_btn.config(command=s.toggle_admin_tools)

    def auto_detect_eco(s):
        """Auto-detect Eco installation paths"""
        log("Starting auto-detection of Eco game paths...")
        s.st.config(text='Auto-detecting Eco paths...')
        s.pb.start()
        
        try:
            paths = get_default_eco_paths()
            if isinstance(paths, Path) and paths.exists():
                s.folder.set(str(paths))
                s.st.config(text=f'Found Eco at: {paths}')
                log(f"Auto-detected Eco path: {paths}")
            else:
                s.st.config(text='No Eco installation found automatically')
                log("No Eco installation found during auto-detection")
                messagebox.showinfo("Auto-Detection", 
                                  "Could not automatically find Eco installation.\n"
                                  "Please use 'Eco Game Folder...' to select manually.")
        finally:
            s.pb.stop()

    def pick(s):
        """Pick Eco folder with better path handling"""
        initial_dir = s.folder.get() if Path(s.folder.get()).exists() else str(Path.home())
        d = filedialog.askdirectory(title="Select Eco/Mods folder", initialdir=initial_dir)
        if d:
            s.folder.set(str(Path(d)))

    def refresh_images(s):
        if not s.data:
            messagebox.showwarning("No Data", "Parse recipes first before refreshing images.")
            return
        
        s.st.config(text='Refreshing images...')
        s.pb.start()
        
        s.icons.clear()
        s.small_icons.clear()
        s.large_icons.clear()
        
        if hasattr(s, '_skill_icons'):
            s._skill_icons.clear()
        if hasattr(s, '_table_icons'):
            s._table_icons.clear()
        if hasattr(s, '_ingredient_icons'):
            s._ingredient_icons.clear()
        
        script_dir = Path(__file__).parent
        ico_dir = script_dir / 'EcoIcons'
        
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            
            # Try multiple naming conventions for icon files
            possible_names = [
                name,  # Try exact name first (e.g., "Acorn Powder")
                spaced_to_camel_case(name),  # Try CamelCase (e.g., "AcornPowder")
                name.replace(" ", ""),  # Try without spaces (e.g., "AcornPowder")
                name.replace(" ", "_"),  # Try with underscores (e.g., "Acorn_Powder")
            ]
            
            icon_found = False
            for icon_name in possible_names:
                icon_path = ico_dir / f"{icon_name}.png"
                
                if icon_path.exists() and Image:
                    try:
                        s.icons[name] = str(icon_path)
                        im = Image.open(icon_path).resize((32, 32), Image.LANCZOS)
                        small_img = ImageTk.PhotoImage(im)
                        s.small_icons[idx] = small_img
                        icon_found = True
                        break
                    except:
                        continue
            
            if not icon_found:
                small_img = s._placeholder_red_small()
                s.small_icons[idx] = small_img
        
        s.filter()
        
        if s.selected_item:
            s.show()
        
        s.st.config(text=f'Images refreshed for {len(s.data)} items.')
        s.pb.stop()
        messagebox.showinfo("Refresh Complete", "All images have been refreshed from the icon folders.")

    def run(s):
        """Start parsing with improved error handling"""
        base_path = Path(s.folder.get())
        if not base_path.exists() or not base_path.is_dir():
            messagebox.showwarning("Error", "Please select a valid folder containing Eco game files.")
            return
        
        if s.parsing_active:
            messagebox.showwarning("Parsing in Progress", "Parsing is already in progress. Please wait.")
            return
        
        s.parsing_active = True
        s.st.config(text='Parsing...')
        s.pb.start()
        s.tree.delete(*s.tree.get_children())
        s.icons.clear()
        s.data.clear()
        
        # Start parsing in background thread
        threading.Thread(target=s._worker, args=(str(base_path),), daemon=True).start()

    def _worker(s, base):
        """Worker thread for parsing with improved error handling and progress updates"""
        try:
            log(f"Starting parse worker for path: {base}")
            base_path = Path(base)
            
            recipes_by_item = {}
            items = {}
            species_drops = {}
            
            # Determine search paths with better logic
            search_paths = s._get_search_paths(base_path)
            
            log(f"=== Searching in {len(search_paths)} directories ===")
            for path in search_paths:
                log(f"  - {path}")
            
            total_files = 0
            processed_files = 0
            
            # Count total .cs files first for progress tracking
            for search_path in search_paths:
                try:
                    for item in search_path.rglob("*.cs"):
                        if item.is_file():
                            total_files += 1
                except PermissionError:
                    log(f"Permission denied accessing: {search_path}")
                    continue
                except Exception as e:
                    log(f"Error counting files in {search_path}: {e}")
                    continue
            
            log(f"Found {total_files} C# files to process")
            
            # Process files
            for search_path in search_paths:
                try:
                    for cs_file in search_path.rglob("*.cs"):
                        if not cs_file.is_file():
                            continue
                        
                        processed_files += 1
                        
                        # Update progress periodically
                        if processed_files % 50 == 0:
                            progress = (processed_files / total_files) * 100 if total_files > 0 else 0
                            s.thread_helper.schedule_update(
                                s.st.config, 
                                text=f'Parsing... {processed_files}/{total_files} files ({progress:.1f}%)'
                            )
                        
                        try:
                            # Check if file contains important items for debugging
                            important_items = ['Dirt', 'Sulfur', 'Stone', 'Sand', 'Clay', 'Coal', 'Crushed']
                            for item in important_items:
                                if item.lower() in cs_file.name.lower():
                                    log(f"Found file containing '{item}': {cs_file}")
                            
                            # Parse individual files with improved error handling
                            if result := parse_cs(str(cs_file)):
                                name = result['result_item']
                                if 'ingredients' in result and result['ingredients']:
                                    if name not in recipes_by_item:
                                        recipes_by_item[name] = []
                                    result['source_file'] = cs_file.name
                                    recipes_by_item[name].append(result)
                                elif name not in items:
                                    result['source_file'] = cs_file.name
                                    items[name] = result
                                    
                                    # Log important basic items
                                    if any(target in name for target in ['Dirt', 'Sulfur', 'Sand', 'Clay', 'Coal', 'Stone', 'Crushed']):
                                        log(f"✓ FOUND ITEM: {name} in {cs_file.name}")
                                    
                        except Exception as e:
                            log(f"Error processing {cs_file}: {e}")
                            continue
                            
                except PermissionError:
                    log(f"Permission denied accessing: {search_path}")
                    continue
                except Exception as e:
                    log(f"Error processing search path {search_path}: {e}")
                    continue
            
            log(f"\n=== PARSING COMPLETE ===")
            log(f"Found {sum(len(recipe_list) for recipe_list in recipes_by_item.values())} total recipes for {len(recipes_by_item)} items")
            log(f"Found {len(items)} non-recipe items")
            
            important_items = ["Dirt", "Sulfur", "Crushed Sandstone", "Crushed Limestone", "Crushed Granite", 
                              "Crushed Shale", "Crushed Gneiss", "Crushed Basalt", "Sand", "Clay", "Coal",
                              "Iron Ore", "Copper Ore", "Gold Ore", "Stone", "Granite", "Limestone", "Sandstone"]
            
            log("\n=== Checking for Important Basic Items ===")
            for item in important_items:
                if item in recipes_by_item:
                    log(f"✓ Found recipe for {item}")
                elif item in items:
                    log(f"✓ Found {item} as item (no recipe)")
                else:
                    log(f"✗ MISSING: {item}")
            
            # Process species drops
            s._process_species_drops(search_paths, species_drops)
            
            # Merge and deduplicate data
            merged = s._merge_and_deduplicate(items, recipes_by_item, species_drops)
            
            # Sort results
            merged_list = list(merged.values())
            merged_list.sort(key=lambda x: x['result_item'].lower())
            s.data = merged_list
            
            log(f"\n=== FINAL COUNT: {len(s.data)} total items ===")
            
            data_items = {item['result_item'] for item in s.data}
            missing = []
            for item in important_items:
                if item not in data_items:
                    missing.append(item)
            
            if missing:
                log(f"\n⚠️ Still missing: {', '.join(missing)}")
            else:
                log(f"\n✓ All important items found!")
            
            # Load icons
            s._load_icons()
            
            # Finish on main thread
            s.thread_helper.schedule_update(s._finish_parse)
            
        except Exception as e:
            log(f"Fatal error in worker thread: {e}")
            s.thread_helper.schedule_update(
                messagebox.showerror, 
                "Parsing Error", 
                f"An error occurred during parsing:\n{e}\n\nCheck the log file for details."
            )
        finally:
            s.parsing_active = False
            s.thread_helper.schedule_update(s.pb.stop)
    
    def _get_search_paths(s, base_path):
        """Get appropriate search paths based on the selected folder"""
        search_paths = []
        
        # Add the base path
        search_paths.append(base_path)
        
        # Check if this looks like an Eco installation and find Mods folder
        if 'eco' in base_path.name.lower() and not 'mods' in base_path.name.lower():
            possible_mods = [
                base_path / 'Mods',
                base_path / 'Eco_Data' / 'Server' / 'Mods',
                base_path / 'Server' / 'Mods',
                base_path / 'Client' / 'Mods',
            ]
            for mods_path in possible_mods:
                if mods_path.exists() and mods_path.is_dir():
                    search_paths = [mods_path]  # Replace base path with Mods path
                    log(f"Found Mods folder at: {mods_path}")
                    break
        
        # If we're in a Mods folder, add special subdirectories
        if 'mods' in str(search_paths[0]).lower():
            mods_path = search_paths[0]
            
            core_path = mods_path / '__core__'
            if core_path.exists():
                search_paths.append(core_path)
                log(f"Added __core__ directory: {core_path}")
                
                # Add core subdirectories
                try:
                    for subdir in core_path.iterdir():
                        if subdir.is_dir():
                            search_paths.append(subdir)
                            log(f"Added __core__ subdirectory: {subdir}")
                except PermissionError:
                    log(f"Permission denied accessing {core_path}")
            
            autogen_path = mods_path / 'AutoGen'
            if autogen_path.exists():
                search_paths.append(autogen_path)
                log(f"Added AutoGen directory: {autogen_path}")
            
            usercode_path = mods_path / 'UserCode'
            if usercode_path.exists():
                search_paths.append(usercode_path)
                log(f"Added UserCode directory: {usercode_path}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_paths = []
        for path in search_paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)
        
        return unique_paths
    
    def _process_species_drops(s, search_paths, species_drops):
        """Process species drop information"""
        for search_path in search_paths:
            try:
                for cs_file in search_path.rglob("*.cs"):
                    if not cs_file.is_file():
                        continue
                        
                    # Check if filename suggests it's a species file
                    if any(x in cs_file.name for x in ['Species', 'Tree', 'Plant', 'Animal']):
                        try:
                            txt = safe_read_file(str(cs_file))
                            if txt is None:
                                continue
                                
                            species_match = re.search(r'class\s+(\w+?)(?:Species|Tree|Plant|Animal)', txt)
                            if species_match:
                                species_name = species_match.group(1)
                                
                                drop_patterns = [
                                    re.compile(r'ResourceItem\s*=\s*typeof\((\w+?)Item\)', re.I),
                                    re.compile(r'new\s+Yield\s*\(\s*typeof\s*\(\s*(\w+?)Item\s*\)', re.I),
                                    re.compile(r'SpeciesResource\s*\(\s*typeof\s*\(\s*(\w+?)Item\s*\)', re.I),
                                ]
                                
                                for pattern in drop_patterns:
                                    for match in pattern.finditer(txt):
                                        item_name = camel_case_to_spaced(match.group(1))  # FIX: Convert to spaced
                                        if item_name not in species_drops:
                                            species_drops[item_name] = []
                                        species_drops[item_name].append(species_name)
                        except Exception as e:
                            log(f"Error processing species file {cs_file}: {e}")
                            continue
            except Exception as e:
                log(f"Error processing species drops in {search_path}: {e}")
                continue
    
    def _merge_and_deduplicate(s, items, recipes_by_item, species_drops):
        """Merge items and recipes, deduplicate, and add relationships"""
        merged = {}
        merged.update(items)
        
        # Process recipes
        for name, recipe_list in recipes_by_item.items():
            if len(recipe_list) == 1:
                recipe_data = recipe_list[0]
                if name in merged and 'nutrition' in merged[name] and 'nutrition' not in recipe_data:
                    recipe_data['nutrition'] = merged[name]['nutrition']
                if name in merged and 'weight' in merged[name] and 'weight' not in recipe_data:
                    recipe_data['weight'] = merged[name]['weight']
                merged[name] = recipe_data
            else:
                # Deduplicate multiple recipes
                unique_recipes = []
                seen_signatures = set()
                
                for recipe in recipe_list:
                    ingredients = recipe.get('ingredients', [])
                    hashable_ingredients = tuple(sorted(tuple(ing) if isinstance(ing, list) else ing for ing in ingredients))
                    
                    signature = (
                        recipe.get('skill', ''),
                        recipe.get('level', 0),
                        recipe.get('crafting_table', ''),
                        hashable_ingredients,
                        recipe.get('description', '')
                    )
                    
                    if signature not in seen_signatures:
                        unique_recipes.append(recipe)
                        seen_signatures.add(signature)
                    else:
                        log(f"Filtered out duplicate recipe for '{name}' from {recipe.get('source_file', 'unknown')}")
                
                if len(unique_recipes) == 1:
                    recipe_data = unique_recipes[0]
                    if name in merged and 'nutrition' in merged[name] and 'nutrition' not in recipe_data:
                        recipe_data['nutrition'] = merged[name]['nutrition']
                    if name in merged and 'weight' in merged[name] and 'weight' not in recipe_data:
                        recipe_data['weight'] = merged[name]['weight']
                    merged[name] = recipe_data
                    log(f"Item '{name}' had {len(recipe_list)} recipes but only 1 unique after deduplication")
                else:
                    primary_recipe = unique_recipes[0].copy()
                    primary_recipe['recipe_variants'] = unique_recipes
                    primary_recipe['has_multiple_recipes'] = True
                    
                    if name in merged and 'nutrition' in merged[name]:
                        primary_recipe['nutrition'] = merged[name]['nutrition']
                    if name in merged and 'weight' in merged[name]:
                        primary_recipe['weight'] = merged[name]['weight']
                    
                    merged[name] = primary_recipe
                    log(f"Item '{name}' has {len(unique_recipes)} unique recipe variants (was {len(recipe_list)} before deduplication)")

        # Add species drop information
        for item_name, species_list in species_drops.items():
            if item_name in merged:
                merged[item_name]['harvested_from'] = sorted(set(species_list))
        
        # Add "used in" relationships
        used_in = {}
        for recipe_name, recipe_data in merged.items():
            if 'ingredients' in recipe_data and recipe_data['ingredients']:
                for ingredient, _ in recipe_data['ingredients']:
                    if ingredient not in used_in:
                        used_in[ingredient] = []
                    used_in[ingredient].append(recipe_name)
        
        for item_name in merged:
            if item_name in used_in:
                merged[item_name]['used_in'] = sorted(used_in[item_name])
        
        return merged
    
    def _load_icons(s):
        """Load icons with cross-platform path handling"""
        script_dir = Path(__file__).parent
        ico_dir = script_dir / 'EcoIcons'
        
        if not ico_dir.exists():
            log(f"Icon directory not found: {ico_dir}")
            return
        
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            
            # Try multiple naming conventions for icon files
            possible_names = [
                name,  # Try exact name first (e.g., "Acorn Powder")
                spaced_to_camel_case(name),  # Try CamelCase (e.g., "AcornPowder")
                name.replace(" ", ""),  # Try without spaces (e.g., "AcornPowder")
                name.replace(" ", "_"),  # Try with underscores (e.g., "Acorn_Powder")
            ]
            
            icon_found = False
            for icon_name in possible_names:
                icon_path = ico_dir / f"{icon_name}.png"
                
                if icon_path.exists() and Image:
                    try:
                        s.icons[name] = str(icon_path)
                        im = Image.open(icon_path).resize((32, 32), Image.LANCZOS)
                        small_img = ImageTk.PhotoImage(im)
                        s.small_icons[idx] = small_img
                        icon_found = True
                        break
                    except Exception as e:
                        log(f"Error loading icon for {name} from {icon_path}: {e}")
                        continue
            
            if not icon_found:
                small_img = s._placeholder_red_small()
                s.small_icons[idx] = small_img
    
    def _finish_parse(s):
        """Finish parsing on main thread"""
        try:
            s.filter()
            s.st.config(text=f'{len(s.data)} items loaded.')
            
            # Log sample of loaded items
            log("\n=== Sample of loaded items ===")
            keywords = ['dirt', 'sulfur', 'crushed', 'sand', 'clay', 'coal', 'stone', 'ore']
            for keyword in keywords:
                matching = [item['result_item'] for item in s.data if keyword in item['result_item'].lower()]
                if matching:
                    log(f"Items containing '{keyword}': {', '.join(matching[:10])}")
                    if len(matching) > 10:
                        log(f"  ... and {len(matching) - 10} more")
            
            s.pb.stop()
            s.parsing_active = False
            
        except Exception as e:
            log(f"Error finishing parse: {e}")
            messagebox.showerror("Error", f"Error completing parse: {e}")

    def filter(s, *_):
        q = s.q.get().lower()
        s.tree.delete(*s.tree.get_children())
        s.filtered_data = []
        
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            
            if name in s._hidden_items:
                continue
            
            if s.filter_tag:
                item_tags = s._tags.get(name, [])
                if s.filter_tag not in item_tags:
                    continue
            
            tags = s._tags.get(name, [])
            name_lower = name.lower()
            
            match = False
            if q:
                if q in name_lower:
                    match = True
                elif q in name_lower.replace('item', ''):
                    match = True
                elif any(q in t.lower() for t in tags):
                    match = True
                elif (q + 'item') in name_lower:
                    match = True
                elif rec.get('description') and q in rec.get('description', '').lower():
                    match = True
            else:
                match = True
            
            if match:
                s.filtered_data.append(rec)
        
        if s.filter_tag and s.filter_tag.lower() == 'food':
            s.nutrition_sort_frame.pack(side="left", padx=(10, 0))
        else:
            s.nutrition_sort_frame.pack_forget()
            s.sort_var.set("Name (A-Z)")
        
        sort_option = s.sort_var.get()
        
        if sort_option == "Name (A-Z)":
            s.filtered_data.sort(key=lambda x: x['result_item'].lower())
        elif sort_option == "Name (Z-A)":
            s.filtered_data.sort(key=lambda x: x['result_item'].lower(), reverse=True)
        else:
            nutrient_map = {
                "Calories": "calories",
                "Carbohydrate": "carbs",
                "Protein": "protein",
                "Fat": "fat",
                "Vitamins": "vitamins"
            }
            
            for nutrient_display, nutrient_key in nutrient_map.items():
                if nutrient_display.lower() in sort_option.lower():
                    reverse = "↓" in sort_option
                    
                    def get_nutrient_value(item):
                        nutrition = item.get('nutrition', {})
                        if nutrient_key == 'calories' and nutrient_key not in nutrition:
                            calc_calories = (nutrition.get('carbs', 0) * 4 + 
                                           nutrition.get('protein', 0) * 4 + 
                                           nutrition.get('fat', 0) * 9)
                            return calc_calories if calc_calories > 0 else -1
                        return nutrition.get(nutrient_key, -1)
                    
                    items_with_nutrition = [item for item in s.filtered_data if item.get('nutrition')]
                    items_without_nutrition = [item for item in s.filtered_data if not item.get('nutrition')]
                    
                    items_with_nutrition.sort(key=get_nutrient_value, reverse=reverse)
                    
                    s.filtered_data = items_with_nutrition + sorted(items_without_nutrition, 
                                                                   key=lambda x: x['result_item'].lower())
                    break
        
        for filtered_idx, rec in enumerate(s.filtered_data):
            name = rec['result_item']
            orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), 0)
            
            if name in s._dev_items:
                script_dir = Path(__file__).parent
                missing_icon_path = script_dir / 'AppIcons' / 'MissingIcon.png'
                if missing_icon_path.exists() and Image:
                    try:
                        im = Image.open(missing_icon_path).resize((32, 32), Image.LANCZOS)
                        icon_img = ImageTk.PhotoImage(im)
                    except:
                        icon_img = s.small_icons.get(orig_idx, s._placeholder_red_small())
                else:
                    icon_img = s.small_icons.get(orig_idx, s._placeholder_red_small())
            else:
                icon_img = s.small_icons.get(orig_idx, s._placeholder_red_small())
            
            display_text = f"– {name}"  # Already spaced
            if s.filter_tag and s.filter_tag.lower() == 'food' and rec.get('nutrition'):
                nutrition = rec['nutrition']
                if "Calories" in s.sort_var.get():
                    cal_val = nutrition.get('calories', 0)
                    if cal_val == 0:
                        cal_val = (nutrition.get('carbs', 0) * 4 + 
                                 nutrition.get('protein', 0) * 4 + 
                                 nutrition.get('fat', 0) * 9)
                    emoji = "🔺" if cal_val < 0 else ""
                    display_text += f" {emoji}({cal_val} cal)"
                elif "Carbohydrates" in s.sort_var.get():
                    val = nutrition.get('carbs', 0)
                    emoji = "🔴" if val < 0 else "🔴"
                    display_text += f" {emoji} ({val} carbs)"
                elif "Protein" in s.sort_var.get():
                    val = nutrition.get('protein', 0)
                    emoji = "🟠" if val < 0 else "🟠"
                    display_text += f" {emoji} ({val} protein)"
                elif "Fat" in s.sort_var.get():
                    val = nutrition.get('fat', 0)
                    emoji = "🟡" if val < 0 else "🟡"
                    display_text += f" {emoji} ({val} fat)"
                elif "Vitamins" in s.sort_var.get():
                    val = nutrition.get('vitamins', 0)
                    emoji = "🟢" if val < 0 else "🟢"
                    display_text += f" {emoji} ({val} vit)"
            
            s.tree.insert('', 'end', iid=str(filtered_idx), text=display_text, image=icon_img)

    def _on_tree_click(s, event):
        region = s.tree.identify_region(event.x, event.y)
        if region != "tree":
            return
            
        item = s.tree.identify_row(event.y)
        if not item:
            return
        
        column = s.tree.identify_column(event.x)
        
        bbox = s.tree.bbox(item, column)
        if bbox:
            cell_x = event.x - bbox[0]
            
            if cell_x < 70:
                idx = int(item)
                if idx < len(s.filtered_data):
                    item_name = s.filtered_data[idx]['result_item']
                    s.hide_item(item_name)
                    return 'break'

    def hide_item(s, item_name):
        if messagebox.askyesno("Hide Item", f"Hide '{item_name}' from the list?"):
            s._hidden_items.add(item_name)
            s._save_hidden_items()
            s.filter()
            s.st.config(text=f"Hidden '{item_name}'")
            
    def _on_tag_key_press(s, event):
        char = event.char.upper()
        
        if not char.isalpha():
            return
        
        for i in range(s.all_tags_listbox.size()):
            tag = s.all_tags_listbox.get(i)
            if tag.upper().startswith(char):
                s.all_tags_listbox.selection_clear(0, tk.END)
                s.all_tags_listbox.selection_set(i)
                s.all_tags_listbox.see(i)
                return
            
    def _on_tree_key_press(s, event):
        char = event.char.upper()
        
        if not char.isalpha():
            return
        
        for idx, rec in enumerate(s.filtered_data):
            item_name = rec['result_item']
            if item_name.upper().startswith(char):
                s.tree.selection_set(str(idx))
                s.tree.see(str(idx))
                s.show()
                return
        
        for idx, rec in enumerate(s.filtered_data):
            item_name = rec['result_item']
            words = re.split(r'(?=[A-Z])|_|-|\s', item_name)
            for word in words:
                if word.upper().startswith(char):
                    s.tree.selection_set(str(idx))
                    s.tree.see(str(idx))
                    s.show()
                    return

    def show_hidden_items(s):
        if not s._hidden_items:
            messagebox.showinfo("No Hidden Items", "There are no hidden items.")
            return
        
        dialog = tk.Toplevel(s.r)
        dialog.title("Hidden Items")
        dialog.geometry("400x500")
        
        tk.Label(dialog, text="Click an item to unhide it:", font=s.ui_font_bold).pack(pady=10)
        
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=(s.ui_font[0], 12))
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        hidden_list = sorted(s._hidden_items)
        for item in hidden_list:
            listbox.insert(tk.END, item)
        
        def unhide_item(event):
            selection = listbox.curselection()
            if selection:
                item_name = hidden_list[selection[0]]
                if messagebox.askyesno("Unhide Item", f"Add '{item_name}' back to the main list?"):
                    s._hidden_items.remove(item_name)
                    s._save_hidden_items()
                    s.filter()
                    listbox.delete(selection[0])
                    hidden_list.pop(selection[0])
                    if not s._hidden_items:
                        dialog.destroy()
        
        listbox.bind('<Double-Button-1>', unhide_item)
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="Close", command=dialog.destroy).pack()

    def _save_hidden_items(s):
        with open(s.hidden_items_file, 'w', encoding='utf-8') as f:
            json.dump(list(s._hidden_items), f, indent=2)
    
    def _save_dev_items(s):
        with open(s.dev_items_file, 'w', encoding='utf-8') as f:
            json.dump(list(s._dev_items), f, indent=2)

    def show(s, *_):
        sel = s.tree.selection()
        if not sel: return
        idx = int(sel[0]); rec = s.filtered_data[idx]; name = rec['result_item']
        s.selected_item = name
        
        if rec.get('has_multiple_recipes'):
            s.current_item_recipes = rec['recipe_variants']
            s.current_recipe_index = 0
        else:
            s.current_item_recipes = [rec]
            s.current_recipe_index = 0
        
        s._update_recipe_display()
        s._save_current()
        
        s.dev_item_var.set(name in s._dev_items)
        
        orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), 0)
        
        if name in s._dev_items:
            script_dir = Path(__file__).parent
            missing_icon_path = script_dir / 'AppIcons' / 'MissingIcon.png'
            if missing_icon_path.exists() and Image:
                try:
                    im = Image.open(missing_icon_path).resize((128,128), Image.LANCZOS)
                    ph = ImageTk.PhotoImage(im); s.ic.config(image=ph); s.ic.image = ph
                except:
                    s.ic.config(image=s._placeholder_red_large())
            else:
                s.ic.config(image=s._placeholder_red_large())
        else:
            icon_path = s.icons.get(name)
            if icon_path and Path(icon_path).exists() and Image:
                try:
                    im = Image.open(icon_path).resize((128,128), Image.LANCZOS)
                    ph = ImageTk.PhotoImage(im); s.ic.config(image=ph); s.ic.image = ph
                except: 
                    s.ic.config(image=s._placeholder_red_large())
            else:
                s.ic.config(image=s._placeholder_red_large())
        
        s._load_current_notes(name)

    def prev_recipe(s):
        if not s.current_item_recipes or len(s.current_item_recipes) <= 1:
            return
        
        s.current_recipe_index = (s.current_recipe_index - 1) % len(s.current_item_recipes)
        s._update_recipe_display()
    
    def next_recipe(s):
        if not s.current_item_recipes or len(s.current_item_recipes) <= 1:
            return
        
        s.current_recipe_index = (s.current_recipe_index + 1) % len(s.current_item_recipes)
        s._update_recipe_display()
    
    def _update_recipe_display(s):
        if not s.selected_item or not s.current_item_recipes:
            return
        
        total_recipes = len(s.current_item_recipes)
        current_num = s.current_recipe_index + 1
        
        if total_recipes > 1:
            s.recipe_info_label.config(text=f"Recipe {current_num} of {total_recipes}")
        else:
            s.recipe_info_label.config(text="")
        
        s.prev_recipe_btn.config(state="normal" if total_recipes > 1 else "disabled")
        s.next_recipe_btn.config(state="normal" if total_recipes > 1 else "disabled")
        
        current_recipe = s.current_item_recipes[s.current_recipe_index]
        
        s._build_separated_display(current_recipe)

    def _build_separated_display(s, rec):
        # Safely define script directory path for icon loading
        try:
            script_dir = Path(__file__).parent
        except:
            script_dir = Path.cwd()  # Fallback to current directory
        
        item_name = rec['result_item']
        custom_data = s._custom_edits.get(item_name, {})
        
        base_item_data = None
        for item in s.data:
            if item['result_item'] == item_name:
                base_item_data = item
                break
        
        if base_item_data:
            display_rec = base_item_data.copy()
            display_rec.update(rec)
            for key in ['description', 'weight', 'nutrition', 'housing_info', 'room_requirements']:
                if key in base_item_data:
                    display_rec[key] = base_item_data[key]
        else:
            display_rec = rec.copy()
        
        if custom_data:
            display_rec.update(custom_data)
        
        # UPDATE ROOM TIER ALERT FIRST - This is the key enhancement!
        # Check if this item has room tier requirements and update the prominent display
        room_reqs = display_rec.get("room_requirements", {})
        if room_reqs and 'required_tier' in room_reqs:
            tier = room_reqs['required_tier']
            # Format as prominent alert with all caps and bold formatting
            s.room_tier_label.config(text=f"ROOM TIER {tier}")
            s.room_tier_alert_frame.pack(fill="x", pady=(0, 10))  # Pack with some spacing
        else:
            # Hide the room tier alert if not needed
            s.room_tier_alert_frame.pack_forget()
        
        s.desc_txt.config(state='normal')  # Always set to normal for editing content
        s.desc_txt.delete('1.0', 'end')
        
        s.desc_txt.insert('end', display_rec['result_item'], 'item_name')
        if display_rec['result_item'] in s._dev_items:
            s.desc_txt.insert('end', ' [DEV ITEM]', 'dev_marker')
        s.desc_txt.insert('end', '\n\n')

        if desc := display_rec.get("description"):
            s.desc_txt.insert('end', desc, 'description')
            s.desc_txt.insert('end', '\n\n')

        has_physical_info = False

        if weight := display_rec.get("weight"):
            s.desc_txt.insert('end', f'Weight: {weight} kg\n', 'weight_info')
            has_physical_info = True

        if housing_info := display_rec.get("housing_info"):
            if 'base_value' in housing_info:
                value = housing_info['base_value']
                s.desc_txt.insert('end', f'Furnishing Value: {value}\n', 'furnishing_value')
                has_physical_info = True
    
            if 'room_category' in housing_info:
                s.desc_txt.insert('end', f'Room Category: {housing_info["room_category"]}\n', 'room_category')
                has_physical_info = True
    
            if 'furniture_type' in housing_info:
                s.desc_txt.insert('end', f'Furniture Type: {housing_info["furniture_type"]}\n', 'furniture_type')
                has_physical_info = True
    
            if 'diminishing_return' in housing_info:
                percentage = housing_info['diminishing_return']
                s.desc_txt.insert('end', f'Repeats in room yield {percentage}% less value each\n', 'diminishing_return')
                has_physical_info = True

        # REDUCED ROOM REQUIREMENTS IN DESCRIPTION - Since they're now prominent at top
        if room_reqs := display_rec.get("room_requirements"):
            if room_reqs.get('requires_containment'):
                s.desc_txt.insert('end', 'Required to be in a room\n', 'room_requirement')
                has_physical_info = True
    
            if 'required_volume' in room_reqs:
                volume = room_reqs['required_volume']
                s.desc_txt.insert('end', f'Requires {volume} square meters of room to use\n', 'room_requirement')
                has_physical_info = True
    
            # Room tier is now prominently displayed at top, so de-emphasize here
            if 'required_tier' in room_reqs:
                tier = room_reqs['required_tier']
                # Much smaller, less prominent mention since it's shown prominently at top
                s.desc_txt.insert('end', f'(Room tier {tier} shown above)\n', 'room_requirement')
                has_physical_info = True

        if nutrition := display_rec.get("nutrition"):
            s.desc_txt.insert('end', '\n')
            s.desc_txt.insert('end', 'Nutrition Information:\n', 'nutrition_header')
            s.desc_txt.insert('end', '\n')
            
            nutrient_order = [
                ('carbs', 'Carbohydrates'),
                ('protein', 'Protein'),
                ('fat', 'Fat'),
                ('vitamins', 'Vitamins')
            ]
            
            has_nutrients = False
            total_nutrients = 0
            for nutrient_key, display_name in nutrient_order:
                if nutrient_key in nutrition:
                    has_nutrients = True
                    value = nutrition[nutrient_key]
                    total_nutrients += value
                    s.desc_txt.insert('end', '  ')
                    s.desc_txt.insert('end', f' {display_name}: {value} ', f'nutrient_{nutrient_key}')
                    s.desc_txt.insert('end', '\n')
            
            if has_nutrients:
                s.desc_txt.insert('end', '\n')
                s.desc_txt.insert('end', '  ')
                
                if 'calories' in nutrition and nutrition['calories'] > 0:
                    s.desc_txt.insert('end', f' Calories: {nutrition["calories"]} ', 'calorie_count_display')
                else:
                    calc_calories = (nutrition.get('carbs', 0) * 4 + 
                                   nutrition.get('protein', 0) * 4 + 
                                   nutrition.get('fat', 0) * 9)
                    
                    if calc_calories == 0 and total_nutrients > 0:
                        calc_calories = total_nutrients * 4
                    
                    s.desc_txt.insert('end', f' Calories: {calc_calories} ', 'calorie_count_display')
                
                s.desc_txt.insert('end', '\n')

        if has_physical_info:
            s.desc_txt.insert('end', '\n')
        
        # Set text widget state based on current edit mode
        s.desc_txt.config(state='disabled')  # Description is always read-only now

        s.recipe_txt.config(state='normal')
        s.recipe_txt.delete('1.0', 'end')
        
        s.used_in_txt.config(state='normal')
        s.used_in_txt.delete('1.0', 'end')
        
        # Create main container for two-column layout
        main_recipe_frame = tk.Frame(s.recipe_txt, bg='white')
        s.recipe_txt.window_create('end', window=main_recipe_frame)
        
        # Left column for skills and crafting tables
        left_column = tk.Frame(main_recipe_frame, bg='white')
        left_column.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Right column for ingredients
        right_column = tk.Frame(main_recipe_frame, bg='white')
        right_column.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # === LEFT COLUMN: Skills and Crafting Tables ===
        
        # Section header for left column
        left_header = tk.Label(left_column, text="Crafting Requirements", 
                              font=(s.main_text_font[0], 12, 'bold'), bg='white', anchor='w')
        left_header.pack(fill='x', pady=(0, 5))
        
        # Skill information
        if display_rec.get("skill"):
            skill_frame = tk.Frame(left_column, bg='white')
            skill_frame.pack(fill='x', pady=2)
            
            skill_label = tk.Label(skill_frame, text="Skill: ", font=s.main_text_font, bg='white')
            skill_label.pack(side='left')
            
            # Create a sub-frame for skill icon and text
            skill_content_frame = tk.Frame(skill_frame, bg='white')
            skill_content_frame.pack(side='left', fill='x', expand=True)
            
            # Insert skill icon
            skill_name = display_rec['skill']
            script_dir = Path(__file__).parent
            skill_icon_path = script_dir / 'SkillIcons' / f"{skill_name}.png"
            if skill_icon_path.exists() and Image:
                try:
                    skill_img = Image.open(skill_icon_path).resize((24, 24), Image.LANCZOS)
                    skill_photo = ImageTk.PhotoImage(skill_img)
                    if not hasattr(s, '_recipe_skill_icons'):
                        s._recipe_skill_icons = {}
                    s._recipe_skill_icons[skill_name] = skill_photo
                    
                    skill_icon_label = tk.Label(skill_content_frame, image=skill_photo, bg='white')
                    skill_icon_label.pack(side='left', padx=(0, 5))
                except:
                    skill_icon_label = tk.Label(skill_content_frame, text='🔵', bg='white')
                    skill_icon_label.pack(side='left', padx=(0, 5))
            else:
                skill_icon_label = tk.Label(skill_content_frame, text='🔵', bg='white')
                skill_icon_label.pack(side='left', padx=(0, 5))
            
            skill_text_label = tk.Label(skill_content_frame, 
                                        text=f"{skill_name} (Lv {display_rec['level']})",
                                       font=s.main_text_font, bg='white', anchor='w')
            skill_text_label.pack(side='left', fill='x', expand=True)
        
        # Crafting table information
        if table := display_rec.get("crafting_table"):
            table_frame = tk.Frame(left_column, bg='white')
            table_frame.pack(fill='x', pady=2)
            
            table_label = tk.Label(table_frame, text="Table: ", font=s.main_text_font, bg='white')
            table_label.pack(side='left')
            
            # Create a sub-frame for table icon and text
            table_content_frame = tk.Frame(table_frame, bg='white', cursor='hand2')
            table_content_frame.pack(side='left', fill='x', expand=True)
            
            # Insert table icon - Try multiple naming conventions
            possible_table_names = [
                table,  # Try exact name first
                spaced_to_camel_case(table),  # Try CamelCase
                table.replace(" ", ""),  # Try without spaces
                table.replace(" ", "_"),  # Try with underscores
            ]

            table_icon_found = False
            for table_icon_name in possible_table_names:
                table_icon_path = script_dir / 'EcoIcons' / f"{table_icon_name}.png"
                if table_icon_path.exists() and Image:
                    try:
                        table_img = Image.open(table_icon_path).resize((24, 24), Image.LANCZOS)
                        table_photo = ImageTk.PhotoImage(table_img)
                        if not hasattr(s, '_recipe_table_icons'):
                            s._recipe_table_icons = {}
                        s._recipe_table_icons[table] = table_photo
        
                        table_icon_label = tk.Label(table_content_frame, image=table_photo, bg='white', cursor='hand2')
                        table_icon_label.pack(side='left', padx=(0, 5))
                        table_icon_found = True
                        break  # IMPORTANT: Break after finding an icon
                    except:
                        continue  # Try next naming convention
    
            # If no icon was found, create a placeholder
            if not table_icon_found:
                table_icon_label = tk.Label(table_content_frame, text='🔴', bg='white', cursor='hand2')
                table_icon_label.pack(side='left', padx=(0, 5))

            # Create the table text label ONLY ONCE, outside the loop
            table_text_label = tk.Label(table_content_frame, text=table,
                       font=s.main_text_font, bg='white', cursor='hand2', anchor='w')
            table_text_label.pack(side='left', fill='x', expand=True)
            
            # Bind click events for table navigation
            def make_table_click_handler(table_name):
                return lambda e: s._handle_ingredient_click(table_name)
            
            table_click_handler = make_table_click_handler(table)
            for widget in [table_content_frame, table_icon_label, table_text_label]:
                widget.bind('<Button-1>', table_click_handler)
        
        # Building materials note (if applicable)
        building_materials = [
            'adobe', 'brick', 'lumber', 'stone', 'mortared stone', 'mortared sandstone',
            'mortared granite', 'mortared limestone', 'ashlar', 'glass steel',
            'corrugated steel', 'reinforced concrete', 'composite', 'nylon',
            'framed', 'hewn', 'log', 'bamboo'
        ]
        item_lower = display_rec['result_item'].lower()
        if any(material in item_lower for material in building_materials):
            building_note = tk.Label(left_column, 
                                   text="[When carried, use hammer to construct, or right-click to stack.]",
                                   font=(s.main_text_font[0], 9, 'italic'), 
                                   fg='#006400', bg='white', wraplength=200, justify='left')
            building_note.pack(fill='x', pady=(10, 0))
        
        # === RIGHT COLUMN: Ingredients ===
        
        # Section header for right column
        right_header = tk.Label(right_column, text="Ingredients", 
                               font=(s.main_text_font[0], 12, 'bold'), bg='white', anchor='w')
        right_header.pack(fill='x', pady=(0, 5))
        
        if display_rec.get("ingredients"):
            ingredients = display_rec["ingredients"]
            
            # Calculate how many items per column (3 columns for ingredients)
            total_ingredients = len(ingredients)
            items_per_column = (total_ingredients + 2) // 3  # 3 columns
            
            # Create a frame for the multi-column layout
            ingredients_frame = tk.Frame(right_column, bg='white')
            ingredients_frame.pack(fill='both', expand=True)
            
            # Left column frame
            ing_left_column = tk.Frame(ingredients_frame, bg='white')
            ing_left_column.pack(side='left', fill='both', expand=True, padx=(0, 5))
            
            # Middle column frame 
            ing_middle_column = tk.Frame(ingredients_frame, bg='white')
            ing_middle_column.pack(side='left', fill='both', expand=True, padx=(5, 5))
            
            # Right column frame 
            ing_right_column = tk.Frame(ingredients_frame, bg='white')
            ing_right_column.pack(side='right', fill='both', expand=True, padx=(5, 0))
            
            # Add ingredients to columns
            for i, (ingredient, quantity) in enumerate(ingredients):
                # Determine which column this ingredient goes in
                if i < items_per_column:
                    parent_frame = ing_left_column
                elif i < items_per_column * 2:
                    parent_frame = ing_middle_column
                else:
                    parent_frame = ing_right_column
                
                ingredient_frame = tk.Frame(parent_frame, bg='white', cursor='hand2')
                ingredient_frame.pack(fill='x', pady=1, padx=2)
                
                # Try to load icon for the ingredient - Try multiple naming conventions
                icon_label = None
                icon_dirs = ['EcoIngredients', 'EcoIcons', 'TagIcons']
                
                possible_ingredient_names = [
                    ingredient,  # Try exact name first
                    spaced_to_camel_case(ingredient),  # Try CamelCase
                    ingredient.replace(" ", ""),  # Try without spaces
                    ingredient.replace(" ", "_"),  # Try with underscores
                ]
                
                icon_found = False
                for icon_dir in icon_dirs:
                    for ingredient_icon_name in possible_ingredient_names:
                        icon_path = script_dir / icon_dir / f"{ingredient_icon_name}.png"
                        if icon_path.exists() and Image:
                            try:
                                ingredient_img = Image.open(icon_path).resize((24, 24), Image.LANCZOS)
                                ingredient_photo = ImageTk.PhotoImage(ingredient_img)
                                
                                # Store reference to prevent garbage collection
                                if not hasattr(s, '_recipe_ingredient_icons'):
                                    s._recipe_ingredient_icons = {}
                                s._recipe_ingredient_icons[f'{ingredient}_{i}'] = ingredient_photo
                                
                                icon_label = tk.Label(ingredient_frame, image=ingredient_photo, bg='white', cursor='hand2')
                                icon_label.pack(side='left', padx=(0, 5))
                                icon_found = True
                                break
                            except Exception as e:
                                log(f"Error loading icon for {ingredient}: {e}")
                                continue
                    if icon_found:
                        break
                
                # If no icon found, create a colored placeholder
                if not icon_found:
                    icon_label = tk.Label(ingredient_frame, text='🔹', bg='white', cursor='hand2', font=('Arial', 12))
                    icon_label.pack(side='left', padx=(0, 5))
                
                # If no icon found, create a colored placeholder
                if icon_label is None:
                    icon_label = tk.Label(ingredient_frame, text='🔹', bg='white', cursor='hand2', font=('Arial', 12))
                    icon_label.pack(side='left', padx=(0, 5))
                
                # Create text label - ingredient is already spaced
                text_label = tk.Label(ingredient_frame, text=f"{ingredient} ×{quantity}", bg='white', fg='blue', 
                                     font=s.main_text_font, cursor='hand2', anchor='w')
                text_label.pack(side='left', fill='x', expand=True)
                
                # Bind click events to both icon and text
                def make_click_handler(item_name):
                    return lambda e: s._handle_ingredient_click(item_name)
                
                def make_enter_handler(item_name):
                    return lambda e: s._on_ingredient_enter(e, item_name)
                
                def make_leave_handler():
                    return lambda e: s._on_ingredient_leave(e)
                
                click_handler = make_click_handler(ingredient)
                enter_handler = make_enter_handler(ingredient)
                leave_handler = make_leave_handler()
                
                for widget in [ingredient_frame, icon_label, text_label]:
                    widget.bind('<Button-1>', click_handler)
                    widget.bind('<Enter>', enter_handler)
                    widget.bind('<Leave>', leave_handler)
        
        else:
            # Handle items without ingredients (harvested/mined items)
            if harvested_from := display_rec.get("harvested_from"):
                species_header = tk.Label(right_column, text="Harvested from Species:", 
                                        font=(s.main_text_font[0], 11, 'bold'), bg='white', anchor='w')
                species_header.pack(fill='x', pady=(0, 5))
                
                for species in harvested_from:
                    species_frame = tk.Frame(right_column, bg='white', cursor='hand2')
                    species_frame.pack(fill='x', pady=1)
                    
                    species_icon = tk.Label(species_frame, text='🌿', bg='white', cursor='hand2')
                    species_icon.pack(side='left', padx=(0, 5))
                    
                    species_exists = any(rec['result_item'] == species for rec in s.data)
                    if species_exists:
                        species_label = tk.Label(species_frame, text=species, bg='white', fg='blue',
                                               font=s.main_text_font, cursor='hand2', anchor='w')
                        species_label.pack(side='left', fill='x', expand=True)
                        
                        def make_species_click_handler(species_name):
                            return lambda e: s._navigate_to_item(species_name)
                        
                        species_click_handler = make_species_click_handler(species)
                        for widget in [species_frame, species_icon, species_label]:
                            widget.bind('<Button-1>', species_click_handler)
                    else:
                        species_label = tk.Label(species_frame, text=species, bg='white',
                                               font=s.main_text_font, anchor='w')
                        species_label.pack(side='left', fill='x', expand=True)
            else:
                # Handle different types of uncraftable items
                item_name_lower = display_rec['result_item'].lower()
                
                if 'carcass' in item_name_lower or any(animal in item_name_lower for animal in [
                    'fish', 'salmon', 'trout', 'bass', 'tuna', 'crab', 'urchin', 
                    'clam', 'otter', 'fox', 'hare', 'deer', 'elk', 'bison', 
                    'wolf', 'bear', 'turkey', 'tortoise', 'sheep', 'goat',
                    'prairie', 'mountain', 'bighorn', 'alligator', 'jaguar', 'agouti'
                ]):
                    note_text = "This animal can only be hunted or fished."
                
                elif any(wood in item_name_lower for wood in ['log', 'logs']):
                    note_text = "Can only be collected by felling trees."
                
                elif any(ore in item_name_lower for ore in [
                    'ore', 'coal', 'stone', 'granite', 'limestone', 'sandstone', 
                    'gneiss', 'basalt', 'shale', 'clay', 'sand', 'dirt', 'crushed'
                ]) and 'ashlar' not in item_name_lower and 'mortared' not in item_name_lower:
                    note_text = "Can only be collected by mining."
                
                elif any(plant in item_name_lower for plant in [
                    'seed', 'seeds', 'bulb', 'spores', 'bean', 'beans', 'beet', 
                    'corn', 'wheat', 'rice', 'tomato', 'pumpkin', 'cotton', 
                    'flax', 'sunflower', 'pineapple', 'papaya', 'taro', 'agave',
                    'berry', 'berries', 'huckle', 'mushroom', 'fern', 'moss',
                    'kelp', 'camas', 'fireweed', 'lupine', 'saxifrage'
                ]):
                    if 'seed' in item_name_lower or 'bulb' in item_name_lower or 'spores' in item_name_lower:
                        note_text = "Can be found by gathering or purchased from farmers."
                    else:
                        note_text = "Can only be collected by gathering or farming."
                
                elif any(material in item_name_lower for material in [
                    'pulp', 'fiber', 'plant', 'palm', 'spruce', 'cactus', 'leaf', 'leaves'
                ]):
                    note_text = "Can only be collected from plants in the wild."
                
                elif 'sulfur' in item_name_lower:
                    note_text = "Can be found in certain biomes, often near volcanic areas."
                
                else:
                    note_text = "This item cannot be crafted."
                
                note_label = tk.Label(right_column, text=note_text, 
                                    font=(s.main_text_font[0], 10, 'italic'), 
                                    fg='#666666', bg='white', wraplength=250, justify='left')
                note_label.pack(fill='x', pady=5)
        
        # Add recipe source info at the bottom if multiple recipes exist
        if len(s.current_item_recipes) > 1:
            source_file = display_rec.get('source_file', 'Unknown')
            s.recipe_txt.insert('end', f'\n\nRecipe from: {source_file}', 'recipe_source')
            s.recipe_txt.tag_config('recipe_source', font=(s.main_text_font[0], 9, 'italic'), foreground='#666666')
        
        s.recipe_txt.config(state='disabled')
        
        # Now handle "Used In" section in separate widget
        if used_in := display_rec.get("used_in"):
            # Calculate how many items per column (3 columns instead of 2)
            total_items = len(used_in)
            items_per_column = (total_items + 2) // 3  # Changed from 2 to 3 columns
            
            # Create a frame for the three-column layout
            used_in_frame = tk.Frame(s.used_in_txt, bg='white')
            s.used_in_txt.window_create('end', window=used_in_frame)
            
            # Left column frame
            left_column = tk.Frame(used_in_frame, bg='white')
            left_column.pack(side='left', fill='both', expand=True, padx=(0, 5))
            
            # Middle column frame 
            middle_column = tk.Frame(used_in_frame, bg='white')
            middle_column.pack(side='left', fill='both', expand=True, padx=(5, 5))
            
            # Right column frame 
            right_column = tk.Frame(used_in_frame, bg='white')
            right_column.pack(side='right', fill='both', expand=True, padx=(5, 0))
            
            for i, recipe_name in enumerate(used_in):
                # Determine which column this item goes in
                if i < items_per_column:
                    parent_frame = left_column
                elif i < items_per_column * 2:
                    parent_frame = middle_column
                else:
                    parent_frame = right_column
                
                # Create a frame for this item (icon + text)
                item_frame = tk.Frame(parent_frame, bg='white', cursor='hand2')
                item_frame.pack(fill='x', pady=1, padx=2)
                
                # Try to load icon for the recipe item - Try multiple naming conventions
                icon_label = None
                icon_dirs = ['EcoIcons', 'EcoIngredients', 'TagIcons']
                
                possible_recipe_names = [
                    recipe_name,  # Try exact name first
                    spaced_to_camel_case(recipe_name),  # Try CamelCase
                    recipe_name.replace(" ", ""),  # Try without spaces
                    recipe_name.replace(" ", "_"),  # Try with underscores
                ]
                
                icon_found = False
                for icon_dir in icon_dirs:
                    for recipe_icon_name in possible_recipe_names:
                        icon_path = script_dir / icon_dir / f"{recipe_icon_name}.png"
                        if icon_path.exists() and Image:
                            try:
                                item_img = Image.open(icon_path).resize((24, 24), Image.LANCZOS)
                                item_photo = ImageTk.PhotoImage(item_img)
                                
                                # Store reference to prevent garbage collection
                                if not hasattr(s, '_used_in_icons'):
                                    s._used_in_icons = {}
                                s._used_in_icons[f'{recipe_name}_{i}'] = item_photo
                                
                                icon_label = tk.Label(item_frame, image=item_photo, bg='white', cursor='hand2')
                                icon_label.pack(side='left', padx=(0, 5))
                                icon_found = True
                                break
                            except Exception as e:
                                log(f"Error loading icon for {recipe_name}: {e}")
                                continue
                    if icon_found:
                        break
                
                # If no icon found, create a colored placeholder
                if not icon_found:
                    icon_label = tk.Label(item_frame, text='🔹', bg='white', cursor='hand2', font=('Arial', 12))
                    icon_label.pack(side='left', padx=(0, 5))
                
                # If no icon found, create a colored placeholder
                if icon_label is None:
                    icon_label = tk.Label(item_frame, text='🔹', bg='white', cursor='hand2', font=('Arial', 12))
                    icon_label.pack(side='left', padx=(0, 5))
                
                # Create text label - recipe_name is already spaced
                text_label = tk.Label(item_frame, text=recipe_name, bg='white', fg='blue', 
                                     font=s.main_text_font, cursor='hand2', anchor='w')
                text_label.pack(side='left', fill='x', expand=True)
                
                # Bind click events to both icon and text
                def make_click_handler(item_name):
                    return lambda e: s._navigate_to_item(item_name)
                
                def make_enter_handler(item_name):
                    return lambda e: s._on_used_in_enter(e, item_name)
                
                def make_leave_handler():
                    return lambda e: s._on_used_in_leave(e)
                
                click_handler = make_click_handler(recipe_name)
                enter_handler = make_enter_handler(recipe_name)
                leave_handler = make_leave_handler()
                
                for widget in [item_frame, icon_label, text_label]:
                    widget.bind('<Button-1>', click_handler)
                    widget.bind('<Enter>', enter_handler)
                    widget.bind('<Leave>', leave_handler)
        else:
            s.used_in_txt.insert('end', 'This item is not used in any recipes.')
        
        s.used_in_txt.config(state='disabled')
        
        s._update_tags_display(s.selected_item)
    
    def _on_ingredient_enter(s, event, item_name):
        """Handle mouse enter for ingredient items"""
        widget = event.widget
        if hasattr(widget, 'master'):
            widget.master.config(bg='#e6f3ff')  # Light blue background
        widget.config(bg='#e6f3ff')
        
        # Clean up any existing tooltips first
        s._cleanup_tooltips()
        
        # Create tooltip
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
        label = tk.Label(tooltip, text=f"Click to navigate to {item_name}", background="#ffffe0", 
                       relief="solid", borderwidth=1, font=("Arial", 9))
        label.pack()
        
        s.current_ingredient_tooltip = tooltip
    
    def _on_ingredient_leave(s, event):
        """Handle mouse leave for ingredient items"""
        widget = event.widget
        if hasattr(widget, 'master'):
            widget.master.config(bg='white')  # Reset background
        widget.config(bg='white')
        
        # Cleanup tooltip
        s._cleanup_ingredient_tooltip()
    
    def _cleanup_ingredient_tooltip(s):
        """Clean up ingredient tooltip"""
        if hasattr(s, 'current_ingredient_tooltip'):
            s.current_ingredient_tooltip.destroy()
            del s.current_ingredient_tooltip
    
    def _on_used_in_enter(s, event, item_name):
        """Handle mouse enter for used-in items"""
        widget = event.widget
        if hasattr(widget, 'master'):
            widget.master.config(bg='#e6f3ff')  # Light blue background
        widget.config(bg='#e6f3ff')
        
        # Clean up any existing tooltips first
        s._cleanup_tooltips()
        
        # Create tooltip
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
        label = tk.Label(tooltip, text=f"Click to navigate to {item_name}", background="#ffffe0", 
                       relief="solid", borderwidth=1, font=("Arial", 9))
        label.pack()
        
        s.current_used_in_tooltip = tooltip
    
    def _on_used_in_leave(s, event):
        """Handle mouse leave for used-in items"""
        widget = event.widget
        if hasattr(widget, 'master'):
            widget.master.config(bg='white')  # Reset background
        widget.config(bg='white')
        
        # Cleanup tooltip
        s._cleanup_used_in_tooltip()
    
    def _cleanup_tooltips(s):
        """Clean up all active tooltips"""
        if hasattr(s, 'current_tooltip'):
            s.current_tooltip.destroy()
            del s.current_tooltip
        if hasattr(s, 'current_used_in_tooltip'):
            s.current_used_in_tooltip.destroy()
            del s.current_used_in_tooltip
        if hasattr(s, 'current_ingredient_tooltip'):
            s.current_ingredient_tooltip.destroy()
            del s.current_ingredient_tooltip
    
    def _cleanup_used_in_tooltip(s):
        """Clean up used-in tooltip"""
        if hasattr(s, 'current_used_in_tooltip'):
            s.current_used_in_tooltip.destroy()
            del s.current_used_in_tooltip

    def _navigate_to_item(s, item_name):
        """Navigate to an item - FIXED VERSION"""
        if hasattr(s, 'current_tooltip'):
            s.current_tooltip.destroy()
            del s.current_tooltip
        
        # Clear search and filters before navigating
        s.q.set("")  # Clear search box
        s.clear_tag_filter()  # Clear any tag filters
        s.filter()  # Re-filter to show all items
        
        # Search in the full data set (s.data), not filtered_data
        found = False
        for idx, rec in enumerate(s.data):
            if rec['result_item'].lower() == item_name.lower():
                # Found the item - now find it in filtered_data
                for filtered_idx, filtered_rec in enumerate(s.filtered_data):
                    if filtered_rec['result_item'] == rec['result_item']:
                        s.tree.selection_set(str(filtered_idx))
                        s.tree.see(str(filtered_idx))
                        s.show()
                        found = True
                        break
                break
        
        if not found:
            log(f"Item not found: '{item_name}'")
            messagebox.showinfo("Item Not Found", f"'{item_name}' was not found in the current data.")
    
    def _handle_ingredient_click(s, ingredient_name):
        """Handle clicking on an ingredient - FIXED VERSION"""
        is_tag = False
        script_dir = Path(__file__).parent
        
        # Check if it's a tag icon - convert to CamelCase for file lookup
        tag_icon_name = spaced_to_camel_case(ingredient_name)
        tag_icon_path = script_dir / 'TagIcons' / f"{tag_icon_name}.png"
        if tag_icon_path.exists():
            is_tag = True
        
        if not is_tag:
            all_tags = set()
            for tags_list in s._tags.values():
                all_tags.update(tags_list)
            if ingredient_name in all_tags:
                is_tag = True
        
        if is_tag:
            s.filter_tag = ingredient_name
            s.current_filter_label.config(text=f"Tag: {ingredient_name}")
            s.tags_filter_btn.config(text="Clear Tags", bg="lightcoral")
            
            s.q.set("")
            
            if ingredient_name.lower() == 'food':
                s.nutrition_sort_frame.pack(side="left", padx=(10, 0))
            else:
                s.nutrition_sort_frame.pack_forget()
                s.sort_var.set("Name (A-Z)")
            
            s.filter()
            
            s.st.config(text=f"Filtered by tag: {ingredient_name}")
        else:
            s._navigate_to_item(ingredient_name)

    def _save_current(s):
        if not s.selected_item: return
        s._notes[s.selected_item] = s.notes.get('1.0','end-1c')
        with open(s.notes_file,'w',encoding='utf-8') as f: 
            json.dump(s._notes,f,indent=2)
        with open(s.tags_file,'w',encoding='utf-8') as f: 
            json.dump(s._tags,f,indent=2)

    def _load_current_notes(s, item):
        s.notes.delete('1.0','end')
        s.notes.insert('1.0', s._notes.get(item,''))
        s.r.after(1, lambda: s._update_tags_display(item))
        
        all_tags = sorted({t for lst in s._tags.values() for t in lst})
        s.all_tags_listbox.delete(0, tk.END)
        for tag in all_tags:
            s.all_tags_listbox.insert(tk.END, tag)

    def _update_filter_label_with_icon(s, tag_name):
        """Update the filter label to show an icon instead of text"""
        # Clear any existing widgets in the label
        for widget in s.current_filter_label.winfo_children():
            widget.destroy()
    
        # Try to load the tag icon - FIX: Convert to CamelCase for icon lookup
        script_dir = Path(__file__).parent
        tag_icon_name = spaced_to_camel_case(tag_name)
        tag_icon_path = script_dir / 'TagIcons' / f"{tag_icon_name}.png"
    
        if tag_icon_path.exists() and Image:
            try:
                tag_img = Image.open(tag_icon_path).resize((24, 24), Image.LANCZOS)
                tag_photo = ImageTk.PhotoImage(tag_img)
            
                # Store reference to prevent garbage collection
                s.current_filter_photo = tag_photo
            
                # Create icon label
                icon_label = tk.Label(s.current_filter_label, image=tag_photo, cursor='hand2')
                icon_label.pack(side='left')
            
                # Add tooltip on hover
                def on_enter(event):
                    # Create tooltip
                    s.filter_tooltip = tk.Toplevel()
                    s.filter_tooltip.wm_overrideredirect(True)
                    s.filter_tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                
                    tooltip_label = tk.Label(s.filter_tooltip, text=f"Filter: {tag_name}", 
                                        background="#ffffe0", relief="solid", borderwidth=1, 
                                        font=("Arial", 9))
                    tooltip_label.pack()
            
                def on_leave(event):
                    if hasattr(s, 'filter_tooltip'):
                        s.filter_tooltip.destroy()
                        del s.filter_tooltip
            
                icon_label.bind('<Enter>', on_enter)
                icon_label.bind('<Leave>', on_leave)
            
                # Make it clickable to clear filter
                icon_label.bind('<Button-1>', lambda e: s.clear_tag_filter())
            
            except Exception as e:
                log(f"Error loading filter icon for {tag_name}: {e}")
                # Fallback to text
                s.current_filter_label.config(text=f"Tag: {tag_name}")
        else:
            # Fallback to text if no icon available
            s.current_filter_label.config(text=f"Tag: {tag_name}")
        
    def _handle_tag_display_click(s, tag_name):
        """Handle clicking on a tag in the tags display to filter by that tag"""
        # Apply the tag filter
        s.filter_tag = tag_name
        s._update_filter_label_with_icon(tag_name)
        s.tags_filter_btn.config(text="Clear Tags", bg="lightcoral")
        
        # Clear search box
        s.q.set("")
        
        # Show nutrition sort options if it's a food tag
        if tag_name.lower() == 'food':
            s.nutrition_sort_frame.pack(side="left", padx=(10, 0))
        else:
            s.nutrition_sort_frame.pack_forget()
            s.sort_var.set("Name (A-Z)")
        
        # Apply the filter
        s.filter()
        
        # Update status
        s.st.config(text=f"Filtered by tag: {tag_name}")

    def _update_tags_display(s, item):
        log(f"DEBUG: _update_tags_display called for item: {item}")
        log(f"DEBUG: s.selected_item is: {s.selected_item}")
        log(f"DEBUG: Tags for {item}: {s._tags.get(item, [])}")

        for widget in s.tags_display_frame.winfo_children():
            widget.destroy()

        tags = s._tags.get(item, [])
        log(f"DEBUG: About to create {len(tags)} tag widgets")

        if not hasattr(s, '_tag_image_refs'):
            s._tag_image_refs = {}

        script_dir = Path(__file__).parent
        tag_icons_dir = script_dir / 'TagIcons'

        # Only show X icon if admin tools are enabled
        x_icon = None
        if hasattr(s, 'tag_remove_enabled') and s.tag_remove_enabled:
            x_icon_path = script_dir / 'AppIcons' / 'X.png'
            if x_icon_path.exists() and Image:
                try:
                    x_img = Image.open(x_icon_path).resize((28, 28), Image.LANCZOS)
                    x_icon = ImageTk.PhotoImage(x_img)
                except Exception as e:
                    log(f"Failed to load X icon: {e}")

        for tag_idx, tag in enumerate(tags):
            tag_frame = tk.Frame(s.tags_display_frame)
            tag_frame.pack(fill='x', pady=1)

            # Only show X button if admin tools are enabled
            if hasattr(s, 'tag_remove_enabled') and s.tag_remove_enabled:
                if x_icon:
                    try:
                        x_btn = tk.Label(tag_frame, image=x_icon, cursor='hand2')
                        x_btn.image = x_icon
                    except:
                        x_btn = tk.Label(tag_frame, text='X', fg='red', cursor='hand2', width=2)
                else:
                    x_btn = tk.Label(tag_frame, text='X', fg='red', cursor='hand2', width=2)

                x_btn.pack(side='left', padx=(0, 2))
                x_btn.bind('<Button-1>', lambda e, tag_to_remove=tag: s._remove_tag_with_confirmation(tag_to_remove))

            # FIX: Convert tag name to CamelCase for icon lookup
            tag_icon_name = spaced_to_camel_case(tag) if ' ' in tag else tag
            tag_icon_path = tag_icons_dir / f"{tag_icon_name}.png"
            tag_label = None

            if tag_icon_path.exists() and Image:
                try:
                    tag_img = Image.open(tag_icon_path).resize((32, 32), Image.LANCZOS)
                    tag_photo = ImageTk.PhotoImage(tag_img)

                    tag_ref_key = f"{item}_{tag}_{tag_idx}"
                    s._tag_image_refs[tag_ref_key] = tag_photo

                    tag_label = tk.Label(tag_frame, image=tag_photo)
                    tag_label.image = tag_photo

                    log(f"Successfully loaded icon for tag: {tag}")
                except Exception as e:
                    log(f"Failed to load icon for tag {tag}: {e}")
                    tag_label = None

            if tag_label is None:
                log(f"Creating placeholder for tag: {tag}")
                tag_label = tk.Label(tag_frame, bg='blue', width=4, height=2, cursor='hand2')

            tag_label.pack(side='left', padx=(0, 5))
            
            # Make tag label clickable
            tag_label.config(cursor='hand2')

            try:
                tag_text_label = tk.Label(tag_frame, text=tag, font=s.ui_font, cursor='hand2', fg='blue')
                tag_text_label.pack(side='left')
                log(f"Created widget for tag: {tag}")
                
                # Add click handlers to both icon and text labels
                def make_tag_click_handler(tag_name):
                    return lambda e: s._handle_tag_display_click(tag_name)
                
                tag_click_handler = make_tag_click_handler(tag)
                tag_label.bind('<Button-1>', tag_click_handler)
                tag_text_label.bind('<Button-1>', tag_click_handler)
                
                # Add hover effects
                def on_enter(e):
                    e.widget.config(fg='darkblue' if hasattr(e.widget, 'cget') and e.widget.cget('text') else None)
                
                def on_leave(e):
                    e.widget.config(fg='blue' if hasattr(e.widget, 'cget') and e.widget.cget('text') else None)
                
                tag_text_label.bind('<Enter>', on_enter)
                tag_text_label.bind('<Leave>', on_leave)
                
            except Exception as e:
                log(f"Error creating text label for tag {tag}: {e}")

    def _on_tag_entry_change(s, event):
        if s.fill_tag_entry.get() == "Fill Tag" or not s.fill_tag_entry.get():
            s._hide_autocomplete()
            return
        
        current_text = s.fill_tag_entry.get().lower()
        
        all_tags = sorted({t for tags in s._tags.values() for t in tags})
        
        s.current_suggestions = [tag for tag in all_tags if tag.lower().startswith(current_text)]
        
        if s.current_suggestions and current_text:
            s._show_autocomplete()
            
            s.autocomplete_listbox.delete(0, tk.END)
            for tag in s.current_suggestions:
                s.autocomplete_listbox.insert(tk.END, tag)
            
            if s.autocomplete_listbox.size() > 0:
                s.autocomplete_listbox.selection_set(0)
        else:
            s._hide_autocomplete()
    
    def _show_autocomplete(s):
        if not s.autocomplete_frame.winfo_ismapped():
            s.autocomplete_frame.pack(fill="both", expand=True)
            s.autocomplete_listbox.pack(side="left", fill="both", expand=True)
            s.autocomplete_scrollbar.pack(side="right", fill="y")
    
    def _hide_autocomplete(s):
        s.autocomplete_frame.pack_forget()
    
    def _autocomplete_tag(s, event):
        if s.autocomplete_listbox.curselection() and s.current_suggestions:
            idx = s.autocomplete_listbox.curselection()[0]
            selected_tag = s.current_suggestions[idx]
            s.fill_tag_entry.delete(0, tk.END)
            s.fill_tag_entry.insert(0, selected_tag)
            s.fill_tag_entry.config(fg='black')
            s._hide_autocomplete()
            return 'break'
    
    def _next_suggestion(s, event):
        if s.autocomplete_listbox.size() > 0:
            current = s.autocomplete_listbox.curselection()
            if current:
                next_idx = (current[0] + 1) % s.autocomplete_listbox.size()
            else:
                next_idx = 0
            s.autocomplete_listbox.selection_clear(0, tk.END)
            s.autocomplete_listbox.selection_set(next_idx)
            s.autocomplete_listbox.see(next_idx)
            return 'break'
    
    def _prev_suggestion(s, event):
        if s.autocomplete_listbox.size() > 0:
            current = s.autocomplete_listbox.curselection()
            if current:
                prev_idx = (current[0] - 1) % s.autocomplete_listbox.size()
            else:
                prev_idx = s.autocomplete_listbox.size() - 1
            s.autocomplete_listbox.selection_clear(0, tk.END)
            s.autocomplete_listbox.selection_set(prev_idx)
            s.autocomplete_listbox.see(prev_idx)
            return 'break'
    
    def _on_suggestion_select(s, event):
        if s.autocomplete_listbox.curselection():
            idx = s.autocomplete_listbox.curselection()[0]
            selected_tag = s.current_suggestions[idx]
            s.fill_tag_entry.delete(0, tk.END)
            s.fill_tag_entry.insert(0, selected_tag)
            s.fill_tag_entry.config(fg='black')
            s._hide_autocomplete()
            s.fill_tag_entry.focus_set()

    def _clear_fill_tag_placeholder(s, event):
        if s.fill_tag_entry.get() == "Fill Tag":
            s.fill_tag_entry.delete(0, tk.END)
            s.fill_tag_entry.config(fg='black')

    def _restore_fill_tag_placeholder(s, event):
        if not s.fill_tag_entry.get():
            s.fill_tag_entry.insert(0, "Fill Tag")
            s.fill_tag_entry.config(fg='gray')
        s.r.after(100, s._hide_autocomplete)

    def _add_tag(s):
        if not s.selected_item:
            return
    
        fill_tag = s.fill_tag_entry.get().strip()
        
        tag = ""
        if fill_tag and fill_tag != "Fill Tag":
            tag = fill_tag
        
        if not tag:
            return
        
        if s.selected_item not in s._tags:
            s._tags[s.selected_item] = []
        
        if tag not in s._tags[s.selected_item]:
            s._tags[s.selected_item].append(tag)
            s._save_current()
            s._update_tags_display(s.selected_item)
            
            all_tags = sorted({t for tags in s._tags.values() for t in tags})
            s.all_tags_listbox.delete(0, tk.END)
            for t in all_tags:
                s.all_tags_listbox.insert(tk.END, t)
    
    def _remove_tag_with_confirmation(s, tag):
        if messagebox.askyesno("Remove Tag", f"Are you sure you want to remove the tag '{tag}'?"):
            s._remove_tag(tag)

    def _remove_tag(s, tag):
        if not s.selected_item:
            return
        
        if s.selected_item in s._tags and tag in s._tags[s.selected_item]:
            s._tags[s.selected_item].remove(tag)
            if not s._tags[s.selected_item]:
                del s._tags[s.selected_item]
            s._save_current()
            s._update_tags_display(s.selected_item)
            
            s.fill_tag_entry.delete(0, tk.END)
            
            all_existing_tags = {t for tags in s._tags.values() for t in tags}
            if tag not in all_existing_tags or s.all_tags_listbox.size() == 0:
                s.all_tags_listbox.delete(0, tk.END)
                for t in sorted(all_existing_tags):
                    s.all_tags_listbox.insert(tk.END, t)
    
    def _toggle_dev_item(s):
        if not s.selected_item:
            return
        
        if s.dev_item_var.get():
            s._dev_items.add(s.selected_item)
            log(f"Marked {s.selected_item} as DevItem")
        else:
            s._dev_items.discard(s.selected_item)
            log(f"Unmarked {s.selected_item} as DevItem")
        
        s._save_dev_items()
        
        s.show()
        
        s.filter()

    def toggle_admin_tools(s):
        """Toggle visibility of admin tools section with warning"""
        if not s.admin_tools_visible:
            # Show warning popup first
            result = messagebox.askyesno(
                "Admin Tools Warning", 
                "⚠️ WARNING ⚠️\n\n"
                "Admin Tools contain advanced functions that can:\n"
                "• Modify item images\n"
                "• Remove item tags\n"
                "• Mark items as DevItems\n"
                "• Combine/replace icons\n"
                "• Format item descriptions\n\n"
                "These changes affect your local data files.\n\n"
                "Only proceed if you understand what you're doing.\n\n"
                "Continue?",
                icon='warning'
            )
            
            if result:
                # Show admin tools by packing the container and frame
                s.admin_tools_container.pack(side='right', anchor='n', padx=(10,0), pady=(0,0))
                s.admin_tools_frame.pack(fill="both", expand=True, padx=2, pady=2)
                s.admin_tools_btn.config(text="Hide Admin Tools", bg="lightcoral")
                s.admin_tools_visible = True
                s._update_tag_remove_buttons(True)  # Enable X buttons
                # Show notes formatting controls
                if hasattr(s, 'notes_formatting_frame'):
                    s.notes_formatting_frame.pack(fill="x", pady=(0, 5), padx=4)
            else:
                return  # User cancelled, don't show admin tools
        else:
            # Hide admin tools by unpacking both frame and container
            s.admin_tools_frame.pack_forget()
            s.admin_tools_container.pack_forget()
            s.admin_tools_btn.config(text="Admin Tools", bg="lightgray")
            s.admin_tools_visible = False
            s._update_tag_remove_buttons(False)  # Disable X buttons
            # Hide notes formatting controls
            if hasattr(s, 'notes_formatting_frame'):
                s.notes_formatting_frame.pack_forget()
    
    def _update_tag_remove_buttons(s, enabled):
        """Enable/disable tag removal X buttons based on admin tools state"""
        # This will be called during tag display updates
        s.tag_remove_enabled = enabled
        # Refresh current tag display if item is selected
        if s.selected_item:
            s._update_tags_display(s.selected_item)

    def _scan_all_missing_images(s):
        """Scan EcoDump for all missing item images"""
        if not s.data:
            messagebox.showwarning("No Data", "Parse recipes first before scanning for images.")
            return
    
        # Confirm with user since this could be a long operation
        result = messagebox.askyesno(
            "Scan All Images",
            "This will scan the EcoDump folder for all items that don't have images.\n\n"
            "This may take several minutes depending on the number of items.\n\n"
            "Continue?"
        )
    
        if not result:
            return
    
        script_dir = Path(__file__).parent
        ecodump_dir = script_dir / 'EcoDump'
        ico_dir = script_dir / 'EcoIcons'
    
        if not ecodump_dir.exists():
            messagebox.showerror("Error", f"EcoDump folder not found at: {ecodump_dir}")
            return
    
        ico_dir.mkdir(exist_ok=True)
    
        # Find items without images - FIX: Convert to CamelCase for file lookup
        missing_items = []
        for rec in s.data:
            name = rec['result_item']
            icon_name = spaced_to_camel_case(name)
            icon_path = ico_dir / f"{icon_name}.png"
            if not icon_path.exists():
                missing_items.append((name, icon_name))
    
        if not missing_items:
            messagebox.showinfo("All Images Present", "All items already have images!")
            return
    
        s.st.config(text=f'Scanning for {len(missing_items)} missing images...')
        s.pb.start()
    
        # Build a cache of all PNG files in EcoDump
        png_files = {}
        try:
            for path in ecodump_dir.rglob("*.png"):
                if path.is_file():
                    filename = path.stem  # Get filename without extension
                    png_files[filename] = path
        except Exception as e:
            log(f"Error scanning EcoDump: {e}")
            s.pb.stop()
            messagebox.showerror("Error", f"Error scanning EcoDump folder: {e}")
            return
    
        # Track results
        found_count = 0
        not_found = []
        errors = []
    
        # Process each missing item
        for idx, (display_name, icon_name) in enumerate(missing_items):
            # Update progress periodically
            if idx % 10 == 0:
                progress_pct = (idx / len(missing_items)) * 100
                s.st.config(text=f'Scanning... {idx}/{len(missing_items)} ({progress_pct:.0f}%) - Found: {found_count}')
        
            if icon_name in png_files:
                # Found the image - copy it
                src_path = png_files[icon_name]
                dest_path = ico_dir / f"{icon_name}.png"
            
                try:
                    shutil.copy(src_path, dest_path)
                    s.icons[display_name] = str(dest_path)
                
                    # Update the small icon in memory
                    orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == display_name), None)
                    if orig_idx is not None and Image:
                        try:
                            im = Image.open(dest_path).resize((32, 32), Image.LANCZOS)
                            small_img = ImageTk.PhotoImage(im)
                            s.small_icons[orig_idx] = small_img
                        except Exception as e:
                            log(f"Error loading icon for {display_name}: {e}")
                
                    found_count += 1
                    log(f"✓ Found and linked image for {display_name}")
                
                except Exception as e:
                    log(f"Error copying image for {display_name}: {e}")
                    errors.append(f"{display_name}: {e}")
            else:
                not_found.append(display_name)
    
        s.pb.stop()
    
        # Refresh the tree view to show new icons
        s.filter()
    
        # Show results summary
        message = f"Scan Complete!\n\n"
        message += f"✓ Found and linked: {found_count} images\n"
    
        if not_found:
            message += f"✗ Not found: {len(not_found)} items\n"
        
            # Log the not found items
            log("\n=== Items without images in EcoDump ===")
            for item in sorted(not_found):
                log(f"  - {item}")
    
        if errors:
            message += f"⚠ Errors: {len(errors)} items\n"
            log("\n=== Errors during scan ===")
            for error in errors:
                log(f"  - {error}")
    
        s.st.config(text=f'Scan complete: {found_count} images found')
    
        # Show detailed dialog
        result_dialog = tk.Toplevel(s.r)
        result_dialog.title("Scan Results")
        result_dialog.geometry("500x400")
    
        # Summary at top
        tk.Label(result_dialog, text=message, font=s.ui_font_bold, justify='left').pack(pady=10, padx=10)
    
        # If there are items not found, show them in a scrollable list
        if not_found:
            tk.Label(result_dialog, text="Items without images in EcoDump:", font=s.ui_font).pack(pady=5)
        
            list_frame = tk.Frame(result_dialog)
            list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")
        
            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=s.ui_font)
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=listbox.yview)
        
            for item in sorted(not_found):
                listbox.insert(tk.END, item)
    
        tk.Button(result_dialog, text="OK", command=result_dialog.destroy, font=s.ui_font).pack(pady=10)

    def _browse_foreground(s):
        filename = filedialog.askopenfilename(
            title="Select Foreground Image",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialdir=str(Path(__file__).parent)
        )
        
        if filename:
            if not filename.lower().endswith('.png'):
                messagebox.showerror("Error", "Only PNG images are supported.")
                return
            
            s.foreground_path.delete(0, 'end')
            s.foreground_path.insert(0, filename)
            s._check_combine_valid()

    def _browse_background(s):
        filename = filedialog.askopenfilename(
            title="Select Background Image",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialdir=str(Path(__file__).parent)
        )
        
        if filename:
            if not filename.lower().endswith('.png'):
                messagebox.showerror("Error", "Only PNG images are supported.")
                return
            
            s.background_path.delete(0, 'end')
            s.background_path.insert(0, filename)
            s._check_combine_valid()

    def _check_combine_valid(s, *_):
        fg_valid = (Path(s.foreground_path.get()).exists() and 
                   s.foreground_path.get().lower().endswith('.png'))
        bg_valid = (Path(s.background_path.get()).exists() and 
                   s.background_path.get().lower().endswith('.png'))
        
        if fg_valid and bg_valid:
            s.combine_btn.config(state='normal')
        else:
            s.combine_btn.config(state='disabled')

    def _combine_images(s):
        sel = s.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an item first.")
            return
        
        idx = int(sel[0])
        if idx >= len(s.filtered_data):
            messagebox.showerror("Error", "Invalid selection.")
            return
        
        name = s.filtered_data[idx]['result_item']
        
        fg_path = s.foreground_path.get()
        bg_path = s.background_path.get()
        
        if not (Path(fg_path).exists() and fg_path.lower().endswith('.png')):
            messagebox.showerror("Error", "Invalid foreground image file.")
            return
        
        if not (Path(bg_path).exists() and bg_path.lower().endswith('.png')):
            messagebox.showerror("Error", "Invalid background image file.")
            return
        
        if not Image:
            messagebox.showerror("Error", "PIL library is required for image combination.")
            return
        
        try:
            fg_img = Image.open(fg_path).convert("RGBA")
            bg_img = Image.open(bg_path).convert("RGBA")
            
            target_size = max(fg_img.size[0], fg_img.size[1], bg_img.size[0], bg_img.size[1])
            if target_size < 64:
                target_size = 64
            
            fg_img.thumbnail((target_size, target_size), Image.LANCZOS)
            bg_img.thumbnail((target_size, target_size), Image.LANCZOS)
            
            combined = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
            
            bg_x = (target_size - bg_img.size[0]) // 2
            bg_y = (target_size - bg_img.size[1]) // 2
            combined.paste(bg_img, (bg_x, bg_y), bg_img)
            
            fg_x = (target_size - fg_img.size[0]) // 2
            fg_y = (target_size - fg_img.size[1]) // 2
            combined.paste(fg_img, (fg_x, fg_y), fg_img)
            
            script_dir = Path(__file__).parent
            ico_dir = script_dir / 'EcoIcons'
            ico_dir.mkdir(exist_ok=True)
            
            # FIX: Use CamelCase for icon filename
            icon_name = spaced_to_camel_case(name)
            dest = ico_dir / f"{icon_name}.png"
            
            combined.save(dest, "PNG")
            
            s.icons[name] = str(dest)
            
            orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), None)
            if orig_idx is not None:
                try:
                    im = Image.open(dest).resize((32, 32), Image.LANCZOS)
                    small_img = ImageTk.PhotoImage(im)
                    s.small_icons[orig_idx] = small_img
                except Exception as e:
                    log(f"Error loading new combined icon: {e}")
            
            s.foreground_path.delete(0, 'end')
            s.background_path.delete(0, 'end')
            s._check_combine_valid()
            
            s.filter()
            
            for idx, rec in enumerate(s.filtered_data):
                if rec['result_item'] == name:
                    s.tree.selection_set(str(idx))
                    s.tree.see(str(idx))
                    s.show()
                    break
            
            messagebox.showinfo("Images Combined", 
                              f"Foreground and background images successfully combined and linked to {name}.")
            
        except Exception as e:
            log(f"Error combining images: {e}")
            messagebox.showerror("Error", f"Failed to combine images: {e}")

    def _browse_image(s):
        sel = s.tree.selection()
        if not sel: 
            messagebox.showwarning("No Selection", "Please select an item first.")
            return
        
        filename = filedialog.askopenfilename(
            title="Select Image",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialdir=str(Path(__file__).parent)
        )
        
        if filename:
            if not filename.lower().endswith('.png'):
                messagebox.showerror("Error", "Only PNG images are supported.")
                return
            
            s.image_path.delete(0, 'end')
            s.image_path.insert(0, filename)
            
            s._link_image()

    def _link_image(s):
        sel = s.tree.selection()
        if not sel: 
            messagebox.showwarning("No Selection", "Please select an item first.")
            return
        
        idx = int(sel[0])
        if idx >= len(s.filtered_data):
            messagebox.showerror("Error", "Invalid selection.")
            return
            
        name = s.filtered_data[idx]['result_item']
        src_path = s.image_path.get()
        
        if not Path(src_path).exists():
            messagebox.showerror("Error", "Source image file not found.")
            return
            
        if not src_path.lower().endswith('.png'):
            messagebox.showerror("Error", "Only PNG images are supported.")
            return
            
        script_dir = Path(__file__).parent
        ico_dir = script_dir / 'EcoIcons'
        ico_dir.mkdir(exist_ok=True)
        
        # FIX: Use CamelCase for icon filename
        icon_name = spaced_to_camel_case(name)
        dest = ico_dir / f"{icon_name}.png"
        
        try:
            shutil.copy(src_path, dest)
            s.icons[name] = str(dest)
            
            orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), None)
            if orig_idx is not None:
                if Image:
                    try:
                        im = Image.open(dest).resize((32, 32), Image.LANCZOS)
                        small_img = ImageTk.PhotoImage(im)
                        s.small_icons[orig_idx] = small_img
                    except Exception as e:
                        log(f"Error loading new icon: {e}")
                        messagebox.showwarning("Warning", f"Image linked but icon preview failed: {e}")
            
            s.image_path.delete(0, 'end')
            
            s.filter()

            for idx, rec in enumerate(s.filtered_data):
                if rec['result_item'] == name:
                    s.tree.selection_set(str(idx))
                    s.tree.see(str(idx))
                    s.show()
                    break
            
            messagebox.showinfo("Image Linked", f"Image successfully linked to {name}.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy image: {e}")
            
    def _auto_scan_image(s):
        sel = s.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select an item first.")
            return
    
        idx = int(sel[0])
        if idx >= len(s.filtered_data):
            messagebox.showerror("Error", "Invalid selection.")
            return
    
        name = s.filtered_data[idx]['result_item']
    
        # Define the EcoDump folder path
        script_dir = Path(__file__).parent
        ecodump_dir = script_dir / 'EcoDump'
    
        if not ecodump_dir.exists():
            messagebox.showerror("Error", f"EcoDump folder not found at: {ecodump_dir}")
            return
    
        # Search for the PNG file - FIX: Use CamelCase for search
        icon_name = spaced_to_camel_case(name)
        target_filename = f"{icon_name}.png"
        found_path = None
    
        s.st.config(text=f'Scanning for {target_filename}...')
        s.pb.start()
    
        # Walk through all subdirectories
        try:
            for path in ecodump_dir.rglob(target_filename):
                if path.is_file():
                    found_path = path
                    break
        except Exception as e:
            log(f"Error scanning EcoDump: {e}")
    
        s.pb.stop()
    
        if not found_path:
            s.st.config(text=f'No image found for {name}')
            messagebox.showinfo("Not Found", f"No PNG file named '{target_filename}' was found in the EcoDump folder or its subfolders.")
            return
            
        # Link the image silently (without popups)
        if not str(found_path).lower().endswith('.png'):
            messagebox.showerror("Error", "Only PNG images are supported.")
            return
            
        script_dir = Path(__file__).parent
        ico_dir = script_dir / 'EcoIcons'
        ico_dir.mkdir(exist_ok=True)
        dest = ico_dir / f"{icon_name}.png"
        
        try:
            shutil.copy(found_path, dest)
            s.icons[name] = str(dest)
            
            orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), None)
            if orig_idx is not None:
                if Image:
                    try:
                        im = Image.open(dest).resize((32, 32), Image.LANCZOS)
                        small_img = ImageTk.PhotoImage(im)
                        s.small_icons[orig_idx] = small_img
                    except Exception as e:
                        log(f"Error loading new icon: {e}")
            
            s.image_path.delete(0, 'end')
            
            s.filter()

            for idx, rec in enumerate(s.filtered_data):
                if rec['result_item'] == name:
                    s.tree.selection_set(str(idx))
                    s.tree.see(str(idx))
                    s.show()
                    break
            
            s.st.config(text=f'✓ Found and linked image for {name}')
            
        except Exception as e:
            log(f"Error linking auto-scanned image: {e}")
            messagebox.showerror("Error", f"Failed to link image: {e}")
                        
    def _placeholder_red_small(s):
        if not hasattr(s,'_red_small') and Image:
            im = Image.new('RGBA', (32,32), (255,0,0,255))
            s._red_small = ImageTk.PhotoImage(im)
        return getattr(s, '_red_small', None)

    def _placeholder_red_large(s):
        if not hasattr(s,'_red_large') and Image:
            im = Image.new('RGBA', (128,128), (255,0,0,255))
            s._red_large = ImageTk.PhotoImage(im)
        return getattr(s, '_red_large', None)

    def toggle_tags_filter(s):
        if s.filter_tag:
            s.clear_tag_filter()
        else:
            s.show_tags_filter()

    def show_tags_filter(s):
        all_tags = set()
        for tags_list in s._tags.values():
            all_tags.update(tags_list)
        
        if not all_tags:
            messagebox.showinfo("No Tags", "No tags have been defined yet.")
            return
        
        dialog = tk.Toplevel(s.r)
        dialog.title("Filter by Tag")
        dialog.geometry("400x500")
        
        tk.Label(dialog, text="Click a tag to filter items:", font=s.ui_font_bold).pack(pady=10)
        
        canvas = tk.Canvas(dialog)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        script_dir = Path(__file__).parent
        tag_icons_dir = script_dir / 'TagIcons'
        
        for tag in sorted(all_tags):
            tag_frame = tk.Frame(scrollable_frame, relief="raised", borderwidth=1, cursor="hand2")
            tag_frame.pack(fill="x", padx=10, pady=2)
            
            # FIX: Convert tag name to CamelCase for icon lookup
            tag_icon_name = spaced_to_camel_case(tag) if ' ' in tag else tag
            tag_icon_path = tag_icons_dir / f"{tag_icon_name}.png"
            if tag_icon_path.exists() and Image:
                try:
                    tag_img = Image.open(tag_icon_path).resize((32, 32), Image.LANCZOS)
                    tag_photo = ImageTk.PhotoImage(tag_img)
                    icon_label = tk.Label(tag_frame, image=tag_photo)
                    icon_label.image = tag_photo
                except:
                    icon_label = tk.Label(tag_frame, bg='gray', width=4, height=2)
            else:
                icon_label = tk.Label(tag_frame, bg='gray', width=4, height=2)
            
            icon_label.pack(side="left", padx=5, pady=5)
            
            tag_label = tk.Label(tag_frame, text=tag, font=s.ui_font)
            tag_label.pack(side="left", padx=5)
            
            count = sum(1 for item_tags in s._tags.values() if tag in item_tags)
            count_label = tk.Label(tag_frame, text=f"({count} items)", font=s.ui_font, fg="gray")
            count_label.pack(side="right", padx=10)
            
            def apply_filter(event, tag_name=tag):
                s.filter_tag = tag_name
                s._update_filter_label_with_icon(tag_name)
                s.tags_filter_btn.config(text="Clear Tags", bg="lightcoral")
                
                s.q.set("")
                
                if tag_name.lower() == 'food':
                    s.nutrition_sort_frame.pack(side="left", padx=(10, 0))
                else:
                    s.nutrition_sort_frame.pack_forget()
                    s.sort_var.set("Name (A-Z)")
                
                dialog.destroy()
                s.filter()
            
            for widget in [tag_frame, icon_label, tag_label, count_label]:
                widget.bind("<Button-1>", apply_filter)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def on_canvas_mousewheel(event):
            canvas.yview_scroll(int(-3*(event.delta/120)), "units")
            return "break"
        
        def bind_mousewheel_to_all(widget):
            widget.bind("<MouseWheel>", on_canvas_mousewheel)
            if platform.system() == "Linux":
                widget.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
                widget.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))
            
            for child in widget.winfo_children():
                bind_mousewheel_to_all(child)
        
        canvas.bind("<MouseWheel>", on_canvas_mousewheel)
        if platform.system() == "Linux":
            canvas.bind("<Button-4>", lambda e: canvas.yview_scroll(-3, "units"))
            canvas.bind("<Button-5>", lambda e: canvas.yview_scroll(3, "units"))
        
        bind_mousewheel_to_all(scrollable_frame)
        
        button_frame = tk.Frame(dialog)
        button_frame.pack(fill="x", pady=10)
        
        def reset_filter():
            s.filter_tag = None
            s.current_filter_label.config(text="")
            s.tags_filter_btn.config(text="Tags", bg="SystemButtonFace")
            s.nutrition_sort_frame.pack_forget()
            s.sort_var.set("Name (A-Z)")
            dialog.destroy()
            s.filter()
        
        tk.Button(button_frame, text="Reset Filter", command=reset_filter, 
                 font=s.ui_font, width=15).pack(side="left", padx=20)
        
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, 
                 font=s.ui_font).pack(side="right", padx=20)

    def toggle_food_filter(s):
        if s.filter_tag == 'Food':
            s.clear_tag_filter()
        else:
            s.filter_tag = 'Food'
            s._update_filter_label_with_icon('Food')
            s.tags_filter_btn.config(text="Clear Tags", bg="lightcoral")
            s.food_items_btn.config(bg="lightgreen")
            
            s.q.set("")
            
            s.nutrition_sort_frame.pack(side="left", padx=(10, 0))
            s.filter()
           
    def clear_tag_filter(s):
        s.filter_tag = None
        for widget in s.current_filter_label.winfo_children():
            widget.destroy()
        s.current_filter_label.config(text="")
        s.tags_filter_btn.config(text="Tags", bg="SystemButtonFace")
        s.food_items_btn.config(bg="SystemButtonFace")
        s.nutrition_sort_frame.pack_forget()
        s.sort_var.set("Name (A-Z)")
        s.filter()

    def _apply_font_change(s, event=None):
        """Apply font change to selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            if s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"font_tag_{int(time.time() * 1000)}"
                
                font_family = s.font_var.get()
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, font=(font_family, s.ui_font[1]))
                
                s._save_current()
        except Exception as e:
            log(f"Error applying font change: {e}")
    
    def _change_notes_size(s, delta):
        """Change text size for selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            if s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"size_tag_{int(time.time() * 1000)}"
                
                # Get current font size or default
                current_size = s.ui_font[1]
                new_size = max(8, min(72, current_size + delta))
                
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, font=(s.ui_font[0], new_size))
                
                s._save_current()
        except Exception as e:
            log(f"Error changing notes size: {e}")
    
    def _toggle_notes_bold(s):
        """Toggle bold formatting for selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            if s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"bold_tag_{int(time.time() * 1000)}"
                
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, font=(s.ui_font[0], s.ui_font[1], 'bold'))
                
                s._save_current()
        except Exception as e:
            log(f"Error toggling notes bold: {e}")
    
    def _toggle_notes_italic(s):
        """Toggle italic formatting for selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            if s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"italic_tag_{int(time.time() * 1000)}"
                
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, font=(s.ui_font[0], s.ui_font[1], 'italic'))
                
                s._save_current()
        except Exception as e:
            log(f"Error toggling notes italic: {e}")
    
    def _choose_text_color(s):
        """Choose text color for selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="Choose Text Color")[1]
            if color and s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"color_tag_{int(time.time() * 1000)}"
                
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, foreground=color)
                
                # Update button color to show current choice
                s.text_color_btn.config(bg=color, fg='white' if color in ['#000000', '#800000', '#000080'] else 'black')
                
                s._save_current()
        except Exception as e:
            log(f"Error choosing text color: {e}")
    
    def _choose_highlight_color(s):
        """Choose highlight color for selected text in notes"""
        if not s.selected_item:
            return
        
        try:
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="Choose Highlight Color")[1]
            if color and s.notes.tag_ranges(tk.SEL):
                sel_start = s.notes.index(tk.SEL_FIRST)
                sel_end = s.notes.index(tk.SEL_LAST)
                
                import time
                tag_name = f"highlight_tag_{int(time.time() * 1000)}"
                
                s.notes.tag_add(tag_name, sel_start, sel_end)
                s.notes.tag_config(tag_name, background=color)
                
                # Update button color to show current choice
                s.highlight_color_btn.config(bg=color, fg='white' if color in ['#000000', '#800000', '#000080'] else 'black')
                
                s._save_current()
        except Exception as e:
            log(f"Error choosing highlight color: {e}")

    def toggle_edit_mode(s):
        s.edit_mode = not s.edit_mode
        
        if s.edit_mode:
            s.desc_txt.config(state='normal')
            # Add glow effect to pencil when edit mode is active
            if hasattr(s, 'pencil_label'):
                s.pencil_label.config(bg='#ffff99', relief='raised', borderwidth=2)  # Yellow glow effect
            s.save_indicator.config(text='🖊 Edit Mode', fg='orange')
        else:
            s.desc_txt.config(state='disabled')
            # Remove glow effect from pencil
            if hasattr(s, 'pencil_label'):
                s.pencil_label.config(bg='SystemButtonFace', relief='flat', borderwidth=0)  # Normal appearance
            s.save_indicator.config(text='')
    
    def _change_text_size(s, delta):
        # Placeholder for text size changes
        pass
    
    def _toggle_bold(s):
        # Placeholder for bold toggle
        pass
    
    def _toggle_italic(s):
        # Placeholder for italic toggle
        pass

    def _on_close(s):
        """Handle application close"""
        try:
            s._save_current()
        except Exception as e:
            log(f"Error saving on close: {e}")
        s.r.destroy()

if __name__ == "__main__":
    try:
        log("Starting Eco Recipe Scanner with Enhanced Room Tier Display and FIXED Navigation...")
        root = tk.Tk()
        GUI(root)
        root.mainloop()
    except Exception as e:
        log(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
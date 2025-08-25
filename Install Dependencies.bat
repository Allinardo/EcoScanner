# eco_recipe_gui_with_notes.pyw – v4.6
# With hide functionality and calorie count display

import os, re, json, threading, tkinter as tk
from tkinter import filedialog, messagebox, ttk
import shutil
from datetime import datetime
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

DEFAULT_ECO_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Eco"
LOG = "eco_parser.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%F %T}  {msg}\n")

# ── Regex for parsing recipes ──
PAT_RES      = re.compile(r"new\s+CraftingElement<\s*(\w+?)Item", re.I)
PAT_ING_STR  = re.compile(r'IngredientElement\s*\(\s*"(\w+?)"\s*,\s*(\d+)', re.I)
PAT_ING_TYPE = re.compile(r'IngredientElement\s*\(\s*typeof\((\w+?)Item\)\s*,\s*(\d+)', re.I)
PAT_ING_GEN  = re.compile(r'IngredientElement<\s*(\w+?)Item\s*>\s*\(\s*(\d+)', re.I)
PAT_DESC     = re.compile(r'\[LocDescription\("(.+?)"\)\]', re.S)
PAT_REQSK    = re.compile(r'\[RequiresSkill\(\s*typeof\((\w+?)Skill\)\s*,\s*(\d+)', re.I)
PAT_SK       = re.compile(r"RequiredSkillType\s*=\s*typeof\((\w+)", re.I)
PAT_LVL      = re.compile(r"RequiredSkillLevel\s*=\s*(\d+)", re.I)
PAT_TAB      = [
    re.compile(r"CraftingTable\s*=\s*typeof\((\w+?)Object\)", re.I),
    re.compile(r"AddRecipe<\s*(\w+?)Object", re.I),
    re.compile(r"AddRecipe\s*\([^,]+,\s*typeof\((\w+?)Object\)", re.I),
    re.compile(r"Initialize\([^)]*typeof\((\w+?)Object\)", re.I),
    re.compile(r"AddRecipe\([^)]*tableType\s*:\s*typeof\((\w+?)Object\)", re.I),
]

# For uncraftable items and better item detection
PAT_ITEM_CLASS = re.compile(r"class\s+(\w+?)Item\b")
PAT_ITEM_DESC  = re.compile(r'\[LocDescription\("(.+?)"\)\]', re.S)

# ── New patterns for nutrition parsing ──
PAT_CALORIES = re.compile(r"Calories\s*=\s*(\d+)", re.I)
PAT_CARBS = re.compile(r"Carbs\s*=\s*(\d+)", re.I)
PAT_PROTEIN = re.compile(r"Protein\s*=\s*(\d+)", re.I)
PAT_FAT = re.compile(r"Fat\s*=\s*(\d+)", re.I)
PAT_VITAMINS = re.compile(r"Vitamins\s*=\s*(\d+)", re.I)
PAT_NUTRIENTS = re.compile(r"Nutrients\s*=\s*new\s*List<.*?>\s*\{([^}]+)\}", re.S | re.I)

# Eco nutrient colors
NUTRIENT_COLORS = {
    'calories': {'fg': '#666666', 'bg': '#E0E0E0'},  # Grey
    'carbs': {'fg': '#FFFFFF', 'bg': '#CC0000'},     # Red with white text
    'protein': {'fg': '#FFFFFF', 'bg': '#FF6600'},   # Orange with white text
    'fat': {'fg': '#000000', 'bg': '#FFCC00'},       # Yellow with black text
    'vitamins': {'fg': '#FFFFFF', 'bg': '#00AA00'}   # Green with white text
}


def parse_items(txt: str):
    out = []
    for m in PAT_ITEM_CLASS.finditer(txt):
        name = m.group(1)
        d = PAT_ITEM_DESC.search(txt, m.end())
        out.append({
            "result_item": name,
            "description": (d.group(1).strip() if d else ""),
            "ingredients": [],  # uncraftable
        })
    return out


def parse_nutrition(txt: str):
    """Extract nutrition information from CS file text"""
    nutrition = {}
    
    # Try direct property matches first
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
    
    # Also try to parse from Nutrients list format
    if nutrients := PAT_NUTRIENTS.search(txt):
        nutrient_text = nutrients.group(1)
        # Parse individual nutrient values from the list
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
    
    # Debug: Let's log what we found
    if nutrition:
        log(f"Found nutrition data: {nutrition}")
    
    return nutrition if nutrition else None


def parse_cs(path: str):
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except Exception as e:
        log(f"read fail {path}: {e}")
        return None
    
    # Check for recipes first
    recipe_result = None
    if "new Recipe" in txt or "new RecipeFamily" in txt:
        m = PAT_RES.search(txt)
        if m:
            rec = {"result_item": m.group(1), "type": "recipe"}
            if d := PAT_DESC.search(txt):
                rec["description"] = d.group(1).strip()
            rec["ingredients"] = [
                (i.replace("Item",""), int(q))
                for pat in (PAT_ING_STR, PAT_ING_TYPE, PAT_ING_GEN)
                for i, q in pat.findall(txt)
            ]
            if sk := PAT_REQSK.search(txt):
                rec.update(skill=sk.group(1), level=int(sk.group(2)))
            else:
                sk2, lv2 = PAT_SK.search(txt), PAT_LVL.search(txt)
                if sk2 and lv2:
                    rec.update(skill=sk2.group(1).replace("Skill",""), level=int(lv2.group(1)))
            tb = next((p.search(txt) for p in PAT_TAB if p.search(txt)), None)
            if tb:
                rec["crafting_table"] = tb.group(1)
            
            # Parse nutrition for food items
            nutrition = parse_nutrition(txt)
            if nutrition:
                rec["nutrition"] = nutrition
            
            recipe_result = rec
    
    # Also check for item classes (for uncraftable items or additional info)
    item_results = []
    for m in PAT_ITEM_CLASS.finditer(txt):
        name = m.group(1)
        # Skip if we already have this as a recipe
        if recipe_result and recipe_result["result_item"] == name:
            continue
        
        # Look for description near the class definition
        desc_search_start = max(0, m.start() - 500)
        desc_search_end = min(len(txt), m.end() + 500)
        desc_text = txt[desc_search_start:desc_search_end]
        
        d = PAT_ITEM_DESC.search(desc_text)
        item_data = {
            "result_item": name,
            "type": "item",
            "description": (d.group(1).strip() if d else ""),
            "ingredients": [],  # uncraftable items have no ingredients
        }
        
        # Parse nutrition for food items even if they're not craftable
        nutrition = parse_nutrition(txt)
        if nutrition:
            item_data["nutrition"] = nutrition
        
        item_results.append(item_data)
    
    # Return recipe if found, otherwise return item results
    if recipe_result:
        return recipe_result
    elif item_results:
        return item_results[0]
    
    return None


class GUI:
    def __init__(s, root):
        s.r = root
        root.title("Eco Recipe Scanner v4.6")
        root.geometry("1290x984")

        # --- State and persistence ---
        s.notes_file = os.path.join(os.path.dirname(__file__), 'notes.json')
        try:
            with open(s.notes_file, 'r', encoding='utf-8') as f:
                s._notes = json.load(f)
        except:
            s._notes = {}
        
        s.tags_file = os.path.join(os.path.dirname(__file__), 'tags.json')
        try:
            with open(s.tags_file, 'r', encoding='utf-8') as f:
                s._tags = json.load(f)
        except:
            s._tags = {}
        
        # Hidden items tracking
        s.hidden_items_file = os.path.join(os.path.dirname(__file__), 'hidden_items.json')
        try:
            with open(s.hidden_items_file, 'r', encoding='utf-8') as f:
                s._hidden_items = set(json.load(f))
        except:
            s._hidden_items = set()
        
        # Custom edits file - this will store all user edits to item data
        s.custom_edits_file = os.path.join(os.path.dirname(__file__), 'custom_item_data.json')
        try:
            with open(s.custom_edits_file, 'r', encoding='utf-8') as f:
                s._custom_edits = json.load(f)
        except:
            s._custom_edits = {}

        s.folder = tk.StringVar(value=DEFAULT_ECO_PATH)
        s.q = tk.StringVar()
        s.sort_var = tk.StringVar(value="Alphabetical")
        s.data = []
        s.filtered_data = []  # Track filtered data
        s.icons = {}
        s.small_icons = {}
        s.large_icons = {}
        s.selected_item = None
        s.edit_mode = False  # Track edit mode state
        s.pencil_angle = 0  # For pencil animation
        s.pencil_direction = 1  # Animation direction

        # --- Load custom fonts FIRST before creating UI ---
        fonts_dir = os.path.join(os.path.dirname(__file__), 'Fonts')
        
        # Load EBGaramond for tree list (size 14)
        s.tree_font = ('Arial', 14)  # Fallback
        eb_garamond_path = os.path.join(fonts_dir, 'EBGaramond-VariableFont_wght.ttf')
        if os.path.isfile(eb_garamond_path):
            try:
                root.tk.call('font', 'create', 'EBGaramond', '-family', eb_garamond_path, '-size', 14)
                s.tree_font = ('EBGaramond', 14)
            except:
                pass
        
        # Load DMSerifText-Italic for main text display
        s.main_text_font = ('Arial', 11, 'italic')  # Fallback
        dm_serif_path = os.path.join(fonts_dir, 'DMSerifText-Italic.ttf')
        if os.path.isfile(dm_serif_path):
            try:
                root.tk.call('font', 'create', 'DMSerifText', '-family', dm_serif_path, '-size', 11, '-slant', 'italic')
                s.main_text_font = ('DMSerifText', 11, 'italic')
            except:
                pass
        
        # Load Arimo for nutrition values
        s.nutrition_font = ('Arial', 10)  # Fallback
        arimo_path = os.path.join(fonts_dir, 'Arimo-VariableFont_wght.ttf')
        if os.path.isfile(arimo_path):
            try:
                root.tk.call('font', 'create', 'Arimo', '-family', arimo_path, '-size', 10)
                s.nutrition_font = ('Arimo', 10)
                s.nutrition_font_bold = ('Arimo', 10, 'bold')
            except:
                s.nutrition_font_bold = ('Arial', 10, 'bold')
        else:
            s.nutrition_font_bold = ('Arial', 10, 'bold')
        
        # Load Alice for all other UI text
        s.ui_font = ('Arial', 10)  # Fallback
        alice_path = os.path.join(fonts_dir, 'Alice-Regular.ttf')
        if os.path.isfile(alice_path):
            try:
                root.tk.call('font', 'create', 'Alice', '-family', alice_path, '-size', 10)
                s.ui_font = ('Alice', 10)
                s.ui_font_bold = ('Alice', 12, 'bold')
            except:
                s.ui_font_bold = ('Arial', 12, 'bold')
        else:
            s.ui_font_bold = ('Arial', 12, 'bold')

        # --- Top controls ---
        top = tk.Frame(root); top.pack(fill="x", padx=6, pady=6)
        
        # Parse button - prominent, top left
        parse_btn = tk.Button(top, text="PARSE ▶", command=s.run, 
                             font=s.ui_font_bold, 
                             bg='#4CAF50', fg='white',
                             padx=20, pady=10)
        parse_btn.pack(side="left", padx=(0, 15))
        
        # Separator
        tk.Label(top, text="|", font=('Arial', 14), fg='gray').pack(side="left", padx=10)
        
        # Eco folder controls
        tk.Entry(top, textvariable=s.folder, width=50, font=s.ui_font).pack(side="left", padx=4)
        tk.Button(top, text="Eco Game Folder...", command=s.pick, font=s.ui_font).pack(side="left")
        tk.Button(top, text="Refresh Images", command=s.refresh_images, bg="lightblue", font=s.ui_font).pack(side="left", padx=6)
        tk.Button(top, text="Hidden Items", command=s.show_hidden_items, bg="lightyellow", font=s.ui_font).pack(side="left", padx=2)
        s.st = tk.Label(top, fg="blue", font=s.ui_font); s.st.pack(side="left", padx=8)
        s.pb = ttk.Progressbar(top, mode="indeterminate", length=140)
        s.pb.pack(side="left", padx=4)

        # --- Search and Sort bar ---
        sr = tk.Frame(root); sr.pack(fill="x", padx=6, pady=(0,6))
        tk.Label(sr, text="Search:", font=s.ui_font).pack(side="left")
        e = tk.Entry(sr, textvariable=s.q, width=30, font=s.ui_font); e.pack(side="left", padx=4)
        e.bind("<KeyRelease>", s.filter)
        
        # Sort controls
        tk.Label(sr, text="Sort by:", font=s.ui_font).pack(side="left", padx=(20, 5))
        sort_dropdown = ttk.Combobox(sr, textvariable=s.sort_var, values=["Alphabetical", "Tags"], 
                                    state='readonly', width=15, font=s.ui_font)
        sort_dropdown.pack(side="left")
        sort_dropdown.bind('<<ComboboxSelected>>', lambda e: s.filter())

        # --- Load custom fonts ---
        fonts_dir = os.path.join(os.path.dirname(__file__), 'Fonts')
        
        # Load EBGaramond for tree list (size 14)
        s.tree_font = ('Arial', 14)  # Fallback
        eb_garamond_path = os.path.join(fonts_dir, 'EBGaramond-VariableFont_wght.ttf')
        if os.path.isfile(eb_garamond_path):
            try:
                root.tk.call('font', 'create', 'EBGaramond', '-family', eb_garamond_path, '-size', 14)
                s.tree_font = ('EBGaramond', 14)
            except:
                pass
        
        # Load DMSerifText-Italic for main text display
        s.main_text_font = ('Arial', 11, 'italic')  # Fallback
        dm_serif_path = os.path.join(fonts_dir, 'DMSerifText-Italic.ttf')
        if os.path.isfile(dm_serif_path):
            try:
                root.tk.call('font', 'create', 'DMSerifText', '-family', dm_serif_path, '-size', 11, '-slant', 'italic')
                s.main_text_font = ('DMSerifText', 11, 'italic')
            except:
                pass
        
        # Load Arimo for nutrition values
        s.nutrition_font = ('Arial', 10)  # Fallback
        arimo_path = os.path.join(fonts_dir, 'Arimo-VariableFont_wght.ttf')
        if os.path.isfile(arimo_path):
            try:
                root.tk.call('font', 'create', 'Arimo', '-family', arimo_path, '-size', 10)
                s.nutrition_font = ('Arimo', 10)
                s.nutrition_font_bold = ('Arimo', 10, 'bold')
            except:
                s.nutrition_font_bold = ('Arial', 10, 'bold')
        else:
            s.nutrition_font_bold = ('Arial', 10, 'bold')
        
        # Load Alice for all other UI text
        s.ui_font = ('Arial', 10)  # Fallback
        alice_path = os.path.join(fonts_dir, 'Alice-Regular.ttf')
        if os.path.isfile(alice_path):
            try:
                root.tk.call('font', 'create', 'Alice', '-family', alice_path, '-size', 10)
                s.ui_font = ('Alice', 10)
                s.ui_font_bold = ('Alice', 12, 'bold')
            except:
                s.ui_font_bold = ('Arial', 12, 'bold')
        else:
            s.ui_font_bold = ('Arial', 12, 'bold')

        # --- Panes ---
        pane = ttk.PanedWindow(root, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=6)
        
        # Create tree
        s.tree = ttk.Treeview(pane, show="tree")
        s.tree.column("#0", width=420)
        s.tree.bind("<<TreeviewSelect>>", s.show)
        s.tree.bind("<Button-1>", s._on_tree_click)
        
        style = ttk.Style()
        style.configure("Treeview", font=s.tree_font)
        
        pane.add(s.tree, weight=1)

        rt = tk.Frame(pane)
        top_section = tk.Frame(rt); top_section.pack(fill='x', pady=(0,4))
        
        left_frame = tk.Frame(top_section); left_frame.pack(side='left', anchor='nw', padx=(0,10))
        tk.Label(left_frame, text='Item Tags', font=s.ui_font_bold).pack(anchor='w')
        s.tags_display_frame = tk.Frame(left_frame); s.tags_display_frame.pack(anchor='w', pady=(0,6))
        
        s.ic = tk.Label(top_section); s.ic.pack(side='left', padx=(10,10))
        
        right_frame = tk.Frame(top_section); right_frame.pack(side='left', anchor='ne', padx=(10,0))
        s.fill_tag_entry = tk.Entry(right_frame, width=15, font=s.ui_font); s.fill_tag_entry.pack(pady=(0,5))
        s.fill_tag_entry.insert(0, "Fill Tag")
        s.fill_tag_entry.bind('<FocusIn>', s._clear_fill_tag_placeholder)
        s.fill_tag_entry.bind('<FocusOut>', s._restore_fill_tag_placeholder)
        s.fill_tag_entry.config(fg='gray')
        
        s.tag_var = tk.StringVar()
        all_tags = sorted({t for tags in s._tags.values() for t in tags})
        s.tag_dropdown = ttk.Combobox(right_frame, textvariable=s.tag_var, values=all_tags, width=15, state='readonly', font=s.ui_font)
        s.tag_dropdown.pack(pady=(0,5))
        s.tag_dropdown.set("Tag Dropdown")
        
        tk.Button(right_frame, text='Add Tag', command=s._add_tag, font=s.ui_font).pack()
        
        link_frame = tk.Frame(rt); link_frame.pack(pady=(0,4))
        s.image_path = tk.Entry(link_frame, width=40, font=s.ui_font); s.image_path.pack(side="left", padx=(0,5))
        s.image_path.bind("<KeyRelease>", s._check_image_path_valid)
        s.link_btn = tk.Button(link_frame, text="Link Image", state="disabled", command=s._link_image, font=s.ui_font)
        s.link_btn.pack(side="left")
        
        s.txt_frame = tk.Frame(rt); s.txt_frame.pack(fill="both", expand=True)
        
        # Create top bar for edit button
        txt_top_bar = tk.Frame(s.txt_frame)
        txt_top_bar.pack(fill="x")
        
        # Load pencil icon
        s.pencil_icon = None
        s.pencil_photo = None
        pencil_path = os.path.join(os.path.dirname(__file__), 'AppIcons', 'Pencil.png')
        if os.path.isfile(pencil_path) and Image:
            try:
                s.pencil_icon = Image.open(pencil_path).resize((20, 20), Image.LANCZOS)
                s.pencil_photo = ImageTk.PhotoImage(s.pencil_icon)
            except:
                pass
        
        # Create edit button with pencil icon
        edit_button_frame = tk.Frame(txt_top_bar)
        edit_button_frame.pack(side="right", padx=5, pady=2)
        
        if s.pencil_photo:
            s.pencil_label = tk.Label(edit_button_frame, image=s.pencil_photo)
            s.pencil_label.pack(side="left", padx=(0, 5))
        
        s.edit_button = tk.Button(edit_button_frame, text="Edit", 
                                 font=s.ui_font, width=6)
        s.edit_button.pack(side="left")
        
        # Create scrollbar for main text
        txt_scroll_frame = tk.Frame(s.txt_frame)
        txt_scroll_frame.pack(fill="both", expand=True)
        
        txt_scroll = tk.Scrollbar(txt_scroll_frame)
        txt_scroll.pack(side="right", fill="y")
        
        # Create text widget (starts as read-only)
        s.txt = tk.Text(txt_scroll_frame, wrap="word", font=s.main_text_font, 
                       yscrollcommand=txt_scroll.set, state="disabled")
        s.txt.pack(side="left", fill="both", expand=True)
        txt_scroll.config(command=s.txt.yview)
        
        # Bind text change event
        s.txt.bind('<KeyRelease>', s._on_text_edit)
        
        # Add save indicator
        s.save_indicator = tk.Label(rt, text='', fg='green', font=s.ui_font)
        s.save_indicator.pack(anchor='e', padx=4)
        
        tk.Label(rt, text='Notes:', font=s.ui_font).pack(anchor='w', padx=4, pady=(4,0))
        s.notes = tk.Text(rt, wrap='word', height=6, font=s.ui_font); s.notes.pack(fill='both', padx=4, pady=(0,6))
        
        # Start pencil animation
        s._animate_pencil()
        
        pane.add(rt, weight=3)

        # Configure text tags for styling
        s.txt.tag_config('item_name', font=(s.main_text_font[0], 14, 'bold'))
        s.txt.tag_config('nutrition_header', font=(s.main_text_font[0], 12, 'bold'))
        s.txt.tag_config('calorie_count', font=(s.main_text_font[0], 10, 'italic'), foreground='#444444')
        s.txt.tag_config('calorie_count_display', font=s.nutrition_font_bold, 
                        foreground='black', background='#E0E0E0')
        
        # Configure nutrition tags with Eco colors
        for nutrient, colors in NUTRIENT_COLORS.items():
            s.txt.tag_config(f'nutrient_{nutrient}', 
                            foreground=colors['fg'], 
                            background=colors['bg'],
                            font=s.nutrition_font_bold)
        
        bt = tk.Frame(root); bt.pack(fill="x", padx=6, pady=4)
        tk.Button(bt, text="Export JSON", command=s.export, font=s.ui_font).pack(side="right")
        tk.Button(bt, text="Export Custom Data", command=s.export_custom_data, 
                 font=s.ui_font, bg='lightgreen').pack(side="right", padx=5)
        tk.Button(bt, text="Import Custom Data", command=s.import_custom_data, 
                 font=s.ui_font, bg='lightcyan').pack(side="right", padx=5)
        root.protocol('WM_DELETE_WINDOW', s._on_close)
        
        # Now configure the edit button command after methods are defined
        s.edit_button.config(command=s.toggle_edit_mode)

    def _on_tree_click(s, event):
        """Handle clicks on tree items"""
        # Get the region clicked
        region = s.tree.identify_region(event.x, event.y)
        if region != "tree":
            return
            
        # Get the item clicked
        item = s.tree.identify_row(event.y)
        if not item:
            return
        
        # Get the column position
        column = s.tree.identify_column(event.x)
        
        # Check if click is on the minus sign area (first 50 pixels of the text area)
        bbox = s.tree.bbox(item, column)
        if bbox:
            # Calculate relative position within the cell
            cell_x = event.x - bbox[0]
            
            # If click is within first 50 pixels (expanded hit area for minus)
            if cell_x < 50:
                # Get item name
                idx = int(item)
                if idx < len(s.filtered_data):
                    item_name = s.filtered_data[idx]['result_item']
                    s.hide_item(item_name)
                    return 'break'  # Prevent selection change

    def hide_item(s, item_name):
        """Hide an item with confirmation"""
        if messagebox.askyesno("Hide Item", f"Hide '{item_name}' from the list?"):
            s._hidden_items.add(item_name)
            s._save_hidden_items()
            s.filter()
            s.st.config(text=f"Hidden '{item_name}'")

    def show_hidden_items(s):
        """Show dialog to unhide hidden items"""
        if not s._hidden_items:
            messagebox.showinfo("No Hidden Items", "There are no hidden items.")
            return
        
        # Create hidden items dialog
        dialog = tk.Toplevel(s.r)
        dialog.title("Hidden Items")
        dialog.geometry("400x500")
        
        tk.Label(dialog, text="Click an item to unhide it:", font=s.ui_font_bold).pack(pady=10)
        
        # Listbox with scrollbar
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Add hidden items to listbox
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
        """Save hidden items list"""
        with open(s.hidden_items_file, 'w', encoding='utf-8') as f:
            json.dump(list(s._hidden_items), f, indent=2)

    def pick(s):
        d = filedialog.askdirectory(title="Select Eco/Mods folder")
        if d: s.folder.set(d)

    def refresh_images(s):
        """Refresh all images from the icon folders without re-parsing recipes"""
        if not s.data:
            messagebox.showwarning("No Data", "Parse recipes first before refreshing images.")
            return
        
        s.st.config(text='Refreshing images...'); s.pb.start()
        
        s.icons.clear()
        s.small_icons.clear()
        s.large_icons.clear()
        
        if hasattr(s, '_skill_icons'):
            s._skill_icons.clear()
        if hasattr(s, '_table_icons'):
            s._table_icons.clear()
        if hasattr(s, '_ingredient_icons'):
            s._ingredient_icons.clear()
        
        ico_dir = os.path.join(os.path.dirname(__file__), 'EcoIcons')
        
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            icon_path = os.path.join(ico_dir, f"{name}.png")
            
            if os.path.isfile(icon_path) and Image:
                try:
                    s.icons[name] = icon_path
                    im = Image.open(icon_path).resize((24, 24), Image.LANCZOS)
                    small_img = ImageTk.PhotoImage(im)
                    s.small_icons[idx] = small_img
                except:
                    small_img = s._placeholder_red_small()
                    s.small_icons[idx] = small_img
            else:
                small_img = s._placeholder_red_small()
                s.small_icons[idx] = small_img
        
        s.filter()
        
        if s.selected_item:
            s.show()
        
        s.st.config(text=f'Images refreshed for {len(s.data)} items.'); s.pb.stop()
        messagebox.showinfo("Refresh Complete", "All images have been refreshed from the icon folders.")

    def run(s):
        base = s.folder.get()
        if not os.path.isdir(base): return messagebox.showwarning("Error","Select valid folder.")
        s.st.config(text='Parsing...'); s.pb.start()
        s.tree.delete(*s.tree.get_children()); s.icons.clear(); s.data.clear()
        threading.Thread(target=s._worker, args=(base,), daemon=True).start()

    def _worker(s, base):
        recipes = {}
        items = {}
        
        for dp,_,fs in os.walk(base):
            for fn in fs:
                if fn.lower().endswith('.cs'):
                    path = os.path.join(dp, fn)
                    if result := parse_cs(path):
                        name = result['result_item']
                        if result.get('type') == 'recipe' or 'ingredients' in result and result['ingredients']:
                            recipes[name] = result
                        else:
                            if name not in recipes:
                                items[name] = result
        
        merged = {}
        merged.update(items)
        merged.update(recipes)
        
        merged_list = list(merged.values())
        merged_list.sort(key=lambda x: x['result_item'].lower())
        s.data = merged_list
        
        ico_dir = os.path.join(os.path.dirname(__file__), 'EcoIcons')
        
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            icon_path = os.path.join(ico_dir, f"{name}.png")
            
            if os.path.isfile(icon_path) and Image:
                try:
                    s.icons[name] = icon_path
                    im = Image.open(icon_path).resize((24, 24), Image.LANCZOS)
                    small_img = ImageTk.PhotoImage(im)
                    s.small_icons[idx] = small_img
                except:
                    small_img = s._placeholder_red_small()
                    s.small_icons[idx] = small_img
            else:
                small_img = s._placeholder_red_small()
                s.small_icons[idx] = small_img
        
        s.r.after(0, s._finish_parse)

    def _finish_parse(s):
        s.filter()  # This will populate the tree excluding hidden items
        s.st.config(text=f'{len(s.data)} items loaded.'); s.pb.stop()

    def filter(s, *_):
        q = s.q.get().lower()
        s.tree.delete(*s.tree.get_children())
        s.filtered_data = []
        
        # First, collect matching items
        for idx, rec in enumerate(s.data):
            name = rec['result_item']
            
            # Skip hidden items
            if name in s._hidden_items:
                continue
            
            tags = s._tags.get(name, [])
            if q in name.lower() or any(q in t.lower() for t in tags):
                s.filtered_data.append(rec)
        
        # Sort based on selected method
        sort_method = s.sort_var.get()
        if sort_method == "Alphabetical":
            s.filtered_data.sort(key=lambda x: x['result_item'].lower())
        elif sort_method == "Tags":
            # Sort by number of tags (most tags first), then alphabetically
            s.filtered_data.sort(key=lambda x: (-len(s._tags.get(x['result_item'], [])), 
                                              x['result_item'].lower()))
        
        # Add items to tree with minus prefix
        for filtered_idx, rec in enumerate(s.filtered_data):
            name = rec['result_item']
            # Find original index for icon
            orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), 0)
            # Add bold minus symbol before the name (it will appear after icon due to TreeView behavior)
            # Use a larger minus for visibility
            s.tree.insert('', 'end', iid=str(filtered_idx), text=f"➖ {name}", image=s.small_icons.get(orig_idx))

    def show(s, *_):
        s._save_current()
        sel = s.tree.selection();
        if not sel: return
        idx = int(sel[0]); rec = s.filtered_data[idx]; name = rec['result_item']
        s.selected_item = name
        
        # Find original index for icon
        orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), 0)
        
        icon_path = s.icons.get(name)
        if icon_path and os.path.isfile(icon_path) and Image:
            try:
                im = Image.open(icon_path).resize((128,128), Image.LANCZOS)
                ph = ImageTk.PhotoImage(im); s.ic.config(image=ph); s.ic.image = ph
            except: 
                s.ic.config(image=s._placeholder_red_large())
        else:
            s.ic.config(image=s._placeholder_red_large())
        
        s._build_enhanced_text_display(rec)
        s.image_path.delete(0,'end'); s.link_btn.config(state='disabled')
        s._load_current_notes(name)

    def _build_enhanced_text_display(s, rec):
        # Save cursor position if in edit mode
        cursor_pos = None
        if s.edit_mode:
            cursor_pos = s.txt.index("insert")
        
        s.txt.config(state='normal')
        s.txt.delete('1.0', 'end')
        
        # Get custom edits for this item if they exist
        item_name = rec['result_item']
        custom_data = s._custom_edits.get(item_name, {})
        
        # Merge custom data with original data
        display_rec = rec.copy()
        if custom_data:
            display_rec.update(custom_data)
        
        # Item name
        s.txt.insert('end', display_rec['result_item'], 'item_name')
        s.txt.insert('end', '\n')
        
        # Description if available
        if desc := display_rec.get("description"):
            s.txt.insert('end', desc)
            s.txt.insert('end', '\n\n')
        
        # Skill with icon
        if display_rec.get("skill"):
            s.txt.insert('end', 'Skill: ')
            s._insert_skill_icon(display_rec['skill'])
            s.txt.insert('end', f" {display_rec['skill']} (Lv {display_rec['level']})\n")
        
        # Table with icon
        if table := display_rec.get("crafting_table"):
            s.txt.insert('end', 'Table: ')
            s._insert_table_icon(table)
            s.txt.insert('end', f" {table}\n")
        
        # Ingredients with icons
        if display_rec.get("ingredients"):
            s.txt.insert('end', '\nIngredients:\n')
            for ingredient, quantity in display_rec["ingredients"]:
                s.txt.insert('end', '  • ')
                s._insert_ingredient_icon(ingredient)
                s.txt.insert('end', f" {ingredient} ×{quantity}\n")
        else:
            # For uncraftable items, show appropriate message based on item type
            item_name_lower = display_rec['result_item'].lower()
            
            # Check for animal carcasses
            if 'carcass' in item_name_lower or any(animal in item_name_lower for animal in [
                'fish', 'salmon', 'trout', 'bass', 'tuna', 'crab', 'urchin', 
                'clam', 'otter', 'fox', 'hare', 'deer', 'elk', 'bison', 
                'wolf', 'bear', 'turkey', 'tortoise', 'sheep', 'goat',
                'prairie', 'mountain', 'bighorn', 'alligator', 'jaguar', 'agouti'
            ]):
                s.txt.insert('end', '\nThis animal can only be hunted or fished.\n')
            
            # Check for logs/wood
            elif any(wood in item_name_lower for wood in ['log', 'logs']):
                s.txt.insert('end', '\nCan only be collected by felling trees.\n')
            
            # Check for mining resources
            elif any(ore in item_name_lower for ore in [
                'ore', 'coal', 'stone', 'granite', 'limestone', 'sandstone', 
                'gneiss', 'basalt', 'shale', 'clay', 'sand', 'dirt', 'crushed'
            ]) and 'ashlar' not in item_name_lower:  # Exclude processed stones
                s.txt.insert('end', '\nCan only be collected by mining.\n')
            
            # Check for farming/gathering resources
            elif any(plant in item_name_lower for plant in [
                'seed', 'seeds', 'bulb', 'spores', 'bean', 'beans', 'beet', 
                'corn', 'wheat', 'rice', 'tomato', 'pumpkin', 'cotton', 
                'flax', 'sunflower', 'pineapple', 'papaya', 'taro', 'agave',
                'berry', 'berries', 'huckle', 'mushroom', 'fern', 'moss',
                'kelp', 'camas', 'fireweed', 'lupine', 'saxifrage'
            ]):
                if 'seed' in item_name_lower or 'bulb' in item_name_lower or 'spores' in item_name_lower:
                    s.txt.insert('end', '\nCan be found by gathering or purchased from farmers.\n')
                else:
                    s.txt.insert('end', '\nCan only be collected by gathering or farming.\n')
            
            # Check for natural plant materials
            elif any(material in item_name_lower for plant in [
                'pulp', 'fiber', 'plant', 'palm', 'spruce', 'cactus', 'leaf', 'leaves'
            ]):
                s.txt.insert('end', '\nCan only be collected from plants in the wild.\n')
            
            # Default message for other uncraftable items
            else:
                s.txt.insert('end', '\nThis item cannot be crafted.\n')
        
        # Nutrition information
        if nutrition := display_rec.get("nutrition"):
            s.txt.insert('end', '\n')
            s.txt.insert('end', 'Nutrition Information:\n', 'nutrition_header')
            s.txt.insert('end', '\n')
            
            # Display nutrients in Eco order: Carbs, Protein, Fat, Vitamins
            nutrient_order = [
                ('carbs', 'Carbohydrates'),
                ('protein', 'Protein'),
                ('fat', 'Fat'),
                ('vitamins', 'Vitamins')
            ]
            
            # Display main nutrients with color bars
            has_nutrients = False
            total_nutrients = 0
            for nutrient_key, display_name in nutrient_order:
                if nutrient_key in nutrition and nutrition[nutrient_key] > 0:
                    has_nutrients = True
                    value = nutrition[nutrient_key]
                    total_nutrients += value
                    # Add spacing and the nutrient bar
                    s.txt.insert('end', '  ')
                    s.txt.insert('end', f' {display_name}: {value} ', f'nutrient_{nutrient_key}')
                    s.txt.insert('end', '\n')
            
            # Always show calorie information if we have any nutrition data
            if has_nutrients:
                s.txt.insert('end', '\n')  # Extra line before calories
                s.txt.insert('end', '  ')
                
                # Check if we have explicit calorie data
                if 'calories' in nutrition and nutrition['calories'] > 0:
                    s.txt.insert('end', f' Calories: {nutrition["calories"]} ', 'calorie_count_display')
                else:
                    # Calculate calories from macronutrients
                    # Standard formula: carbs*4 + protein*4 + fat*9
                    calc_calories = (nutrition.get('carbs', 0) * 4 + 
                                   nutrition.get('protein', 0) * 4 + 
                                   nutrition.get('fat', 0) * 9)
                    
                    # If calculated calories are 0 but we have nutrients, use a simple multiplier
                    # (This handles cases where Eco might use different units)
                    if calc_calories == 0 and total_nutrients > 0:
                        # Rough estimate based on total nutrients
                        calc_calories = total_nutrients * 4
                    
                    s.txt.insert('end', f' Calories: {calc_calories} ', 'calorie_count_display')
                
                s.txt.insert('end', '\n')
        
        # Set text state based on edit mode
        if not s.edit_mode:
            s.txt.config(state='disabled')
        else:
            # Restore cursor position
            if cursor_pos:
                s.txt.mark_set("insert", cursor_pos)
                s.txt.see("insert")

    def _insert_skill_icon(s, skill_name):
        skill_icon_path = os.path.join(os.path.dirname(__file__), 'SkillIcons', f"{skill_name}.png")
        if os.path.isfile(skill_icon_path) and Image:
            try:
                skill_img = Image.open(skill_icon_path).resize((32, 32), Image.LANCZOS)
                skill_photo = ImageTk.PhotoImage(skill_img)
                if not hasattr(s, '_skill_icons'):
                    s._skill_icons = {}
                s._skill_icons[skill_name] = skill_photo
                s.txt.image_create('end', image=skill_photo)
            except:
                s.txt.insert('end', '🔵')
        else:
            s.txt.insert('end', '🔵')

    def _insert_table_icon(s, table_name):
        table_icon_path = os.path.join(os.path.dirname(__file__), 'EcoIcons', f"{table_name}.png")
        if os.path.isfile(table_icon_path) and Image:
            try:
                table_img = Image.open(table_icon_path).resize((32, 32), Image.LANCZOS)
                table_photo = ImageTk.PhotoImage(table_img)
                if not hasattr(s, '_table_icons'):
                    s._table_icons = {}
                s._table_icons[table_name] = table_photo
                
                s.txt.image_create('end', image=table_photo)
                
                current_pos = s.txt.index('end-1c')
                s.txt.tag_add(f'table_{table_name}', f'{current_pos}')
                s.txt.tag_bind(f'table_{table_name}', '<Button-1>', 
                              lambda e, item=table_name: s._navigate_to_item(item))
                s.txt.tag_config(f'table_{table_name}', foreground='blue', underline=True)
            except:
                s.txt.insert('end', '🔴')
        else:
            s.txt.insert('end', '🔴')

    def _insert_ingredient_icon(s, ingredient_name):
        ingredient_icon_path = os.path.join(os.path.dirname(__file__), 'EcoIcons', f"{ingredient_name}.png")
        if os.path.isfile(ingredient_icon_path) and Image:
            try:
                ingredient_img = Image.open(ingredient_icon_path).resize((32, 32), Image.LANCZOS)
                ingredient_photo = ImageTk.PhotoImage(ingredient_img)
                if not hasattr(s, '_ingredient_icons'):
                    s._ingredient_icons = {}
                s._ingredient_icons[ingredient_name] = ingredient_photo
                
                s.txt.image_create('end', image=ingredient_photo)
                
                current_pos = s.txt.index('end-1c')
                s.txt.tag_add(f'ingredient_{ingredient_name}', f'{current_pos}')
                s.txt.tag_bind(f'ingredient_{ingredient_name}', '<Button-1>', 
                              lambda e, item=ingredient_name: s._navigate_to_item(item))
                s.txt.tag_config(f'ingredient_{ingredient_name}', foreground='blue', underline=True)
            except:
                s.txt.insert('end', '🔴')
        else:
            s.txt.insert('end', '🔴')

    def _navigate_to_item(s, item_name):
        for idx, rec in enumerate(s.filtered_data):
            if rec['result_item'].lower() == item_name.lower():
                s.tree.selection_set(str(idx))
                s.tree.see(str(idx))
                s.show()
                return
        
        messagebox.showinfo("Item Not Found", f"'{item_name}' was not found in the current data.")

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
        s._update_tags_display(item)
        
        all_tags = sorted({t for lst in s._tags.values() for t in lst})
        s.tag_dropdown['values'] = all_tags

    def _update_tags_display(s, item):
        for widget in s.tags_display_frame.winfo_children():
            widget.destroy()
        
        tags = s._tags.get(item, [])
        tag_icons_dir = os.path.join(os.path.dirname(__file__), 'TagIcons')
        x_icon_path = os.path.join(os.path.dirname(__file__), 'X.png')
        
        x_icon = None
        if os.path.isfile(x_icon_path) and Image:
            try:
                x_img = Image.open(x_icon_path).resize((24, 24), Image.LANCZOS)
                x_icon = ImageTk.PhotoImage(x_img)
            except:
                pass
        
        for tag in tags:
            tag_frame = tk.Frame(s.tags_display_frame)
            tag_frame.pack(fill='x', pady=1)
            
            # X button for removal using AppIcons/X.png
            x_icon = None
            x_icon_path = os.path.join(os.path.dirname(__file__), 'AppIcons', 'X.png')
            if os.path.isfile(x_icon_path) and Image:
                try:
                    x_img = Image.open(x_icon_path).resize((24, 24), Image.LANCZOS)
                    x_icon = ImageTk.PhotoImage(x_img)
                except:
                    pass
            
            if x_icon:
                x_btn = tk.Label(tag_frame, image=x_icon, cursor='hand2')
                x_btn.image = x_icon
            else:
                x_btn = tk.Label(tag_frame, text='X', fg='red', cursor='hand2', width=2)
            x_btn.pack(side='left', padx=(0, 2))
            x_btn.bind('<Button-1>', lambda e, t=tag: s._remove_tag_with_confirmation(t))
            
            tag_icon_path = os.path.join(tag_icons_dir, f"{tag}.png")
            if os.path.isfile(tag_icon_path) and Image:
                try:
                    tag_img = Image.open(tag_icon_path).resize((32, 32), Image.LANCZOS)
                    tag_photo = ImageTk.PhotoImage(tag_img)
                    tag_label = tk.Label(tag_frame, image=tag_photo)
                    tag_label.image = tag_photo
                except:
                    tag_label = tk.Label(tag_frame, bg='blue', width=4, height=2)
            else:
                tag_label = tk.Label(tag_frame, bg='blue', width=4, height=2)
            
            tag_label.pack(side='left', padx=(0, 5))
            tk.Label(tag_frame, text=tag, font=s.ui_font).pack(side='left')

    def _clear_fill_tag_placeholder(s, event):
        if s.fill_tag_entry.get() == "Fill Tag":
            s.fill_tag_entry.delete(0, tk.END)
            s.fill_tag_entry.config(fg='black')

    def _restore_fill_tag_placeholder(s, event):
        if not s.fill_tag_entry.get():
            s.fill_tag_entry.insert(0, "Fill Tag")
            s.fill_tag_entry.config(fg='gray')

    def _add_tag(s):
        if not s.selected_item:
            return
        
        fill_tag = s.fill_tag_entry.get().strip()
        dropdown_tag = s.tag_var.get().strip()
        
        tag = ""
        if fill_tag and fill_tag != "Fill Tag":
            tag = fill_tag
        elif dropdown_tag and dropdown_tag != "Tag Dropdown":
            tag = dropdown_tag
        
        if not tag:
            return
        
        if s.selected_item not in s._tags:
            s._tags[s.selected_item] = []
        
        if tag not in s._tags[s.selected_item]:
            s._tags[s.selected_item].append(tag)
            s._save_current()
            s._update_tags_display(s.selected_item)
            
            s.fill_tag_entry.delete(0, tk.END)
            s.fill_tag_entry.insert(0, "Fill Tag")
            s.fill_tag_entry.config(fg='gray')
            
            s.tag_var.set("Tag Dropdown")

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

    def export(s):
        if not s.data: messagebox.showwarning("Nothing","Parse first."); return
        # Export only non-hidden items
        export_data = [rec for rec in s.data if rec['result_item'] not in s._hidden_items]
        fn = os.path.join(s.folder.get(),"eco_recipes.json")
        with open(fn,'w',encoding='utf-8') as f: json.dump(export_data,f,indent=2)
        messagebox.showinfo("Exported",f"Recipes exported to {fn}.\n(Excluded {len(s._hidden_items)} hidden items)")

    def _check_image_path_valid(s,*_):
        ok = os.path.isfile(s.image_path.get()) and s.image_path.get().lower().endswith('.png')
        s.link_btn.config(state='normal' if ok else 'disabled')

    def _link_image(s):
        sel = s.tree.selection();
        if not sel: return
        idx=int(sel[0]); name=s.filtered_data[idx]['result_item']
        ico_dir=os.path.join(os.path.dirname(__file__),'EcoIcons'); os.makedirs(ico_dir,exist_ok=True)
        dest=os.path.join(ico_dir,f"{name}.png"); shutil.copy(s.image_path.get(),dest)
        s.icons[name]=dest; 
        # Find original index
        orig_idx = next((i for i, r in enumerate(s.data) if r['result_item'] == name), 0)
        s.small_icons.pop(orig_idx,None); s.large_icons.pop(name,None)
        messagebox.showinfo("Image Linked",f"Image linked to {name}."); s.show()

    def _placeholder_red_small(s):
        if not hasattr(s,'_red_small') and Image:
            im=Image.new('RGBA',(24,24),(255,0,0,255)); s._red_small=ImageTk.PhotoImage(im)
        return s._red_small

    def _placeholder_red_large(s):
        if not hasattr(s,'_red_large') and Image:
            im=Image.new('RGBA',(128,128),(255,0,0,255)); s._red_large=ImageTk.PhotoImage(im)
        return s._red_large

    def _on_close(s):
        s._save_current(); s.r.destroy()

    def _on_text_edit(s, event=None):
        """Handle text edits in the main display"""
        if not s.selected_item or not s.edit_mode:
            return
        
        # Get the current text content
        current_text = s.txt.get('1.0', 'end-1c')
        
        # Parse the edited text back into structured data
        edited_data = s._parse_edited_text(current_text)
        
        if edited_data:
            # Store the edits
            s._custom_edits[s.selected_item] = edited_data
            s._save_custom_edits()
            
            # Show save indicator
            s.save_indicator.config(text='✓ Saved')
            s.root.after(2000, lambda: s.save_indicator.config(text=''))
    
    def _parse_edited_text(s, text):
        """Parse the edited text back into structured data"""
        lines = text.strip().split('\n')
        if not lines:
            return None
        
        data = {}
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Item name (first line)
            if i == 0:
                continue  # Don't allow editing item name
            
            # Description (second non-empty line if no skill/table info)
            if i == 1 and not any(marker in line for marker in ['Skill:', 'Table:', 'Ingredients:']):
                data['description'] = line
            
            # Skill line
            if line.startswith('Skill:'):
                skill_match = re.search(r'Skill:\s*(?:.*?)(\w+)\s*\(Lv\s*(\d+)\)', line)
                if skill_match:
                    data['skill'] = skill_match.group(1)
                    data['level'] = int(skill_match.group(2))
            
            # Table line
            elif line.startswith('Table:'):
                table_match = re.search(r'Table:\s*(?:.*?)(\w+)', line)
                if table_match:
                    data['crafting_table'] = table_match.group(1)
            
            # Ingredients section
            elif line == 'Ingredients:':
                current_section = 'ingredients'
                data['ingredients'] = []
            
            # Ingredient line
            elif current_section == 'ingredients' and line.startswith('•'):
                ing_match = re.search(r'•\s*(?:.*?)(\w+)\s*×(\d+)', line)
                if ing_match:
                    data['ingredients'].append([ing_match.group(1), int(ing_match.group(2))])
            
            # Nutrition section
            elif line == 'Nutrition Information:':
                current_section = 'nutrition'
                data['nutrition'] = {}
            
            # Nutrition values
            elif current_section == 'nutrition':
                # Parse nutrition bars
                if 'Carbohydrates:' in line:
                    carb_match = re.search(r'Carbohydrates:\s*(\d+)', line)
                    if carb_match:
                        if 'nutrition' not in data:
                            data['nutrition'] = {}
                        data['nutrition']['carbs'] = int(carb_match.group(1))
                elif 'Protein:' in line:
                    prot_match = re.search(r'Protein:\s*(\d+)', line)
                    if prot_match:
                        if 'nutrition' not in data:
                            data['nutrition'] = {}
                        data['nutrition']['protein'] = int(prot_match.group(1))
                elif 'Fat:' in line:
                    fat_match = re.search(r'Fat:\s*(\d+)', line)
                    if fat_match:
                        if 'nutrition' not in data:
                            data['nutrition'] = {}
                        data['nutrition']['fat'] = int(fat_match.group(1))
                elif 'Vitamins:' in line:
                    vit_match = re.search(r'Vitamins:\s*(\d+)', line)
                    if vit_match:
                        if 'nutrition' not in data:
                            data['nutrition'] = {}
                        data['nutrition']['vitamins'] = int(vit_match.group(1))
                elif 'Calories:' in line:
                    cal_match = re.search(r'Calories:\s*(\d+)', line)
                    if cal_match:
                        if 'nutrition' not in data:
                            data['nutrition'] = {}
                        data['nutrition']['calories'] = int(cal_match.group(1))
        
        return data
    
    def _save_custom_edits(s):
        """Save custom edits to file"""
        with open(s.custom_edits_file, 'w', encoding='utf-8') as f:
            json.dump(s._custom_edits, f, indent=2)
    
    def export_custom_data(s):
        """Export custom data that can be shared with others"""
        if not s._custom_edits:
            messagebox.showinfo("No Custom Data", "No custom edits have been made yet.")
            return
        
        # Ask where to save
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="eco_custom_data.json"
        )
        
        if filename:
            # Create a comprehensive export with metadata
            export_data = {
                "version": "1.0",
                "export_date": datetime.now().isoformat(),
                "item_count": len(s._custom_edits),
                "custom_edits": s._custom_edits,
                "tags": s._tags,  # Include tags as well
                "notes": s._notes  # Include notes too
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2)
            
            messagebox.showinfo("Export Complete", 
                              f"Custom data exported to:\n{filename}\n\n"
                              f"This file contains {len(s._custom_edits)} edited items "
                              f"and can be shared with others!")
    
    def import_custom_data(s):
        """Import custom data from a file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="eco_custom_data.json"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Check if it's a valid custom data file
            if 'custom_edits' not in import_data:
                messagebox.showerror("Invalid File", "This doesn't appear to be a valid custom data file.")
                return
            
            # Ask user what to do with existing data
            if s._custom_edits:
                result = messagebox.askyesnocancel(
                    "Import Custom Data",
                    "You have existing custom edits.\n\n"
                    "Yes - Merge with existing data (keep both)\n"
                    "No - Replace existing data\n"
                    "Cancel - Cancel import"
                )
                
                if result is None:  # Cancel
                    return
                elif result:  # Yes - Merge
                    # Merge the data
                    for item, data in import_data['custom_edits'].items():
                        s._custom_edits[item] = data
                    
                    # Merge tags if present
                    if 'tags' in import_data:
                        for item, tags in import_data['tags'].items():
                            if item in s._tags:
                                # Merge tags, avoiding duplicates
                                s._tags[item] = list(set(s._tags[item] + tags))
                            else:
                                s._tags[item] = tags
                    
                    # Merge notes if present
                    if 'notes' in import_data:
                        for item, note in import_data['notes'].items():
                            if item not in s._notes or not s._notes[item]:
                                s._notes[item] = note
                else:  # No - Replace
                    s._custom_edits = import_data['custom_edits']
                    if 'tags' in import_data:
                        s._tags = import_data['tags']
                    if 'notes' in import_data:
                        s._notes = import_data['notes']
            else:
                # No existing data, just import
                s._custom_edits = import_data['custom_edits']
                if 'tags' in import_data:
                    s._tags = import_data['tags']
                if 'notes' in import_data:
                    s._notes = import_data['notes']
            
            # Save all imported data
            s._save_custom_edits()
            s._save_current()
            
            # Refresh display if an item is selected
            if s.selected_item:
                sel = s.tree.selection()
                if sel:
                    s.show()
            
            item_count = len(import_data['custom_edits'])
            messagebox.showinfo("Import Complete", 
                              f"Successfully imported custom data!\n\n"
                              f"Items with custom edits: {item_count}\n"
                              f"From: {os.path.basename(filename)}")
            
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import custom data:\n{str(e)}")
    
    def toggle_edit_mode(s):
        """Toggle between edit and read-only mode"""
        s.edit_mode = not s.edit_mode
        
        if s.edit_mode:
            # Enable editing
            s.txt.config(state='normal')
            s.edit_button.config(bg='yellow', relief='sunken')
            s.save_indicator.config(text='📝 Edit Mode', fg='orange')
        else:
            # Disable editing
            s.txt.config(state='disabled')
            s.edit_button.config(bg='SystemButtonFace', relief='raised')
            s.save_indicator.config(text='')
    
    def _animate_pencil(s):
        """Animate the pencil icon rotation"""
        if not s.pencil_icon or not hasattr(s, 'pencil_label'):
            return
        
        # Update angle
        s.pencil_angle += s.pencil_direction * 0.5
        
        # Reverse direction at limits
        if s.pencil_angle >= 9:
            s.pencil_angle = 9
            s.pencil_direction = -1
        elif s.pencil_angle <= -9:
            s.pencil_angle = -9
            s.pencil_direction = 1
        
        # Only animate if in edit mode
        if s.edit_mode:
            try:
                # Rotate the pencil image
                rotated = s.pencil_icon.rotate(s.pencil_angle, expand=False, fillcolor=None)
                s.pencil_photo = ImageTk.PhotoImage(rotated)
                s.pencil_label.config(image=s.pencil_photo)
            except:
                pass
        else:
            # Reset to original position when not editing
            if s.pencil_angle != 0:
                s.pencil_angle = 0
                try:
                    s.pencil_photo = ImageTk.PhotoImage(s.pencil_icon)
                    s.pencil_label.config(image=s.pencil_photo)
                except:
                    pass
        
        # Schedule next frame (50ms = 20fps)
        s.root.after(50, s._animate_pencil)

if __name__ == "__main__":
    root=tk.Tk(); GUI(root); root.mainloop()
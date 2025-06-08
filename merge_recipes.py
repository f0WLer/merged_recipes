import os
import sys
import zipfile
import json
import re
from collections import defaultdict

# Define the modid whitelist here
MODID_WHITELIST = {
    "minecraft",  # always include vanilla
    "create",
    "mekanism",
    "immersiveengineering",
    "modern_industrialization",
    "minecolonies",
    # add more modids as needed
}


def detect_modid_from_toml(toml_content):
    # Attempt to extract modid from mods.toml content (simple regex)
    match = re.search(r'id\s*=\s*"([^"]+)"', toml_content)
    if match:
        return match.group(1)
    return None

def get_modid_from_jar(jar_path):
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            # Check for mods.toml or neoforge.mods.toml
            for toml_path in ['META-INF/mods.toml', 'META-INF/neoforge.mods.toml']:
                try:
                    with z.open(toml_path) as f:
                        content = f.read().decode('utf-8')
                        modid = detect_modid_from_toml(content)
                        if modid:
                            return modid
                except KeyError:
                    continue
        # fallback: modid = jar filename before first dash or underscore
        filename = os.path.basename(jar_path)
        fallback_modid = re.split(r'[-_]', filename)[0]
        return fallback_modid.lower()
    except Exception as e:
        print(f"Warning: Could not get modid for {jar_path}: {e}")
        return None

def get_all_recipe_files(zip_file, modid):
    # Return list of all recipe JSON paths in zip under data/<modid>/recipes/ and data/<modid>/recipe/ recursively
    candidates = []
    prefixes = [f"data/{modid}/recipes/", f"data/{modid}/recipe/"]
    for f in zip_file.namelist():
        if any(f.startswith(prefix) for prefix in prefixes) and f.endswith('.json'):
            candidates.append(f)
    return candidates

def extract_output_ids(recipe_json):
    outputs = []

    # Handle standard Minecraft crafting result
    if 'result' in recipe_json and isinstance(recipe_json['result'], dict):
        rid = recipe_json['result'].get('id') or recipe_json['result'].get('item')
        if rid:
            outputs.append(rid)

    # Create-style multi-output format
    elif 'results' in recipe_json and isinstance(recipe_json['results'], list):
        for r in recipe_json['results']:
            rid = r.get('id') or r.get('item')
            if rid:
                outputs.append(rid)

    elif 'output' in recipe_json:
        output = recipe_json['output']
        if isinstance(output, dict):
            rid = output.get('id') or output.get('item')
            if rid:
                outputs.append(rid)
        elif isinstance(output, str):
            outputs.append(output)

    elif 'outputs' in recipe_json:
        for out in recipe_json['outputs']:
            if isinstance(out, dict):
                rid = out.get('id') or out.get('item')
                if rid:
                    outputs.append(rid)
            elif isinstance(out, str):
                outputs.append(out)

    # Deduplicate & ensure strings
    return list(set(o for o in outputs if isinstance(o, str)))


def extract_recipes_from_zip(jar_path, modid_filter=None):
    recipes = {}
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            modid = get_modid_from_jar(jar_path)
            if not modid:
                print(f"Could not detect modid for jar {jar_path}")
                return recipes
            if modid not in MODID_WHITELIST:
                print(f"Skipping mod '{modid}' (not in whitelist)")
                return recipes
            print(f"Extracting recipes from mod jar '{os.path.basename(jar_path)}' modid(s): {modid}")

            recipe_files = get_all_recipe_files(z, modid)
            for rf in recipe_files:
                try:
                    with z.open(rf) as f:
                        recipe_json = json.load(f)
                except Exception as e:
                    print(f"Error reading recipe {rf} in {jar_path}: {e}")
                    continue
                output_ids = extract_output_ids(recipe_json)
                if not output_ids:
                    # Some recipes don't have outputs or are weird; skip
                    continue
                for out_id in output_ids:
                    # Avoid unhashable dict keys, make sure out_id is string
                    if isinstance(out_id, dict):
                        continue
                    # Store the full recipe json keyed by output id
                    # If multiple recipes produce same output, store as list
                    if out_id not in recipes:
                        recipes[out_id] = []
                    recipes[out_id].append(recipe_json)
    except Exception as e:
        print(f"Error opening jar {jar_path}: {e}")
    return recipes

def extract_vanilla_recipes_from_jar(jar_path):
    recipes = {}
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            prefix = "data/minecraft/recipes/"
            recipe_files = [f for f in z.namelist() if f.startswith(prefix) and f.endswith('.json')]
            print(f"Extracting vanilla recipes from {len(recipe_files)} files")
            for rf in recipe_files:
                try:
                    with z.open(rf) as f:
                        recipe_json = json.load(f)
                except Exception as e:
                    print(f"Error reading vanilla recipe {rf}: {e}")
                    continue
                output_ids = extract_output_ids(recipe_json)
                if not output_ids:
                    continue
                for out_id in output_ids:
                    if isinstance(out_id, dict):
                        continue
                    if out_id not in recipes:
                        recipes[out_id] = []
                    recipes[out_id].append(recipe_json)
    except Exception as e:
        print(f"Error opening vanilla jar {jar_path}: {e}")
    return recipes

def merge_recipe_dicts(dicts):
    merged = defaultdict(list)
    for d in dicts:
        for k, v in d.items():
            merged[k].extend(v)
    return dict(merged)

def main():
    if len(sys.argv) != 3:
        print("Usage: python merge_recipes.py <mods_folder_path> <minecraft_jar_path>")
        return

    mods_folder = sys.argv[1]
    minecraft_jar_path = sys.argv[2]

    all_mod_recipes = []
    mod_jars = [os.path.join(mods_folder, f) for f in os.listdir(mods_folder) if f.endswith('.jar')]

    print(f"Found {len(mod_jars)} mod jars to process...")

    for jar_path in mod_jars:
        mod_recipes = extract_recipes_from_zip(jar_path)
        if mod_recipes:
            all_mod_recipes.append(mod_recipes)

    vanilla_recipes = extract_vanilla_recipes_from_jar(minecraft_jar_path)
    if vanilla_recipes:
        all_mod_recipes.append(vanilla_recipes)

    merged = merge_recipe_dicts(all_mod_recipes)
    print(f"Total unique output items with recipes collected: {len(merged)}")

    out_path = "merged_recipes.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2)

    print(f"Saved merged recipes to {out_path}")

if __name__ == "__main__":
    main()

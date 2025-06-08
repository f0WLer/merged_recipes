import os
import zipfile
import json
from collections import OrderedDict

# 🧱 List of mod namespaces to include (filter recipes by mod)
WHITELIST_MODS = {
    "modern_industrialization",
    "ae2",
    "minecraft",  # Optional: include vanilla recipes
    "thermal",    # Add others as needed
    "create",
    "mekanism",
    "minecolonies",
    # "botania", "immersiveengineering", etc.
}

def merge_recipes(mods_path, output_file):
    merged_recipes = OrderedDict()
    jar_files = []

    # Find all .jar files in the mods folder
    for root, _, files in os.walk(mods_path):
        for f in files:
            if f.endswith(".jar"):
                jar_files.append(os.path.join(root, f))

    jar_files.sort()
    print(f"Found {len(jar_files)} mod jars.")

    for jar_path in jar_files:
        print(f"Processing {os.path.basename(jar_path)}...")
        try:
            with zipfile.ZipFile(jar_path, 'r') as jar:
                recipe_files = [f for f in jar.namelist() if f.startswith("data/") and "/recipes/" in f and f.endswith(".json")]

                for rf in recipe_files:
                    try:
                        parts = rf.split('/')
                        if len(parts) < 4:
                            continue  # not a proper recipe path

                        namespace = parts[1]
                        if namespace not in WHITELIST_MODS:
                            continue  # skip unwanted mods

                        recipe_id = f"{namespace}:{'/'.join(parts[3:])}".replace(".json", "")
                        with jar.open(rf) as file:
                            recipe_json = json.load(file)
                            merged_recipes[recipe_id] = recipe_json

                    except Exception as e:
                        print(f"  Failed to load recipe {rf}: {e}")

        except zipfile.BadZipFile:
            print(f"Warning: {jar_path} is not a valid zip file, skipping.")

    with open(output_file, 'w', encoding='utf-8') as out_file:
        json.dump(merged_recipes, out_file, indent=2, ensure_ascii=False)

    print(f"\n✅ Merged {len(merged_recipes)} recipes saved to {output_file}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Merge selected Minecraft modpack recipes into a single JSON.")
    parser.add_argument("mods_folder", help="Path to mods folder (with .jar files)")
    parser.add_argument("output_file", help="Path to output JSON file")

    args = parser.parse_args()
    merge_recipes(args.mods_folder, args.output_file)

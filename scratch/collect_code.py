import os

def collect_code():
    project_root = "D:\\Project\\eIdarati_multiAgent_langraph"
    output_file = os.path.join(project_root, "all.txt")
    
    exclude_dirs = {".git", ".venv", "__pycache__", ".langgraph_api"}
    exclude_files = {"all.txt", "idarati.db", "architecture.png", ".env"}
    exclude_extensions = {".pckl", ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico"}

    with open(output_file, "w", encoding="utf-8") as f_out:
        for root, dirs, files in os.walk(project_root):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files:
                    continue
                if any(file.endswith(ext) for ext in exclude_extensions):
                    continue
                
                rel_path = os.path.relpath(os.path.join(root, file), project_root)
                f_out.write(f"\n{'='*80}\n")
                f_out.write(f"FILE: {rel_path}\n")
                f_out.write(f"{'='*80}\n\n")
                
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f_in:
                        f_out.write(f_in.read())
                except Exception as e:
                    f_out.write(f"ERROR READING FILE: {str(e)}\n")
                
                f_out.write("\n")

if __name__ == "__main__":
    collect_code()
    print("Code collection complete. Updated all.txt.")

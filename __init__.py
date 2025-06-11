# import os
#
# def print_tree(start_path, exclude_dirs=[".git", "__pycache__"], indent=""):
#     for item in os.listdir(start_path):
#         if item in exclude_dirs:
#             continue
#         path = os.path.join(start_path, item)
#         if os.path.isdir(path):
#             print(f"{indent}├── {item}/")
#             print_tree(path, exclude_dirs, indent + "    ")
#         else:
#             print(f"{indent}├── {item}")
#
# if __name__ == "__main__":
#     print("BroadcastRecorder_dev/")
#     print_tree(".", exclude_dirs=[".git", "__pycache__", ".idea", "media", "node_modules", "venv", ".gitignore", ".txt"], indent="")

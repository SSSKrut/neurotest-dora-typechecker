# Made by DeepSeek
import ast
import sys
import os
from typing import List, Tuple, Optional, Dict

class TypeFinder(ast.NodeVisitor):
    def __init__(self, target_type: Optional[str] = None):
        self.target_type = target_type
        self.results = []

    def visit_Name(self, node: ast.Name):
        if self.target_type is None or node.id == self.target_type:
            self.results.append((node.lineno, node.col_offset, node.id, 'NameExpr'))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if self.target_type is None or node.func.id == self.target_type:
                self.results.append((node.lineno, node.col_offset, node.func.id, 'CallExpr'))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if isinstance(node.value, ast.Name):
            full_name = f"{node.value.id}.{node.attr}"
            if self.target_type is None or full_name == self.target_type:
                self.results.append((node.lineno, node.col_offset, full_name, 'AttributeExpr'))
        self.generic_visit(node)

def dora(filename: str, target_type: Optional[str] = None, visited_files: Optional[set] = None, import_map: Optional[Dict[str, str]] = None) -> List[Tuple[int, int, str, str, str]]:
    if visited_files is None:
        visited_files = set()
    if import_map is None:
        import_map = {}

    if filename in visited_files:
        return []

    visited_files.add(filename)

    with open(filename, 'r') as file:
        content = file.read()

    tree = ast.parse(content)
    finder = TypeFinder(target_type)
    finder.visit(tree)

    results = []
    for lineno, col_offset, type_name, expr_type in finder.results:
        source_file = import_map.get(type_name, filename)
        results.append((lineno, col_offset, type_name, expr_type, source_file))

    # Parse imports and analyze imported files
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_map[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            for alias in node.names:
                imported_name = alias.name
                if module:
                    full_imported_name = f"{module}.{imported_name}"
                else:
                    full_imported_name = imported_name
                import_map[alias.asname or imported_name] = full_imported_name

                if target_type is None or full_imported_name == target_type:
                    imported_file = resolve_import(filename, full_imported_name)
                    if imported_file:
                        imported_results = dora(imported_file, target_type, visited_files, import_map)
                        results.extend(imported_results)

    return results

def resolve_import(current_file: str, import_name: str) -> Optional[str]:
    # Simple heuristic to resolve imports based on the current file's directory
    current_dir = os.path.dirname(current_file)
    potential_file = os.path.join(current_dir, f"{import_name.replace('.', os.sep)}.py")
    if os.path.exists(potential_file):
        return potential_file
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: dora <filename> [-t <type>]")
        sys.exit(1)

    filename = sys.argv[1]
    target_type = None

    if '-t' in sys.argv:
        target_type_index = sys.argv.index('-t') + 1
        if target_type_index < len(sys.argv):
            target_type = sys.argv[target_type_index]

    if not os.path.exists(filename):
        print(f"File '{filename}' not found.")
        sys.exit(1)

    results = dora(filename, target_type)
    for lineno, col_offset, type_name, expr_type, source_file in results:
        print(f"{filename}:{lineno}:{col_offset}")
        print(f"      {type_name} ({expr_type}, {type_name} from \"{source_file}\")")
        print(f"      v")
        with open(filename, 'r') as file:
            lines = file.readlines()
            print(lines[lineno - 1].rstrip())
        print()

if __name__ == "__main__":
    main()
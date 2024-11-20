# Made by Claude 3.5
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
import ast
from dataclasses import dataclass

@dataclass
class TypeLocation:
    file: Path
    line: int
    column: int
    type_name: str
    expr_kind: str
    source_line: str = None  # Added field
    source_file: str = None

class TypeVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, source_lines: List[str]):
        self.file_path = file_path
        self.locations: List[TypeLocation] = []
        self.source_lines = source_lines
        
    def visit_AnnAssign(self, node: ast.AnnAssign):
        if isinstance(node.annotation, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=node.lineno,
                column=node.col_offset,
                type_name=node.annotation.id,
                expr_kind="TypeAnnotation",
                source_line=self.source_lines[node.lineno - 1].strip()
            ))
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        self.locations.append(TypeLocation(
            file=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            type_name=node.name,
            expr_kind="ClassDef",
            source_line=self.source_lines[node.lineno - 1].strip()
        ))
        self.generic_visit(node)
        
    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=node.lineno,
                column=node.col_offset,
                type_name=node.func.id,
                expr_kind="Call",
                source_line=self.source_lines[node.lineno - 1].strip()
            ))
        self.generic_visit(node)
        
class ImportTracker:
    def __init__(self):
        self.imports: Dict[str, str] = {}
        
    def analyze_imports(self, file_path: Path) -> None:
        with open(file_path) as f:
            tree = ast.parse(f.read())
            
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Handle from-imports (from module import name)
                if node.module:
                    module_parts = node.module.split('.')
                    module_path = Path(file_path).parent
                    for part in module_parts:
                        module_path = module_path / part
                    module_path = module_path.with_suffix('.py')
                    
                    for name in node.names:
                        self.imports[name.name] = str(module_path)
                        
            elif isinstance(node, ast.Import):
                # Handle direct imports (import module)
                for name in node.names:
                    module_parts = name.name.split('.')
                    module_path = Path(file_path).parent
                    for part in module_parts:
                        module_path = module_path / part
                    module_path = module_path.with_suffix('.py')
                    self.imports[name.name] = str(module_path)

class TypeAnalyzer:
    def __init__(self):
        self.import_tracker = ImportTracker()
        self.analyzed_files: Set[Path] = set()
        self.locations: List[TypeLocation] = []

    def analyze_file(self, file_path: Path, type_pattern: str = None) -> List[TypeLocation]:
        if file_path in self.analyzed_files:
            return self.locations
            
        self.analyzed_files.add(file_path)
        self.import_tracker.analyze_imports(file_path)

        with open(file_path) as f:
            source = f.read()
            source_lines = source.splitlines()
            tree = ast.parse(source)
            
        visitor = TypeVisitor(file_path, source_lines)
        visitor.visit(tree)
        
        for location in visitor.locations:
            type_name = location.type_name
            if type_name in self.import_tracker.imports:
                location.source_file = self.import_tracker.imports[type_name]
                
            if type_pattern is None or type_pattern in type_name:
                self.locations.append(location)
                if location.source_file:
                    self.analyze_file(Path(location.source_file), type_pattern)
                    
        return self.locations

def format_location(loc: TypeLocation) -> str:
    source_info = f" from \"{loc.source_file}\"" if loc.source_file else ""
    return (f"{loc.file}:{loc.line}:{loc.column}\n"
            f"      {loc.type_name} ({loc.expr_kind}{source_info})\n"
            f"      v\n"
            f"{loc.source_line}\n")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Python type search engine")
    parser.add_argument("file", help="File to analyze")
    parser.add_argument("-t", "--type", help="Type pattern to search for")
    args = parser.parse_args()

    analyzer = TypeAnalyzer()
    locations = analyzer.analyze_file(Path(args.file), args.type)
    
    for loc in locations:
        print(format_location(loc))

if __name__ == "__main__":
    main()
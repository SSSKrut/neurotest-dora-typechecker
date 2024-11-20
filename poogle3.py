# Made by Claude 3.5
from typing import Dict, List, Set, Tuple, Optional, Any
from pathlib import Path
import ast
from dataclasses import dataclass
import os
import re

class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


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

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Handle function arguments
        for arg in node.args.args:
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    self.locations.append(TypeLocation(
                        file=self.file_path,
                        line=node.lineno,
                        column=arg.col_offset,
                        type_name=arg.annotation.id,
                        expr_kind="NameExpr",
                        source_line=self.source_lines[node.lineno - 1].strip()
                    ))
                elif isinstance(arg.annotation, ast.Subscript):
                    # Handle subscript types like List[str]
                    self._handle_subscript(arg.annotation, node.lineno)

        # Handle return type
        if node.returns:
            if isinstance(node.returns, ast.Name):
                self.locations.append(TypeLocation(
                    file=self.file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    type_name=node.returns.id,
                    expr_kind="NameExpr",
                    source_line=self.source_lines[node.lineno - 1].strip()
                ))
            elif isinstance(node.returns, ast.Subscript):
                self._handle_subscript(node.returns, node.lineno)

        self.generic_visit(node)

    def _handle_subscript(self, node: ast.Subscript, lineno: int):
        # Handle the main type (e.g., List or Optional)
        if isinstance(node.value, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=lineno,
                column=node.col_offset,
                type_name=node.value.id,
                expr_kind="NameExpr",
                source_line=self.source_lines[lineno - 1].strip()
            ))
        
        # Handle the subscript type (e.g., str in List[str])
        if isinstance(node.slice, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=lineno,
                column=node.slice.col_offset if hasattr(node.slice, 'col_offset') else node.col_offset,
                type_name=node.slice.id,
                expr_kind="NameExpr",
                source_line=self.source_lines[lineno - 1].strip()
            ))
        
        # Record the full type expression
        full_type = f"{node.value.id}[{node.slice.id}]"
        self.locations.append(TypeLocation(
            file=self.file_path,
            line=lineno,
            column=node.col_offset,
            type_name=full_type,
            expr_kind="SubscriptExpr",
            source_line=self.source_lines[lineno - 1].strip()
        ))

    def visit_Name(self, node: ast.Name):
        self.locations.append(TypeLocation(
            file=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            type_name=node.id,
            expr_kind="NameExpr",
            source_line=self.source_lines[node.lineno - 1].strip()
        ))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=node.lineno,
                column=node.col_offset,
                type_name=f'"{node.value}"',
                expr_kind="strExpr",
                source_line=self.source_lines[node.lineno - 1].strip()
            ))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        # Handle variable name
        if isinstance(node.target, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=node.lineno,
                column=node.target.col_offset,
                type_name=node.target.id,
                expr_kind="NameExpr",
                source_line=self.source_lines[node.lineno - 1].strip()
            ))

        # Handle type annotation
        if isinstance(node.annotation, ast.Name):
            self.locations.append(TypeLocation(
                file=self.file_path,
                line=node.lineno,
                column=node.annotation.col_offset,
                type_name=node.annotation.id,
                expr_kind="NameExpr",
                source_line=self.source_lines[node.lineno - 1].strip()
            ))
        elif isinstance(node.annotation, ast.Subscript):
            self._handle_subscript(node.annotation, node.lineno)

        # Handle value if present
        if node.value:
            self.visit(node.value)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Handle variable names
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.locations.append(TypeLocation(
                    file=self.file_path,
                    line=node.lineno,
                    column=target.col_offset,
                    type_name=target.id,
                    expr_kind="NameExpr",
                    source_line=self.source_lines[node.lineno - 1].strip()
                ))
        
        # Handle value
        self.visit(node.value)
        self.generic_visit(node)

class ImportTracker:
    BUILTIN_MODULES = {
        'typing', 'collections', 'datetime', 'os', 'sys', 'pathlib',
        'json', 're', 'math', 'random', 'time', 'itertools', 'functools'
    }

    def __init__(self):
        self.imports: Dict[str, str] = {}
        
    def analyze_imports(self, file_path: Path) -> None:
        with open(file_path) as f:
            tree = ast.parse(f.read())
            
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                # Skip built-in modules
                if node.module in self.BUILTIN_MODULES:
                    continue
                    
                if node.module:
                    module_parts = node.module.split('.')
                    module_path = Path(file_path).parent
                    for part in module_parts:
                        module_path = module_path / part
                    module_path = module_path.with_suffix('.py')
                    
                    for name in node.names:
                        self.imports[name.name] = str(module_path)
                        
            elif isinstance(node, ast.Import):
                for name in node.names:
                    # Skip built-in modules
                    if name.name in self.BUILTIN_MODULES:
                        continue
                        
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


def supports_color() -> bool:
    """Check if the terminal supports colors"""
    if os.getenv('TERM') is None:
        return False
    return os.isatty(1)  # 1 is stdout

def format_location(loc: TypeLocation) -> str:
    # Get the line indent level
    indent = len(loc.source_line) - len(loc.source_line.lstrip())
    pointer_indent = " " * (loc.column + indent)
    
    # Calculate type description indent to match the first character
    type_indent = " " * loc.column
    
    source_info = f" from \"{loc.source_file}\"" if loc.source_file else ""
    
    if supports_color():
        return (
            f"{Colors.BLUE}{loc.file}:{loc.line}:{loc.column}{Colors.END}\n"
            f"{type_indent}{Colors.YELLOW}{loc.type_name}{Colors.END} "
            f"{Colors.GREEN}({loc.expr_kind}{source_info}){Colors.END}\n"
            f"{pointer_indent}{Colors.BOLD}v{Colors.END}\n"
            f"{loc.source_line}\n"
        )
    else:
        return (
            f"{loc.file}:{loc.line}:{loc.column}\n"
            f"{type_indent}{loc.type_name} ({loc.expr_kind}{source_info})\n"
            f"{pointer_indent}v\n"
            f"{loc.source_line}\n"
        )

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Python type search engine")
    parser.add_argument("file", help="File to analyze")
    parser.add_argument("-t", "--type", help="Type pattern to search for")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()

    if args.no_color:
        global supports_color
        supports_color = lambda: False

    analyzer = TypeAnalyzer()
    locations = analyzer.analyze_file(Path(args.file), args.type)
    
    for loc in locations:
        print(format_location(loc))

if __name__ == "__main__":
    main()
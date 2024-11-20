#!/usr/bin/env python3  

import argparse  
import ast  
import os  
import sys  
from typing import List, Tuple, Optional  
import pkg_resources
import importlib.util

# ANSI color codes for coloring  
COLOR_RESET = "\033[0m"  
COLOR_RED = "\033[31m"  
COLOR_GREEN = "\033[32m"  
COLOR_YELLOW = "\033[33m"  
COLOR_BLUE = "\033[34m"  
COLOR_MAGENTA = "\033[35m"  
COLOR_CYAN = "\033[36m"  
COLOR_BOLD = "\033[1m"  

def parse_args():  
    parser = argparse.ArgumentParser(description='Dora: Search Python code by type expressions with colored output.')  
    parser.add_argument('paths', nargs='+', help='Files or directories to search')  
    parser.add_argument('-t', '--type', help='Type to search for (e.g., int, main.User, List[str])')  
    return parser.parse_args()  

def find_py_files(paths: List[str]) -> List[str]:  
    py_files = []  
    for path in paths:  
        if os.path.isfile(path) and path.endswith('.py'):  
            py_files.append(os.path.abspath(path))  
        elif os.path.isdir(path):  
            for root, _, files in os.walk(path):  
                for file in files:  
                    if file.endswith('.py'):  
                        py_files.append(os.path.abspath(os.path.join(root, file)))  
    return py_files  

def get_expr_type(node: ast.AST) -> str:  
    """  
    Map AST node types to expression type strings.  
    """  
    if isinstance(node, ast.Call):  
        return "CallExpr"  
    elif isinstance(node, ast.Name):  
        return "NameExpr"  
    elif isinstance(node, ast.Attribute):  
        return "AttributeExpr"  
    elif isinstance(node, ast.Subscript):  
        return "SubscriptExpr"  
    elif isinstance(node, ast.Constant):  
        return f"{type(node.value).__name__}Expr"  
    elif isinstance(node, ast.BinOp):  
        return "BinOpExpr"  
    elif isinstance(node, ast.UnaryOp):  
        return "UnaryOpExpr"  
    elif isinstance(node, ast.List):  
        return "ListExpr"  
    elif isinstance(node, ast.Tuple):  
        return "TupleExpr"  
    elif isinstance(node, ast.Dict):  
        return "DictExpr"  
    elif isinstance(node, ast.Lambda):  
        return "LambdaExpr"  
    elif isinstance(node, ast.Compare):  
        return "CompareExpr"  
    elif isinstance(node, ast.BoolOp):  
        return "BoolOpExpr"  
    elif isinstance(node, ast.IfExp):  
        return "IfExpExpr"  
    elif isinstance(node, ast.Expr):  
        return "Expr"  
    else:  
        return type(node).__name__  # Default to AST node name  

def get_fully_qualified_name(node: ast.AST, aliases: dict) -> str:  
    """  
    Attempt to get the fully qualified name of a type annotation.  
    """  
    if isinstance(node, ast.Name):  
        return node.id  
    elif isinstance(node, ast.Attribute):  
        value = get_fully_qualified_name(node.value, aliases)  
        return f"{value}.{node.attr}" if value else node.attr  
    elif isinstance(node, ast.Subscript):  
        value = get_fully_qualified_name(node.value, aliases)  
        slice_val = get_fully_qualified_name(node.slice, aliases)  
        return f"{value}[{slice_val}]"  
    elif isinstance(node, ast.Index):  # For Python <3.9  
        return get_fully_qualified_name(node.value, aliases)  
    elif isinstance(node, ast.Tuple):  
        return ", ".join(get_fully_qualified_name(elt, aliases) for elt in node.elts)  
    elif isinstance(node, ast.List):  
        return ", ".join(get_fully_qualified_name(elt, aliases) for elt in node.elts)  
    elif isinstance(node, ast.Constant):  
        return repr(node.value)  
    elif isinstance(node, ast.Str):  # For Python <3.8  
        return repr(node.s)  
    else:  
        return ""  
def get_package_info(module_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get package name and description for a module.
    Returns (package_name, description) tuple.
    """
    try:
        # Try to get package info from pkg_resources
        dist = pkg_resources.working_set.by_key.get(module_name.split('.')[0])
        if dist:
            return dist.project_name, dist.description
        
        # For standard library modules
        if module_name in sys.stdlib_module_names:
            return module_name, "Python Standard Library"
            
        # Try to get module spec
        spec = importlib.util.find_spec(module_name.split('.')[0])
        if spec and spec.origin:
            if 'site-packages' in spec.origin:
                return module_name, "Third-party package"
            elif 'python' in spec.origin:
                return module_name, "Python Standard Library"
                
    except Exception:
        pass
    return None, None

def extract_imports(node: ast.AST, file_path: str) -> dict:
    """
    Extract import aliases with their sources and package info.
    Returns a dictionary mapping aliases to (module_name, source, package_info) tuples.
    """
    aliases = {}
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                name = alias.name
                asname = alias.asname if alias.asname else alias.name
                try:
                    module = __import__(name.split('.')[0])
                    source = module.__file__ if hasattr(module, '__file__') else name
                    pkg_name, pkg_desc = get_package_info(name)
                except ImportError:
                    source = name
                    pkg_name, pkg_desc = None, None
                aliases[asname] = (name, source, (pkg_name, pkg_desc))
                
        elif isinstance(child, ast.ImportFrom):
            module = child.module
            for alias in child.names:
                name = alias.name
                asname = alias.asname if alias.asname else alias.name
                full_name = f"{module}.{name}" if module else name
                try:
                    if module:
                        base_module = __import__(module.split('.')[0])
                        source = base_module.__file__ if hasattr(base_module, '__file__') else module
                        pkg_name, pkg_desc = get_package_info(module)
                    else:
                        source = os.path.abspath(os.path.dirname(file_path))
                        pkg_name, pkg_desc = None, "Local module"
                except ImportError:
                    source = module or "local"
                    pkg_name, pkg_desc = None, None
                aliases[asname] = (full_name, source, (pkg_name, pkg_desc))
    return aliases

def extract_expressions(node: ast.AST, aliases: dict) -> List[ast.AST]:  
    """  
    Extract all expressions from the AST.  
    """  
    exprs = []  

    class ExprVisitor(ast.NodeVisitor):  
        def visit_Call(self, node: ast.Call):  
            exprs.append(node)  
            self.generic_visit(node)  

        def visit_Name(self, node: ast.Name):  
            exprs.append(node)  
            self.generic_visit(node)  

        def visit_Attribute(self, node: ast.Attribute):  
            exprs.append(node)  
            self.generic_visit(node)  

        def visit_Subscript(self, node: ast.Subscript):  
            exprs.append(node)  
            self.generic_visit(node)  

        def visit_Constant(self, node: ast.Constant):  
            exprs.append(node)  
            self.generic_visit(node)  

        # Add more visit_ methods if needed for other expression types  

    ExprVisitor().visit(node)  
    return exprs  

def extract_annotations_and_exprs(node: ast.AST, aliases: dict) -> List[Tuple[ast.AST, str]]:  
    """  
    Extract type annotations and expressions with their inferred types.  
    Returns a list of tuples containing the node and its type string.  
    """  
    results = []  

    class AnnotationExprVisitor(ast.NodeVisitor):  
        def visit_FunctionDef(self, func: ast.FunctionDef):  
            # Function arguments  
            for arg in func.args.args + func.args.kwonlyargs:  
                if arg.annotation:  
                    results.append((arg.annotation, get_fully_qualified_name(arg.annotation, aliases)))  
            # Return annotation  
            if func.returns:  
                results.append((func.returns, get_fully_qualified_name(func.returns, aliases)))  
            self.generic_visit(func)  

        def visit_AsyncFunctionDef(self, func: ast.AsyncFunctionDef):  
            self.visit_FunctionDef(func)  

        def visit_AnnAssign(self, ann: ast.AnnAssign):  
            if ann.annotation:  
                results.append((ann.annotation, get_fully_qualified_name(ann.annotation, aliases)))  
            self.generic_visit(ann)  

        def visit_Assign(self, assign: ast.Assign):  
            # Look for variable annotations in type comments  
            for target in assign.targets:  
                if isinstance(target, ast.Name) and assign.type_comment:  
                    # Parse the type comment  
                    try:  
                        type_comment = ast.parse(assign.type_comment, mode='eval').body  
                        results.append((type_comment, get_fully_qualified_name(type_comment, aliases)))  
                    except:  
                        pass  
            self.generic_visit(assign)  

        def visit_ClassDef(self, cls: ast.ClassDef):  
            # Base classes could have type expressions  
            for base in cls.bases:  
                results.append((base, get_fully_qualified_name(base, aliases)))  
            self.generic_visit(cls)  

    AnnotationExprVisitor().visit(node)  

    # Now extract expressions  
    exprs = extract_expressions(node, aliases)  
    for expr in exprs:  
        expr_type = get_expr_type(expr)  
        type_str = infer_type(expr, aliases)  
        results.append((expr, type_str))  

    return results  

def infer_type(node: ast.AST, aliases: dict) -> str:  
    """  
    Infer the type of an expression node.  
    This is a simplistic inference based on the node type.  
    """  
    if isinstance(node, ast.Call):  
        # Attempt to get the function being called  
        func_name = get_fully_qualified_name(node.func, aliases)  
        return func_name if func_name else "Unknown"  
    elif isinstance(node, ast.Name):  
        return node.id  
    elif isinstance(node, ast.Attribute):  
        return get_fully_qualified_name(node, aliases)  
    elif isinstance(node, ast.Constant):  
        return type(node.value).__name__  
    elif isinstance(node, ast.Subscript):  
        return get_fully_qualified_name(node, aliases)  
    elif isinstance(node, ast.BinOp):  
        return "BinOp"  
    elif isinstance(node, ast.UnaryOp):  
        return "UnaryOp"  
    elif isinstance(node, ast.List):  
        return "List"  
    elif isinstance(node, ast.Tuple):  
        return "Tuple"  
    elif isinstance(node, ast.Dict):  
        return "Dict"  
    elif isinstance(node, ast.Lambda):  
        return "Lambda"  
    elif isinstance(node, ast.Compare):  
        return "Compare"  
    elif isinstance(node, ast.BoolOp):  
        return "BoolOp"  
    elif isinstance(node, ast.IfExp):  
        return "IfExp"  
    else:  
        return "Unknown"  

def colorize(text: str, color_code: str) -> str:  
    return f"{color_code}{text}{COLOR_RESET}"  

def search_file(file_path: str, target_type: Optional[str]) -> List[Tuple[int, int, str, str, str, str, Optional[str], Optional[Tuple[str, str]]]]:
    """
    Enhanced search_file that includes import source and package information
    """
    matches = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=file_path)

        aliases = extract_imports(tree, file_path)
        annotations_and_exprs = extract_annotations_and_exprs(tree, aliases)

        lines = source.splitlines()

        for node, type_str in annotations_and_exprs:
            if not hasattr(node, 'lineno') or not hasattr(node, 'col_offset'):
                continue
                
            # Get import source and package info for Names
            import_source = None
            pkg_info = None
            if isinstance(node, ast.Name) and node.id in aliases:
                _, source, pkg_info = aliases[node.id]
                import_source = os.path.basename(source) if source.endswith('.py') else source

            line_no = node.lineno
            col_offset = node.col_offset
            end_lineno = getattr(node, 'end_lineno', line_no)
            end_col_offset = getattr(node, 'end_col_offset', col_offset + 1)

            if target_type and type_str != target_type:
                continue

            expr_type = get_expr_type(node)

            if line_no - 1 < len(lines):
                source_line = lines[line_no - 1]
                expr_str = source_line[col_offset:end_col_offset] if end_col_offset > col_offset else source_line[col_offset:]
            else:
                source_line = ""
                expr_str = ""

            matches.append((line_no, col_offset, type_str, expr_type, source_line, expr_str, import_source, pkg_info))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Skipping {file_path}: {e}", file=sys.stderr)
    return matches

def highlight_expression(source_line: str, expr_str: str, col_offset: int) -> str:  
    """  
    Highlight the expression in the source line using ANSI colors.  
    """  
    before = source_line[:col_offset]  
    after = source_line[col_offset + len(expr_str):]  
    highlighted = colorize(expr_str, COLOR_GREEN)  
    return before + highlighted + after  

def main():
    args = parse_args()
    target_type = args.type
    paths = args.paths

    py_files = find_py_files(paths)
    if not py_files:
        print("No Python files found.")
        return

    for file in py_files:
        matches = search_file(file, target_type)
        for match in matches:
            line_no, col_offset, type_str, expr_type, source_line, expr_str, import_source, pkg_info = match
            print(f"{file}:{line_no}:{col_offset}")
            
            padding = " " * col_offset
            colored_expr = colorize(expr_str, COLOR_CYAN)
            
            # Add import source and package information if available
            if import_source:
                source_info = colorize(import_source, COLOR_YELLOW)
                if pkg_info and pkg_info[0] and pkg_info[1]:
                    pkg_name, pkg_desc = pkg_info
                    print(f"{padding}{colored_expr} ({expr_type}) from {source_info}")
                    print(f"{padding}└─ {pkg_name}: {pkg_desc}")
                else:
                    print(f"{padding}{colored_expr} ({expr_type}) from {source_info}")
            else:
                print(f"{padding}{colored_expr} ({expr_type})")
                
            print(f"{padding}v")
            highlighted_line = highlight_expression(source_line, expr_str, col_offset)
            print(f"{highlighted_line}")
            print()

if __name__ == "__main__":  
    main()
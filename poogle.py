#!/usr/bin/env python3  

import argparse  
import ast  
import os  
from typing import List, Tuple, Set  

def parse_args():  
    parser = argparse.ArgumentParser(description='Search Python code by type expressions.')  
    parser.add_argument('type', help='Type to search for (e.g., int, List[str])')  
    parser.add_argument('paths', nargs='+', help='Files or directories to search')  
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

def type_matches(annotation, target_type: str) -> bool:  
    """  
    Recursively check if the target_type appears in the annotation.  
    """  
    if isinstance(annotation, ast.Name):  
        return annotation.id == target_type  
    elif isinstance(annotation, ast.Attribute):  
        return annotation.attr == target_type  
    elif isinstance(annotation, ast.Subscript):  
        return type_matches(annotation.value, target_type) or type_matches(annotation.slice, target_type)  
    elif isinstance(annotation, ast.Tuple):  
        return any(type_matches(elt, target_type) for elt in annotation.elts)  
    elif isinstance(annotation, ast.List):  
        return any(type_matches(elt, target_type) for elt in annotation.elts)  
    elif isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):  
        # Handle Python 3.10+ | union types  
        return type_matches(annotation.left, target_type) or type_matches(annotation.right, target_type)  
    elif isinstance(annotation, ast.Call):  
        return type_matches(annotation.func, target_type) or any(type_matches(arg, target_type) for arg in annotation.args)  
    return False  

def extract_annotations(node: ast.AST) -> List[Tuple[ast.AST, int, int]]:  
    """  
    Extract all type annotations from the AST node.  
    Returns a list of tuples containing the annotation node and its line and column.  
    """  
    annotations = []  

    class AnnotationVisitor(ast.NodeVisitor):  
        def visit_FunctionDef(self, func: ast.FunctionDef):  
            # Function arguments  
            for arg in func.args.args + func.args.kwonlyargs:  
                if arg.annotation:  
                    annotations.append((arg.annotation, arg.annotation.lineno, arg.annotation.col_offset))  
            # Return annotation  
            if func.returns:  
                annotations.append((func.returns, func.returns.lineno, func.returns.col_offset))  
            self.generic_visit(func)  

        def visit_AsyncFunctionDef(self, func: ast.AsyncFunctionDef):  
            self.visit_FunctionDef(func)  

        def visit_AnnAssign(self, ann: ast.AnnAssign):  
            if ann.annotation:  
                annotations.append((ann.annotation, ann.annotation.lineno, ann.annotation.col_offset))  
            self.generic_visit(ann)  

        def visit_Assign(self, assign: ast.Assign):  
            # Look for variable annotations in type comments  
            for target in assign.targets:  
                if isinstance(target, ast.Name) and assign.type_comment:  
                    # Parse the type comment  
                    try:  
                        type_comment = ast.parse(assign.type_comment, mode='eval').body  
                        annotations.append((type_comment, assign.lineno, assign.col_offset))  
                    except:  
                        pass  
            self.generic_visit(assign)  

        def visit_ClassDef(self, cls: ast.ClassDef):  
            # Base classes could have type expressions  
            for base in cls.bases:  
                annotations.append((base, base.lineno, base.col_offset))  
            self.generic_visit(cls)  

    AnnotationVisitor().visit(node)  
    return annotations  

def search_file(file_path: str, target_type: str) -> List[Tuple[int, int, str]]:  
    matches = []  
    try:  
        with open(file_path, 'r', encoding='utf-8') as f:  
            source = f.read()  
        tree = ast.parse(source, filename=file_path)  
        annotations = extract_annotations(tree)  
        for annotation, lineno, col_offset in annotations:  
            if type_matches(annotation, target_type):  
                matches.append((lineno, col_offset, target_type))  
    except (SyntaxError, UnicodeDecodeError) as e:  
        print(f"Skipping {file_path}: {e}")  
    return matches  

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
        for lineno, col, typ in matches:  
            print(f"{file}:{lineno}:{col}")  

if __name__ == "__main__":  
    main()
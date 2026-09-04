"""Lift the hard-coded jurisdiction chains out of legacy docassemble-MACourts.

The legacy package encodes every city/county jurisdiction rule as a long
``if``/``elif`` chain of Python literals. This script parses those functions with
``ast`` and emits the equivalent data, so ``macourts/data/jurisdiction_rules.json``
can be regenerated and diffed instead of hand-maintained.

Usage::

    python scripts/extract_legacy_jurisdiction_rules.py \
        --legacy ~/docassemble-MACourts/docassemble/MACourts/macourts.py \
        --out /tmp/legacy_rules.json

Curated corrections (documented in docs/jurisdiction_rules.md) are applied on top
of this output by hand; this script deliberately reports raw legacy behavior.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

# legacy method name -> (department, selection mode)
FUNCTIONS = {
    "matching_district_court_name": ("District Court", "all"),
    "matching_juvenile_court_name": ("Juvenile Court", "all"),
    "matching_probate_and_family_court_name": ("Probate and Family Court", "all"),
    "matching_superior_court_name": ("Superior Court", "first"),
    "matching_housing_court_name": ("Housing Court", "first"),
}

# Chain entries that implement plumbing rather than jurisdiction.
PLUMBING_NAMES = {"depth", "matches", "local_superior_court", "local_housing_court"}

# Legacy constructs that are jurisdiction logic but not city/county data. They are
# reimplemented directly in ``macourts.core`` and must not become rules:
#   hasattr(..., "county")  -> the "infer Suffolk County for Boston" preamble
#   self.matching_bmc(...)  -> the BMC-division-dependent Juvenile special cases
# ``hasattr(..., "neighborhood")`` is *not* in this set: it guards real
# neighborhood jurisdiction data, which ``parse_neighborhood_group`` keeps.
REIMPLEMENTED_CALLS = {"matching_bmc"}


class Unsupported(Exception):
    """Raised when a legacy construct is not jurisdiction data."""


def attr_path(node: ast.AST) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def zero_arg_call_path(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and not node.args and not node.keywords:
        return attr_path(node.func)
    return None


def string_list(node: ast.AST) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values = []
    for element in node.elts:
        if not (isinstance(element, ast.Constant) and isinstance(element.value, str)):
            return None
        values.append(element.value.strip().casefold())
    return values


def is_plumbing(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Name) and child.id in PLUMBING_NAMES
        for child in ast.walk(node)
    )


def is_reimplemented(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = (
            child.func.attr
            if isinstance(child.func, ast.Attribute)
            else getattr(child.func, "id", "")
        )
        if name in REIMPLEMENTED_CALLS:
            return True
        if name == "hasattr" and len(child.args) == 2:
            attribute = child.args[1]
            if isinstance(attribute, ast.Constant) and attribute.value == "county":
                return True
    return False


def parse_neighborhood_group(node: ast.BoolOp) -> dict:
    """``hasattr(a, 'neighborhood') and a.city.lower() == 'boston' and ...in [...]``."""
    city = None
    names = None
    pending = list(node.values)
    while pending:
        item = pending.pop()
        if isinstance(item, ast.BoolOp) and isinstance(item.op, ast.And):
            pending.extend(item.values)
            continue
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id == "hasattr":
                continue
        if isinstance(item, ast.Compare) and len(item.ops) == 1:
            left = zero_arg_call_path(item.left)
            operator = item.ops[0]
            right = item.comparators[0]
            if (
                left
                and left.endswith(".city.lower")
                and isinstance(operator, ast.Eq)
                and isinstance(right, ast.Constant)
            ):
                city = right.value.strip().casefold()
                continue
            if left and left.endswith(".neighborhood.lower") and isinstance(operator, ast.In):
                values = string_list(right)
                if values is not None:
                    names = values
                    continue
        raise Unsupported(ast.dump(item)[:200])
    if names is None:
        raise Unsupported("neighborhood group without a name list")
    return {"city": city, "names": names}


def parse_comparison(node: ast.Compare, rule: dict) -> None:
    if len(node.ops) != 1:
        raise Unsupported(ast.dump(node)[:200])
    left = zero_arg_call_path(node.left)
    operator = node.ops[0]
    right = node.comparators[0]
    if not left:
        raise Unsupported(ast.dump(node)[:200])

    if left.endswith(".city.lower") and isinstance(operator, ast.In):
        values = string_list(right)
        if values is None:
            raise Unsupported(ast.dump(node)[:200])
        rule.setdefault("cities", []).extend(values)
        return
    if left.endswith(".city.lower") and isinstance(operator, ast.NotIn):
        values = string_list(right)
        if values is None:
            raise Unsupported(ast.dump(node)[:200])
        rule.setdefault("excluded_cities", []).extend(values)
        return
    if left.endswith(".county.lower"):
        if isinstance(operator, ast.Eq) and isinstance(right, ast.Constant):
            rule.setdefault("counties", []).append(right.value.strip().casefold())
            return
        if isinstance(operator, ast.In):
            values = string_list(right)
            if values is not None:
                rule.setdefault("counties", []).extend(values)
                return
    if left.endswith(".neighborhood.lower") and isinstance(operator, ast.In):
        values = string_list(right)
        if values is not None:
            rule.setdefault("neighborhoods", []).append({"city": None, "names": values})
            return
    raise Unsupported(ast.dump(node)[:200])


def parse_test(node: ast.AST) -> dict:
    """Turn one chain test into a rule predicate dict."""
    rule: dict = {}

    def walk(test: ast.AST) -> None:
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            inner = test.operand
            if isinstance(inner, ast.Compare) and len(inner.ops) == 1 and isinstance(inner.ops[0], ast.In):
                values = string_list(inner.comparators[0])
                left = zero_arg_call_path(inner.left)
                if values is not None and left and left.endswith(".city.lower"):
                    rule.setdefault("excluded_cities", []).extend(values)
                    return
            raise Unsupported(ast.dump(test)[:200])
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
            for value in test.values:
                walk(value)
            return
        if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
            # An ``and`` is either a neighborhood group or a real conjunction.
            try:
                group = parse_neighborhood_group(test)
            except Unsupported:
                group = None
            if group is not None:
                rule.setdefault("neighborhoods", []).append(group)
                return
            for value in test.values:
                walk(value)
            rule["require_all"] = True
            return
        if isinstance(test, ast.Compare):
            parse_comparison(test, rule)
            return
        raise Unsupported(ast.dump(test)[:200])

    walk(node)
    for key in ("cities", "counties", "excluded_cities"):
        if key in rule:
            rule[key] = sorted(dict.fromkeys(rule[key]))
    return rule


def parse_body(body: list[ast.stmt]) -> list[str]:
    """Collect the court names a chain branch produces."""
    names: list[str] = []
    for statement in body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            path = attr_path(statement.value.func)
            arguments = statement.value.args
            if path.endswith(".append") and len(arguments) == 1:
                argument = arguments[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    names.append(argument.value)
                    continue
            if path.endswith(".extend") and len(arguments) == 1:
                values = arguments[0]
                if isinstance(values, (ast.List, ast.Tuple)):
                    for element in values.elts:
                        if not (
                            isinstance(element, ast.Constant)
                            and isinstance(element.value, str)
                        ):
                            raise Unsupported(ast.dump(statement)[:200])
                        names.append(element.value)
                    continue
            raise Unsupported(ast.dump(statement)[:200])
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
            if isinstance(target, ast.Name) and isinstance(value, ast.Constant):
                if isinstance(value.value, str):
                    if value.value:
                        names.append(value.value)
                    continue
            raise Unsupported(ast.dump(statement)[:200])
        raise Unsupported(ast.dump(statement)[:200])
    return names


def flatten_chain(node: ast.If) -> list[dict]:
    rules: list[dict] = []
    while True:
        if not is_plumbing(node.test) and not is_reimplemented(node.test):
            try:
                predicate = parse_test(node.test)
                courts = parse_body(node.body)
            except Unsupported as error:
                rules.append({"unsupported": str(error)})
            else:
                if predicate and courts:
                    rules.append({**predicate, "courts": courts})
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            node = node.orelse[0]
            continue
        return rules


def extract(legacy_path: Path) -> dict:
    tree = ast.parse(legacy_path.read_text(encoding="utf-8"))
    functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    departments = []
    for function_name, (department, selection) in FUNCTIONS.items():
        rules: list[dict] = []
        for statement in functions[function_name].body:
            if isinstance(statement, ast.If):
                rules.extend(flatten_chain(statement))
        departments.append(
            {"department": department, "selection": selection, "rules": rules}
        )
    return {"schema_version": 1, "departments": departments}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    data = extract(arguments.legacy)
    arguments.out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for department in data["departments"]:
        unsupported = [rule for rule in department["rules"] if "unsupported" in rule]
        print(
            f'{department["department"]}: {len(department["rules"])} rules'
            f'{f", {len(unsupported)} UNSUPPORTED" if unsupported else ""}'
        )
        for rule in unsupported:
            print("   ", rule["unsupported"][:160])


if __name__ == "__main__":
    main()

import csv
import json
import os
from typing import Any, Dict, Iterable, List
from xml.etree.ElementTree import Element, SubElement, ElementTree

class ExportManager:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def export_json(self, items: List[Dict[str, Any]], filename: str) -> str:
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
        return path

    def export_csv(self, items: List[Dict[str, Any]], filename: str) -> str:
        path = os.path.join(self.output_dir, filename)
        # Flatten top-level keys; lists/dicts converted to JSON strings
        keys = self._collect_keys(items)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for it in items:
                row = {k: (json.dumps(it.get(k)) if isinstance(it.get(k), (list, dict)) else it.get(k)) for k in keys}
                writer.writerow(row)
        return path

    def export_xml(self, items: List[Dict[str, Any]], filename: str, root_tag: str = "items", item_tag: str = "item") -> str:
        path = os.path.join(self.output_dir, filename)
        root = Element(root_tag)
        for it in items:
            node = SubElement(root, item_tag)
            self._append_dict(node, it)
        ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    # -------------------- helpers --------------------

    def _collect_keys(self, items: Iterable[Dict[str, Any]]) -> List[str]:
        keys = set()
        for it in items:
            keys.update(list(it.keys()))
        # Stable order with important keys first
        preferred = ["name", "profileUrl", "userId", "profileImage", "coverImage", "images", "userData", "_fetchedAt", "_source"]
        ordered = [k for k in preferred if k in keys] + sorted(k for k in keys if k not in preferred)
        return ordered

    def _append_dict(self, parent: Element, data: Dict[str, Any]) -> None:
        for k, v in data.items():
            if isinstance(v, dict):
                node = SubElement(parent, k)
                self._append_dict(node, v)
            elif isinstance(v, list):
                arr = SubElement(parent, k)
                for item in v:
                    child = SubElement(arr, "item")
                    if isinstance(item, (dict, list)):
                        # nested structure
                        if isinstance(item, dict):
                            self._append_dict(child, item)
                        else:
                            for sub in item:
                                sub_el = SubElement(child, "item")
                                sub_el.text = str(sub)
                    else:
                        child.text = str(item)
            else:
                node = SubElement(parent, k)
                node.text = "" if v is None else str(v)
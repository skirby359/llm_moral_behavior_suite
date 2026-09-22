"""Wave 7 minimal pairs: regenerate each variant family from its anchor and the committed manifest.

    uv run python scenarios_sandbox/wave7_pairs.py            # write the four variant YAMLs
    uv run python scenarios_sandbox/wave7_pairs.py --check    # exit 1 if any committed file differs

The manifest (wave7_pairs.json) is the preregistered span partition: it says which strings a
variant may differ from its anchor in, and nothing else. A variant file is therefore a pure
function of (anchor bytes, manifest); this module is that function, and
tests/test_wave7_minimal_pairs.py asserts the committed files equal its output. Authoring "by
hand" would leave open the accident the design note warns about -- changing several things and
reading one -- so the only way a variant can differ from its anchor is to edit the manifest,
which is itself under the preregistration's no-edit rule after the first frontier call.

META lines (the leading comment block; the id, family and title lines) are rewritten from the
manifest and excluded from the equality check; everything else is anchor text with the ordered
substitutions applied.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scenarios_sandbox" / "wave7_pairs.json"


def load_manifest(path: pathlib.Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def split_meta(text: str, meta_prefixes: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Return (header comment lines, body lines) where the body has id/family/title blanked.

    The header block is every leading line that starts with '#' up to the first blank line.
    Body META lines are kept as positional markers (replaced by their prefix alone) so the
    line alignment of anchor and variant is preserved for diffing.
    """
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        i += 1
    header, body = lines[:i], lines[i:]
    body = [
        (next(p for p in meta_prefixes if ln.startswith(p)) + "\n") if any(ln.startswith(p) for p in meta_prefixes) else ln
        for ln in body
    ]
    return header, body


def apply_substitutions(text: str, subs: list[list[str]]) -> str:
    for src, dst in subs:
        text = text.replace(src, dst)
    return text


def stem_of(file: str) -> str:
    return pathlib.Path(file).stem


def render_variant(anchor_text: str, spec: dict, family: str, manifest: dict) -> str:
    """The full variant file text: manifest header, then the anchor body with substitutions
    applied and the id / family / title lines rewritten."""
    prefixes = tuple(manifest["meta_line_prefixes"])
    _, body = split_meta(anchor_text, prefixes)
    stem = stem_of(spec["file"])
    out_lines = []
    for ln in body:
        if ln == "id:\n":
            out_lines.append(f'id: "sb_{stem}"\n')
        elif ln == "family:\n":
            out_lines.append(f'family: "{family}"\n')
        elif ln == "title:\n":
            out_lines.append(f'title: "{spec["title"]}"\n')
        else:
            out_lines.append(ln)
    text = "".join(out_lines)
    text = apply_substitutions(text, spec["substitutions"])
    header = "\n".join(spec["header"]) + "\n"
    return header + text


def variant_body_from_anchor(anchor_text: str, spec: dict, manifest: dict) -> str:
    """Anchor body (META blanked) with substitutions applied: what the committed variant's body
    must equal once its own META lines are blanked."""
    prefixes = tuple(manifest["meta_line_prefixes"])
    _, body = split_meta(anchor_text, prefixes)
    return apply_substitutions("".join(body), spec["substitutions"])


def body_of(text: str, manifest: dict) -> str:
    prefixes = tuple(manifest["meta_line_prefixes"])
    _, body = split_meta(text, prefixes)
    return "".join(body)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="compare, do not write")
    args = ap.parse_args(argv)
    manifest = load_manifest()
    rc = 0
    for family, spec in manifest["variants"].items():
        anchor_path = ROOT / manifest["anchors"][spec["anchor"]]["file"]
        out_path = ROOT / spec["file"]
        rendered = render_variant(anchor_path.read_text(encoding="utf-8"), spec, family, manifest)
        if args.check:
            current = out_path.read_text(encoding="utf-8") if out_path.exists() else None
            ok = current == rendered
            print(f"  {'OK  ' if ok else 'DIFF'}  {spec['file']}")
            rc |= 0 if ok else 1
        else:
            out_path.write_text(rendered, encoding="utf-8", newline="\n")
            print(f"  wrote {spec['file']}  ({spec['label']}, {spec['dimension']} swap of {spec['anchor']})")
    return rc


if __name__ == "__main__":
    sys.exit(main())

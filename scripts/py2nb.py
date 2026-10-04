"""Convert a "percent-format" Python file into a Jupyter notebook.

Source of truth for every notebook is a plain `.py` file in `notebooks/src/`
(so the code can be linted, diffed and smoke-tested outside Jupyter).

Cell markers:
    # %% [markdown]   -> markdown cell (every following line starting with '# ')
    # %%               -> code cell

Usage:  python scripts/py2nb.py notebooks/src/02_price.py notebooks/02_price.ipynb
"""
import sys
import nbformat as nbf


def convert(src: str, dst: str) -> None:
    nb = nbf.v4.new_notebook()
    cells, kind, buf = [], None, []

    def flush():
        if kind is None:
            return
        text = "\n".join(buf).strip("\n")
        if not text:
            return
        if kind == "md":
            lines = [l[2:] if l.startswith("# ") else l.lstrip("#") for l in text.split("\n")]
            cells.append(nbf.v4.new_markdown_cell("\n".join(lines)))
        else:
            cells.append(nbf.v4.new_code_cell(text))

    for line in open(src, encoding="utf-8").read().split("\n"):
        if line.startswith("# %% [markdown]"):
            flush(); kind, buf = "md", []
        elif line.startswith("# %%"):
            flush(); kind, buf = "code", []
        else:
            buf.append(line)
    flush()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    nbf.write(nb, dst)
    print(f"wrote {dst} ({len(cells)} cells)")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])

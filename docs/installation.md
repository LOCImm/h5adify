# Installation

```bash
git clone <your-repo>
cd h5adify
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Optional extras

```bash
pip install -e ".[sodb]"  # SODB via pysodb
pip install -e ".[docs]"  # docs build
```

## Build docs

```bash
cd docs
make html
```

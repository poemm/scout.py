
The Python file `scout.py` implements the [Scout spec](https://ethresear.ch/t/phase-2-execution-prototyping-engine-ewasm-scout/5509) to parse yaml test files, and to execute the Wasm tests.


# Dependencies

We use Python3. We use the standard `PyYAML` package to parse Scout test yaml format, and `pywebassembly` to execute Wasm.

```
cd scout.py

# PyYAML
# Option 1) on debian-based distros
apt-get install python3-yaml
# Option 2) on fedora-based distros
yum install python3-yaml
# Option 3) on other systems, can use pip
pip install pyyaml

# PyWebAssembly
git clone https://github.com/poemm/pywebassembly.git
```


# Execute

```
# from scout.py repo directory
python3 scout.py helloworld.yaml
# warning: yaml files specify path to wasm files relative to scout.exec, everything is in the same directory for now
```

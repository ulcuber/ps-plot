# Install

You can `make clean` to change install method

## Pip

```bash
make venv
. venv/bin/activate
make install
```

## Pacman, Emerge

See `Makefile`

```bash
make {pacman|emerge}
make venv-system
```

# Run

- `./run` to from anywhere without `cd` within `venv`
- `./run --help` to see implemented flags
- `./run --group` to sum resources of processes with the same name
- `./run --group --pid <pid> --memtype rss` to see which libs of this process eating more RAM
- `./forest [--with_libs]` for maximum details in CLI

# Extra

## CLI

- `make pcpu` for top CPU consumers
- `make pmem` for top Memory consumers

---

For more see `Makefile` recipes

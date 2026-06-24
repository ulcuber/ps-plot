.PHONY: pcpu pmem pacman emerge venv-system venv conda activate activate-conda clean install install-all uninstall test lint lint-fix

# CLI way
pcpu:
	ps -Ao pid,nice,pcpu,pmem,etime,cmd:40 --sort=-pcpu | head -n 15
pmem:
	ps -Ao pid,pcpu,pmem,etime,cmd:40,uss,rss --sort=-pmem | head -n 15

pacman:
	sudo pacman -S python-pyqt6 python-psutil python-matplotlib python-numpy
emerge:
	sudo emerge --ask --verbose --quiet \
		dev-python/PyQt6 \
		dev-python/psutil \
		dev-python/matplotlib \
		dev-python/numpy
# Only 13.4MB instead of 441.2MB
venv-system:
	python -m venv --system-site-packages --symlinks venv

venv:
	python -m venv venv
conda:
	conda create -f environment.yml

# . ./venv/bin/activate before make
activate:
	. venv/bin/activate
activate-conda:
	conda activate conda_env
clean:
	rm -rf venv
	rm -rf conda_env
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Qt
install:
	pip install -r requirements.txt
uninstall:
	pip uninstall -r ./requirements.txt

test:
	python -m unittest discover -f -s tests -t .
lint:
	python -m ruff check src
lint-fix:
	python -m ruff format src

.PHONY: install install-all test lint format typecheck samples demo evaluate serve docker clean

install:            ## Install the package with dev tools
	pip install -e ".[dev]"

install-all:        ## Install everything (API, spaCy, LLM, dev)
	pip install -e ".[all]"
	python -m spacy download en_core_web_sm
	python -m spacy download fr_core_news_sm

test:               ## Run the test suite with coverage
	pytest --cov --cov-report=term-missing

lint:               ## Static checks
	ruff check .
	ruff format --check .

format:             ## Auto-format
	ruff check --fix .
	ruff format .

typecheck:
	mypy src

samples:            ## (Re)generate the synthetic documents
	idp generate-samples

demo: samples       ## Process the sample documents
	idp process data/samples -o output

evaluate: samples   ## Score the pipeline against ground truth
	idp evaluate data/samples --min-f1 0.95
	-idp evaluate data/samples_hard

serve:              ## Start the REST API on http://127.0.0.1:8000/docs
	idp serve

docker:
	docker build -t idp-agent .

clean:
	rm -rf output .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info

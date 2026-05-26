# OPA-policies-src — local-test makefile.
#
# Run alleen vanuit deze directory:
#   make -C opa-policies-src test

.PHONY: fmt test bundle help

help:
	@echo "Targets:"
	@echo "  make fmt    — opa fmt --diff trino/"
	@echo "  make test   — opa test trino/ + data.json"
	@echo "  make bundle — sync trino/*.rego naar platform/10-opa/policies/"

fmt:
	opa fmt --diff trino/

test:
	opa test trino/ data/role_mappings.json -v

bundle:
	bash ../scripts/build-opa-bundle.sh

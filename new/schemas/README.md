# Schema directory status

The active JSON Schema contracts are maintained only in `../contracts/` and are loaded
from there by backend runtime validation. The duplicate, outdated schema copies that
were formerly in this directory have been removed. `intp.py` is retained as an unrelated
legacy artifact; it is not a schema or a runtime contract source.
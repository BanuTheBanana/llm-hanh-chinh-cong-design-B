from functools import lru_cache
from pathlib import Path
import json
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parents[3] / 'contracts'

@lru_cache
def validator(name):
    schemas = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in ROOT.glob('*.schema.json')}
    registry = Registry().with_resources((n, Resource.from_contents(s, default_specification=DRAFT202012)) for n,s in schemas.items())
    return Draft202012Validator(schemas[name+'.schema.json'], registry=registry, format_checker=FormatChecker())

def validate(name, data):
    errors = list(validator(name).iter_errors(data))
    if errors:
        # No document text in errors/logs.
        e = errors[0]
        raise ValueError(f'{name}: invalid field {"/".join(map(str,e.path)) or "root"}; rule={e.validator}')

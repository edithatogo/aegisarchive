"""Validate the JSON Schema vocabulary used by bundled profiles, without dependencies."""
import math


def validate(value, schema, path='$'):
    expected = schema.get('type')
    checks = {'object': lambda x: isinstance(x, dict), 'array': lambda x: isinstance(x, list),
              'string': lambda x: isinstance(x, str), 'boolean': lambda x: isinstance(x, bool),
              'integer': lambda x: isinstance(x, int) and not isinstance(x, bool),
              'number': lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)}
    if expected and (expected not in checks or not checks[expected](value)):
        raise ValueError(f'{path}: expected {expected}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{path}: value outside enum')
    for key, fails in [('minimum', lambda bound: value < bound), ('maximum', lambda bound: value > bound)]:
        if key in schema and fails(schema[key]):
            raise ValueError(f'{path}: outside {key}')
    if isinstance(value, dict):
        for key in schema.get('required', []):
            if key not in value:
                raise ValueError(f'{path}: missing {key}')
        properties = schema.get('properties', {})
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], f'{path}.{key}')
            elif schema.get('additionalProperties') is False:
                raise ValueError(f'{path}: unknown key {key}')
    if isinstance(value, list) and 'items' in schema:
        for index, item in enumerate(value):
            validate(item, schema['items'], f'{path}[{index}]')

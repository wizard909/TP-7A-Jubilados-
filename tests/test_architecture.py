import ast
from importlib.util import resolve_name
from pathlib import Path
from sys import stdlib_module_names
import unittest


APP = Path(__file__).resolve().parents[1] / 'app'
DOMAIN = 'app.solicitudes.dominio'
SERVICE = 'app.solicitudes.servicio'
ALLOWED = {
    DOMAIN: set(),
    SERVICE: {DOMAIN},
    'app.solicitudes.repositorio': {DOMAIN, 'app.persistencia'},
    'app.integraciones.padron': {DOMAIN, 'app.configuracion'},
    'app.persistencia': {'app.configuracion'},
    'app.configuracion': set(),
    'app.dependencias': {SERVICE, 'app.persistencia', 'app.solicitudes.repositorio',
                         'app.integraciones.padron', 'app.configuracion'},
    'app.seguridad': {SERVICE, 'app.configuracion'},
    'app.errores_http': {DOMAIN},
    'app.api': {DOMAIN, SERVICE, 'app.dependencias', 'app.seguridad'},
    'app.web': {DOMAIN, SERVICE, 'app.dependencias', 'app.seguridad', 'app.errores_http'},
    'app.main': {'app.api', 'app.seguridad', 'app.web', 'app.configuracion', 'app.errores_http',
                 'app.persistencia', 'app.solicitudes.repositorio'},
}


def imports(path, module):
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            yield from (name.name for name in node.names)
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ''
            if node.level:
                package = module.rpartition('.')[0]
                target = resolve_name('.' * node.level + target, package)
            if target in {'app', 'app.solicitudes', 'app.integraciones'}:
                yield from (f'{target}.{name.name}' for name in node.names)
            else:
                yield target


class ArchitectureTests(unittest.TestCase):
    def test_imports_respect_the_module_boundaries(self):
        modules = {'.'.join(path.relative_to(APP.parent).with_suffix('').parts): path
                   for path in APP.rglob('*.py') if path.name != '__init__.py'}
        self.assertEqual(set(modules), set(ALLOWED), 'Actualizar el mapa si se agrega un módulo')
        for module, path in modules.items():
            for target in imports(path, module):
                with self.subTest(module=module, dependency=target):
                    root = target.split('.')[0]
                    if root == 'app':
                        self.assertIn(target, ALLOWED[module])
                    elif module in {DOMAIN, SERVICE}:
                        self.assertIn(root, stdlib_module_names, 'Las reglas no importan infraestructura externa')

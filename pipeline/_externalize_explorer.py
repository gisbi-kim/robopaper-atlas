"""Keep explorer data in cacheable scripts smaller than a single huge HTML file."""
import hashlib
import json
from pathlib import Path


def externalize_explorer(content, root):
    decoder = json.JSONDecoder()
    scripts = []
    root = Path(root)
    (root / 'explorer_data').mkdir(exist_ok=True)
    for name in ('ALL', 'WB_VOCAB', 'WB_PAPERS'):
        marker = f'const {name} = '
        start = content.index(marker)
        value, length = decoder.raw_decode(content[start + len(marker):])
        pairs = list(value.items()) if isinstance(value, dict) else value
        for offset in range(0, len(pairs), 20000):
            part = pairs[offset:offset + 20000]
            serialized = json.dumps(dict(part) if isinstance(value, dict) else part, ensure_ascii=False)
            initial = f'const {name} = ' + ('{}' if isinstance(value, dict) else '[]') + ';\n' if offset == 0 else ''
            body = initial + (f'Object.assign({name}, {serialized});\n' if isinstance(value, dict) else f'{name}.push(...{serialized});\n')
            digest = hashlib.sha256(body.encode()).hexdigest()[:12]
            filename = f'explorer_data/{name.lower()}-{offset // 20000}-{digest}.js'
            (root / filename).write_text(body, encoding='utf-8', newline='\n')
            scripts.append(f'<script src="{filename}"></script>')
        content = content[:start] + content[start + len(marker) + length + 1:]
    return content.replace('<script>\n', '\n'.join(scripts) + '\n<script>\n', 1)

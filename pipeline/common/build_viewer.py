"""Inline a pack's model.json into its viewer template → site/diseases/<topic>/3d.html
usage: python3 pipeline/common/build_viewer.py ankle-sprain carpal-tunnel"""
import sys, os
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PACKS = { 'ankle-sprain': 'viewer_ankle_template.html', 'carpal-tunnel': 'viewer6_template.html',
          'compression-fracture': 'viewer_spine_template.html', 'knee-oa': 'viewer_knee_template.html' }
for topic in sys.argv[1:]:
    tpl = open(os.path.join(REPO, 'pipeline', topic, PACKS[topic]), encoding='utf-8').read()
    data = open(os.path.join(REPO, 'pipeline', topic, 'model.json'), encoding='utf-8').read().strip()
    assert tpl.count('__DATA__') == 1
    open(os.path.join(REPO, 'site', 'diseases', topic, '3d.html'), 'w', encoding='utf-8').write(tpl.replace('__DATA__', data))
    print('built', topic, len(tpl), len(data))

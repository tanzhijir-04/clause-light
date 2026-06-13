# -*- coding: utf-8 -*-
import json, os
base = r'C:\Users\20300\Desktop\clause-light\designs\contract-annotated-view'
data = json.load(open(os.path.join(base, 'data.json'), 'r', encoding='utf-8'))
print('Loaded', len(data.get('clauses',[])), 'clauses')

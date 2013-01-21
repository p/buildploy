#!/usr/bin/env python

import os.path
import os
import re

index = ''
spec_dir = os.path.join(os.path.dirname(__file__), 'specs')
for entry in sorted(os.listdir(spec_dir)):
    if entry[0] == '.' or not entry.endswith('.yml'):
        continue
    
    path = os.path.join(spec_dir, entry)
    with open(path) as f:
        content = f.read()
    
    match = re.compile(r'(^#.*(?:\n(?:^#.*))*)', re.M).match(content)
    if not match:
        import warnings
        warnings.warn('Did not find spec description in %s' % entry)
        continue
    
    description = re.compile(r'^#\s*', re.M).sub('', match.group(1))
    index += "## %s\n\n%s\n\n" % (entry, description)

# delete the last newline
index = index[:len(index)-1]
index = "# Spec index\n\n%s" % index

with open(os.path.join(spec_dir, 'INDEX.md'), 'w') as f:
    f.write(index)

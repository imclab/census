#!/usr/bin/env python

import csv
import re
import sys

from csvkit.unicsv import UnicodeCSVReader

import config, utils
import logging

TABLE_NAME_PATTERN = re.compile(r'^(?P<name>.+)\s+\[(?P<size>\d+)\].*$')


KEY_MAPPINGS = {}

with open('field_mappings_2000_2010.csv', 'rU') as f:
    reader = csv.DictReader(f)

    for row in reader:
        # Skip fields that don't map
        if not row['field_2000']:
            continue

        if not row['field_2010']:
            continue

        # TODO - skipping computed fields
        if '-' in row['field_2000'] or '+' in row['field_2000']:
            continue

        if '-' in row['field_2010'] or '+' in row['field_2010']:
            continue

        KEY_MAPPINGS[row['field_2010']] = row['field_2000']

YEAR = '2010'

def is_skipworthy_row(row):
    chk = set(row)
    if len(chk) == 1 and '' in chk:
        return True
    if row[:3] == ['','',''] and row[3].startswith('NOTE'):
        return True
    if row[1] and not row[0]: # section header
        return True
    return False

def dictify_row(row):
    row = map(unicode.strip,row)
    if is_skipworthy_row(row): return None
    table_id, line, indent = row[0:3]
    continuation = not table_id and not line and not indent
    if table_id:
        if table_id.endswith('.'): table_id = table_id[:-1]
    if indent:
        indent = int(indent)
    if line:
        line = int(line)
    return { 
        'table_id': table_id,
        'line': line,
        'indent': indent,
        'labels': row[3:9],
        'continuation': continuation
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('You must provide the filename of a CSV as an argument to this script.')

    FILENAME = sys.argv[1]

    with open(FILENAME) as f:
        rows = UnicodeCSVReader(f, encoding='latin-1')
        headers = rows.next()

        inserts = 0
        row_count = 0
        skipped = 0

        table = None 
        tables = {}
        hierarchy = []
        last_key = ''
        last_indent = 0

        for row in rows:
            row_count += 1
            if not row: continue
            row = map(unicode.strip,row)
            row = dictify_row(row)
            if row:
                if row['continuation']:
                    idx = last_processed['indent'] + 1
                    fragment = row['labels'][idx]
                    last_processed['text'] += ' %s' % fragment
                    continue

                table = tables.setdefault(row['table_id'],{ 'key': row['table_id'], 'year': '2010', 'labels': {} })

                if not row['line']: # we probably have a table name or a universe
                    if row['labels'][0].startswith("Universe:"):
                        parts = row['labels'][0].split(":", 2)
                        table['universe'] = parts[1].strip()
                    else:
                        # we know that they have extra labels for "indents" for avg/median that we just want to skip
                        if not row['labels'][0].startswith('Average') and not row['labels'][0].startswith('Median'): 
                            match = TABLE_NAME_PATTERN.match(row['labels'][0])
                            if not match:
                                if not row['labels'][0]: continue
                                fix_row = rows.next()
                                dfr = dictify_row(fix_row)
                                row['labels'][0] += ' %s' % dfr['labels'][1]
                                match = TABLE_NAME_PATTERN.match(row['labels'][0])
                                if not match:
                                    logging.warn( "Expected a table name at row %i [%s]" % ( row_count, row['labels'][0]  ) )
                                    continue
                            name_dict = match.groupdict()
                            table['name'] = name_dict['name']
                            table['size'] = int(name_dict['size'])
                else: # there's a line number
                    key = utils.generate_stat_key(row['table_id'],row['line'])
                    parent = parent_key = None
                    if row['indent'] > 0:
                        chk_line = row['line']
                        while parent is None and chk_line > 1:
                            chk_line -= 1
                            parent_key = utils.generate_stat_key(row['table_id'],chk_line)
                            chk_parent = table['labels'][parent_key]
                            if chk_parent['indent'] == row['indent'] - 1:
                                parent = chk_parent
                                parent['has_children'] = True
                                parent_key = parent['key']

                    last_processed = {
                        'key': key,
                        'text': row['labels'][row['indent']],
                        'indent': row['indent'],
                        'parent': parent_key,
                        'has_children': False, #maybe! we'll reset this later in the loop if we discover otherwise. look up.
                        'key_2000': KEY_MAPPINGS[key] if key in KEY_MAPPINGS else None,
                    } # keep it around for later

                    table['labels'][key] = last_processed # but also save it...
    # Save final table
    # sanity check:
    for k,v in tables.items():
        if not k:
            print "still have an empty key!"
        else:    
            if k != v['key']:
                raise AssertionError("Keys don't match for k=%s" % k)
            try:
                if len(v['labels']) != v['size']:
                    raise AssertionError("Not enough labels for k=%s expected %i got %i" % (k,v['size'],len(v['labels'])))
            except KeyError:
                print "Unexpectedly missing size for table %s keys: %s" % (k, ','.join(v.keys()))

    collection = utils.get_label_collection()
    collection.remove({ 'dataset': 'SF1' }, safe=True)
    collection.save({ 'dataset': 'SF1', 'tables': tables}, safe=True)

    print 'load_sf_labels_2010:'
    print ' Row count: %i' % row_count
    print ' Skipped: %i' % skipped
    print ' Tables: %i' % len(tables)


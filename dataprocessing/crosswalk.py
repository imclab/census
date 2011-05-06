#!/usr/bin/env python

from pymongo import Connection

import config
import utils

connection = Connection()
db = connection[config.CENSUS_DB]
collection = db[config.GEOGRAPHIES_COLLECTION]
collection_2000 = db[config.GEOGRAPHIES_2000_COLLECTION]

row_count = 0
inserts = 0

for geography in collection.find():
    row_count += 1

    if geography['sumlev'] == config.SUMLEV_TRACT:
        # TODO: execute crosswalk
        pass

    geography_2000 = collection_2000.find_one({ 'geoid': geography['geoid'] })

    if not geography_2000:
        print 'Couldn\'t find matching 2000 geography for %s (%s)' % (geography['metadata']['NAME'], geography['geoid'])

    geography['data']['2000'] = geography_2000['data']['2000']

    collection.save(geography)
    inserts += 1

print 'Row count: %i' % row_count
print 'Inserted: %i' % inserts

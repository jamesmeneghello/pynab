DROP FUNCTION create_nzb(integer);

CREATE OR REPLACE FUNCTION create_nzb (binary_id integer)
	RETURNS integer
AS $$

if 'io' in SD:
	io = SD['io']
else:
	import io
	SD['io'] = io

if 'saxutils' in SD:
	saxutils = SD['saxutils']
else:
	import xml.sax.saxutils
	SD['saxutils'] = xml.sax.saxutils
	saxutils = xml.sax.saxutils

if 'pytz' in SD:
	pytz = SD['pytz']
else:
	import pytz
	SD['pytz'] = pytz

if 'regex' in SD:
	regex = SD['regex']
else:
	import regex
	SD['regex'] = regex

if 'gzip' in SD:
	gzip = SD['gzip']
else:
	import gzip
	SD['gzip'] = gzip
	

BATCH_SIZE = 1

XREF_REGEX = regex.compile('^([a-z0-9\.\-_]+):(\d+)?$', regex.I)

micro_plan = plpy.prepare(
'''
SELECT 
	clean_name, category
FROM
	binaries
WHERE
	id = $1
''', ["integer"])

# 2015-01-07 09:38:33

full_plan = plpy.prepare(
'''
SELECT 
	segments.segment, segments.size, segments.message_id,
	parts.subject, parts.total_segments, 
	to_char(parts.posted, 'YYYY-MM-DD HH24:MI:SS') as posted, 
	binaries.name, binaries.clean_name, binaries.category, binaries.total_parts, binaries.xref, binaries.group_name, binaries.posted_by
FROM
	binaries 
		INNER JOIN parts ON parts.binary_id = binaries.id
		INNER JOIN segments ON segments.part_id = parts.id
		
WHERE
	binaries.id = $1
ORDER BY
	parts.subject, segments.segment

''', ["integer"])

row = plpy.execute(micro_plan, [binary_id], 1)

if row.nrows() > 0:
	# 3.x
	out = io.BytesIO()
	with gzip.GzipFile(fileobj=out, mode='w') as xml:
		xml.write('<?xml version="1.0" encoding="UTF-8"?>\n'
				'<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">\n'
				'<nzb>\n'
				'<head><meta type="category">{}</meta><meta type="name">{}</meta></head>\n'
				.format(row[0]['category'], saxutils.escape(row[0]['clean_name']))
		)

		cursor = plpy.cursor(full_plan, [binary_id])

		while True:
			rows = cursor.fetch(BATCH_SIZE)
			if not rows:
				break
			
			for row in rows:
				if row['segment'] == 1:
					xml.write('<file poster={} date={} subject={}>\n<groups>'.format(
						saxutils.quoteattr(row['posted_by']),
						saxutils.quoteattr(row['posted']),
						saxutils.quoteattr('{0} (1/{1:d})'.format(row['subject'], row['total_segments']))
					))

					# get groups from xref
					groups = []
					raw_groups = row['xref'].split(' ')
					for raw_group in raw_groups:
						result = XREF_REGEX.search(raw_group)
						if result:
							groups.append(result.group(1))

					for group in groups:
						xml.write('<group>{}</group>'.format(group))

					xml.write('</groups>\n<segments>\n')

				# write current segment
				xml.write('<segment bytes="{}" number="{}">{}</segment>\n'.format(
					row['size'],
					row['segment'],
					saxutils.escape(row['message_id'])
				))

				if row['segment'] == row['total_segments']:
					xml.write('</segments>\n</file>\n')

		xml.write('</nzb>')

	insert_plan = plpy.prepare('INSERT INTO nzbs (data) VALUES ($1) RETURNING id', ["bytea"])
	rv = plpy.execute(insert_plan, [out.getvalue()])

	if rv:
		delete_plan = plpy.prepare('DELETE FROM binaries WHERE id = $1', ["integer"])
		plpy.execute(delete_plan, [binary_id])

	return rv[0]['id']

$$ LANGUAGE plpythonu;

--SELECT create_nzb(243);
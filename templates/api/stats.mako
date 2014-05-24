<?xml version="1.0" encoding="UTF-8" ?>
<stats>
    <totals>
        % for label, total in totals.items():
            <total label="${label}" total="${total['total']}" processed="${total['processed']}" failed="${total['failed']}"></total>
        % endfor
    </totals>

    <categories>
        % for category, value in categories:
            <category label="${category.parent.name} > ${category.name}" value="${value}"></category>
        % endfor
    </categories>
</stats>
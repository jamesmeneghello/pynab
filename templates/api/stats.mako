<?xml version="1.0" encoding="UTF-8" ?>
<stats>
    <totals>
        % for total in totals:
            <total label="${total['label']}" total="${total['total']}" processed="${total['processed']}"></total>
        % endfor
    </totals>

    <categories>
        % for (category, value) in categories:
            <category label="${category.parent.name} > ${category.name}" value="${value}"></category>
        % endfor
    </categories>
</stats>
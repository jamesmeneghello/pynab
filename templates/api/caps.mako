<?xml version="1.0" encoding="UTF-8" ?>
    <%!
        import pynab.api
    %>
<caps>
    <server appversion="${app_version}" version="${api_version}" email="${email}"/>
    <limits max="${result_limit}" default="${result_default}"/>

    <registration available="no" open="no"/>

    <searching>
        % if 's|search' in pynab.api.functions:
            <search available="yes"/>
        % endif
        % if 'tv|tvsearch' in pynab.api.functions:
            <tv-search available="yes"/>
        % endif
        % if 'm|movie' in pynab.api.functions:
            <movie-search available="yes"/>
        % endif
        % if 'b|book' in pynab.api.functions:
            <book-search available="yes"/>
        % endif
    </searching>

    <categories>
        % for id, category in sorted(categories.items()):
            <category id="${category['_id']}" name="${category['name']}">
                % for subcategory in category['categories']:
                    <subcat id="${subcategory['_id']}" name="${subcategory['name']}"/>
                % endfor
            </category>
        % endfor
    </categories>
</caps>
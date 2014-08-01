<?xml version="1.0" encoding="UTF-8" ?>\
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
        % for category in categories:
            <category id="${category.id}" name="${category.name}">
                % for subcategory in category.children:
                    <subcat id="${subcategory.id}" name="${subcategory.name}"/>
                % endfor
            </category>
        % endfor
    </categories>
</caps>
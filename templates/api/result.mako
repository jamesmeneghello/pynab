<?xml version="1.0" encoding="UTF-8"?>\
<%!
    import config, sys
    from email import utils
%>
<rss version="2.0" xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/">
<channel>
    <title>${config.api.get('title', 'pynab')}</title>
    <description>${config.api.get('description', '')}</description>
    <link>${get_link('')}</link>\
    % if search:
    <newznab:response offset="${offset}" total="${total}"/>\
    % endif
    % for release in releases:
        <%
            if sys.version_info >= (3,3):
                added_date = release.added.timestamp()
                posted_date = release.posted.timestamp()
            else:
                added_date = int(release.added.strftime("%s"))
                posted_date = int(release.posted.strftime("%s"))
        %>
        <item>
            <title>${release.search_name | x}</title>
            <guid isPermaLink="true">${get_link('/details/' + str(release.id))}</guid>
            <link>${get_link('/api')}?t=g&amp;guid=${release.id}&amp;apikey=${api_key}</link>
            <pubDate>${utils.formatdate(added_date)}</pubDate>
            % if release.category.parent_id:
            <category>${release.category.parent.name} &gt; ${release.category.name}</category>
            % else:
            <category>${release.category.name}</category>
            % endif
            <description>${release.search_name | x}</description>
            <posted>${utils.formatdate(posted_date)}</posted>
            <group>${release.group.name}</group>
            <enclosure url="${get_link('/api')}?t=g&amp;guid=${release.id}&amp;apikey=${api_key}" type="application/x-nzb"></enclosure>
            <grabs>${release.grabs}</grabs>
            <size>${release.size}</size>

            <newznab:attr name="category" value="${release.category.id}"/>
            % if release.category.parent_id:
            <newznab:attr name="category" value="${release.category.parent_id}"/>
            % endif
            % if detail or extended:
            <newznab:attr name="size" value="${release.size}"/>
            % endif
            % if release.tvshow_id:
            <newznab:attr name="rageid" value="${release.tvshow_id}"/>
            % endif
            <newznab:attr name="guid" value="${release.id}"/>
            <newznab:attr name="poster" value="${release.posted_by | x}"/>
            <newznab:attr name="usenetdate" value="${utils.formatdate(posted_date)}"/>
            <newznab:attr name="grabs" value="${release.grabs}"/>
            <newznab:attr name="group" value="${release.group.name}"/>
            <newznab:attr name="size" value="${release.size}"/>
        </item>
    % endfor
    </channel>
</rss>

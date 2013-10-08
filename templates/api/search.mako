<?xml version="1.0" encoding="UTF-8"?>
    <%!
        import config
    %>
<rss version="2.0">

    <channel>
        <title>${config.site['title']}</title>
        <description>${config.site['description']}</description>

        <!-- this pynab tracker does not support the offset argument for direct searches -->
        <!-- works fine for rss feeds, though -->
        <newznab:response offset="${offset}" total="${total}"/>

        % for release in releases:
            <item>
                <title>${release['search_name']}</title>
                <guid isPermaLink="true">/details/${release['id']}</guid>
                <link>
                /api/nzb/${release['id']}</link>
                <pubDate>${release['added']}</pubDate>
                % if 'parent_id' in release['category']:
                    <category>${release['category']['parent']['name']} &gt; ${release['category']['name']}</category>
                % else:
                    <category>${release['category']['name']}</category>
                % endif
                <description>${release['search_name']}</description>
                <enclosure url="/api/nzb/${release['id']}" length="${release['nzb_size']}"
                           type="application/x-nzb-compressed"/>
                <newznab:attr name="category" value="${release['category']['_id']}"/>
                % if 'parent_id' in release['category']:
                    <newznab:attr name="category" value="${release['category']['parent_id']}"/>
                % endif
                % if release.get('size'):
                    <newznab:attr name="size" value="${release['size']}"/>
                % endif
                <newznab:attr name="guid" value="${release['id']}"/>
            </item>
        % endfor

    </channel>
</rss>
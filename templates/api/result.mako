<?xml version="1.0" encoding="UTF-8"?>
    <%!
        import config
    %>
<rss version="2.0">

    <channel>
        <title>${config.site['title']}</title>
        <description>${config.site['description']}</description>

        % if search:
            <!-- this pynab tracker does not support the offset argument for direct searches -->
            <!-- works fine for rss feeds, though -->
            <newznab:response offset="${offset}" total="${total}"/>
        % endif

        % for release in releases:
            <item>
                <title>${release['search_name']}</title>
                <guid isPermaLink="true">/details/${release['id']}&apikey=${api_key}</guid>
                <link>
                /api?t=g&guid=${release['id']}&apikey=${api_key}</link>
                <pubDate>${release['added']}</pubDate>
                % if 'parent_id' in release['category']:
                    <category>${release['category']['parent']['name']} &gt; ${release['category']['name']}</category>
                % else:
                    <category>${release['category']['name']}</category>
                % endif
                <description>${release['search_name']}</description>
                <enclosure url="/api?t=g&guid=${release['id']}&apikey=${api_key}" length="${release['nzb_size']}"
                           type="application/x-nzb"/>
                <newznab:attr name="category" value="${release['category']['_id']}"/>
                % if 'parent_id' in release['category']:
                    <newznab:attr name="category" value="${release['category']['parent_id']}"/>
                % endif
                % if release.get('size'):
                    <newznab:attr name="size" value="${release['size']}"/>
                % endif
                % if detail:
                    <newznab:attr name="size" value="${release['size']}"/>
                    <newznab:attr name="files" value="${release['file_count']}"/>
                    <newznab:attr name="poster" value="${release['posted_by']}"/>
                    <newznab:attr name="grabs" value="${release['grabs']}"/>
                    <newznab:attr name="usenetdate" value="${release['posted']}"/>
                    <newznab:attr name="group" value="${release['group']['name']}"/>
                % endif
                <newznab:attr name="guid" value="${release['id']}"/>
            </item>
        % endfor

    </channel>
</rss>
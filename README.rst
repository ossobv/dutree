dutree :: Disk usage summary
============================

*dutree* shows a summary of the directories/files which take up the most space.

Example usage::

    $ dutree /srv

Annotated output, where only paths of >4G are shown::

     12.1 G  /srv/data/audiofiles/
              ^-- audiofiles contains files/dirs with a total of 12.1G
                  but it does NOT contain a single dir or file larger
                  than 4G.
      4.3 G  /srv/data/callrecordings/unmatched/
      4.5 G  /srv/data/fax/
     17.5 G  /srv/data/playlists/
     34.4 G  /srv/data/twinfield_invoices/1/
      7.8 G  /srv/data/*
               ^-- data contains more files/directories than shown above
                   but those that don't total above 4G are merged into
                   this "leftover" node. That includes /twinfield_invoices/
                   except for the /1/ subdirectory which already has its
                   individual listing.
     32   B  /srv/*
               ^-- there was only /data/ in /srv/, but the directory itself
                   also takes up a tiny bit of space
      -----
     80.6 G  TOTAL (86558511658)

**NOTE**: The directories do not count the size of themselves, only of their
contents. This explains any discrepancies with ``du -sb`` output.


Library usage::

     >>> from dutree import Scanner
     >>> scanner = Scanner('/srv')
     >>> tree = scanner.scan()
     >>> tree.size()
     86558511658

     >>> len(tree.get_leaves())
     7

     >>> leaf0 = tree.get_leaves()[0]
     >>> leaf0.name()
     '/srv/data/audiofiles/'

     >>> leaf0.size() / (1024.0 * 1024 * 1024)
     12.092280263081193

dutree :: Disk usage summary
============================

*dutree* shows a summary of the directories/files which take up the most
space.

Instead of showing *only the root of the files* with sizes, or the
details of *every file*, it shows *only the paths taking up the most
space*.

Example usage::

    $ dutree /srv

Annotated output, where only paths of >5% of the total size are shown
(which is about 4GB for this dataset)::

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
                   this "leftover" node. that includes everything in
                   /twinfield_invoices/ except for the /1/ subdirectory
                   which has its individual listing above.
     32   B  /srv/*
               ^-- only /data/ is in /srv/, but the directory itself also
                   takes up a tiny bit of space
      -----
     80.6 G  TOTAL (86558511658)

**NOTE**: The directories do not count the size of themselves, only of
their contents. This explains any discrepancies with ``du -sb`` output.

**NOTE**: On filesystems with built-in compression (like ZFS) or with many
sparse files, you may want to check the --count-blocks option. This
should better reflect the actual used size (and align with ``du -sh``).


Library usage::

    >>> from dutree import Scanner
    >>> scanner = Scanner('/srv')
    >>> tree = scanner.scan(use_apparent_size=True)
    >>> tree.app_size()
    86558511658

    >>> len(tree.get_leaves())
    7

    >>> leaf0 = tree.get_leaves()[0]
    >>> leaf0.name()
    '/srv/data/audiofiles/'

    >>> leaf0.app_size() / (1024.0 * 1024 * 1024)
    12.092280263081193


History
-------

* v1.6

  - **Fix so the tests work with Python 3 as well.**
  - **Fix grave bugs with real size.**
    The real size calculation was wrong sometimes, it raised assertion
    sometimes and the leaf count would be off sometimes.

* v1.5

  - **Add apparent vs. real size.**
    Deprecates ``node.size()``. Use ``node.app_size()`` instead.
    Get the real used size using ``node.use_size()``.
    Group by real used size by passing ``use_apparent_size=False`` to
    ``scan()``.
  - **Don't die if we cannot enter directories.**

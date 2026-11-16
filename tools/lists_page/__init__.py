# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Write ``docs/lists.md``, the page of the lists that ``resolve()`` reads
(roadmap item 55), from the code objects: ``python -m tools.lists_page``.

``evidence`` holds what the lists themselves do not record (where a row
comes from, how many packages declare it); ``rules`` the named rules;
``render`` the page. ``tests/test_lists_page.py`` fails when the page and the
code differ."""

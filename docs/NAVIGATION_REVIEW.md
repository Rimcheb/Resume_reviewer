# Navigation review follow-up (#113)

Shared navigation styles live in style.css and use the shared spacing, shape and
color tokens. The current page uses a filled primary background; keyboard focus
has a separate offset outline, including on the current page.

Integrated the updated #112 and role-alias matching from #114. The list keeps its
category dropdown and owner guidance; detail links preserve the canonical category
and page in return_to. Back destinations normalize known legacy aliases and reject
unknown categories instead of generating broken links. Tests exercise the complete
filtered page-two list → detail → Back destination alongside safe redirects and
CSRF-protected logout.

#114 remains a separately reviewed PR; it is included here as an integration
dependency, and its original branch/history is preserved.

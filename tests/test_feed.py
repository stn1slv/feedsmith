"""Tests for the Atom feed builder."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from feedsmith.feed import build_atom

ATOM = "{http://www.w3.org/2005/Atom}"


def test_build_atom_snapshot(sample_meta, sample_posts, snapshot):
    assert build_atom(sample_meta, sample_posts) == snapshot


def test_build_atom_structure(sample_meta, sample_posts):
    root = ET.fromstring(build_atom(sample_meta, sample_posts))
    assert root.tag == f"{ATOM}feed"
    assert root.findtext(f"{ATOM}title") == "Example Blog"

    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 2
    # Newest entry first (caller sorts; builder preserves order).
    assert entries[0].findtext(f"{ATOM}title") == "Second & newest post"
    assert entries[0].find(f"{ATOM}author/{ATOM}name").text == "Ada Lovelace"


def test_empty_feed_has_updated_timestamp(sample_meta):
    root = ET.fromstring(build_atom(sample_meta, []))
    assert root.findtext(f"{ATOM}updated") is not None
    assert root.findall(f"{ATOM}entry") == []

"""Fixed Tamil and Hindi RTI glossary: what the prompts teach and what the eval measures."""

from unseal.llm.glossary import glossary_block, load_glossary, missed_terms, term_errors


def test_every_entry_is_complete_and_self_consistent() -> None:
    entries = load_glossary()
    assert len(entries) >= 12
    assert len({e.concept for e in entries}) == len(entries)
    for entry in entries:
        assert entry.en, entry.concept
        assert all(phrase == phrase.lower() for phrase in entry.en)
        for local in (entry.ta, entry.hi):
            assert local.match[0] in local.term  # the main stem comes from the preferred term
            # Legal terms carry provenance, like the rules data: where it came from, how sure.
            assert local.source.strip(), entry.concept
            assert local.confidence in {"high", "medium", "low"}
            for avoided in local.avoid:  # an avoided form never contains an accepted one
                assert not any(stem in avoided for stem in local.match), (entry.concept, avoided)


def test_block_lists_each_concept_in_the_target_language_only() -> None:
    tamil, hindi = glossary_block("ta"), glossary_block("hi")
    assert "- certified copy: சான்றளிக்கப்பட்ட நகல்" in tamil
    assert "- certified copy: प्रमाणित प्रति" in hindi
    assert "प्रमाणित" not in tamil
    assert len(tamil.splitlines()) == len(load_glossary())


def test_term_errors_find_known_wrong_variants() -> None:
    assert term_errors("தேர்வின் சான்றிதழ் நகலை வழங்கவும்", "ta") == ["certified copy: சான்றிதழ் நகல"]
    assert term_errors("कृपया प्रमाणित प्रति दें", "hi") == []


def test_missed_terms_accept_inflections_and_nukta_spellings() -> None:
    source = "Certified copy of the work order and the file notings"
    tamil = "பணி ஆணையின் சான்றளிக்கப்பட்ட நகல்களை வழங்கவும்"  # case endings on both terms
    assert missed_terms(tamil, "ta", source) == ["file notings"]
    hindi = "कार्य आदेश की प्रमाणित प्रतियाँ और फाइल नोटिंग"  # फाइल without the nukta
    assert missed_terms(hindi, "hi", source) == []
    assert missed_terms("anything at all", "ta", "nothing from the glossary here") == []
